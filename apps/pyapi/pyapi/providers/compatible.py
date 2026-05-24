from __future__ import annotations

import logging
import time

import httpx

from .turn import Turn
from .types import ChatResult, EmptyModelResponseError

logger = logging.getLogger("pyapi.provider")


class OpenAICompatibleProvider:
    def __init__(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        http_referer: str,
        app_title: str,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http_referer = http_referer
        self.app_title = app_title

    async def complete(
        self,
        history: list[Turn],
        max_response_tokens: int,
        system_prompt: str | None = None,
    ) -> ChatResult:
        if not self.api_key:
            raise ValueError(f"{self.provider} API key is required")
        if not self.model:
            raise ValueError(f"{self.provider} chat model is required")

        endpoint = f"{self.base_url}/chat/completions"
        messages = build_messages(history, system_prompt)
        body = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_response_tokens,
            "temperature": 0.7,
            "stream": False,
        }

        start = time.monotonic()
        logger.info(
            "%s request endpoint=%s model=%s messages=%d",
            self.provider,
            endpoint,
            self.model,
            len(messages),
        )

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": self.http_referer,
                    "X-Title": self.app_title,
                },
                json=body,
            )

        logger.info(
            "%s response status=%d duration=%.3fs bytes=%d",
            self.provider,
            response.status_code,
            time.monotonic() - start,
            len(response.content),
        )

        payload = response.json()
        if response.status_code < 200 or response.status_code >= 300:
            message = payload.get("error", {}).get("message") or response.reason_phrase
            logger.warning(
                "%s error status=%d message=%s body=%s",
                self.provider,
                response.status_code,
                message,
                response.text,
            )
            raise ValueError(f"{self.provider} error {response.status_code}: {message}")

        choices = payload.get("choices") or []
        if not choices:
            logger.warning(
                "%s returned no choices payload_keys=%s body=%s",
                self.provider,
                sorted(payload.keys()),
                response.text,
            )
            raise EmptyModelResponseError(self.provider)

        content = extract_message_content(choices[0])
        if not content:
            logger.warning("%s returned empty content payload=%s", self.provider, choices[0])
            raise EmptyModelResponseError(self.provider)

        return ChatResult(
            content=content,
            provider=self.provider,
            model=payload.get("model") or self.model,
        )


def build_messages(history: list[Turn], system_prompt: str | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for turn in history:
        if turn.role in {"user", "assistant", "system"}:
            messages.append({"role": turn.role, "content": turn.content})
    return messages


def extract_message_content(choice: dict[str, object]) -> str:
    message = choice.get("message")
    if not isinstance(message, dict):
        return ""

    raw_content = message.get("content")
    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()

    refusal = message.get("refusal")
    if isinstance(refusal, str):
        return refusal.strip()

    return ""
