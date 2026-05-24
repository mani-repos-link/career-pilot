from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pyapi.config import find_data_dir

JOB_SEARCH_PATH = find_data_dir() / "job-search-portals.yml"


@dataclass(frozen=True)
class PortalConfig:
    name: str
    enabled: bool
    base_url: str
    path: str
    search_query: str
    user_agent: str
    last_refreshed: str
    add_cookie_for_search_if_exists: bool
    description: str
    how_to: str


@dataclass(frozen=True)
class JobSearchConfig:
    positive_roles: tuple[str, ...] = field(default_factory=tuple)
    negative_roles: tuple[str, ...] = field(default_factory=tuple)
    search_queries: tuple[str, ...] = field(default_factory=tuple)
    portals: dict[str, PortalConfig] = field(default_factory=dict)

    def enabled_portals(self) -> list[PortalConfig]:
        return [p for p in self.portals.values() if p.enabled]


def load_job_search(path: Path = JOB_SEARCH_PATH) -> JobSearchConfig:
    if not path.exists():
        raise FileNotFoundError(
            f"job search config not found at {path}. Copy data/job-search-portals.example.yml and edit."
        )
    data = yaml.safe_load(path.read_text()) or {}
    roles = data.get("roles") or {}
    portals_raw = data.get("portals") or {}
    portals = {
        name: PortalConfig(
            name=name,
            enabled=bool(entry.get("enabled", True)),
            base_url=entry.get("base_url", ""),
            path=entry.get("path", ""),
            search_query=entry.get("search_query", ""),
            user_agent=entry.get("user_agent", ""),
            last_refreshed=str(entry.get("last_refreshed", "")),
            add_cookie_for_search_if_exists=bool(entry.get("add_cookie_for_search_if_exists", False)),
            description=(entry.get("description") or "").strip(),
            how_to=(entry.get("how_to") or "").strip(),
        )
        for name, entry in portals_raw.items()
    }
    return JobSearchConfig(
        positive_roles=tuple(roles.get("positive") or ()),
        negative_roles=tuple(roles.get("negative") or ()),
        search_queries=tuple(data.get("search_queries") or ()),
        portals=portals,
    )
