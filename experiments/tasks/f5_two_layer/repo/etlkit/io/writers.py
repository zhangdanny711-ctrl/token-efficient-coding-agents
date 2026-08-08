"""Output writers.

Values that json can't serialize natively (Decimal, date) are rendered
as strings, matching the storefront convention of JSON-safe payloads.
"""

import csv
import datetime
import json
import os
from decimal import Decimal

from ..errors import LoadError


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _clean(record):
    """Drop bookkeeping keys and coerce values for output."""
    return {
        key: _jsonable(value)
        for key, value in record.items()
        if not key.startswith("_")
    }


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_records(path, fmt, records):
    """Write records to `path` in `fmt`; returns the number written."""
    _ensure_parent(path)
    if fmt == "jsonl":
        return _write_jsonl(path, records)
    if fmt == "csv":
        return _write_csv(path, records)
    raise LoadError("no writer for format %r" % fmt)


def _write_jsonl(path, records):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(_clean(record), sort_keys=True) + "\n")
    except OSError as exc:
        raise LoadError("could not write %s: %s" % (path, exc))
    return len(records)


def _write_csv(path, records):
    if not records:
        # still create the file so downstream jobs see an empty target
        _ensure_parent(path)
        open(path, "w", encoding="utf-8").close()
        return 0
    fieldnames = sorted({key for r in records for key in _clean(r)})
    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow({k: _jsonable(v) for k, v in _clean(record).items()})
    except (OSError, csv.Error) as exc:
        raise LoadError("could not write %s: %s" % (path, exc))
    return len(records)


def write_rejects(path, rejects):
    """Write reject entries as JSONL; returns the number written."""
    _ensure_parent(path)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            for entry in rejects:
                row = dict(entry)
                row["record"] = _clean(row.get("record", {}))
                fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    except OSError as exc:
        raise LoadError("could not write rejects %s: %s" % (path, exc))
    return len(rejects)
