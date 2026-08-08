"""Configuration handling for report generation."""

from .utils import deep_merge

DEFAULTS = {
    "title": "Report",
    "format": {
        "decimals": 2,
        "thousands_sep": ",",
        "currency_symbol": "$",
    },
    "sections": {
        "summary": True,
        "details": True,
    },
}


def load_config(user_config=None):
    """Merge user configuration over the defaults."""
    return deep_merge(DEFAULTS, user_config or {})
