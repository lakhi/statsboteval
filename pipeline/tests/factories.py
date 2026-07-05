"""SYNTHETIC fixture factory — no real student data, ever (repo policy)."""

from datetime import date, datetime, timezone

from statsboteval_pipeline.contract import (
    Aggregates,
    AllTimeWindow,
    Footnote,
    HeatmapCell,
    HeatmapGrid,
    Histogram,
    HistogramBin,
    LanguageSection,
    LanguageTotals,
    LanguageWeekly,
    LanguageWindow,
    MessagesByLanguage,
    SCHEMA_VERSION,
    Sections,
    SemesterWindow,
    SessionsSection,
    SessionsWindow,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    TokensSection,
    TokensWindow,
    TrailingWindow,
    UsageContext,
    UsageContextTotals,
    UsageContextWeekly,
    UsageContextWindow,
    UserClasses,
    WeeklyEntry,
    WeeklySeries,
    ok,
    suppressed,
    weeks_range,
)

WEEKS = ["2025-W11", "2025-W12", "2025-W13", "2025-W14"]
WINDOW_IDS = ("all_time", "2025S", "trailing_4")

FOOTNOTES = {
    "chat_fragmentation": Footnote(text="The credit-limit UI nudges students toward starting new chats."),
    "bachelor_onboarding": Footnote(text="Bachelor students had access only from 16 May 2025."),
    "language_heuristic": Footnote(text="Language detected locally by a statistical heuristic (lang-heuristic-v1)."),
    "user_class_definitions": Footnote(text="One-time/monthly/sporadic per the Bergmann Stage-2 definitions."),
    "duration_definition": Footnote(text="Duration = last minus first server timestamp; single-message sessions = 0."),
}


def series(values: list[int | None], footnote_ids: list[str] | None = None) -> WeeklySeries:
    entries = [
        WeeklyEntry(week=w, cell=suppressed() if v is None else ok(v)) for w, v in zip(WEEKS, values, strict=True)
    ]
    return WeeklySeries(series=entries, footnote_ids=footnote_ids)


def grid() -> HeatmapGrid:
    cells = [
        HeatmapCell(dow=d, hour=h, cell=suppressed() if (d == 7 and h < 6) else ok((d * h) % 9))
        for d in range(1, 8)
        for h in range(24)
    ]
    return HeatmapGrid(cells=cells)


def histogram(unit: str, footnote_ids: list[str] | None = None) -> Histogram:
    return Histogram(
        unit=unit,
        bins=[
            HistogramBin(lo=1, hi=1, cell=ok(214)),
            HistogramBin(lo=2, hi=3, cell=ok(96)),
            HistogramBin(lo=4, hi=7, cell=suppressed()),
            HistogramBin(lo=8, hi=None, cell=ok(11)),
        ],
        n_total=ok(327),
        summary={"status": "ok", "n_students": 74, "median": 2.0, "p25": 1.0, "p75": 4.0, "mean": 2.4, "sd": 2.1},
        footnote_ids=footnote_ids,
    )


def window_totals() -> UsageContextTotals:
    return UsageContextTotals(active_students=ok(58), messages=ok(412), sessions=ok(163), new_registrations=ok(21))


def make_synthetic_aggregates() -> Aggregates:
    per_window_temporal = {wid: TemporalUsageWindow(activity_heatmap=grid()) for wid in WINDOW_IDS}
    per_window_usage = {
        wid: UsageContextWindow(
            totals=window_totals(),
            user_classes=UserClasses(
                one_time=ok(31), monthly=ok(6), sporadic=ok(21), footnote_ids=["user_class_definitions"]
            ),
        )
        for wid in WINDOW_IDS
    }
    per_window_sessions = {
        wid: SessionsWindow(
            messages_per_session=histogram("sessions", ["chat_fragmentation"]),
            session_duration_minutes=histogram("sessions", ["chat_fragmentation", "duration_definition"]),
        )
        for wid in WINDOW_IDS
    }
    per_window_tokens = {wid: TokensWindow(completion_tokens_per_message=histogram("messages")) for wid in WINDOW_IDS}
    per_window_language = {
        wid: LanguageWindow(totals=LanguageTotals(de=ok(280), en=ok(120), other=ok(0), undetermined=suppressed()))
        for wid in WINDOW_IDS
    }
    return Aggregates(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime(2025, 4, 7, 5, 0, tzinfo=timezone.utc),
        data_through_week="2025-W14",
        data_through_date=date(2025, 4, 6),
        first_week="2025-W11",
        privacy_floor_n=3,
        label_versions={"language": "lang-heuristic-v1"},
        timezone="Europe/Vienna",
        data_provenance="synthetic",
        pipeline_version="0.1.0",
        windows=[
            AllTimeWindow(
                kind="all_time", id="all_time", label="All time",
                coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
            SemesterWindow(
                kind="semester", id="2025S", label="Summer semester 2025",
                start_date=date(2025, 3, 1), end_date=date(2025, 6, 30),
                weeks=weeks_range("2025-W10", "2025-W26"),
                coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
            TrailingWindow(
                kind="trailing", id="trailing_4", label="Last 4 weeks",
                weeks=WEEKS, coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
        ],
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=series([41, None, 0, 87]),
                    sessions=series([18, None, 0, 33], ["chat_fragmentation"]),
                    active_students=series([12, None, 0, 19], ["bachelor_onboarding"]),
                ),
                per_window=per_window_temporal,
            ),
            usage_context=UsageContext(
                weekly=UsageContextWeekly(registrations=series([9, 4, 0, None])),
                per_window=per_window_usage,
            ),
            sessions=SessionsSection(per_window=per_window_sessions),
            tokens=TokensSection(per_window=per_window_tokens),
            language=LanguageSection(
                weekly=LanguageWeekly(
                    messages_by_language=MessagesByLanguage(
                        de=series([30, None, 0, 60]),
                        en=series([11, None, 0, 27]),
                        other=series([0, 0, 0, 0]),
                        undetermined=series([0, None, 0, 0]),
                        footnote_ids=["language_heuristic"],
                    )
                ),
                per_window=per_window_language,
            ),
        ),
    )
