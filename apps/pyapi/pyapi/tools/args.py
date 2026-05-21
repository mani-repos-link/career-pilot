from __future__ import annotations

from typing import Any


def string_arg(arguments: dict[str, Any], key: str, fallback: str) -> str:
    value = arguments.get(key, fallback)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def int_arg(arguments: dict[str, Any], key: str, fallback: int, *, minimum: int, maximum: int) -> int:
    value = arguments.get(key, fallback)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return max(minimum, min(maximum, value))


def limit_chars(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}\n... truncated at {max_chars} characters"
