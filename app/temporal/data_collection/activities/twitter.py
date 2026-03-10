import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

ACTOR_ID = "nfp1fpt5gUlBwPcor"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    text = raw.get("text") or raw.get("fullText") or ""
    author = raw.get("author") or {}
    entities = raw.get("entities") or {}
    hashtags = [h.get("text", "") for h in (entities.get("hashtags") or [])]
    media = raw.get("media") or []
    return {
        "source": "twitter",
        "source_id": str(raw.get("id", "")),
        "vertical_id": input.vertical_id,
        "content_type": "post",
        "title": text[:500] if text else "Untitled",
        "body": text,
        "url": raw.get("url") or raw.get("twitterUrl"),
        "file_urls": [u for u in media if isinstance(u, str)],
        "raw_data": raw,
        "tags": list(set(input.keywords + hashtags)),
        "region": "US",
        "platform_metadata": {
            "likes": raw.get("likeCount", 0),
            "retweets": raw.get("retweetCount", 0),
            "replies": raw.get("replyCount", 0),
            "quotes": raw.get("quoteCount", 0),
            "views": raw.get("viewCount", 0),
            "bookmarks": raw.get("bookmarkCount", 0),
            "author_username": author.get("userName"),
            "author_name": author.get("name"),
            "author_followers": author.get("followers", 0),
            "author_verified": author.get("isBlueVerified", False),
            "created_at": raw.get("createdAt"),
            "is_reply": raw.get("isReply", False),
            "is_retweet": raw.get("isRetweet", False),
            "is_quote": raw.get("isQuote", False),
            "lang": raw.get("lang"),
        },
        "published_at": safe_published_at(raw.get("createdAt")),
        "is_trending": False,
    }


@activity.defn
async def collect_twitter(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting Twitter data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "searchTerms": [keyword],
            "sort": "Top",
            "maxItems": 50,
        })

        normalized = [_normalize(raw, input) for raw in items if raw.get("type") == "tweet"]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Twitter: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="twitter",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Twitter collection failed: {e}")
        return CollectionResult(
            platform="twitter",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
