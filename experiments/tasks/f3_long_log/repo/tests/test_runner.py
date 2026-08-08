import io
import json

from etlkit.runner import run_job

from .conftest import write_csv, write_spec


def run_to_string(spec_path):
    stream = io.StringIO()
    code = run_job(str(spec_path), stream=stream)
    return code, stream.getvalue()


class TestRunJob:
    def test_degraded_run(self, orders_dir):
        code, log = run_to_string(orders_dir / "orders.spec.json")
        assert code == 0
        assert "status: DEGRADED" in log
        out = (orders_dir / "out" / "orders.jsonl").read_text().strip().splitlines()
        assert len(out) == 4
        rejects = (orders_dir / "out" / "orders.rejects.jsonl").read_text().splitlines()
        assert len(rejects) == 1
        assert json.loads(rejects[0])["record"]["quantity"] == "oops"

    def test_clean_run_is_ok(self, tmp_path):
        write_csv(tmp_path / "in.csv", ["A"], [[1], [2]])
        write_spec(
            tmp_path / "job.json",
            {
                "job": "clean",
                "source": {"path": "in.csv"},
                "target": {"path": "out/x.jsonl", "format": "jsonl"},
                "options": {"verbose": False},
            },
        )
        code, log = run_to_string(tmp_path / "job.json")
        assert code == 0
        assert "status: OK" in log
        assert "records loaded: 2" in log

    def test_totals_are_consistent(self, orders_dir):
        code, log = run_to_string(orders_dir / "orders.spec.json")
        assert "records in: 5" in log
        assert "records loaded: 4" in log
        assert "records rejected: 1" in log

    def test_derived_totals_correct(self, orders_dir):
        run_to_string(orders_dir / "orders.spec.json")
        rows = [
            json.loads(line)
            for line in (orders_dir / "out" / "orders.jsonl").read_text().splitlines()
        ]
        by_id = {row["order_id"]: row for row in rows}
        assert by_id["1"]["total"] == "20.00"
        assert by_id["5"]["total"] == "24.00"

    def test_broken_spec_fails(self, tmp_path):
        write_spec(tmp_path / "bad.json", {"job": "x"})
        code, log = run_to_string(tmp_path / "bad.json")
        assert code == 2
        assert "status: FAILED" in log

    def test_missing_source_fails_but_reports(self, tmp_path):
        write_spec(
            tmp_path / "job.json",
            {
                "job": "gone",
                "source": {"path": "nope.csv"},
                "target": {"path": "out/x.jsonl", "format": "jsonl"},
                "options": {"verbose": False},
            },
        )
        code, log = run_to_string(tmp_path / "job.json")
        assert code == 2
        assert "source file not found" in log
        assert "status: FAILED" in log
        # the summary block still runs on fatal errors
        assert "SUMMARY" in log

    def test_reject_limit_fails_run(self, tmp_path):
        write_csv(tmp_path / "in.csv", ["Q"], [["x"], ["y"], [1]])
        write_spec(
            tmp_path / "job.json",
            {
                "job": "limited",
                "source": {"path": "in.csv"},
                "checks": [{"rule": "type", "field": "q", "type": "int"}],
                "target": {"path": "out/x.jsonl", "format": "jsonl"},
                "options": {"verbose": False, "reject_limit_pct": 25},
            },
        )
        code, log = run_to_string(tmp_path / "job.json")
        assert code == 2
        assert "refusing to load" in log
