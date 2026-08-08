"""URL slug generation."""

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Replace accented characters with their ASCII base form."""
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def slugify(text: str, max_length: int = 60) -> str:
    """Turn text into a lowercase URL slug.

    Words are joined by single hyphens; leading/trailing hyphens are
    stripped; result is truncated to max_length without cutting words
    in half (truncation drops trailing partial words).
    """
    text = strip_accents(text).lower()
    # Non-alphanumeric runs are collapsed into a single hyphen.
    text = re.sub(r"[^a-z0-9]", "-", text)
    text = text.strip("-")
    if len(text) <= max_length:
        return text
    # Truncate at the last hyphen before max_length so words stay whole.
    cut = text.rfind("-", 0, max_length + 1)
    if cut == -1:
        return text[:max_length]
    return text[:cut].rstrip("-")


def unique_slug(text: str, existing) -> str:
    """Return a slug not present in `existing`, adding -2, -3, ... suffixes."""
    base = slugify(text)
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"
