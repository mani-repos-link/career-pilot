import unittest

from pyapi.agents.prompts import assistant_system_prompt
from pyapi.providers import EmptyModelResponseError
from pyapi.providers.compatible import build_messages, extract_message_content


class ProviderParsingTest(unittest.TestCase):
    def test_extract_message_content_handles_null_content(self) -> None:
        self.assertEqual(extract_message_content({"message": {"content": None}}), "")

    def test_extract_message_content_handles_text_parts(self) -> None:
        content = extract_message_content(
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "text", "text": "world"},
                    ]
                }
            }
        )

        self.assertEqual(content, "hello\nworld")

    def test_extract_message_content_uses_refusal_text(self) -> None:
        content = extract_message_content({"message": {"content": None, "refusal": "I cannot help with that."}})

        self.assertEqual(content, "I cannot help with that.")

    def test_empty_model_response_error_message_is_stable(self) -> None:
        self.assertEqual(str(EmptyModelResponseError("openrouter")), "openrouter returned an empty message")

    def test_tool_prompt_names_role_and_available_tools(self) -> None:
        messages = build_messages([], assistant_system_prompt(True, True))
        prompt = messages[0]["content"]

        self.assertIn("Career Pilot", prompt)
        self.assertIn("<tool_call>", prompt)
        for tool in ("ls", "grep", "read_file", "sqlite_query", "explain_context", "fetch_url", "read_llms_txt"):
            self.assertIn(tool, prompt)
        self.assertIn("local_inspect", prompt)
        self.assertIn("data_inspect", prompt)
        self.assertIn("web_surf", prompt)

    def test_prompt_omits_internet_caps_when_disabled(self) -> None:
        prompt = assistant_system_prompt(True, False)
        self.assertIn("local_inspect", prompt)
        self.assertNotIn("web_surf", prompt)
        self.assertNotIn("fetch_url", prompt)

    def test_prompt_omits_tool_protocol_when_tools_off(self) -> None:
        prompt = assistant_system_prompt(False, False)
        self.assertNotIn("<tool_call>", prompt)
        self.assertNotIn("Capabilities enabled", prompt)


if __name__ == "__main__":
    unittest.main()
