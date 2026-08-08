"""Load stage: write survivors to the target and rejects to the reject file.

Before writing, the reject-rate guard runs: if more than
options.reject_limit_pct of the *input* records were rejected, the load
aborts with LoadError — a mostly-rejected batch nearly always means a
wrong spec, and loading the few survivors would mask it.
"""

from ..contracts import counts, ensure_batch, stamp
from ..errors import LoadError
from ..io import write_records, write_rejects
from ..spec import resolve_path
from ..utils.numbers import percent
from ..utils.text import pluralize

STAGE = "load"


def run_load(spec, batch, log):
    ensure_batch(batch, expected_stage="transform")
    log.banner(STAGE, "LOAD")

    got = counts(batch)
    total_in = got["records"] + got["rejects"]
    reject_pct = percent(got["rejects"], total_in)
    limit = spec["options"]["reject_limit_pct"]
    log.info(
        STAGE,
        "reject rate %.1f%% (%d of %d), limit %s%%"
        % (reject_pct, got["rejects"], total_in, limit),
    )
    if reject_pct > limit:
        raise LoadError(
            "reject rate %.1f%% exceeds limit %s%% — refusing to load"
            % (reject_pct, limit)
        )

    target = spec["target"]
    target_path = resolve_path(spec, target["path"])
    written = write_records(target_path, target["format"], batch["records"])
    log.info(
        STAGE,
        "wrote %s to %s" % (pluralize(written, "record"), target_path),
    )

    if spec["rejects"]:
        reject_path = resolve_path(spec, spec["rejects"]["path"])
        write_rejects(reject_path, batch["rejects"])
        log.info(
            STAGE,
            "wrote %s to %s"
            % (pluralize(len(batch["rejects"]), "reject entry", "reject entries"),
               reject_path),
        )
    elif batch["rejects"]:
        log.warning(
            STAGE,
            "%s discarded (no rejects path configured)"
            % pluralize(len(batch["rejects"]), "reject entry", "reject entries"),
        )

    batch["meta"]["written"] = written
    batch["meta"]["target_path"] = target_path
    return stamp(batch, STAGE)
