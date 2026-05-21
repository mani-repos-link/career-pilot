from __future__ import annotations

from pyapi.agents import parse_delegate, provider_for_agent, run_subagent
from pyapi.dependencies import AppServices
from pyapi.providers import ChatResult


async def dispatch_delegate(services: AppServices, content: str) -> ChatResult | None:
    """If content carries a <delegate> tag, run that sub-agent and return its result. Else None."""
    call = parse_delegate(content)
    if call is None:
        return None

    agent = services.catalog.get(call.agent)
    if agent is None:
        return ChatResult(
            content=f"Unknown sub-agent '{call.agent}'. Available: {', '.join(services.catalog) or 'none'}.",
            provider=services.chat_provider.provider,
            model=services.chat_provider.model,
        )

    provider = provider_for_agent(agent, services.chat_provider, services.chat_config)
    return await run_subagent(
        provider,
        agent,
        call.instruction,
        services.context.max_response_tokens,
    )
