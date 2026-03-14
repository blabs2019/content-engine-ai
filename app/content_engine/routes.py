"""
Content Engine — Routes (FastAPI)

Endpoint: /api/v1/content-engine/generate
Config management endpoints under /api/v1/content-engine/config/
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.llm_provider import get_llm_provider
from app.models.vertical import Vertical, VerticalSeason
from .models import BusinessConfigOverride
from .config_resolver import ConfigResolver, CONTENT_TYPES
from .pipeline import ContentEnginePipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content-engine", tags=["content-engine"])
config_resolver = ConfigResolver()


# ── Request/Response Models ──

class GenerateRequest(BaseModel):
    business_id: Optional[int] = None
    businessId: Optional[int] = None
    platform: str = "facebook"
    timeframe_weeks: int = 4
    startDate: Optional[str] = None
    start_date: Optional[str] = None
    instructions: str = ""
    ai_provider: str = "claude"
    business_context: dict = {}
    products_and_services: list = []
    competitors: dict = {}
    business: dict = {}
    recent_posts: list = []
    vector_store_ids: list = []
    debug_level: Optional[str] = None


class BusinessOverrideRequest(BaseModel):
    config_type: str
    config_key: str
    config_value: Any


class BusinessOverrideDeleteRequest(BaseModel):
    config_type: str
    config_key: str


class SeasonalTriggerCreate(BaseModel):
    vertical: str
    trigger_system: Optional[str] = None
    month_start: int
    month_end: int
    focus: str
    hook: Optional[str] = None
    example_post: Optional[str] = None
    priority: int = 5


class SeasonalTriggerUpdate(BaseModel):
    trigger_system: Optional[str] = None
    month_start: Optional[int] = None
    month_end: Optional[int] = None
    focus: Optional[str] = None
    hook: Optional[str] = None
    example_post: Optional[str] = None
    priority: Optional[int] = None
    active: Optional[bool] = None


# ── Generate Endpoint ──

@router.post("/generate")
async def generate_content_calendar(payload: GenerateRequest):
    """Generate social media content calendar using the 4-stage pipeline."""
    try:
        platform = payload.platform
        timeframe_weeks = payload.timeframe_weeks
        start_date = payload.startDate or payload.start_date or ''
        instructions = payload.instructions
        ai_provider_name = payload.ai_provider
        business_id = payload.business_id or payload.businessId

        # Validate platform
        valid_platforms = ['facebook', 'linkedin', 'twitter', 'instagram']
        if platform not in valid_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
            )

        # Validate timeframe
        if timeframe_weeks < 1 or timeframe_weeks > 12:
            raise HTTPException(status_code=400, detail="timeframe_weeks must be between 1 and 12")

        business_context = payload.business_context or {}

        # Initialize AI provider
        try:
            ai_provider = get_llm_provider(ai_provider_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI provider init failed: {str(e)}")

        # Build opportunities dict
        opportunities = {
            'products_and_services': payload.products_and_services,
            'competitors': payload.competitors,
            'business': payload.business,
        }

        recent_posts = payload.recent_posts
        vector_store_ids = payload.vector_store_ids or None
        debug_level = payload.debug_level

        # Run pipeline in thread (it's synchronous)
        pipeline = ContentEnginePipeline(
            ai_provider=ai_provider,
            provider_name=ai_provider_name,
            debug_level=debug_level
        )
        result = await asyncio.to_thread(
            pipeline.generate,
            business_context=business_context,
            platform=platform,
            timeframe_weeks=timeframe_weeks,
            start_date=start_date,
            opportunities=opportunities,
            instructions=instructions,
            business_id=int(business_id) if business_id else None,
            recent_posts=recent_posts,
            vector_store_ids=vector_store_ids
        )

        if result['status'] == 'success':
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Pipeline failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content engine error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Config Management Endpoints ──

@router.get("/config/vertical/{vertical}")
async def get_vertical_config(
    vertical: str,
    business_id: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
):
    """Get resolved config for a vertical (with optional business override)."""
    target_months = [month] if month else None
    try:
        config = await asyncio.to_thread(
            config_resolver.resolve,
            vertical=vertical,
            business_id=business_id,
            target_months=target_months
        )
        return {"status": "success", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/verticals")
async def get_all_verticals():
    """Get config summary for all verticals."""
    try:
        result = await asyncio.to_thread(config_resolver.get_all_verticals_config)
        return {"status": "success", "verticals": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/business/{business_id}/override")
async def set_business_override(
    business_id: int,
    payload: BusinessOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a business config override."""
    try:
        result = await db.execute(
            select(BusinessConfigOverride).where(
                BusinessConfigOverride.business_id == business_id,
                BusinessConfigOverride.config_type == payload.config_type,
                BusinessConfigOverride.config_key == payload.config_key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_value = payload.config_value
        else:
            override = BusinessConfigOverride(
                business_id=business_id,
                config_type=payload.config_type,
                config_key=payload.config_key,
                config_value=payload.config_value,
            )
            db.add(override)

        await db.commit()
        return {
            "status": "success",
            "message": f"Override set for business {business_id}: {payload.config_type}/{payload.config_key}"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/business/{business_id}/overrides")
async def get_business_overrides(business_id: int, db: AsyncSession = Depends(get_db)):
    """Get all overrides for a business."""
    result = await db.execute(
        select(BusinessConfigOverride).where(BusinessConfigOverride.business_id == business_id)
    )
    overrides = result.scalars().all()
    return {
        "status": "success",
        "business_id": business_id,
        "overrides": [o.to_dict() for o in overrides]
    }


@router.delete("/config/business/{business_id}/override")
async def delete_business_override(
    business_id: int,
    payload: BusinessOverrideDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific business override."""
    try:
        result = await db.execute(
            delete(BusinessConfigOverride).where(
                BusinessConfigOverride.business_id == business_id,
                BusinessConfigOverride.config_type == payload.config_type,
                BusinessConfigOverride.config_key == payload.config_key,
            )
        )
        await db.commit()
        return {"status": "success", "deleted": result.rowcount}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Seasonal Trigger Management (via VerticalSeason) ──

def _month_range_to_window(month_start: int, month_end: int) -> str:
    """Convert month numbers to a season_window string like 'Nov-Feb'."""
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return f"{month_names[month_start - 1]}-{month_names[month_end - 1]}"


@router.get("/config/seasonal-triggers")
async def get_seasonal_triggers(
    vertical: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get seasonal triggers, optionally filtered by vertical and month."""
    query = select(VerticalSeason).where(VerticalSeason.active == True)
    if vertical:
        # Join to Vertical to filter by name
        query = query.join(Vertical).where(Vertical.name == vertical)

    result = await db.execute(query)
    triggers = result.scalars().all()

    if month:
        triggers = [t for t in triggers if t.is_active_for_month(month)]

    return {
        "status": "success",
        "triggers": [t.to_dict() for t in triggers]
    }


@router.post("/config/seasonal-triggers", status_code=201)
async def add_seasonal_trigger(payload: SeasonalTriggerCreate, db: AsyncSession = Depends(get_db)):
    """Add a new seasonal trigger."""
    try:
        # Look up vertical by name
        result = await db.execute(select(Vertical).where(Vertical.name == payload.vertical))
        vert = result.scalar_one_or_none()
        if not vert:
            raise HTTPException(status_code=404, detail=f"Vertical '{payload.vertical}' not found")

        trigger = VerticalSeason(
            vertical_id=vert.id,
            season_window=_month_range_to_window(payload.month_start, payload.month_end),
            trigger_system=payload.trigger_system,
            month_start=payload.month_start,
            month_end=payload.month_end,
            focus=payload.focus,
            hook=payload.hook,
            example_post=payload.example_post,
            priority=payload.priority,
        )
        db.add(trigger)
        await db.commit()
        await db.refresh(trigger)
        return {"status": "success", "trigger": trigger.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/seasonal-triggers/{trigger_id}")
async def update_seasonal_trigger(
    trigger_id: int,
    payload: SeasonalTriggerUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing seasonal trigger."""
    result = await db.execute(select(VerticalSeason).where(VerticalSeason.id == trigger_id))
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    try:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(trigger, field, value)

        # Update season_window if month range changed
        if 'month_start' in update_data or 'month_end' in update_data:
            ms = trigger.month_start
            me = trigger.month_end
            if ms and me:
                trigger.season_window = _month_range_to_window(ms, me)

        await db.commit()
        await db.refresh(trigger)
        return {"status": "success", "trigger": trigger.to_dict()}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/seasonal-triggers/{trigger_id}")
async def delete_seasonal_trigger(trigger_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a seasonal trigger."""
    result = await db.execute(select(VerticalSeason).where(VerticalSeason.id == trigger_id))
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    try:
        await db.delete(trigger)
        await db.commit()
        return {"status": "success", "deleted": trigger_id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
