"""The batch contract shared by all stages.

A *batch* is the single value handed from stage to stage. It is a plain
dict so that logs, tests, and debugging sessions can inspect it without
any class machinery:

    {
        "job":     str,          # job name from the spec
        "stage":   str,          # last stage that touched the batch
        "records": [dict, ...],  # surviving records, in input order
        "rejects": [dict, ...],  # reject entries (see make_reject)
        "meta":    dict,         # stage-specific bookkeeping
    }

Stages must go through `stamp` when passing a batch on, and may use
`ensure_batch` at their entry point to fail loudly on a malformed
hand-off rather than corrupting downstream state.
"""

from .errors import EtlError

BATCH_KEYS = ("job", "stage", "records", "rejects", "meta")


def make_batch(job, records=None, meta=None):
    """Create a fresh batch at the start of a run."""
    return {
        "job": job,
        "stage": "init",
        "records": list(records or []),
        "rejects": [],
        "meta": dict(meta or {}),
    }


def ensure_batch(batch, expected_stage=None):
    """Assert that `batch` matches the contract; return it unchanged.

    Raises EtlError (fatal) on violation: a malformed batch means a
    stage bug, not bad data, so it must never be routed to rejects.
    """
    if not isinstance(batch, dict):
        raise EtlError("batch must be a dict, got %s" % type(batch).__name__)
    missing = [key for key in BATCH_KEYS if key not in batch]
    if missing:
        raise EtlError("batch is missing keys: %s" % ", ".join(missing))
    if not isinstance(batch["records"], list):
        raise EtlError("batch['records'] must be a list")
    if not isinstance(batch["rejects"], list):
        raise EtlError("batch['rejects'] must be a list")
    if expected_stage is not None and batch["stage"] != expected_stage:
        raise EtlError(
            "expected a batch from stage %r, got one from %r"
            % (expected_stage, batch["stage"])
        )
    return batch


def stamp(batch, stage):
    """Mark the batch as having passed through `stage`."""
    batch["stage"] = stage
    return batch


def make_reject(record, stage, reason, field=None):
    """Build one reject entry.

    The original record is kept whole so the reject file is enough to
    replay or hand-correct failed rows.
    """
    return {
        "record": dict(record),
        "stage": stage,
        "reason": str(reason),
        "field": field,
    }


def counts(batch):
    """Convenience summary used by logs and the final report."""
    return {
        "records": len(batch["records"]),
        "rejects": len(batch["rejects"]),
    }
