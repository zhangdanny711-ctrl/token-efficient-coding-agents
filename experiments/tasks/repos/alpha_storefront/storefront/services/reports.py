"""Reporting service.

Read-only aggregate queries over the order book and product catalog.
Everything here returns JSON-safe structures: monetary values are
decimal strings (via ``Money.to_decimal_string()``), never Money
objects or floats, so reports can be serialised directly.

Revenue reporting convention: an order counts toward revenue once it
has been paid, i.e. in the ``paid`` or ``fulfilled`` states.  Pending
and cancelled orders never count; refunded orders are excluded from
revenue-style metrics because the money was returned.
"""

from storefront.domain.money import Money
from storefront.persistence import OrderRepository, ProductRepository
from storefront.utils.config import load_config
from storefront.utils.logging import get_logger

logger = get_logger(__name__)

#: Statuses whose orders count as realised revenue.
REVENUE_STATUSES = ("paid", "fulfilled")

#: All statuses an order can hold, for sales_by_status buckets.
ALL_STATUSES = ("pending", "paid", "fulfilled", "cancelled", "refunded")


class ReportsService:
    """Aggregate reporting over orders and products.

    Parameters
    ----------
    store:
        Shared backing store used to construct the repositories.
    config:
        Optional configuration overrides; ``report_top_n`` controls the
        default size of :meth:`top_products`.
    """

    def __init__(self, store, config=None):
        self._orders = OrderRepository(store)
        self._products = ProductRepository(store)
        self._config = load_config(config)

    # ------------------------------------------------------------------
    # revenue
    # ------------------------------------------------------------------
    def revenue_summary(self):
        """Summarise realised revenue across paid and fulfilled orders.

        Returns a dict with:

        - ``order_count``: number of revenue-bearing orders.
        - ``gross_revenue``: sum of grand totals (decimal string).
        - ``tax_collected``: sum of tax totals.
        - ``shipping_collected``: sum of shipping totals.
        - ``discounts_given``: sum of discount totals.

        All monetary values are decimal strings.
        """
        orders = self._revenue_orders()
        gross = Money.zero()
        tax = Money.zero()
        shipping = Money.zero()
        discounts = Money.zero()
        for order in orders:
            gross = gross.add(order.grand_total)
            tax = tax.add(order.tax_total)
            shipping = shipping.add(order.shipping_total)
            discounts = discounts.add(order.discount_total)
        summary = {
            "order_count": len(orders),
            "gross_revenue": gross.to_decimal_string(),
            "tax_collected": tax.to_decimal_string(),
            "shipping_collected": shipping.to_decimal_string(),
            "discounts_given": discounts.to_decimal_string(),
        }
        logger.debug("revenue summary over %d orders", len(orders))
        return summary

    def sales_by_status(self):
        """Count orders in each lifecycle status.

        Every known status appears in the result (with a zero count if
        no orders hold it) so consumers get a stable shape.
        """
        counts = {status: 0 for status in ALL_STATUSES}
        for order in self._orders.list():
            counts[order.status] = counts.get(order.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    def top_products(self, n=None):
        """Rank products by realised revenue.

        Aggregates units and line revenue across every paid/fulfilled
        order, then returns the top ``n`` products (default: the
        configured ``report_top_n``) as dicts with keys ``product_id``,
        ``name``, ``units``, and ``revenue`` (decimal string), sorted
        by revenue descending; ties break on units then product id for
        determinism.

        Product names are denormalised from the order lines themselves
        so the report works even if a product was later removed from
        the catalog.
        """
        if n is None:
            n = self._config["report_top_n"]
        if n <= 0:
            return []

        totals = {}
        for order in self._revenue_orders():
            for line in order.lines:
                entry = totals.setdefault(
                    line.product_id,
                    {"name": line.name, "units": 0, "revenue_cents": 0},
                )
                entry["units"] += line.quantity
                entry["revenue_cents"] += line.line_total.cents

        ranked = sorted(
            totals.items(),
            key=lambda pair: (-pair[1]["revenue_cents"], -pair[1]["units"], pair[0]),
        )
        return [
            {
                "product_id": product_id,
                "name": data["name"],
                "units": data["units"],
                "revenue": Money(data["revenue_cents"]).to_decimal_string(),
            }
            for product_id, data in ranked[:n]
        ]

    # ------------------------------------------------------------------
    # customers
    # ------------------------------------------------------------------
    def customer_lifetime_value(self, customer_id):
        """Total realised spend for one customer, as a decimal string.

        Considers the customer's ``paid``, ``fulfilled``, and
        ``refunded`` orders, but **excludes refunded orders from the
        sum**: a refunded order's money went back to the customer, so
        it contributes nothing to lifetime value.  (Refunded orders are
        still "considered" in the sense that they are deliberately
        filtered out here rather than accidentally included -- this is
        the documented business rule, not an oversight.)  Pending and
        cancelled orders never involve settled money and are likewise
        excluded.
        """
        total = Money.zero()
        for order in self._orders.list_by_customer(customer_id):
            if order.status in REVENUE_STATUSES:
                total = total.add(order.grand_total)
            # "refunded" is intentionally skipped: money was returned.
        return total.to_decimal_string()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _revenue_orders(self):
        """Return every order in a revenue-bearing status."""
        orders = []
        for status in REVENUE_STATUSES:
            orders.extend(self._orders.list_by_status(status))
        return orders
