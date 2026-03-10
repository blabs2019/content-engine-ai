from datetime import datetime
from pydantic import BaseModel


class ContentBase(BaseModel):
    title: str
    body: str | None = None
    status: str = "draft"


class ContentCreate(ContentBase):
    pass


class ContentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None


class ContentResponse(ContentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
