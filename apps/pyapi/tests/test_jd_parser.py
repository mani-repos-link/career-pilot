from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyapi.config import ToolConfig
from pyapi.tools.jd_parser import run_parse_jd


def tool_config(root: Path) -> ToolConfig:
    return ToolConfig(
        enabled=True,
        database_url="sqlite://",
        workspace_root=root,
        max_iterations=3,
        max_output_chars=12000,
        internet_enabled=True,
        network_timeout_seconds=10,
        max_network_bytes=300000,
        crawl_max_pages=5,
    )


SAMPLE = """\
Senior Full Stack Engineer

Legartis is hiring at Zurich. Salary: CHF 110,000 - 140,000.

You will work with Angular, TypeScript, Python, Kubernetes, Docker, and Postgres.
Fluent in English; German nice to have.
"""


class ParseJdTest(unittest.TestCase):
    def test_parses_title_location_salary_skills(self) -> None:
        with TemporaryDirectory() as directory:
            config = tool_config(Path(directory))
            payload = json.loads(run_parse_jd(config, {"text": SAMPLE}))

            self.assertIn("Full Stack Engineer", payload["title"])
            self.assertEqual(payload["location"], "Zurich")
            self.assertEqual(payload["salary"]["currency"], "CHF")
            self.assertEqual(payload["salary"]["min"], 110000.0)
            self.assertEqual(payload["salary"]["max"], 140000.0)
            for skill in ("angular", "typescript", "python", "kubernetes", "docker", "postgres"):
                self.assertIn(skill, payload["skills"])
            for lang in ("english", "german"):
                self.assertIn(lang, payload["languages"])
            self.assertIn("Legartis", payload["text"])

    def test_requires_url_or_text(self) -> None:
        with TemporaryDirectory() as directory:
            config = tool_config(Path(directory))
            with self.assertRaises(ValueError):
                run_parse_jd(config, {})


if __name__ == "__main__":
    unittest.main()
