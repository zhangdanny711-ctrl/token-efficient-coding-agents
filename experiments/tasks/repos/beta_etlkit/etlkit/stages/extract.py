"""Extract stage: read the source file into a fresh batch."""

from ..contracts import make_batch, stamp
from ..io import read_records
from ..spec import resolve_path
from ..utils.text import pluralize, truncate

STAGE = "extract"


def run_extract(spec, log):
    """Read the source and return the initial batch."""
    src = spec["source"]
    path = resolve_path(spec, src["path"])
    log.banner(STAGE, "EXTRACT")
    log.info(STAGE, "reading %s (%s)" % (path, src["format"]))

    records = read_records(path, src["format"])

    for record in records:
        preview = ", ".join(
            "%s=%s" % (k, truncate(v, 18))
            for k, v in list(record.items())[:4]
            if not k.startswith("_")
        )
        log.debug(STAGE, "line %s: %s" % (record.get("_line", "?"), preview))

    if records:
        fields = sorted(k for k in records[0] if not k.startswith("_"))
        log.info(STAGE, "detected fields: %s" % ", ".join(fields))

    batch = make_batch(spec["job"], records=records, meta={"source_path": path})
    log.info(STAGE, "extracted %s" % pluralize(len(records), "record"))
    return stamp(batch, STAGE)
