"""
Content Engine — Trending Intelligence Integration

Fetches real-time data directly from the database (CollectedData table).

Data structure produced:
    channels: {instagram, youtube, twitter, reddit, facebook, linkedin}
        each channel: {trending: [...], all_time_favourite: [...]}
    news: [...]
    meta_ads: [...]
    hashtags: [...]

Vertical IDs are resolved automatically via the Vertical Registry.
"""

from typing import Dict, List, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

SOCIAL_CHANNELS = {"facebook", "twitter", "reddit", "youtube", "linkedin", "instagram"}


class TrendingIntelligence:
    """
    Fetches trending data directly from the database.

    Usage:
        trending = TrendingIntelligence()
        data = trending.fetch_all(vertical='insurance', platform='facebook')

        data['social_pulse']    → viral posts (for Stage 2 style references)
        data['topics']          → trending topics (for Stage 1 topic ideas)
        data['news']            → industry news (for Stage 1 timely triggers)
        data['hashtags']        → trending hashtags (for Stage 2 hashtag guidance)
    """

    def fetch_all(self, vertical: str, platform: str = None) -> Dict[str, Any]:
        try:
            logger.info(f"[Trending] Fetching trending data for vertical='{vertical}', platform='{platform}'")
            raw = self._fetch_raw(vertical)
            if not raw:
                logger.warning(f"[Trending] No raw data found for vertical='{vertical}'")
                return self._empty_response()

            channels = raw.get('channels', {})
            logger.info(
                f"[Trending] Raw data loaded — channels={list(channels.keys())}, "
                f"news={len(raw.get('news', []))}, hashtags={len(raw.get('hashtags', []))}"
            )

            result = {
                'social_pulse': self._extract_social_pulse(raw, platform),
                'topics': self._extract_topics(raw),
                'news': self._extract_news(raw),
                'hashtags': self._extract_hashtags(raw),
            }

            logger.info(
                f"[Trending] Final result — social_pulse={len(result['social_pulse'])}, "
                f"topics={len(result['topics'])}, news={len(result['news'])}, "
                f"hashtags={len(result['hashtags'])}"
            )
            return result
        except Exception as e:
            logger.error(f"[Trending] Failed to fetch trending intelligence: {type(e).__name__}: {e}", exc_info=True)
            return self._empty_response()

    def _fetch_raw(self, vertical: str) -> Optional[Dict]:
        """Fetch raw data directly from the database."""
        from .vertical_registry import VerticalRegistry

        registry = VerticalRegistry()
        vertical_id = registry.get_id(vertical)
        if not vertical_id:
            logger.warning(f"[Trending] Vertical '{vertical}' not found in registry, skipping trending fetch")
            return None

        try:
            from app.database import SyncSessionLocal
            from app.models.collected_data import CollectedData

            session = SyncSessionLocal()
            try:
                rows = (
                    session.query(CollectedData)
                    .filter(CollectedData.vertical_id == vertical_id)
                    .order_by(CollectedData.reach_score.desc())
                    .all()
                )
                logger.info(f"[Trending] Queried {len(rows)} rows from collected_data for vertical_id={vertical_id}")
                return self._rows_to_raw_format(rows)
            finally:
                session.close()
        except Exception as e:
            logger.error(f"[Trending] Failed to query collected_data (vertical_id={vertical_id}): {type(e).__name__}: {e}", exc_info=True)
            return None

    def _rows_to_raw_format(self, rows) -> Dict:
        """Convert DB rows to the dict structure that _extract_* methods expect."""
        channels = {}
        news = []
        hashtags = []

        for row in rows:
            try:
                source = getattr(row, 'source', None)
                if not source:
                    continue

                # Hashtag metadata row
                if getattr(row, 'content_type', '') == "tags":
                    try:
                        names = json.loads(row.body) if row.body else []
                        raw_hashtags = (row.raw_data or {}).get("hashtags", [])
                        name_to_count = {
                            h.get("name", ""): h.get("media_count", 0) for h in raw_hashtags
                        }
                        for name in names:
                            hashtags.append({
                                'name': name,
                                'posts_count': int(name_to_count.get(name, 0)),
                            })
                    except Exception as e:
                        logger.warning(f"[Trending] Failed to parse hashtag row (id={getattr(row, 'id', '?')}, source={source}): {type(e).__name__}: {e}")
                    continue

                # Skip keyword/title insight rows
                if getattr(row, 'content_type', '') in ("keyword", "title"):
                    continue

                # Build item dict — safely access each field
                item = {
                    'source_id': getattr(row, 'source_id', None),
                    'title': getattr(row, 'title', '') or '',
                    'body': getattr(row, 'body', None),
                    'url': getattr(row, 'url', None),
                    'tags': getattr(row, 'tags', None) or [],
                    'platform_metadata': getattr(row, 'platform_metadata', None) or {},
                    'published_at': str(row.published_at) if getattr(row, 'published_at', None) else '',
                    'reach_score': getattr(row, 'reach_score', 0) or 0,
                    'is_trending': getattr(row, 'is_trending', False),
                    'is_all_time_favourite': getattr(row, 'is_all_time_favourite', False),
                }

                if source == "google_news":
                    news.append(item)
                elif source == "meta_ads":
                    pass  # Not used by trending extraction
                elif source in SOCIAL_CHANNELS:
                    if source not in channels:
                        channels[source] = {'trending': [], 'all_time_favourite': []}
                    if row.is_trending:
                        channels[source]['trending'].append(item)
                    if row.is_all_time_favourite:
                        channels[source]['all_time_favourite'].append(item)
            except Exception as e:
                logger.warning(
                    f"[Trending] Skipping row (id={getattr(row, 'id', '?')}, source={getattr(row, 'source', '?')}, "
                    f"content_type={getattr(row, 'content_type', '?')}): {type(e).__name__}: {e}"
                )
                continue

        return {
            'channels': channels,
            'news': news,
            'meta_ads': [],
            'hashtags': hashtags,
        }

    # ── Extract Social Pulse (viral posts for Stage 2 style references) ──

    def _extract_social_pulse(self, raw: Dict, platform: str = None) -> List[Dict]:
        """
        Flatten all channel posts into a unified social pulse list.
        Sorted by reach_score descending. These teach the AI style and hooks.
        """
        posts = []
        channels = raw.get('channels', {})

        for channel_name, channel_data in channels.items():
            if platform and not self._platform_matches_channel(platform, channel_name):
                continue

            for post in channel_data.get('trending', []):
                normalized = self._normalize_post(post, channel_name)
                if normalized:
                    posts.append(normalized)

            for post in channel_data.get('all_time_favourite', []):
                normalized = self._normalize_post(post, channel_name)
                if normalized:
                    posts.append(normalized)

        # Deduplicate by source_id
        seen = set()
        unique = []
        for p in posts:
            key = p.get('source_id', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(p)

        unique.sort(key=lambda x: x.get('engagement', {}).get('reach_score', 0), reverse=True)
        result = unique[:20]

        logger.info(f"Extracted {len(result)} social pulse posts (from {len(unique)} unique)")
        return result

    def _normalize_post(self, post: Dict, channel: str) -> Optional[Dict]:
        text = post.get('body') or post.get('title') or ''
        if not text or len(text.strip()) < 10:
            return None

        meta = post.get('platform_metadata', {})
        engagement = self._extract_engagement(meta, channel)
        account = self._extract_account(meta, channel)

        return {
            'id': post.get('source_id', ''),
            'source_id': post.get('source_id', ''),
            'post_text': text[:600],
            'hook_line': (text.split('\n')[0] or '')[:200],
            'platform': channel,
            'format': meta.get('type', 'post'),
            'account': account,
            'engagement': {
                'views': engagement.get('views', 0),
                'likes': engagement.get('likes', 0),
                'comments': engagement.get('comments', 0),
                'shares': engagement.get('shares', 0),
                'reach_score': post.get('reach_score', 0),
            },
            'posted_at': post.get('published_at', ''),
            'is_viral': post.get('is_trending', False),
            'is_all_time': post.get('is_all_time_favourite', False),
            'tags': post.get('tags', []),
            'url': post.get('url', ''),
        }

    def _extract_engagement(self, meta: Dict, channel: str) -> Dict:
        extractors = {
            'instagram': lambda m: {'views': 0, 'likes': m.get('likes', 0), 'comments': m.get('comments', 0), 'shares': 0},
            'youtube': lambda m: {'views': m.get('views', 0), 'likes': m.get('likes', 0), 'comments': m.get('comments', 0), 'shares': 0},
            'twitter': lambda m: {'views': m.get('views', 0), 'likes': m.get('likes', 0), 'comments': m.get('replies', 0), 'shares': m.get('retweets', 0)},
            'reddit': lambda m: {'views': 0, 'likes': m.get('upvotes', 0), 'comments': m.get('comments', 0), 'shares': 0},
            'facebook': lambda m: {'views': 0, 'likes': m.get('reactions', 0), 'comments': m.get('comments', 0), 'shares': 0},
            'linkedin': lambda m: {'views': 0, 'likes': m.get('likes', 0), 'comments': m.get('comments', 0), 'shares': m.get('shares', 0)},
        }
        return extractors.get(channel, lambda m: {'views': 0, 'likes': 0, 'comments': 0, 'shares': 0})(meta)

    def _extract_account(self, meta: Dict, channel: str) -> str:
        account_fields = {
            'instagram': ('owner_username', '@'),
            'youtube': ('channel_name', ''),
            'twitter': ('author_username', '@'),
            'reddit': ('username', 'u/'),
            'facebook': ('author_name', ''),
            'linkedin': ('author_name', ''),
        }
        field, prefix = account_fields.get(channel, ('', ''))
        value = meta.get(field, '')
        return f"{prefix}{value}" if value else ''

    def _platform_matches_channel(self, platform: str, channel: str) -> bool:
        return platform.lower() == channel.lower()

    # ── Extract Topics ──

    def _extract_topics(self, raw: Dict) -> List[Dict]:
        topics = []
        channels = raw.get('channels', {})

        for channel_name, channel_data in channels.items():
            for post in channel_data.get('trending', []):
                if post.get('reach_score', 0) > 100:
                    title = post.get('title', '')
                    if title and len(title) > 15:
                        topics.append({
                            'id': post.get('source_id', ''),
                            'topic': title[:200],
                            'growth_percent': 0,
                            'monthly_volume': 0,
                            'relevance_score': min(post.get('reach_score', 0) / 10000, 10),
                            'vertical': '',
                            'category': channel_name,
                            'source': channel_name,
                        })

        topics.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return topics[:15]

    # ── Extract News ──

    def _extract_news(self, raw: Dict) -> List[Dict]:
        news_items = raw.get('news', [])
        result = []
        for item in news_items:
            meta = item.get('platform_metadata', {})
            result.append({
                'id': item.get('source_id', ''),
                'title': item.get('title', ''),
                'source': meta.get('source_name', ''),
                'url': item.get('url', ''),
                'published_at': item.get('published_at', ''),
                'relevance_score': item.get('reach_score', 0),
                'vertical': '',
                'summary': (item.get('body') or '')[:300],
            })
        return result[:10]

    # ── Extract Hashtags ──

    def _extract_hashtags(self, raw: Dict) -> List[Dict]:
        hashtags = raw.get('hashtags', [])
        return [
            {
                'id': h.get('name', ''),
                'hashtag': f"#{h.get('name', '')}",
                'vertical': '',
                'growth_percent': 0,
                'monthly_volume': h.get('posts_count', 0),
                'platforms': [],
            }
            for h in hashtags
        ]

    def _empty_response(self) -> Dict[str, List]:
        return {
            'social_pulse': [],
            'topics': [],
            'news': [],
            'hashtags': [],
        }
