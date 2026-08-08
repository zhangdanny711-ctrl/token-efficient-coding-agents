"""Job spec loading and structural validation.

A job spec is a JSON document:

    {
        "job": "orders_daily",
        "source":   {"path": "samples/orders.csv", "format": "csv"},
        "schema":   {"order_id": "int", "amount": "decimal", ...},
        "checks":   [{"rule": "required", "field": "order_id"}, ...],
        "ops":      [{"op": "cast", "field": "amount", "to": "decimal"}, ...],
        "target":   {"path": "out/orders.jsonl", "format": "jsonl"},
        "rejects":  {"path": "out/orders.rejects.jsonl"},
        "options":  {"verbose": true, "reject_limit_pct": 25}
    }

`load_spec` reads and validates the document; every structural problem
is reported as SpecError before any data is touched.
"""

import json
import os

from .errors import SpecError

KNOWN_FORMATS = ("csv", "jsonl")
KNOWN_TYPES = ("str", "int", "decimal", "date", "bool")

REQUIRED_SECTIONS = ("job", "source", "target")

DEFAULT_OPTIONS = {
    "verbose": True,
    # Abort the load if more than this share of input records were
    # rejected — a mostly-rejected batch usually means a wrong spec,
    # and silently loading the survivors would hide that.
    "reject_limit_pct": 25,
}


def load_spec(path):
    """Read a spec file and return the validated spec dict."""
    if not os.path.exists(path):
        raise SpecError("spec file not found: %s" % path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SpecError("spec is not valid JSON: %s" % exc)
    return validate_spec(raw, base_dir=os.path.dirname(os.path.abspath(path)))


def validate_spec(raw, base_dir="."):
    """Validate the structure of a spec dict and normalize defaults."""
    if not isinstance(raw, dict):
        raise SpecError("spec root must be an object")

    for section in REQUIRED_SECTIONS:
        if section not in raw:
            raise SpecError("spec is missing required section %r" % section)

    spec = dict(raw)
    spec["base_dir"] = base_dir

    if not isinstance(spec["job"], str) or not spec["job"].strip():
        raise SpecError("'job' must be a non-empty string")

    spec["source"] = _validate_endpoint(spec["source"], "source")
    spec["target"] = _validate_endpoint(spec["target"], "target")

    rejects = spec.get("rejects") or {}
    if rejects and "path" not in rejects:
        raise SpecError("'rejects' section needs a 'path'")
    spec["rejects"] = rejects

    spec["schema"] = _validate_schema(spec.get("schema") or {})
    spec["checks"] = _validate_checks(spec.get("checks") or [])
    spec["ops"] = _validate_ops(spec.get("ops") or [])

    options = dict(DEFAULT_OPTIONS)
    options.update(spec.get("options") or {})
    spec["options"] = options

    return spec


def _validate_endpoint(section, name):
    if not isinstance(section, dict):
        raise SpecError("'%s' must be an object" % name)
    if "path" not in section:
        raise SpecError("'%s' needs a 'path'" % name)
    fmt = section.get("format", "csv")
    if fmt not in KNOWN_FORMATS:
        raise SpecError(
            "'%s' format %r not supported (choose from %s)"
            % (name, fmt, ", ".join(KNOWN_FORMATS))
        )
    out = dict(section)
    out["format"] = fmt
    return out


def _validate_schema(schema):
    if not isinstance(schema, dict):
        raise SpecError("'schema' must be an object of field: type")
    for field, ftype in schema.items():
        if ftype not in KNOWN_TYPES:
            raise SpecError(
                "schema field %r has unknown type %r (choose from %s)"
                % (field, ftype, ", ".join(KNOWN_TYPES))
            )
    return dict(schema)


def _validate_checks(checks):
    from . import rules  # deferred to avoid an import cycle

    if not isinstance(checks, list):
        raise SpecError("'checks' must be a list")
    out = []
    for i, check in enumerate(checks):
        if not isinstance(check, dict) or "rule" not in check:
            raise SpecError("checks[%d] must be an object with a 'rule'" % i)
        if check["rule"] not in rules.RULES:
            raise SpecError(
                "checks[%d] uses unknown rule %r (known: %s)"
                % (i, check["rule"], ", ".join(sorted(rules.RULES)))
            )
        if "field" not in check and check["rule"] != "unique":
            raise SpecError("checks[%d] (%s) needs a 'field'" % (i, check["rule"]))
        out.append(dict(check))
    return out


def _validate_ops(ops):
    from . import ops as ops_mod  # deferred to avoid an import cycle

    if not isinstance(ops, list):
        raise SpecError("'ops' must be a list")
    out = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict) or "op" not in op:
            raise SpecError("ops[%d] must be an object with an 'op'" % i)
        if op["op"] not in ops_mod.OPS:
            raise SpecError(
                "ops[%d] uses unknown op %r (known: %s)"
                % (i, op["op"], ", ".join(sorted(ops_mod.OPS)))
            )
        out.append(dict(op))
    return out


def resolve_path(spec, path):
    """Resolve a spec-relative path against the spec file's directory."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(spec["base_dir"], path))
