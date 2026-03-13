import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.collected_data import CollectedData
from app.models.vertical import Vertical
from app.schemas.collected_data import (
    CollectedDataResponse,
    CollectedDataItem,
    ChannelData,
    HashtagItem,
    VerticalCollectedDataResponse,
    CollectionTriggerResponse,
    MasterCollectionTriggerResponse,
)
from app.temporal.client import get_temporal_client
from app.temporal.data_collection.shared import CollectionInput
from app.temporal.data_collection.workflows import (
    DataCollectionWorkflow,
    FacebookCollectionWorkflow,
    InstagramCollectionWorkflow,
    TwitterCollectionWorkflow,
    RedditCollectionWorkflow,
    GoogleNewsCollectionWorkflow,
    YouTubeCollectionWorkflow,
    LinkedInCollectionWorkflow,
    MetaAdsCollectionWorkflow,
)

settings = get_settings()

router = APIRouter(tags=["data-collection"])

PLATFORM_WORKFLOW_MAP = {
    "facebook": FacebookCollectionWorkflow,
    "instagram": InstagramCollectionWorkflow,
    "twitter": TwitterCollectionWorkflow,
    "reddit": RedditCollectionWorkflow,
    "google_news": GoogleNewsCollectionWorkflow,
    "youtube": YouTubeCollectionWorkflow,
    "linkedin": LinkedInCollectionWorkflow,
    "meta_ads": MetaAdsCollectionWorkflow,
}

VALID_PLATFORMS = list(PLATFORM_WORKFLOW_MAP.keys())


async def _get_vertical(vertical_id: int, db: AsyncSession) -> Vertical:
    """Look up a vertical by ID. Raises 404 if not found."""
    result = await db.execute(select(Vertical).where(Vertical.id == vertical_id))
    vertical = result.scalar_one_or_none()
    if not vertical:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return vertical


# --- Trigger endpoints ---


@router.post("/collect/all/{vertical_id}", response_model=MasterCollectionTriggerResponse)
async def trigger_all_platform_collection(
    vertical_id: int,
    keywords: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    vertical = await _get_vertical(vertical_id, db)

    client = await get_temporal_client()
    effective_keywords = keywords if keywords else [vertical.name]
    input_data = CollectionInput(vertical_id=vertical_id, keywords=effective_keywords, vertical_name=vertical.name)

    workflow_id = f"collect-all-v{vertical_id}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"

    await client.start_workflow(
        DataCollectionWorkflow.run,
        input_data,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    return MasterCollectionTriggerResponse(
        workflow_id=workflow_id,
        vertical_id=vertical_id,
        platforms=VALID_PLATFORMS,
        status="started",
    )


@router.post("/collect/{platform}/{vertical_id}", response_model=CollectionTriggerResponse)
async def trigger_platform_collection(
    platform: str,
    vertical_id: int,
    keywords: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of: {VALID_PLATFORMS}")

    vertical = await _get_vertical(vertical_id, db)

    client = await get_temporal_client()
    wf_class = PLATFORM_WORKFLOW_MAP[platform]
    effective_keywords = keywords if keywords else [vertical.name]
    input_data = CollectionInput(vertical_id=vertical_id, keywords=effective_keywords, vertical_name=vertical.name)

    workflow_id = f"collect-{platform}-v{vertical_id}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"

    await client.start_workflow(
        wf_class.run,
        input_data,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    return CollectionTriggerResponse(
        workflow_id=workflow_id,
        platform=platform,
        vertical_id=vertical_id,
        status="started",
    )


# --- Query endpoints ---

# Social platforms that go into channels (trending + all_time_favourite split)
SOCIAL_CHANNELS = {"facebook", "twitter", "reddit", "youtube", "linkedin", "instagram"}


@router.get("/collected-data", response_model=list[CollectedDataResponse])
async def list_collected_data(
    source: str | None = None,
    vertical_id: int | None = None,
    content_type: str | None = None,
    is_trending: bool | None = None,
    collected_after: datetime | None = None,
    collected_before: datetime | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(CollectedData)

    if source is not None:
        query = query.where(CollectedData.source == source)
    if vertical_id is not None:
        query = query.where(CollectedData.vertical_id == vertical_id)
    if content_type is not None:
        query = query.where(CollectedData.content_type == content_type)
    if is_trending is not None:
        query = query.where(CollectedData.is_trending == is_trending)
    if collected_after is not None:
        query = query.where(CollectedData.collected_at >= collected_after)
    if collected_before is not None:
        query = query.where(CollectedData.collected_at <= collected_before)

    query = query.order_by(CollectedData.collected_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/collected-data/vertical/{vertical_id}",
    response_model=VerticalCollectedDataResponse,
)
async def get_vertical_collected_data(
    vertical_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return all collected data for a vertical, organised by type.

    - **channels**: social platforms grouped with trending + all_time_favourite lists
    - **news**: google_news items
    - **meta_ads**: meta_ads items
    - **hashtags**: most-used Instagram hashtags with post counts
    """
    await _get_vertical(vertical_id, db)

    # Fetch all collected data for this vertical in one query
    result = await db.execute(
        select(CollectedData)
        .where(CollectedData.vertical_id == vertical_id)
        .order_by(CollectedData.reach_score.desc())
    )
    rows = result.scalars().all()

    # Buckets
    channels: dict[str, ChannelData] = {}
    news: list[CollectedDataItem] = []
    meta_ads: list[CollectedDataItem] = []
    hashtags: list[HashtagItem] = []
    news_keywords: list[str] = []
    news_titles: list[str] = []

    for row in rows:
        source = row.source

        # Hashtag metadata row (content_type="tags") → extract hashtag list
        if row.content_type == "tags":
            try:
                names = json.loads(row.body) if row.body else []
                raw_hashtags = (row.raw_data or {}).get("hashtags", [])
                name_to_count = {
                    h.get("name", ""): h.get("postsCount", 0) for h in raw_hashtags
                }
                for name in names:
                    hashtags.append(HashtagItem(
                        name=name,
                        posts_count=int(name_to_count.get(name, 0)),
                    ))
            except Exception:
                pass
            continue

        # News insights rows (keyword/title) → extract string arrays
        if row.content_type in ("keyword", "title"):
            try:
                names = json.loads(row.body) if row.body else []
                if row.content_type == "keyword":
                    news_keywords = names
                else:
                    news_titles = names
            except Exception:
                pass
            continue

        item = CollectedDataItem.model_validate(row)

        if source == "google_news":
            news.append(item)
        elif source == "meta_ads":
            meta_ads.append(item)
        elif source in SOCIAL_CHANNELS:
            if source not in channels:
                channels[source] = ChannelData()
            if row.is_trending:
                channels[source].trending.append(item)
            if row.is_all_time_favourite:
                channels[source].all_time_favourite.append(item)

    return VerticalCollectedDataResponse(
        vertical_id=vertical_id,
        channels=channels,
        news=news,
        meta_ads=meta_ads,
        hashtags=hashtags,
        news_keywords=news_keywords,
        news_titles=news_titles,
    )


@router.get("/collected-data/{record_id}", response_model=CollectedDataResponse)
async def get_collected_data(record_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CollectedData).where(CollectedData.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Collected data record not found")
    return record
