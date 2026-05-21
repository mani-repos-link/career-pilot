from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from pyapi.config import ToolConfig

from .args import int_arg, string_arg

IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
}
MAX_TEXT_FILE_BYTES = 1_000_000
CODE_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sql",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}


def run_ls(config: ToolConfig, arguments: dict[str, Any]) -> str:
    target = resolve_tool_path(config.workspace_root, string_arg(arguments, "path", "."))
    recursive = bool(arguments.get("recursive", False))
    max_entries = int_arg(arguments, "max_entries", 100, minimum=1, maximum=500)

    if not target.exists():
        raise ValueError(f"path does not exist: {display_path(config.workspace_root, target)}")

    if target.is_file():
        return display_path(config.workspace_root, target)

    entries: list[str] = []
    iterator = target.rglob("*") if recursive else target.iterdir()
    for child in sorted(iterator, key=lambda item: display_path(config.workspace_root, item)):
        if should_ignore(child):
            if child.is_dir() and recursive:
                continue
            continue
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{display_path(config.workspace_root, child)}{suffix}")
        if len(entries) >= max_entries:
            entries.append(f"... truncated at {max_entries} entries")
            break
    return "\n".join(entries)


def run_grep(config: ToolConfig, arguments: dict[str, Any]) -> str:
    pattern = string_arg(arguments, "pattern", "").strip()
    if not pattern:
        raise ValueError("grep requires a non-empty pattern")

    target = resolve_tool_path(config.workspace_root, string_arg(arguments, "path", "."))
    case_sensitive = bool(arguments.get("case_sensitive", False))
    max_matches = int_arg(arguments, "max_matches", 50, minimum=1, maximum=200)
    needle = pattern if case_sensitive else pattern.lower()

    if not target.exists():
        raise ValueError(f"path does not exist: {display_path(config.workspace_root, target)}")

    files = [target] if target.is_file() else iter_search_files(target)
    matches: list[str] = []
    for file_path in files:
        if should_ignore(file_path):
            continue
        try:
            if file_path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            lines = file_path.read_text(errors="strict").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            haystack = line if case_sensitive else line.lower()
            if needle in haystack:
                rel_path = display_path(config.workspace_root, file_path)
                matches.append(f"{rel_path}:{line_number}: {line.strip()}")
                if len(matches) >= max_matches:
                    matches.append(f"... truncated at {max_matches} matches")
                    return "\n".join(matches)

    return "\n".join(matches)


def run_read_file(config: ToolConfig, arguments: dict[str, Any]) -> str:
    target = resolve_tool_path(config.workspace_root, string_arg(arguments, "path", ""))
    start_line = int_arg(arguments, "start_line", 1, minimum=1, maximum=1_000_000)
    max_lines = int_arg(arguments, "max_lines", 120, minimum=1, maximum=300)

    if not target.exists():
        raise ValueError(f"path does not exist: {display_path(config.workspace_root, target)}")
    if not target.is_file():
        raise ValueError("read_file requires a file path")
    if target.stat().st_size > MAX_TEXT_FILE_BYTES:
        raise ValueError("file is too large to read")

    try:
        lines = target.read_text(errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("file is not valid text") from error

    end_line = min(len(lines), start_line + max_lines - 1)
    selected = lines[start_line - 1 : end_line]
    header = f"File: {display_path(config.workspace_root, target)} lines {start_line}-{end_line} of {len(lines)}"
    body = "\n".join(f"{line_number}: {line}" for line_number, line in enumerate(selected, start=start_line))
    return f"{header}\n{body}"


def run_project_tree(config: ToolConfig, arguments: dict[str, Any]) -> str:
    target = resolve_tool_path(config.workspace_root, string_arg(arguments, "path", "."))
    max_depth = int_arg(arguments, "max_depth", 3, minimum=1, maximum=8)
    max_entries = int_arg(arguments, "max_entries", 200, minimum=1, maximum=1000)

    if not target.exists():
        raise ValueError(f"path does not exist: {display_path(config.workspace_root, target)}")
    if target.is_file():
        return display_path(config.workspace_root, target)

    entries: list[str] = [f"{display_path(config.workspace_root, target)}/"]
    append_tree_entries(config.workspace_root, target, entries, max_depth=max_depth, max_entries=max_entries)
    return "\n".join(entries)


def run_find_symbol(config: ToolConfig, arguments: dict[str, Any]) -> str:
    symbol = string_arg(arguments, "symbol", "").strip()
    if not symbol:
        raise ValueError("find_symbol requires a symbol")
    target = resolve_tool_path(config.workspace_root, string_arg(arguments, "path", "."))
    max_matches = int_arg(arguments, "max_matches", 50, minimum=1, maximum=200)
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")

    files = [target] if target.is_file() else iter_search_files(target)
    matches: list[str] = []
    for file_path in files:
        if file_path.suffix.lower() not in CODE_EXTENSIONS or should_ignore(file_path):
            continue
        try:
            if file_path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            lines = file_path.read_text(errors="strict").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(f"{display_path(config.workspace_root, file_path)}:{line_number}: {line.strip()}")
                if len(matches) >= max_matches:
                    matches.append(f"... truncated at {max_matches} matches")
                    return "\n".join(matches)
    return "\n".join(matches)


def append_tree_entries(
    root: Path,
    directory: Path,
    entries: list[str],
    *,
    max_depth: int,
    max_entries: int,
    depth: int = 1,
) -> None:
    if depth > max_depth or len(entries) >= max_entries:
        return

    children = [child for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()) if not should_ignore(child)]
    for child in children:
        if len(entries) >= max_entries:
            entries.append(f"... truncated at {max_entries} entries")
            return
        indent = "  " * depth
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{indent}{child.name}{suffix}")
        if child.is_dir():
            append_tree_entries(root, child, entries, max_depth=max_depth, max_entries=max_entries, depth=depth + 1)


def resolve_tool_path(root: Path, raw_path: str) -> Path:
    workspace = root.resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError("path is outside the configured tool workspace")
    return resolved


def iter_search_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if should_ignore(path):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def should_ignore(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root.resolve()).as_posix() or "."
    except ValueError:
        return path.as_posix()
