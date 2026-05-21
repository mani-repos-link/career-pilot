from __future__ import annotations

from pyapi.store import Store


def title_session_from_first_prompt(store: Store, session_id: str, content: str) -> None:
    session = store.get_session(session_id)
    if session.title != "New chat":
        return

    title = title_from_prompt(content)
    if title:
        store.update_session_title(session_id, title)


def title_from_prompt(content: str, max_length: int = 64) -> str:
    title = " ".join(content.split())
    if len(title) <= max_length:
        return title
    return f"{title[: max_length - 1].rstrip()}..."
