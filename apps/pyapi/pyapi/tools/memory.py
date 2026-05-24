"""Agent-callable memory tools.

Handler signature matches the rest of HANDLERS in registry.py: (ToolConfig, args, session_id).
A MemoryStore is constructed per call from the shared engine — same pattern as data.py's
run_explain_context. Cheap, avoids passing the store through HANDLERS' static dict.
"""

from __future__ import annotations

import json
from typing import Any

from pyapi.config import ToolConfig
from pyapi.memory import MemoryStore, SCOPE_GLOBAL, SCOPE_SESSION, VALID_SCOPES, format_memory_block

from .args import string_arg


def run_remember(config: ToolConfig, arguments: dict[str, Any], current_session_id: str | None = None) -> str:
    key = string_arg(arguments, "key", "").strip()
    content = string_arg(arguments, "content", "").strip()
    scope = string_arg(arguments, "scope", SCOPE_SESSION).strip() or SCOPE_SESSION
    if not key:
        raise ValueError("key is required")
    if not content:
        raise ValueError("content is required")
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope must be one of {sorted(VALID_SCOPES)}; got {scope!r}")

    session_id = _session_id_for_scope(scope, current_session_id)
    store = MemoryStore(config.database_url)
    record = store.upsert(scope, session_id, key, content)
    return json.dumps(
        {"ok": True, "scope": record.scope, "key": record.key, "id": record.id},
        indent=2,
    )


def run_forget(config: ToolConfig, arguments: dict[str, Any], current_session_id: str | None = None) -> str:
    key = string_arg(arguments, "key", "").strip()
    scope = string_arg(arguments, "scope", SCOPE_SESSION).strip() or SCOPE_SESSION
    if not key:
        raise ValueError("key is required")
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope must be one of {sorted(VALID_SCOPES)}; got {scope!r}")

    session_id = _session_id_for_scope(scope, current_session_id)
    store = MemoryStore(config.database_url)
    removed = store.delete(scope, session_id, key)
    return json.dumps({"ok": True, "removed": removed, "scope": scope, "key": key}, indent=2)


def run_recall(config: ToolConfig, arguments: dict[str, Any], current_session_id: str | None = None) -> str:
    if not current_session_id:
        raise ValueError("recall needs a session_id; called outside a conversation")
    store = MemoryStore(config.database_url)
    memories = store.list(current_session_id, include_global=True)
    if not memories:
        return "(no memories)"
    # Reuse the same formatter the injector uses, unbounded here (the LLM asked).
    return format_memory_block(memories, max_chars=0)


def _session_id_for_scope(scope: str, current_session_id: str | None) -> str | None:
    if scope == SCOPE_SESSION:
        if not current_session_id:
            raise ValueError("session scope needs a session_id; called outside a conversation")
        return current_session_id
    if scope == SCOPE_GLOBAL:
        return None
    raise ValueError(f"unsupported scope {scope!r}")
