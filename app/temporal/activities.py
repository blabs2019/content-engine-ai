from temporalio import activity
from loguru import logger


@activity.defn
async def process_content(content_id: int) -> str:
    logger.info(f"Processing content id={content_id}")
    # Add your content processing logic here
    return f"Content {content_id} processed successfully"
