import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import Aggregates, Coverage, SemesterWindow, dump_doc, window_adapter

from statsboteval_pipeline.contract import weeks_range
from statsboteval_pipeline.windows import build_windows

from .factories import WEEKS, make_synthetic_aggregates


def test_coverage_uses_from_alias() -> None:
    cov = Coverage.model_validate({"from": "2025-W11", "through": "2025-W14"})
    assert cov.from_ == "2025-W11"
    assert dump_doc(cov) == {"from": "2025-W11", "through": "2025-W14"}


def test_coverage_rejects_reversed() -> None:
    with pytest.raises(ValidationError):
        Coverage.model_validate({"from": "2025-W14", "through": "2025-W11"})


def test_window_union_discriminates_on_kind() -> None:
    w = window_adapter.validate_python(
        {"id": "all_time", "kind": "all_time", "label": "All time", "short_label": "All time",
         "coverage": {"from": "2025-W11", "through": "2025-W14"}}
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


# --- semester slices (1.8.0, D-56) ----------------------------------------------------


def slice_doc(**overrides: object) -> dict:
    """A registry holding 2025S and one slice of it, with `overrides` applied to the slice."""
    dumped = dump_doc(make_synthetic_aggregates())
    entry = next(w for w in dumped["windows"] if w["id"] == "2025S.last1")
    entry.update(overrides)
    return dumped


def test_slice_parent_must_be_a_semester_in_the_registry() -> None:
    with pytest.raises(ValidationError, match="not a semester window in this registry"):
        Aggregates.model_validate(slice_doc(parent_window_id="2026W"))


def test_slice_weeks_must_belong_to_its_parent() -> None:
    with pytest.raises(ValidationError, match="holds weeks outside 2025S"):
        Aggregates.model_validate(slice_doc(weeks=["2025-W30"], coverage={"from": "2025-W30", "through": "2025-W30"}))


def test_slice_semester_weeks_must_index_full_membership() -> None:
    # 2025S starts at W10, so W14 is teaching week 5. Claiming week 4 is what indexing
    # against *covered* weeks would produce on an axis that starts at W11 — plausible on
    # its own, and wrong by exactly the number of unpublishable opening weeks (D-54).
    with pytest.raises(ValidationError, match="teaching weeks"):
        Aggregates.model_validate(slice_doc(semester_weeks=[4, 4]))


def test_slice_coverage_must_span_its_weeks() -> None:
    with pytest.raises(ValidationError, match="coverage must span exactly its weeks"):
        Aggregates.model_validate(slice_doc(coverage={"from": "2025-W11", "through": "2025-W14"}))


def test_enrollment_may_not_be_keyed_by_a_slice() -> None:
    # One institutional headcount per semester; a slice reads its parent's (D-56).
    dumped = dump_doc(make_synthetic_aggregates())
    dumped["enrollment"] = {
        "per_window": {"2025S.last1": {"bachelor": 170, "master": 298, "source": "roster", "as_of": "2026-03-01"}}
    }
    with pytest.raises(ValidationError, match="parent_window_id"):
        Aggregates.model_validate(dumped)


def test_a_pre_1_8_0_document_still_validates() -> None:
    """Roll-forward safety: the document already in the blob must parse under this schema.

    The API validates every blob it fetches against the schema it ships with (contract
    §11), so if the *previous* publish stopped validating there would be no safe order to
    deploy in — code-then-blob and blob-then-code would both take the dashboard down with a
    500 until the other half landed. This reconstructs a 1.7.0-shaped registry: no slices,
    no short_label, and a trailing window, which is why `TrailingWindow` is still a member
    of the union though nothing emits one. Delete it and this fails.

    `api/tests/fixtures/aggregates_synthetic.json` is a 1.0.0 document kept as the same
    proof from the other end.
    """
    dumped = dump_doc(make_synthetic_aggregates())
    dumped["windows"] = [w for w in dumped["windows"] if w["kind"] != "semester_slice"]
    for window in dumped["windows"]:
        # `pop`, not `del`: since D-57 the pipeline no longer emits short_label on these
        # kinds, so the synthetic document already lacks it. The point stands either way —
        # a 1.7.0 registry has no short_label anywhere.
        window.pop("short_label", None)
    dumped["windows"].append(
        {
            "kind": "trailing",
            "id": "trailing_4",
            "label": "Last Avl. 4 weeks",
            "weeks": WEEKS,
            "coverage": {"from": WEEKS[0], "through": WEEKS[-1]},
        }
    )
    for section in dumped["sections"].values():
        if "per_window" in section:
            section["per_window"] = {
                k: v for k, v in section["per_window"].items() if not k.startswith("2025S.")
            }
    Aggregates.model_validate(dumped)


def test_the_pipeline_no_longer_emits_a_trailing_window() -> None:
    # The union keeps `trailing` only so the previous publish parses; producing one again
    # would resurrect the axis-anchored window D-56 removed.
    axis = weeks_range("2025-W09", "2026-W12")
    assert [w.kind for w in build_windows(axis) if w.kind == "trailing"] == []
