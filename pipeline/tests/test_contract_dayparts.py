"""Dayparts registry + coarse grid + semester profiles (schema 1.6.0, D-54).

The registry checks live on Aggregates, not on DaypartGrid: density is
7 x len(dayparts) and only the root sees the registry. So most of this file builds
a whole document — the same reason test_contract_trends does.
"""

import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    Daypart,
    DaypartCell,
    DaypartGrid,
    DaypartTotals,
    SemesterProfile,
    SemesterProfilePoint,
    dump_doc,
    ok,
    suppressed,
)
from statsboteval_pipeline.contract import Aggregates

from .factories import DAYPARTS, make_synthetic_aggregates


def rebuild(doc: Aggregates, mutate) -> Aggregates:
    """Round-trip a document through a dict mutation, so root validators re-run."""
    dumped = dump_doc(doc)
    mutate(dumped)
    return Aggregates.model_validate(dumped)


# --- the registry itself ----------------------------------------------------


def test_daypart_rejects_midnight_wrap() -> None:
    # Equal six-hour blocks tile 0..24 with nothing spanning midnight; a wrapping block
    # would break both the `from <= h < to` lookup and the "bars are comparable" claim.
    with pytest.raises(ValidationError):
        Daypart(id="night", label="Night", from_hour=22, to_hour=6)


def test_registry_must_tile_the_whole_day() -> None:
    doc = make_synthetic_aggregates()
    gap = [d.model_dump() for d in DAYPARTS]
    gap[1]["from_hour"] = 7  # 6..7 uncovered
    with pytest.raises(ValidationError, match="contiguously"):
        rebuild(doc, lambda d: d.update(dayparts=gap))

    short = [d.model_dump() for d in DAYPARTS[:-1]]
    with pytest.raises(ValidationError, match="whole day"):
        rebuild(doc, lambda d: d.update(dayparts=short))


def test_duplicate_daypart_ids_rejected() -> None:
    doc = make_synthetic_aggregates()
    dupes = [d.model_dump() for d in DAYPARTS]
    dupes[1]["id"] = "night"
    with pytest.raises(ValidationError, match="unique"):
        rebuild(doc, lambda d: d.update(dayparts=dupes))


def test_daypart_cells_without_a_registry_rejected() -> None:
    doc = make_synthetic_aggregates()
    with pytest.raises(ValidationError, match="registry is missing"):
        rebuild(doc, lambda d: d.pop("dayparts"))


# --- the grid ---------------------------------------------------------------


def test_grid_density_is_seven_times_the_registry() -> None:
    doc = make_synthetic_aggregates()
    grid = doc.sections.temporal_usage.per_window["all_time"].daypart_heatmap
    assert len(grid.cells) == 7 * len(DAYPARTS) == 28

    def drop_one(dumped: dict) -> None:
        cells = dumped["sections"]["temporal_usage"]["per_window"]["all_time"]["daypart_heatmap"]["cells"]
        del cells[-1]

    with pytest.raises(ValidationError, match="exactly 28 cells"):
        rebuild(doc, drop_one)


def test_grid_rejects_unknown_daypart_id() -> None:
    doc = make_synthetic_aggregates()

    def rename(dumped: dict) -> None:
        cells = dumped["sections"]["temporal_usage"]["per_window"]["all_time"]["daypart_heatmap"]["cells"]
        cells[0]["daypart"] = "brunch"

    with pytest.raises(ValidationError, match="unknown dayparts"):
        rebuild(doc, rename)


def test_grid_rejects_duplicate_pairs() -> None:
    cells = [DaypartCell(dow=1, daypart="night", cell=ok(1)) for _ in range(2)]
    with pytest.raises(ValidationError, match="duplicate"):
        DaypartGrid(cells=cells)


def test_totals_must_hold_exactly_the_registry_ids() -> None:
    doc = make_synthetic_aggregates()

    def drop_key(dumped: dict) -> None:
        totals = dumped["sections"]["temporal_usage"]["per_window"]["all_time"]["daypart_totals"]
        del totals["by_daypart"]["night"]

    with pytest.raises(ValidationError, match="exactly the registry ids"):
        rebuild(doc, drop_key)


def test_totals_carry_a_suppressed_side_without_a_value() -> None:
    # Invariant 2 through the new shape: a suppressed span has no value field to read.
    totals = DaypartTotals(
        by_daypart={p.id: ok(1) for p in DAYPARTS}, weekend=suppressed(), weekday=ok(9)
    )
    assert "value" not in dump_doc(totals)["weekend"]


# --- semester profiles ------------------------------------------------------


def test_semester_profile_partial_coverage_keeps_its_index() -> None:
    # The fixture axis (W11-W14) starts inside 2025S (W10-W26), so week 1 is off-axis and
    # the profile opens at semester_week 2. Re-indexing to 1 here would slide the curve a
    # week left and silently misalign every comparison the overlay exists to make.
    doc = make_synthetic_aggregates()
    profile = doc.sections.temporal_usage.semester_profiles[0]
    assert [p.semester_week for p in profile.points] == [2, 3, 4, 5]
    assert profile.points[0].week == "2025-W11"


def test_semester_profile_must_reference_a_semester_window() -> None:
    doc = make_synthetic_aggregates()

    def repoint(dumped: dict) -> None:
        dumped["sections"]["temporal_usage"]["semester_profiles"][0]["window_id"] = "trailing_4"

    with pytest.raises(ValidationError, match="not a semester window"):
        rebuild(doc, repoint)

    def unknown(dumped: dict) -> None:
        dumped["sections"]["temporal_usage"]["semester_profiles"][0]["window_id"] = "2099W"

    with pytest.raises(ValidationError, match="unknown window"):
        rebuild(doc, unknown)


def test_semester_week_must_ascend_uniquely() -> None:
    doc = make_synthetic_aggregates()

    def scramble(dumped: dict) -> None:
        points = dumped["sections"]["temporal_usage"]["semester_profiles"][0]["points"]
        points[0]["semester_week"] = points[1]["semester_week"]

    with pytest.raises(ValidationError, match="ascend uniquely"):
        rebuild(doc, scramble)


def test_semester_profile_point_rejects_week_zero() -> None:
    with pytest.raises(ValidationError):
        SemesterProfilePoint(semester_week=0, week="2025-W11", messages=ok(1), active_students=ok(1))


# --- additivity: a 1.5.0-shaped document still validates --------------------


def test_document_without_any_1_6_0_field_still_validates() -> None:
    doc = make_synthetic_aggregates()

    def strip(dumped: dict) -> None:
        dumped.pop("dayparts")
        temporal = dumped["sections"]["temporal_usage"]
        temporal.pop("semester_profiles")
        for window in temporal["per_window"].values():
            window.pop("daypart_heatmap")
            window.pop("daypart_totals")

    older = rebuild(doc, strip)
    assert older.dayparts is None
    assert older.sections.temporal_usage.semester_profiles is None
    assert older.sections.temporal_usage.per_window["all_time"].daypart_heatmap is None
    # activity_heatmap is untouched by the bump: still required, still 168 cells.
    assert len(older.sections.temporal_usage.per_window["all_time"].activity_heatmap.cells) == 168


def test_optional_fields_dump_absent_not_null() -> None:
    profile = SemesterProfile(window_id="2025S", label="x", kind="summer", points=[])
    assert "footnote_ids" not in dump_doc(profile)
