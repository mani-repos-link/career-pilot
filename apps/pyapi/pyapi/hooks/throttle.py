"""Min-interval throttle between LLM calls.

Hook on ``model.pre_call`` enforces a process-global minimum interval between any
two provider requests. Useful when free-tier endpoints rate-limit aggressively.

Set ``LLM_CALL_THROTTLE_SECONDS`` in the environment (default 0 disables the gate).
Implementation note: the throttle is async — it yields to the event loop, it does
not block other coroutines. It is global because rate limits are per-API-key, not
per-agent.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pyapi.hooks import HookRegistry

logger = logging.getLogger("pyapi.throttle")


def register_llm_call_throttle(hooks: HookRegistry, seconds: float) -> None:
    if seconds <= 0:
        return
    state: dict[str, float] = {"last": 0.0}
    gate = asyncio.Lock()

    async def handler(_payload: dict[str, Any]) -> None:
        async with gate:
            now = time.monotonic()
            delta = now - state["last"]
            if delta < seconds:
                wait = seconds - delta
                logger.info("llm_call.throttle sleep_seconds=%.3f", wait)
                await asyncio.sleep(wait)
            state["last"] = time.monotonic()

    hooks.register("model.pre_call", handler)
