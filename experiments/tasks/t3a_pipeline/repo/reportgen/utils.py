"""Small shared helpers."""


def deep_merge(base, override):
    """Return a new dict with `override` merged over `base`.

    Nested dicts merge key-by-key; other values in override replace base.
    """
    out = dict(base)
    for key, value in override.items():
        out[key] = value
    return out


def format_number(value, decimals, thousands_sep):
    s = f"{value:,.{decimals}f}"
    if thousands_sep != ",":
        s = s.replace(",", thousands_sep)
    return s


def clamp(value, lo, hi):
    return max(lo, min(hi, value))
