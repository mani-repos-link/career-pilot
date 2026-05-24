from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from pyapi.agents import SubAgent
from pyapi.config import ChatConfig, ContextConfig, ToolConfig
from pyapi.hooks import HookRegistry
from pyapi.providers import ChatResult, Turn
from pyapi.services.dispatch import dispatch_delegate


def chat_config() -> ChatConfig:
    return ChatConfig(
        provider="fake",
        model="fake-model",
        openrouter_api_key="",
        openrouter_base_url="",
        huggingface_api_key="",
        huggingface_base_url="",
        http_referer="",
        app_title="",
    )


def context_config() -> ContextConfig:
    return ContextConfig(max_response_tokens=100, max_history_messages=30, max_memory_chars=2000)


def tool_config(root: Path) -> ToolConfig:
    return ToolConfig(
        enabled=False,
        database_url="sqlite://",
        workspace_root=root,
        max_iterations=3,
        max_output_chars=12000,
        internet_enabled=False,
        network_timeout_seconds=10,
        max_network_bytes=300000,
        crawl_max_pages=5,
    )


class ScriptedProvider:
    provider = "fake"
    model = "fake-model"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[list[Turn], str | None]] = []

    async def complete(
        self,
        history: list[Turn],
        max_response_tokens: int,
        system_prompt: str | None = None,
    ) -> ChatResult:
        self.calls.append((list(history), system_prompt))
        content = self._responses.pop(0) if self._responses else ""
        return ChatResult(content=content, provider=self.provider, model=self.model)


def make_services(provider: ScriptedProvider, catalog: dict[str, SubAgent], hooks: HookRegistry, directory: Path) -> SimpleNamespace:
    return SimpleNamespace(
        chat_provider=provider,
        chat_config=chat_config(),
        context=context_config(),
        tools=tool_config(directory),
        catalog=catalog,
        hooks=hooks,
    )


class DispatchDelegateTest(unittest.TestCase):
    def test_unknown_agent_returns_error_chat_result(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider(["unused"])
                services = make_services(provider, {}, HookRegistry(), Path(directory))
                result = await dispatch_delegate(
                    services,
                    '<delegate>{"agent":"ghost","instruction":"hi"}</delegate>',
                    "session_1",
                )
                assert result is not None
                self.assertIn("Unknown sub-agent", result.content)

        asyncio.run(run())

    def test_no_delegate_tag_returns_none(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider([])
                services = make_services(provider, {}, HookRegistry(), Path(directory))
                result = await dispatch_delegate(services, "just a normal answer", "session_1")
                self.assertIsNone(result)

        asyncio.run(run())

    def test_sub_agent_llm_failure_falls_back_to_chat_model(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                class FailingProvider:
                    provider = "openrouter"
                    model = "bogus/model:free"

                    async def complete(self, *_a, **_k):
                        raise ValueError("openrouter error 402: Out of credits")

                main_provider = ScriptedProvider(["letter from fallback"])
                catalog = {
                    "resume_tailor": SubAgent(
                        name="resume_tailor",
                        description="d",
                        system_prompt="p",
                        provider_override="openrouter",
                        model_override="bogus/model:free",
                    )
                }
                services = make_services(main_provider, catalog, HookRegistry(), Path(directory))

                with mock.patch(
                    "pyapi.services.dispatch.provider_for_agent",
                    return_value=FailingProvider(),
                ):
                    result = await dispatch_delegate(
                        services,
                        '<delegate>{"agent":"resume_tailor","instruction":"cover letter for Acme"}</delegate>',
                        "session_1",
                    )

                assert result is not None
                self.assertEqual(result.content, "letter from fallback")
                self.assertEqual(len(main_provider.calls), 1)

        asyncio.run(run())

    def test_sub_agent_failure_without_override_propagates(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                class FailingMain:
                    provider = "openrouter"
                    model = "fake-model"

                    async def complete(self, *_a, **_k):
                        raise ValueError("openrouter error 429: rate limited")

                catalog = {"resume_tailor": SubAgent(name="resume_tailor", description="d", system_prompt="p")}
                services = make_services(FailingMain(), catalog, HookRegistry(), Path(directory))

                with self.assertRaises(ValueError):
                    await dispatch_delegate(
                        services,
                        '<delegate>{"agent":"resume_tailor","instruction":"x"}</delegate>',
                        "session_1",
                    )

        asyncio.run(run())

    def test_delegate_pre_hook_can_rewrite_instruction(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider(["tailored"])
                hooks = HookRegistry()

                @hooks.on("delegate.pre")
                def prepend_profile(payload: dict) -> None:
                    payload["instruction"] = f"<profile>YAML</profile>\n\n{payload['instruction']}"

                catalog = {"resume_tailor": SubAgent(name="resume_tailor", description="d", system_prompt="p")}
                services = make_services(provider, catalog, hooks, Path(directory))
                result = await dispatch_delegate(
                    services,
                    '<delegate>{"agent":"resume_tailor","instruction":"tailor for SRE"}</delegate>',
                    "session_1",
                )
                assert result is not None
                self.assertEqual(result.content, "tailored")
                # Sub-agent received the rewritten instruction in its first user turn.
                first_turn = provider.calls[0][0][0]
                self.assertIn("<profile>YAML</profile>", first_turn.content)
                self.assertTrue(first_turn.content.endswith("tailor for SRE"))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
