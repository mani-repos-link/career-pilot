from __future__ import annotations

import json
import re
from typing import Callable, Iterable

from pyapi.config import ToolConfig
from pyapi.hooks import HookRegistry
from pyapi.providers import ChatProvider, ChatResult, Turn
from pyapi.tools.manifest import CapabilitySpec, MANIFEST
from pyapi.tools.parser import parse_tool_call

from .base import DelegateCall, SubAgent
from .loop import append_tool_turns, tool_step
from .system_prompt import TOOL_PROTOCOL, format_capabilities

AgentProviderFactory = Callable[[SubAgent], ChatProvider]

DELEGATE_PATTERN = re.compile(r"<delegate>(.*?)</delegate>", re.DOTALL)


def parse_delegate(content: str, known_agents: Iterable[str] = ()) -> DelegateCall | None:
    """Find a delegate intent in assistant content.

    Recognises three shapes (in order):
      1. Native ``<delegate>{"agent":..,"instruction":..}</delegate>`` tag.
      2. JSON tool call with tool name ``delegate``: ``<tool_call>{"tool":"delegate",
         "arguments":{"agent":..,"instruction":..}}</tool_call>``.
      3. JSON tool call where the tool name itself is a known sub-agent name (e.g.
         owl-alpha emits ``<tool_call>{"tool":"resume_tailor","arguments":{...}}``);
         the entire ``arguments`` object becomes the instruction payload.

    Shapes 2 and 3 cover model dialects that ignore the ``<delegate>`` protocol
    and route everything through the tool-call channel.
    """
    match = DELEGATE_PATTERN.search(content)
    if match:
        call = _delegate_from_json(match.group(1).strip())
        if call is not None:
            return call

    request = parse_tool_call(content)
    if request is None:
        return None

    if request.tool == "delegate":
        agent = request.arguments.get("agent")
        instruction = request.arguments.get("instruction")
        if isinstance(agent, str) and isinstance(instruction, str):
            return DelegateCall(agent=agent, instruction=instruction)

    if request.tool in set(known_agents):
        instruction = request.arguments.get("instruction")
        if isinstance(instruction, str) and instruction.strip():
            return DelegateCall(agent=request.tool, instruction=instruction)
        return DelegateCall(
            agent=request.tool,
            instruction=json.dumps(request.arguments, ensure_ascii=False, indent=2),
        )

    return None


def _delegate_from_json(blob: str) -> DelegateCall | None:
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError:
        return None
    agent = payload.get("agent")
    instruction = payload.get("instruction")
    if not isinstance(agent, str) or not isinstance(instruction, str):
        return None
    return DelegateCall(agent=agent, instruction=instruction)


def subagent_system_prompt(agent: SubAgent) -> str:
    base = agent.system_prompt.strip()
    if not agent.tool_names:
        return base
    caps: list[CapabilitySpec] = MANIFEST.capabilities_for_tools(agent.tool_names)
    if not caps:
        return base
    return "\n\n".join([base, format_capabilities(caps), TOOL_PROTOCOL])


async def run_subagent(
    chat_provider: ChatProvider,
    agent: SubAgent,
    instruction: str,
    tools_config: ToolConfig,
    max_response_tokens: int,
    *,
    session_id: str,
    hooks: HookRegistry,
) -> ChatResult:
    system_prompt = subagent_system_prompt(agent)
    turns: list[Turn] = [Turn("user", instruction)]

    has_tools = bool(agent.tool_names) and tools_config.enabled
    if not has_tools:
        pre = await hooks.emit(
            "model.pre_call",
            {
                "system_prompt": system_prompt,
                "turns": turns,
                "session_id": session_id,
                "agent_name": agent.name,
                "provider": chat_provider.provider,
                "model": chat_provider.model,
            },
        )
        result = await chat_provider.complete(
            pre["turns"], max_response_tokens, system_prompt=pre["system_prompt"]
        )
        await hooks.emit(
            "model.post_call",
            {
                "result": result,
                "session_id": session_id,
                "agent_name": agent.name,
                "provider": chat_provider.provider,
                "model": chat_provider.model,
            },
        )
        return result

    max_iterations = tools_config.max_iterations
    for attempt in range(max_iterations + 1):
        step = await tool_step(
            chat_provider,
            system_prompt,
            turns,
            max_response_tokens,
            session_id=session_id,
            tools_config=tools_config,
            hooks=hooks,
            allowed_names=agent.tool_names,
            agent_name=agent.name,
        )

        if step.tool_request is None:
            return step.chat_result

        if attempt >= max_iterations:
            return ChatResult(
                content=f"Sub-agent '{agent.name}' hit the tool-iteration limit.",
                provider=step.chat_result.provider,
                model=step.chat_result.model,
            )

        append_tool_turns(turns, step)

    return ChatResult(
        content=f"Sub-agent '{agent.name}' hit the tool-iteration limit.",
        provider=chat_provider.provider,
        model=chat_provider.model,
    )
