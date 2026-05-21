from __future__ import annotations

from pyapi.config import ChatConfig

from .compatible import OpenAICompatibleProvider


class HuggingFaceProvider(OpenAICompatibleProvider):
    def __init__(self, config: ChatConfig):
        super().__init__(
            provider="huggingface",
            base_url=config.huggingface_base_url,
            api_key=config.huggingface_api_key,
            model=config.model,
            http_referer=config.http_referer,
            app_title=config.app_title,
        )
