from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolRequest:
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionResult:
    tool: str
    ok: bool
    output: str
