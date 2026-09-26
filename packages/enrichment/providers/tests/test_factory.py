import httpx

from packages.enrichment.providers.factory import create_configured_ai_provider
from packages.shared.config import Settings


def test_provider_factory_is_disabled_without_explicit_model_configuration() -> None:
    with httpx.Client() as sync_client:
        del sync_client
    client = httpx.AsyncClient()
    try:
        assert create_configured_ai_provider(Settings(), client) is None
        assert (
            create_configured_ai_provider(
                Settings(model_base_url="https://provider.example/v1"),
                client,
            )
            is None
        )
        provider = create_configured_ai_provider(
            Settings(
                model_base_url="https://provider.example/v1",
                model_name="chat-model",
                embedding_model_name="embedding-model",
                embedding_dimensions=3,
            ),
            client,
        )
        assert provider is not None
        assert provider.name == "chat-model"
    finally:
        import asyncio

        asyncio.run(client.aclose())
