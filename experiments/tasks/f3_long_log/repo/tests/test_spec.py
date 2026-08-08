import pytest

from etlkit.errors import SpecError
from etlkit.spec import load_spec, resolve_path, validate_spec

from .conftest import write_spec

MINIMAL = {
    "job": "j",
    "source": {"path": "in.csv"},
    "target": {"path": "out.jsonl", "format": "jsonl"},
}


def test_minimal_spec_validates():
    spec = validate_spec(dict(MINIMAL))
    assert spec["job"] == "j"
    assert spec["source"]["format"] == "csv"  # default
    assert spec["checks"] == []
    assert spec["ops"] == []
    assert spec["options"]["reject_limit_pct"] == 25


def test_missing_section():
    with pytest.raises(SpecError, match="missing required section 'target'"):
        validate_spec({"job": "j", "source": {"path": "x"}})


def test_root_must_be_object():
    with pytest.raises(SpecError, match="root must be an object"):
        validate_spec([1, 2])


def test_blank_job_name():
    bad = dict(MINIMAL, job="  ")
    with pytest.raises(SpecError, match="non-empty string"):
        validate_spec(bad)


def test_unknown_format():
    bad = dict(MINIMAL, source={"path": "x", "format": "parquet"})
    with pytest.raises(SpecError, match="format 'parquet' not supported"):
        validate_spec(bad)


def test_unknown_schema_type():
    bad = dict(MINIMAL, schema={"f": "float"})
    with pytest.raises(SpecError, match="unknown type 'float'"):
        validate_spec(bad)


def test_unknown_rule():
    bad = dict(MINIMAL, checks=[{"rule": "regex", "field": "f"}])
    with pytest.raises(SpecError, match="unknown rule 'regex'"):
        validate_spec(bad)


def test_check_needs_field():
    bad = dict(MINIMAL, checks=[{"rule": "required"}])
    with pytest.raises(SpecError, match="needs a 'field'"):
        validate_spec(bad)


def test_unknown_op():
    bad = dict(MINIMAL, ops=[{"op": "explode", "field": "f"}])
    with pytest.raises(SpecError, match="unknown op 'explode'"):
        validate_spec(bad)


def test_rejects_needs_path():
    bad = dict(MINIMAL, rejects={"format": "jsonl"})
    with pytest.raises(SpecError, match="needs a 'path'"):
        validate_spec(bad)


def test_options_merge_defaults():
    spec = validate_spec(dict(MINIMAL, options={"verbose": False}))
    assert spec["options"]["verbose"] is False
    assert spec["options"]["reject_limit_pct"] == 25


def test_load_spec_missing_file(tmp_path):
    with pytest.raises(SpecError, match="not found"):
        load_spec(str(tmp_path / "nope.json"))


def test_load_spec_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(SpecError, match="not valid JSON"):
        load_spec(str(path))


def test_load_spec_sets_base_dir(tmp_path):
    path = write_spec(tmp_path / "ok.json", MINIMAL)
    spec = load_spec(path)
    assert spec["base_dir"] == str(tmp_path)
    assert resolve_path(spec, "in.csv") == str(tmp_path / "in.csv")


def test_resolve_path_absolute_passthrough(tmp_path):
    spec = validate_spec(dict(MINIMAL), base_dir=str(tmp_path))
    assert resolve_path(spec, "/abs/x.csv") == "/abs/x.csv"
