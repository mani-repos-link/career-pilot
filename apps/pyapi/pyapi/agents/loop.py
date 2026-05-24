"""One LLM round-trip + optional tool execution. Shared by main loop and sub-agent runs.

The outer iteration belongs to the caller — that's where main vs sub-agent differs (sub-agent
delegations are disabled, main allows them). `tool_step` is the inner unit both share: pre-call
hooks, the LLM call itself, post-call hooks, optional tool execution with its own hook pair.

Step 4 (hook registry) wires the emit sites in this module. Step 6 fills the actual hook events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pyapi.config import ToolConfig
from pyapi.hooks import HookRegistry
from pyapi.providers import ChatProvider, ChatResult, Turn
from pyapi.tools import (
    ToolExecutionResult,
    ToolRequest,
    execute_tool_call_async,
    format_tool_result,
    parse_tool_call,
)


@dataclass(frozen=True)
class ToolStepResult:
    """Outcome of one LLM round-trip.

    `tool_request` is None when the model produced a terminal answer; the caller returns
    `chat_result` to the user. Otherwise the caller appends the assistant turn + tool result
    turn to history and iterates.
    """

    chat_result: ChatResult
    tool_request: ToolRequest | None
    tool_result: ToolExecutionResult | None


async def tool_step(
    provider: ChatProvider,
    system_prompt: str,
    turns: list[Turn],
    max_response_tokens: int,
    *,
    session_id: str,
    tools_config: ToolConfig,
    hooks: HookRegistry,
    allowed_names: Iterable[str] | None = None,
    agent_name: str | None = None,
) -> ToolStepResult:
    pre = await hooks.emit(
        "model.pre_call",
        {
            "system_prompt": system_prompt,
            "turns": turns,
            "session_id": session_id,
            "agent_name": agent_name,
            "provider": provider.provider,
            "model": provider.model,
        },
    )
    chat_result = await provider.complete(
        pre["turns"],
        max_response_tokens,
        system_prompt=pre["system_prompt"],
    )
    await hooks.emit(
        "model.post_call",
        {
            "result": chat_result,
            "session_id": session_id,
            "agent_name": agent_name,
            "provider": provider.provider,
            "model": provider.model,
        },
    )

    if not tools_config.enabled:
        return ToolStepResult(chat_result=chat_result, tool_request=None, tool_result=None)

    request = parse_tool_call(chat_result.content, model=chat_result.model or provider.model)
    if request is None:
        return ToolStepResult(chat_result=chat_result, tool_request=None, tool_result=None)

    pre_tool = await hooks.emit(
        "tool.pre_call",
        {
            "request": request,
            "session_id": session_id,
            "agent_name": agent_name,
            "allowed_names": allowed_names,
            "provider": provider.provider,
            "model": provider.model,
        },
    )
    if "result" in pre_tool and isinstance(pre_tool["result"], ToolExecutionResult):
        result = pre_tool["result"]
    else:
        result = await execute_tool_call_async(
            tools_config,
            request,
            current_session_id=session_id,
            allowed_names=allowed_names,
        )

    await hooks.emit(
        "tool.post_call",
        {
            "request": request,
            "result": result,
            "session_id": session_id,
            "agent_name": agent_name,
            "provider": provider.provider,
            "model": provider.model,
        },
    )
    return ToolStepResult(chat_result=chat_result, tool_request=request, tool_result=result)


def append_tool_turns(turns: list[Turn], step: ToolStepResult) -> None:
    """Mutate turns in place: assistant call + system-formatted tool result."""
    assert step.tool_result is not None
    turns.append(Turn("assistant", step.chat_result.content))
    turns.append(Turn("system", format_tool_result(step.tool_result)))
