"""Search a job portal using cookie-authenticated Playwright.

LinkedIn and Indeed both gate their search behind login; this tool reads cookies
from ``data/cookies.yml`` (see ``inputs/cookies.py``), launches a headless Chromium
with a matching user agent, navigates the search URL, and pulls a list of jobs.

The DOM extraction is portal-specific and brittle — selectors change. Each portal
has its own ``_search_<portal>`` function that returns ``list[dict]``. When a portal
changes its layout, fix that one function; the rest of the tool is generic.

Output JSON shape:
    {
      "portal":  "linkedin",
      "query":   "full stack engineer",
      "location":"Zurich",
      "count":   12,
      "jobs":    [
        {"external_id":"...","title":"...","company":"...","location":"...","url":"...","posted":"..."}
      ],
      "warnings": ["..."]
    }

Playwright is loaded lazily so the rest of the project still imports when the
browsers aren't installed yet (run ``playwright install chromium`` once).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any

from pyapi.config import ToolConfig
from pyapi.inputs.cookies import PortalCookies, load_cookies

from .args import string_arg

logger = logging.getLogger("pyapi.tools.job_search")

DEFAULT_MAX_RESULTS = 20


async def run_search_jobs(
    config: ToolConfig,
    arguments: dict[str, Any],
    current_session_id: str | None = None,
) -> str:
    query = string_arg(arguments, "query", "").strip()
    location = string_arg(arguments, "location", "").strip()
    portal = string_arg(arguments, "portal", "linkedin").strip().lower()
    max_results = int(arguments.get("max_results") or DEFAULT_MAX_RESULTS)

    if not query:
        raise ValueError("query is required")

    cookies = load_cookies().get(portal)
    if cookies is None:
        raise ValueError(
            f"no cookies configured for portal '{portal}' in data/cookies.yml — "
            "add an entry under 'portals:' before searching."
        )

    handler = _PORTAL_HANDLERS.get(portal)
    if handler is None:
        raise ValueError(f"portal '{portal}' not supported. Known: {', '.join(sorted(_PORTAL_HANDLERS)) or 'none'}")

    jobs, warnings = await handler(query, location, max_results, cookies)
    return json.dumps(
        {
            "portal": portal,
            "query": query,
            "location": location,
            "count": len(jobs),
            "jobs": jobs[:max_results],
            "warnings": warnings,
        },
        indent=2,
        ensure_ascii=False,
    )


async def _search_linkedin(
    query: str,
    location: str,
    max_results: int,
    cookies: PortalCookies,
) -> tuple[list[dict[str, Any]], list[str]]:
    params: dict[str, str] = {"keywords": query}
    if location:
        params["location"] = location
    search_url = f"{cookies.base_url}/jobs/search/?{urllib.parse.urlencode(params)}"

    warnings: list[str] = []
    jobs: list[dict[str, Any]] = []

    async with _browser_session(cookies) as page:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector("ul.jobs-search__results-list li, ul.scaffold-layout__list li", timeout=10000)
        except Exception as err:
            warnings.append(f"results list selector did not appear: {err}")

        # Scroll to load more cards (LinkedIn lazy-loads).
        for _ in range(5):
            await page.mouse.wheel(0, 1800)
            await page.wait_for_timeout(700)
            cards = await page.query_selector_all("ul.jobs-search__results-list li, ul.scaffold-layout__list li")
            if len(cards) >= max_results:
                break

        cards = await page.query_selector_all("ul.jobs-search__results-list li, ul.scaffold-layout__list li")
        for card in cards[:max_results]:
            try:
                title_el = await card.query_selector("a.job-card-list__title, h3.base-search-card__title, a.job-card-container__link")
                company_el = await card.query_selector("h4.base-search-card__subtitle, span.job-card-container__company-name, a.hidden-nested-link")
                location_el = await card.query_selector("span.job-search-card__location, ul.job-card-container__metadata-wrapper li")
                link_el = title_el if title_el else await card.query_selector("a")

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                loc = (await location_el.inner_text()).strip() if location_el else None
                href = await link_el.get_attribute("href") if link_el else None
                external_id = _extract_li_job_id(href) if href else None

                if title and href:
                    jobs.append({
                        "external_id": external_id,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "url": _absolute(href, cookies.base_url),
                        "posted": None,
                    })
            except Exception as err:
                warnings.append(f"card parse failed: {err}")

    if not jobs:
        warnings.append("0 jobs extracted — LinkedIn may have changed selectors or the cookie is expired.")
    return jobs, warnings


async def _search_indeed(
    query: str,
    location: str,
    max_results: int,
    cookies: PortalCookies,
) -> tuple[list[dict[str, Any]], list[str]]:
    params = {"q": query}
    if location:
        params["l"] = location
    search_url = f"{cookies.base_url}/jobs?{urllib.parse.urlencode(params)}"

    warnings: list[str] = []
    jobs: list[dict[str, Any]] = []

    async with _browser_session(cookies) as page:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector("div.job_seen_beacon, a[data-jk]", timeout=10000)
        except Exception as err:
            warnings.append(f"Indeed results selector did not appear: {err}")

        cards = await page.query_selector_all("div.job_seen_beacon, a[data-jk]")
        for card in cards[:max_results]:
            try:
                jk = await card.get_attribute("data-jk")
                title_el = await card.query_selector("h2.jobTitle span, h2.jobTitle a")
                company_el = await card.query_selector("span[data-testid='company-name'], span.companyName")
                loc_el = await card.query_selector("div[data-testid='text-location'], div.companyLocation")
                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                loc = (await loc_el.inner_text()).strip() if loc_el else None
                href = f"{cookies.base_url}/viewjob?jk={jk}" if jk else None
                if title and href:
                    jobs.append({
                        "external_id": jk,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "url": href,
                        "posted": None,
                    })
            except Exception as err:
                warnings.append(f"card parse failed: {err}")

    if not jobs:
        warnings.append("0 jobs extracted — Indeed may have changed selectors or the cookie is expired.")
    return jobs, warnings


def _extract_li_job_id(href: str) -> str | None:
    import re
    m = re.search(r"/jobs/view/(\d+)", href or "")
    return m.group(1) if m else None


def _absolute(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return f"{base.rstrip('/')}/{href}"


class _browser_session:
    """Async ctx manager that yields a Playwright page with cookies applied."""

    def __init__(self, cookies: PortalCookies) -> None:
        self._cookies = cookies
        self._pw = None
        self._browser = None
        self._context = None

    async def __aenter__(self):
        try:
            from playwright.async_api import async_playwright
        except Exception as err:
            raise RuntimeError(
                f"playwright not installed ({err}). Run `uv pip install playwright && playwright install chromium`."
            )
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(user_agent=self._cookies.user_agent or None)
        if self._cookies.cookies:
            await self._context.add_cookies(self._cookies.to_playwright())
        return await self._context.new_page()

    async def __aexit__(self, *_exc):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()


_PORTAL_HANDLERS = {
    "linkedin": _search_linkedin,
    "indeed":   _search_indeed,
}
