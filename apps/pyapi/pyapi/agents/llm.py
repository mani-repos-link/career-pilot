from __future__ import annotations

from pyapi.config import ChatConfig
from pyapi.providers import ChatProvider, create_chat_provider_for

from .base import SubAgent


def provider_for_agent(
    agent: SubAgent,
    default_provider: ChatProvider,
    chat_config: ChatConfig,
) -> ChatProvider:
    if not agent.provider_override or not agent.model_override:
        return default_provider
    if (
        agent.provider_override == default_provider.provider
        and agent.model_override == default_provider.model
    ):
        return default_provider
    return create_chat_provider_for(agent.provider_override, agent.model_override, chat_config)
