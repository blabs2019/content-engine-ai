import asyncio
import json

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

HASHTAG_SEARCH_ACTOR = "apify/instagram-scraper"
HASHTAG_POSTS_ACTOR = "reGe1ST3OBgYZSsZJ"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    caption = raw.get("caption") or ""
    hashtags = raw.get("hashtags") or []
    images = raw.get("images") or []
    file_urls = []
    if raw.get("displayUrl"):
        file_urls.append(raw["displayUrl"])
    for img in images:
        if isinstance(img, str) and img not in file_urls:
            file_urls.append(img)

    return {
        "source": "instagram",
        "source_id": str(raw.get("id") or raw.get("shortCode", "")),
        "vertical_id": input.vertical_id,
        "content_type": "post",
        "title": caption[:500] if caption else "Untitled",
        "body": caption,
        "url": raw.get("url"),
        "file_urls": file_urls,
        "raw_data": raw,
        "tags": list(set(input.keywords + hashtags)),
        "region": "US",
        "platform_metadata": {
            "likes": raw.get("likesCount", 0),
            "comments": raw.get("commentsCount", 0),
            "owner_username": raw.get("ownerUsername"),
            "owner_fullname": raw.get("ownerFullName"),
            "type": raw.get("type"),
            "location_name": raw.get("locationName"),
            "location_id": raw.get("locationId"),
            "short_code": raw.get("shortCode"),
            "timestamp": raw.get("timestamp"),
        },
        "published_at": safe_published_at(raw.get("timestamp")),
        "is_trending": False,
    }


@activity.defn
async def collect_instagram_hashtags(input: CollectionInput) -> list[str]:
    """Step 1: Search for trending hashtags and store top 10."""
    logger.info(f"Instagram Step 1: finding hashtags for vertical_id={input.vertical_id}")

    keyword = " ".join(input.keywords) if input.keywords else "trending"

    items = await asyncio.to_thread(run_actor_sync, HASHTAG_SEARCH_ACTOR, {
        "search": keyword,
        "searchLimit": 10,
        "searchType": "hashtag",
        "resultsLimit": 50,
        "addParentData": False,
    })

    # Filter out error/empty items
    valid_items = [i for i in items if not i.get("error") and i.get("name")]

    if not valid_items:
        logger.warning(f"Instagram: no valid hashtags returned for '{keyword}'")
        return [keyword]

    all_names = [h["name"] for h in valid_items if h.get("name")]

    from app.config import get_settings
    top_n_hashtags = get_settings().TOP_N_HASHTAGS

    logger.info(f"Instagram Step 1: scraped {len(all_names)} hashtags, using AI to rank top {top_n_hashtags}")

    # Use LLM to rank and pick the top N most relevant hashtags for the vertical
    from app.services.llm_provider import get_llm_provider, ChatMessage

    vertical_name = input.vertical_name or keyword
    # Include postsCount so LLM can factor in popularity
    name_to_count = {h["name"]: h.get("postsCount", 0) for h in valid_items if h.get("name")}
    hashtags_text = "\n".join(
        f"- {name} (posts: {name_to_count.get(name, 0):,})" for name in all_names
    )
    messages = [
        ChatMessage(
            role="system",
            content=(
                f"You are a social media expert. Given a list of Instagram hashtags (with their "
                f"post counts) and a vertical/niche, rank and pick the top {top_n_hashtags} best hashtags.\n\n"
                f"Consider both relevance to the vertical AND popularity (post count). "
                f"A highly relevant hashtag with good reach is better than a niche one with "
                f"very few posts.\n\n"
                f"Return ONLY a JSON object: {{\"hashtags\": [\"tag1\", \"tag2\", ...]}}\n"
                f"Return exactly the hashtag names from the list, ranked best first, no modifications."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Vertical/Niche: {vertical_name}\n\n"
                f"Available hashtags:\n{hashtags_text}\n\n"
                f"Rank and pick the top {top_n_hashtags} best hashtags for \"{vertical_name}\" considering "
                f"both relevance and popularity. Return as JSON: {{\"hashtags\": [...]}}"
            ),
        ),
    ]

    try:
        llm = get_llm_provider()
        response = await asyncio.to_thread(
            llm.chat_completion, messages, 0.1
        )
        raw_text = response.content.strip()
        if "```" in raw_text:
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]

        import json as json_mod
        parsed = json_mod.loads(raw_text)
        ai_picks = parsed.get("hashtags", [])

        # Validate: only keep hashtags that exist in our scraped list
        valid_set = set(all_names)
        top_names = [h for h in ai_picks if h in valid_set][:top_n_hashtags]

        if not top_names:
            # Fallback: sort by postsCount
            sorted_tags = sorted(valid_items, key=lambda x: x.get("postsCount", 0), reverse=True)
            top_names = [h["name"] for h in sorted_tags[:top_n_hashtags] if h.get("name")]

        logger.info(f"Instagram Step 1: AI picked top 10 hashtags: {top_names}")
    except Exception as e:
        logger.warning(f"Instagram: AI hashtag selection failed ({e}), falling back to postsCount")
        sorted_tags = sorted(valid_items, key=lambda x: x.get("postsCount", 0), reverse=True)
        top_names = [h["name"] for h in sorted_tags[:top_n_hashtags] if h.get("name")]

    logger.info(f"Instagram Step 1: top {top_n_hashtags} hashtags: {top_names}")

    # Build raw data for the kept hashtags
    name_to_raw = {h["name"]: h for h in valid_items if h.get("name")}
    top_hashtag_data = [name_to_raw[n] for n in top_names if n in name_to_raw]

    # Store top hashtags as a collected_data row

    hashtag_row = {
        "source": "instagram",
        "source_id": f"{input.vertical_id}_instagram_top_tag",
        "vertical_id": input.vertical_id,
        "content_type": "tags",
        "title": f"Top Instagram Hashtags for {keyword}",
        "body": json.dumps(top_names),
        "url": None,
        "file_urls": [],
        "raw_data": {"hashtags": top_hashtag_data},
        "tags": input.keywords or [],
        "region": "US",
        "platform_metadata": {},
        "is_trending": False,
    }
    await upsert_collected_data([hashtag_row])
    logger.info(f"Instagram: stored top 10 hashtags for vertical_id={input.vertical_id}")

    return top_names if top_names else [keyword]


@activity.defn
async def collect_instagram_posts(input: CollectionInput) -> CollectionResult:
    """Step 2: Scrape posts from top hashtags."""
    logger.info(f"Instagram Step 2: scraping posts for vertical_id={input.vertical_id}")

    try:
        hashtags = input.keywords if input.keywords else ["trending"]

        items = await asyncio.to_thread(run_actor_sync, HASHTAG_POSTS_ACTOR, {
            "hashtags": hashtags,
            "resultsType": "posts",
            "resultsLimit": 50,
            "keywordSearch": True,
        })

        # Filter out error/empty items from Apify response
        valid_items = [raw for raw in items if not raw.get("error") and (raw.get("id") or raw.get("shortCode"))]
        logger.info(f"Instagram: {len(items)} raw items, {len(valid_items)} valid after filtering")

        normalized = [_normalize(raw, input) for raw in valid_items]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Instagram: scraped {len(normalized)} posts for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="instagram",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Instagram collection failed: {e}")
        return CollectionResult(
            platform="instagram",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
