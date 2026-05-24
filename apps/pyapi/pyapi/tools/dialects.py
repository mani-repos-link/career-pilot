"""Per-model tool-call dialects.

Different model families emit tool calls in different surface syntaxes:
- Qwen / MiniMax / Nemotron / generic OpenAI-compat → ``<tool_call>{json}</tool_call>``
- Llama 3.x → ``<function=name>{json args}</function>`` or ``<|python_tag|>{json}``
- Gemma → ```` ```tool_code\n{json}\n``` ```` or a markdown ```json block
- LongCat / owl-alpha → ``<longcat_tool_call>name <longcat_arg_key>…``

`select_dialect(model)` resolves the active LLM's dialect by substring match against
the model identifier (case-insensitive). `parse_tool_call` consults the chosen dialect
first, then falls back to every other registered dialect so a model that drifts into
another family's format still parses.

To add a new dialect:
1. Write a `parse_*` function returning `ToolRequest | None`.
2. Append a `ToolDialect(...)` entry to `REGISTRY` with substrings of the model name.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .types import ToolRequest

DialectParser = Callable[[str], "ToolRequest | None"]


@dataclass(frozen=True)
class ToolDialect:
    name: str
    model_substrings: tuple[str, ...]
    parse: DialectParser


_JSON_TOOL_CALL_RE = re.compile(r"<tool_call>(?P<payload>.*?)</tool_call>", re.DOTALL)
_LLAMA_FUNCTION_RE = re.compile(
    r"<function=(?P<tool>[a-zA-Z0-9_-]+)>(?P<args>.*?)</function>",
    re.DOTALL,
)
_LLAMA_PYTHON_TAG_RE = re.compile(r"<\|python_tag\|>\s*(?P<payload>\{.*\})\s*$", re.DOTALL)
_GEMMA_TOOL_CODE_RE = re.compile(r"```tool_code\s*\n?(?P<payload>.*?)```", re.DOTALL)
_MD_JSON_RE = re.compile(r"```(?:json)?\s*\n(?P<payload>\{.*?\})\s*\n?```", re.DOTALL)
_LONGCAT_OPEN_RE = re.compile(
    r"<longcat_tool_call>(?P<tool>[a-zA-Z0-9_-]+)\s*(?P<body>.*?)</longcat_tool_call>",
    re.DOTALL,
)
_LONGCAT_LOOSE_RE = re.compile(
    r"(?P<tool>[a-zA-Z0-9_-]+)\s*(?P<body>.*?<longcat_arg_key>.*?</longcat_arg_value>.*?)</longcat_tool_call>",
    re.DOTALL,
)
_LONGCAT_ARG_RE = re.compile(
    r"<longcat_arg_key>(?P<key>.*?)</longcat_arg_key>\s*<longcat_arg_value>(?P<value>.*?)</longcat_arg_value>",
    re.DOTALL,
)


def parse_json_tool_call(content: str) -> ToolRequest | None:
    match = _JSON_TOOL_CALL_RE.search(content)
    if not match:
        return None
    return _build_from_json_payload(match.group("payload"))


def parse_llama_tool_call(content: str) -> ToolRequest | None:
    match = _LLAMA_FUNCTION_RE.search(content)
    if match:
        return _build_from_named_json(match.group("tool"), match.group("args"))
    match = _LLAMA_PYTHON_TAG_RE.search(content)
    if match:
        return _build_from_json_payload(match.group("payload"))
    return parse_json_tool_call(content)


def parse_gemma_tool_call(content: str) -> ToolRequest | None:
    match = _GEMMA_TOOL_CODE_RE.search(content)
    if match:
        return _build_from_json_payload(match.group("payload").strip())
    json_call = parse_json_tool_call(content)
    if json_call is not None:
        return json_call
    match = _MD_JSON_RE.search(content)
    if match:
        candidate = _build_from_json_payload(match.group("payload"))
        if candidate.tool != "invalid":
            return candidate
    return None


def parse_longcat_tool_call(content: str) -> ToolRequest | None:
    match = _LONGCAT_OPEN_RE.search(content)
    if not match:
        match = _LONGCAT_LOOSE_RE.search(content)
    if not match:
        return None
    arguments: dict[str, Any] = {}
    for arg in _LONGCAT_ARG_RE.finditer(match.group("body")):
        key = arg.group("key").strip()
        value = arg.group("value").strip()
        if key:
            arguments[key] = _coerce_value(value)
    return ToolRequest(tool=match.group("tool").strip(), arguments=arguments)


def _build_from_json_payload(payload: str) -> ToolRequest:
    cleaned = payload.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return ToolRequest(tool="invalid", arguments={"error": "tool call payload must be valid JSON"})
    tool = data.get("tool") or data.get("name")
    arguments = data.get("arguments")
    if arguments is None:
        arguments = data.get("parameters", {})
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        return ToolRequest(tool="invalid", arguments={"error": "tool call requires string tool and object arguments"})
    return ToolRequest(tool=tool, arguments=arguments)


def _build_from_named_json(tool: str, args_blob: str) -> ToolRequest:
    try:
        arguments = json.loads(args_blob.strip())
    except json.JSONDecodeError:
        return ToolRequest(tool="invalid", arguments={"error": "tool arguments must be valid JSON"})
    if not isinstance(arguments, dict):
        return ToolRequest(tool="invalid", arguments={"error": "tool arguments must be an object"})
    return ToolRequest(tool=tool, arguments=arguments)


def _coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


LONGCAT_DIALECT = ToolDialect(
    name="longcat",
    model_substrings=("longcat", "owl-alpha", "owl/"),
    parse=parse_longcat_tool_call,
)
LLAMA_DIALECT = ToolDialect(
    name="llama",
    model_substrings=("llama",),
    parse=parse_llama_tool_call,
)
GEMMA_DIALECT = ToolDialect(
    name="gemma",
    model_substrings=("gemma",),
    parse=parse_gemma_tool_call,
)
QWEN_DIALECT = ToolDialect(
    name="qwen",
    model_substrings=("qwen",),
    parse=parse_json_tool_call,
)
NEMOTRON_DIALECT = ToolDialect(
    name="nemotron",
    model_substrings=("nemotron",),
    parse=parse_json_tool_call,
)
MINIMAX_DIALECT = ToolDialect(
    name="minimax",
    model_substrings=("minimax",),
    parse=parse_json_tool_call,
)
DEFAULT_DIALECT = ToolDialect(
    name="json",
    model_substrings=(),
    parse=parse_json_tool_call,
)

REGISTRY: tuple[ToolDialect, ...] = (
    LONGCAT_DIALECT,
    LLAMA_DIALECT,
    GEMMA_DIALECT,
    QWEN_DIALECT,
    NEMOTRON_DIALECT,
    MINIMAX_DIALECT,
    DEFAULT_DIALECT,
)


def select_dialect(model: str | None) -> ToolDialect:
    if not model:
        return DEFAULT_DIALECT
    lowered = model.lower()
    for dialect in REGISTRY:
        if any(token in lowered for token in dialect.model_substrings):
            return dialect
    return DEFAULT_DIALECT
