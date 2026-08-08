"""Application configuration defaults and loading.

Configuration is a flat dict validated against :data:`DEFAULTS`;
unknown keys are rejected so typos fail fast rather than being
silently ignored.
"""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    "currency": "USD",
    "free_shipping_threshold_cents": 7500,
    "flat_shipping_cents": 599,
    "heavy_order_grams": 5000,
    "heavy_surcharge_cents": 400,
    "default_tax_state": "CA",
    "report_top_n": 5,
}


def load_config(overrides: dict | None = None) -> dict:
    """Build an effective config from :data:`DEFAULTS` plus ``overrides``.

    The defaults are copied (never mutated) and overrides are
    shallow-merged on top. Any override key not present in
    :data:`DEFAULTS` raises ``ValueError``.
    """
    config = dict(DEFAULTS)
    if overrides is None:
        return config
    unknown = sorted(set(overrides) - set(DEFAULTS))
    if unknown:
        raise ValueError(f"unknown config keys: {', '.join(unknown)}")
    config.update(overrides)
    return config
