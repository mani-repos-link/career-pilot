"""Lifecycle hook registry.

A hook is a callable (sync or async) registered on a named event. When the harness emits
an event, every registered handler runs in registration order. Handlers mutate the payload
dict in place — that's the contract. To short-circuit (e.g., return a synthetic tool result
without executing the real tool), raise HookHalt(payload). The emitter catches it and
returns the halted payload to the caller.

Events fired by the harness (see Step 6):
  model.pre_call   {system_prompt, turns, session_id, agent_name}
  model.post_call  {result, session_id, agent_name}
  tool.pre_call    {request, session_id, agent_name, allowed_names}   -- HookHalt may inject {result}
  tool.post_call   {request, result, session_id, agent_name}
  delegate.pre     {agent, instruction}
  delegate.post    {agent, result}

Handlers should be cheap. Don't make network calls in pre_call hooks unless you mean to
double the latency of every turn. Hook ordering is registration order; document priorities
in your own setup.
"""

from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

logger = logging.getLogger("pyapi.hooks")

HookFn = Callable[[dict[str, Any]], Awaitable[None] | None]


class HookHalt(Exception):
    """Raised by a hook to short-circuit emit. The emitter returns `payload`."""

    def __init__(self, payload: dict[str, Any]):
        super().__init__("hook halted")
        self.payload = payload


class HookRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, list[HookFn]] = defaultdict(list)

    def on(self, event: str) -> Callable[[HookFn], HookFn]:
        def decorator(fn: HookFn) -> HookFn:
            self.register(event, fn)
            return fn

        return decorator

    def register(self, event: str, fn: HookFn) -> None:
        self._handlers[event].append(fn)

    def handlers(self, event: str) -> list[HookFn]:
        return list(self._handlers.get(event, ()))

    async def emit(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        for handler in self._handlers.get(event, ()):
            try:
                outcome = handler(payload)
                if inspect.isawaitable(outcome):
                    await outcome
            except HookHalt as halt:
                return halt.payload
            except Exception:
                logger.exception("hook failure event=%s handler=%s", event, getattr(handler, "__name__", repr(handler)))
        return payload
