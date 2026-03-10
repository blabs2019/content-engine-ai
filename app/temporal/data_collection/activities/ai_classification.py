import asyncio
from datetime import datetime, timedelta, timezone

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import ClassificationInput, ClassificationItem, ClassificationResult
from app.config import get_settings


def _is_recent(item: dict, cutoff: datetime) -> bool:
    """Check if an item's published_at date is after the cutoff."""
    published = item.get("published_at")
    if not published:
        return False
    try:
        pub_str = str(published).replace("Z", "+00:00")
        pub_dt = datetime.fromisoformat(pub_str)
        return pub_dt >= cutoff
    except (ValueError, AttributeError):
        # Fallback: try common non-ISO formats (e.g. Twitter)
        for fmt in (
            "%a %b %d %H:%M:%S %z %Y",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
        ):
            try:
                pub_dt = datetime.strptime(str(published), fmt)
                return pub_dt >= cutoff
            except ValueError:
                continue
    return False


def _build_dtos_with_short_ids(items: list[dict], reach_map: dict):
    """Build DTOs with short index IDs so the LLM can handle them reliably.

    Returns (dtos, idx_to_sid) where idx_to_sid maps "1","2",... back to real source_ids.
    This is critical for google_news where source_ids are 200+ char base64 strings.
    """
    from app.services.ai_classifier import ContentItemDTO

    dtos = []
    idx_to_sid = {}
    for i, item in enumerate(items, start=1):
        sid = item.get("source_id", "")
        idx = str(i)
        idx_to_sid[idx] = sid
        dtos.append(ContentItemDTO(
            id=idx,
            title=item.get("title", ""),
            reach_score=reach_map.get(sid, 0.0),
        ))
    return dtos, idx_to_sid


def _map_back(ranked_idxs: list[str], idx_to_sid: dict) -> list[str]:
    """Convert ranked short index IDs back to real source_ids."""
    return [idx_to_sid[idx] for idx in ranked_idxs if idx in idx_to_sid]


@activity.defn
async def classify_collected_data(input: ClassificationInput) -> ClassificationResult:
    """Single-mode AI classification activity.

    Uses flag-based updates to preserve raw_data saved by scrapers.

    mode="trending":
      1. Reset is_trending=False for all rows
      2. Filter to recent items only
      3. AI call with trending prompt (viral/buzzy)
      4. Upsert keepers with is_trending=True

    mode="all_time":
      1. Reset is_all_time_favourite=False for all rows
      2. AI call on ALL items with quality prompt (evergreen/educational)
      3. Upsert keepers with is_all_time_favourite=True
      4. Delete unflagged rows (cleanup)
    """
    settings = get_settings()
    top_n = settings.TOP_N_RESULTS
    trending_days = settings.TRENDING_DATE_RANGE_DAYS
    mode = input.mode

    logger.info(
        f"AI Classification [{mode}]: starting for vertical_id={input.vertical_id}, "
        f"source={input.source}, vertical_name={input.vertical_name}, "
        f"items_count={len(input.items_data)}"
    )

    try:
        from app.services.data_store import upsert_collected_data, reset_flags, delete_unflagged, delete_except_source_ids
        from app.services.ai_classifier import classify_content, compute_reach_score

        all_items = input.items_data

        if not all_items:
            logger.info(
                f"AI Classification [{mode}]: no items for "
                f"vertical_id={input.vertical_id}, source={input.source}"
            )
            return ClassificationResult(
                vertical_id=input.vertical_id,
                source=input.source,
                trending_count=0,
                all_time_favourite_count=0,
                status="success",
            )

        # Build source_id → item dict mapping
        sid_to_item = {item["source_id"]: item for item in all_items if item.get("source_id")}

        # Compute reach scores for all items
        reach_map = {}
        for item in all_items:
            sid = item.get("source_id", "")
            reach_map[sid] = compute_reach_score(item.get("source", ""), item.get("platform_metadata"))

        # --- google_news: single relevance call (no trending/all-time split) ---
        if input.source == "google_news":
            dtos, idx_to_sid = _build_dtos_with_short_ids(all_items, reach_map)
            ranked_idxs = await asyncio.to_thread(
                classify_content, dtos, input.vertical_name, top_n,
                mode="relevance",
            )
            sids = _map_back(ranked_idxs[:top_n], idx_to_sid) if ranked_idxs else []

            keeper_items = []
            for sid in sids:
                if sid in sid_to_item:
                    item = dict(sid_to_item[sid])
                    item["reach_score"] = 0.0
                    keeper_items.append(item)

            count = await upsert_collected_data(keeper_items)
            # Delete non-keeper rows (preserves raw_data on keepers)
            deleted = await delete_except_source_ids(input.vertical_id, input.source, sids)
            logger.info(f"AI Classification [google_news]: cleaned up {deleted} non-relevant rows")

            logger.info(
                f"AI Classification [google_news]: saved {count} relevant items "
                f"from {len(all_items)} total for vertical_id={input.vertical_id}"
            )
            kept_result = [
                ClassificationItem(
                    source_id=sid,
                    title=sid_to_item[sid].get("title", "")[:200],
                    reach_score=0.0,
                )
                for sid in sids if sid in sid_to_item
            ]
            return ClassificationResult(
                vertical_id=input.vertical_id,
                source=input.source,
                trending_count=0,
                all_time_favourite_count=0,
                status="success",
                items=kept_result,
            )

        if mode == "trending":
            # Reset trending flags (preserves rows + raw_data)
            await reset_flags(input.vertical_id, input.source, "is_trending")

            # Filter to recent items only
            cutoff = datetime.now(timezone.utc) - timedelta(days=trending_days)
            pool = [item for item in all_items if _is_recent(item, cutoff)]

            logger.info(
                f"AI Classification [trending]: {len(all_items)} total items, "
                f"{len(pool)} recent (within {trending_days} days)"
            )

            if not pool:
                return ClassificationResult(
                    vertical_id=input.vertical_id,
                    source=input.source,
                    trending_count=0,
                    all_time_favourite_count=0,
                    status="success",
                )

            dtos, idx_to_sid = _build_dtos_with_short_ids(pool, reach_map)
            ranked_idxs = await asyncio.to_thread(
                classify_content, dtos, input.vertical_name, top_n,
                mode="trending",
            )
            sids = _map_back(ranked_idxs[:top_n], idx_to_sid) if ranked_idxs else []

            keeper_items = []
            for sid in sids:
                if sid in sid_to_item:
                    item = dict(sid_to_item[sid])
                    item["is_trending"] = True
                    item.pop("is_all_time_favourite", None)  # don't touch this flag
                    item["reach_score"] = reach_map.get(sid, 0.0)
                    keeper_items.append(item)

            count = await upsert_collected_data(keeper_items)

            logger.info(
                f"AI Classification [trending]: saved {count} trending items "
                f"from {len(pool)} recent for vertical_id={input.vertical_id}, "
                f"source={input.source}"
            )

            kept_result = [
                ClassificationItem(
                    source_id=sid,
                    title=sid_to_item[sid].get("title", "")[:200],
                    is_trending=True,
                    reach_score=reach_map.get(sid, 0.0),
                )
                for sid in sids if sid in sid_to_item
            ]
            return ClassificationResult(
                vertical_id=input.vertical_id,
                source=input.source,
                trending_count=len(sids),
                all_time_favourite_count=0,
                status="success",
                items=kept_result,
            )

        else:  # mode == "all_time"
            # Reset all_time flags (preserves rows + raw_data)
            await reset_flags(input.vertical_id, input.source, "is_all_time_favourite")

            dtos, idx_to_sid = _build_dtos_with_short_ids(all_items, reach_map)
            ranked_idxs = await asyncio.to_thread(
                classify_content, dtos, input.vertical_name, top_n,
                mode="all_time",
            )
            sids = _map_back(ranked_idxs[:top_n], idx_to_sid) if ranked_idxs else []

            keeper_items = []
            for sid in sids:
                if sid in sid_to_item:
                    item = dict(sid_to_item[sid])
                    item["is_all_time_favourite"] = True
                    item.pop("is_trending", None)  # don't overwrite trending flag
                    item["reach_score"] = reach_map.get(sid, 0.0)
                    keeper_items.append(item)

            count = await upsert_collected_data(keeper_items)

            # Cleanup: delete rows that have neither trending nor all_time flag
            deleted = await delete_unflagged(input.vertical_id, input.source)

            logger.info(
                f"AI Classification [all_time]: saved {count} all-time items "
                f"from {len(all_items)} total for vertical_id={input.vertical_id}, "
                f"source={input.source}, cleaned up {deleted} unflagged rows"
            )

            kept_result = [
                ClassificationItem(
                    source_id=sid,
                    title=sid_to_item[sid].get("title", "")[:200],
                    is_all_time_favourite=True,
                    reach_score=reach_map.get(sid, 0.0),
                )
                for sid in sids if sid in sid_to_item
            ]
            return ClassificationResult(
                vertical_id=input.vertical_id,
                source=input.source,
                trending_count=0,
                all_time_favourite_count=len(sids),
                status="success",
                items=kept_result,
            )

    except Exception as e:
        logger.error(f"AI Classification [{mode}] failed: {e}")
        return ClassificationResult(
            vertical_id=input.vertical_id,
            source=input.source,
            trending_count=0,
            all_time_favourite_count=0,
            status="error",
            error_message=str(e),
        )
