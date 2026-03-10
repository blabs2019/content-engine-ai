import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.data_collection.shared import (
        CollectionInput,
        CollectionResult,
        MasterCollectionResult,
        ClassificationInput,
    )
    from app.temporal.data_collection.activities import (
        collect_facebook,
        collect_instagram_hashtags,
        collect_instagram_posts,
        collect_twitter,
        collect_reddit,
        collect_google_news,
        collect_youtube,
        collect_linkedin,
        collect_meta_ads,
        classify_collected_data,
    )

NO_RETRY = RetryPolicy(maximum_attempts=1)

# Activities used by the master fan-out (Instagram is handled by its own 2-step workflow)
PLATFORM_ACTIVITIES = {
    "facebook": collect_facebook,
    "twitter": collect_twitter,
    "reddit": collect_reddit,
    "google_news": collect_google_news,
    "youtube": collect_youtube,
    "linkedin": collect_linkedin,
    "meta_ads": collect_meta_ads,
}


async def _run_classification(input: CollectionInput, source: str, data: list[dict]) -> None:
    """Helper: run AI classification activities.

    google_news  → single relevance call (no trending/all-time split)
    all others   → TWO separate calls: trending then all_time
    """
    if not input.vertical_name or not data:
        return

    if source == "meta_ads":
        return  # meta_ads does AI filtering inside its own scraper activity

    if source == "google_news":
        # Single call — relevance ranking (no engagement data)
        await workflow.execute_activity(
            classify_collected_data,
            ClassificationInput(
                vertical_id=input.vertical_id,
                source=source,
                vertical_name=input.vertical_name,
                items_data=data,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=NO_RETRY,
        )
        return

    # Call 1: Trending — clears old data, filters recent items, saves trending keepers
    await workflow.execute_activity(
        classify_collected_data,
        ClassificationInput(
            vertical_id=input.vertical_id,
            source=source,
            vertical_name=input.vertical_name,
            items_data=data,
            mode="trending",
        ),
        start_to_close_timeout=timedelta(minutes=10),
        retry_policy=NO_RETRY,
    )

    # Call 2: All-time favourite — no clear, upserts all-time keepers
    await workflow.execute_activity(
        classify_collected_data,
        ClassificationInput(
            vertical_id=input.vertical_id,
            source=source,
            vertical_name=input.vertical_name,
            items_data=data,
            mode="all_time",
        ),
        start_to_close_timeout=timedelta(minutes=10),
        retry_policy=NO_RETRY,
    )


@workflow.defn
class FacebookCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_facebook, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "facebook", result.data)
        return result


@workflow.defn
class InstagramCollectionWorkflow:
    """2-step workflow: discover hashtags → scrape posts from those hashtags."""

    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        # Step 1: get top trending hashtags for the keyword
        hashtags = await workflow.execute_activity(
            collect_instagram_hashtags,
            input,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=NO_RETRY,
        )

        # Step 2: scrape posts from those hashtags
        updated_input = CollectionInput(
            vertical_id=input.vertical_id,
            keywords=hashtags,
            season_context=input.season_context,
            vertical_name=input.vertical_name,
        )
        result = await workflow.execute_activity(
            collect_instagram_posts,
            updated_input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )

        # Step 3: AI classification (pass scraped data)
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "instagram", result.data)
        return result


@workflow.defn
class TwitterCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_twitter, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "twitter", result.data)
        return result


@workflow.defn
class RedditCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_reddit, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "reddit", result.data)
        return result


@workflow.defn
class GoogleNewsCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_google_news, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "google_news", result.data)
        return result


@workflow.defn
class YouTubeCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_youtube, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "youtube", result.data)
        return result


@workflow.defn
class LinkedInCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_linkedin, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "linkedin", result.data)
        return result


@workflow.defn
class MetaAdsCollectionWorkflow:
    @workflow.run
    async def run(self, input: CollectionInput) -> CollectionResult:
        result = await workflow.execute_activity(
            collect_meta_ads, input,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NO_RETRY,
        )
        if result.status == "success" and result.items_collected > 0:
            await _run_classification(input, "meta_ads", result.data)
        return result


ALL_COLLECTION_WORKFLOWS = [
    FacebookCollectionWorkflow,
    InstagramCollectionWorkflow,
    TwitterCollectionWorkflow,
    RedditCollectionWorkflow,
    GoogleNewsCollectionWorkflow,
    YouTubeCollectionWorkflow,
    LinkedInCollectionWorkflow,
    MetaAdsCollectionWorkflow,
]


@workflow.defn
class DataCollectionWorkflow:
    """Master workflow that fans out to all platform activities concurrently."""

    @workflow.run
    async def run(self, input: CollectionInput) -> MasterCollectionResult:
        tasks = []
        platform_names = []

        # Fan out non-Instagram platforms as direct activities
        for name, activity_fn in PLATFORM_ACTIVITIES.items():
            platform_names.append(name)
            tasks.append(
                workflow.execute_activity(
                    activity_fn, input,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=NO_RETRY,
                )
            )

        # Instagram: run as child workflow (2-step process, handles its own classification)
        platform_names.append("instagram")
        tasks.append(
            workflow.execute_child_workflow(
                InstagramCollectionWorkflow.run,
                input,
                id=f"collect-instagram-v{input.vertical_id}-child",
            )
        )

        settled = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for i, outcome in enumerate(settled):
            if isinstance(outcome, Exception):
                results.append(CollectionResult(
                    platform=platform_names[i],
                    vertical_id=input.vertical_id,
                    items_collected=0,
                    status="error",
                    error_message=str(outcome),
                ))
            else:
                results.append(outcome)

        # Run AI classification for each successful non-Instagram platform
        # (Instagram classification is handled inside InstagramCollectionWorkflow)
        # Each platform gets 2 sequential calls (trending + all_time), platforms run concurrently
        classification_coros = []
        for r in results:
            if r.platform == "instagram":
                continue  # Already classified in child workflow
            if r.status == "success" and r.items_collected > 0 and input.vertical_name:
                classification_coros.append(
                    _run_classification(input, r.platform, r.data)
                )

        if classification_coros:
            await asyncio.gather(*classification_coros, return_exceptions=True)

        total = sum(r.items_collected for r in results)
        return MasterCollectionResult(
            vertical_id=input.vertical_id,
            platform_results=results,
            total_items_collected=total,
        )
