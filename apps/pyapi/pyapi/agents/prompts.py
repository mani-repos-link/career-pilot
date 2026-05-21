from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base import SubAgent


BASE_ASSISTANT_PROMPT = (
    "You are Career Pilot — a job-hunt assistant. You search roles, parse job "
    "descriptions, tailor resumes per JD, auto-apply, and track applications.\n"
    "Stay concrete. Answer with the minimum needed to act. Ask for missing inputs "
    "instead of inventing them. Use only facts from the conversation or tool results."
)


@dataclass(frozen=True)
class Capability:
    name: str
    purpose: str
    tools: tuple[str, ...]


LOCAL_INSPECT = Capability(
    name="local_inspect",
    purpose="Read-only inspection of the workspace: list, search, read files, find symbols.",
    tools=("ls", "grep", "read_file", "project_tree", "find_symbol"),
)

DATA_INSPECT = Capability(
    name="data_inspect",
    purpose="Read-only inspection of app state: SELECT against the local DB and explain raw turn context.",
    tools=("sqlite_query", "explain_context"),
)

WEB_SURF = Capability(
    name="web_surf",
    purpose="Read live public web pages and search results. Real fetch, not pretraining. Public HTTP(S) only.",
    tools=("fetch_url", "web_search", "read_llms_txt", "crawl_site"),
)


TOOL_PROTOCOL = (
    "Tool protocol:\n"
    "- When a tool is needed, reply with ONLY one <tool_call> tag. No prose, no markdown.\n"
    '- Shape: <tool_call>{"tool":"<name>","arguments":{...}}</tool_call>\n'
    "- One call per reply. After the result returns, answer the user using the findings.\n"
    "- If a tool errors, read the error, fix the arguments, retry once, then explain to the user."
)


DELEGATE_PROTOCOL = (
    "Delegate protocol:\n"
    "- For job-hunt specialist work, delegate to ONE sub-agent below. Reply with ONLY this tag:\n"
    '  <delegate>{"agent":"<name>","instruction":"<self-contained paragraph>"}</delegate>\n'
    "- The sub-agent will not see prior turns, so the instruction must include every detail it needs.\n"
    "- If required inputs are missing (e.g. no JD for resume_tailor), ASK the user — do not delegate.\n"
    "- Do not chain delegate and tool_call in the same reply. Pick one."
)


def assistant_system_prompt(
    tools_enabled: bool,
    internet_tools_enabled: bool = False,
    catalog: dict[str, SubAgent] | None = None,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    sections = [f"{BASE_ASSISTANT_PROMPT}\nToday is {today}."]

    if tools_enabled:
        caps = [LOCAL_INSPECT, DATA_INSPECT]
        if internet_tools_enabled:
            caps.append(WEB_SURF)
        sections.append(format_capabilities(caps))
        sections.append(TOOL_PROTOCOL)

    if catalog:
        sections.append(format_subagents(catalog))
        sections.append(DELEGATE_PROTOCOL)

    return "\n\n".join(sections).strip()


def format_capabilities(caps: list[Capability]) -> str:
    lines = ["Capabilities enabled:"]
    for cap in caps:
        lines.append(f"- {cap.name}: {cap.purpose}")
        lines.append(f"  tools: {', '.join(cap.tools)}")
    return "\n".join(lines)


def format_subagents(catalog: dict[str, SubAgent]) -> str:
    lines = ["Sub-agents available:"]
    for agent in catalog.values():
        lines.append(f"- {agent.name}: {agent.description}")
    return "\n".join(lines)
