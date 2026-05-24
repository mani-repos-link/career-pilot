from __future__ import annotations

from .models import MemoryRecord


def format_memory_block(memories: list[MemoryRecord], max_chars: int) -> str:
    """Format memories as a system-prompt section. Empty string when no memories.

    Truncated at max_chars to keep the prompt bounded. Caller decides how to splice
    the block into the prompt.
    """
    if not memories:
        return ""

    lines = ["Memories:"]
    for memory in memories:
        lines.append(f"- [{memory.scope}] {memory.key}: {memory.content}")
    block = "\n".join(lines)

    if max_chars > 0 and len(block) > max_chars:
        return block[: max_chars - len(_TRUNCATED)] + _TRUNCATED
    return block


_TRUNCATED = "\n[…memories truncated]"
