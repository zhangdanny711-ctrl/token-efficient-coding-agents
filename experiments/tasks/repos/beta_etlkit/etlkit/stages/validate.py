"""Validate stage: apply the spec's checks record by record.

A record failing any check goes to the reject pile with the rule name
and message; surviving records continue in input order. Check state
(e.g. `unique`'s seen-set) is scoped per check instance per run.
"""

from ..contracts import ensure_batch, make_reject, stamp
from ..errors import CheckFailure
from ..rules import RULES
from ..utils.text import pluralize

STAGE = "validate"


def run_validate(spec, batch, log):
    ensure_batch(batch, expected_stage="extract")
    log.banner(STAGE, "VALIDATE")
    checks = spec["checks"]
    if not checks:
        log.info(STAGE, "no checks configured, passing batch through")
        return stamp(batch, STAGE)

    for check in checks:
        log.info(
            STAGE,
            "check: %s on %r" % (check["rule"], check.get("field", check.get("fields"))),
        )

    states = [{} for _ in checks]
    survivors = []
    for record in batch["records"]:
        line = record.get("_line", "?")
        failed = None
        for check, state in zip(checks, states):
            rule_fn = RULES[check["rule"]]
            try:
                rule_fn(record, check, state)
            except CheckFailure as exc:
                failed = (check, exc)
                break
        if failed is None:
            log.debug(STAGE, "line %s: ok" % line)
            survivors.append(record)
        else:
            check, exc = failed
            log.warning(
                STAGE,
                "line %s rejected by %s: %s" % (line, check["rule"], exc),
            )
            batch["rejects"].append(
                make_reject(record, STAGE, str(exc), field=exc.field)
            )

    batch["records"] = survivors
    batch["meta"]["checks_run"] = len(checks)
    log.info(
        STAGE,
        "kept %s, rejected %s"
        % (
            pluralize(len(survivors), "record"),
            pluralize(len(batch["rejects"]), "record"),
        ),
    )
    return stamp(batch, STAGE)
