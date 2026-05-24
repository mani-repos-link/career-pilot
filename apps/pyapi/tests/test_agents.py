import unittest

from pyapi.agents import (
    CATALOG,
    DelegateCall,
    parse_delegate,
)


class CatalogTest(unittest.TestCase):
    def test_catalog_has_four_agents(self) -> None:
        self.assertEqual(set(CATALOG), {"resume_tailor", "job_scout", "applier", "tracker"})

    def test_each_agent_has_system_prompt(self) -> None:
        for agent in CATALOG.values():
            self.assertTrue(agent.system_prompt.strip())
            self.assertTrue(agent.description.strip())


class ParseDelegateTest(unittest.TestCase):
    def test_parse_valid_delegate(self) -> None:
        content = (
            'I will route this.\n'
            '<delegate>{"agent":"resume_tailor","instruction":"Tailor for SRE role"}</delegate>'
        )
        call = parse_delegate(content)
        self.assertEqual(call, DelegateCall(agent="resume_tailor", instruction="Tailor for SRE role"))

    def test_parse_returns_none_without_tag(self) -> None:
        self.assertIsNone(parse_delegate("Please paste the JD first."))

    def test_parse_returns_none_with_invalid_json(self) -> None:
        self.assertIsNone(parse_delegate("<delegate>not-json</delegate>"))

    def test_parse_returns_none_with_missing_fields(self) -> None:
        self.assertIsNone(parse_delegate('<delegate>{"agent":"resume_tailor"}</delegate>'))

    def test_parse_recognises_tool_call_with_tool_delegate(self) -> None:
        content = (
            '<tool_call>{"tool":"delegate","arguments":'
            '{"agent":"resume_tailor","instruction":"Tailor for SRE role"}}</tool_call>'
        )
        call = parse_delegate(content, known_agents=CATALOG.keys())
        self.assertEqual(call, DelegateCall(agent="resume_tailor", instruction="Tailor for SRE role"))

    def test_parse_recognises_sub_agent_name_as_tool_with_instruction(self) -> None:
        content = (
            '<tool_call>{"tool":"resume_tailor","arguments":'
            '{"instruction":"Tailor for SRE role"}}</tool_call>'
        )
        call = parse_delegate(content, known_agents=CATALOG.keys())
        self.assertEqual(call, DelegateCall(agent="resume_tailor", instruction="Tailor for SRE role"))

    def test_parse_recognises_sub_agent_with_freeform_arguments(self) -> None:
        content = (
            '<tool_call>{"tool":"resume_tailor","arguments":'
            '{"company":"Rocken","role":"Software Engineer"}}</tool_call>'
        )
        call = parse_delegate(content, known_agents=CATALOG.keys())
        self.assertIsNotNone(call)
        assert call is not None
        self.assertEqual(call.agent, "resume_tailor")
        self.assertIn("Rocken", call.instruction)

    def test_parse_ignores_tool_call_for_unknown_agent(self) -> None:
        content = '<tool_call>{"tool":"web_search","arguments":{"q":"x"}}</tool_call>'
        self.assertIsNone(parse_delegate(content, known_agents=CATALOG.keys()))


if __name__ == "__main__":
    unittest.main()
