import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync
from app.services.data_store import upsert_collected_data

ACTOR_ID = "buIWk2uOUzTmcLsuB"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    content = raw.get("content") or ""
    author = raw.get("author") or {}
    engagement = raw.get("engagement") or {}
    posted_at = raw.get("postedAt") or {}

    # Collect image URLs from postImages array
    image_urls = []
    for img in (raw.get("postImages") or []):
        if img.get("url"):
            image_urls.append(img["url"])
    # Add video thumbnail if present
    post_video = raw.get("postVideo") or {}
    if post_video.get("thumbnailUrl"):
        image_urls.append(post_video["thumbnailUrl"])
    # Add article image if present
    article = raw.get("article") or {}
    article_img = article.get("image") or {}
    if article_img.get("url"):
        image_urls.append(article_img["url"])

    return {
        "source": "linkedin",
        "source_id": str(raw.get("id") or raw.get("entityId", "")),
        "vertical_id": input.vertical_id,
        "content_type": "post",
        "title": content[:500] if content else "Untitled",
        "body": content,
        "url": raw.get("linkedinUrl"),
        "file_urls": image_urls,
        "raw_data": raw,
        "tags": input.keywords or [],
        "region": "US",
        "platform_metadata": {
            "likes": engagement.get("likes", 0),
            "comments": engagement.get("comments", 0),
            "shares": engagement.get("shares", 0),
            "reactions": engagement.get("reactions", []),
            "author_name": author.get("name"),
            "author_type": author.get("type"),
            "author_info": author.get("info"),
            "author_url": author.get("linkedinUrl"),
            "posted_date": posted_at.get("date"),
            "posted_ago": posted_at.get("postedAgoText"),
            "article_title": article.get("title"),
            "article_link": article.get("link"),
            "has_video": bool(post_video.get("videoUrl")),
        },
        "published_at": safe_published_at(posted_at.get("date")),
        "is_trending": False,
    }


@activity.defn
async def collect_linkedin(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting LinkedIn data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "searchQueries": [keyword],
            "maxPosts": 50,
            "scrapeReactions": False,
            "scrapeComments": False,
        })

        # Filter: only posts
        valid_items = [raw for raw in items if raw.get("type") == "post"]
        logger.info(f"LinkedIn: {len(items)} raw items, {len(valid_items)} valid posts after filtering")

        normalized = [_normalize(raw, input) for raw in valid_items]
        await upsert_collected_data(normalized)
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"LinkedIn: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="linkedin",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"LinkedIn collection failed: {e}")
        return CollectionResult(
            platform="linkedin",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
