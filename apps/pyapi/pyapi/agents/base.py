from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubAgent:
    name: str
    description: str
    system_prompt: str
    tool_names: tuple[str, ...] = ()
    provider_override: str | None = None
    model_override: str | None = None


@dataclass(frozen=True)
class AgentResult:
    agent: str
    content: str
    provider: str
    model: str


@dataclass(frozen=True)
class DelegateCall:
    agent: str
    instruction: str
