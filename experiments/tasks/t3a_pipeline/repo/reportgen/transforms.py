"""Row transforms applied before rendering."""


def sort_rows(rows, descending=True):
    return sorted(rows, key=lambda r: r["value"], reverse=descending)


def top_n(rows, n):
    return rows[:n]


def add_share(rows):
    """Annotate each row with its share of the total (0..1)."""
    total = sum(r["value"] for r in rows) or 1.0
    return [{**r, "share": r["value"] / total} for r in rows]
