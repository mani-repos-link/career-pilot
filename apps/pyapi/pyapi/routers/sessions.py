from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from pyapi.schemas import CreateSessionRequest, UpdateSessionRequest
from pyapi.store import NotFoundError

from pyapi.dependencies import AppServices

logger = logging.getLogger("pyapi.routes.sessions")


def create_sessions_router(services: AppServices) -> APIRouter:
    router = APIRouter()
    store = services.store

    @router.get("/api/sessions")
    async def list_sessions() -> dict[str, list[dict[str, str]]]:
        return {"sessions": [session.to_api() for session in store.list_sessions()]}

    @router.post("/api/sessions", status_code=201)
    async def create_session(request: CreateSessionRequest) -> dict[str, dict[str, str]]:
        return {"session": store.create_session(request.title).to_api()}

    @router.patch("/api/sessions/{session_id}")
    async def update_session(session_id: str, request: UpdateSessionRequest) -> dict[str, dict[str, str]]:
        try:
            session = store.update_session_title(session_id, request.title)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail="session not found") from err
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        return {"session": session.to_api()}

    @router.delete("/api/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str) -> Response:
        try:
            store.delete_session(session_id)
        except NotFoundError as err:
            raise HTTPException(status_code=404, detail="session not found") from err
        logger.info("session deleted session_id=%s", session_id)
        return Response(status_code=204)

    return router
