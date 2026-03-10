import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

ACTOR_ID = "eWUEW5YpCaCBAa0Zs"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    title = raw.get("title") or ""
    return {
        "source": "google_news",
        "source_id": str(raw.get("guid") or raw.get("link") or ""),
        "vertical_id": input.vertical_id,
        "content_type": "article",
        "title": title[:500] if title else "Untitled",
        "body": None,
        "url": raw.get("link") or raw.get("loadedUrl"),
        "file_urls": [u for u in [raw.get("image")] if u],
        "raw_data": raw,
        "tags": input.keywords or [],
        "region": "US",
        "platform_metadata": {
            "source_name": raw.get("source"),
            "source_url": raw.get("sourceUrl"),
            "published_at": raw.get("publishedAt"),
            "rss_link": raw.get("rssLink"),
            "loaded_url": raw.get("loadedUrl"),
        },
        "published_at": safe_published_at(raw.get("publishedAt")),
        "is_trending": False,
    }


@activity.defn
async def collect_google_news(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting Google News data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "query": keyword,
            "language": "US:en",
            "maxItems": 50,
            "fetchArticleDetails": True,
            "proxyConfiguration": {"useApifyProxy": True},
        })

        # Filter out items without a title or link
        valid_items = [raw for raw in items if raw.get("title") and raw.get("link")]
        logger.info(f"Google News: {len(items)} raw items, {len(valid_items)} valid articles after filtering")

        normalized = [_normalize(raw, input) for raw in valid_items]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Google News: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="google_news",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Google News collection failed: {e}")
        return CollectionResult(
            platform="google_news",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
