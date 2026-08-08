"""Validation rules.

Each rule is a callable `rule(record, check, state) -> None` that raises
CheckFailure to reject the record. `state` is a per-run dict scoped to
one check instance, used by stateful rules such as `unique`.
"""

import datetime

from .errors import CheckFailure
from .utils.numbers import parse_decimal, parse_int
from .utils.text import is_blank


def rule_required(record, check, state):
    field = check["field"]
    if field not in record or is_blank(record[field]):
        raise CheckFailure("required field %r is missing or blank" % field, field=field)


def rule_type(record, check, state):
    """Check that the field parses as the declared type without changing it."""
    field = check["field"]
    if field not in record or is_blank(record[field]):
        return  # absence is `required`'s business, not ours
    expected = check.get("type", "str")
    value = record[field]
    try:
        if expected == "int":
            parse_int(value)
        elif expected == "decimal":
            float(str(value).strip().lstrip("$"))
        elif expected == "date":
            datetime.date.fromisoformat(str(value).strip())
        elif expected == "bool":
            if str(value).strip().lower() not in ("true", "false", "1", "0"):
                raise ValueError("not a boolean: %r" % value)
    except ValueError as exc:
        raise CheckFailure(str(exc), field=field)


def rule_range(record, check, state):
    field = check["field"]
    if field not in record or is_blank(record[field]):
        return
    try:
        value = parse_decimal(record[field])
    except ValueError as exc:
        raise CheckFailure(str(exc), field=field)
    low = check.get("min")
    high = check.get("max")
    if low is not None and value < parse_decimal(low):
        raise CheckFailure(
            "%s=%s is below the minimum %s" % (field, value, low), field=field
        )
    if high is not None and value > parse_decimal(high):
        raise CheckFailure(
            "%s=%s is above the maximum %s" % (field, value, high), field=field
        )


def rule_one_of(record, check, state):
    field = check["field"]
    if field not in record or is_blank(record[field]):
        return
    allowed = check.get("values", [])
    if record[field] not in allowed:
        raise CheckFailure(
            "%s=%r is not one of %s" % (field, record[field], ", ".join(allowed)),
            field=field,
        )


def rule_unique(record, check, state):
    """Reject records whose key fields repeat an earlier record's."""
    fields = check.get("fields") or [check["field"]]
    key = tuple(str(record.get(f, "")) for f in fields)
    seen = state.setdefault("seen", set())
    if key in seen:
        raise CheckFailure(
            "duplicate value for %s: %s" % ("+".join(fields), "/".join(key)),
            field=fields[0],
        )
    seen.add(key)


def rule_matches(record, check, state):
    """Substring / prefix check — deliberately not full regex to keep specs tame."""
    field = check["field"]
    if field not in record or is_blank(record[field]):
        return
    value = str(record[field])
    prefix = check.get("prefix")
    contains = check.get("contains")
    if prefix is not None and not value.startswith(prefix):
        raise CheckFailure(
            "%s=%r does not start with %r" % (field, value, prefix), field=field
        )
    if contains is not None and contains not in value:
        raise CheckFailure(
            "%s=%r does not contain %r" % (field, value, contains), field=field
        )


RULES = {
    "required": rule_required,
    "type": rule_type,
    "range": rule_range,
    "one_of": rule_one_of,
    "unique": rule_unique,
    "matches": rule_matches,
}
