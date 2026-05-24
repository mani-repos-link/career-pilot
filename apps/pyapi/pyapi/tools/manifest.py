from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import yaml

from pyapi.config import find_config_dir

MANIFEST_PATH = find_config_dir() / "tools.yml"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str
    description: str


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    purpose: str
    requires_internet: bool
    tools: tuple[ToolSpec, ...]


@dataclass(frozen=True)
class ToolManifest:
    capabilities: dict[str, CapabilitySpec]
    tools: dict[str, ToolSpec]

    def capabilities_for_tools(self, allowed_names: Iterable[str]) -> list[CapabilitySpec]:
        allowed = set(allowed_names)
        scoped: list[CapabilitySpec] = []
        for cap in self.capabilities.values():
            tools = tuple(spec for spec in cap.tools if spec.name in allowed)
            if tools:
                scoped.append(replace(cap, tools=tools))
        return scoped


def load_manifest(path: Path = MANIFEST_PATH) -> ToolManifest:
    data = yaml.safe_load(path.read_text())
    tools_by_name: dict[str, ToolSpec] = {}
    by_capability: dict[str, list[ToolSpec]] = {}
    for entry in data.get("tools", []):
        spec = ToolSpec(name=entry["name"], capability=entry["capability"], description=entry["description"])
        tools_by_name[spec.name] = spec
        by_capability.setdefault(spec.capability, []).append(spec)

    capabilities: dict[str, CapabilitySpec] = {}
    for name, cap in (data.get("capabilities") or {}).items():
        capabilities[name] = CapabilitySpec(
            name=name,
            purpose=" ".join(cap["purpose"].split()),
            requires_internet=bool(cap.get("requires_internet", False)),
            tools=tuple(by_capability.get(name, ())),
        )
    return ToolManifest(capabilities=capabilities, tools=tools_by_name)


MANIFEST: ToolManifest = load_manifest()
