from __future__ import annotations

from dataclasses import replace

from pyapi.config import ChatConfig

from .huggingface import HuggingFaceProvider
from .openrouter import OpenRouterProvider
from .types import ChatProvider, ChatResult


def create_chat_provider(config: ChatConfig) -> ChatProvider:
    return create_chat_provider_for(config.provider, config.model, config)


def create_chat_provider_for(provider: str, model: str, config: ChatConfig) -> ChatProvider:
    chat = replace(config, provider=provider, model=model)
    if provider == "openrouter":
        return OpenRouterProvider(chat)
    if provider == "huggingface":
        return HuggingFaceProvider(chat)
    return UnsupportedProvider(provider)


class UnsupportedProvider:
    def __init__(self, provider: str):
        self.provider = provider
        self.model = ""

    async def complete(self, *_object: object, **_kwargs: object) -> ChatResult:
        raise ValueError(f'unsupported chat provider "{self.provider}"')
