"""End-to-end run over the shipped sample job.

These tests pin the expected outcome of `samples/orders_july.spec.json`
so refactors to any stage can be checked against a realistic job. The
sample files are copied into a tmp dir first so runs never dirty the
repo.
"""

import io
import json
import shutil
from pathlib import Path

import pytest

from etlkit.runner import run_job

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def sample_run(tmp_path):
    shutil.copy(SAMPLES / "orders_july.csv", tmp_path / "orders_july.csv")
    shutil.copy(SAMPLES / "orders_july.spec.json", tmp_path / "orders_july.spec.json")
    stream = io.StringIO()
    code = run_job(str(tmp_path / "orders_july.spec.json"), stream=stream)
    return tmp_path, code, stream.getvalue()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_sample_job_completes(sample_run):
    _, code, log = sample_run
    assert code == 0
    assert "status: DEGRADED" in log


def test_sample_job_counts(sample_run):
    tmp_path, _, log = sample_run
    rows = load_rows(tmp_path / "out" / "orders_july.jsonl")
    rejects = load_rows(tmp_path / "out" / "orders_july.rejects.jsonl")
    # 75 input rows, of which exactly 5 are genuinely dirty
    assert len(rows) == 70
    assert len(rejects) == 5
    assert "records loaded: 70" in log


def test_premium_orders_are_loaded(sample_run):
    """LUX-5001 is the premium SKU; its orders must load like any other."""
    tmp_path, _, _ = sample_run
    rows = load_rows(tmp_path / "out" / "orders_july.jsonl")
    lux = [r for r in rows if r["sku"] == "LUX-5001"]
    assert len(lux) == 9
    assert all(r["unit_price"] == "1204.50" for r in lux)


def test_line_totals(sample_run):
    tmp_path, _, _ = sample_run
    rows = load_rows(tmp_path / "out" / "orders_july.jsonl")
    by_id = {r["order_id"]: r for r in rows}
    # spot-check one ordinary and one premium order
    assert by_id[70002]["line_total"] == "61.00"   # 4 x 15.25
    lux = [r for r in rows if r["sku"] == "LUX-5001"][0]
    expected = 1204.50 * int(lux["quantity"])
    assert lux["line_total"] == "%.2f" % expected
