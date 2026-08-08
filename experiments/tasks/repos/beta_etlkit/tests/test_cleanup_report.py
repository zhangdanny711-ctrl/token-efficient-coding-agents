import io

from etlkit.cleanup import run_cleanup
from etlkit.contracts import make_batch
from etlkit.report import status_of, write_report
from etlkit.spec import validate_spec


def spec_for(tmp_path):
    return validate_spec(
        {
            "job": "t",
            "source": {"path": "in.csv"},
            "target": {"path": "out/x.jsonl", "format": "jsonl"},
            "rejects": {"path": "out/x.rejects.jsonl"},
            "options": {"verbose": False},
        },
        base_dir=str(tmp_path),
    )


class TestCleanup:
    def test_removes_stale_work_files(self, tmp_path, quiet_log):
        out = tmp_path / "out"
        out.mkdir()
        (out / "old.tmp").write_text("x")
        (out / "old.partial").write_text("x")
        (out / "keep.jsonl").write_text("x")
        removed = run_cleanup(spec_for(tmp_path), quiet_log)
        assert removed == 2
        assert (out / "keep.jsonl").exists()

    def test_missing_dir_is_fine(self, tmp_path, quiet_log):
        assert run_cleanup(spec_for(tmp_path), quiet_log) == 0

    def test_warns_on_empty_reject_file(self, tmp_path):
        from etlkit.utils.log import RunLog

        out = tmp_path / "out"
        out.mkdir()
        (out / "x.rejects.jsonl").write_text("")
        stream = io.StringIO()
        run_cleanup(spec_for(tmp_path), RunLog(stream=stream, verbose=False))
        assert "empty reject file" in stream.getvalue()


class TestReport:
    def test_status_of(self):
        clean = make_batch("j")
        assert status_of(clean) == "OK"
        degraded = make_batch("j")
        degraded["rejects"].append({"stage": "validate"})
        assert status_of(degraded) == "DEGRADED"
        assert status_of(None, fatal=ValueError("x")) == "FAILED"

    def test_write_report_counts(self, tmp_path, quiet_log):
        spec = spec_for(tmp_path)
        batch = make_batch("t")
        batch["meta"]["written"] = 3
        batch["rejects"] = [
            {"stage": "validate"},
            {"stage": "transform"},
            {"stage": "validate"},
        ]
        status = write_report(spec, batch, quiet_log)
        assert status == "DEGRADED"
        text = quiet_log.stream.getvalue()
        assert "records in: 6" in text
        assert "rejected in validate: 2" in text
        assert "rejected in transform: 1" in text
