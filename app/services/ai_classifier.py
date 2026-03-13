import json
from dataclasses import dataclass

from loguru import logger

from app.prompts import load_prompt
from app.services.llm_provider import get_llm_provider, ChatMessage


@dataclass
class ContentItemDTO:
    """Lightweight DTO for AI processing."""

    id: str  # source_id from the platform
    title: str
    reach_score: float = 0.0
    body_snippet: str = ""


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
        return meta.get("reactions", 0) + meta.get("comments", 0) * 2 + meta.get("shares", 0) * 2
    elif source == "meta_ads":
        return float(meta.get("collation_count") or 0)
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

    # Build item lines — include body_snippet when available and different from title
    lines = []
    for item in items:
        line = f"- ID:{item.id} | Reach:{item.reach_score:,.0f} | {item.title}"
        if item.body_snippet and item.body_snippet[:100] != item.title[:100]:
            line += f" | Snippet: {item.body_snippet}"
        lines.append(line)
    items_text = "\n".join(lines)

    # Load system prompt from template file
    template_map = {
        "trending": "trending_system.txt",
        "relevance": "relevance_system.txt",
        "all_time": "all_time_system.txt",
    }
    template_file = template_map.get(mode, "all_time_system.txt")
    system_content = load_prompt(template_file).format(vertical_name=vertical_name)

    suffix_map = {
        "trending": "ranked by trending/viral potential (most buzzy first)",
        "relevance": "ranked by relevance (most relevant first). Return ALL item IDs, ranked",
        "all_time": "ranked by quality + evergreen value (best first)",
    }
    user_suffix = suffix_map.get(mode, suffix_map["all_time"])

    user_content = load_prompt("user_prompt.txt").format(
        vertical_name=vertical_name,
        items_text=items_text,
        top_n=top_n,
        user_suffix=user_suffix,
    )

    messages = [
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user", content=user_content),
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
