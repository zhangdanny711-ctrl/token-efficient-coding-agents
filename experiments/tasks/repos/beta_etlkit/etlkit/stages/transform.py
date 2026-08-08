"""Transform stage: apply the spec's ops in order to each record.

Ops mutate a copy of the record; the first failing op rejects the
record, and later ops never see it. Field-level errors (RecordError,
ValueError, KeyError) become rejects; anything else is a stage bug and
propagates as a fatal error.
"""

from ..contracts import ensure_batch, make_reject, stamp
from ..errors import RecordError
from ..ops import OPS
from ..utils.text import pluralize, truncate

STAGE = "transform"


def run_transform(spec, batch, log):
    ensure_batch(batch, expected_stage="validate")
    log.banner(STAGE, "TRANSFORM")
    ops = spec["ops"]
    if not ops:
        log.info(STAGE, "no ops configured, passing batch through")
        return stamp(batch, STAGE)

    for op in ops:
        log.info(STAGE, "op: %s on %r" % (op["op"], op.get("field")))

    survivors = []
    for record in batch["records"]:
        line = record.get("_line", "?")
        working = dict(record)
        error = None
        for op in ops:
            op_fn = OPS[op["op"]]
            try:
                working = op_fn(working, op)
            except (RecordError, ValueError, KeyError) as exc:
                error = (op, exc)
                break
        if error is None:
            changed = [
                k for k in working
                if k not in record or working[k] != record[k]
            ]
            log.debug(
                STAGE,
                "line %s: %s"
                % (
                    line,
                    "updated " + ", ".join(sorted(changed)) if changed else "unchanged",
                ),
            )
            survivors.append(working)
        else:
            op, exc = error
            field = getattr(exc, "field", None) or op.get("field")
            log.warning(
                STAGE,
                "line %s rejected by op %s: %s" % (line, op["op"], truncate(exc, 80)),
            )
            batch["rejects"].append(make_reject(record, STAGE, str(exc), field=field))

    batch["records"] = survivors
    batch["meta"]["ops_run"] = len(ops)
    log.info(STAGE, "transformed %s" % pluralize(len(survivors), "record"))
    return stamp(batch, STAGE)
