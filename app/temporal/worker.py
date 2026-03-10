import asyncio

from temporalio.worker import Worker

from app.config import get_settings
from app.temporal.client import get_temporal_client
from app.temporal.activities import process_content
from app.temporal.workflows import ContentProcessingWorkflow
from app.temporal.data_collection.workflows import (
    DataCollectionWorkflow,
    ALL_COLLECTION_WORKFLOWS,
)
from app.temporal.data_collection.activities import ALL_COLLECTION_ACTIVITIES

settings = get_settings()


async def start_worker():
    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[
            ContentProcessingWorkflow,
            DataCollectionWorkflow,
            *ALL_COLLECTION_WORKFLOWS,
        ],
        activities=[
            process_content,
            *ALL_COLLECTION_ACTIVITIES,
        ],
    )

    print(f"Temporal worker started on queue: {settings.TEMPORAL_TASK_QUEUE}")
    await worker.run()


def main():
    asyncio.run(start_worker())


if __name__ == "__main__":
    main()
