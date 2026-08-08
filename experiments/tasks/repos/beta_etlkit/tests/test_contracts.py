import pytest

from etlkit.contracts import (
    counts,
    ensure_batch,
    make_batch,
    make_reject,
    stamp,
)
from etlkit.errors import EtlError


def test_make_batch_shape():
    batch = make_batch("job1", records=[{"a": 1}])
    assert batch["job"] == "job1"
    assert batch["stage"] == "init"
    assert batch["records"] == [{"a": 1}]
    assert batch["rejects"] == []
    assert batch["meta"] == {}


def test_make_batch_copies_inputs():
    records = [{"a": 1}]
    batch = make_batch("job1", records=records)
    records.append({"b": 2})
    assert len(batch["records"]) == 1


def test_ensure_batch_accepts_valid():
    batch = make_batch("j")
    assert ensure_batch(batch) is batch


def test_ensure_batch_rejects_non_dict():
    with pytest.raises(EtlError, match="must be a dict"):
        ensure_batch([])


def test_ensure_batch_rejects_missing_keys():
    with pytest.raises(EtlError, match="missing keys"):
        ensure_batch({"job": "j"})


def test_ensure_batch_checks_stage():
    batch = stamp(make_batch("j"), "extract")
    ensure_batch(batch, expected_stage="extract")
    with pytest.raises(EtlError, match="expected a batch from stage"):
        ensure_batch(batch, expected_stage="validate")


def test_stamp_sets_stage():
    batch = make_batch("j")
    assert stamp(batch, "validate")["stage"] == "validate"


def test_make_reject_copies_record():
    record = {"a": 1}
    entry = make_reject(record, "validate", "bad", field="a")
    record["a"] = 2
    assert entry["record"] == {"a": 1}
    assert entry["stage"] == "validate"
    assert entry["reason"] == "bad"
    assert entry["field"] == "a"


def test_counts():
    batch = make_batch("j", records=[{}, {}])
    batch["rejects"].append(make_reject({}, "validate", "x"))
    assert counts(batch) == {"records": 2, "rejects": 1}
