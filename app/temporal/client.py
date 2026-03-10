from temporalio.client import Client
from temporalio.service import TLSConfig

from app.config import get_settings

settings = get_settings()

_client: Client | None = None


def _load_tls_config() -> TLSConfig:
    with open(settings.TEMPORAL_TLS_CERT_FILE, "rb") as f:
        client_cert = f.read()
    with open(settings.TEMPORAL_TLS_KEY_FILE, "rb") as f:
        client_key = f.read()
    return TLSConfig(client_cert=client_cert, client_private_key=client_key)


async def get_temporal_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.TEMPORAL_TARGET,
            namespace=settings.TEMPORAL_NAMESPACE,
            tls=_load_tls_config(),
        )
    return _client
