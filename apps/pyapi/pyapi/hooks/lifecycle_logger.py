"""Stdout lifecycle logger.

Registers handlers on every event the harness emits and prints one structured line
per step via the ``pyapi.lifecycle`` logger. The default logging config writes to
stdout (see main.py), so this is a zero-extra-config trace of the whole pipeline.

Each line is keyed by ``[<session_id>|#<seq>]`` so steps within one turn correlate.
Every line carries the ``agent`` it belongs to. LLM-call lines (``model.pre_call`` /
``model.post_call``) and tool lines also carry ``provider`` and ``model`` so it is
obvious which model handled which task — handy when sub-agents have their own LLMs.

The sequence counter is per-session and lives only in process memory. Per-turn
usage (counts of LLM calls per agent+model) is tracked in ``_turn_usage`` and
flushed via ``turn_summary``.

Sample (sub-agent on a different model):

    [ses|#1] turn.start agent=main
    [ses|#2] model.pre_call agent=main provider=openrouter model=openrouter/owl-alpha turns=3
    [ses|#3] model.post_call agent=main provider=openrouter model=openrouter/owl-alpha content_chars=145
    [ses|#4] tool.pre_call agent=main tool=ls provider=openrouter model=openrouter/owl-alpha args=['path']
    [ses|#5] tool.post_call agent=main tool=ls ok=True out_chars=42
    [ses|#6] delegate.pre agent=resume_tailor instruction_chars=1780
    [ses|#7] model.pre_call agent=resume_tailor provider=openrouter model=google/gemma-3-27b-it:free turns=1
    [ses|#8] model.post_call agent=resume_tailor provider=openrouter model=google/gemma-3-27b-it:free content_chars=2100
    [ses|#9] turn.summary calls=main:openrouter/owl-alpha=2, resume_tailor:google/gemma-3-27b-it:free=1
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any

from pyapi.hooks import HookRegistry

logger = logging.getLogger("pyapi.lifecycle")


class LifecycleLogger:
    def __init__(self) -> None:
        self._seq: dict[str, int] = defaultdict(int)
        self._turn_usage: dict[str, Counter[str]] = defaultdict(Counter)

    def _tick(self, session_id: str | None) -> tuple[str, int]:
        sid = session_id or "unknown"
        self._seq[sid] += 1
        return sid, self._seq[sid]

    def on_model_pre_call(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent_name") or "main"
        provider = payload.get("provider") or "?"
        model = payload.get("model") or "?"
        turns = payload.get("turns") or []
        prompt = payload.get("system_prompt") or ""
        self._turn_usage[sid][f"{agent}:{model}"] += 1
        logger.info(
            "[%s|#%d] model.pre_call agent=%s provider=%s model=%s turns=%d system_chars=%d",
            sid, n, agent, provider, model, len(turns), len(prompt),
        )

    def on_model_post_call(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent_name") or "main"
        result = payload.get("result")
        provider = payload.get("provider") or getattr(result, "provider", "?")
        model = payload.get("model") or getattr(result, "model", "?")
        logger.info(
            "[%s|#%d] model.post_call agent=%s provider=%s model=%s content_chars=%d",
            sid, n, agent, provider, model,
            len(getattr(result, "content", "") or ""),
        )

    def on_tool_pre_call(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent_name") or "main"
        provider = payload.get("provider") or "?"
        model = payload.get("model") or "?"
        request = payload.get("request")
        args = getattr(request, "arguments", {}) or {}
        logger.info(
            "[%s|#%d] tool.pre_call agent=%s tool=%s provider=%s model=%s args=%s",
            sid, n, agent,
            getattr(request, "tool", "?"),
            provider, model,
            sorted(args.keys()),
        )

    def on_tool_post_call(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent_name") or "main"
        request = payload.get("request")
        result = payload.get("result")
        logger.info(
            "[%s|#%d] tool.post_call agent=%s tool=%s ok=%s out_chars=%d",
            sid, n, agent,
            getattr(request, "tool", "?"),
            getattr(result, "ok", "?"),
            len(getattr(result, "output", "") or ""),
        )

    def on_delegate_pre(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent")
        instruction = payload.get("instruction") or ""
        logger.info(
            "[%s|#%d] delegate.pre agent=%s instruction_chars=%d",
            sid, n,
            getattr(agent, "name", "?"),
            len(instruction),
        )

    def on_delegate_post(self, payload: dict[str, Any]) -> None:
        sid, n = self._tick(payload.get("session_id"))
        agent = payload.get("agent")
        result = payload.get("result")
        provider = payload.get("provider") or getattr(result, "provider", "?")
        model = payload.get("model") or getattr(result, "model", "?")
        logger.info(
            "[%s|#%d] delegate.post agent=%s provider=%s model=%s content_chars=%d",
            sid, n,
            getattr(agent, "name", "?"),
            provider, model,
            len(getattr(result, "content", "") or ""),
        )

    def turn_start(self, session_id: str, *, agent: str = "main") -> None:
        sid, n = self._tick(session_id)
        self._turn_usage.pop(sid, None)
        logger.info("[%s|#%d] turn.start agent=%s", sid, n, agent)

    def turn_end(self, session_id: str, *, agent: str = "main", reason: str = "ok") -> None:
        sid, n = self._tick(session_id)
        logger.info("[%s|#%d] turn.end agent=%s reason=%s", sid, n, agent, reason)
        usage = self._turn_usage.pop(sid, Counter())
        if usage:
            summary = ", ".join(f"{key}={count}" for key, count in usage.most_common())
            logger.info("[%s|#summary] turn.summary llm_calls=%s", sid, summary)


def register_lifecycle_logger(hooks: HookRegistry) -> LifecycleLogger:
    handler = LifecycleLogger()
    hooks.register("model.pre_call", handler.on_model_pre_call)
    hooks.register("model.post_call", handler.on_model_post_call)
    hooks.register("tool.pre_call", handler.on_tool_pre_call)
    hooks.register("tool.post_call", handler.on_tool_post_call)
    hooks.register("delegate.pre", handler.on_delegate_pre)
    hooks.register("delegate.post", handler.on_delegate_post)
    return handler
