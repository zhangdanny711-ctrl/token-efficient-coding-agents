import subprocess
import sys

from .conftest import write_csv, write_spec


def run_cli(*argv, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "etlkit", *argv],
        capture_output=True, text=True, cwd=cwd,
    )


def make_job(tmp_path):
    write_csv(tmp_path / "in.csv", ["A"], [[1]])
    return write_spec(
        tmp_path / "job.json",
        {
            "job": "cli",
            "source": {"path": "in.csv"},
            "target": {"path": "out/x.jsonl", "format": "jsonl"},
            "options": {"verbose": False},
        },
    )


class TestCli:
    def test_run_ok(self, tmp_path):
        spec = make_job(tmp_path)
        proc = run_cli("run", spec)
        assert proc.returncode == 0
        assert "status: OK" in proc.stdout

    def test_check_ok(self, tmp_path):
        spec = make_job(tmp_path)
        proc = run_cli("check", spec)
        assert proc.returncode == 0
        assert "spec ok" in proc.stdout

    def test_check_bad_spec(self, tmp_path):
        path = write_spec(tmp_path / "bad.json", {"job": "x"})
        proc = run_cli("check", path)
        assert proc.returncode == 2
        assert "spec error" in proc.stderr

    def test_run_missing_spec(self, tmp_path):
        proc = run_cli("run", str(tmp_path / "nope.json"))
        assert proc.returncode == 2
