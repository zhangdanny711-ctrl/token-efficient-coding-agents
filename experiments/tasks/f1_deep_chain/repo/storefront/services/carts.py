"""Shopping cart service.

Owns the full lifecycle of a :class:`~storefront.domain.models.Cart`:
creation, adding/removing/adjusting items, and clearing.  Prices are
snapshotted onto cart items at add time so an in-flight cart is
insulated from later catalog price changes; the pricing service uses
that snapshot when quoting.
"""

from storefront.domain.errors import NotFoundError, ValidationError
from storefront.domain.models import Cart, CartItem
from storefront.persistence import (
    CartRepository,
    CustomerRepository,
    ProductRepository,
)
from storefront.utils.logging import get_logger

logger = get_logger(__name__)


class CartService:
    """Application service for shopping carts.

    Parameters
    ----------
    store:
        Shared backing store used to construct the repositories.
    clock:
        Object with a ``now() -> datetime`` method; used to timestamp
        newly created carts.
    sequences:
        Mapping of id sequences from ``make_sequences()``; the ``cart``
        sequence supplies new cart ids.
    """

    def __init__(self, store, clock, sequences):
        self._carts = CartRepository(store)
        self._products = ProductRepository(store)
        self._customers = CustomerRepository(store)
        self._clock = clock
        self._sequences = sequences

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def create_cart(self, customer_id):
        """Create and persist an empty cart for an existing customer.

        Raises :class:`NotFoundError` (from the customer repository) if
        the customer does not exist -- carts are never created for
        unknown customers.
        """
        # Validate customer existence; get() raises NotFoundError.
        self._customers.get(customer_id)
        cart = Cart(
            cart_id=self._sequences["cart"].next(),
            customer_id=customer_id,
            items=[],
            created_at=self._clock.now(),
        )
        self._carts.add(cart)
        logger.debug("created cart %s for customer %s", cart.cart_id, customer_id)
        return cart

    def get_cart(self, cart_id):
        """Fetch a cart by id (NotFoundError if absent)."""
        return self._carts.get(cart_id)

    # ------------------------------------------------------------------
    # item mutation
    # ------------------------------------------------------------------
    def add_item(self, cart_id, product_id, qty):
        """Add ``qty`` units of a product to the cart.

        Rules:

        - Quantity must be a positive integer.
        - The product must exist and be active; inactive products can
          remain in carts that already hold them, but cannot be added.
        - If the cart already contains the product, quantities are
          merged into the existing line rather than duplicating it.
        - The line's ``unit_price`` is a snapshot of the product's
          current catalog price taken at first add; merging additional
          quantity keeps the original snapshot.

        Returns the updated cart.
        """
        self._require_positive_qty(qty)
        cart = self._carts.get(cart_id)
        product = self._products.get(product_id)
        if not product.active:
            raise ValidationError(
                "product %s (%s) is inactive and cannot be added to a cart"
                % (product.product_id, product.name)
            )

        existing = cart.find_item(product_id)
        if existing is not None:
            existing.quantity += qty
        else:
            cart.items.append(
                CartItem(
                    product_id=product.product_id,
                    quantity=qty,
                    unit_price=product.price,
                )
            )
        self._carts.update(cart)
        logger.debug(
            "cart %s: added %d x %s (total qty now %d)",
            cart_id,
            qty,
            product_id,
            cart.total_quantity(),
        )
        return cart

    def remove_item(self, cart_id, product_id):
        """Remove a product's line from the cart entirely.

        Removing a product that is not in the cart raises
        :class:`NotFoundError` so callers can distinguish a no-op from
        a successful removal.
        """
        cart = self._carts.get(cart_id)
        item = cart.find_item(product_id)
        if item is None:
            raise NotFoundError(
                "product %s is not in cart %s" % (product_id, cart_id)
            )
        cart.items = [i for i in cart.items if i.product_id != product_id]
        self._carts.update(cart)
        logger.debug("cart %s: removed product %s", cart_id, product_id)
        return cart

    def set_quantity(self, cart_id, product_id, qty):
        """Set the exact quantity for a product line.

        A quantity of zero removes the line (a common storefront UX
        convention); negative quantities are rejected.  Setting a
        quantity for a product not yet in the cart raises
        :class:`NotFoundError` -- use :meth:`add_item` to introduce new
        lines so the price snapshot is taken properly.
        """
        if not isinstance(qty, int) or qty < 0:
            raise ValidationError(
                "quantity must be a non-negative integer, got %r" % (qty,)
            )
        if qty == 0:
            return self.remove_item(cart_id, product_id)

        cart = self._carts.get(cart_id)
        item = cart.find_item(product_id)
        if item is None:
            raise NotFoundError(
                "product %s is not in cart %s" % (product_id, cart_id)
            )
        item.quantity = qty
        self._carts.update(cart)
        logger.debug("cart %s: set %s quantity to %d", cart_id, product_id, qty)
        return cart

    def clear_cart(self, cart_id):
        """Empty the cart's items while keeping the cart itself."""
        cart = self._carts.get(cart_id)
        cart.items = []
        self._carts.update(cart)
        logger.debug("cart %s cleared", cart_id)
        return cart

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def carts_for_customer(self, customer_id):
        """Return every cart belonging to a customer."""
        return self._carts.list_by_customer(customer_id)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _require_positive_qty(qty):
        """Reject non-positive or non-integer quantities."""
        if not isinstance(qty, int) or qty <= 0:
            raise ValidationError(
                "quantity must be a positive integer, got %r" % (qty,)
            )
