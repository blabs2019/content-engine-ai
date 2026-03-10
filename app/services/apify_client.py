from apify_client import ApifyClient
from loguru import logger

from app.config import get_settings

settings = get_settings()


def run_actor_sync(actor_id: str, run_input: dict) -> list[dict]:
    """Run an Apify actor and return dataset items using the official SDK.

    This is synchronous — call via asyncio.to_thread() from async activities.
    """
    logger.info(f"Apify: starting actor {actor_id}")

    client = ApifyClient(settings.APIFY_TOKEN)
    run = client.actor(actor_id).call(run_input=run_input, max_total_charge_usd=1.0)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    logger.info(f"Apify: actor {actor_id} returned {len(items)} items")
    return items
