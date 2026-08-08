"""Deterministic sample data for demos, benchmarks, and tests.

:func:`seed_store` populates an :class:`InMemoryStore` with a small but
realistic catalog: twelve products across four categories, five
customers with addresses in different states, four discount codes, and
inventory levels for every product.  All inserts go through the
repository layer so the seeded data exercises exactly the same code
paths that the application uses at runtime.

Identifiers come from the caller-supplied sequence generators and
timestamps from the caller-supplied clock, so seeding is fully
deterministic and reproducible.
"""

from __future__ import annotations

from typing import Any, Dict

from storefront.domain.models import Address, Customer, Discount, Product
from storefront.domain.money import Money
from storefront.persistence.repositories import (
    CustomerRepository,
    DiscountRepository,
    InventoryRecords,
    ProductRepository,
)
from storefront.persistence.store import InMemoryStore

# Catalog fixture: (sku, name, description, price_cents, category, tags,
# weight_grams).  Product ids are assigned from the sequence at seed time.
_PRODUCT_ROWS = (
    (
        "ELEC-1001", "Aurora Wireless Earbuds",
        "Noise-isolating true wireless earbuds with 28-hour case battery.",
        7999, "electronics", ["audio", "wireless", "bluetooth"], 58,
    ),
    (
        "ELEC-1002", "Volt USB-C Wall Charger 65W",
        "GaN fast charger with two USB-C ports and foldable prongs.",
        3499, "electronics", ["charging", "usb-c", "travel"], 112,
    ),
    (
        "ELEC-1003", "Pixelframe 27\" Monitor",
        "27-inch QHD IPS monitor with height-adjustable stand.",
        27999, "electronics", ["display", "office", "qhd"], 6400,
    ),
    (
        "KTCH-2001", "Ember Cast Iron Skillet 12\"",
        "Pre-seasoned cast iron skillet with pour spouts and helper handle.",
        4299, "kitchen", ["cookware", "cast-iron"], 3100,
    ),
    (
        "KTCH-2002", "Brewline Pour-Over Kettle",
        "Gooseneck stainless kettle with built-in thermometer, 1 liter.",
        5499, "kitchen", ["coffee", "kettle", "stainless"], 820,
    ),
    (
        "KTCH-2003", "Sharpcrest Chef Knife 8\"",
        "High-carbon steel chef knife with full tang and walnut handle.",
        8999, "kitchen", ["knives", "prep"], 285,
    ),
    (
        "OUTD-3001", "Trailhead 2P Backpacking Tent",
        "Two-person three-season tent, 2.1 kg packed, aluminum poles.",
        18999, "outdoors", ["camping", "tent", "backpacking"], 2100,
    ),
    (
        "OUTD-3002", "Summit Insulated Bottle 1L",
        "Double-wall vacuum bottle keeps drinks cold 24 hours.",
        2799, "outdoors", ["hydration", "insulated"], 390,
    ),
    (
        "OUTD-3003", "Ridgeline Headlamp 400",
        "400-lumen rechargeable headlamp with red night mode.",
        3299, "outdoors", ["lighting", "hiking", "rechargeable"], 86,
    ),
    (
        "OFFC-4001", "Standfast Laptop Riser",
        "Aluminum laptop stand with six height settings.",
        4599, "office", ["desk", "ergonomics", "aluminum"], 1240,
    ),
    (
        "OFFC-4002", "Quill Mechanical Keyboard",
        "Tenkeyless mechanical keyboard with hot-swappable switches.",
        10999, "office", ["keyboard", "mechanical", "tkl"], 780,
    ),
    (
        "OFFC-4003", "Ledger Desk Pad XL",
        "Stitched-edge vegan leather desk pad, 80 x 40 cm.",
        1999, "office", ["desk", "accessory"], 540,
    ),
)

# Customer fixture: (email, name, loyalty_tier, address rows).  Each
# address row is (street, city, state, postal_code).
_CUSTOMER_ROWS = (
    (
        "maya.chen@example.com", "Maya Chen", "gold",
        (("1200 Harbor Blvd", "San Diego", "CA", "92101"),),
    ),
    (
        "liam.osullivan@example.com", "Liam O'Sullivan", "standard",
        (("88 Greenwich St Apt 4B", "New York", "NY", "10006"),),
    ),
    (
        "sofia.ramirez@example.com", "Sofia Ramirez", "silver",
        (
            ("415 Travis St", "Houston", "TX", "77002"),
            ("902 Elm Loop", "Austin", "TX", "78704"),
        ),
    ),
    (
        "noah.kim@example.com", "Noah Kim", "standard",
        (("2311 Pine St", "Seattle", "WA", "98101"),),
    ),
    (
        "ava.novak@example.com", "Ava Novak", "gold",
        (("77 Alder Way", "Portland", "OR", "97205"),),
    ),
)

# Discount fixture: (code, kind, value, min_subtotal_cents, active).
_DISCOUNT_ROWS = (
    ("WELCOME10", "percent", 10, 0, True),
    ("SAVE15", "percent", 15, 5000, True),
    ("FIVER", "fixed", 500, 2000, True),
    ("EXPIRED", "percent", 20, 0, False),
)

# Inventory fixture: sku -> (available, reserved).  ELEC-1003 is the
# deliberate low-stock product used to exercise stock-out paths.
_INVENTORY_LEVELS = {
    "ELEC-1001": (140, 6),
    "ELEC-1002": (220, 0),
    "ELEC-1003": (2, 1),
    "KTCH-2001": (75, 2),
    "KTCH-2002": (60, 0),
    "KTCH-2003": (48, 3),
    "OUTD-3001": (35, 1),
    "OUTD-3002": (310, 8),
    "OUTD-3003": (95, 0),
    "OFFC-4001": (120, 4),
    "OFFC-4002": (55, 2),
    "OFFC-4003": (180, 0),
}


def seed_store(store: InMemoryStore, clock: Any, sequences: Dict[str, Any]) -> Dict[str, int]:
    """Populate ``store`` with the standard sample dataset.

    Args:
        store: The store to populate; expected to be empty.
        clock: A clock exposing ``now() -> datetime`` (e.g.
            :class:`storefront.utils.clock.FixedClock`).  Reserved for
            fixtures that carry timestamps; seeding stays deterministic
            because the clock is injected rather than read from the
            system.
        sequences: The id generators from
            :func:`storefront.utils.ids.make_sequences`, keyed by entity
            name (``"product"``, ``"customer"``, ...).

    Returns:
        A summary dict: ``{"products": 12, "customers": 5, "discounts": 4}``.
    """
    products = ProductRepository(store)
    customers = CustomerRepository(store)
    discounts = DiscountRepository(store)
    inventory = InventoryRecords(store)

    # Touch the clock once so seeding participates in the injected time
    # source; fixtures below are timestamp-free by design.
    clock.now()

    # -- Products -------------------------------------------------------
    sku_to_product_id: Dict[str, str] = {}
    for sku, name, description, price_cents, category, tags, weight in _PRODUCT_ROWS:
        product_id = sequences["product"].next()
        sku_to_product_id[sku] = product_id
        products.add(
            Product(
                product_id=product_id,
                sku=sku,
                name=name,
                description=description,
                price=Money(price_cents),
                category=category,
                tags=list(tags),
                weight_grams=weight,
            )
        )

    # -- Customers ------------------------------------------------------
    for email, name, tier, address_rows in _CUSTOMER_ROWS:
        customers.add(
            Customer(
                customer_id=sequences["customer"].next(),
                email=email,
                name=name,
                loyalty_tier=tier,
                addresses=[
                    Address(
                        street=street,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                    )
                    for street, city, state, postal_code in address_rows
                ],
            )
        )

    # -- Discounts --------------------------------------------------------
    for code, kind, value, min_subtotal_cents, active in _DISCOUNT_ROWS:
        discounts.add(
            Discount(
                code=code,
                kind=kind,
                value=value,
                min_subtotal_cents=min_subtotal_cents,
                active=active,
            )
        )

    # -- Inventory --------------------------------------------------------
    for sku, (available, reserved) in _INVENTORY_LEVELS.items():
        inventory.set_level(
            sku_to_product_id[sku], available=available, reserved=reserved
        )

    return {
        "products": len(_PRODUCT_ROWS),
        "customers": len(_CUSTOMER_ROWS),
        "discounts": len(_DISCOUNT_ROWS),
    }
