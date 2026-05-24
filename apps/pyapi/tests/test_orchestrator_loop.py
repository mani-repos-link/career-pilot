from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyapi.agents import SubAgent, run_subagent
from pyapi.config import ChatConfig, ContextConfig, ToolConfig
from pyapi.hooks import HookRegistry
from pyapi.providers import ChatResult, Turn


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
        enabled=True,
        database_url="sqlite://",
        workspace_root=root,
        max_iterations=3,
        max_output_chars=12000,
        internet_enabled=False,
        network_timeout_seconds=10,
        max_network_bytes=300000,
        crawl_max_pages=5,
    )


def turn(role: str, content: str) -> Turn:
    return Turn(role=role, content=content)


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


class RunSubagentTest(unittest.TestCase):
    def test_empty_tool_names_returns_single_completion(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider(["tailored resume content"])
                agent = SubAgent(name="resume_tailor", description="", system_prompt="prompt")
                result = await run_subagent(
                    provider, agent, "instruction", tool_config(Path(directory)), 100,
                    session_id="session_1",
                    hooks=HookRegistry(),
                )
                self.assertEqual(result.content, "tailored resume content")
                self.assertEqual(len(provider.calls), 1)
                self.assertEqual(provider.calls[0][1], "prompt")

        asyncio.run(run())

    def test_allowed_tool_runs_then_returns_final(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "notes.txt").write_text("hello")
                provider = ScriptedProvider(
                    [
                        '<tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>',
                        "Found notes.txt.",
                    ]
                )
                agent = SubAgent(
                    name="job_scout",
                    description="",
                    system_prompt="scout prompt",
                    tool_names=("ls",),
                )
                result = await run_subagent(
                    provider, agent, "list files", tool_config(root), 100,
                    session_id="session_1",
                    hooks=HookRegistry(),
                )
                self.assertEqual(result.content, "Found notes.txt.")
                self.assertEqual(len(provider.calls), 2)
                self.assertIn("Tool result (ls, ok)", provider.calls[1][0][-1].content)

        asyncio.run(run())

    def test_tool_outside_allowlist_returns_allowlist_error(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider(
                    [
                        '<tool_call>{"tool":"grep","arguments":{"query":"x"}}</tool_call>',
                        "Sorry, I cannot use grep.",
                    ]
                )
                agent = SubAgent(
                    name="job_scout",
                    description="",
                    system_prompt="scout prompt",
                    tool_names=("ls",),
                )
                result = await run_subagent(
                    provider, agent, "search", tool_config(Path(directory)), 100,
                    session_id="session_1",
                    hooks=HookRegistry(),
                )
                self.assertEqual(result.content, "Sorry, I cannot use grep.")
                last_tool_msg = provider.calls[1][0][-1].content
                self.assertIn("allowlist", last_tool_msg)
                self.assertIn("grep", last_tool_msg)

        asyncio.run(run())

    def test_iteration_limit_returns_bounded_error(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "a.txt").write_text("x")
                payload = '<tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>'
                provider = ScriptedProvider([payload] * 10)
                config = tool_config(root)
                agent = SubAgent(
                    name="job_scout",
                    description="",
                    system_prompt="scout prompt",
                    tool_names=("ls",),
                )
                result = await run_subagent(
                    provider, agent, "list files", config, 100,
                    session_id="session_1",
                    hooks=HookRegistry(),
                )
                self.assertIn("tool-iteration limit", result.content)
                self.assertEqual(len(provider.calls), config.max_iterations + 1)

        asyncio.run(run())

    def test_model_pre_call_hook_can_append_to_system_prompt(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                provider = ScriptedProvider(["ok"])
                hooks = HookRegistry()

                @hooks.on("model.pre_call")
                def add_memory(payload: dict) -> None:
                    payload["system_prompt"] = f"{payload['system_prompt']}\n\nMemories: hello"

                agent = SubAgent(name="resume_tailor", description="", system_prompt="base")
                await run_subagent(
                    provider, agent, "do it", tool_config(Path(directory)), 100,
                    session_id="session_1",
                    hooks=hooks,
                )
                self.assertIn("Memories: hello", provider.calls[0][1] or "")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
