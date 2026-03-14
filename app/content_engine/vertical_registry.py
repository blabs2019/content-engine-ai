"""
Content Engine — Vertical Registry

Single source of truth for all verticals. Auto-discovers from the
database instead of external HTTP calls.

Provides:
    - resolve(name_or_industry) → {name, id} with fuzzy matching
    - list_all() → all active verticals
    - get_id(name) → vertical_id

Cached in memory with TTL. Thread-safe.
"""

from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher
import logging
import time
import threading

logger = logging.getLogger(__name__)

# Cache TTL: 10 minutes (verticals rarely change)
CACHE_TTL_SECONDS = 600

# Common aliases for verticals — maps alternative names to canonical names
ALIASES = {
    'hvac': 'plumbing',
    'home-services': 'plumbing',
    'home services': 'plumbing',
    'heating': 'plumbing',
    'air conditioning': 'plumbing',
    'electrician': 'plumbing',
    'handyman': 'plumbing',
    'law': 'legal',
    'law firm': 'legal',
    'attorney': 'legal',
    'lawyer': 'legal',
    'band': 'musician',
    'music': 'musician',
    'cafe': 'restaurant',
    'bakery': 'restaurant',
    'food': 'restaurant',
    'barbershop': 'salon',
    'beauty': 'salon',
    'spa': 'salon',
    'saas': 'startup',
    'tech': 'startup',
    'fintech': 'startup',
    'software': 'startup',
    'builder': 'construction',
    'contractor': 'construction',
    'general contractor': 'construction',
}


class VerticalRegistry:
    """
    Auto-discovers verticals from the database.

    Usage:
        registry = VerticalRegistry()
        v = registry.resolve('insurance')        → {'name': 'insurance', 'id': 2}
        v = registry.resolve('HVAC')             → {'name': 'Plumbing', 'id': 1}  (alias)
        v = registry.resolve('plumbing repair')  → {'name': 'Plumbing', 'id': 1}  (fuzzy)
        vid = registry.get_id('insurance')       → 2
        all = registry.list_all()                → [{'name': 'Plumbing', 'id': 1}, ...]
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton — one registry shared across the app."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._cache = []           # List of vertical dicts
        self._cache_time = 0       # Timestamp of last fetch
        self._name_to_id = {}      # Lowercase name → id
        self._initialized = True

    def list_all(self) -> List[Dict]:
        """Return all active verticals."""
        self._ensure_cache()
        return self._cache

    def get_vertical_names(self) -> List[str]:
        """Return just the names, lowercased."""
        self._ensure_cache()
        return list(self._name_to_id.keys())

    def get_id(self, name: str) -> Optional[int]:
        """Get vertical ID by name. Returns None if not found."""
        resolved = self.resolve(name)
        return resolved['id'] if resolved else None

    def resolve(self, name: str) -> Optional[Dict]:
        """
        Resolve a vertical name to {name, id}.

        Resolution order:
        1. Exact match (case-insensitive)
        2. Alias match (common alternative names)
        3. Fuzzy match (best match above 0.5 threshold)
        4. None (not found)
        """
        self._ensure_cache()
        if not self._cache:
            logger.warning("Vertical registry is empty — database may have no verticals")
            return None

        key = name.lower().strip()

        # 1. Exact match
        if key in self._name_to_id:
            return self._build_result(key)

        # 2. Alias match
        alias_target = ALIASES.get(key)
        if alias_target and alias_target.lower() in self._name_to_id:
            logger.info(f"Vertical alias: '{name}' → '{alias_target}'")
            return self._build_result(alias_target.lower())

        # 3. Fuzzy match — find best match among known verticals
        best_match = None
        best_score = 0.0
        for known_name in self._name_to_id.keys():
            # Check if the input contains the vertical name or vice versa
            if known_name in key or key in known_name:
                score = 0.85  # High score for substring match
            else:
                score = SequenceMatcher(None, key, known_name).ratio()

            if score > best_score:
                best_score = score
                best_match = known_name

        if best_match and best_score >= 0.5:
            logger.info(f"Vertical fuzzy match: '{name}' → '{best_match}' (score={best_score:.2f})")
            return self._build_result(best_match)

        # 4. Not found
        logger.warning(f"No vertical match for '{name}'. Available: {list(self._name_to_id.keys())}")
        return None

    def resolve_from_context(self, business_context: Dict) -> Optional[Dict]:
        """
        Resolve vertical from business context fields.

        Checks in order:
        1. business_context['vertical'] — explicit, highest priority
        2. business_context['industry'] — next best signal
        3. business_context['business_description'] — scan for keywords
        """
        self._ensure_cache()

        # 1. Explicit vertical field
        explicit = business_context.get('vertical', '').strip()
        if explicit:
            result = self.resolve(explicit)
            if result:
                return result

        # 2. Industry field
        industry = business_context.get('industry', '').strip()
        if industry:
            result = self.resolve(industry)
            if result:
                return result

        # 3. Scan description for any known vertical name or alias
        desc = ' '.join([
            business_context.get('business_description', ''),
            business_context.get('business_name', ''),
        ]).lower()

        if desc.strip():
            # Check aliases first (more specific)
            for alias, target in ALIASES.items():
                if alias in desc:
                    result = self.resolve(target)
                    if result:
                        logger.info(f"Vertical detected from description: alias '{alias}' → '{target}'")
                        return result

            # Check vertical names directly
            for vname in self._name_to_id.keys():
                if vname in desc:
                    logger.info(f"Vertical detected from description: '{vname}'")
                    return self._build_result(vname)

        return None

    def _build_result(self, lowercase_name: str) -> Dict:
        """Build a result dict from the cached data."""
        vid = self._name_to_id[lowercase_name]
        # Find original-case name from cache
        for v in self._cache:
            if v['id'] == vid:
                return {'name': v['name'], 'id': vid}
        return {'name': lowercase_name, 'id': vid}

    def _ensure_cache(self):
        """Refresh cache if expired."""
        now = time.time()
        if self._cache and (now - self._cache_time) < CACHE_TTL_SECONDS:
            return

        with self._lock:
            # Double-check after acquiring lock
            if self._cache and (now - self._cache_time) < CACHE_TTL_SECONDS:
                return
            self._fetch_verticals()

    def _fetch_verticals(self):
        """Fetch verticals directly from the database."""
        try:
            from app.database import SyncSessionLocal
            from app.models.vertical import Vertical

            session = SyncSessionLocal()
            try:
                verticals = session.query(Vertical).filter(Vertical.is_active == True).all()

                active = [{'name': v.name, 'id': v.id} for v in verticals]
                self._cache = active
                self._cache_time = time.time()
                self._name_to_id = {
                    v['name'].lower(): v['id']
                    for v in active
                    if v.get('name') and v.get('id')
                }

                names = ', '.join(f"{v['name']}(id={v['id']})" for v in active)
                logger.info(f"Vertical registry loaded: {len(active)} verticals — {names}")
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to fetch verticals: {str(e)}")
            # Keep stale cache if it exists
            if not self._cache:
                logger.warning("Vertical registry is empty and could not be populated")

    def invalidate_cache(self):
        """Force a refresh on next access."""
        self._cache_time = 0
