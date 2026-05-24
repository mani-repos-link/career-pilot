from __future__ import annotations

import inspect
from typing import Awaitable, Callable, Iterable

from pyapi.config import ToolConfig

from .applications import (
    run_list_applications,
    run_log_application,
    run_store_jd,
    run_store_job,
    run_update_status,
)
from .args import limit_chars
from .data import run_explain_context
from .jd_parser import run_parse_jd
from .job_search import run_search_jobs
from .local import run_find_symbol, run_grep, run_ls, run_project_tree, run_read_file
from .manifest import MANIFEST
from .memory import run_forget, run_recall, run_remember
from .render import run_render_pdf, run_render_resume, run_save_document
from .types import ToolExecutionResult, ToolRequest
from .web import run_crawl_site, run_curl, run_fetch_url, run_read_llms_txt, run_web_search, run_wget

ToolHandler = Callable[[ToolConfig, dict, str | None], "str | Awaitable[str]"]


def _no_session(fn: Callable[[ToolConfig, dict], "str | Awaitable[str]"]) -> ToolHandler:
    return lambda config, args, _session: fn(config, args)


HANDLERS: dict[str, ToolHandler] = {
    "ls": _no_session(run_ls),
    "grep": _no_session(run_grep),
    "read_file": _no_session(run_read_file),
    "project_tree": _no_session(run_project_tree),
    "find_symbol": _no_session(run_find_symbol),
    "explain_context": run_explain_context,
    "fetch_url": _no_session(run_fetch_url),
    "curl": _no_session(run_curl),
    "wget": _no_session(run_wget),
    "web_search": _no_session(run_web_search),
    "read_llms_txt": _no_session(run_read_llms_txt),
    "crawl_site": _no_session(run_crawl_site),
    "remember": run_remember,
    "forget": run_forget,
    "recall": run_recall,
    "render_resume": _no_session(lambda config, args: run_render_resume(config, args)),
    "save_document": _no_session(lambda config, args: run_save_document(config, args)),
    "render_pdf": _no_session(lambda config, args: run_render_pdf(config, args)),
    "parse_jd": _no_session(run_parse_jd),
    "search_jobs": _no_session(run_search_jobs),
    "store_job": _no_session(run_store_job),
    "store_jd": _no_session(run_store_jd),
    "log_application": _no_session(run_log_application),
    "update_status": _no_session(run_update_status),
    "list_applications": _no_session(run_list_applications),
}


def execute_tool_call(
    config: ToolConfig,
    request: ToolRequest,
    current_session_id: str | None = None,
    *,
    allowed_names: Iterable[str] | None = None,
) -> ToolExecutionResult:
    if not config.enabled:
        return ToolExecutionResult(request.tool, False, "Tools are disabled.")

    if request.tool == "invalid":
        message = str(request.arguments.get("error", "Invalid tool call."))
        return ToolExecutionResult(request.tool, False, message)

    if allowed_names is not None:
        allowlist = set(allowed_names)
        if request.tool not in allowlist:
            return ToolExecutionResult(
                request.tool,
                False,
                f'Tool "{request.tool}" is not in this agent\'s allowlist. Allowed: {", ".join(sorted(allowlist)) or "(none)"}.',
            )

    handler = HANDLERS.get(request.tool)
    if handler is None:
        return ToolExecutionResult(
            request.tool,
            False,
            f'Unknown tool "{request.tool}". Available tools: {available_tools(config)}.',
        )

    try:
        output = handler(config, request.arguments, current_session_id)
    except Exception as error:
        return ToolExecutionResult(request.tool, False, str(error))

    if inspect.isawaitable(output):
        return ToolExecutionResult(
            request.tool,
            False,
            f'Tool "{request.tool}" is async; call execute_tool_call_async instead.',
        )

    return ToolExecutionResult(request.tool, True, limit_chars(output or "(no results)", config.max_output_chars))


async def execute_tool_call_async(
    config: ToolConfig,
    request: ToolRequest,
    current_session_id: str | None = None,
    *,
    allowed_names: Iterable[str] | None = None,
) -> ToolExecutionResult:
    if not config.enabled:
        return ToolExecutionResult(request.tool, False, "Tools are disabled.")

    if request.tool == "invalid":
        message = str(request.arguments.get("error", "Invalid tool call."))
        return ToolExecutionResult(request.tool, False, message)

    if allowed_names is not None:
        allowlist = set(allowed_names)
        if request.tool not in allowlist:
            return ToolExecutionResult(
                request.tool,
                False,
                f'Tool "{request.tool}" is not in this agent\'s allowlist. Allowed: {", ".join(sorted(allowlist)) or "(none)"}.',
            )

    handler = HANDLERS.get(request.tool)
    if handler is None:
        return ToolExecutionResult(
            request.tool,
            False,
            f'Unknown tool "{request.tool}". Available tools: {available_tools(config)}.',
        )

    try:
        output = handler(config, request.arguments, current_session_id)
        if inspect.isawaitable(output):
            output = await output
    except Exception as error:
        return ToolExecutionResult(request.tool, False, str(error))

    return ToolExecutionResult(request.tool, True, limit_chars(output or "(no results)", config.max_output_chars))


def format_tool_result(result: ToolExecutionResult) -> str:
    status = "ok" if result.ok else "error"
    return f"Tool result ({result.tool}, {status}):\n{result.output}"


def available_tools(config: ToolConfig) -> str:
    names = [
        spec.name
        for spec in MANIFEST.tools.values()
        if spec.name in HANDLERS
        and (config.internet_enabled or not MANIFEST.capabilities[spec.capability].requires_internet)
    ]
    return ", ".join(names)
