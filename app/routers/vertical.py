from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.vertical import Vertical, VerticalSeason
from app.schemas.vertical import (
    VerticalCreate, VerticalUpdate, VerticalResponse,
    VerticalSeasonCreate, VerticalSeasonUpdate, VerticalSeasonResponse,
)

router = APIRouter(prefix="/verticals", tags=["verticals"])


# --- Vertical CRUD ---

@router.get("/", response_model=list[VerticalResponse])
async def list_verticals(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vertical).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{vertical_id}", response_model=VerticalResponse)
async def get_vertical(vertical_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vertical).where(Vertical.id == vertical_id))
    vertical = result.scalar_one_or_none()
    if not vertical:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return vertical


@router.post("/", response_model=VerticalResponse, status_code=201)
async def create_vertical(payload: VerticalCreate, db: AsyncSession = Depends(get_db)):
    vertical = Vertical(
        name=payload.name,
        trigger_type=payload.trigger_type,
        is_active=payload.is_active,
    )
    for s in payload.seasons:
        vertical.seasons.append(VerticalSeason(**s.model_dump()))
    db.add(vertical)
    await db.commit()
    await db.refresh(vertical)
    return vertical


@router.put("/{vertical_id}", response_model=VerticalResponse)
async def update_vertical(vertical_id: int, payload: VerticalUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vertical).where(Vertical.id == vertical_id))
    vertical = result.scalar_one_or_none()
    if not vertical:
        raise HTTPException(status_code=404, detail="Vertical not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vertical, field, value)
    await db.commit()
    await db.refresh(vertical)
    return vertical


@router.delete("/{vertical_id}", status_code=204)
async def delete_vertical(vertical_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vertical).where(Vertical.id == vertical_id))
    vertical = result.scalar_one_or_none()
    if not vertical:
        raise HTTPException(status_code=404, detail="Vertical not found")
    await db.delete(vertical)
    await db.commit()


# --- VerticalSeason CRUD ---

@router.get("/{vertical_id}/seasons", response_model=list[VerticalSeasonResponse])
async def list_seasons(vertical_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VerticalSeason).where(VerticalSeason.vertical_id == vertical_id))
    return result.scalars().all()


@router.post("/{vertical_id}/seasons", response_model=VerticalSeasonResponse, status_code=201)
async def create_season(vertical_id: int, payload: VerticalSeasonCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vertical).where(Vertical.id == vertical_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vertical not found")
    season = VerticalSeason(vertical_id=vertical_id, **payload.model_dump())
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return season


@router.put("/{vertical_id}/seasons/{season_id}", response_model=VerticalSeasonResponse)
async def update_season(vertical_id: int, season_id: int, payload: VerticalSeasonUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VerticalSeason).where(VerticalSeason.id == season_id, VerticalSeason.vertical_id == vertical_id)
    )
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(season, field, value)
    await db.commit()
    await db.refresh(season)
    return season


@router.delete("/{vertical_id}/seasons/{season_id}", status_code=204)
async def delete_season(vertical_id: int, season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VerticalSeason).where(VerticalSeason.id == season_id, VerticalSeason.vertical_id == vertical_id)
    )
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    await db.delete(season)
    await db.commit()
