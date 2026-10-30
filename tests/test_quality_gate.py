import pytest

pytest.importorskip("pydantic")

from tests.test_quality_rules import NOW, SENT, good_row, sha  # noqa: E402
from src.quality.gate import (  # noqa: E402
    QualityGateError, check_gate, failure_rate, reason_counts, validate_records,
)
from src.quality.models import schema_problems  # noqa: E402


def run(rows):
    return validate_records(rows, min_words=40, max_words=340, now=NOW)


def test_good_rows_pass():
    valid, invalid = run([good_row(SENT * 6), good_row(SENT * 7)])
    assert len(valid) == 2 and invalid == []


def test_bad_rows_get_reasons_and_timestamp():
    valid, invalid = run([good_row(), {**good_row(SENT * 8), "version": 0}])
    assert len(valid) == 1 and len(invalid) == 1
    assert "BAD_VERSION" in invalid[0]["error_reasons"]
    assert invalid[0]["failed_at"]


def test_missing_field_and_wrong_type_are_schema_problems():
    row = good_row()
    del row["title"]
    assert "SCHEMA_title" in schema_problems(row)
    assert "SCHEMA_version" in schema_problems({**good_row(), "version": "1"})
    assert schema_problems(good_row()) == []


def test_duplicate_chunk_id_and_text():
    a = good_row(SENT * 6)
    dup_id = dict(a)
    dup_text = {**a, "chunk_id": sha("other")}
    valid, invalid = run([a, dup_id, dup_text])
    assert len(valid) == 1
    assert "DUPLICATE_ID" in invalid[0]["error_reasons"]
    assert "DUPLICATE_TEXT" in invalid[1]["error_reasons"]


def test_gate_threshold():
    check_gate(total=100, n_invalid=5, threshold=0.05)  # exactly at the limit passes
    with pytest.raises(QualityGateError):
        check_gate(total=100, n_invalid=6, threshold=0.05)
    check_gate(total=0, n_invalid=0, threshold=0.05)  # empty file does not divide by zero
    assert failure_rate(200, 10) == 0.05


def test_reason_counts():
    invalid = [{"error_reasons": ["A", "B"]}, {"error_reasons": ["A"]}]
    assert reason_counts(invalid) == {"A": 2, "B": 1}