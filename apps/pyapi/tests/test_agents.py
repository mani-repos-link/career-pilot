import unittest

from pyapi.agents import (
    CATALOG,
    DelegateCall,
    orchestrator_system_prompt,
    parse_delegate,
)


class CatalogTest(unittest.TestCase):
    def test_catalog_has_four_agents(self) -> None:
        self.assertEqual(set(CATALOG), {"resume_tailor", "job_scout", "applier", "tracker"})

    def test_each_agent_has_system_prompt(self) -> None:
        for agent in CATALOG.values():
            self.assertTrue(agent.system_prompt.strip())
            self.assertTrue(agent.description.strip())


class OrchestratorPromptTest(unittest.TestCase):
    def test_prompt_lists_every_agent(self) -> None:
        prompt = orchestrator_system_prompt(CATALOG)
        for name in CATALOG:
            self.assertIn(name, prompt)

    def test_prompt_shows_delegate_tag(self) -> None:
        prompt = orchestrator_system_prompt(CATALOG)
        self.assertIn("<delegate>", prompt)


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


if __name__ == "__main__":
    unittest.main()
