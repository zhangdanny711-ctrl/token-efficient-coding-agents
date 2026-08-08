"""Plain-text rendering of the report."""

from .utils import format_number


def render_summary(rows, config):
    fmt = config["format"]
    total = sum(r["value"] for r in rows)
    number = format_number(total, fmt["decimals"], fmt["thousands_sep"])
    return f"{config['title']}: total {fmt['currency_symbol']}{number}"


def render_details(rows, config):
    fmt = config["format"]
    lines = []
    for r in rows:
        number = format_number(r["value"], fmt["decimals"], fmt["thousands_sep"])
        share = f"{r['share'] * 100:.1f}%" if "share" in r else ""
        lines.append(f"  {r['label']}: {fmt['currency_symbol']}{number} {share}".rstrip())
    return "\n".join(lines)
