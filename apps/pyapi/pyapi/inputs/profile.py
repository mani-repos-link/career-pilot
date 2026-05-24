from __future__ import annotations

from pathlib import Path

import yaml

from pyapi.config import find_data_dir

PROFILE_PATH = find_data_dir() / "profile" / "profile.yml"
EXAMPLE_PATH = find_data_dir() / "profile" / "profile.example.yml"


def load_profile_yaml(path: Path = PROFILE_PATH) -> str:
    """Return the profile YAML as a raw string for prompt injection.

    Caller passes the string straight to the LLM. We do not parse + reserialize —
    the user's hand-edited yml comments and field order are preserved.
    """
    if path.exists():
        return path.read_text().strip()
    if EXAMPLE_PATH.exists():
        raise FileNotFoundError(
            f"profile not found at {path}. Copy the template at {EXAMPLE_PATH} and edit it."
        )
    raise FileNotFoundError(f"profile not found at {path} and no example template available.")


def load_profile(path: Path = PROFILE_PATH) -> dict:
    """Parsed view of the profile yml. Use when you need to inspect fields in code."""
    raw = load_profile_yaml(path)
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or "candidate" not in data:
        raise ValueError(f"profile yml at {path} must have a top-level `candidate:` key")
    return data
