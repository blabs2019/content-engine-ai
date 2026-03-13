from sqlalchemy import delete, select, update

from app.database import AsyncSessionLocal
from app.models.collected_data import CollectedData


async def clear_collected_data(vertical_id: int, source: str) -> int:
    """Delete all collected data for a given vertical and source.

    Preserves metadata rows (content_type='tags') such as Instagram hashtags.
    Returns the number of rows deleted.
    """
    async with AsyncSessionLocal() as session:
        stmt = delete(CollectedData).where(
            CollectedData.vertical_id == vertical_id,
            CollectedData.source == source,
            CollectedData.content_type.notin_(["tags", "keyword", "title"]),
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def reset_flags(vertical_id: int, source: str, flag_name: str) -> int:
    """Reset a boolean flag to False for all rows of a vertical+source.

    Preserves tags rows (e.g. Instagram hashtags).
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            update(CollectedData)
            .where(
                CollectedData.vertical_id == vertical_id,
                CollectedData.source == source,
                CollectedData.content_type.notin_(["tags", "keyword", "title"]),
            )
            .values(**{flag_name: False})
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def delete_unflagged(vertical_id: int, source: str) -> int:
    """Delete rows that have neither is_trending nor is_all_time_favourite.

    Used after both trending + all_time classifications complete to clean up
    non-keeper rows while preserving raw_data on keepers.
    """
    async with AsyncSessionLocal() as session:
        stmt = delete(CollectedData).where(
            CollectedData.vertical_id == vertical_id,
            CollectedData.source == source,
            CollectedData.content_type.notin_(["tags", "keyword", "title"]),
            CollectedData.is_trending == False,
            CollectedData.is_all_time_favourite == False,
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def delete_except_source_ids(vertical_id: int, source: str, keep_ids: list[str]) -> int:
    """Delete all rows for vertical+source EXCEPT those with source_id in keep_ids.

    Used for google_news/meta_ads single-pass classification cleanup.
    """
    async with AsyncSessionLocal() as session:
        conditions = [
            CollectedData.vertical_id == vertical_id,
            CollectedData.source == source,
            CollectedData.content_type.notin_(["tags", "keyword", "title"]),
        ]
        if keep_ids:
            conditions.append(CollectedData.source_id.notin_(keep_ids))
        stmt = delete(CollectedData).where(*conditions)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def upsert_collected_data(items: list[dict]) -> int:
    """Insert or update collected data items based on (source, source_id).

    If an item with the same source + source_id exists, update it.
    Otherwise insert a new row.

    Returns the number of items upserted.
    """
    if not items:
        return 0

    count = 0
    async with AsyncSessionLocal() as session:
        for item in items:
            source_id = item.get("source_id") or None
            source = item.get("source")
            # Normalize empty source_id to None (MySQL unique index allows multiple NULLs)
            # Truncate to 255 chars to prevent "Data too long" errors
            if source_id and len(source_id) > 255:
                source_id = source_id[:255]
            item["source_id"] = source_id

            # Truncate other String columns to their max lengths
            if item.get("title") and len(item["title"]) > 500:
                item["title"] = item["title"][:500]
            if item.get("source") and len(item["source"]) > 50:
                item["source"] = item["source"][:50]
            if item.get("content_type") and len(item["content_type"]) > 50:
                item["content_type"] = item["content_type"][:50]
            if item.get("url") and len(item["url"]) > 2048:
                item["url"] = item["url"][:2048]
            if item.get("region") and len(item["region"]) > 100:
                item["region"] = item["region"][:100]
            if item.get("published_at") and len(str(item["published_at"])) > 100:
                item["published_at"] = str(item["published_at"])[:100]

            if source_id and source:
                stmt = select(CollectedData).where(
                    CollectedData.source == source,
                    CollectedData.source_id == source_id,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    for key, value in item.items():
                        setattr(existing, key, value)
                else:
                    session.add(CollectedData(**item))
            else:
                session.add(CollectedData(**item))

            count += 1

        await session.commit()

    return count
