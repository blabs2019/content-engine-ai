import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

ACTOR_ID = "h7sDV53CddomktSi5"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    title = raw.get("title") or ""
    hashtags = raw.get("hashtags") or []
    return {
        "source": "youtube",
        "source_id": str(raw.get("id") or raw.get("videoId", "")),
        "vertical_id": input.vertical_id,
        "content_type": "video",
        "title": title[:500] if title else "Untitled",
        "body": raw.get("description"),
        "url": raw.get("url"),
        "file_urls": [u for u in [raw.get("thumbnailUrl"), raw.get("thumbnail")] if u],
        "raw_data": raw,
        "tags": list(set(input.keywords + hashtags)),
        "region": "US",
        "platform_metadata": {
            "views": raw.get("viewCount", 0),
            "likes": raw.get("likes", 0) or raw.get("likeCount", 0),
            "comments": raw.get("commentsCount", 0) or raw.get("commentCount", 0),
            "duration": raw.get("duration"),
            "channel_name": raw.get("channelName"),
            "channel_url": raw.get("channelUrl"),
            "subscribers": raw.get("numberOfSubscribers", 0) or raw.get("subscribers", 0),
            "published_at": raw.get("publishedAt") or raw.get("date"),
        },
        "published_at": safe_published_at(raw.get("publishedAt") or raw.get("date")),
        "is_trending": False,
    }


@activity.defn
async def collect_youtube(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting YouTube data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "searchKeywords": keyword,
            "maxResults": 50,
            "gl": "US",
            "hl": "en",
            "type": "video",
            "uploadDate": "month",
        })

        normalized = [_normalize(raw, input) for raw in items]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"YouTube: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="youtube",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"YouTube collection failed: {e}")
        return CollectionResult(
            platform="youtube",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
