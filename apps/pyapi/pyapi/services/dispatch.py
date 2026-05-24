from __future__ import annotations

import logging

from pyapi.agents import (
    parse_delegate,
    provider_for_agent,
    run_subagent,
)
from pyapi.dependencies import AppServices
from pyapi.providers import ChatProvider, ChatResult, EmptyModelResponseError

logger = logging.getLogger("pyapi.dispatch")


async def dispatch_delegate(services: AppServices, content: str, session_id: str) -> ChatResult | None:
    """If content carries a <delegate> tag, run that sub-agent and return its result. Else None.

    Falls back to the main ``CHAT_MODEL`` provider when the agent's own LLM raises a
    provider error (4xx/5xx) or returns an empty response. The fallback runs once. If
    it also fails, the exception bubbles to the route (502). Fallback is skipped when
    the agent had no override (its provider IS the main one).
    """
    call = parse_delegate(content, known_agents=services.catalog.keys())
    if call is None:
        return None

    agent = services.catalog.get(call.agent)
    if agent is None:
        return ChatResult(
            content=f"Unknown sub-agent '{call.agent}'. Available: {', '.join(services.catalog) or 'none'}.",
            provider=services.chat_provider.provider,
            model=services.chat_provider.model,
        )

    pre = await services.hooks.emit(
        "delegate.pre",
        {"agent": agent, "instruction": call.instruction, "session_id": session_id},
    )
    provider = provider_for_agent(agent, services.chat_provider, services.chat_config)
    logger.info(
        "dispatch.delegate session_id=%s agent=%s provider=%s model=%s",
        session_id, agent.name, provider.provider, provider.model,
    )

    try:
        result = await _run_with_provider(services, agent, pre["instruction"], provider, session_id)
    except (ValueError, EmptyModelResponseError) as err:
        fallback = services.chat_provider
        if fallback is provider or (
            fallback.provider == provider.provider and fallback.model == provider.model
        ):
            raise
        logger.warning(
            "dispatch.delegate primary failed session_id=%s agent=%s primary=%s/%s error=%s — falling back to %s/%s",
            session_id, agent.name, provider.provider, provider.model, err,
            fallback.provider, fallback.model,
        )
        result = await _run_with_provider(services, agent, pre["instruction"], fallback, session_id)
        logger.info(
            "dispatch.delegate fallback ok session_id=%s agent=%s fallback=%s/%s",
            session_id, agent.name, fallback.provider, fallback.model,
        )

    await services.hooks.emit(
        "delegate.post",
        {"agent": agent, "result": result, "session_id": session_id},
    )
    return result


async def _run_with_provider(
    services: AppServices,
    agent,
    instruction: str,
    provider: ChatProvider,
    session_id: str,
) -> ChatResult:
    return await run_subagent(
        provider,
        agent,
        instruction,
        services.tools,
        services.context.max_response_tokens,
        session_id=session_id,
        hooks=services.hooks,
    )
