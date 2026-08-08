"""Config validation."""

VALID_SECTION_KEYS = {"summary", "details"}


def validate_config(config):
    """Raise ValueError on structurally invalid config."""
    if not isinstance(config.get("title"), str):
        raise ValueError("title must be a string")
    sections = config.get("sections", {})
    unknown = set(sections) - VALID_SECTION_KEYS
    if unknown:
        raise ValueError(f"unknown sections: {sorted(unknown)}")
    return config
