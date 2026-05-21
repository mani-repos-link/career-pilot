from __future__ import annotations

from dataclasses import dataclass

from pyapi.agents import SubAgent
from pyapi.config import ChatConfig, ContextConfig, ToolConfig
from pyapi.providers import ChatProvider
from pyapi.store import Store


@dataclass(frozen=True)
class AppServices:
    store: Store
    chat_provider: ChatProvider
    chat_config: ChatConfig
    context: ContextConfig
    tools: ToolConfig
    catalog: dict[str, SubAgent]
