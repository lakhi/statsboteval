"""Candidate pool, gate and relevance ranking for the trends section (D-49).

These tests drive `build_trends` directly with in-memory structures rather than through
DuckDB: the whole point of the T-3 design is that findings are computed from the same
objects the sections are, so the unit of test is that function.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pytest

from statsboteval_pipeline.contract import weeks_range, week_monday
from statsboteval_pipeline.trends import (
    DEDUCTIVE_EXCLUDED,
    build_trends,
    iter_candidate_ids,
)
from statsboteval_pipeline.windows import build_windows

# W20 2025 falls in 2025S (Thursday 15 May), W45 in 2025W (Thursday 6 Nov), so this axis
# publishes two semesters plus all_time, and each semester's slices.
TWO_SEMESTERS = weeks_range("2025-W20", "2025-W45")
ONE_SEMESTER = weeks_range("2025-W20", "2025-W25")

FLOOR = 3


@dataclass(frozen=True)
class Msg:
    history_id: int
    pseudonym: str
    local: datetime
    week: str
    lang: str


@dataclass(frozen=True)
class Sess:
    pseudonym: str
    week: str
    n_messages: int
    duration_minutes: float


class Ids:
    """Globally unique history ids — topic membership is keyed on them."""

    def __init__(self) -> None:
        self.next = 1

    def take(self) -> int:
        self.next += 1
        return self.next - 1


def messages(
    ids: Ids,
    week: str,
    *,
    students: int,
    per_student: int,
    lang: str = "de",
    hour: int = 10,
    dow: int = 1,
) -> list[Msg]:
    stamp = datetime.combine(week_monday(week) + timedelta(days=dow - 1), time(hour))
    return [Msg(ids.take(), f"stu{s:03d}", stamp, week, lang) for s in range(students) for _ in range(per_student)]


def spread(ids: Ids, weeks: list[str], **kwargs: int | str) -> list[Msg]:
    out: list[Msg] = []
    for week in weeks:
        out.extend(messages(ids, week, **kwargs))  # type: ignore[arg-type]
    return out


def mark_stride(msgs: list[Msg], fraction: float) -> set[int]:
    """history_ids of a deterministic ~`fraction` of `msgs`, spread across students.

    Slicing a prefix instead would concentrate the subset on one or two students, and it
    would then be dropped by the privacy floor rather than by the gate under test.
    """
    if fraction <= 0:
        return set()
    stride = max(1, round(1 / fraction))
    return {m.history_id for i, m in enumerate(msgs) if i % stride == 0}


def with_german_share(msgs: list[Msg], german: float) -> list[Msg]:
    """Relabel a spread subset to English so German lands near `german`."""
    english = mark_stride(msgs, 1.0 - german)
    return [Msg(m.history_id, m.pseudonym, m.local, m.week, "en" if m.history_id in english else "de") for m in msgs]


def two_periods(ids: Ids, axis: list[str], *, students: int = 8, per_student: int = 12) -> tuple[list[Msg], list[Msg]]:
    """Messages for the first and second published semester of `axis`."""
    first = spread(ids, semester_weeks(axis, "2025S"), students=students, per_student=per_student)
    second = spread(ids, semester_weeks(axis, "2025W"), students=students, per_student=per_student)
    return first, second


def semester_weeks(axis: list[str], semester_id: str) -> list[str]:
    window = next(w for w in build_windows(axis) if w.id == semester_id)
    return [w for w in axis if w in set(window.weeks)]


def run(
    msgs: list[Msg],
    *,
    axis: list[str],
    sessions: list[Sess] | None = None,
    registrations: list[tuple[str, str]] | None = None,
    positives: dict[str, dict[str, set[int]]] | None = None,
    deductive_labels: dict[str, str] | None = None,
    floor_n: int = FLOOR,
) -> dict[str, object]:
    section = build_trends(
        msgs=msgs,
        sessions=sessions or [],
        registrations=registrations or [],
        windows=build_windows(axis),
        axis=axis,
        floor_n=floor_n,
        positives=positives,
        deductive_labels=deductive_labels,
    )
    return dict(section.per_window)


# --- the pairing table ----------------------------------------------------------------


def test_earliest_semester_has_no_predecessor() -> None:
    ids = Ids()
    msgs = spread(ids, ONE_SEMESTER, students=10, per_student=5)
    per_window = run(msgs, axis=ONE_SEMESTER)
    assert per_window["2025S"].baseline is None  # type: ignore[attr-defined]
    assert per_window["2025S"].findings == []  # type: ignore[attr-defined]
    assert per_window["2025S"].insufficient_data is False  # type: ignore[attr-defined]


def test_semester_compares_against_the_previous_semester() -> None:
    ids = Ids()
    msgs = spread(ids, TWO_SEMESTERS, students=10, per_student=5)
    baseline = run(msgs, axis=TWO_SEMESTERS)["2025W"].baseline  # type: ignore[attr-defined]
    assert baseline.kind == "window"
    assert baseline.window_id == "2025S"


def test_semester_slices_are_not_assessed_at_all() -> None:
    """D-56 deferred slice pairing with the hidden Trends tab — this pins the deferral.

    The rule it guards is not "we haven't got round to it": _pair_for's old trailing branch
    would have handed a slice the tail of the axis as its baseline, which across a break is
    weeks nobody was in class for. Findings are floor-checked and published whether or not
    a tab renders them, so a slice that silently acquires a baseline is wrong output, not a
    missing feature. Deciding slice pairing is the first task of un-hiding Trends.
    """
    ids = Ids()
    msgs = spread(ids, TWO_SEMESTERS, students=10, per_student=5)
    per_window = run(msgs, axis=TWO_SEMESTERS)
    slices = [w.id for w in build_windows(TWO_SEMESTERS) if w.kind == "semester_slice"]
    assert slices, "the axis must actually publish slices for this to prove anything"
    assert [wid for wid in slices if wid in per_window] == []


def test_all_time_needs_two_semesters_for_a_trajectory() -> None:
    ids = Ids()
    one = run(spread(ids, ONE_SEMESTER, students=10, per_student=5), axis=ONE_SEMESTER)
    assert one["all_time"].baseline is None  # type: ignore[attr-defined]

    ids = Ids()
    two = run(spread(ids, TWO_SEMESTERS, students=10, per_student=5), axis=TWO_SEMESTERS)
    assert two["all_time"].baseline.kind == "trajectory"  # type: ignore[attr-defined]


def test_every_selectable_period_gets_an_entry() -> None:
    # Semesters and all_time, i.e. every window trends actually assesses (see above).
    ids = Ids()
    msgs = spread(ids, TWO_SEMESTERS, students=10, per_student=5)
    per_window = run(msgs, axis=TWO_SEMESTERS)
    assert set(per_window) == {
        w.id for w in build_windows(TWO_SEMESTERS) if w.kind != "semester_slice"
    }


# --- the gate -------------------------------------------------------------------------


def language_shift(ids: Ids, axis: list[str], *, base: float = 0.8, current: float = 0.5) -> list[Msg]:
    """A partial two-semester German-share move, well above every minimum n.

    Partial on purpose: a *complete* flip leaves one side with no contributing students,
    which the floor drops before the effect gate is ever consulted.
    """
    first, second = two_periods(ids, axis)
    return with_german_share(first, base) + with_german_share(second, current)


def test_a_large_clean_shift_publishes() -> None:
    ids = Ids()
    findings = run(language_shift(ids, TWO_SEMESTERS), axis=TWO_SEMESTERS)["2025W"].findings  # type: ignore[attr-defined]
    assert {f.id for f in findings} & {"language-de-share", "language-en-share"}


def test_a_measure_falling_to_zero_publishes_nothing() -> None:
    # Documented consequence of flooring shares on *numerator* students: English goes
    # 50% -> 0%, so its current side has no contributing students and cannot be reported
    # without leaking what the topics-style suppression withholds. German makes the
    # mirror-image move over the same messages and publishes normally, which is what
    # shows the drop is about the zero side rather than about the comparison failing.
    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS)
    findings = run(with_german_share(first, 0.5) + with_german_share(second, 1.0), axis=TWO_SEMESTERS)["2025W"].findings  # type: ignore[attr-defined]
    assert "language-en-share" not in {f.id for f in findings}
    german = next(f for f in findings if f.id == "language-de-share")
    assert german.title == "German share of messages rose"


def test_sub_floor_sides_are_dropped_and_flagged_insufficient() -> None:
    # Two students per period: every candidate fails the floor, nothing was testable.
    ids = Ids()
    first = spread(ids, semester_weeks(TWO_SEMESTERS, "2025S"), students=2, per_student=20)
    second = spread(ids, semester_weeks(TWO_SEMESTERS, "2025W"), students=2, per_student=20)
    entry = run(with_german_share(first, 0.8) + with_german_share(second, 0.4), axis=TWO_SEMESTERS)["2025W"]
    assert entry.findings == []  # type: ignore[attr-defined]
    assert entry.insufficient_data is True  # type: ignore[attr-defined]


def test_a_window_with_no_evaluable_candidate_is_insufficient_not_flat() -> None:
    """The far end of the same rule: nothing was even *defined*, let alone testable.

    A window whose current side has no messages at all evaluates no candidate — every
    measure is undefined on that side, so `_assess` never sees one. Reporting "no
    meaningful shifts" here would claim a comparison ran when none did (D-49 choice 12).
    Practically unreachable on today's corpus, where even a break week evaluates the full
    pool and fails the floor gate instead; pinned so the two paths cannot diverge.
    """
    ids = Ids()
    # Messages only in the earlier semester: 2025W has a baseline but nothing to measure.
    first = spread(ids, semester_weeks(TWO_SEMESTERS, "2025S"), students=8, per_student=20)
    entry = run(first, axis=TWO_SEMESTERS)["2025W"]
    assert entry.baseline is not None  # type: ignore[attr-defined]
    assert entry.findings == []  # type: ignore[attr-defined]
    assert entry.insufficient_data is True  # type: ignore[attr-defined]


def test_a_flat_period_is_not_insufficient_data() -> None:
    # Plenty of testable material, no shift: "nothing changed", not "nothing to compare".
    ids = Ids()
    entry = run(language_shift(ids, TWO_SEMESTERS, base=0.8, current=0.8), axis=TWO_SEMESTERS)["2025W"]
    assert entry.findings == []  # type: ignore[attr-defined]
    assert entry.insufficient_data is False  # type: ignore[attr-defined]


def test_effect_thresholds_are_per_family_not_per_kind() -> None:
    # The identical ~3 pp move, read two ways: below the 5 pp language floor, above the
    # 2 pp topic floor. Without per-family thresholds, tier 1 would be unreachable.
    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS)
    language = run(with_german_share(first, 0.97) + with_german_share(second, 0.94), axis=TWO_SEMESTERS)[
        "2025W"
    ].findings  # type: ignore[attr-defined]
    assert not [f for f in language if f.id.startswith("language-")]

    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS)
    marked = mark_stride(first, 0.03) | mark_stride(second, 0.06)
    topics = run(first + second, axis=TWO_SEMESTERS, positives={"method_theme": {"regression": marked}})[
        "2025W"
    ].findings  # type: ignore[attr-defined]
    assert [f.id for f in topics] == ["topics-method_theme-regression"]


def test_small_base_shares_also_need_a_relative_move() -> None:
    # ~33 -> ~34 pp clears the 2 pp topic floor but not the 30% relative floor.
    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS)
    marked = mark_stride(first, 0.33) | mark_stride(second, 0.34)
    findings = run(first + second, axis=TWO_SEMESTERS, positives={"method_theme": {"anova": marked}})["2025W"].findings  # type: ignore[attr-defined]
    assert not [f for f in findings if f.tab == "topics"]


# --- relevance ranking ----------------------------------------------------------------


def test_relevance_tier_outranks_a_much_larger_effect() -> None:
    # A ~7 pp tier-1 method-theme move must outrank a 30 pp tier-3 language move. This is
    # the whole point of D-49 choice 6: usefulness orders, effect size only breaks ties.
    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS)
    marked = mark_stride(first, 0.10) | mark_stride(second, 0.17)
    msgs = with_german_share(first, 0.8) + with_german_share(second, 0.5)
    findings = run(msgs, axis=TWO_SEMESTERS, positives={"method_theme": {"regression": marked}})["2025W"].findings  # type: ignore[attr-defined]
    assert findings[0].tab == "topics"
    assert findings[0].id == "topics-method_theme-regression"
    # The much larger language move still publishes — it just ranks below.
    assert "language" in {f.tab for f in findings}
    assert abs(findings[-1].delta) > abs(findings[0].delta)


def test_a_compete_group_spends_at_most_one_slot() -> None:
    # German and English are complementary, so both always move together; only the
    # larger may occupy a slot, or one shift would fill the tab twice over.
    ids = Ids()
    findings = run(language_shift(ids, TWO_SEMESTERS), axis=TWO_SEMESTERS)["2025W"].findings  # type: ignore[attr-defined]
    assert len([f for f in findings if f.id.startswith("language-")]) == 1


def test_dayparts_compete_as_one_group() -> None:
    ids = Ids()
    weeks_first, weeks_second = semester_weeks(TWO_SEMESTERS, "2025S"), semester_weeks(TWO_SEMESTERS, "2025W")
    # Mornings in the first period, evenings in the second: every daypart share moves.
    first = spread(ids, weeks_first, students=8, per_student=12, hour=8)
    second = spread(ids, weeks_second, students=8, per_student=12, hour=20)
    findings = run(first + second, axis=TWO_SEMESTERS)["2025W"].findings  # type: ignore[attr-defined]
    assert len([f for f in findings if f.id.startswith("timing-daypart-")]) <= 1


def test_topics_may_take_three_slots_and_other_tabs_two() -> None:
    ids = Ids()
    first, second = two_periods(ids, TWO_SEMESTERS, per_student=40)
    # Six disjoint themes, each roughly doubling its share between the periods.
    positives: dict[str, dict[str, set[int]]] = {"method_theme": {}}
    for i in range(6):
        base_ids = {m.history_id for j, m in enumerate(first) if j % 12 == i}
        cur_ids = {m.history_id for j, m in enumerate(second) if j % 6 == i}
        positives["method_theme"][f"theme{i}"] = base_ids | cur_ids
    findings = run(first + second, axis=TWO_SEMESTERS, positives=positives)["2025W"].findings  # type: ignore[attr-defined]
    assert len([f for f in findings if f.tab == "topics"]) == 3
    assert len(findings) <= 5


# --- trajectories ---------------------------------------------------------------------


def test_all_time_findings_carry_one_point_per_semester() -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    findings = run(msgs, axis=TWO_SEMESTERS)["all_time"].findings  # type: ignore[attr-defined]
    assert findings, "the flip should be visible over all time too"
    for finding in findings:
        assert [p.window_id for p in finding.trajectory] == ["2025S", "2025W"]
        assert all(p.n_students >= FLOOR for p in finding.trajectory)


def test_only_all_time_carries_trajectories() -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    per_window = run(msgs, axis=TWO_SEMESTERS)
    for window_id, entry in per_window.items():
        if window_id == "all_time":
            continue
        assert all(f.trajectory is None for f in entry.findings)  # type: ignore[attr-defined]


def test_all_time_findings_cite_cohort_turnover() -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    findings = run(msgs, axis=TWO_SEMESTERS)["all_time"].findings  # type: ignore[attr-defined]
    assert all("cohort_turnover" in f.footnote_ids for f in findings)


# --- the pool ------------------------------------------------------------------------


def test_topic_candidates_appear_only_with_a_classification() -> None:
    without = set(iter_candidate_ids())
    with_topics = set(iter_candidate_ids({"method_theme": {"regression": set()}}))
    assert not any(i.startswith("topics-") for i in without)
    assert "topics-method_theme-regression" in with_topics


def test_language_deductive_categories_are_excluded_from_the_pool() -> None:
    # The Language tab owns that measure; publishing both would double-count one
    # phenomenon inside a single BH family.
    labels = {code: code.replace("_", " ").title() for code in (*DEDUCTIVE_EXCLUDED, "statistics_interaction")}
    positives = {"deductive": {code: {1} for code in labels}}
    pool = set(iter_candidate_ids(positives, labels))
    for code in DEDUCTIVE_EXCLUDED:
        assert f"topics-deductive-{code}" not in pool
    assert "topics-deductive-statistics_interaction" in pool


def test_every_finding_cites_the_method_footnote() -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    per_window = run(msgs, axis=TWO_SEMESTERS)
    for entry in per_window.values():
        for finding in entry.findings:  # type: ignore[attr-defined]
            assert "trend_method" in finding.footnote_ids


def test_titles_name_the_measure_and_its_direction() -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    findings = run(msgs, axis=TWO_SEMESTERS)["2025W"].findings  # type: ignore[attr-defined]
    german = next((f for f in findings if f.id == "language-de-share"), None)
    if german is not None:
        assert german.title == "German share of messages fell"
        assert german.delta < 0


@pytest.mark.parametrize("floor", [1, 3, 5])
def test_no_published_side_ever_falls_below_the_floor(floor: int) -> None:
    ids = Ids()
    msgs = language_shift(ids, TWO_SEMESTERS)
    per_window = run(msgs, axis=TWO_SEMESTERS, floor_n=floor)
    for entry in per_window.values():
        for finding in entry.findings:  # type: ignore[attr-defined]
            assert finding.current.n_students >= floor
            assert finding.baseline.n_students >= floor
            for point in finding.trajectory or ():
                assert point.n_students >= floor
