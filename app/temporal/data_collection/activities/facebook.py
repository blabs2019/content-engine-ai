import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

ACTOR_ID = "Ew2lyICEnHMcqRo6T"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    text = raw.get("message") or ""
    author = raw.get("author") or {}

    # Extract direct media links
    file_urls = []
    image = raw.get("image")
    if isinstance(image, dict) and image.get("uri"):
        file_urls.append(image["uri"])
    if raw.get("video"):
        file_urls.append(raw["video"])
    if raw.get("video_thumbnail"):
        file_urls.append(raw["video_thumbnail"])
    for album_img in (raw.get("album_preview") or []):
        if isinstance(album_img, dict) and album_img.get("uri"):
            file_urls.append(album_img["uri"])

    return {
        "source": "facebook",
        "source_id": str(raw.get("post_id", "")),
        "vertical_id": input.vertical_id,
        "content_type": "post",
        "title": text[:500] if text else "Untitled",
        "body": text,
        "url": raw.get("url"),
        "file_urls": file_urls,
        "raw_data": raw,
        "tags": input.keywords or [],
        "region": "US",
        "platform_metadata": {
            "reactions": raw.get("reactions_count", 0),
            "reactions_breakdown": raw.get("reactions", {}),
            "comments": raw.get("comments_count", 0),
            "shares": raw.get("reshare_count", 0),
            "post_id": raw.get("post_id"),
            "author_name": author.get("name") if isinstance(author, dict) else author,
            "author_url": author.get("url") if isinstance(author, dict) else None,
            "timestamp": raw.get("timestamp"),
        },
        "published_at": safe_published_at(raw.get("timestamp")),
        "is_trending": False,
    }


@activity.defn
async def collect_facebook(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting Facebook data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "location_uid": "United States",
            "query": keyword,
            "maxResults": 50
        })

        normalized = [_normalize(raw, input) for raw in items]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Facebook: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="facebook",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Facebook collection failed: {e}")
        return CollectionResult(
            platform="facebook",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
