"""Final run report.

The report is the machine-readable tail of the log: fixed-format lines
that CI jobs grep for, plus a one-word status.

    OK        every input record was loaded
    DEGRADED  the run completed but some records were rejected
    FAILED    a fatal error aborted the run
"""

STAGE = "report"


def status_of(batch, fatal=None):
    if fatal is not None:
        return "FAILED"
    if batch and batch["rejects"]:
        return "DEGRADED"
    return "OK"


def write_report(spec, batch, log, fatal=None):
    """Emit the summary block; returns the status string."""
    status = status_of(batch, fatal=fatal)
    log.banner(STAGE, "SUMMARY")
    log.info(STAGE, "job: %s" % spec["job"])

    if batch is not None:
        loaded = batch["meta"].get("written", 0)
        rejected = len(batch["rejects"])
        total = loaded + rejected
        log.info(STAGE, "records in: %d" % total)
        log.info(STAGE, "records loaded: %d" % loaded)
        log.info(STAGE, "records rejected: %d" % rejected)
        by_stage = {}
        for entry in batch["rejects"]:
            by_stage[entry["stage"]] = by_stage.get(entry["stage"], 0) + 1
        for stage in sorted(by_stage):
            log.info(STAGE, "  rejected in %s: %d" % (stage, by_stage[stage]))

    if fatal is not None:
        log.error(STAGE, "fatal: %s" % fatal)

    level_counts = log.summary_counts()
    log.info(
        STAGE,
        "log lines: %d info, %d warning, %d error"
        % (level_counts["INFO"], level_counts["WARNING"], level_counts["ERROR"]),
    )
    log.info(STAGE, "status: %s" % status)
    return status
