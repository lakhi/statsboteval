"""Trends section (schema 1.3.0, additive — D-49).

Findings are the one published shape with no suppressed state: sub-floor candidates are
dropped before publication rather than marked. That makes the floor a *document-level*
check rather than something floored_count() guarantees construction-side, so most of
these tests exercise Aggregates._check_trends rather than the leaf models.
"""

import json

import jsonschema
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    Aggregates,
    Finding,
    MeasureValue,
    TrajectoryPoint,
    TrendsSection,
    TrendsWindow,
    dump_doc,
)
from statsboteval_pipeline.export_schema import generate_schema
from tests.factories import make_synthetic_aggregates


def measure(value: float = 48.1, n_students: int = 74) -> MeasureValue:
    return MeasureValue(value=value, n_students=n_students)


def finding(
    *,
    slug: str = "language-de-share",
    tab: str = "language",
    current: MeasureValue | None = None,
    baseline: MeasureValue | None = None,
    trajectory: list[TrajectoryPoint] | None = None,
) -> Finding:
    return Finding(
        id=slug,
        tab=tab,
        title="German share of messages fell",
        measure="German share of messages",
        kind="share",
        unit="% of messages",
        current=current or measure(),
        baseline=baseline or measure(61.8, 91),
        delta=-13.7,
        evidence="robust",
        method="two-proportion z, BH-adjusted",
        trajectory=trajectory,
        footnote_ids=["language_heuristic"],
    )


def window(**kwargs: object) -> TrendsWindow:
    kwargs.setdefault("baseline", {"kind": "window", "window_id": "2025S"})
    return TrendsWindow(**kwargs)  # type: ignore[arg-type]


def with_trends(doc: Aggregates, trends: TrendsSection) -> Aggregates:
    # Rebuild via model_validate so the cross-document validator runs (model_copy skips it).
    dumped = dump_doc(doc)
    dumped["sections"]["trends"] = dump_doc(trends)
    return Aggregates.model_validate(dumped)


def trends_for(doc: Aggregates, entry: TrendsWindow) -> TrendsSection:
    return TrendsSection(per_window={w.id: entry for w in doc.windows})


# --- additive-bump proofs -------------------------------------------------------------


def test_absent_trends_section_still_valid() -> None:
    # A 1.2.0-shaped document must remain valid under 1.3.0 (invariant 5, §10). The
    # factory carries a trends section now, so the absence is constructed explicitly
    # rather than inherited — this asserts the *optionality*, not the factory's contents.
    doc = make_synthetic_aggregates()
    doc = doc.model_copy(update={"sections": doc.sections.model_copy(update={"trends": None})})
    Aggregates.model_validate(dump_doc(doc))
    assert "trends" not in dump_doc(doc)["sections"]


def test_document_with_trends_matches_exported_schema() -> None:
    doc = with_trends(
        make_synthetic_aggregates(), trends_for(make_synthetic_aggregates(), window(findings=[finding()]))
    )
    jsonschema.validate(json.loads(json.dumps(dump_doc(doc))), generate_schema())


# --- the exclude_none trap ------------------------------------------------------------


def test_null_baseline_survives_exclude_none() -> None:
    # dump_doc excludes None, but null IS the "no predecessor" marker the dashboard
    # branches on — TrendsWindow._serialize must reinstate it (cf. HistogramBin.hi).
    doc = with_trends(make_synthetic_aggregates(), trends_for(make_synthetic_aggregates(), TrendsWindow()))
    entry = dump_doc(doc)["sections"]["trends"]["per_window"]["2025S"]
    assert "baseline" in entry
    assert entry["baseline"] is None


def test_present_baseline_dumps_normally() -> None:
    entry = dump_doc(window(findings=[finding()]))
    assert entry["baseline"] == {"kind": "window", "window_id": "2025S"}


# --- window-level coherence -----------------------------------------------------------


def test_findings_require_a_baseline() -> None:
    with pytest.raises(ValidationError, match="findings require a baseline"):
        TrendsWindow(baseline=None, findings=[finding()])


def test_insufficient_data_requires_a_baseline() -> None:
    with pytest.raises(ValidationError, match="insufficient_data is meaningless"):
        TrendsWindow(baseline=None, insufficient_data=True)


def test_insufficient_data_excludes_findings() -> None:
    # "nothing was testable" and "here is what changed" are mutually exclusive claims.
    with pytest.raises(ValidationError, match="must be false when findings are published"):
        window(insufficient_data=True, findings=[finding()])


def test_insufficient_data_with_empty_findings_is_the_break_week_state() -> None:
    entry = window(insufficient_data=True)
    assert entry.findings == []
    assert dump_doc(entry)["insufficient_data"] is True


# --- caps -----------------------------------------------------------------------------


def test_topics_may_publish_three_findings() -> None:
    entry = window(findings=[finding(slug=f"topics-{i}", tab="topics") for i in range(3)])
    assert len(entry.findings) == 3


def test_topics_cap_is_three() -> None:
    with pytest.raises(ValidationError, match="at most 3 findings from tab 'topics'"):
        window(findings=[finding(slug=f"topics-{i}", tab="topics") for i in range(4)])


def test_other_tabs_cap_at_two() -> None:
    with pytest.raises(ValidationError, match="at most 2 findings from tab 'language'"):
        window(findings=[finding(slug=f"language-{i}") for i in range(3)])


def test_overall_cap_is_five() -> None:
    findings = [finding(slug=f"topics-{i}", tab="topics") for i in range(3)]
    findings += [finding(slug=f"timing-{i}", tab="timing") for i in range(2)]
    findings += [finding(slug="language-0")]
    with pytest.raises(ValidationError):
        window(findings=findings)


# --- the floor ------------------------------------------------------------------------


@pytest.mark.parametrize("side", ["current", "baseline"])
def test_sub_floor_side_is_rejected(side: str) -> None:
    # floor_n is 3 in the factory; 2 passes the leaf model (ge=1) and must fail the doc.
    doc = make_synthetic_aggregates()
    entry = window(findings=[finding(**{side: measure(1.0, 2)})])  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match=f"side {side} has n_students=2 below the floor"):
        with_trends(doc, trends_for(doc, entry))


def test_sub_floor_trajectory_point_is_rejected() -> None:
    doc = make_synthetic_aggregates()
    entry = TrendsWindow(
        baseline={"kind": "trajectory"},
        findings=[
            finding(
                trajectory=[
                    TrajectoryPoint(window_id="2025S", value=68.2, n_students=88),
                    TrajectoryPoint(window_id="2025S", value=61.8, n_students=2),
                ]
            )
        ],
    )
    with pytest.raises(ValidationError, match="below the floor"):
        with_trends(doc, TrendsSection(per_window={"all_time": entry}))


# --- registry references --------------------------------------------------------------


def test_baseline_must_reference_a_published_window() -> None:
    doc = make_synthetic_aggregates()
    entry = TrendsWindow(baseline={"kind": "window", "window_id": "2024W"}, findings=[finding()])
    with pytest.raises(ValidationError, match="references unknown window '2024W'"):
        with_trends(doc, trends_for(doc, entry))


def test_trajectory_point_must_reference_a_published_window() -> None:
    doc = make_synthetic_aggregates()
    entry = TrendsWindow(
        baseline={"kind": "trajectory"},
        findings=[finding(trajectory=[TrajectoryPoint(window_id="2024W", value=68.2, n_students=88)])],
    )
    with pytest.raises(ValidationError, match="trajectory references unknown window '2024W'"):
        with_trends(doc, TrendsSection(per_window={"all_time": entry}))


def test_weeks_baseline_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="baseline.from must not be after"):
        TrendsWindow(baseline={"kind": "weeks", "from": "2026-W24", "through": "2026-W21"})


# --- trajectories ---------------------------------------------------------------------


def test_trajectory_requires_a_trajectory_baseline() -> None:
    with pytest.raises(ValidationError, match="carries a trajectory without a trajectory baseline"):
        window(findings=[finding(trajectory=[TrajectoryPoint(window_id="2025S", value=68.2, n_students=88)])])


def test_trajectory_baseline_requires_trajectories() -> None:
    with pytest.raises(ValidationError, match="must carry a trajectory under a trajectory baseline"):
        TrendsWindow(baseline={"kind": "trajectory"}, findings=[finding()])


def test_trajectory_baseline_belongs_only_to_all_time() -> None:
    doc = make_synthetic_aggregates()
    entry = TrendsWindow(
        baseline={"kind": "trajectory"},
        findings=[finding(trajectory=[TrajectoryPoint(window_id="2025S", value=68.2, n_students=88)])],
    )
    with pytest.raises(ValidationError, match="a trajectory baseline belongs only to the all_time window"):
        with_trends(doc, TrendsSection(per_window={"2025S": entry}))
