from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    """One message in an LLM-bound history: role + content.

    The provider contract takes a list of Turn — not MessageRecord — so the
    provider never sees DB shape. Build Turns from MessageRecord via
    MessageRecord.to_turn(); synthesize them ad-hoc for tool-loop intermediates.
    """

    role: str
    content: str
