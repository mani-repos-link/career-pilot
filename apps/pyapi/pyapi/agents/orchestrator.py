from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable

from pyapi.providers import ChatProvider, ChatResult
from pyapi.store import MessageRecord

from .base import DelegateCall, SubAgent

AgentProviderFactory = Callable[[SubAgent], ChatProvider]

MAX_DELEGATIONS = 3
DELEGATE_PATTERN = re.compile(r"<delegate>(.*?)</delegate>", re.DOTALL)


def orchestrator_system_prompt(catalog: dict[str, SubAgent]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    roster = "\n".join(f"- {agent.name}: {agent.description}" for agent in catalog.values())
    return (
        f"You are the Career Pilot orchestrator. Today is {today}.\n"
        "\n"
        "You route each user turn to ONE sub-agent or, when the request is purely conversational "
        "(greeting, clarification, summary of what you can do), you answer directly.\n"
        "\n"
        "Sub-agents available:\n"
        f"{roster}\n"
        "\n"
        "To delegate, reply with ONLY this tag (no prose around it):\n"
        '<delegate>{"agent":"<name>","instruction":"<one paragraph in plain English>"}</delegate>\n'
        "\n"
        "Rules:\n"
        "- Pick the single best-fit agent. Do not chain agents in one reply.\n"
        "- The instruction must be self-contained — the sub-agent will not see prior turns.\n"
        "- If required inputs are missing (e.g., no JD for resume_tailor), ASK the user for them "
        "  instead of delegating. Do not invent inputs.\n"
        "- If no sub-agent fits, answer the user directly with a short message."
    )


def parse_delegate(content: str) -> DelegateCall | None:
    match = DELEGATE_PATTERN.search(content)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
    agent = payload.get("agent")
    instruction = payload.get("instruction")
    if not isinstance(agent, str) or not isinstance(instruction, str):
        return None
    return DelegateCall(agent=agent, instruction=instruction)


async def run_subagent(
    chat_provider: ChatProvider,
    agent: SubAgent,
    instruction: str,
    max_response_tokens: int,
) -> ChatResult:
    user_message = MessageRecord(
        id="orchestrator_delegate",
        session_id="orchestrator",
        role="user",
        content=instruction,
        provider=None,
        model=None,
        parent_message_id=None,
        active_response_id=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return await chat_provider.complete(
        [user_message],
        max_response_tokens,
        system_prompt=agent.system_prompt,
    )


async def run_orchestrator(
    chat_provider: ChatProvider,
    catalog: dict[str, SubAgent],
    history: list[MessageRecord],
    max_response_tokens: int,
    agent_provider_factory: AgentProviderFactory | None = None,
) -> ChatResult:
    system_prompt = orchestrator_system_prompt(catalog)
    working = list(history)
    pick_provider = agent_provider_factory or (lambda _agent: chat_provider)

    for _ in range(MAX_DELEGATIONS):
        decision = await chat_provider.complete(
            working,
            max_response_tokens,
            system_prompt=system_prompt,
        )
        call = parse_delegate(decision.content)
        if call is None:
            return decision

        agent = catalog.get(call.agent)
        if agent is None:
            return ChatResult(
                content=f"Orchestrator picked unknown agent '{call.agent}'. Available: {', '.join(catalog)}.",
                provider=decision.provider,
                model=decision.model,
            )

        sub_result = await run_subagent(pick_provider(agent), agent, call.instruction, max_response_tokens)
        working.append(orchestrator_note(f"agent={agent.name} returned:\n{sub_result.content}"))
        return sub_result

    return ChatResult(
        content="Orchestrator reached its delegation limit without a final answer.",
        provider=chat_provider.provider,
        model=chat_provider.model,
    )


def orchestrator_note(content: str) -> MessageRecord:
    return MessageRecord(
        id="orchestrator_note",
        session_id="orchestrator",
        role="system",
        content=content,
        provider=None,
        model=None,
        parent_message_id=None,
        active_response_id=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
