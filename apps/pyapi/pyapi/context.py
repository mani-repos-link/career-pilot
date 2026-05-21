from __future__ import annotations

from .config import ContextConfig
from .store import MessageRecord


def build_llm_context(messages: list[MessageRecord], config: ContextConfig) -> list[MessageRecord]:
    return messages[-config.max_history_messages:]
