"""
Content Engine — Reference Resolver

Resolves what the Stage 2 Writer sees:
    Layer A: Content Type Brief (what the post's JOB is)
    Layer B: Style References (viral posts showing what works in this vertical)

Key design: Reference posts are style references by VERTICAL, not content type.
They teach hook craft and energy for an industry. The content type brief teaches
the post's purpose/structure. The AI merges both.

Integration:
    Learnings come from the standalone content-fine-tuning service via HTTP API.
    Falls back to static briefs if service is unavailable.
"""

from typing import Dict, List, Any, Optional, Set
from .models import ContentTypeBrief, ReferencePost, CuratedItem
import logging
import threading

logger = logging.getLogger(__name__)


def _get_fine_tuning_url() -> str:
    from app.config import get_settings
    return get_settings().CONTENT_FINE_TUNING_URL


# Track which verticals we've already triggered auto-generation for (per process lifetime)
_auto_gen_triggered: Set[str] = set()
_auto_gen_lock = threading.Lock()


def _fetch_composed_brief(content_type: str = None, vertical: str = None,
                           platform: str = None, token_budget: int = 2000) -> Optional[str]:
    """
    Fetch composed brief from the standalone content-fine-tuning service.
    Returns the brief text, or None if service is unavailable.
    """
    fine_tuning_url = _get_fine_tuning_url()
    if not fine_tuning_url:
        return None

    try:
        import requests

        params = {'token_budget': token_budget}
        if content_type:
            params['content_type'] = content_type
        if vertical:
            params['vertical'] = vertical
        if platform:
            params['platform'] = platform

        response = requests.get(
            f"{fine_tuning_url}/api/compose-brief",
            params=params,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            brief = data.get('brief', '')
            if brief and 'No specific learnings available' not in brief:
                logger.info(
                    f"Fetched composed brief from fine-tuning service: "
                    f"{data.get('total_learnings_matched', '?')} learnings"
                )
                return brief

        return None

    except Exception as e:
        logger.warning(f"Fine tuning service unavailable: {str(e)}")
        return None


def _trigger_auto_learnings(vertical: str):
    """
    Fire-and-forget: trigger learnings generation for a vertical that has none.
    Runs in a background thread so it doesn't block content generation.
    """
    fine_tuning_url = _get_fine_tuning_url()
    if not fine_tuning_url:
        return

    with _auto_gen_lock:
        if vertical in _auto_gen_triggered:
            return
        _auto_gen_triggered.add(vertical)

    def _generate():
        try:
            import requests
            logger.info(f"Auto-generating learnings for vertical '{vertical}' (first request)")
            response = requests.post(
                f"{fine_tuning_url}/api/analyze-from-trending",
                json={
                    'vertical': vertical,
                    'ai_provider': 'claude',
                    'viral_limit': 20,
                    'non_viral_limit': 10,
                },
                timeout=120
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get('learnings_generated', len(data.get('learnings', [])))
                logger.info(
                    f"Auto-generated {count} learnings for '{vertical}'. "
                    f"They are auto-approved at medium confidence. "
                    f"Next request for this vertical will use them."
                )

                # Auto-approve all generated learnings at medium confidence
                learnings = data.get('learnings', [])
                if learnings:
                    ids = [l['id'] for l in learnings if l.get('id')]
                    if ids:
                        requests.post(
                            f"{fine_tuning_url}/api/learnings/bulk-approve",
                            json={'learning_ids': ids, 'confidence': 'medium', 'reviewed_by': 'auto_gen'},
                            timeout=10
                        )
                        logger.info(f"Auto-approved {len(ids)} learnings for '{vertical}'")
            else:
                logger.warning(
                    f"Auto-learnings generation failed for '{vertical}': "
                    f"{response.status_code} {response.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"Auto-learnings generation failed for '{vertical}': {str(e)}")

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()


class ReferenceResolver:
    """
    Resolves reference material for the Stage 2 Writer.
    """

    def get_type_brief(self, content_type: str, vertical: str = None,
                        platform: str = None) -> str:
        """
        Layer A: Get the content brief for a content type + vertical.

        Waterfall:
        1. Composed learnings from content-fine-tuning service (HTTP API)
        2. Static briefs from content_engine_type_briefs table
        3. Hardcoded defaults (cold start)
        """
        # Tier 1: Composed learnings via HTTP API
        composed = _fetch_composed_brief(content_type, vertical, platform)
        if composed:
            logger.info(f"Using composed learnings brief for {content_type}/{vertical}")
            return composed

        # No learnings found — trigger background auto-generation for next time
        if _get_fine_tuning_url() and vertical:
            _trigger_auto_learnings(vertical)

        from app.database import SyncSessionLocal
        session = SyncSessionLocal()
        try:
            # Tier 2: Vertical-specific static brief
            if vertical:
                brief = session.query(ContentTypeBrief).filter_by(
                    content_type=content_type, vertical=vertical, active=True
                ).first()
                if brief:
                    return brief.brief_text

            # Tier 3: Universal static brief
            brief = session.query(ContentTypeBrief).filter_by(
                content_type=content_type, vertical=None, active=True
            ).first()
            if brief:
                return brief.brief_text
        finally:
            session.close()

        # Tier 4: Hardcoded defaults
        return self._default_briefs().get(content_type,
            f"This is a {content_type} post. Follow the general principles of good content.")

    def get_style_references(self, vertical: str, platform: str = None) -> List[Dict]:
        """
        Layer B: Get ALL active style reference posts for this vertical + platform.
        """
        from app.database import SyncSessionLocal
        session = SyncSessionLocal()
        try:
            posts = []
            seen_ids = set()

            # Tier 1: Exact match (vertical + platform)
            if platform:
                tier1 = session.query(ReferencePost).filter_by(
                    vertical=vertical, platform=platform, active=True
                ).all()
                for p in tier1:
                    if p.id not in seen_ids:
                        posts.append(p.to_dict())
                        seen_ids.add(p.id)

            # Tier 2: Vertical match (any platform)
            tier2 = session.query(ReferencePost).filter_by(
                vertical=vertical, active=True
            ).filter(ReferencePost.platform.is_(None)).all()
            for p in tier2:
                if p.id not in seen_ids:
                    posts.append(p.to_dict())
                    seen_ids.add(p.id)

            # Tier 3: Universal (no vertical, no platform)
            tier3 = session.query(ReferencePost).filter_by(
                vertical=None, active=True
            ).all()
            for p in tier3:
                if p.id not in seen_ids:
                    posts.append(p.to_dict())
                    seen_ids.add(p.id)

            logger.info(f"Resolved {len(posts)} style references for {vertical}/{platform}")
            return posts
        finally:
            session.close()

    def get_curated_references(self, vertical: str) -> List[Dict]:
        """Get curated items tagged as style references by humans."""
        from app.database import SyncSessionLocal
        session = SyncSessionLocal()
        try:
            items = session.query(CuratedItem).filter_by(
                vertical=vertical, use_as_reference=True, active=True
            ).all()
            return [item.to_dict() for item in items]
        finally:
            session.close()

    def get_curated_topics(self, vertical: str) -> List[Dict]:
        """Get curated items tagged as must-use topics by humans."""
        from app.database import SyncSessionLocal
        session = SyncSessionLocal()
        try:
            items = session.query(CuratedItem).filter_by(
                vertical=vertical, use_as_topic=True, active=True
            ).all()
            return [item.to_dict() for item in items]
        finally:
            session.close()

    def build_writer_context(self, content_type: str, vertical: str,
                              platform: str = None,
                              trending_social_pulse: List[Dict] = None,
                              trending_hashtags: List[Dict] = None) -> Dict[str, Any]:
        """Build the complete writer context for a single post."""
        # Layer A: Content type brief
        type_brief = self.get_type_brief(content_type, vertical=vertical, platform=platform)

        # Layer B: Style references (merge DB + curated + trending)
        style_refs = []

        # From reference library DB
        db_refs = self.get_style_references(vertical, platform)
        style_refs.extend(db_refs)

        # From human-curated items
        curated_refs = self.get_curated_references(vertical)
        for item in curated_refs:
            style_refs.append({
                'post_text': item['content'],
                'source': 'curated',
                'engagement_data': item.get('engagement_data'),
            })

        # From trending social pulse (if provided)
        if trending_social_pulse:
            for pulse in trending_social_pulse:
                style_refs.append({
                    'post_text': pulse.get('post_text', ''),
                    'hook_line': pulse.get('hook_line', ''),
                    'source': 'trending_viral',
                    'source_account': pulse.get('account', ''),
                    'engagement_views': pulse.get('engagement', {}).get('views', 0),
                    'engagement_likes': pulse.get('engagement', {}).get('likes', 0),
                })

        # Format trending hashtags
        hashtag_list = []
        if trending_hashtags:
            hashtag_list = [h.get('hashtag', '') for h in trending_hashtags[:15]]

        return {
            'type_brief': type_brief,
            'style_references': style_refs,
            'trending_hashtags': hashtag_list,
        }

    def format_style_references_for_prompt(self, style_refs: List[Dict]) -> str:
        """Format style references into a prompt-ready string."""
        if not style_refs:
            return "(No style references available. Write in a natural, engaging voice.)"

        lines = []
        for idx, ref in enumerate(style_refs, 1):
            post_text = ref.get('post_text', '')
            if not post_text:
                continue

            if len(post_text) > 500:
                post_text = post_text[:500] + "..."

            engagement = ""
            views = ref.get('engagement_views')
            likes = ref.get('engagement_likes')
            if views or likes:
                parts = []
                if views:
                    parts.append(f"{views:,} views")
                if likes:
                    parts.append(f"{likes:,} likes")
                engagement = f" ({', '.join(parts)})"

            account = ref.get('source_account', '')
            account_str = f" — {account}" if account else ""

            lines.append(f"---\n{post_text}\n{account_str}{engagement}\n---")

        return '\n'.join(lines) if lines else "(No style references available.)"

    @staticmethod
    def _default_briefs() -> Dict[str, str]:
        """Default content type briefs — used when DB has no data."""
        return {
            'transformation': (
                "This post shows a visible change — before and after, problem and solution. "
                "The work is the story. The reader should feel the problem's weight, "
                "then feel the relief of the fix."
            ),
            'educational': (
                "This post teaches the audience one useful thing. No selling. Pure value. "
                "The reader should think 'I didn't know that' and want to screenshot it. "
                "Reveal a hidden risk, common mistake, or little-known fact."
            ),
            'social_proof': (
                "This post tells a real client's story — not just a star rating. "
                "Start with the client's crisis, not your solution. "
                "The reader should think 'they helped someone like me.'"
            ),
            'community': (
                "This post references something hyper-local — a neighborhood, event, or landmark. "
                "It builds 'one of us' feeling. The reader should feel belonging and pride. "
                "Name the specific place, not just the city."
            ),
            'soft_promotional': (
                "This post introduces a service or offer but leads with value, not price. "
                "Value first, offer second, always. The reader should get something useful "
                "before they even realize there's an offer attached."
            ),
            'behind_the_scenes': (
                "This post shows the unglamorous, unpolished, real side of the business. "
                "Smartphone quality wins over polished production. "
                "The reader should feel authenticity and connection — 'these are real people.'"
            ),
            'scenario_story': (
                "This post paints a vivid 'what if this happened to you' scene. "
                "No real client names. The reader should see themselves in the scenario. "
                "Create emotional connection to an otherwise dry topic."
            ),
            'authority_opinion': (
                "This post takes a clear, contrarian stance on something in the industry. "
                "Not educational — opinionated. The reader should think 'I never thought of it that way.' "
                "Challenge common beliefs with specific proof."
            ),
            'origin_network': (
                "This post celebrates the people, moments, and places that built the business. "
                "Named individuals, specific stories. The reader should feel nostalgia and loyalty. "
                "Triggers Circle 1-2 engagement which ignites the algorithm."
            ),
            'seasonal_timely': (
                "This post connects the business to a season, holiday, or cultural moment "
                "in a way that's relevant to their service — not just 'Happy Thanksgiving.' "
                "The reader should feel urgency and relevance — 'this applies to me RIGHT NOW.'"
            ),
            'human_moments': (
                "This post shows the real people behind the business — a birthday, anniversary, "
                "new hire, team gathering. No selling. No educating. Pure humanity. "
                "The reader should feel warmth — like a text from someone who genuinely means it."
            ),
        }
