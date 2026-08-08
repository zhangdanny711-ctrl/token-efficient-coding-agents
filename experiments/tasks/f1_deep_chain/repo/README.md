# storefront

An internal training codebase: a small but complete e-commerce backend
written in pure Python (standard library only). It models a catalog,
carts, checkout, order fulfilment, customer accounts, and reporting,
behind an HTTP-style API layer that is dispatched in-process rather
than over a socket.

The codebase is intentionally framework-free so that every layer —
routing, validation, persistence, money handling — is plain Python you
can read end to end.

## Architecture

Requests flow top-down; nothing lower in the stack imports anything
above it.

```
api  ->  services  ->  domain
              \->  persistence
```

- **api** builds `Request` objects, routes them through a route table,
  and translates domain errors into status codes. Handlers validate
  input and serialize results; they contain no business rules.
- **services** own the business workflows (checkout, payment, stock
  reservation, refunds) and coordinate repositories.
- **domain** holds the entities (`Product`, `Cart`, `Order`,
  `Customer`, ...), value objects such as `Money` and `Address`, and
  the error hierarchy.
- **persistence** provides the in-memory `Store`, typed repositories,
  and JSON-safe serializers.
- **utils** contains cross-cutting helpers (logging, ids, clocks).

## Layers

| Layer                    | Package                  | Responsibility                                |
| ------------------------ | ------------------------ | --------------------------------------------- |
| API                      | `storefront.api`         | Routing, request/response, error mapping      |
| Services                 | `storefront.services`    | Business workflows and orchestration          |
| Domain                   | `storefront.domain`      | Entities, value objects, domain errors        |
| Persistence              | `storefront.persistence` | In-memory store, repositories, serializers    |
| Utilities                | `storefront.utils`       | Logging and shared helpers                    |

## Module inventory

- `storefront/api/app.py` — `Api` front controller and route table
- `storefront/api/request.py`, `response.py` — request/response types
- `storefront/api/errors.py` — exception-to-status mapping
- `storefront/api/middleware.py` — error handling and logging wrappers
- `storefront/api/handlers/` — one module per resource: `products`,
  `carts`, `orders`, `customers`, `reports`
- `storefront/services/` — `CatalogService`, `CartService`,
  `OrderService`, `CustomerService`, `ReportsService`
- `storefront/domain/` — models and errors
- `storefront/persistence/` — store, repositories, serializers
- `storefront/utils/` — logging and helpers

## Running the tests

From the repository root:

```
python3 -m pytest tests/ -q
```

The suite exercises the API layer through `Api.dispatch`, so it covers
routing, validation, and the service workflows together. No third-party
packages are required beyond `pytest` itself.

## Conventions

- Money is handled with `decimal.Decimal`; serializers emit amounts as
  strings to keep payloads JSON-safe.
- Domain errors map to statuses at the API boundary: validation and
  discount problems are 400, missing entities 404, and state conflicts
  (out of stock, illegal transitions) 409.
- Handlers follow the signature `handler(service, request) -> Response`
  and never reach around their bound service.
