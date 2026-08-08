"""Order orchestration service.

This module hosts :class:`OrderService`, the coordinator for the whole
order lifecycle::

    place_order   cart -> pending order (+ pending payment, stock reserved)
    pay_order     pending -> paid       (payment captured, stock committed)
    fulfill_order paid -> fulfilled     (shipment created)
    refund_order  fulfilled -> refunded (payment refunded)
    cancel_order  pending|paid -> cancelled
                  (stock released or restocked, payment refunded if captured)

Status transitions are ultimately authorised by the domain model's
``Order.can_transition_to``; this service enforces them *before* doing
any side effects so a rejected transition never leaves partial state
behind.  The one operation with multi-step side effects that can fail
midway -- inventory reservation during placement -- is explicitly
compensated: on :class:`~storefront.domain.errors.OutOfStockError` the
already-reserved lines are released before the error is re-raised.

Monetary figures always come from a :class:`PricingService` quote and
are validated by ``Order.validate()`` before persistence, so an order
in the repository is guaranteed internally consistent.
"""

from storefront.domain.errors import (
    IllegalStateError,
    NotFoundError,
    OutOfStockError,
    ValidationError,
)
from storefront.domain.models import Order, OrderLine, Payment, Shipment
from storefront.persistence import (
    CartRepository,
    CustomerRepository,
    DiscountRepository,
    OrderRepository,
    PaymentRepository,
    ProductRepository,
    ShipmentRepository,
)
from storefront.services.inventory import InventoryService
from storefront.services.pricing import PricingService
from storefront.utils.config import load_config
from storefront.utils.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """End-to-end order placement and lifecycle management.

    The service constructs its own repositories, pricing service, and
    inventory service over the shared ``store`` so that callers only
    need to hand it the application-level collaborators.

    Parameters
    ----------
    store:
        Shared backing store for all repositories.
    clock:
        Object with ``now() -> datetime``; stamps ``placed_at``.
    sequences:
        Id sequence mapping from ``make_sequences()``; the ``order``,
        ``payment``, and ``shipment`` sequences are consumed here.
    config:
        Optional configuration overrides, forwarded to both
        :func:`load_config` and the internal :class:`PricingService`.
    """

    def __init__(self, store, clock, sequences, config=None):
        self._orders = OrderRepository(store)
        self._customers = CustomerRepository(store)
        self._carts = CartRepository(store)
        self._products = ProductRepository(store)
        self._payments = PaymentRepository(store)
        self._shipments = ShipmentRepository(store)
        self._pricing = PricingService(DiscountRepository(store), config=config)
        self._inventory = InventoryService(store)
        self._clock = clock
        self._sequences = sequences
        self._config = load_config(config)

    # ==================================================================
    # placement
    # ==================================================================
    def place_order(self, customer_id, cart_id, discount_code=None, address_index=0):
        """Convert a customer's cart into a pending order.

        The placement pipeline (each step is a private helper below):

        1. Load and validate the customer and cart -- the cart must
           belong to the customer and must not be empty.
        2. Resolve the shipping address from the customer's address
           book by index.
        3. Resolve every cart item's product; inactive products are a
           :class:`ValidationError` (they were deactivated after being
           carted).
        4. Reserve inventory for every line.  If any line cannot be
           reserved, the lines reserved so far are rolled back and the
           :class:`OutOfStockError` is re-raised -- placement is
           all-or-nothing with respect to stock.
        5. Quote the cart via :class:`PricingService`, passing the
           customer's loyalty tier so tier pricing applies.
        6. Build immutable :class:`OrderLine` records from the cart
           items (sku/name denormalised from the product for the
           historical record).
        7. Create the ``pending`` :class:`Order` with totals lifted
           straight from the breakdown, run ``Order.validate()``, and
           persist it.
        8. Create a ``pending`` :class:`Payment` for the grand total.
        9. Clear the cart so it cannot be placed twice.

        Returns the persisted pending order.
        """
        customer, cart = self._load_customer_and_cart(customer_id, cart_id)
        address = self._resolve_shipping_address(customer, address_index)
        products_by_id = self._resolve_products(cart.items)

        self._reserve_lines(cart.items)
        try:
            breakdown = self._pricing.quote(
                cart.items,
                products_by_id,
                address,
                discount_code=discount_code,
                tier=customer.loyalty_tier,
            )
            lines = self._build_order_lines(cart.items, products_by_id)
            order = self._create_order(customer_id, lines, breakdown, address)
        except Exception:
            # Quoting or order construction failed after stock was
            # reserved; give the units back before propagating.
            self._release_lines(cart.items)
            raise

        self._create_pending_payment(order)
        self._clear_cart_after_placement(cart)
        logger.info(
            "order %s placed for customer %s (grand total %s)",
            order.order_id,
            customer_id,
            order.grand_total.to_decimal_string(),
        )
        return order

    # ------------------------------------------------------------------
    # placement helpers
    # ------------------------------------------------------------------
    def _load_customer_and_cart(self, customer_id, cart_id):
        """Fetch the customer and cart, enforcing ownership and content.

        Raises
        ------
        NotFoundError
            If either record does not exist.
        ValidationError
            If the cart belongs to a different customer, or is empty.
        """
        customer = self._customers.get(customer_id)
        cart = self._carts.get(cart_id)
        if cart.customer_id != customer_id:
            raise ValidationError(
                "cart %s belongs to customer %s, not %s"
                % (cart_id, cart.customer_id, customer_id)
            )
        if not cart.items:
            raise ValidationError("cart %s is empty; nothing to order" % (cart_id,))
        return customer, cart

    @staticmethod
    def _resolve_shipping_address(customer, address_index):
        """Pick the shipping address from the customer's address book.

        ``address_index`` selects among the customer's saved addresses;
        index 0 (the default) resolves via ``primary_address()`` so the
        domain's notion of "primary" is honoured.
        """
        if address_index == 0:
            address = customer.primary_address()
            if address is None:
                raise ValidationError(
                    "customer %s has no addresses on file" % (customer.customer_id,)
                )
            return address
        if address_index < 0 or address_index >= len(customer.addresses):
            raise ValidationError(
                "customer %s has no address at index %d"
                % (customer.customer_id, address_index)
            )
        return customer.addresses[address_index]

    def _resolve_products(self, items):
        """Load the product for every cart item.

        Returns a ``{product_id: Product}`` mapping.  A product that
        has been deactivated since it was carted raises
        :class:`ValidationError` -- we refuse to sell inactive goods.
        """
        products = {}
        for item in items:
            product = self._products.get(item.product_id)
            if not product.active:
                raise ValidationError(
                    "product %s (%s) is no longer available"
                    % (product.product_id, product.name)
                )
            products[product.product_id] = product
        return products

    def _reserve_lines(self, items):
        """Reserve stock for every cart line, all-or-nothing.

        On :class:`OutOfStockError` for any line, every reservation
        made so far in this call is released before the error is
        re-raised, so a failed placement never strands stock in the
        reserved pool.
        """
        reserved = []
        try:
            for item in items:
                self._inventory.reserve(item.product_id, item.quantity)
                reserved.append(item)
        except OutOfStockError:
            for done in reserved:
                self._inventory.release(done.product_id, done.quantity)
            logger.warning(
                "reservation rolled back after out-of-stock (%d lines released)",
                len(reserved),
            )
            raise

    def _release_lines(self, items):
        """Release previously reserved stock for every line (compensation)."""
        for item in items:
            self._inventory.release(item.product_id, item.quantity)

    @staticmethod
    def _build_order_lines(items, products_by_id):
        """Materialise order lines from cart items.

        SKU and name are denormalised from the product at placement
        time so the order remains an accurate historical record even if
        the catalog changes later.  Unit prices come from the cart's
        snapshot, and line totals are recomputed from that snapshot.
        """
        lines = []
        for item in items:
            product = products_by_id[item.product_id]
            lines.append(
                OrderLine(
                    product_id=item.product_id,
                    sku=product.sku,
                    name=product.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total(),
                )
            )
        return lines

    def _create_order(self, customer_id, lines, breakdown, address):
        """Assemble, validate, and persist the pending order.

        Totals are copied verbatim from the pricing breakdown; the
        domain's ``Order.validate()`` re-checks the grand-total
        identity as a final safety net before anything is written.
        """
        order = Order(
            order_id=self._sequences["order"].next(),
            customer_id=customer_id,
            lines=lines,
            status="pending",
            subtotal=breakdown.subtotal,
            discount_total=breakdown.discount_total,
            tax_total=breakdown.tax_total,
            shipping_total=breakdown.shipping_total,
            grand_total=breakdown.grand_total,
            shipping_address=address,
            placed_at=self._clock.now(),
        )
        order.validate()
        self._orders.add(order)
        return order

    def _create_pending_payment(self, order):
        """Create the pending payment that :meth:`pay_order` will capture."""
        payment = Payment(
            payment_id=self._sequences["payment"].next(),
            order_id=order.order_id,
            amount=order.grand_total,
            method="unspecified",
            status="pending",
        )
        self._payments.add(payment)
        return payment

    def _clear_cart_after_placement(self, cart):
        """Empty the placed cart so a double-submit cannot re-order it."""
        cart.items = []
        self._carts.update(cart)

    # ==================================================================
    # payment
    # ==================================================================
    def pay_order(self, order_id, method="card"):
        """Capture payment for a pending order.

        Effects, in order:

        1. Guard: the order must currently be ``pending`` (and the
           domain must allow the ``paid`` transition), otherwise
           :class:`IllegalStateError`.
        2. The order's pending payment is captured (status
           ``captured``) and stamped with the actual payment method.
        3. Every line's reservation is committed -- the stock is now
           permanently sold and will not return to the available pool.
        4. The order moves to ``paid``.

        Returns the updated order.
        """
        order = self._orders.get(order_id)
        self._require_transition(order, "paid")

        payment = self._pending_payment_for(order)
        payment.method = method
        payment.status = "captured"
        self._payments.update(payment)

        for line in order.lines:
            self._inventory.commit_reservation(line.product_id, line.quantity)

        order.status = "paid"
        self._orders.update(order)
        logger.info("order %s paid via %s", order_id, method)
        return order

    def _pending_payment_for(self, order):
        """Locate the order's single pending payment record.

        Placement always creates exactly one pending payment; its
        absence means the order is in an inconsistent state.
        """
        for payment in self._payments.list_by_order(order.order_id):
            if payment.status == "pending":
                return payment
        raise IllegalStateError(
            "order %s has no pending payment to capture" % (order.order_id,)
        )

    # ==================================================================
    # cancellation and refund
    # ==================================================================
    def cancel_order(self, order_id):
        """Cancel a pending or paid order.

        Inventory compensation depends on how far the order got:

        - ``pending``: stock was merely *reserved*, so each line is
          released back to the available pool.
        - ``paid``: reservations were already committed (the units left
          the books), so the units are *restocked* instead.

        Any captured payment is marked ``refunded``.  Transitions from
        other states are rejected via ``can_transition_to``.

        Returns the cancelled order.
        """
        order = self._orders.get(order_id)
        self._require_transition(order, "cancelled")

        if order.status == "pending":
            for line in order.lines:
                self._inventory.release(line.product_id, line.quantity)
        elif order.status == "paid":
            for line in order.lines:
                self._inventory.restock(line.product_id, line.quantity)

        self._refund_captured_payments(order)

        order.status = "cancelled"
        self._orders.update(order)
        logger.info("order %s cancelled", order_id)
        return order

    def refund_order(self, order_id):
        """Refund a fulfilled order.

        Only ``fulfilled`` orders can be refunded (earlier states go
        through :meth:`cancel_order` instead).  The captured payment is
        marked ``refunded`` and the order moves to ``refunded``.  Stock
        is *not* automatically returned: physical returns are handled
        by a separate warehouse process that calls
        :meth:`InventoryService.restock` once goods actually arrive.

        Returns the refunded order.
        """
        order = self._orders.get(order_id)
        if order.status != "fulfilled":
            raise IllegalStateError(
                "order %s cannot be refunded from status %r (must be fulfilled)"
                % (order_id, order.status)
            )
        self._require_transition(order, "refunded")

        self._refund_captured_payments(order)

        order.status = "refunded"
        self._orders.update(order)
        logger.info("order %s refunded", order_id)
        return order

    def _refund_captured_payments(self, order):
        """Mark every captured payment on the order as refunded.

        Pending payments are left untouched: money never moved, so
        there is nothing to give back.
        """
        for payment in self._payments.list_by_order(order.order_id):
            if payment.status == "captured":
                payment.status = "refunded"
                self._payments.update(payment)
                logger.debug(
                    "payment %s for order %s refunded",
                    payment.payment_id,
                    order.order_id,
                )

    # ==================================================================
    # fulfilment
    # ==================================================================
    def fulfill_order(self, order_id, carrier="UPS"):
        """Ship a paid order.

        Only ``paid`` orders can be fulfilled.  A
        :class:`~storefront.domain.models.Shipment` is created in the
        ``queued`` state with a tracking code drawn from the
        ``shipment`` id sequence, and the order moves to ``fulfilled``.

        Returns the new shipment (the order is updated in place).
        """
        order = self._orders.get(order_id)
        if order.status != "paid":
            raise IllegalStateError(
                "order %s cannot be fulfilled from status %r (must be paid)"
                % (order_id, order.status)
            )
        self._require_transition(order, "fulfilled")

        shipment_id = self._sequences["shipment"].next()
        shipment = Shipment(
            shipment_id=shipment_id,
            order_id=order.order_id,
            carrier=carrier,
            tracking_code=self._make_tracking_code(carrier, shipment_id),
            status="queued",
        )
        self._shipments.add(shipment)

        order.status = "fulfilled"
        self._orders.update(order)
        logger.info(
            "order %s fulfilled via %s (tracking %s)",
            order_id,
            carrier,
            shipment.tracking_code,
        )
        return shipment

    @staticmethod
    def _make_tracking_code(carrier, shipment_id):
        """Generate a pseudo tracking code for a shipment.

        Real carrier integration would call out to the carrier API;
        the benchmark repository fabricates a deterministic code from
        the carrier prefix and the shipment's own id, so a shipment can
        always be traced back from its tracking code.
        """
        return "%s-%s" % (carrier.upper(), shipment_id)

    # ==================================================================
    # queries
    # ==================================================================
    def get_order(self, order_id):
        """Fetch an order by id (NotFoundError if absent)."""
        return self._orders.get(order_id)

    def list_orders_for_customer(self, customer_id):
        """Return every order ever placed by a customer."""
        return self._orders.list_by_customer(customer_id)

    def list_orders_by_status(self, status):
        """Return every order currently in ``status``.

        Handy for operational dashboards (e.g. all ``paid`` orders
        awaiting fulfilment).  Unknown statuses simply return an empty
        list rather than raising, mirroring repository semantics.
        """
        return self._orders.list_by_status(status)

    def shipments_for_order(self, order_id):
        """Return the shipments created for an order.

        The order is fetched first so an unknown id raises
        :class:`NotFoundError` instead of silently returning ``[]``.
        """
        self._orders.get(order_id)
        return self._shipments.list_by_order(order_id)

    def payments_for_order(self, order_id):
        """Return the payment records attached to an order.

        As with :meth:`shipments_for_order`, the order id is validated
        before the payment lookup.
        """
        self._orders.get(order_id)
        return self._payments.list_by_order(order_id)

    def order_totals_summary(self, order_id):
        """Return a JSON-safe summary of an order's financials.

        The structure uses decimal strings for all monetary values and
        plain built-in containers throughout, so it can be handed to
        :func:`json.dumps` directly.  Includes per-line detail, the
        order status, and the latest payment status (or ``None`` when
        no payment record exists, which should not happen for orders
        created through this service).
        """
        order = self._orders.get(order_id)
        payments = self._payments.list_by_order(order_id)
        payment_status = payments[-1].status if payments else None
        return {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "status": order.status,
            "payment_status": payment_status,
            "subtotal": order.subtotal.to_decimal_string(),
            "discount_total": order.discount_total.to_decimal_string(),
            "tax_total": order.tax_total.to_decimal_string(),
            "shipping_total": order.shipping_total.to_decimal_string(),
            "grand_total": order.grand_total.to_decimal_string(),
            "lines": [
                {
                    "product_id": line.product_id,
                    "sku": line.sku,
                    "name": line.name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price.to_decimal_string(),
                    "line_total": line.line_total.to_decimal_string(),
                }
                for line in order.lines
            ],
        }

    # ==================================================================
    # internals
    # ==================================================================
    @staticmethod
    def _require_transition(order, target_status):
        """Raise :class:`IllegalStateError` when a transition is illegal.

        Delegates the actual rule to the domain's
        ``Order.can_transition_to`` so the state machine is defined in
        exactly one place; this helper only translates a refusal into a
        descriptive exception.
        """
        if not order.can_transition_to(target_status):
            raise IllegalStateError(
                "order %s cannot move from %r to %r"
                % (order.order_id, order.status, target_status)
            )
