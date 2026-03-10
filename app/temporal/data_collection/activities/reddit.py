import asyncio

from temporalio import activity
from loguru import logger

from app.temporal.data_collection.shared import CollectionInput, CollectionResult, safe_published_at
from app.services.apify_client import run_actor_sync

ACTOR_ID = "oAuCIx3ItNrs2okjQ"


def _normalize(raw: dict, input: CollectionInput) -> dict:
    title = raw.get("title") or ""
    body = raw.get("body") or ""
    image_urls = raw.get("imageUrls") or []
    if raw.get("thumbnailUrl"):
        image_urls = [raw["thumbnailUrl"]] + [u for u in image_urls if u != raw["thumbnailUrl"]]
    return {
        "source": "reddit",
        "source_id": str(raw.get("id") or raw.get("parsedId", "")),
        "vertical_id": input.vertical_id,
        "content_type": "post",
        "title": title[:500] if title else "Untitled",
        "body": body,
        "url": raw.get("url"),
        "file_urls": [u for u in image_urls if isinstance(u, str) and u.startswith("http")],
        "raw_data": raw,
        "tags": list(set(input.keywords + [raw.get("parsedCommunityName", "")])),
        "region": "US",
        "platform_metadata": {
            "upvotes": raw.get("upVotes", 0),
            "upvote_ratio": raw.get("upVoteRatio", 0),
            "comments": raw.get("numberOfComments", 0),
            "username": raw.get("username"),
            "community": raw.get("communityName"),
            "parsed_community": raw.get("parsedCommunityName"),
            "flair": raw.get("flair"),
            "is_video": raw.get("isVideo", False),
            "external_link": raw.get("link"),
            "created_at": raw.get("createdAt"),
            "over_18": raw.get("over18", False),
        },
        "published_at": safe_published_at(raw.get("createdAt")),
        "is_trending": False,
    }


@activity.defn
async def collect_reddit(input: CollectionInput) -> CollectionResult:
    logger.info(f"Collecting Reddit data for vertical_id={input.vertical_id}")

    try:
        keyword = " ".join(input.keywords) if input.keywords else "trending"

        items = await asyncio.to_thread(run_actor_sync, ACTOR_ID, {
            "searches": [keyword],
            "searchPosts": True,
            "searchComments": False,
            "searchCommunities": False,
            "searchUsers": False,
            "sort": "hot",
            "maxItems": 50,
            "maxPostCount": 50,
            "maxComments": 0,
            "includeNSFW": False,
            "skipComments": True,
            "skipCommunity": False,
            "skipUserPosts": False,
            "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        })

        # Filter: only posts, skip comments and ads
        valid_items = [raw for raw in items if raw.get("dataType") == "post" and not raw.get("isAd", False)]
        logger.info(f"Reddit: {len(items)} raw items, {len(valid_items)} valid posts after filtering")

        normalized = [_normalize(raw, input) for raw in valid_items]
        for item in normalized:
            item.pop("raw_data", None)

        logger.info(f"Reddit: scraped {len(normalized)} items for vertical_id={input.vertical_id}")
        return CollectionResult(
            platform="reddit",
            vertical_id=input.vertical_id,
            items_collected=len(normalized),
            status="success",
            data=normalized,
        )
    except Exception as e:
        logger.error(f"Reddit collection failed: {e}")
        return CollectionResult(
            platform="reddit",
            vertical_id=input.vertical_id,
            items_collected=0,
            status="error",
            error_message=str(e),
        )
