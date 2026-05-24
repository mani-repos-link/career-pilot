from __future__ import annotations

import unittest

from pyapi.tools import parse_tool_call, select_dialect


class SelectDialectTest(unittest.TestCase):
    def test_owl_alpha_picks_longcat_dialect(self) -> None:
        self.assertEqual(select_dialect("openrouter/owl-alpha").name, "longcat")
        self.assertEqual(select_dialect("openrouter/owl-alpha:free").name, "longcat")

    def test_llama_model_picks_llama_dialect(self) -> None:
        self.assertEqual(select_dialect("meta-llama/llama-3.3-70b-instruct:free").name, "llama")

    def test_gemma_model_picks_gemma_dialect(self) -> None:
        self.assertEqual(select_dialect("google/gemma-4-31b-it:free").name, "gemma")

    def test_qwen_model_picks_qwen_dialect(self) -> None:
        self.assertEqual(select_dialect("qwen/qwen3-coder:free").name, "qwen")

    def test_unknown_model_falls_back_to_default(self) -> None:
        self.assertEqual(select_dialect("does-not-exist/foo").name, "json")
        self.assertEqual(select_dialect(None).name, "json")


class ParseToolCallTest(unittest.TestCase):
    def test_llama_function_tag_parses(self) -> None:
        request = parse_tool_call(
            '<function=fetch_url>{"url":"https://example.com"}</function>',
            model="meta-llama/llama-3.3-70b-instruct:free",
        )
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://example.com")

    def test_llama_python_tag_parses(self) -> None:
        request = parse_tool_call(
            '<|python_tag|>{"tool":"ls","arguments":{"path":"."}}',
            model="meta-llama/llama-3.3-70b-instruct:free",
        )
        assert request is not None
        self.assertEqual(request.tool, "ls")
        self.assertEqual(request.arguments["path"], ".")

    def test_gemma_tool_code_block_parses(self) -> None:
        request = parse_tool_call(
            'Sure.\n```tool_code\n{"tool":"ls","arguments":{"path":"."}}\n```',
            model="google/gemma-4-31b-it:free",
        )
        assert request is not None
        self.assertEqual(request.tool, "ls")

    def test_longcat_dialect_still_parses_owl_alpha(self) -> None:
        request = parse_tool_call(
            "<longcat_tool_call>fetch_url\n"
            "<longcat_arg_key>url</longcat_arg_key>\n"
            "<longcat_arg_value>https://x.test</longcat_arg_value>\n"
            "</longcat_tool_call>",
            model="openrouter/owl-alpha:free",
        )
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://x.test")

    def test_plain_prose_returns_none_for_every_dialect(self) -> None:
        self.assertIsNone(parse_tool_call("Just a regular sentence.", model="qwen/qwen3-coder:free"))
        self.assertIsNone(parse_tool_call("Just a regular sentence.", model="google/gemma-4-31b-it:free"))

    def test_qwen_uses_standard_tool_call_tag(self) -> None:
        request = parse_tool_call(
            '<tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>',
            model="qwen/qwen3-coder:free",
        )
        assert request is not None
        self.assertEqual(request.tool, "ls")


if __name__ == "__main__":
    unittest.main()
