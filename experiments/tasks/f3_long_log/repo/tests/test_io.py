import datetime
import json
from decimal import Decimal

import pytest

from etlkit.errors import ExtractError, LoadError
from etlkit.io import read_records, write_records, write_rejects
from etlkit.io.readers import read_csv, read_jsonl

from .conftest import write_csv


class TestReadCsv:
    def test_headers_normalized(self, tmp_path):
        path = write_csv(tmp_path / "a.csv", ["Order ID", "Unit Price"], [[1, "2.5"]])
        records = read_csv(path)
        assert records[0]["order_id"] == "1"
        assert records[0]["unit_price"] == "2.5"

    def test_line_numbers(self, tmp_path):
        path = write_csv(tmp_path / "a.csv", ["a"], [[1], [2]])
        records = read_csv(path)
        assert [r["_line"] for r in records] == [2, 3]

    def test_blank_lines_skipped(self, tmp_path):
        path = tmp_path / "a.csv"
        path.write_text("a,b\n1,2\n,\n3,4\n")
        assert len(read_csv(str(path))) == 2

    def test_ragged_row(self, tmp_path):
        path = tmp_path / "a.csv"
        path.write_text("a,b\n1\n")
        with pytest.raises(ExtractError, match="has 1 cells, expected 2"):
            read_csv(str(path))

    def test_duplicate_header(self, tmp_path):
        path = write_csv(tmp_path / "a.csv", ["Order ID", "order_id"], [[1, 2]])
        with pytest.raises(ExtractError, match="duplicate column"):
            read_csv(path)

    def test_empty_file(self, tmp_path):
        path = tmp_path / "a.csv"
        path.write_text("")
        with pytest.raises(ExtractError, match="empty"):
            read_csv(str(path))

    def test_missing_file(self, tmp_path):
        with pytest.raises(ExtractError, match="not found"):
            read_records(str(tmp_path / "nope.csv"), "csv")


class TestReadJsonl:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "a.jsonl"
        path.write_text('{"a": 1}\n\n{"a": 2}\n')
        records = read_jsonl(str(path))
        assert [r["a"] for r in records] == [1, 2]
        assert records[1]["_line"] == 3

    def test_bad_line(self, tmp_path):
        path = tmp_path / "a.jsonl"
        path.write_text('{"a": 1}\nnot json\n')
        with pytest.raises(ExtractError, match="line 2 is not valid JSON"):
            read_jsonl(str(path))

    def test_non_object_line(self, tmp_path):
        path = tmp_path / "a.jsonl"
        path.write_text("[1, 2]\n")
        with pytest.raises(ExtractError, match="not an object"):
            read_jsonl(str(path))


class TestWriters:
    def test_jsonl_strips_bookkeeping_and_stringifies(self, tmp_path):
        out = tmp_path / "out" / "x.jsonl"
        n = write_records(
            str(out), "jsonl",
            [{"amount": Decimal("2.50"), "date": datetime.date(2026, 7, 1), "_line": 2}],
        )
        assert n == 1
        row = json.loads(out.read_text())
        assert row == {"amount": "2.50", "date": "2026-07-01"}

    def test_csv_writer(self, tmp_path):
        out = tmp_path / "x.csv"
        write_records(str(out), "csv", [{"b": 1, "a": 2}])
        lines = out.read_text().strip().splitlines()
        assert lines[0] == "a,b"
        assert lines[1] == "2,1"

    def test_csv_empty_creates_file(self, tmp_path):
        out = tmp_path / "x.csv"
        assert write_records(str(out), "csv", []) == 0
        assert out.exists()

    def test_unknown_format(self, tmp_path):
        with pytest.raises(LoadError, match="no writer"):
            write_records(str(tmp_path / "x"), "xml", [])

    def test_write_rejects(self, tmp_path):
        out = tmp_path / "r.jsonl"
        n = write_rejects(
            str(out),
            [{"record": {"a": 1, "_line": 5}, "stage": "validate",
              "reason": "bad", "field": "a"}],
        )
        assert n == 1
        row = json.loads(out.read_text())
        assert row["record"] == {"a": 1}
        assert row["stage"] == "validate"
