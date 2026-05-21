from __future__ import annotations

from pyapi.config import ChatConfig

from .compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, config: ChatConfig):
        super().__init__(
            provider="openrouter",
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key,
            model=config.model,
            http_referer=config.http_referer,
            app_title=config.app_title,
        )
