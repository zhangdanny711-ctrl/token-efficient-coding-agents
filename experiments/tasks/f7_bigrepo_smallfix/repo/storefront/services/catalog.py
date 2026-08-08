"""Product catalog service.

Read-mostly operations over the product catalog (search, filtering)
plus the administrative mutations (adding products, toggling
availability).  Pricing and inventory concerns live in their own
services; this module only cares about the products themselves.
"""

from storefront.domain.errors import ValidationError
from storefront.domain.models import Product
from storefront.domain.money import Money
from storefront.persistence import ProductRepository
from storefront.utils.logging import get_logger

logger = get_logger(__name__)


class CatalogService:
    """Application service for the product catalog.

    Parameters
    ----------
    store:
        Shared backing store used to construct the repository.
    """

    def __init__(self, store):
        self._products = ProductRepository(store)

    # ------------------------------------------------------------------
    # search and browse
    # ------------------------------------------------------------------
    def search(self, query):
        """Search active products by name or tag, case-insensitively.

        A product matches when the query term appears as a substring of
        its name, or matches (substring) any of its tags.  Blank
        queries are rejected rather than returning the whole catalog --
        use :meth:`list_active` for that.

        Returns matching products sorted by name for stable output.
        """
        if not query or not query.strip():
            raise ValidationError("search query must not be blank")
        term = query.strip().lower()
        matches = []
        for product in self._products.list_active():
            if term in product.name.lower():
                matches.append(product)
                continue
            if any(term in tag.lower() for tag in product.tags):
                matches.append(product)
        matches.sort(key=lambda p: p.name.lower())
        logger.debug("search %r matched %d products", term, len(matches))
        return matches

    def list_active(self):
        """Return every active product."""
        return self._products.list_active()

    def list_by_category(self, category):
        """Return the products in a category (delegates to the repository)."""
        return self._products.list_by_category(category)

    def price_between(self, lo_cents, hi_cents):
        """Return active products whose price falls in an inclusive range.

        Bounds are integer cents; ``lo_cents`` must be non-negative and
        no greater than ``hi_cents``.  Results are sorted by ascending
        price so callers get a natural "cheapest first" ordering.
        """
        if lo_cents < 0:
            raise ValidationError("lower price bound must be non-negative")
        if hi_cents < lo_cents:
            raise ValidationError(
                "upper price bound (%d) is below lower bound (%d)"
                % (hi_cents, lo_cents)
            )
        results = [
            product
            for product in self._products.list_active()
            if lo_cents <= product.price.cents <= hi_cents
        ]
        results.sort(key=lambda p: p.price.cents)
        return results

    def get_product(self, product_id):
        """Fetch a product by id (NotFoundError if absent)."""
        return self._products.get(product_id)

    # ------------------------------------------------------------------
    # administration
    # ------------------------------------------------------------------
    def add_product(
        self,
        sequences,
        sku,
        name,
        description,
        price_cents,
        category,
        tags,
        weight_grams,
    ):
        """Create and persist a new active product.

        Parameters
        ----------
        sequences:
            Id sequence mapping from ``make_sequences()``; the
            ``product`` sequence supplies the new id.
        sku, name, description, category:
            Descriptive fields; sku and name must be non-blank.
        price_cents:
            Unit price in integer cents; must be positive.
        tags:
            Iterable of tag strings (stored as a list).
        weight_grams:
            Physical unit weight, used by shipping surcharges; must be
            non-negative.

        Returns the persisted product.
        """
        if not sku or not sku.strip():
            raise ValidationError("product sku must not be blank")
        if not name or not name.strip():
            raise ValidationError("product name must not be blank")
        if not isinstance(price_cents, int) or price_cents <= 0:
            raise ValidationError(
                "price_cents must be a positive integer, got %r" % (price_cents,)
            )
        if not isinstance(weight_grams, int) or weight_grams < 0:
            raise ValidationError(
                "weight_grams must be a non-negative integer, got %r" % (weight_grams,)
            )

        product = Product(
            product_id=sequences["product"].next(),
            sku=sku.strip(),
            name=name.strip(),
            description=description,
            price=Money(price_cents),
            category=category,
            tags=list(tags),
            weight_grams=weight_grams,
            active=True,
        )
        self._products.add(product)
        logger.info("added product %s (%s)", product.product_id, product.sku)
        return product

    def deactivate(self, product_id):
        """Hide a product from sale (existing carts keep their snapshot).

        Deactivation is idempotent.  Returns the updated product.
        """
        product = self._products.get(product_id)
        if product.active:
            product.active = False
            self._products.update(product)
            logger.info("deactivated product %s", product_id)
        return product

    def activate(self, product_id):
        """Return a previously deactivated product to sale (idempotent)."""
        product = self._products.get(product_id)
        if not product.active:
            product.active = True
            self._products.update(product)
            logger.info("activated product %s", product_id)
        return product
