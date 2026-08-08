"""Data loading: rows come in as lists of dicts."""


def load_rows(raw):
    """Validate and normalize raw row dicts. Requires 'label' and 'value'."""
    rows = []
    for i, item in enumerate(raw):
        if "label" not in item or "value" not in item:
            raise ValueError(f"row {i}: missing 'label' or 'value'")
        rows.append({"label": str(item["label"]), "value": float(item["value"])})
    return rows
