from __future__ import annotations

from .dialects import REGISTRY, select_dialect
from .types import ToolRequest


def parse_tool_call(content: str, *, model: str | None = None) -> ToolRequest | None:
    """Parse a tool call from assistant content.

    If ``model`` is provided, the matching dialect parses first. If that misses (or
    no model is given), every registered dialect is tried so models that drift
    into another family's syntax still parse. The first non-None result wins.
    """
    primary = select_dialect(model)
    request = primary.parse(content)
    if request is not None:
        return request
    for dialect in REGISTRY:
        if dialect is primary:
            continue
        request = dialect.parse(content)
        if request is not None:
            return request
    return None
