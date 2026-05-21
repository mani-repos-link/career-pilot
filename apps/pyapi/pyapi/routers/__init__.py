from __future__ import annotations

from fastapi import APIRouter

from pyapi.agents import SubAgent
from pyapi.config import ChatConfig, ContextConfig, ToolConfig
from pyapi.providers import ChatProvider
from pyapi.store import Store

from pyapi.dependencies import AppServices

from .messages import create_messages_router
from .sessions import create_sessions_router


def create_router(
    store: Store,
    chat_provider: ChatProvider,
    chat_config: ChatConfig,
    context: ContextConfig,
    tools: ToolConfig,
    catalog: dict[str, SubAgent],
) -> APIRouter:
    services = AppServices(
        store=store,
        chat_provider=chat_provider,
        chat_config=chat_config,
        context=context,
        tools=tools,
        catalog=catalog,
    )
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/providers")
    async def providers() -> dict[str, object]:
        return {
            "chat": ["openrouter", "huggingface"],
            "active": {
                "chat": {"provider": chat_provider.provider, "model": chat_provider.model},
                "tools": {
                    "enabled": tools.enabled,
                    "internetEnabled": tools.internet_enabled,
                    "capabilities": {
                        "localProjectInspection": tools.enabled,
                        "publicWebSurfing": tools.enabled and tools.internet_enabled,
                    },
                },
            },
        }

    router.include_router(create_sessions_router(services))
    router.include_router(create_messages_router(services))
    return router


__all__ = ["create_router"]
