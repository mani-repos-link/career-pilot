def redacted_key(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 10:
        return "present-too-short"
    return f"{value[:7]}...{value[-4:]} len={len(value)}"
