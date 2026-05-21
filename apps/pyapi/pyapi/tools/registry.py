from __future__ import annotations

from pyapi.config import ToolConfig

from .args import limit_chars
from .data import run_explain_context, run_sqlite_query
from .local import run_find_symbol, run_grep, run_ls, run_project_tree, run_read_file
from .types import ToolExecutionResult, ToolRequest
from .web import run_crawl_site, run_curl, run_fetch_url, run_read_llms_txt, run_web_search, run_wget


def execute_tool_call(config: ToolConfig, request: ToolRequest, current_session_id: str | None = None) -> ToolExecutionResult:
    if not config.enabled:
        return ToolExecutionResult(request.tool, False, "Tools are disabled.")

    try:
        if request.tool == "ls":
            output = run_ls(config, request.arguments)
        elif request.tool == "grep":
            output = run_grep(config, request.arguments)
        elif request.tool == "read_file":
            output = run_read_file(config, request.arguments)
        elif request.tool == "project_tree":
            output = run_project_tree(config, request.arguments)
        elif request.tool == "find_symbol":
            output = run_find_symbol(config, request.arguments)
        elif request.tool == "sqlite_query":
            output = run_sqlite_query(config, request.arguments)
        elif request.tool == "explain_context":
            output = run_explain_context(config, request.arguments, current_session_id)
        elif request.tool == "fetch_url":
            output = run_fetch_url(config, request.arguments)
        elif request.tool == "curl":
            output = run_curl(config, request.arguments)
        elif request.tool == "wget":
            output = run_wget(config, request.arguments)
        elif request.tool == "web_search":
            output = run_web_search(config, request.arguments)
        elif request.tool == "read_llms_txt":
            output = run_read_llms_txt(config, request.arguments)
        elif request.tool == "crawl_site":
            output = run_crawl_site(config, request.arguments)
        elif request.tool == "invalid":
            output = str(request.arguments.get("error", "Invalid tool call."))
            return ToolExecutionResult(request.tool, False, output)
        else:
            return ToolExecutionResult(request.tool, False, f'Unknown tool "{request.tool}". Available tools: {available_tools(config)}.')
    except Exception as error:
        return ToolExecutionResult(request.tool, False, str(error))

    return ToolExecutionResult(request.tool, True, limit_chars(output or "(no results)", config.max_output_chars))


def format_tool_result(result: ToolExecutionResult) -> str:
    status = "ok" if result.ok else "error"
    return f"Tool result ({result.tool}, {status}):\n{result.output}"


def available_tools(config: ToolConfig) -> str:
    tools = [
        "ls",
        "grep",
        "read_file",
        "project_tree",
        "find_symbol",
        "sqlite_query",
        "explain_context",
    ]
    if config.internet_enabled:
        tools.extend(["fetch_url", "curl", "wget", "web_search", "read_llms_txt", "crawl_site"])
    return ", ".join(tools)
