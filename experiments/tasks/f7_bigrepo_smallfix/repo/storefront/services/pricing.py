"""Pricing service: quotes, discounts, tax, and shipping.

This module turns a cart full of :class:`~storefront.domain.models.CartItem`
objects into a fully itemised :class:`PriceBreakdown`.  The pricing
pipeline applied by :meth:`PricingService.quote` is, in order:

1. **Line totals** -- each cart item's snapshot ``unit_price`` times its
   quantity (the domain's ``CartItem.line_total``).
2. **Subtotal** -- the sum of all line totals.
3. **Loyalty tier adjustment** -- an automatic percentage adjustment
   based on the customer's loyalty tier (currently only ``gold``
   receives a benefit).  Applied *before* any discount code so that
   discount minimum-subtotal thresholds are evaluated against the
   tier-adjusted subtotal.
4. **Discount code** -- an optional :class:`~storefront.domain.models.Discount`
   looked up by code and applied via the domain's ``discount_amount``.
5. **Tax** -- computed on the *taxable* amount (subtotal minus all
   discounts) using the destination state's rate via the domain's
   ``tax_for``.  Shipping is never taxed.
6. **Shipping** -- free above a configurable threshold, otherwise a
   flat rate plus a surcharge for heavy orders.

All arithmetic is carried out in integer cents through the domain
:class:`~storefront.domain.money.Money` type; no floats ever hold a
monetary amount.
"""

from dataclasses import dataclass, field

from storefront.domain.discounts import discount_amount
from storefront.domain.errors import DiscountError, NotFoundError, ValidationError
from storefront.domain.money import Money
from storefront.domain.tax import tax_for
from storefront.persistence import DiscountRepository
from storefront.utils.config import load_config
from storefront.utils.logging import get_logger

logger = get_logger(__name__)

#: Loyalty tiers recognised by the pricing engine.  Tiers not listed
#: here are treated as "standard" (no automatic adjustment).
KNOWN_TIERS = ("standard", "silver", "gold")

#: Percentage taken off the subtotal for gold-tier customers.
GOLD_TIER_DISCOUNT_RATE = 0.02


@dataclass
class PriceBreakdown:
    """Immutable-by-convention result of a pricing quote.

    Attributes
    ----------
    subtotal:
        Sum of all line totals after any loyalty tier adjustment,
        before discount codes, tax, and shipping.
    discount_total:
        Amount removed by the discount code (zero when no code was
        supplied).
    tax_total:
        Tax charged on the taxable amount (``subtotal - discount_total``).
    shipping_total:
        Shipping charge, including any heavy-order surcharge.
    grand_total:
        ``subtotal - discount_total + tax_total + shipping_total``.
    lines:
        Per-line detail dictionaries with keys ``product_id``,
        ``quantity``, ``unit_price``, and ``line_total``; monetary
        values are decimal strings such as ``"12.34"`` so the structure
        is JSON-safe as-is.
    discount_code:
        The applied discount code, or ``None`` when no code was used.
    """

    subtotal: Money
    discount_total: Money
    tax_total: Money
    shipping_total: Money
    grand_total: Money
    lines: list = field(default_factory=list)
    discount_code: str = None

    def as_dict(self):
        """Render the breakdown as a JSON-safe dictionary.

        Every :class:`Money` value is converted to a decimal string
        (e.g. ``"19.99"``); ``lines`` is already JSON-safe by
        construction.  The returned dictionary can be serialised with
        :func:`json.dumps` without a custom encoder.
        """
        return {
            "subtotal": self.subtotal.to_decimal_string(),
            "discount_total": self.discount_total.to_decimal_string(),
            "tax_total": self.tax_total.to_decimal_string(),
            "shipping_total": self.shipping_total.to_decimal_string(),
            "grand_total": self.grand_total.to_decimal_string(),
            "lines": [dict(line) for line in self.lines],
            "discount_code": self.discount_code,
        }


class PricingService:
    """Computes prices for carts and orders.

    Parameters
    ----------
    discount_repo:
        A :class:`~storefront.persistence.DiscountRepository` used to
        resolve discount codes.
    config:
        Optional dictionary of configuration overrides; merged over the
        defaults by :func:`storefront.utils.config.load_config`.  The
        keys consumed here are ``free_shipping_threshold_cents``,
        ``flat_shipping_cents``, ``heavy_order_grams``, and
        ``heavy_surcharge_cents``.
    """

    def __init__(self, discount_repo, config=None):
        self._discounts = discount_repo
        self._config = load_config(config)

    # ------------------------------------------------------------------
    # line-level arithmetic
    # ------------------------------------------------------------------
    def line_total(self, item):
        """Return the extended price of a single cart item.

        The unit price used is the *snapshot* captured when the item
        was added to the cart, deliberately insulating in-flight carts
        from later catalog price changes.

        Parameters
        ----------
        item:
            A :class:`~storefront.domain.models.CartItem`.

        Returns
        -------
        Money
            ``unit_price * quantity``.
        """
        if item.quantity <= 0:
            raise ValidationError(
                "cart item for product %s has non-positive quantity %d"
                % (item.product_id, item.quantity)
            )
        return item.line_total()

    def subtotal(self, items):
        """Sum the line totals of every cart item.

        Parameters
        ----------
        items:
            Iterable of :class:`~storefront.domain.models.CartItem`.

        Returns
        -------
        Money
            The cart subtotal before any adjustments.  An empty item
            list yields ``Money.zero()``.
        """
        total = Money.zero()
        for item in items:
            total = total.add(self.line_total(item))
        return total

    # ------------------------------------------------------------------
    # loyalty tier adjustment
    # ------------------------------------------------------------------
    def apply_tier_adjustment(self, subtotal, tier):
        """Apply the automatic loyalty-tier price adjustment.

        This is a deliberate extension hook: today only the ``gold``
        tier receives a benefit (a flat 2% off the subtotal); the
        ``standard`` and ``silver`` tiers pass through unchanged.
        Adding a new tier only requires touching this method.

        The adjustment happens *before* discount codes so a gold
        customer's discount-code eligibility (minimum subtotal
        thresholds) is judged on what they would actually pay.

        Parameters
        ----------
        subtotal:
            The pre-adjustment cart subtotal.
        tier:
            The customer's loyalty tier string.  Unknown tiers are
            treated as ``standard`` rather than rejected, so that
            pricing never hard-fails on a stale tier value.

        Returns
        -------
        Money
            The adjusted subtotal.
        """
        if tier == "gold":
            reduction = subtotal.percent(GOLD_TIER_DISCOUNT_RATE)
            adjusted = subtotal.sub(reduction)
            logger.debug(
                "gold tier adjustment: %s -> %s",
                subtotal.to_decimal_string(),
                adjusted.to_decimal_string(),
            )
            return adjusted
        # "standard", "silver", and anything unrecognised: no change.
        return subtotal

    # ------------------------------------------------------------------
    # discount codes
    # ------------------------------------------------------------------
    def discount_for(self, subtotal, discount_code):
        """Resolve and evaluate an optional discount code.

        Parameters
        ----------
        subtotal:
            The (tier-adjusted) subtotal the discount applies to.
        discount_code:
            The code entered by the customer, or ``None``/empty when no
            code was supplied.

        Returns
        -------
        tuple[Money, str | None]
            The discount amount and the code that produced it.  When no
            code is supplied the result is ``(Money.zero(), None)``.

        Raises
        ------
        DiscountError
            If the code is unknown (a repository
            :class:`~storefront.domain.errors.NotFoundError` is
            translated into a friendlier ``DiscountError``) or if the
            domain rules reject the discount, e.g. an inactive code or
            an unmet minimum subtotal.
        """
        if not discount_code:
            return Money.zero(), None
        try:
            discount = self._discounts.find_by_code(discount_code)
        except NotFoundError:
            raise DiscountError("unknown code %r" % (discount_code,))
        amount = discount_amount(discount, subtotal)
        logger.debug(
            "discount %s takes %s off subtotal %s",
            discount_code,
            amount.to_decimal_string(),
            subtotal.to_decimal_string(),
        )
        return amount, discount_code

    # ------------------------------------------------------------------
    # shipping
    # ------------------------------------------------------------------
    def shipping_for(self, items, products_by_id, subtotal_after_discount):
        """Compute the shipping charge for an order.

        The rules, in evaluation order:

        1. **Free shipping** -- if the post-discount subtotal meets or
           exceeds ``free_shipping_threshold_cents``, shipping is free
           regardless of weight.  Discounts therefore *can* push an
           order below the free-shipping bar.
        2. **Flat rate** -- otherwise the base charge is
           ``flat_shipping_cents``.
        3. **Heavy surcharge** -- if the physical weight of the order
           (sum of ``product.weight_grams * quantity`` over every line)
           strictly exceeds ``heavy_order_grams``, an additional
           ``heavy_surcharge_cents`` is added on top of the flat rate.

        Parameters
        ----------
        items:
            Iterable of cart items being shipped.
        products_by_id:
            Mapping of ``product_id`` to
            :class:`~storefront.domain.models.Product`, used to look up
            per-unit weights.
        subtotal_after_discount:
            The amount the customer pays for goods, used for the
            free-shipping threshold check.

        Returns
        -------
        Money
            The total shipping charge (possibly zero).
        """
        threshold = self._config["free_shipping_threshold_cents"]
        if subtotal_after_discount.cents >= threshold:
            logger.debug(
                "free shipping: %s >= threshold %d cents",
                subtotal_after_discount.to_decimal_string(),
                threshold,
            )
            return Money.zero()

        charge_cents = self._config["flat_shipping_cents"]
        total_weight = self._total_weight_grams(items, products_by_id)
        if total_weight > self._config["heavy_order_grams"]:
            charge_cents += self._config["heavy_surcharge_cents"]
            logger.debug(
                "heavy order surcharge applied: %d grams > %d grams",
                total_weight,
                self._config["heavy_order_grams"],
            )
        return Money(charge_cents)

    # ------------------------------------------------------------------
    # tax
    # ------------------------------------------------------------------
    def tax_for_address(self, taxable, address):
        """Compute sales tax for a destination address.

        The taxable base is the goods subtotal *minus* all discounts;
        shipping charges are not taxed.  Rate selection is delegated to
        the domain's :func:`storefront.domain.tax.tax_for`, keyed on
        the destination state.

        Parameters
        ----------
        taxable:
            The taxable amount (``subtotal - discount_total``).
        address:
            The shipping :class:`~storefront.domain.models.Address`;
            only its ``state`` participates in rate lookup.

        Returns
        -------
        Money
            The tax owed (zero in states without a configured rate).
        """
        if address is None:
            raise ValidationError("a shipping address is required to compute tax")
        return tax_for(taxable, address.state)

    # ------------------------------------------------------------------
    # full quote
    # ------------------------------------------------------------------
    def quote(self, items, products_by_id, address, discount_code=None, tier="standard"):
        """Produce a complete :class:`PriceBreakdown` for a cart.

        This is the single entry point order placement uses; it wires
        together every rule in this module in the documented pipeline
        order (lines -> subtotal -> tier adjustment -> discount code ->
        tax -> shipping) and guarantees the identity::

            grand_total == subtotal - discount_total
                           + tax_total + shipping_total

        Parameters
        ----------
        items:
            Non-empty iterable of cart items.
        products_by_id:
            Mapping of product id to product for every item; used for
            shipping-weight lookups.  A missing product is a
            :class:`ValidationError` -- callers are expected to have
            resolved products before quoting.
        address:
            Destination :class:`~storefront.domain.models.Address`.
        discount_code:
            Optional discount code to apply.
        tier:
            The customer's loyalty tier (see
            :meth:`apply_tier_adjustment`).

        Returns
        -------
        PriceBreakdown
        """
        items = list(items)
        self._validate_quote_inputs(items, products_by_id)

        raw_subtotal = self.subtotal(items)
        # The tier benefit is folded into discount_total (rather than
        # replacing the subtotal) so the reported subtotal always equals
        # the sum of the line totals — Order.validate() relies on that.
        adjusted_subtotal = self.apply_tier_adjustment(raw_subtotal, tier)
        tier_reduction = raw_subtotal.sub(adjusted_subtotal)

        code_discount, applied_code = self.discount_for(adjusted_subtotal, discount_code)
        discount = tier_reduction.add(code_discount)
        after_discount = raw_subtotal.sub(discount)

        tax = self.tax_for_address(after_discount, address)
        shipping = self.shipping_for(items, products_by_id, after_discount)

        grand = raw_subtotal.sub(discount).add(tax).add(shipping)

        breakdown = PriceBreakdown(
            subtotal=raw_subtotal,
            discount_total=discount,
            tax_total=tax,
            shipping_total=shipping,
            grand_total=grand,
            lines=self._line_details(items),
            discount_code=applied_code,
        )
        logger.debug("quote complete: %s", breakdown.as_dict())
        return breakdown

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _total_weight_grams(items, products_by_id):
        """Sum the physical weight of an order in grams.

        Each line contributes ``product.weight_grams * quantity``.
        Used exclusively by the heavy-order shipping surcharge rule.
        """
        total = 0
        for item in items:
            product = products_by_id.get(item.product_id)
            if product is None:
                raise ValidationError(
                    "no product resolved for cart item %s" % (item.product_id,)
                )
            total += product.weight_grams * item.quantity
        return total

    def _line_details(self, items):
        """Build the JSON-safe per-line detail list for a breakdown.

        Monetary values are rendered as decimal strings so consumers
        (API layers, reports) can serialise the structure directly.
        """
        details = []
        for item in items:
            details.append(
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price.to_decimal_string(),
                    "line_total": self.line_total(item).to_decimal_string(),
                }
            )
        return details

    @staticmethod
    def _validate_quote_inputs(items, products_by_id):
        """Reject structurally invalid quote requests early.

        A quote requires at least one item, and every item must have a
        resolved product in ``products_by_id`` (needed for weight-based
        shipping).  Quantity positivity is enforced per-line in
        :meth:`PricingService.line_total`.
        """
        if not items:
            raise ValidationError("cannot quote an empty item list")
        if products_by_id is None:
            raise ValidationError("products_by_id mapping is required")
        missing = [
            item.product_id for item in items if item.product_id not in products_by_id
        ]
        if missing:
            raise ValidationError(
                "quote is missing product records for: %s" % (", ".join(missing),)
            )
