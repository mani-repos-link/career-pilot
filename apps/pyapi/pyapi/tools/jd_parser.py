"""Parse a job description into structured fields.

Accepts a URL (fetched via httpx) or raw text. Pulls the visible JD text out of the
HTML and extracts a small set of high-signal fields by regex/heuristics. Heavy NLP
is intentionally avoided — the sub-agent's own LLM does interpretation; this tool
just gives it clean, structured raw material.

Output JSON shape:
    {
      "source_url": "<url or null>",
      "title":      "<str or null>",
      "company":    "<str or null>",
      "location":   "<str or null>",
      "salary":     {"min": <num|null>, "max": <num|null>, "currency": "<str|null>", "raw": "<str|null>"},
      "skills":     ["..."],
      "languages":  ["..."],
      "text":       "<cleaned JD text>"
    }
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from pyapi.config import ToolConfig

from .args import string_arg

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SALARY_RE = re.compile(
    r"(?P<currency>CHF|EUR|USD|GBP|€|\$|£)\s*"
    r"(?P<min>[\d'.,\s]+)"
    r"\s*(?:[-–—to]+\s*(?P<max>[\d'.,\s]+))?",
    re.IGNORECASE,
)

KNOWN_SKILLS: tuple[str, ...] = (
    "python", "typescript", "javascript", "java", "kotlin", "go", "golang", "rust", "c#", "c++", "php", "ruby",
    "angular", "react", "vue", "svelte", "next.js", "nuxt", "astro", "tailwind",
    "node.js", "django", "fastapi", "spring", "rails", "laravel",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "aws", "gcp", "azure",
    "ci/cd", "github actions", "jenkins", "argo", "prometheus", "grafana",
    "graphql", "rest", "websockets", "grpc",
    "ai", "ml", "llm", "rag", "openai", "anthropic", "tensorflow", "pytorch",
    "clean code", "clean architecture", "ddd", "tdd", "scrum", "agile",
)

KNOWN_LANGUAGES: tuple[str, ...] = (
    "english", "german", "french", "italian", "spanish", "portuguese", "dutch", "polish",
    "deutsch", "französisch", "italienisch", "spanisch", "englisch",
)


def run_parse_jd(
    config: ToolConfig,
    arguments: dict[str, Any],
    current_session_id: str | None = None,
) -> str:
    url = string_arg(arguments, "url", "").strip()
    text = string_arg(arguments, "text", "").strip()
    if not url and not text:
        raise ValueError("provide either 'url' or 'text'")

    if url:
        text = _fetch_jd(url, config.network_timeout_seconds, config.max_network_bytes)

    cleaned = _clean_text(text)
    payload = {
        "source_url": url or None,
        "title":      _guess_title(cleaned),
        "company":    _guess_company(cleaned),
        "location":   _guess_location(cleaned),
        "salary":     _guess_salary(cleaned),
        "skills":     _scan(cleaned, KNOWN_SKILLS),
        "languages":  _scan(cleaned, KNOWN_LANGUAGES),
        "text":       cleaned[:8000],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _fetch_jd(url: str, timeout: float, max_bytes: int) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        body = response.text[:max_bytes]
    return _html_to_text(body)


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _guess_title(text: str) -> str | None:
    for line in text.splitlines()[:30]:
        stripped = line.strip()
        if 4 <= len(stripped) <= 120 and re.search(r"engineer|developer|architect|scientist|designer|manager|lead|director", stripped, re.IGNORECASE):
            return stripped
    return None


def _guess_company(text: str) -> str | None:
    match = re.search(r"(?:at|bei|for)\s+([A-Z][A-Za-z0-9&.\- ]{2,40})", text)
    if match:
        return match.group(1).strip(" .,")
    return None


def _guess_location(text: str) -> str | None:
    match = re.search(r"\b(Zurich|Zürich|Bern|Geneva|Basel|Lausanne|Berlin|Munich|Hamburg|London|Paris|Milan|Bolzano|Bozen|Vienna|Amsterdam|Madrid|Lisbon|Remote|Hybrid)\b", text, re.IGNORECASE)
    return match.group(1) if match else None


def _guess_salary(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"min": None, "max": None, "currency": None, "raw": None}
    match = SALARY_RE.search(text)
    if not match:
        return out
    out["raw"] = match.group(0).strip()
    out["currency"] = _normalize_currency(match.group("currency"))
    out["min"] = _parse_number(match.group("min"))
    if match.group("max"):
        out["max"] = _parse_number(match.group("max"))
    return out


def _normalize_currency(token: str) -> str:
    token = token.strip()
    return {"€": "EUR", "$": "USD", "£": "GBP"}.get(token, token.upper())


def _parse_number(token: str) -> float | None:
    """Parse 110,000 / 110'000 / 110.000 / 110 000 / 110.5 → float.

    Treats commas, apostrophes, and whitespace as thousand-separators. Dots are
    thousand-separators when followed by exactly three digits at end-of-token,
    otherwise decimal points. Trailing punctuation is stripped.
    """
    raw = token.strip().strip(".,;:! ")
    raw = raw.replace("'", "").replace(",", "").replace(" ", "")
    # If a single dot remains and is followed by exactly 3 digits, treat as thousand-sep.
    if raw.count(".") == 1:
        head, tail = raw.split(".")
        if len(tail) == 3 and tail.isdigit():
            raw = head + tail
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _scan(text: str, vocab: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for term in vocab:
        if term in lowered and term not in hits:
            hits.append(term)
    return hits
