from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    Aggregates,
    AllTimeWindow,
    Footnote,
    Sections,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    HeatmapCell,
    HeatmapGrid,
    WeeklyEntry,
    WeeklySeries,
    ok,
)

WEEKS = ["2025-W11", "2025-W12"]


def series(footnote_ids: list[str] | None = None) -> WeeklySeries:
    return WeeklySeries(series=[WeeklyEntry(week=w, cell=ok(3)) for w in WEEKS], footnote_ids=footnote_ids)


def grid() -> HeatmapGrid:
    return HeatmapGrid(cells=[HeatmapCell(dow=d, hour=h, cell=ok(0)) for d in range(1, 8) for h in range(24)])


def minimal_doc(**overrides) -> dict:
    base = dict(
        schema_version="1.0.0",
        generated_at=datetime(2025, 3, 24, 5, 0, tzinfo=timezone.utc),
        data_through_week="2025-W12",
        data_through_date=date(2025, 3, 23),
        first_week="2025-W11",
        privacy_floor_n=3,
        label_versions={"language": "lang-heuristic-v1"},
        timezone="Europe/Vienna",
        data_provenance="synthetic",
        pipeline_version="0.1.0",
        windows=[
            AllTimeWindow(
                kind="all_time", id="all_time", label="All time",
                coverage={"from": "2025-W11", "through": "2025-W12"},
            )
        ],
        footnotes={"chat_fragmentation": Footnote(text="Credit UI nudges new chats.")},
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=series(),
                    sessions=series(footnote_ids=["chat_fragmentation"]),
                    active_students=series(),
                ),
                per_window={"all_time": TemporalUsageWindow(activity_heatmap=grid())},
            )
        ),
    )
    base.update(overrides)
    return base


def test_valid_document_parses() -> None:
    agg = Aggregates(**minimal_doc())
    assert agg.privacy_floor_n == 3


def test_data_through_date_must_be_sunday_of_week() -> None:
    with pytest.raises(ValidationError, match="Sunday"):
        Aggregates(**minimal_doc(data_through_date=date(2025, 3, 22)))


def test_unknown_window_key_rejected() -> None:
    doc = minimal_doc()
    doc["sections"].temporal_usage.per_window["2099S"] = TemporalUsageWindow(activity_heatmap=grid())
    with pytest.raises(ValidationError, match="unknown window"):
        Aggregates(**doc)


def test_unknown_footnote_id_rejected() -> None:
    doc = minimal_doc(footnotes={})
    with pytest.raises(ValidationError, match="unknown footnote"):
        Aggregates(**doc)


def test_sparse_weekly_series_rejected() -> None:
    sparse = WeeklySeries(series=[WeeklyEntry(week="2025-W11", cell=ok(3))])
    doc = minimal_doc()
    doc["sections"].temporal_usage.weekly.messages = sparse
    with pytest.raises(ValidationError, match="dense"):
        Aggregates(**doc)


def test_naive_generated_at_rejected() -> None:
    with pytest.raises(ValidationError):
        Aggregates(**minimal_doc(generated_at=datetime(2025, 3, 24, 5, 0)))
