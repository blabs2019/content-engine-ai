from dataclasses import dataclass, field
from datetime import datetime, timezone


def safe_published_at(value) -> str | None:
    """Safely convert any publish-date value to an ISO-8601 string.

    Handles:
      - None / empty → None
      - int / float epoch timestamps (seconds or milliseconds)
      - ISO-8601 date strings (returned as-is after validation)
      - Any unexpected type/format → None (never raises)
    """
    if value is None:
        return None

    try:
        # Epoch timestamp (Facebook / Instagram return int or float)
        if isinstance(value, (int, float)):
            # Apify sometimes returns milliseconds
            if value > 1e12:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            # ISO formats — return as-is (already valid)
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    datetime.strptime(value, fmt)
                    return value
                except ValueError:
                    continue

            # Non-ISO formats — parse and convert to ISO-8601
            # Twitter: "Wed Mar 04 06:14:40 +0000 2026"
            # LinkedIn/Reddit: "Mon, 04 Mar 2026 12:00:00 GMT"
            for fmt in (
                "%a %b %d %H:%M:%S %z %Y",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%B %d, %Y",
            ):
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue

            # Could not parse but it's a non-empty string — return as-is
            return value

        # dict, list, or other unexpected type
        return None
    except Exception:
        return None


@dataclass
class CollectionInput:
    vertical_id: int
    keywords: list[str] = field(default_factory=list)
    season_context: str | None = None
    vertical_name: str = ""


@dataclass
class CollectionResult:
    platform: str
    vertical_id: int
    items_collected: int
    status: str  # "success" | "error"
    error_message: str | None = None
    data: list[dict] = field(default_factory=list)  # normalized items (no raw_data)


@dataclass
class MasterCollectionResult:
    vertical_id: int
    platform_results: list[CollectionResult] = field(default_factory=list)
    total_items_collected: int = 0


@dataclass
class ClassificationInput:
    vertical_id: int
    source: str
    vertical_name: str
    items_data: list[dict] = field(default_factory=list)  # items to classify + save
    mode: str = "all_time"  # "trending" | "all_time"


@dataclass
class ClassificationItem:
    source_id: str
    title: str
    is_trending: bool = False
    is_all_time_favourite: bool = False
    reach_score: float = 0.0


@dataclass
class ClassificationResult:
    vertical_id: int
    source: str
    trending_count: int
    all_time_favourite_count: int
    status: str  # "success" | "error"
    error_message: str | None = None
    items: list[ClassificationItem] = field(default_factory=list)
