"""SYNTHETIC fixture factory — no real student data, ever (repo policy)."""

from datetime import date, datetime, timezone

from statsboteval_pipeline.contract import (
    Aggregates,
    AllTimeWindow,
    Daypart,
    DaypartCell,
    DaypartGrid,
    DaypartTotals,
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
    PerStudentSection,
    PerStudentWindow,
    SCHEMA_VERSION,
    Sections,
    SemesterProfile,
    SemesterProfilePoint,
    SemesterWindow,
    SessionsSection,
    SessionsWindow,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    TrailingWindow,
    TrendsSection,
    TrendsWindow,
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
    "weeks_active_window": Footnote(text="Weeks active counts only the weeks inside the selected window."),
    "trend_method": Footnote(text="Findings are selected by relevance among changes that cleared a noise gate."),
    "cohort_turnover": Footnote(text="Each semester draws a largely different cohort of students."),
    "daypart_definition": Footnote(text="Vienna local time, four equal six-hour blocks; bars are comparable."),
    "semester_week_alignment": Footnote(text="Week 1 is the semester's first ISO week; compare shape, not height."),
}

# Mirrors aggregate.DAYPARTS — the fixture must publish the same registry the pipeline does,
# or the design fixture and the real document disagree about what a bar means.
DAYPARTS = [
    Daypart(id="night", label="Night", from_hour=0, to_hour=6),
    Daypart(id="morning", label="Morning", from_hour=6, to_hour=12),
    Daypart(id="afternoon", label="Afternoon", from_hour=12, to_hour=18),
    Daypart(id="evening", label="Evening", from_hour=18, to_hour=24),
]


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


def daypart_grid() -> DaypartGrid:
    """Sunday night suppressed, so the design fixture exercises the striped cell."""
    cells = [
        DaypartCell(
            dow=d,
            daypart=p.id,
            cell=suppressed() if (d == 7 and p.id == "night") else ok((d * (i + 2)) % 17),
        )
        for d in range(1, 8)
        for i, p in enumerate(DAYPARTS)
    ]
    return DaypartGrid(cells=cells, footnote_ids=["daypart_definition"])


def daypart_totals() -> DaypartTotals:
    return DaypartTotals(
        by_daypart={"night": ok(12), "morning": ok(118), "afternoon": ok(214), "evening": ok(68)},
        weekend=ok(94),
        weekday=ok(318),
        footnote_ids=["daypart_definition"],
    )


def semester_profiles() -> list[SemesterProfile]:
    """2025S runs W10-W26 but the fixture axis is W11-W14, so the profile starts at
    semester_week 2 and stops at 5 — the partial-coverage path the real July break hits."""
    values = [(2, "2025-W11", 41, 12), (3, "2025-W12", None, None), (4, "2025-W13", 0, 0), (5, "2025-W14", 87, 19)]
    return [
        SemesterProfile(
            window_id="2025S",
            label="Summer semester 2025",
            kind="summer",
            points=[
                SemesterProfilePoint(
                    semester_week=i,
                    week=w,
                    messages=suppressed() if msgs is None else ok(msgs),
                    active_students=suppressed() if students is None else ok(students),
                )
                for i, w, msgs, students in values
            ],
            footnote_ids=["semester_week_alignment", "cohort_turnover"],
        )
    ]


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


def trends() -> TrendsSection:
    """A trends section shaped the way this 4-week axis would really produce one.

    The axis covers a single semester, so `all_time` has no earlier semester to plot a
    trajectory against and `2025S` has no predecessor at all — both carry `baseline: null`,
    which is also what exercises the TrendsWindow serializer that reinstates the null.
    Trajectories need two semesters and are exercised by the multi-semester dev fixture.
    """
    return TrendsSection(
        per_window={
            "all_time": TrendsWindow(baseline=None),
            "2025S": TrendsWindow(baseline=None),
            "trailing_4": TrendsWindow(
                baseline={"kind": "weeks", "from": "2025-W11", "through": "2025-W12"},
                findings=[
                    {
                        "id": "language-de-share",
                        "tab": "language",
                        "title": "German share of messages fell",
                        "measure": "German share of messages",
                        "kind": "share",
                        "unit": "% of messages",
                        "current": {"value": 48.1, "n_students": 12},
                        "baseline": {"value": 61.8, "n_students": 9},
                        "delta": -13.7,
                        "evidence": "robust",
                        "method": "two-proportion z, BH-adjusted",
                        "footnote_ids": ["trend_method", "language_heuristic"],
                    },
                    {
                        "id": "engagement-messages-per-session",
                        "tab": "engagement",
                        "title": "Messages per conversation rose",
                        "measure": "Median messages per conversation",
                        "kind": "median",
                        "unit": "messages",
                        "current": {"value": 3.0, "n_students": 12},
                        "baseline": {"value": 2.0, "n_students": 9},
                        "delta": 1.0,
                        "evidence": "indicative",
                        "method": "Mann-Whitney U (normal approximation)",
                        "footnote_ids": ["trend_method", "chat_fragmentation"],
                    },
                ],
            ),
        }
    )


def window_totals() -> UsageContextTotals:
    return UsageContextTotals(active_students=ok(58), messages=ok(412), sessions=ok(163), new_registrations=ok(21))


def make_synthetic_aggregates() -> Aggregates:
    per_window_temporal = {
        wid: TemporalUsageWindow(
            activity_heatmap=grid(), daypart_heatmap=daypart_grid(), daypart_totals=daypart_totals()
        )
        for wid in WINDOW_IDS
    }
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
    per_window_per_student = {
        wid: PerStudentWindow(
            sessions_per_student=histogram("students", ["chat_fragmentation"]),
            weeks_active_per_student=histogram("students", ["weeks_active_window"]),
            messages_per_student=histogram("students"),
        )
        for wid in WINDOW_IDS
    }
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
                kind="trailing", id="trailing_4", label="Last Avl. 4 weeks",
                weeks=WEEKS, coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
        ],
        dayparts=DAYPARTS,
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=series([41, None, 0, 87]),
                    sessions=series([18, None, 0, 33], ["chat_fragmentation"]),
                    active_students=series([12, None, 0, 19], ["bachelor_onboarding"]),
                ),
                per_window=per_window_temporal,
                semester_profiles=semester_profiles(),
            ),
            usage_context=UsageContext(
                weekly=UsageContextWeekly(registrations=series([9, 4, 0, None])),
                per_window=per_window_usage,
            ),
            sessions=SessionsSection(per_window=per_window_sessions),
            per_student=PerStudentSection(per_window=per_window_per_student),
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
            trends=trends(),
        ),
    )
