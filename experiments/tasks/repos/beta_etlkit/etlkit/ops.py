"""Transform operations.

Each op is a callable `op(record, spec_op) -> record` applied to every
surviving record in spec order. Ops return the (possibly new) record;
raising RecordError/ValueError routes the record to the rejects pile.
"""

import datetime
from decimal import Decimal

from .errors import RecordError
from .utils.numbers import format_money, parse_decimal, parse_int
from .utils.text import is_blank


def op_cast(record, op):
    """Cast a field to a real Python type: {"op":"cast","field":F,"to":T}."""
    field = op["field"]
    to = op.get("to", "str")
    if field not in record or is_blank(record[field]):
        return record
    value = record[field]
    try:
        if to == "int":
            record[field] = parse_int(value)
        elif to == "decimal":
            record[field] = parse_decimal(value)
        elif to == "date":
            record[field] = datetime.date.fromisoformat(str(value).strip())
        elif to == "bool":
            record[field] = str(value).strip().lower() in ("true", "1")
        elif to == "str":
            record[field] = str(value)
        else:
            raise RecordError("unknown cast target %r" % to, field=field)
    except ValueError as exc:
        raise RecordError("cast %s to %s failed: %s" % (field, to, exc), field=field)
    return record


def op_rename(record, op):
    """{"op":"rename","field":OLD,"to":NEW} — no-op if OLD is absent."""
    old, new = op["field"], op["to"]
    if old in record:
        record[new] = record.pop(old)
    return record


def op_default(record, op):
    """Fill a missing/blank field: {"op":"default","field":F,"value":V}."""
    field = op["field"]
    if field not in record or is_blank(record[field]):
        record[field] = op.get("value")
    return record


def op_drop(record, op):
    """Remove a field: {"op":"drop","field":F}."""
    record.pop(op["field"], None)
    return record


def op_derive(record, op):
    """Compute a new field from others.

    {"op":"derive","field":"total","formula":"multiply",
     "args":["quantity","unit_price"]}

    Formulas: multiply, add, subtract, money (re-format a decimal
    field to 2dp string), concat (join string fields with a space).
    """
    field = op["field"]
    formula = op.get("formula")
    args = op.get("args", [])
    values = []
    for name in args:
        if name not in record:
            raise RecordError(
                "derive %r needs field %r which is missing" % (field, name),
                field=name,
            )
        values.append(record[name])
    try:
        if formula == "multiply":
            result = _as_decimal(values[0])
            for v in values[1:]:
                result *= _as_decimal(v)
            record[field] = result
        elif formula == "add":
            result = _as_decimal(values[0])
            for v in values[1:]:
                result += _as_decimal(v)
            record[field] = result
        elif formula == "subtract":
            record[field] = _as_decimal(values[0]) - _as_decimal(values[1])
        elif formula == "money":
            record[field] = format_money(_as_decimal(values[0]))
        elif formula == "concat":
            record[field] = " ".join(str(v) for v in values)
        else:
            raise RecordError("unknown derive formula %r" % formula, field=field)
    except (ValueError, ArithmeticError) as exc:
        raise RecordError(
            "derive %r (%s) failed: %s" % (field, formula, exc), field=field
        )
    return record


def _as_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return parse_decimal(value)


OPS = {
    "cast": op_cast,
    "rename": op_rename,
    "default": op_default,
    "drop": op_drop,
    "derive": op_derive,
}
