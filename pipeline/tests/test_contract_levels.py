"""Program-level split + enrollment block (schema 1.7.0, D-55).

The split's whole promise is that a level slice is the *same* computation over a subset,
so these tests mostly prove sameness: the same bin edges, the same floor, the same
definitions. What they guard against is a future refactor that gives one section its own
private notion of a program level or a daypart.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pathlib

import pytest
from pydantic import ValidationError

from statsboteval_pipeline.aggregate import build_aggregates, read_cohort_totals
from statsboteval_pipeline.contract import (
    Aggregates,
    Enrollment,
    EnrollmentEntry,
    STATUS_KEYS,
    dump_doc,
)
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.fixtures import seed_synthetic, seed_synthetic_labels


@pytest.fixture(scope="module")
def doc(tmp_path_factory: pytest.TempPathFactory) -> Aggregates:
    path = tmp_path_factory.mktemp("levels") / "corpus.duckdb"
    con = open_corpus(path)
    seed_synthetic(con, weeks=40, seed=7)
    seed_synthetic_labels(con, seed=7)
    return build_aggregates(
        con,
        floor_n=3,
        now=datetime.now(timezone.utc),
        provenance="synthetic",
        pipeline_version="test",
        classification_version="statsboteval-v2",
        enrollment=Enrollment(
            per_window={
                "2026S": EnrollmentEntry(
                    bachelor=900, master=600, source="synthetic", as_of=date(2026, 3, 1)
                )
            }
        ),
    )


def test_every_section_publishes_the_split(doc: Aggregates) -> None:
    """A level filter that reaches four tabs and not the fifth is worse than none."""
    s = doc.sections
    assert s.temporal_usage is not None and s.usage_context is not None
    assert s.sessions is not None and s.per_student is not None and s.language is not None
    window = next(iter(s.usage_context.per_window))
    assert s.temporal_usage.per_window[window].by_status
    assert s.temporal_usage.weekly_by_status
    assert s.usage_context.per_window[window].by_status
    assert s.sessions.per_window[window].by_status
    assert s.per_student.per_window[window].by_status
    assert s.language.per_window[window].by_status
    assert s.language.weekly_by_status


def test_levels_agree_across_sections(doc: Aggregates) -> None:
    """One window, one set of levels — a message's level cannot depend on which tab reads it."""
    s = doc.sections
    assert s.usage_context is not None and s.temporal_usage is not None
    assert s.sessions is not None and s.per_student is not None and s.language is not None
    for window, entry in s.usage_context.per_window.items():
        expected = set(entry.by_status or {})
        assert set(s.temporal_usage.per_window[window].by_status or {}) == expected
        assert set(s.sessions.per_window[window].by_status or {}) == expected
        assert set(s.per_student.per_window[window].by_status or {}) == expected
        assert set(s.language.per_window[window].by_status or {}) == expected


def test_level_messages_sum_to_the_window_total(doc: Aggregates) -> None:
    """Messages partition exactly across levels (students do not — transitioners overlap).

    This is also the arithmetic behind the deferred secondary-suppression gap: the sum
    holding is precisely what makes a lone suppressed level recoverable by subtraction.
    """
    usage = doc.sections.usage_context
    assert usage is not None
    for entry in usage.per_window.values():
        if not entry.by_status or entry.totals.messages.status != "ok":
            continue
        parts = [b.messages for b in entry.by_status.values()]
        if any(p.status != "ok" for p in parts):
            continue
        assert sum(p.value for p in parts if p.status == "ok") == entry.totals.messages.value


def test_split_reuses_the_cohort_wide_shapes(doc: Aggregates) -> None:
    """Same bin edges and same daypart ids: a level is a subset, not a second design."""
    per_student, sessions, temporal = (
        doc.sections.per_student,
        doc.sections.sessions,
        doc.sections.temporal_usage,
    )
    assert per_student is not None and sessions is not None and temporal is not None
    for window, entry in per_student.per_window.items():
        edges = [(b.lo, b.hi) for b in entry.messages_per_student.bins]
        for level in (entry.by_status or {}).values():
            assert [(b.lo, b.hi) for b in level.messages_per_student.bins] == edges
    for window, sess in sessions.per_window.items():
        edges = [(b.lo, b.hi) for b in sess.session_duration_minutes.bins]
        for level in (sess.by_status or {}).values():
            assert [(b.lo, b.hi) for b in level.session_duration_minutes.bins] == edges
    for window, temp in temporal.per_window.items():
        assert temp.daypart_totals is not None
        ids = set(temp.daypart_totals.by_daypart)
        for level in (temp.by_status or {}).values():
            assert set(level.daypart_totals.by_daypart) == ids


def test_by_status_omits_the_unrendered_hour_grid(doc: Aggregates) -> None:
    """44 KB per copy for a grid nothing draws (D-54); the split is the part that renders."""
    temporal = doc.sections.temporal_usage
    assert temporal is not None
    for entry in temporal.per_window.values():
        for level in (entry.by_status or {}).values():
            assert not hasattr(level, "activity_heatmap")


def test_unknown_level_key_is_refused(doc: Aggregates) -> None:
    """One root-level walk catches a stray key in ANY by_status map, not just topics'."""
    dumped = dump_doc(doc)
    window = next(iter(dumped["sections"]["language"]["per_window"]))
    entry = dumped["sections"]["language"]["per_window"][window]
    entry["by_status"]["doktorat"] = entry["by_status"][next(iter(entry["by_status"]))]
    with pytest.raises(ValidationError, match="unknown program level"):
        Aggregates.model_validate(dumped)
    assert "doktorat" not in STATUS_KEYS


def test_per_level_weekly_series_stay_dense(doc: Aggregates) -> None:
    """The client slices these with the same code as the cohort-wide ones, so a short
    per-level series would silently start a trend line late rather than fail."""
    temporal = doc.sections.temporal_usage
    assert temporal is not None and temporal.weekly_by_status is not None
    expected = [e.week for e in temporal.weekly.messages.series]
    for weekly in temporal.weekly_by_status.values():
        assert [e.week for e in weekly.messages.series] == expected
        assert [e.week for e in weekly.active_students.series] == expected


def test_enrollment_is_semester_only(doc: Aggregates) -> None:
    """all_time spans cohort turnover, so it has no defensible denominator and may not
    carry one. A semester slice may not either, for the opposite reason: it lies inside one
    term, so it reads that term's entry through parent_window_id rather than duplicating
    the headcount under a second key (D-56)."""
    assert doc.enrollment is not None
    semesters = {w.id for w in doc.windows if w.kind == "semester"}
    assert set(doc.enrollment.per_window) <= semesters

    dumped = dump_doc(doc)
    dumped["enrollment"]["per_window"]["all_time"] = {
        "bachelor": 1, "master": 1, "source": "x", "as_of": "2026-03-01",
    }
    with pytest.raises(ValidationError, match="not a semester window"):
        Aggregates.model_validate(dumped)


def test_enrollment_clips_to_the_built_registry(tmp_path: pytest.TempPathFactory) -> None:
    """The table is maintained by hand and outlives any one axis, so a stale semester in
    it must not become a window id the registry never heard of."""
    con = open_corpus(pathlib.Path(str(tmp_path)) / "clip.duckdb")
    seed_synthetic(con, weeks=20, seed=11)
    built = build_aggregates(
        con,
        floor_n=3,
        now=datetime.now(timezone.utc),
        provenance="synthetic",
        pipeline_version="test",
        enrollment=Enrollment(
            per_window={
                "1999S": EnrollmentEntry(
                    bachelor=1, master=1, source="stale", as_of=date(1999, 3, 1)
                )
            }
        ),
    )
    assert built.enrollment is not None
    assert "1999S" not in built.enrollment.per_window


def test_committed_cohort_totals_load() -> None:
    """The real table parses and covers the semesters the dashboard publishes reach for."""
    enrollment = read_cohort_totals()
    assert enrollment is not None
    assert set(enrollment.per_window) >= {"2025S", "2025W", "2026S"}
    for entry in enrollment.per_window.values():
        assert entry.bachelor > 0 and entry.master > 0
        assert "SSC-Psych" in entry.source


def test_a_1_6_0_document_still_validates(doc: Aggregates) -> None:
    """Additive bump (contract §10): drop every 1.7.0 field and the document stays legal."""
    dumped = dump_doc(doc)
    dumped.pop("enrollment", None)
    dumped["sections"]["temporal_usage"].pop("weekly_by_status", None)
    dumped["sections"]["language"].pop("weekly_by_status", None)
    for name in ("temporal_usage", "usage_context", "sessions", "per_student", "language"):
        for entry in dumped["sections"][name]["per_window"].values():
            entry.pop("by_status", None)
    dumped["schema_version"] = "1.6.0"
    Aggregates.model_validate(dumped)
