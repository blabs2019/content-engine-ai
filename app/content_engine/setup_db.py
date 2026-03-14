"""
Content Engine — Database Seed Data

Seeds initial configuration data into verticals and vertical_seasons tables.
Tables are created by Alembic migrations.

Usage:
    from app.content_engine.setup_db import seed_content_engine
    seed_content_engine()
"""

from app.models.vertical import Vertical, VerticalSeason
from .models import ContentTypeBrief
import logging

logger = logging.getLogger(__name__)


# ── Weight Presets per Vertical ──

PRESETS = {
    'home-services': {
        'transformation': 0.25, 'educational': 0.25, 'community': 0.10,
        'soft_promotional': 0.10, 'behind_the_scenes': 0.10, 'social_proof': 0.05,
        'authority_opinion': 0.05, 'seasonal_timely': 0.05, 'human_moments': 0.05,
        'scenario_story': 0.00, 'origin_network': 0.00,
    },
    'insurance': {
        'educational': 0.25, 'scenario_story': 0.20, 'social_proof': 0.15,
        'seasonal_timely': 0.10, 'authority_opinion': 0.10, 'soft_promotional': 0.10,
        'community': 0.05, 'human_moments': 0.05, 'transformation': 0.00,
        'behind_the_scenes': 0.00, 'origin_network': 0.00,
    },
    'legal': {
        'educational': 0.25, 'scenario_story': 0.20, 'authority_opinion': 0.15,
        'social_proof': 0.10, 'seasonal_timely': 0.10, 'soft_promotional': 0.10,
        'community': 0.05, 'human_moments': 0.05, 'transformation': 0.00,
        'behind_the_scenes': 0.00, 'origin_network': 0.00,
    },
    'musician': {
        'behind_the_scenes': 0.25, 'community': 0.15, 'social_proof': 0.15,
        'soft_promotional': 0.10, 'human_moments': 0.10, 'seasonal_timely': 0.10,
        'authority_opinion': 0.05, 'educational': 0.05, 'origin_network': 0.05,
        'transformation': 0.00, 'scenario_story': 0.00,
    },
    'restaurant': {
        'behind_the_scenes': 0.20, 'community': 0.15, 'social_proof': 0.15,
        'transformation': 0.10, 'seasonal_timely': 0.10, 'soft_promotional': 0.10,
        'human_moments': 0.10, 'educational': 0.05, 'authority_opinion': 0.05,
        'scenario_story': 0.00, 'origin_network': 0.00,
    },
    'salon': {
        'transformation': 0.20, 'behind_the_scenes': 0.15, 'social_proof': 0.15,
        'seasonal_timely': 0.15, 'soft_promotional': 0.10, 'community': 0.10,
        'human_moments': 0.10, 'educational': 0.05, 'authority_opinion': 0.00,
        'scenario_story': 0.00, 'origin_network': 0.00,
    },
    'construction': {
        'transformation': 0.25, 'educational': 0.15, 'behind_the_scenes': 0.15,
        'social_proof': 0.10, 'seasonal_timely': 0.10, 'community': 0.10,
        'soft_promotional': 0.10, 'authority_opinion': 0.05, 'human_moments': 0.00,
        'scenario_story': 0.00, 'origin_network': 0.00,
    },
    'startup': {
        'educational': 0.20, 'authority_opinion': 0.20, 'behind_the_scenes': 0.15,
        'social_proof': 0.15, 'soft_promotional': 0.10, 'community': 0.05,
        'human_moments': 0.05, 'seasonal_timely': 0.05, 'transformation': 0.05,
        'scenario_story': 0.00, 'origin_network': 0.00,
    },
    'professional-services': {
        'educational': 0.20, 'authority_opinion': 0.15, 'social_proof': 0.15,
        'community': 0.10, 'soft_promotional': 0.10, 'seasonal_timely': 0.10,
        'behind_the_scenes': 0.05, 'human_moments': 0.05, 'scenario_story': 0.05,
        'transformation': 0.05, 'origin_network': 0.00,
    },
}

# Aliases to map vertical names to presets
PRESET_ALIASES = {
    'plumbing': 'home-services', 'hvac': 'home-services', 'electrician': 'home-services',
    'roofing': 'home-services', 'landscaping': 'home-services', 'cleaning': 'home-services',
    'pest-control': 'home-services', 'painting': 'home-services',
    'law': 'legal', 'attorney': 'legal', 'law-firm': 'legal',
    'barbershop': 'salon', 'spa': 'salon', 'beauty': 'salon',
    'cafe': 'restaurant', 'bakery': 'restaurant', 'bar': 'restaurant',
    'band': 'musician', 'dj': 'musician', 'artist': 'musician',
    'contractor': 'construction', 'remodeling': 'construction',
    'tech': 'startup', 'saas': 'startup',
    'consulting': 'professional-services', 'accounting': 'professional-services',
    'real-estate': 'professional-services', 'financial': 'professional-services',
}


# ── Seasonal Trigger Presets ──

SEASONAL_PRESETS = {
    'home-services': [
        ('Weather & Climate Cycles', 11, 2, 'Winter: Heating system prep and frozen pipe prevention',
         'Is your furnace ready before the first freeze hits?', 8),
        ('Weather & Climate Cycles', 3, 5, 'Spring: AC tune-up before summer demand spikes',
         'Book now before the summer rush fills every slot', 8),
        ('Weather & Climate Cycles', 6, 8, 'Summer: Energy bills and system efficiency',
         'Your system is working its hardest right now', 7),
        ('Weather & Climate Cycles', 9, 10, 'Fall: Pre-winter heating inspection season',
         'One check now saves a breakdown at the worst possible time', 8),
    ],
    'insurance': [
        ('Enrollment Windows & Life Events', 10, 11, 'Open enrollment preparation — health plans',
         'Open enrollment opens November 1. Most people auto-renew without checking.', 9),
        ('Enrollment Windows & Life Events', 1, 1, 'New year coverage review — life changes trigger new needs',
         'New year means new coverage needs for a lot of families', 8),
        ('Enrollment Windows & Life Events', 4, 4, 'Tax season — deductibles and premium reminders',
         'Tax season is the one time people actually look at what they pay', 7),
        ('Enrollment Windows & Life Events', 10, 12, 'Medicare open enrollment (Oct 15 - Dec 7)',
         'Medicare beneficiaries can switch plans right now', 9),
    ],
    'legal': [
        ('Business Cycles & Legal Deadlines', 1, 2, 'New year business formation season',
         'More businesses are formed in January than any other month', 8),
        ('Business Cycles & Legal Deadlines', 4, 4, 'Tax season — business structure and liability review',
         'Tax season forces business owners to look at their structure', 7),
        ('Business Cycles & Legal Deadlines', 6, 8, 'Real estate and contract season',
         'Summer is peak real estate and contractor season', 7),
        ('Business Cycles & Legal Deadlines', 9, 10, 'Q4 business planning — contracts and compliance',
         'Q4 is when smart business owners get their legal house in order', 7),
    ],
    'musician': [
        ('Performance & Release Seasons', 1, 2, 'New music teaser season',
         'First new music of the year hits different', 7),
        ('Performance & Release Seasons', 4, 5, 'Festival and summer show announcement season',
         'Summer show announcements drive the biggest ticket sales window', 8),
        ('Performance & Release Seasons', 9, 10, 'Fall tour and album release season',
         'Fall is the best season for new music', 8),
        ('Performance & Release Seasons', 12, 12, 'Year-end fan gratitude and year-in-review',
         'The most emotional and shared content of the year', 7),
    ],
    'construction': [
        ('Project Planning & Weather Cycles', 2, 3, 'Spring project planning — homeowners and developers start budgeting',
         'Spring is when project decisions get made', 8),
        ('Project Planning & Weather Cycles', 5, 6, 'Active build season — showcase ongoing projects',
         'Peak build season is here', 7),
        ('Project Planning & Weather Cycles', 8, 9, 'Fall project booking — last window before winter shutdowns',
         'September is the last good month to start before winter', 8),
        ('Project Planning & Weather Cycles', 11, 11, 'Year-end commercial renovation push',
         'Companies want improvements done before fiscal year close', 6),
    ],
    'salon': [
        ('Cultural Moments & Beauty Occasions', 3, 3, "International Women's Day — makeover, confidence, self-care",
         "Women's Day is the perfect moment to connect beauty with confidence", 7),
        ('Cultural Moments & Beauty Occasions', 4, 5, 'Prom and wedding season — bridal and formal styling',
         'Prom and wedding season books out fast', 8),
        ('Cultural Moments & Beauty Occasions', 6, 7, 'Summer hair and skin prep — color, treatments, beach-ready',
         'Summer hair is a whole different game', 7),
        ('Cultural Moments & Beauty Occasions', 10, 11, 'Holiday glam season — party looks, gifts, year-end self-care',
         'The holiday season is the busiest booking period for salons', 8),
        ('Cultural Moments & Beauty Occasions', 2, 2, "Valentine's Day — couples treatments, self-love, gift cards",
         "Valentine's is as much about self-love as it is about romance", 7),
    ],
}


def _month_range_to_window(month_start: int, month_end: int) -> str:
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return f"{month_names[month_start - 1]}-{month_names[month_end - 1]}"


def _get_preset_for_vertical(vertical_name: str) -> str:
    """Map a vertical name to a config preset key."""
    name_lower = vertical_name.lower().replace(' ', '-')
    if name_lower in PRESETS:
        return name_lower
    if name_lower in PRESET_ALIASES:
        return PRESET_ALIASES[name_lower]
    return 'professional-services'


def seed_content_engine(vertical_name: str = None, force: bool = False):
    """Seed content engine data into verticals and vertical_seasons.

    Args:
        vertical_name: If provided, seed only this vertical.
        force: If True, clear existing config and re-seed.
    """
    from app.database import SyncSessionLocal

    session = SyncSessionLocal()
    try:
        if vertical_name:
            verticals = session.query(Vertical).filter_by(name=vertical_name).all()
            if not verticals:
                logger.error(f"Vertical '{vertical_name}' not found in database")
                return
        else:
            verticals = session.query(Vertical).filter_by(is_active=True).all()

        if not verticals:
            logger.warning("No active verticals found in database. Nothing to seed.")
            return

        seeded = 0
        for vert in verticals:
            preset_key = _get_preset_for_vertical(vert.name)
            weights = PRESETS.get(preset_key, PRESETS['professional-services'])

            if force or not vert.content_type_weights:
                vert.content_type_weights = weights
                vert.content_types_enabled = {ct: w > 0 for ct, w in weights.items()}
                logger.info(f"Seeded weights for '{vert.name}' (preset: {preset_key})")
                seeded += 1
            else:
                logger.info(f"Skipping '{vert.name}' — already has weights")

            # Seed seasonal triggers
            seasonal_data = SEASONAL_PRESETS.get(preset_key, [])
            if seasonal_data and (force or not vert.seasons):
                if force:
                    for s in list(vert.seasons):
                        session.delete(s)
                    session.flush()
                for trigger_system, m_start, m_end, focus, hook, priority in seasonal_data:
                    session.add(VerticalSeason(
                        vertical_id=vert.id,
                        season_window=_month_range_to_window(m_start, m_end),
                        trigger_system=trigger_system,
                        month_start=m_start,
                        month_end=m_end,
                        focus=focus,
                        hook=hook,
                        priority=priority,
                    ))

        # Seed content type briefs (universal, not per-vertical)
        existing_brief = session.query(ContentTypeBrief).first()
        if not existing_brief or force:
            if force:
                session.query(ContentTypeBrief).delete()
            _seed_content_type_briefs(session)

        session.commit()
        logger.info(f"Content engine seed complete. {seeded} verticals configured.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed content engine: {str(e)}")
        raise
    finally:
        session.close()


def _seed_content_type_briefs(session):
    """Seed the 11 content type briefs (Layer A)."""
    from .reference_resolver import ReferenceResolver
    briefs = ReferenceResolver._default_briefs()

    for content_type, brief_text in briefs.items():
        session.add(ContentTypeBrief(
            content_type=content_type,
            brief_text=brief_text
        ))

    logger.info(f"Seeded {len(briefs)} content type briefs")


def reseed_all():
    """Drop and recreate all content engine data. Use with caution."""
    seed_content_engine(force=True)


def list_verticals_status():
    """Show all verticals and their content engine config status."""
    from app.database import SyncSessionLocal

    session = SyncSessionLocal()
    try:
        verticals = session.query(Vertical).all()
        results = []
        for vert in verticals:
            preset_key = _get_preset_for_vertical(vert.name)
            has_weights = bool(vert.content_type_weights)
            season_count = len([s for s in vert.seasons if s.active])
            results.append({
                'name': vert.name,
                'is_active': vert.is_active,
                'preset': preset_key,
                'has_weights': has_weights,
                'season_count': season_count,
            })
        return results
    finally:
        session.close()
