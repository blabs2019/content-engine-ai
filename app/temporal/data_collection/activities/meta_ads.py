import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data, delete_except_source_ids

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
    """Scrape meta ads, AI-filter for relevance, save only top N."""
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
        logger.info(f"Meta Ads: scraped {len(normalized)} items, running AI relevance filter")

        # AI relevance filter: pass title + source_id to rank by vertical relevance
        from app.config import get_settings
        from app.services.ai_classifier import classify_content, ContentItemDTO, compute_reach_score

        top_n = get_settings().TOP_N_RESULTS
        vertical_name = input.vertical_name or keyword

        # Build DTOs with short index IDs for reliable AI processing
        dtos = []
        idx_to_item = {}
        for i, item in enumerate(normalized, start=1):
            idx = str(i)
            idx_to_item[idx] = item
            dtos.append(ContentItemDTO(
                id=idx,
                title=item.get("title", ""),
                reach_score=compute_reach_score("meta_ads", item.get("platform_metadata")),
                body_snippet=(item.get("body") or "")[:200],
            ))

        ranked_idxs = await asyncio.to_thread(
            classify_content, dtos, vertical_name, len(normalized),
            mode="relevance",
        )

        # From AI-relevant ads, sort by impressions (collation_count) desc, take top N
        relevant_items = [idx_to_item[idx] for idx in ranked_idxs if idx in idx_to_item]
        relevant_items.sort(
            key=lambda x: float((x.get("platform_metadata") or {}).get("collation_count") or 0),
            reverse=True,
        )
        keepers = relevant_items[:top_n]

        # Set reach_score on keepers
        for item in keepers:
            item["reach_score"] = compute_reach_score("meta_ads", item.get("platform_metadata"))

        # Save only top N to DB (with raw_data)
        await upsert_collected_data(keepers)
        keep_sids = [item["source_id"] for item in keepers]
        deleted = await delete_except_source_ids(input.vertical_id, "meta_ads", keep_sids)

        logger.info(
            f"Meta Ads: AI kept {len(keepers)} relevant from {len(normalized)} total, "
            f"cleaned up {deleted} old rows for vertical_id={input.vertical_id}"
        )

        # Strip raw_data for gRPC return
        for item in keepers:
            item.pop("raw_data", None)

        return CollectionResult(
            platform="meta_ads",
            vertical_id=input.vertical_id,
            items_collected=len(keepers),
            status="success",
            data=keepers,
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
