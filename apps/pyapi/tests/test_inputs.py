from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pyapi.inputs.cookies import load_cookies
from pyapi.inputs.job_search import load_job_search
from pyapi.inputs.profile import load_profile, load_profile_yaml


class ProfileLoaderTest(unittest.TestCase):
    def test_load_profile_yaml_returns_raw_text(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.yml"
            path.write_text("candidate:\n  full_name: Test\n")
            self.assertIn("Test", load_profile_yaml(path))

    def test_load_profile_parses_yaml(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.yml"
            path.write_text("candidate:\n  full_name: Test\n  title: Engineer\n")
            profile = load_profile(path)
            self.assertEqual(profile["candidate"]["full_name"], "Test")

    def test_load_profile_rejects_missing_candidate_key(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.yml"
            path.write_text("other: value\n")
            with self.assertRaises(ValueError):
                load_profile(path)

    def test_load_profile_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_profile_yaml(Path("/nonexistent/path/profile.yml"))


class CookiesLoaderTest(unittest.TestCase):
    def test_load_cookies_returns_empty_when_missing(self) -> None:
        self.assertEqual(load_cookies(Path("/nonexistent/cookies.yml")), {})

    def test_load_cookies_parses_portals(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.yml"
            path.write_text(
                """
portals:
  linkedin:
    base_url: https://www.linkedin.com
    user_agent: "ua"
    last_refreshed: 2026-05-22
    cookies:
      - name: li_at
        value: secret
        domain: .linkedin.com
        path: /
        secure: true
        httpOnly: true
"""
            )
            cookies = load_cookies(path)
            self.assertIn("linkedin", cookies)
            linkedin = cookies["linkedin"]
            self.assertEqual(linkedin.user_agent, "ua")
            self.assertEqual(len(linkedin.cookies), 1)
            self.assertEqual(linkedin.cookies[0].name, "li_at")
            playwright_shape = linkedin.to_playwright()
            self.assertEqual(playwright_shape[0]["name"], "li_at")
            self.assertTrue(playwright_shape[0]["secure"])


class JobSearchLoaderTest(unittest.TestCase):
    def test_load_job_search_parses_roles_and_portals(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "job-search-portals.yml"
            path.write_text(
                """
roles:
  positive:
    - Full Stack Engineer
  negative:
    - Data Scientist
search_queries:
  - "site:linkedin.com Senior Engineer"
portals:
  linkedin:
    enabled: true
    base_url: https://www.linkedin.com
    path: /jobs/search
    search_query: '"Senior Engineer"'
    user_agent: ua
    last_refreshed: 2026-05-22
    add_cookie_for_search_if_exists: true
    description: LinkedIn jobs
    how_to: steps
  disabled_portal:
    enabled: false
    base_url: https://example.com
    path: /
    search_query: ""
    user_agent: ""
    last_refreshed: ""
    add_cookie_for_search_if_exists: false
    description: ""
    how_to: ""
"""
            )
            config = load_job_search(path)
            self.assertEqual(config.positive_roles, ("Full Stack Engineer",))
            self.assertEqual(config.negative_roles, ("Data Scientist",))
            self.assertEqual(len(config.search_queries), 1)
            self.assertIn("linkedin", config.portals)
            self.assertTrue(config.portals["linkedin"].add_cookie_for_search_if_exists)
            self.assertEqual([p.name for p in config.enabled_portals()], ["linkedin"])

    def test_load_job_search_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_job_search(Path("/nonexistent/job-search-portals.yml"))


if __name__ == "__main__":
    unittest.main()
