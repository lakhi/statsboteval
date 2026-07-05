import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import Coverage, SemesterWindow, dump_doc, window_adapter


def test_coverage_uses_from_alias() -> None:
    cov = Coverage.model_validate({"from": "2025-W11", "through": "2025-W14"})
    assert cov.from_ == "2025-W11"
    assert dump_doc(cov) == {"from": "2025-W11", "through": "2025-W14"}


def test_coverage_rejects_reversed() -> None:
    with pytest.raises(ValidationError):
        Coverage.model_validate({"from": "2025-W14", "through": "2025-W11"})


def test_window_union_discriminates_on_kind() -> None:
    w = window_adapter.validate_python(
        {"id": "all_time", "kind": "all_time", "label": "All time", "coverage": {"from": "2025-W11", "through": "2025-W14"}}
    )
    assert w.kind == "all_time"
    assert not hasattr(w, "weeks")  # all_time carries no membership list (contract §6.1)


def test_semester_window_requires_dates_and_weeks() -> None:
    with pytest.raises(ValidationError):
        window_adapter.validate_python(
            {"id": "2025S", "kind": "semester", "label": "Summer semester 2025", "coverage": {"from": "2025-W11", "through": "2025-W14"}}
        )


def test_semester_window_round_trip() -> None:
    w = SemesterWindow(
        kind="semester",
        id="2025S",
        label="Summer semester 2025",
        start_date="2025-03-01",
        end_date="2025-06-30",
        weeks=["2025-W10", "2025-W11"],
        coverage={"from": "2025-W11", "through": "2025-W11"},
    )
    dumped = dump_doc(w)
    assert dumped["start_date"] == "2025-03-01"
    assert dumped["coverage"]["from"] == "2025-W11"
