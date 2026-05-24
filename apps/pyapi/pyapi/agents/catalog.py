from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from pyapi.config import AgentLLM, find_config_dir

from .base import SubAgent

CONFIG_DIR = find_config_dir()
AGENTS_YML = CONFIG_DIR / "agents.yml"


def load_catalog(yml_path: Path = AGENTS_YML) -> dict[str, SubAgent]:
    data = yaml.safe_load(yml_path.read_text())
    catalog: dict[str, SubAgent] = {}
    for entry in data.get("agents", []):
        name = entry["name"]
        prompt_path = yml_path.parent / entry["prompt"]
        catalog[name] = SubAgent(
            name=name,
            description=" ".join(entry["description"].split()),
            system_prompt=prompt_path.read_text().strip(),
            tool_names=tuple(entry.get("tools") or ()),
        )
    return catalog


CATALOG: dict[str, SubAgent] = load_catalog()
RESUME_TAILOR = CATALOG["resume_tailor"]
JOB_SCOUT = CATALOG["job_scout"]
APPLIER = CATALOG["applier"]
TRACKER = CATALOG["tracker"]


def build_catalog(agent_llms: dict[str, AgentLLM]) -> dict[str, SubAgent]:
    resolved: dict[str, SubAgent] = {}
    for name, agent in CATALOG.items():
        llm = agent_llms.get(name)
        if llm is None:
            resolved[name] = agent
            continue
        resolved[name] = replace(agent, provider_override=llm.provider, model_override=llm.model)
    return resolved
