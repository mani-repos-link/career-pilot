from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from pyapi.schemas import CreateMessageRequest
from pyapi.store import NotFoundError

from pyapi.dependencies import AppServices
from pyapi.services import answer_user_message, regenerate_assistant_response

logger = logging.getLogger("pyapi.routes.messages")


def create_messages_router(services: AppServices) -> APIRouter:
    router = APIRouter()
    store = services.store

    @router.get("/api/sessions/{session_id}/messages")
    async def list_messages(
        session_id: str,
        limit: int = Query(default=15, ge=1, le=100),
        before: str | None = None,
    ) -> dict[str, object]:
        try:
            messages, has_more = store.list_messages_page(session_id, limit=limit, before=before)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail="session not found") from err
        return {
            "messages": [message.to_api() for message in messages],
            "page": {
                "hasMore": has_more,
                "nextBefore": messages[0].created_at.isoformat().replace("+00:00", "Z") if has_more and messages else None,
            },
        }

    @router.post("/api/sessions/{session_id}/messages", status_code=201)
    async def create_message(
        session_id: str,
        request: CreateMessageRequest,
    ) -> dict[str, object]:
        started = time.monotonic()
        logger.info(
            "message create start session_id=%s role=%s content_chars=%d",
            session_id,
            request.role,
            len(request.content),
        )

        try:
            user_message = store.create_message(session_id, request.role, request.content)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail="session not found") from err
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

        messages = [user_message]
        if request.role == "user":
            try:
                result = await answer_user_message(
                    services,
                    session_id,
                    user_message,
                    update_title=True,
                )
            except Exception as err:
                logger.exception("message create chat_error session_id=%s", session_id)
                raise HTTPException(status_code=502, detail=str(err)) from err
            messages.append(result.assistant_message)

        logger.info(
            "message create done session_id=%s returned_messages=%d duration=%.3fs",
            session_id,
            len(messages),
            time.monotonic() - started,
        )
        return {"message": user_message.to_api(), "messages": [message.to_api() for message in messages]}

    @router.post("/api/sessions/{session_id}/messages/{message_id}/activate")
    async def activate_message(session_id: str, message_id: str) -> dict[str, dict[str, str | None]]:
        try:
            message = store.set_active_response(session_id, message_id)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail="message not found") from err
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        return {"message": message.to_api()}

    @router.post("/api/sessions/{session_id}/messages/{message_id}/regenerate", status_code=201)
    async def regenerate_message(
        session_id: str,
        message_id: str,
    ) -> dict[str, object]:
        started = time.monotonic()
        try:
            result = await regenerate_assistant_response(services, session_id, message_id)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        except Exception as err:
            logger.exception("message regenerate chat_error session_id=%s message_id=%s", session_id, message_id)
            raise HTTPException(status_code=502, detail=str(err)) from err

        logger.info(
            "message regenerate done session_id=%s message_id=%s duration=%.3fs",
            session_id,
            message_id,
            time.monotonic() - started,
        )
        return {"message": result.assistant_message.to_api()}

    return router
