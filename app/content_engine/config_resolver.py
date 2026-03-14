"""
Content Engine — Config Resolver

Resolves the final configuration for a business by merging:
    1. Vertical defaults (from verticals table — content_type_weights, content_types_enabled)
    2. Business overrides (from content_engine_business_override)

Business overrides win where both exist.
"""

from typing import Dict, List, Any, Optional
from app.models.vertical import Vertical, VerticalSeason
from .models import BusinessConfigOverride
import logging

logger = logging.getLogger(__name__)

# All 11 content types
CONTENT_TYPES = [
    'transformation', 'educational', 'social_proof', 'community',
    'soft_promotional', 'behind_the_scenes', 'scenario_story',
    'authority_opinion', 'origin_network', 'seasonal_timely', 'human_moments'
]

# Content types that require real photos (AI images never acceptable)
REQUIRES_REAL_PHOTO = [
    'transformation', 'behind_the_scenes', 'origin_network', 'human_moments'
]


class ConfigResolver:
    """
    Resolves content engine config for a business.

    Usage:
        resolver = ConfigResolver()
        config = resolver.resolve(vertical='home-services', business_id=123)
    """

    def resolve(self, vertical: str, business_id: Optional[int] = None,
                target_months: Optional[List[int]] = None) -> Dict[str, Any]:
        from app.database import SyncSessionLocal

        session = SyncSessionLocal()
        try:
            # Step 1: Load vertical
            vert = session.query(Vertical).filter_by(name=vertical).first()

            weights = {}
            enabled = {}
            if vert:
                weights = vert.content_type_weights or {}
                enabled = vert.content_types_enabled or {}

            # Step 2: Apply business overrides
            override_config = {}
            if business_id:
                overrides = session.query(BusinessConfigOverride).filter_by(business_id=business_id).all()
                for override in overrides:
                    key = f"{override.config_type}:{override.config_key}"
                    override_config[key] = override.config_value
                    logger.info(f"Business {business_id} override: {key} = {override.config_value}")

            # Step 3: Build resolved output
            resolved = {
                'vertical': vertical,
                'business_id': business_id,
                'content_type_weights': {},
                'enabled_content_types': [],
                'seasonal_triggers': [],
            }

            for content_type in CONTENT_TYPES:
                # Weight — check override first, then vertical default
                weight_override_key = f"content_type_weight:{content_type}"
                if weight_override_key in override_config:
                    val = override_config[weight_override_key]
                    weight = val.get('weight', 0.0) if isinstance(val, dict) else 0.0
                else:
                    weight = weights.get(content_type, 0.0)
                resolved['content_type_weights'][content_type] = weight

                # Enabled — check override first, then vertical default
                enabled_override_key = f"content_type_enabled:{content_type}"
                if enabled_override_key in override_config:
                    val = override_config[enabled_override_key]
                    is_enabled = val.get('enabled', True) if isinstance(val, dict) else True
                else:
                    is_enabled = enabled.get(content_type, True)
                if is_enabled and weight > 0:
                    resolved['enabled_content_types'].append(content_type)

            # Step 4: Load seasonal triggers from VerticalSeason
            resolved['seasonal_triggers'] = self._get_seasonal_triggers(
                session, vert, target_months
            )

            logger.info(
                f"Resolved config for {vertical} (biz={business_id}): "
                f"{len(resolved['enabled_content_types'])} content types enabled, "
                f"{len(resolved['seasonal_triggers'])} seasonal triggers active"
            )

            return resolved
        finally:
            session.close()

    def _get_seasonal_triggers(self, session, vert: Optional[Vertical],
                                target_months: Optional[List[int]] = None) -> List[Dict]:
        if not vert:
            return []

        triggers = [s for s in vert.seasons if s.active]

        # Filter by target months if specified
        if target_months:
            triggers = [t for t in triggers if any(t.is_active_for_month(m) for m in target_months)]

        # Sort by priority (highest first)
        triggers.sort(key=lambda t: t.priority, reverse=True)

        return [t.to_dict() for t in triggers]

    def get_all_verticals_config(self) -> Dict[str, Any]:
        """Return config summary for all verticals (for admin/debug)."""
        from app.database import SyncSessionLocal

        session = SyncSessionLocal()
        try:
            verticals = session.query(Vertical).filter_by(is_active=True).all()
            result = {}
            for vert in verticals:
                weights = vert.content_type_weights or {}
                enabled = vert.content_types_enabled or {}
                enabled_types = [
                    ct for ct in CONTENT_TYPES
                    if enabled.get(ct, True) and weights.get(ct, 0.0) > 0
                ]
                result[vert.name] = {
                    'enabled_types': enabled_types,
                    'weights': weights,
                    'seasonal_count': len([s for s in vert.seasons if s.active])
                }
            return result
        finally:
            session.close()
