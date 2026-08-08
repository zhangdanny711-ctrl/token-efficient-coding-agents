import pytest

from reportgen import generate_report

ROWS = [
    {"label": "alpha", "value": 100},
    {"label": "beta", "value": 300},
]


def test_default_report():
    out = generate_report(ROWS)
    assert "Report: total $400.00" in out
    assert "beta: $300.00 75.0%" in out


def test_partial_format_override():
    # Overriding one format key must keep the other format defaults.
    out = generate_report(ROWS, {"format": {"decimals": 0}})
    assert "Report: total $400" in out
    assert "$400.00" not in out


def test_partial_sections_override():
    # Disabling one section must keep the other section's default.
    out = generate_report(ROWS, {"sections": {"details": False}})
    assert "total" in out
    assert "beta" not in out


def test_title_override():
    out = generate_report(ROWS, {"title": "Q3"})
    assert out.startswith("Q3: total")


def test_invalid_section_rejected():
    with pytest.raises(ValueError):
        generate_report(ROWS, {"sections": {"bogus": True}})
