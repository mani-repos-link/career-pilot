from __future__ import annotations

from datetime import datetime

from pyapi.tools.manifest import MANIFEST, CapabilitySpec

from .base import SubAgent


BASE_ASSISTANT_PROMPT = (
    "You are Career Pilot — a job-hunt assistant.\n"
    "Rule 1: Never invent facts about the user, jobs, tools, or sub-agents. Use only the conversation and tool results.\n"
    "Rule 2: For specialist work (resume, cover letter, search, apply, tracking) delegate. For chit-chat or clarifying questions, answer directly.\n"
    "Rule 3: Ask for missing inputs once; do not retry the same question."
)


TOOL_PROTOCOL = (
    "Tool protocol:\n"
    "- Use ONLY the exact tool names listed under 'Capabilities enabled' above. Any other name fails and wastes an iteration.\n"
    "- When a tool is needed, reply with ONLY one <tool_call> tag — no prose, no markdown, no leading whitespace.\n"
    '- Shape: <tool_call>{"tool":"<name>","arguments":{...}}</tool_call>\n'
    "- One call per reply. After the result returns, answer the user using the findings.\n"
    "- If a tool errors, read the error, fix the arguments, retry once, then explain to the user.\n"
    "Examples:\n"
    '  OK:   <tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>\n'
    '  BAD:  <tool_call>{"tool":"find","arguments":{"pattern":"*.md"}}</tool_call>   ← \'find\' is not in the list'
)


DELEGATE_PROTOCOL = (
    "Delegate protocol:\n"
    "- For job-hunt specialist work, delegate to ONE sub-agent below. Reply with ONLY this tag:\n"
    '  <delegate>{"agent":"<name>","instruction":"<self-contained paragraph>"}</delegate>\n'
    "- The sub-agent will not see prior turns; the instruction must contain every detail it needs (full JD text, company, role, etc.).\n"
    "- The candidate profile and portal cookies are auto-injected — do NOT ask the user for them.\n"
    "- Only ASK the user when the user-supplied input is itself missing (e.g. no JD pasted).\n"
    "- Do not chain delegate and tool_call in the same reply. Pick one.\n"
    "Intent → agent:\n"
    "- 'tailor my resume / rewrite CV for this role'        → resume_tailor\n"
    "- 'write me a cover letter / motivation letter'         → resume_tailor (it handles both)\n"
    "- 'find jobs / search LinkedIn / parse this JD or URL'  → job_scout\n"
    "- 'apply to job X / submit application'                 → applier\n"
    "- 'log/list/update/show my applications'                → tracker"
)


def assistant_system_prompt(
    tools_enabled: bool,
    internet_tools_enabled: bool = False,
    catalog: dict[str, SubAgent] | None = None,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    sections = [f"{BASE_ASSISTANT_PROMPT}\nToday is {today}."]

    if tools_enabled:
        caps = enabled_capabilities(internet_tools_enabled)
        if caps:
            sections.append(format_capabilities(caps))
            sections.append(TOOL_PROTOCOL)

    if catalog:
        sections.append(format_subagents(catalog))
        sections.append(DELEGATE_PROTOCOL)

    return "\n\n".join(sections).strip()


def enabled_capabilities(internet_enabled: bool) -> list[CapabilitySpec]:
    return [
        cap
        for cap in MANIFEST.capabilities.values()
        if cap.tools and (internet_enabled or not cap.requires_internet)
    ]


def format_capabilities(caps: list[CapabilitySpec]) -> str:
    lines = ["Capabilities enabled:"]
    for cap in caps:
        lines.append(f"- {cap.name}: {cap.purpose}")
        tool_list = ", ".join(spec.name for spec in cap.tools)
        lines.append(f"  tools: {tool_list}")
    return "\n".join(lines)


def format_subagents(catalog: dict[str, SubAgent]) -> str:
    lines = ["Sub-agents available:"]
    for agent in catalog.values():
        lines.append(f"- {agent.name}: {agent.description}")
    return "\n".join(lines)
