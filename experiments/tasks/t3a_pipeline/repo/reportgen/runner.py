"""End-to-end report generation."""

from .config import load_config
from .loaders import load_rows
from .renderers import render_details, render_summary
from .transforms import add_share, sort_rows
from .validators import validate_config


def generate_report(raw_rows, user_config=None):
    config = validate_config(load_config(user_config))
    rows = add_share(sort_rows(load_rows(raw_rows)))

    parts = []
    if config["sections"]["summary"]:
        parts.append(render_summary(rows, config))
    if config["sections"]["details"]:
        parts.append(render_details(rows, config))
    return "\n".join(parts)
