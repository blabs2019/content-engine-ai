from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import Content
from app.schemas.content import ContentCreate, ContentUpdate, ContentResponse

router = APIRouter(prefix="/contents", tags=["contents"])


@router.get("/", response_model=list[ContentResponse])
async def list_contents(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


@router.post("/", response_model=ContentResponse, status_code=201)
async def create_content(payload: ContentCreate, db: AsyncSession = Depends(get_db)):
    content = Content(**payload.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(content_id: int, payload: ContentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)
    return content


@router.delete("/{content_id}", status_code=204)
async def delete_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(content)
    await db.commit()
