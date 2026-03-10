import json
from dataclasses import dataclass

from loguru import logger

from app.services.llm_provider import get_llm_provider, ChatMessage


@dataclass
class ContentItemDTO:
    """Lightweight DTO for AI processing."""

    id: str  # source_id from the platform
    title: str
    reach_score: float = 0.0


def compute_reach_score(source: str, platform_metadata: dict | None) -> float:
    """Compute a unified engagement/reach score from platform-specific metadata."""
    if not platform_metadata:
        return 0.0

    meta = platform_metadata
    source = source.lower()

    if source == "twitter":
        return (
            meta.get("likes", 0)
            + meta.get("retweets", 0) * 2
            + meta.get("views", 0) * 0.01
        )
    elif source == "reddit":
        return float(meta.get("upvotes", 0))
    elif source == "instagram":
        return meta.get("likes", 0) + meta.get("comments", 0) * 2
    elif source == "youtube":
        return meta.get("views", 0) * 0.01 + meta.get("likes", 0)
    elif source == "linkedin":
        return (
            meta.get("likes", 0)
            + meta.get("shares", 0) * 2
            + meta.get("comments", 0)
        )
    elif source == "facebook":
        return meta.get("reactions", 0) + meta.get("comments", 0) * 2
    elif source == "meta_ads":
        return float(meta.get("collation_count", 0))
    else:
        # google_news and unknown sources
        return 0.0


def classify_content(
    items: list[ContentItemDTO],
    vertical_name: str,
    top_n: int = 10,
    mode: str = "all_time",
    provider_name: str | None = None,
) -> list[str]:
    """Send items to LLM and get back source_ids relevant to the vertical.

    Synchronous — call via asyncio.to_thread from async activities.
    Returns a list of source_ids ranked by the mode's criteria (best first).
    Only includes genuinely relevant items.
    Returns [] on any failure — never breaks the pipeline.

    mode:
      - "trending": prioritise viral, buzzy, timely content
      - "all_time": prioritise evergreen quality, educational value, depth
    """
    if not items:
        return []

    llm = get_llm_provider(provider_name)

    # Build the item list for the prompt (include reach_score so AI factors in popularity)
    items_text = "\n".join(
        f"- ID:{item.id} | Reach:{item.reach_score:,.0f} | {item.title}"
        for item in items
    )

    if mode == "trending":
        system_content = (
            "You are a social media trend analyst. You will be given a list of RECENT content items "
            "(each with an ID, reach score, and title) and a vertical/niche name. Your job is to "
            "identify the most TRENDING and VIRAL items — content that is generating buzz right now.\n\n"
            "Prioritise: viral potential, high engagement velocity (high reach relative to recency), "
            "controversial or conversation-starting topics, breaking news, and timely content.\n\n"
            "Deprioritise: evergreen/educational content, generic advice, and low-engagement posts.\n\n"
            "Return ONLY a JSON object with a single key 'ranked_ids' containing an array of "
            "item IDs (as strings) ordered by trending/viral score (most viral first). Include only "
            "items genuinely relevant to the vertical.\n\n"
            "Example response:\n"
            '{"ranked_ids": ["abc123", "def456", "ghi789"]}'
        )
        user_suffix = "ranked by trending/viral potential (most buzzy first)"
    elif mode == "relevance":
        system_content = (
            "You are a content relevance analyst. You will be given a list of content items "
            "(each with an ID and title) and a vertical/niche name. Your job is to "
            "rank ALL items by how relevant they are to the given vertical.\n\n"
            "Prioritise: directly related to the vertical, informative, newsworthy, "
            "practical, or educational for people in this niche.\n\n"
            "IMPORTANT: You MUST return ALL item IDs, ranked from most relevant to least relevant. "
            "Do NOT filter out items — include every single item in your ranking. "
            "The caller will decide how many to keep.\n\n"
            "Return ONLY a JSON object with a single key 'ranked_ids' containing an array of "
            "ALL item IDs (as strings) ordered by relevance (most relevant first).\n\n"
            "Example response:\n"
            '{"ranked_ids": ["abc123", "def456", "ghi789"]}'
        )
        user_suffix = "ranked by relevance (most relevant first). Return ALL item IDs, ranked"
    else:
        system_content = (
            "You are a content quality analyst. You will be given a list of content items "
            "(each with an ID, reach score, and title) and a vertical/niche name. Your job is to "
            "identify the highest-quality, most VALUABLE items — content that is evergreen and worth saving.\n\n"
            "Prioritise: educational depth, practical how-to guides, industry insights, expert knowledge, "
            "inspirational stories, and genuinely useful information for the vertical.\n\n"
            "Deprioritise: viral fluff, memes, low-effort humour, rage-bait, and engagement farming.\n\n"
            "Return ONLY a JSON object with a single key 'ranked_ids' containing an array of "
            "item IDs (as strings) ordered by quality + value (best first). Include only "
            "items genuinely relevant to the vertical.\n\n"
            "Example response:\n"
            '{"ranked_ids": ["abc123", "def456", "ghi789"]}'
        )
        user_suffix = "ranked by quality + evergreen value (best first)"

    messages = [
        ChatMessage(role="system", content=system_content),
        ChatMessage(
            role="user",
            content=(
                f"Vertical/Niche: {vertical_name}\n\n"
                f"Content items:\n{items_text}\n\n"
                f"Return the top {top_n} most relevant items for the "
                f'"{vertical_name}" vertical, {user_suffix}. Return as JSON: '
                f'{{"ranked_ids": [...]}}'
            ),
        ),
    ]

    raw_text = ""
    try:
        response = llm.chat_completion(messages, temperature=0.1)
        raw_text = response.content.strip()

        # Parse JSON — handle markdown code blocks
        if "```" in raw_text:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            raw_text = raw_text[json_start:json_end]

        parsed = json.loads(raw_text)
        ranked_ids = parsed.get("ranked_ids", [])

        # Validate: convert to string and keep only known IDs
        valid_ids = {item.id for item in items}
        filtered = [str(id_) for id_ in ranked_ids if str(id_) in valid_ids]

        logger.info(
            f"AI classification for '{vertical_name}': "
            f"{len(filtered)} relevant items from {len(items)} total"
        )
        return filtered

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}. Raw: {raw_text[:200]}")
        return []
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        return []
