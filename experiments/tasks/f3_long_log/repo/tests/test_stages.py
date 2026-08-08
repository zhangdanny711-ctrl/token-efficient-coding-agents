import pytest

from etlkit.contracts import make_batch, stamp
from etlkit.errors import EtlError, LoadError
from etlkit.spec import validate_spec
from etlkit.stages import run_extract, run_load, run_transform, run_validate

from .conftest import write_csv


def spec_for(tmp_path, **overrides):
    base = {
        "job": "t",
        "source": {"path": "in.csv", "format": "csv"},
        "target": {"path": "out/out.jsonl", "format": "jsonl"},
        "options": {"verbose": False},
    }
    base.update(overrides)
    return validate_spec(base, base_dir=str(tmp_path))


class TestExtract:
    def test_reads_and_stamps(self, tmp_path, quiet_log):
        write_csv(tmp_path / "in.csv", ["A", "B"], [[1, 2], [3, 4]])
        batch = run_extract(spec_for(tmp_path), quiet_log)
        assert batch["stage"] == "extract"
        assert len(batch["records"]) == 2
        assert batch["records"][0]["a"] == "1"


class TestValidate:
    def test_partitions_records(self, tmp_path, quiet_log):
        spec = spec_for(
            tmp_path,
            checks=[{"rule": "type", "field": "q", "type": "int"}],
        )
        batch = stamp(make_batch("t", records=[{"q": "1"}, {"q": "x"}]), "extract")
        batch = run_validate(spec, batch, quiet_log)
        assert len(batch["records"]) == 1
        assert len(batch["rejects"]) == 1
        assert batch["rejects"][0]["stage"] == "validate"

    def test_requires_extract_batch(self, tmp_path, quiet_log):
        spec = spec_for(tmp_path)
        batch = make_batch("t")  # still stage=init
        with pytest.raises(EtlError, match="expected a batch from stage"):
            run_validate(spec, batch, quiet_log)

    def test_first_failing_check_wins(self, tmp_path, quiet_log):
        spec = spec_for(
            tmp_path,
            checks=[
                {"rule": "required", "field": "a"},
                {"rule": "required", "field": "b"},
            ],
        )
        batch = stamp(make_batch("t", records=[{}]), "extract")
        batch = run_validate(spec, batch, quiet_log)
        assert "'a'" in batch["rejects"][0]["reason"]


class TestTransform:
    def test_applies_ops_in_order(self, tmp_path, quiet_log):
        spec = spec_for(
            tmp_path,
            ops=[
                {"op": "cast", "field": "q", "to": "int"},
                {"op": "rename", "field": "q", "to": "quantity"},
            ],
        )
        batch = stamp(make_batch("t", records=[{"q": "3"}]), "validate")
        batch = run_transform(spec, batch, quiet_log)
        assert batch["records"][0]["quantity"] == 3

    def test_failing_record_rejected_others_survive(self, tmp_path, quiet_log):
        spec = spec_for(tmp_path, ops=[{"op": "cast", "field": "q", "to": "int"}])
        batch = stamp(make_batch("t", records=[{"q": "1"}, {"q": "x"}]), "validate")
        batch = run_transform(spec, batch, quiet_log)
        assert len(batch["records"]) == 1
        assert batch["rejects"][0]["stage"] == "transform"

    def test_original_record_kept_in_reject(self, tmp_path, quiet_log):
        spec = spec_for(
            tmp_path,
            ops=[
                {"op": "rename", "field": "q", "to": "quantity"},
                {"op": "cast", "field": "quantity", "to": "int"},
            ],
        )
        batch = stamp(make_batch("t", records=[{"q": "x"}]), "validate")
        batch = run_transform(spec, batch, quiet_log)
        # reject carries the pre-transform record, not the half-mutated copy
        assert batch["rejects"][0]["record"] == {"q": "x"}


class TestLoad:
    def test_writes_target_and_rejects(self, tmp_path, quiet_log):
        spec = spec_for(tmp_path, rejects={"path": "out/r.jsonl"})
        batch = stamp(
            make_batch("t", records=[{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]),
            "transform",
        )
        batch["rejects"].append(
            {"record": {}, "stage": "validate", "reason": "x", "field": None}
        )
        batch = run_load(spec, batch, quiet_log)
        assert (tmp_path / "out" / "out.jsonl").exists()
        assert (tmp_path / "out" / "r.jsonl").exists()
        assert batch["meta"]["written"] == 4

    def test_reject_limit_aborts(self, tmp_path, quiet_log):
        spec = spec_for(tmp_path, options={"verbose": False, "reject_limit_pct": 25})
        batch = stamp(make_batch("t", records=[{"a": 1}]), "transform")
        for _ in range(3):
            batch["rejects"].append(
                {"record": {}, "stage": "validate", "reason": "x", "field": None}
            )
        with pytest.raises(LoadError, match="exceeds limit"):
            run_load(spec, batch, quiet_log)
        assert not (tmp_path / "out" / "out.jsonl").exists()
