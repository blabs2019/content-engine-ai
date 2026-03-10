from datetime import datetime
from pydantic import BaseModel


# --- VerticalSeason schemas ---

class VerticalSeasonBase(BaseModel):
    season_window: str
    focus: str
    hook: str | None = None
    example_post: str | None = None


class VerticalSeasonCreate(VerticalSeasonBase):
    pass


class VerticalSeasonUpdate(BaseModel):
    season_window: str | None = None
    focus: str | None = None
    hook: str | None = None
    example_post: str | None = None


class VerticalSeasonResponse(VerticalSeasonBase):
    id: int
    vertical_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Vertical schemas ---

class VerticalBase(BaseModel):
    name: str
    trigger_type: str
    is_active: bool = True


class VerticalCreate(VerticalBase):
    seasons: list[VerticalSeasonCreate] = []


class VerticalUpdate(BaseModel):
    name: str | None = None
    trigger_type: str | None = None
    is_active: bool | None = None


class VerticalResponse(VerticalBase):
    id: int
    created_at: datetime
    updated_at: datetime
    seasons: list[VerticalSeasonResponse] = []

    model_config = {"from_attributes": True}
