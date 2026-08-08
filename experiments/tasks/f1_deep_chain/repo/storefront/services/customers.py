"""Customer account service.

Handles registration, address book maintenance, and loyalty tier
management for :class:`~storefront.domain.models.Customer` records.
"""

from storefront.domain.errors import NotFoundError, ValidationError
from storefront.domain.models import Address, Customer
from storefront.persistence import CustomerRepository
from storefront.utils.logging import get_logger

logger = get_logger(__name__)

#: Loyalty tiers a customer may hold, in ascending order of benefit.
VALID_TIERS = ("standard", "silver", "gold")


class CustomerService:
    """Application service for customer accounts.

    Parameters
    ----------
    store:
        Shared backing store used to construct the repository.
    sequences:
        Id sequence mapping from ``make_sequences()``; the ``customer``
        sequence supplies new customer ids.
    """

    def __init__(self, store, sequences):
        self._customers = CustomerRepository(store)
        self._sequences = sequences

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------
    def register_customer(self, email, name, address):
        """Create a new customer account.

        Email addresses are the unique natural key for accounts: an
        attempt to register with an email that already exists raises
        :class:`ValidationError`.  Uniqueness is checked by attempting
        a ``find_by_email`` lookup and treating "not found" as the
        success path.

        Parameters
        ----------
        email:
            The customer's email address (normalised to lowercase).
        name:
            Display name.
        address:
            Initial :class:`~storefront.domain.models.Address`; becomes
            the customer's primary address.

        Returns the persisted customer, starting at the ``standard``
        loyalty tier.
        """
        normalised = self._normalise_email(email)
        if not name or not name.strip():
            raise ValidationError("customer name must not be blank")
        if not isinstance(address, Address):
            raise ValidationError("an initial Address is required for registration")

        try:
            self._customers.find_by_email(normalised)
        except NotFoundError:
            pass
        else:
            raise ValidationError(
                "a customer with email %s is already registered" % (normalised,)
            )

        customer = Customer(
            customer_id=self._sequences["customer"].next(),
            email=normalised,
            name=name.strip(),
            loyalty_tier="standard",
            addresses=[address],
        )
        self._customers.add(customer)
        logger.info("registered customer %s (%s)", customer.customer_id, normalised)
        return customer

    # ------------------------------------------------------------------
    # profile maintenance
    # ------------------------------------------------------------------
    def get_customer(self, customer_id):
        """Fetch a customer by id (NotFoundError if absent)."""
        return self._customers.get(customer_id)

    def find_by_email(self, email):
        """Look up a customer by email (NotFoundError if absent)."""
        return self._customers.find_by_email(self._normalise_email(email))

    def add_address(self, customer_id, address):
        """Append an address to a customer's address book.

        The first address in the list remains the primary; newly added
        addresses are selectable at order time via ``address_index``.
        Returns the updated customer.
        """
        if not isinstance(address, Address):
            raise ValidationError("address must be an Address instance")
        customer = self._customers.get(customer_id)
        customer.addresses.append(address)
        self._customers.update(customer)
        logger.debug(
            "customer %s now has %d addresses", customer_id, len(customer.addresses)
        )
        return customer

    def set_loyalty_tier(self, customer_id, tier):
        """Change a customer's loyalty tier.

        The tier must be one of :data:`VALID_TIERS`; anything else is a
        :class:`ValidationError`.  Tier changes take effect on the next
        pricing quote (see ``PricingService.apply_tier_adjustment``).
        Returns the updated customer.
        """
        if tier not in VALID_TIERS:
            raise ValidationError(
                "invalid loyalty tier %r; expected one of %s"
                % (tier, ", ".join(VALID_TIERS))
            )
        customer = self._customers.get(customer_id)
        customer.loyalty_tier = tier
        self._customers.update(customer)
        logger.info("customer %s moved to %s tier", customer_id, tier)
        return customer

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_email(email):
        """Lowercase and strip an email, rejecting obviously bad input.

        This is intentionally not a full RFC 5322 validation -- just a
        pragmatic "looks like an email" check (single ``@`` with a dot
        in the domain part).
        """
        if not email or not email.strip():
            raise ValidationError("email must not be blank")
        candidate = email.strip().lower()
        local, sep, domain = candidate.partition("@")
        if not sep or not local or "." not in domain:
            raise ValidationError("invalid email address: %r" % (email,))
        return candidate
