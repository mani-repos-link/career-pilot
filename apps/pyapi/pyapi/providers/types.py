from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .turn import Turn


@dataclass(frozen=True)
class ChatResult:
    content: str
    provider: str
    model: str


MODEL_EMPTY_RESPONSE_MESSAGE = (
    "I'm sorry, I couldn't generate a useful response for that request. "
    "Please rephrase it or add a little more context."
)


class EmptyModelResponseError(ValueError):
    def __init__(self, provider: str):
        super().__init__(f"{provider} returned an empty message")
        self.provider = provider


class ChatProvider(Protocol):
    provider: str
    model: str

    async def complete(
        self,
        history: list[Turn],
        max_response_tokens: int,
        system_prompt: str | None = None,
    ) -> ChatResult: ...
