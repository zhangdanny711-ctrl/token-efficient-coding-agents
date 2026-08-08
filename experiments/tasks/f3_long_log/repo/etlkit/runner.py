"""The run orchestrator.

`run_job` executes the fixed stage chain against one spec:

    extract -> validate -> transform -> load -> (cleanup) -> report

Per-record problems are already absorbed by the stages (they become
rejects); what reaches this level is only fatal: a broken spec, an
unreadable source, a contract violation between stages, or an aborted
load. On fatal errors the run is marked FAILED but cleanup and the
report still execute, so the log always ends with the same summary
block regardless of outcome.
"""

from .cleanup import run_cleanup
from .errors import EtlError
from .report import write_report
from .spec import load_spec
from .stages import run_extract, run_load, run_transform, run_validate
from .utils.log import RunLog


def run_job(spec_path, stream=None):
    """Run the job described by `spec_path`.

    Returns an exit code: 0 for OK or DEGRADED, 2 for FAILED,
    matching the CLI contract.
    """
    log = RunLog(stream=stream)
    try:
        spec = load_spec(spec_path)
    except EtlError as exc:
        log.error("spec", str(exc))
        log.info("report", "status: FAILED")
        return 2

    log.verbose = bool(spec["options"].get("verbose", True))
    log.info("run", "etlkit starting job %r from %s" % (spec["job"], spec_path))

    batch = None
    fatal = None
    try:
        batch = run_extract(spec, log)
        batch = run_validate(spec, batch, log)
        batch = run_transform(spec, batch, log)
        batch = run_load(spec, batch, log)
    except EtlError as exc:
        fatal = exc
        log.error(batch["stage"] if batch else "extract", str(exc))

    run_cleanup(spec, log)
    status = write_report(spec, batch, log, fatal=fatal)
    return 0 if status in ("OK", "DEGRADED") else 2
