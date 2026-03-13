from datetime import datetime
from pydantic import BaseModel


class CollectedDataBase(BaseModel):
    source: str
    vertical_id: int
    content_type: str
    title: str
    body: str | None = None
    url: str | None = None
    file_urls: list[str] | None = None
    raw_data: dict | None = None
    tags: list[str] | None = None
    region: str | None = None
    platform_metadata: dict | None = None
    is_trending: bool = False
    is_all_time_favourite: bool = False


class CollectedDataCreate(CollectedDataBase):
    collected_at: datetime | None = None


class CollectedDataResponse(CollectedDataBase):
    id: int
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Lightweight item for the vertical dashboard endpoint ---


class CollectedDataItem(BaseModel):
    """Lightweight item returned in the vertical dashboard (no raw_data)."""
    id: int
    source: str
    source_id: str | None = None
    content_type: str
    title: str
    body: str | None = None
    url: str | None = None
    file_urls: list[str] | None = None
    tags: list[str] | None = None
    platform_metadata: dict | None = None
    published_at: str | None = None
    reach_score: float = 0.0
    is_trending: bool = False
    is_all_time_favourite: bool = False

    model_config = {"from_attributes": True}


class ChannelData(BaseModel):
    """Trending + all-time favourite lists for a single social channel."""
    trending: list[CollectedDataItem] = []
    all_time_favourite: list[CollectedDataItem] = []


class HashtagItem(BaseModel):
    name: str
    posts_count: int = 0


class VerticalCollectedDataResponse(BaseModel):
    """Full dashboard response for a vertical — all collected data organised by type."""
    vertical_id: int
    channels: dict[str, ChannelData] = {}
    news: list[CollectedDataItem] = []
    meta_ads: list[CollectedDataItem] = []
    hashtags: list[HashtagItem] = []
    news_keywords: list[str] = []
    news_titles: list[str] = []


class CollectionTriggerResponse(BaseModel):
    workflow_id: str
    platform: str
    vertical_id: int
    status: str


class MasterCollectionTriggerResponse(BaseModel):
    workflow_id: str
    vertical_id: int
    platforms: list[str]
    status: str
