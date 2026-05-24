from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pyapi.config import find_data_dir

COOKIES_PATH = find_data_dir() / "cookies.yml"


@dataclass(frozen=True)
class CookieEntry:
    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    httpOnly: bool = False


@dataclass(frozen=True)
class PortalCookies:
    portal: str
    base_url: str
    user_agent: str
    last_refreshed: str
    cookies: tuple[CookieEntry, ...] = field(default_factory=tuple)

    def to_playwright(self) -> list[dict]:
        """Shape consumable by Playwright's context.add_cookies()."""
        return [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": c.secure,
                "httpOnly": c.httpOnly,
            }
            for c in self.cookies
        ]


def load_cookies(path: Path = COOKIES_PATH) -> dict[str, PortalCookies]:
    """Load all portal cookies keyed by portal name. Empty dict if file missing."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    portals_raw = data.get("portals") or {}
    result: dict[str, PortalCookies] = {}
    for name, entry in portals_raw.items():
        cookies = tuple(
            CookieEntry(
                name=c["name"],
                value=c["value"],
                domain=c["domain"],
                path=c.get("path", "/"),
                secure=bool(c.get("secure", False)),
                httpOnly=bool(c.get("httpOnly", False)),
            )
            for c in entry.get("cookies") or ()
        )
        result[name] = PortalCookies(
            portal=name,
            base_url=entry.get("base_url", ""),
            user_agent=entry.get("user_agent", ""),
            last_refreshed=str(entry.get("last_refreshed", "")),
            cookies=cookies,
        )
    return result
