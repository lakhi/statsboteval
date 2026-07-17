"""Weekly aggregation + privacy floor -> the contract document.

The floor (contract invariant 1) is applied in exactly one place: floored_count()
(plus its summary-stats sibling _summary()). No other code may turn corpus
numbers into cells. ISO-week bucketing happens in Python after
UTC->Europe/Vienna conversion — calendar knowledge lives here, not in SQL
(matching the contract's semester principle).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import duckdb

from .contract import (
    Aggregates,
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
    OkCell,
    OkSummaryStats,
    SCHEMA_VERSION,
    Sections,
    SessionsSection,
    SessionsWindow,
    SummaryStats,
    SuppressedCell,
    SuppressedSummaryStats,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    TokensSection,
    TokensWindow,
    UsageContext,
    UsageContextTotals,
    UsageContextWeekly,
    UsageContextWindow,
    UserClasses,
    WeeklyEntry,
    WeeklySeries,
    Window,
    date_to_week,
    ok,
    suppressed,
    week_monday,
    week_sunday,
    weeks_range,
)
from .language import LABEL_VERSION as LANGUAGE_LABEL_VERSION
from .windows import build_windows

VIENNA = ZoneInfo("Europe/Vienna")

LANGUAGE_CODES = ("de", "en", "other", "undetermined")

# Fixed bin edges, pinned to the design fixture the dashboard was built against.
MESSAGES_PER_SESSION_BINS: list[tuple[int, int | None]] = [(1, 1), (2, 3), (4, 7), (8, None)]
SESSION_DURATION_BINS: list[tuple[int, int | None]] = [(0, 1), (2, 5), (6, 15), (16, 30), (31, None)]
COMPLETION_TOKENS_BINS: list[tuple[int, int | None]] = [(0, 100), (101, 250), (251, 500), (501, 1000), (1001, None)]

# Footnote catalog texts are pinned in docs/aggregates-contract.md §6.2.
FOOTNOTES = {
    "chat_fragmentation": Footnote(
        text="The credit-limit UI nudges students toward starting new chats; "
        "conversation counts may overstate distinct dialogues."
    ),
    "bachelor_onboarding": Footnote(
        text="The bachelor cohort exists only from 2025-05-16; trends crossing "
        "that boundary partly reflect cohort composition, not behavior."
    ),
    "language_heuristic": Footnote(
        text="Language is detected by a local heuristic (lang-heuristic-v1); "
        "very short or mixed-language messages may be misclassified."
    ),
    "user_class_definitions": Footnote(
        text="One-time / monthly / sporadic follow the Bergmann et al. Stage-2 operational definitions."
    ),
    "duration_definition": Footnote(
        text="Session duration = last minus first server timestamp in the session; "
        "single-message sessions count as 0 minutes."
    ),
}


def floored_count(value: int, n_students: int, floor_n: int) -> OkCell | SuppressedCell:
    """The one and only construction path from corpus numbers to a published cell."""
    if value < 0 or n_students < 0 or floor_n < 1:
        raise ValueError(f"invalid floor inputs: value={value} n_students={n_students} floor_n={floor_n}")
    if value > 0 and n_students == 0:
        raise ValueError(f"incoherent cell: value={value} with no contributing students")
    if n_students == 0 or n_students >= floor_n:
        return ok(value)
    return suppressed()


def _quantile_type2(sorted_vals: list[float], p: float) -> float:
    """R quantile type 2 — the estimator the Bergmann reference scripts use."""
    n = len(sorted_vals)
    h = n * p + 0.5
    lo = min(max(math.ceil(h - 0.5), 1), n)
    hi = min(max(math.floor(h + 0.5), 1), n)
    return (sorted_vals[lo - 1] + sorted_vals[hi - 1]) / 2


def _summary(
    values: list[float], students: set[str], floor_n: int, *, with_mean_sd: bool = True
) -> SummaryStats | None:
    """Summary stats under the same floor as cells; None when there is nothing to summarize."""
    if not values:
        return None
    if len(students) < floor_n:
        return SuppressedSummaryStats(status="suppressed")
    vals = sorted(values)
    mean = sd = None
    if with_mean_sd:
        mean = round(sum(vals) / len(vals), 1)
        if len(vals) > 1:
            sd = round(math.sqrt(sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / (len(vals) - 1)), 1)
    return OkSummaryStats(
        status="ok",
        n_students=len(students),
        median=round(_quantile_type2(vals, 0.5), 1),
        p25=round(_quantile_type2(vals, 0.25), 1),
        p75=round(_quantile_type2(vals, 0.75), 1),
        mean=mean,
        sd=sd,
    )


@dataclass(frozen=True)
class _Message:
    pseudonym: str
    session: tuple[str, int]
    local: datetime  # Europe/Vienna
    week: str
    completion_tokens: int
    lang: str


@dataclass(frozen=True)
class _Session:
    pseudonym: str
    week: str  # week of the first message (D-08)
    n_messages: int
    duration_minutes: float


def _histogram(
    unit: str,
    edges: list[tuple[int, int | None]],
    items: list[tuple[int, float, str]],  # (bin value, summary value, pseudonym)
    floor_n: int,
    footnote_ids: list[str] | None = None,
    *,
    with_mean_sd: bool = True,
) -> Histogram:
    counts = [0] * len(edges)
    students: list[set[str]] = [set() for _ in edges]
    for bin_value, _, pseudonym in items:
        for i, (lo, hi) in enumerate(edges):
            if lo <= bin_value and (hi is None or bin_value <= hi):
                counts[i] += 1
                students[i].add(pseudonym)
                break
        else:
            raise ValueError(f"value {bin_value} fits no {unit} bin")
    all_students = {pseudonym for _, _, pseudonym in items}
    return Histogram(
        unit=unit,
        bins=[
            HistogramBin(lo=lo, hi=hi, cell=floored_count(counts[i], len(students[i]), floor_n))
            for i, (lo, hi) in enumerate(edges)
        ],
        n_total=floored_count(len(items), len(all_students), floor_n),
        summary=_summary([sv for _, sv, _ in items], all_students, floor_n, with_mean_sd=with_mean_sd),
        footnote_ids=footnote_ids,
    )


def _user_classes(user_dates: dict[str, list[datetime]], floor_n: int) -> UserClasses:
    """Bergmann Stage-2 typology (pinned operationalizations, bergmann-framework.md).

    Computed on Vienna-local timestamps for consistency with the document's
    timezone (the reference scripts used UTC; the thresholds are what is pinned).
    """
    one_time = monthly = sporadic = 0
    for stamps in user_dates.values():
        stamps = sorted(stamps)
        days = [s.date() for s in stamps]
        span_days = (days[-1] - days[0]).days + 1
        within_24h = stamps[-1] - stamps[0] <= timedelta(hours=24)
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        if span_days < 3 and within_24h:
            one_time += 1
        elif all(g < 30 for g in gaps) and span_days >= 30:
            monthly += 1
        else:
            sporadic += 1
    return UserClasses(
        one_time=floored_count(one_time, one_time, floor_n),
        monthly=floored_count(monthly, monthly, floor_n),
        sporadic=floored_count(sporadic, sporadic, floor_n),
        footnote_ids=["user_class_definitions"],
    )


def _window_weeks(window: Window, axis: list[str]) -> set[str]:
    if window.kind == "all_time":
        return set(axis)
    return set(window.weeks) & set(axis)


def build_aggregates(
    con: duckdb.DuckDBPyConnection,
    *,
    floor_n: int,
    now: datetime,
    provenance: Literal["synthetic", "production"],
    pipeline_version: str,
    axis_start: date | None = None,
) -> Aggregates:
    rows = con.execute(
        "SELECT m.pseudonym, m.session_started, m.created_at, m.completion_tokens, l.code "
        "FROM messages m LEFT JOIN labels l ON l.history_id = m.history_id "
        "  AND l.label_version = ? AND l.domain = 'language'",
        [LANGUAGE_LABEL_VERSION],
    ).fetchall()
    if not rows:
        raise ValueError("corpus has no messages; nothing to aggregate")

    # Axis: complete ISO weeks only (invariant 3). data_through_week = the last week
    # fully elapsed before `now` (extract time) in Vienna. Trailing quiet weeks were
    # measured (extraction covered them, found nothing) -> they publish as ok(0);
    # clipping them off would misencode a measured zero as "absent" (invariant 2).
    now_week_monday = week_monday(date_to_week(now.astimezone(VIENNA).date()))
    through = date_to_week(now_week_monday - timedelta(days=7))
    through_monday = week_monday(through)

    msgs: list[_Message] = []
    for pseudonym, session_started, created_at, completion_tokens, lang in rows:
        local = created_at.replace(tzinfo=timezone.utc).astimezone(VIENNA)
        if axis_start is not None and local.date() < axis_start:
            continue  # pre-launch pilot traffic stays in the corpus, out of publishes
        week = date_to_week(local.date())
        if week_monday(week) > through_monday:
            continue  # current, incomplete week
        msgs.append(
            _Message(pseudonym, (pseudonym, session_started), local, week, completion_tokens, lang or "undetermined")
        )
    if not msgs:
        raise ValueError("no corpus data within the publishable range (axis_start / complete weeks)")

    first = min(m.week for m in msgs)
    axis = weeks_range(first, through)
    windows = build_windows(axis)

    by_session: dict[tuple[str, int], list[_Message]] = defaultdict(list)
    for m in msgs:
        by_session[m.session].append(m)
    sessions = [
        _Session(
            pseudonym=key[0],
            week=min(group, key=lambda m: m.local).week,
            n_messages=len(group),
            duration_minutes=(max(m.local for m in group) - min(m.local for m in group)).total_seconds() / 60,
        )
        for key, group in by_session.items()
    ]

    registrations: list[tuple[str, str]] = []  # (pseudonym, week)
    for pseudonym, registered_at in con.execute("SELECT pseudonym, registered_at FROM students").fetchall():
        local_date = registered_at.replace(tzinfo=timezone.utc).astimezone(VIENNA).date()
        if axis_start is not None and local_date < axis_start:
            continue
        registrations.append((pseudonym, date_to_week(local_date)))

    # ---- weekly series ------------------------------------------------------
    def weekly_series(
        per_week_counts: dict[str, int], per_week_students: dict[str, set[str]], footnote_ids: list[str] | None = None
    ) -> WeeklySeries:
        entries = [
            WeeklyEntry(
                week=w,
                cell=floored_count(per_week_counts.get(w, 0), len(per_week_students.get(w, set())), floor_n),
            )
            for w in axis
        ]
        return WeeklySeries(series=entries, footnote_ids=footnote_ids)

    def tally(items: list[tuple[str, str]]) -> tuple[dict[str, int], dict[str, set[str]]]:
        """items: (pseudonym, week) -> per-week counts + contributing-student sets."""
        counts: dict[str, int] = defaultdict(int)
        students: dict[str, set[str]] = defaultdict(set)
        for pseudonym, week in items:
            counts[week] += 1
            students[week].add(pseudonym)
        return counts, students

    msg_counts, msg_students = tally([(m.pseudonym, m.week) for m in msgs])
    session_counts, session_students = tally([(s.pseudonym, s.week) for s in sessions])
    reg_counts, reg_students = tally(registrations)

    active_series = WeeklySeries(
        series=[
            WeeklyEntry(
                week=w,
                cell=floored_count(len(msg_students.get(w, set())), len(msg_students.get(w, set())), floor_n),
            )
            for w in axis
        ]
    )

    # ---- per-window sections ------------------------------------------------
    temporal_windows: dict[str, TemporalUsageWindow] = {}
    usage_windows: dict[str, UsageContextWindow] = {}
    session_windows: dict[str, SessionsWindow] = {}
    token_windows: dict[str, TokensWindow] = {}
    language_windows: dict[str, LanguageWindow] = {}

    for window in windows:
        weeks = _window_weeks(window, axis)
        w_msgs = [m for m in msgs if m.week in weeks]
        w_sessions = [s for s in sessions if s.week in weeks]

        heat_counts: dict[tuple[int, int], int] = defaultdict(int)
        heat_students: dict[tuple[int, int], set[str]] = defaultdict(set)
        for m in w_msgs:
            key = (m.local.isoweekday(), m.local.hour)
            heat_counts[key] += 1
            heat_students[key].add(m.pseudonym)
        temporal_windows[window.id] = TemporalUsageWindow(
            activity_heatmap=HeatmapGrid(
                cells=[
                    HeatmapCell(
                        dow=dow,
                        hour=hour,
                        cell=floored_count(
                            heat_counts.get((dow, hour), 0), len(heat_students.get((dow, hour), set())), floor_n
                        ),
                    )
                    for dow in range(1, 8)
                    for hour in range(24)
                ]
            )
        )

        active = {m.pseudonym for m in w_msgs}
        new_regs = [p for p, week in registrations if week in weeks]
        user_dates: dict[str, list[datetime]] = defaultdict(list)
        for m in w_msgs:
            user_dates[m.pseudonym].append(m.local)
        usage_windows[window.id] = UsageContextWindow(
            totals=UsageContextTotals(
                active_students=floored_count(len(active), len(active), floor_n),
                messages=floored_count(len(w_msgs), len(active), floor_n),
                sessions=floored_count(len(w_sessions), len({s.pseudonym for s in w_sessions}), floor_n),
                new_registrations=floored_count(len(new_regs), len(set(new_regs)), floor_n),
            ),
            user_classes=_user_classes(user_dates, floor_n),
        )

        session_windows[window.id] = SessionsWindow(
            messages_per_session=_histogram(
                "sessions",
                MESSAGES_PER_SESSION_BINS,
                [(s.n_messages, float(s.n_messages), s.pseudonym) for s in w_sessions],
                floor_n,
                ["chat_fragmentation"],
            ),
            session_duration_minutes=_histogram(
                "sessions",
                SESSION_DURATION_BINS,
                [(int(s.duration_minutes), s.duration_minutes, s.pseudonym) for s in w_sessions],
                floor_n,
                ["chat_fragmentation", "duration_definition"],
                # Resumed chats span days under the (student, started) session key,
                # so a duration mean is dominated by them; robust stats only.
                with_mean_sd=False,
            ),
        )
        token_windows[window.id] = TokensWindow(
            completion_tokens_per_message=_histogram(
                "messages",
                COMPLETION_TOKENS_BINS,
                [(m.completion_tokens, float(m.completion_tokens), m.pseudonym) for m in w_msgs],
                floor_n,
            )
        )

        lang_totals: dict[str, OkCell | SuppressedCell] = {}
        for code in LANGUAGE_CODES:
            in_code = [m for m in w_msgs if m.lang == code]
            lang_totals[code] = floored_count(len(in_code), len({m.pseudonym for m in in_code}), floor_n)
        language_windows[window.id] = LanguageWindow(totals=LanguageTotals(**lang_totals))

    lang_weekly = {}
    for code in LANGUAGE_CODES:
        counts, students = tally([(m.pseudonym, m.week) for m in msgs if m.lang == code])
        lang_weekly[code] = weekly_series(counts, students)

    return Aggregates(
        schema_version=SCHEMA_VERSION,
        generated_at=now.astimezone(timezone.utc),
        data_through_week=through,
        data_through_date=week_sunday(through),
        first_week=first,
        privacy_floor_n=floor_n,
        label_versions={"language": LANGUAGE_LABEL_VERSION},
        timezone="Europe/Vienna",
        data_provenance=provenance,
        pipeline_version=pipeline_version,
        windows=windows,
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=weekly_series(msg_counts, msg_students),
                    sessions=weekly_series(session_counts, session_students, ["chat_fragmentation"]),
                    active_students=active_series,
                ),
                per_window=temporal_windows,
            ),
            usage_context=UsageContext(
                weekly=UsageContextWeekly(
                    registrations=weekly_series(reg_counts, reg_students, ["bachelor_onboarding"])
                ),
                per_window=usage_windows,
            ),
            sessions=SessionsSection(per_window=session_windows),
            tokens=TokensSection(per_window=token_windows),
            language=LanguageSection(
                weekly=LanguageWeekly(
                    messages_by_language=MessagesByLanguage(**lang_weekly, footnote_ids=["language_heuristic"])
                ),
                per_window=language_windows,
            ),
        ),
    )
