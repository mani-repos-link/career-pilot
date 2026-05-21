from __future__ import annotations

import json
import re
from typing import Any

from .types import ToolRequest

TOOL_CALL_RE = re.compile(r"<tool_call>(?P<payload>.*?)</tool_call>", re.DOTALL)
LONGCAT_TOOL_CALL_RE = re.compile(
    r"<longcat_tool_call>(?P<tool>[a-zA-Z0-9_-]+)\s*(?P<body>.*?)</longcat_tool_call>",
    re.DOTALL,
)
LONGCAT_LOOSE_TOOL_CALL_RE = re.compile(
    r"^\s*(?P<tool>[a-zA-Z0-9_-]+)\s*(?P<body>.*?<longcat_arg_key>.*?</longcat_arg_value>.*?)</longcat_tool_call>\s*$",
    re.DOTALL,
)
LONGCAT_ARGUMENT_RE = re.compile(
    r"<longcat_arg_key>(?P<key>.*?)</longcat_arg_key>\s*<longcat_arg_value>(?P<value>.*?)</longcat_arg_value>",
    re.DOTALL,
)


def parse_tool_call(content: str) -> ToolRequest | None:
    match = TOOL_CALL_RE.search(content)
    if not match:
        return parse_longcat_tool_call(content)

    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return ToolRequest(tool="invalid", arguments={"error": "tool call payload must be valid JSON"})

    tool = payload.get("tool")
    arguments = payload.get("arguments", {})
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        return ToolRequest(tool="invalid", arguments={"error": "tool call requires string tool and object arguments"})
    return ToolRequest(tool=tool, arguments=arguments)


def parse_longcat_tool_call(content: str) -> ToolRequest | None:
    match = LONGCAT_TOOL_CALL_RE.search(content)
    if not match:
        match = LONGCAT_LOOSE_TOOL_CALL_RE.search(content)
    if not match:
        return None

    arguments: dict[str, Any] = {}
    for argument_match in LONGCAT_ARGUMENT_RE.finditer(match.group("body")):
        key = argument_match.group("key").strip()
        value = argument_match.group("value").strip()
        if key:
            arguments[key] = parse_longcat_value(value)

    return ToolRequest(tool=match.group("tool").strip(), arguments=arguments)


def parse_longcat_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value
