from __future__ import annotations

import logging
from dataclasses import dataclass

from pyapi.context import build_llm_context
from pyapi.dependencies import AppServices
from pyapi.agents.loop import append_tool_turns, tool_step
from pyapi.agents.system_prompt import assistant_system_prompt
from pyapi.providers import MODEL_EMPTY_RESPONSE_MESSAGE, ChatResult, EmptyModelResponseError, Turn
from pyapi.store import MessageRecord, NotFoundError

from .dispatch import dispatch_delegate

from .titles import title_session_from_first_prompt

logger = logging.getLogger("pyapi.services.conversation")


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
    messages = build_llm_context(context_messages, services.context)
    turns = [message.to_turn() for message in messages]
    result = await complete_with_fallback(services, turns, session_id)
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
    history: list[Turn],
    session_id: str,
) -> ChatResult:
    try:
        return await complete_with_tools(services, history, session_id)
    except EmptyModelResponseError:
        return ChatResult(
            content=MODEL_EMPTY_RESPONSE_MESSAGE,
            provider=services.chat_provider.provider,
            model=services.chat_provider.model,
        )


async def complete_with_tools(
    services: AppServices,
    history: list[Turn],
    session_id: str,
) -> ChatResult:
    services.lifecycle.turn_start(session_id, agent="main")
    logger.info(
        "turn.start session_id=%s history_turns=%d max_iterations=%d",
        session_id, len(history), services.tools.max_iterations,
    )
    system_prompt = assistant_system_prompt(
        services.tools.enabled,
        services.tools.internet_enabled,
        catalog=services.catalog,
    )
    turns = list(history)
    max_iterations = services.tools.max_iterations

    try:
        for attempt in range(max_iterations + 1):
            logger.info("turn.iteration session_id=%s attempt=%d/%d", session_id, attempt + 1, max_iterations + 1)
            step = await tool_step(
                services.chat_provider,
                system_prompt,
                turns,
                services.context.max_response_tokens,
                session_id=session_id,
                tools_config=services.tools,
                hooks=services.hooks,
            )

            delegated = await dispatch_delegate(services, step.chat_result.content, session_id)
            if delegated is not None:
                services.lifecycle.turn_end(session_id, reason="delegated")
                return delegated

            if step.tool_request is None:
                services.lifecycle.turn_end(session_id, reason="final_answer")
                return step.chat_result

            if attempt >= max_iterations:
                services.lifecycle.turn_end(session_id, reason="tool_loop_limit")
                return ChatResult(
                    content="I could not finish the request because the tool loop reached its configured limit.",
                    provider=step.chat_result.provider,
                    model=step.chat_result.model,
                )

            append_tool_turns(turns, step)

        services.lifecycle.turn_end(session_id, reason="tool_loop_limit_fallthrough")
        return ChatResult(
            content="I could not finish the request because the tool loop reached its configured limit.",
            provider=services.chat_provider.provider,
            model=services.chat_provider.model,
        )
    except Exception:
        services.lifecycle.turn_end(session_id, reason="exception")
        raise


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
