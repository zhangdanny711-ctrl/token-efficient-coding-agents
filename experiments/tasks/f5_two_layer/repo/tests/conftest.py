import io
import json

import pytest

from etlkit.utils.log import RunLog


@pytest.fixture
def log():
    """A RunLog writing to an in-memory buffer; .getvalue() via log.stream."""
    return RunLog(stream=io.StringIO())


@pytest.fixture
def quiet_log():
    return RunLog(stream=io.StringIO(), verbose=False)


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(",".join(header) + "\n")
        for row in rows:
            fh.write(",".join(str(c) for c in row) + "\n")
    return str(path)


def write_spec(path, spec):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    return str(path)


@pytest.fixture
def orders_dir(tmp_path):
    """A tiny self-contained job: 4 good rows, 1 bad quantity."""
    write_csv(
        tmp_path / "orders.csv",
        ["Order ID", "Customer Name", "Quantity", "Unit Price"],
        [
            [1, "Ada Byron", 2, "10.00"],
            [2, "Grace Field", 1, "5.50"],
            [3, "Mary Post", "oops", "3.00"],
            [4, "Jean Hall", 4, "2.25"],
            [5, "Kay Antonelli", 3, "8.00"],
        ],
    )
    spec = {
        "job": "orders_mini",
        "source": {"path": "orders.csv", "format": "csv"},
        "checks": [
            {"rule": "required", "field": "order_id"},
            {"rule": "type", "field": "quantity", "type": "int"},
        ],
        "ops": [
            {"op": "cast", "field": "quantity", "to": "int"},
            {"op": "cast", "field": "unit_price", "to": "decimal"},
            {
                "op": "derive",
                "field": "total",
                "formula": "multiply",
                "args": ["quantity", "unit_price"],
            },
        ],
        "target": {"path": "out/orders.jsonl", "format": "jsonl"},
        "rejects": {"path": "out/orders.rejects.jsonl"},
        "options": {"verbose": False},
    }
    write_spec(tmp_path / "orders.spec.json", spec)
    return tmp_path
