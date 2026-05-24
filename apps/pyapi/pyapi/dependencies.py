from __future__ import annotations

from dataclasses import dataclass

from pyapi.agents import SubAgent
from pyapi.config import ChatConfig, ContextConfig, ToolConfig
from pyapi.hooks import HookRegistry
from pyapi.hooks.lifecycle_logger import LifecycleLogger
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
    hooks: HookRegistry
    lifecycle: LifecycleLogger
