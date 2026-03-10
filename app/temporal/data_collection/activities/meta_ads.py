import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync

ACTOR_ID = "bo5X18oGenWEV9vVo"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    snapshot = raw.get("snapshot") or {}
    body = snapshot.get("body") or {}
    text = body.get("text") or ""

    # Collect image URLs from snapshot
    images = snapshot.get("images") or []
    file_urls = [img["original_image_url"] for img in images if img.get("original_image_url")]

    # Collect video URLs from snapshot
    videos = snapshot.get("videos") or []
    for vid in videos:
        if vid.get("video_hd_url"):
            file_urls.append(vid["video_hd_url"])
        elif vid.get("video_sd_url"):
            file_urls.append(vid["video_sd_url"])

    return {
        "source": "meta_ads",
        "source_id": str(raw.get("ad_archive_id", "")),
        "vertical_id": input.vertical_id,
        "content_type": "ad",
        "title": text[:500] if text else "Untitled",
        "body": text,
        "url": snapshot.get("link_url"),
        "file_urls": file_urls,
        "raw_data": raw,
        "tags": input.keywords or [],
        "region": "US",
        "platform_metadata": {
            "page_name": snapshot.get("page_name"),
            "page_id": raw.get("page_id"),
            "cta_text": snapshot.get("cta_text"),
            "publisher_platform": raw.get("publisher_platform", []),
            "start_date": raw.get("start_date"),
            "end_date": raw.get("end_date"),
            "is_active": raw.get("is_active"),
            "display_format": snapshot.get("display_format"),
            "collation_count": raw.get("collation_count", 0),
            "page_like_count": snapshot.get("page_like_count", 0),
            "page_categories": snapshot.get("page_categories", []),
        },
        "published_at": safe_published_at(raw.get("start_date")),
        "is_trending": False,
    }


@activity.defn
async def collect_meta_ads(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting Meta Ads data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "query": keyword,
            "maxItems": 50,
            "country": "US",
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": "US",
            },
        })

        normalized = [_normalize(raw, input) for raw in items]
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Meta Ads: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="meta_ads",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Meta Ads collection failed: {e}")
        return CollectionResult(
            platform="meta_ads",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
