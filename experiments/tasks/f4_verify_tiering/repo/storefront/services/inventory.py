"""Inventory management service.

Wraps :class:`storefront.persistence.InventoryRecords` with the business
rules for reserving, releasing, committing, and adjusting stock.  The
underlying record for each product tracks two counters:

- ``available``: units on hand that can still be promised to new orders.
- ``reserved``: units promised to pending (unpaid) orders.

The lifecycle of a unit of stock is::

    restock/adjust  ->  available
    reserve         ->  available -1, reserved +1   (order placed)
    commit          ->  reserved -1                 (order paid; permanent)
    release         ->  reserved -1, available +1   (order cancelled)
"""

from storefront.domain.errors import OutOfStockError, ValidationError
from storefront.persistence import InventoryRecords
from storefront.utils.logging import get_logger

logger = get_logger(__name__)


class InventoryService:
    """Stock level bookkeeping for products.

    Parameters
    ----------
    store:
        The shared backing store handed to every repository/record set
        in the application.  The service builds its own
        :class:`InventoryRecords` view over it.
    """

    def __init__(self, store):
        self._records = InventoryRecords(store)

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def available(self, product_id):
        """Return the number of units currently available for sale.

        Reserved units are excluded: they are promised to pending
        orders and cannot be sold again.
        """
        level = self._records.get_level(product_id)
        return level["available"]

    def reserved(self, product_id):
        """Return the number of units currently held by reservations."""
        level = self._records.get_level(product_id)
        return level["reserved"]

    # ------------------------------------------------------------------
    # reservation lifecycle
    # ------------------------------------------------------------------
    def reserve(self, product_id, qty):
        """Move ``qty`` units from available to reserved.

        Called when an order is placed but not yet paid.  Raises
        :class:`OutOfStockError` when the product does not have enough
        available stock, naming the product and both quantities so the
        caller can surface a useful message.
        """
        self._require_positive(qty)
        level = self._records.get_level(product_id)
        if level["available"] < qty:
            raise OutOfStockError(
                "insufficient stock for product %s: requested %d, available %d"
                % (product_id, qty, level["available"])
            )
        self._records.update_level(
            product_id,
            available=level["available"] - qty,
            reserved=level["reserved"] + qty,
        )
        logger.debug("reserved %d units of %s", qty, product_id)

    def release(self, product_id, qty):
        """Return ``qty`` reserved units back to the available pool.

        Called when a pending order is cancelled.  Releasing more than
        is currently reserved indicates a bookkeeping bug and raises
        :class:`ValidationError`.
        """
        self._require_positive(qty)
        level = self._records.get_level(product_id)
        if level["reserved"] < qty:
            raise ValidationError(
                "cannot release %d units of product %s: only %d reserved"
                % (qty, product_id, level["reserved"])
            )
        self._records.update_level(
            product_id,
            available=level["available"] + qty,
            reserved=level["reserved"] - qty,
        )
        logger.debug("released %d units of %s", qty, product_id)

    def commit_reservation(self, product_id, qty):
        """Permanently consume ``qty`` reserved units.

        Called when an order is paid: the units leave the reserved pool
        and are *not* returned to available stock -- they are gone.
        """
        self._require_positive(qty)
        level = self._records.get_level(product_id)
        if level["reserved"] < qty:
            raise ValidationError(
                "cannot commit %d units of product %s: only %d reserved"
                % (qty, product_id, level["reserved"])
            )
        self._records.update_level(product_id, reserved=level["reserved"] - qty)
        logger.debug("committed %d units of %s", qty, product_id)

    # ------------------------------------------------------------------
    # stock adjustments
    # ------------------------------------------------------------------
    def adjust(self, product_id, delta):
        """Apply a manual correction of ``delta`` units to available stock.

        Positive deltas add stock (e.g. found during a recount), negative
        deltas remove it (e.g. damaged units).  The resulting available
        count may never go below zero.
        """
        if not isinstance(delta, int) or delta == 0:
            raise ValidationError("adjustment delta must be a non-zero integer")
        level = self._records.get_level(product_id)
        new_available = level["available"] + delta
        if new_available < 0:
            raise ValidationError(
                "adjustment of %d would drive product %s below zero (available %d)"
                % (delta, product_id, level["available"])
            )
        self._records.update_level(product_id, available=new_available)
        logger.debug("adjusted %s by %+d units", product_id, delta)

    def restock(self, product_id, qty):
        """Add ``qty`` newly received units to the available pool."""
        self._require_positive(qty)
        level = self._records.get_level(product_id)
        self._records.update_level(product_id, available=level["available"] + qty)
        logger.debug("restocked %s with %d units", product_id, qty)

    def set_level(self, product_id, available, reserved=0):
        """Overwrite the stock record for a product (initial seeding)."""
        if available < 0 or reserved < 0:
            raise ValidationError("stock levels must be non-negative")
        self._records.set_level(product_id, available, reserved=reserved)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _require_positive(qty):
        """Reject non-positive or non-integer quantities."""
        if not isinstance(qty, int) or qty <= 0:
            raise ValidationError("quantity must be a positive integer, got %r" % (qty,))
