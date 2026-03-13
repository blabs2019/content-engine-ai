import asyncio
import json

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput


@activity.defn
async def extract_news_insights(input: CollectionInput) -> None:
    """Extract top keywords and titles from the final google_news articles via AI."""
    logger.info(f"Extracting news insights for vertical_id={input.vertical_id}")

    try:
        from sqlalchemy import select
        from app.database import AsyncSessionLocal as async_session
        from app.models.collected_data import CollectedData
        from app.prompts import load_prompt
        from app.services.llm_provider import get_llm_provider, ChatMessage
        from app.services.data_store import upsert_collected_data

        # 1. Query DB for final google_news articles (post-classification keepers)
        async with async_session() as session:
            result = await session.execute(
                select(CollectedData)
                .where(
                    CollectedData.vertical_id == input.vertical_id,
                    CollectedData.source == "google_news",
                    CollectedData.content_type == "article",
                )
            )
            articles = result.scalars().all()

        if not articles:
            logger.info(f"No google_news articles found for vertical_id={input.vertical_id}")
            return

        # 2. Build article list for AI
        lines = []
        for a in articles:
            line = f"- {a.title}"
            if a.body and a.body[:100] != (a.title or "")[:100]:
                snippet = a.body[:300].strip()
                if len(a.body) > 300:
                    snippet += "..."
                line += f" | {snippet}"
            lines.append(line)
        articles_text = "\n".join(lines)

        # 3. Send to AI
        vertical_name = input.vertical_name or "general"
        system_content = load_prompt("news_insights_system.txt").format(vertical_name=vertical_name)

        messages = [
            ChatMessage(role="system", content=system_content),
            ChatMessage(
                role="user",
                content=(
                    f"Vertical/Niche: {vertical_name}\n\n"
                    f"News articles:\n{articles_text}\n\n"
                    f"Extract the top 10 keywords and top 10 content titles for the "
                    f'"{vertical_name}" vertical. Return as JSON: '
                    f'{{"keywords": [...], "titles": [...]}}'
                ),
            ),
        ]

        llm = get_llm_provider()
        response = await asyncio.to_thread(
            llm.chat_completion, messages, 0.3,
        )
        raw_text = response.content.strip()

        # Parse JSON — handle markdown code blocks
        if "```" in raw_text:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            raw_text = raw_text[json_start:json_end]

        parsed = json.loads(raw_text)
        keywords = parsed.get("keywords", [])[:10]
        titles = parsed.get("titles", [])[:10]

        logger.info(
            f"News insights for '{vertical_name}': "
            f"{len(keywords)} keywords, {len(titles)} titles"
        )

        # 4. Save as two rows (same pattern as Instagram hashtags)
        rows = []
        if keywords:
            rows.append({
                "source": "google_news",
                "source_id": f"{input.vertical_id}_google_news_keywords",
                "vertical_id": input.vertical_id,
                "content_type": "keyword",
                "title": f"Top News Keywords for {vertical_name}",
                "body": json.dumps(keywords),
                "url": None,
                "file_urls": [],
                "raw_data": None,
                "tags": input.keywords or [],
                "region": "US",
                "platform_metadata": {},
                "is_trending": False,
            })
        if titles:
            rows.append({
                "source": "google_news",
                "source_id": f"{input.vertical_id}_google_news_titles",
                "vertical_id": input.vertical_id,
                "content_type": "title",
                "title": f"Top Content Titles for {vertical_name}",
                "body": json.dumps(titles),
                "url": None,
                "file_urls": [],
                "raw_data": None,
                "tags": input.keywords or [],
                "region": "US",
                "platform_metadata": {},
                "is_trending": False,
            })

        if rows:
            await upsert_collected_data(rows)
            logger.info(f"Saved {len(rows)} news insight rows for vertical_id={input.vertical_id}")

    except Exception as e:
        logger.error(f"News insights extraction failed: {e}")
