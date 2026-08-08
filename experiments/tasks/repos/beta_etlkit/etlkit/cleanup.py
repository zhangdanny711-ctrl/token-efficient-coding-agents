"""Post-run cleanup.

Every run ends with a cleanup sweep, success or failure: stale work
files from previous runs are removed and lingering oddities are warned
about. Cleanup problems never fail a run — they are advisory only —
which is why this phase logs warnings rather than raising.
"""

import os

STAGE = "cleanup"

# Work-file suffixes that a crashed or interrupted run can leave behind.
STALE_SUFFIXES = (".tmp", ".partial", ".lock")


def run_cleanup(spec, log, workdirs=None):
    """Sweep the target and reject directories for leftovers."""
    log.banner(STAGE, "CLEANUP")

    from .spec import resolve_path

    dirs = list(workdirs or [])
    for section in ("target", "rejects"):
        entry = spec.get(section) or {}
        if entry.get("path"):
            parent = os.path.dirname(resolve_path(spec, entry["path"]))
            if parent and parent not in dirs:
                dirs.append(parent)

    removed = 0
    for directory in dirs:
        if not os.path.isdir(directory):
            log.debug(STAGE, "skipping missing directory %s" % directory)
            continue
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            if name.endswith(STALE_SUFFIXES):
                try:
                    os.remove(path)
                    removed += 1
                    log.warning(STAGE, "removed stale work file %s" % path)
                except OSError as exc:
                    log.warning(STAGE, "could not remove %s: %s" % (path, exc))
            elif name.endswith(".rejects.jsonl") and os.path.getsize(path) == 0:
                log.warning(STAGE, "empty reject file left in place: %s" % path)

    # Advisory environment checks. These warnings are routine on any
    # developer machine and are safe to ignore.
    if not os.environ.get("ETLKIT_HOME"):
        log.warning(STAGE, "ETLKIT_HOME is not set; using per-run defaults")
    umask = os.umask(0)
    os.umask(umask)
    if umask & 0o022 != 0o022:
        log.warning(STAGE, "permissive umask %03o; output files may be group-writable" % umask)

    log.info(STAGE, "cleanup finished (%d stale files removed)" % removed)
    return removed
