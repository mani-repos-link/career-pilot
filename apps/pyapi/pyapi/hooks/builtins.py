"""Built-in hooks registered at startup.

- inject_memories: on model.pre_call, appends the current session+global memory block to
  the system prompt. Reads memories via MemoryStore.
- inject_profile: on delegate.pre for the resume_tailor agent, wraps the instruction with
  the candidate profile YAML so the sub-agent has the data it needs.

Add new built-ins here and register them in register_builtins().
"""

from __future__ import annotations

import logging
from typing import Any

from pyapi.config import ContextConfig
from pyapi.hooks import HookRegistry
from pyapi.hooks.lifecycle_logger import LifecycleLogger, register_lifecycle_logger
from pyapi.hooks.throttle import register_llm_call_throttle
from pyapi.inputs import load_profile_yaml
from pyapi.memory import MemoryStore, format_memory_block

logger = logging.getLogger("pyapi.hooks.builtins")


def register_builtins(
    hooks: HookRegistry,
    *,
    memory_store: MemoryStore,
    context: ContextConfig,
) -> LifecycleLogger:
    lifecycle = register_lifecycle_logger(hooks)
    register_llm_call_throttle(hooks, context.llm_call_throttle_seconds)
    hooks.register("model.pre_call", _memory_injector(memory_store, context))
    hooks.register("delegate.pre", _profile_injector())
    return lifecycle


def _memory_injector(memory_store: MemoryStore, context: ContextConfig):
    def inject(payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id")
        if not session_id:
            return
        memories = memory_store.list(session_id, include_global=True)
        block = format_memory_block(memories, max_chars=context.max_memory_chars)
        if not block:
            return
        prompt = payload.get("system_prompt") or ""
        payload["system_prompt"] = f"{prompt}\n\n{block}" if prompt else block

    return inject


def _profile_injector():
    def inject(payload: dict[str, Any]) -> None:
        agent = payload.get("agent")
        if agent is None or getattr(agent, "name", None) != "resume_tailor":
            return
        try:
            profile_yaml = load_profile_yaml()
        except FileNotFoundError as err:
            logger.warning("resume_tailor: %s", err)
            return
        instruction = payload.get("instruction") or ""
        payload["instruction"] = f"<profile>\n{profile_yaml}\n</profile>\n\n{instruction}"

    return inject
