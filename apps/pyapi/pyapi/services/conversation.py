from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pyapi.context import build_llm_context
from pyapi.dependencies import AppServices
from pyapi.agents.prompts import assistant_system_prompt
from pyapi.providers import MODEL_EMPTY_RESPONSE_MESSAGE, ChatResult, EmptyModelResponseError
from pyapi.store import MessageRecord, NotFoundError
from pyapi.tools import execute_tool_call, format_tool_result, parse_tool_call

from .dispatch import dispatch_delegate

from .titles import title_session_from_first_prompt


@dataclass(frozen=True)
class AssistantResponseResult:
    user_message: MessageRecord
    assistant_message: MessageRecord


async def answer_user_message(
    services: AppServices,
    session_id: str,
    user_message: MessageRecord,
    *,
    update_title: bool,
) -> AssistantResponseResult:
    store = services.store
    if update_title:
        title_session_from_first_prompt(store, session_id, user_message.content)

    context_messages = store.list_context_messages(session_id, through_user_message_id=user_message.id)
    return await create_assistant_response(services, session_id, user_message, context_messages)


async def regenerate_assistant_response(
    services: AppServices,
    session_id: str,
    message_id: str,
) -> AssistantResponseResult:
    history = services.store.list_messages(session_id)
    anchor_user = find_regeneration_anchor(history, message_id)
    context_messages = services.store.list_context_messages(session_id, through_user_message_id=anchor_user.id)
    return await create_assistant_response(services, session_id, anchor_user, context_messages)


async def create_assistant_response(
    services: AppServices,
    session_id: str,
    user_message: MessageRecord,
    context_messages: list[MessageRecord],
) -> AssistantResponseResult:
    store = services.store
    history = build_llm_context(context_messages, services.context)
    result = await complete_with_fallback(services, history)
    assistant_message = store.create_message(
        session_id,
        "assistant",
        result.content,
        provider=result.provider,
        model=result.model,
        parent_message_id=user_message.id,
        make_active=True,
    )
    return AssistantResponseResult(
        user_message=user_message,
        assistant_message=assistant_message,
    )


async def complete_with_fallback(
    services: AppServices,
    history: list[MessageRecord],
) -> ChatResult:
    try:
        return await complete_with_tools(services, history)
    except EmptyModelResponseError:
        return ChatResult(
            content=MODEL_EMPTY_RESPONSE_MESSAGE,
            provider=services.chat_provider.provider,
            model=services.chat_provider.model,
        )


async def complete_with_tools(
    services: AppServices,
    history: list[MessageRecord],
) -> ChatResult:
    system_prompt = assistant_system_prompt(
        services.tools.enabled,
        services.tools.internet_enabled,
        catalog=services.catalog,
    )
    tool_history = list(history)

    for attempt in range(services.tools.max_iterations + 1):
        result = await services.chat_provider.complete(
            tool_history,
            services.context.max_response_tokens,
            system_prompt=system_prompt,
        )

        delegated = await dispatch_delegate(services, result.content)
        if delegated is not None:
            return delegated

        tool_request = parse_tool_call(result.content) if services.tools.enabled else None
        if tool_request is None:
            return result

        if attempt >= services.tools.max_iterations:
            return ChatResult(
                content="I could not finish the request because the tool loop reached its configured limit.",
                provider=result.provider,
                model=result.model,
            )

        tool_result = execute_tool_call(services.tools, tool_request, current_session_id=current_session_id(tool_history))
        tool_history.append(synthetic_message("assistant", result.content))
        tool_history.append(synthetic_message("system", format_tool_result(tool_result)))

    return ChatResult(
        content="I could not finish the request because the tool loop reached its configured limit.",
        provider=services.chat_provider.provider,
        model=services.chat_provider.model,
    )


def synthetic_message(role: str, content: str) -> MessageRecord:
    return MessageRecord(
        id=f"tool_{role}",
        session_id="tool_loop",
        role=role,
        content=content,
        provider=None,
        model=None,
        parent_message_id=None,
        active_response_id=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def current_session_id(history: list[MessageRecord]) -> str | None:
    for message in reversed(history):
        if message.session_id:
            return message.session_id
    return None


def find_regeneration_anchor(history: list[MessageRecord], message_id: str) -> MessageRecord:
    target_index = next((index for index, message in enumerate(history) if message.id == message_id), None)
    if target_index is None:
        raise NotFoundError("message not found")

    target = history[target_index]
    if target.role == "user":
        return target
    if target.role != "assistant":
        raise ValueError("only user or assistant messages can be regenerated")

    parent_id = target.parent_message_id
    if parent_id:
        anchor = next((message for message in history if message.id == parent_id), None)
        if anchor is not None:
            return anchor

    anchor = next(
        (message for message in reversed(history[:target_index]) if message.role == "user"),
        None,
    )
    if anchor is None:
        raise ValueError("no user message to regenerate from")
    return anchor
