"""Input readers.

Both readers return a list of dicts with string keys. CSV headers are
normalized to snake_case on the way in (see utils.text.normalize_header)
so specs can always refer to fields in one canonical spelling.
"""

import csv
import json
import os

from ..errors import ExtractError
from ..utils.text import normalize_header


def read_records(path, fmt):
    """Dispatch to the reader for `fmt`."""
    if not os.path.exists(path):
        raise ExtractError("source file not found: %s" % path)
    if fmt == "csv":
        return read_csv(path)
    if fmt == "jsonl":
        return read_jsonl(path)
    raise ExtractError("no reader for format %r" % fmt)


def read_csv(path):
    """Read a CSV file into a list of dicts, normalizing headers."""
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        raise ExtractError("could not read CSV %s: %s" % (path, exc))

    if not rows:
        raise ExtractError("CSV %s is empty (no header row)" % path)

    header = [normalize_header(h) for h in rows[0]]
    seen = set()
    for name in header:
        if not name:
            raise ExtractError("CSV %s has a blank column header" % path)
        if name in seen:
            raise ExtractError(
                "CSV %s has duplicate column %r after normalization" % (path, name)
            )
        seen.add(name)

    records = []
    for lineno, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip fully blank lines
        if len(row) != len(header):
            raise ExtractError(
                "CSV %s line %d has %d cells, expected %d"
                % (path, lineno, len(row), len(header))
            )
        record = dict(zip(header, (cell.strip() for cell in row)))
        record["_line"] = lineno
        records.append(record)
    return records


def read_jsonl(path):
    """Read a JSON-lines file into a list of dicts."""
    records = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ExtractError(
                        "JSONL %s line %d is not valid JSON: %s" % (path, lineno, exc)
                    )
                if not isinstance(obj, dict):
                    raise ExtractError(
                        "JSONL %s line %d is not an object" % (path, lineno)
                    )
                obj["_line"] = lineno
                records.append(obj)
    except OSError as exc:
        raise ExtractError("could not read JSONL %s: %s" % (path, exc))
    return records
