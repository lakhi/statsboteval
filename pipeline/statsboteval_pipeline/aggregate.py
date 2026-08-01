"""Weekly aggregation + privacy floor -> the contract document.

The floor (contract invariant 1) is applied in exactly one place: floored_count()
(plus its summary-stats sibling _summary()). No other code may turn corpus
numbers into cells. The one shape outside that rule is a trends Finding
(contract §7.6, D-49), which has no suppressed state because sub-floor
candidates are dropped before publication rather than marked — trends.py owns
that path and Aggregates._check_trends re-proves the floor on every published
side. ISO-week bucketing happens in Python after
UTC->Europe/Vienna conversion — calendar knowledge lives here, not in SQL
(matching the contract's semester principle).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import duckdb

from .contract import (
    Aggregates,
    CountCell,
    Daypart,
    DaypartCell,
    DaypartGrid,
    DaypartTotals,
    Enrollment,
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
    PerStudentByStatus,
    PerStudentSection,
    PerStudentWindow,
    SCHEMA_VERSION,
    SessionsByStatus,
    Sections,
    SemesterProfile,
    SemesterProfilePoint,
    SessionsSection,
    SessionsWindow,
    SummaryStats,
    SuppressedCell,
    SuppressedSummaryStats,
    TemporalUsage,
    TemporalUsageByStatus,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    UsageContext,
    UsageContextByStatus,
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
from .classify.codebook import DEDUCTIVE_CATEGORY_NAMES, category_code
from .contract import TopicDistribution, TopicGroup, TopicItem, TopicsSection, TopicsWindowEntry
from .extract import read_last_extracted_at
from .language import LABEL_VERSION as LANGUAGE_LABEL_VERSION
from .stats import classify_user, is_frequent, quantile_type2
from .status import read_status, resolve_status, status_at
from .trends import build_trends
from .windows import build_windows

VIENNA = ZoneInfo("Europe/Vienna")

LANGUAGE_CODES = ("de", "en", "other", "undetermined")

# Fixed bin edges, pinned to the design fixture the dashboard was built against.
MESSAGES_PER_SESSION_BINS: list[tuple[int, int | None]] = [(1, 1), (2, 3), (4, 7), (8, None)]
SESSION_DURATION_BINS: list[tuple[int, int | None]] = [(0, 1), (2, 5), (6, 15), (16, 30), (31, None)]
# Per-student edges (1.5.0, D-53). The first two reuse the session shape so a reader moving
# between "per conversation" and "per student" cards is reading the same ruler; the message
# edges are wider because a student's message count spans an order of magnitude more.
SESSIONS_PER_STUDENT_BINS: list[tuple[int, int | None]] = [(1, 1), (2, 3), (4, 7), (8, None)]
WEEKS_ACTIVE_BINS: list[tuple[int, int | None]] = [(1, 1), (2, 3), (4, 7), (8, None)]
MESSAGES_PER_STUDENT_BINS: list[tuple[int, int | None]] = [(1, 2), (3, 5), (6, 10), (11, 25), (26, None)]

# Dayparts (1.6.0, D-54). Four EQUAL six-hour blocks, and the equality is the point: bar
# height reads as intensity, so unequal bins invert the finding. The rejected 6-block draft
# put 09-12 at 1,010 messages against 14-18 at 1,560 — which says "afternoons are far
# busier" while the per-hour rates are 337 and 390, and the shortest bar (12-14, 2 h) was
# the densest period of the day at 408/h. Equal widths also mean nothing wraps midnight
# and _daypart_of is `hour // 6`. Suppression is a bonus: 7x4 hides 3 of 4,419 messages
# all-time where 7x24 hides 85, and the four-week window (then trailing_4, now a semester
# slice — D-56) goes from 76% hidden to 14%.
DAYPARTS: list[Daypart] = [
    Daypart(id="night", label="Night", from_hour=0, to_hour=6),
    Daypart(id="morning", label="Morning", from_hour=6, to_hour=12),
    Daypart(id="afternoon", label="Afternoon", from_hour=12, to_hour=18),
    Daypart(id="evening", label="Evening", from_hour=18, to_hour=24),
]

def _daypart_of(hour: int) -> str:
    """Vienna-local hour -> daypart id, [from_hour, to_hour).

    A scan rather than `hour // 6`: the division is only correct while every block is six
    hours wide, and that is a *display* property of the current registry, not a law. If
    the blocks are ever re-cut, this keeps working and the charts just stop being equal-
    width. Four comparisons per message is not a cost worth that trap.
    """
    for part in DAYPARTS:
        if part.from_hour <= hour < part.to_hour:
            return part.id
    raise ValueError(f"hour {hour} falls in no daypart; registry does not tile the day")

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
    # Wording pinned to the OSF analysis script it reproduces (verified 2026-07-30), and
    # phrased in days rather than variable names: the reader is an educator, not a reviewer
    # re-running the R. "Frequent" is stated as a subset because it is one (stats.is_frequent).
    "user_class_definitions": Footnote(
        text="Classes follow the operational definitions of Bergmann et al. (2026), applied to "
        "the selected window: one-time = all messages within 24 hours and spanning under 3 days; "
        "monthly = active over 30 days or more with no gap of 30 days or longer; sporadic = "
        "everything else. Frequent counts the monthly users who additionally never paused for "
        "14 days, so it is a subset of monthly and is not added to the other three. "
        "Materials: https://osf.io/v8ydk/overview"
    ),
    "user_class_window": Footnote(
        text="Each student is classified from their activity inside the selected window only, so "
        "a window shorter than 30 days cannot contain a monthly user by definition."
    ),
    # D-58 cut this to the definition alone. It renders inside the retention tile now, not
    # in a paragraph under four unrelated numbers, and a note that sits in its cell has to
    # be readable at a glance. "First-ever" still carries the D-50 baseline (first use is
    # read from the whole recorded history, behind axis_start) — what left the page is the
    # explanation of it, not the behaviour.
    "retention_definition": Footnote(
        text="New = the student's first-ever message falls inside the selected window; returning "
        "= they had already used StatsBot before it. The two add up to the active users."
    ),
    # 1.8.0 (D-58). Emitted on the all_time window ONLY, because that is the one window
    # where "returning" means something other than what the reader assumes. The pipeline
    # decides when the caveat applies because it is the side that knows the window kind;
    # the dashboard renders whichever retention ids arrive and never branches on it.
    "retention_all_time": Footnote(
        text="All time has no earlier period except the 2024/25 pilot, so returning here names "
        "the pilot cohort rather than semester-to-semester loyalty."
    ),
    "signup_activation": Footnote(
        text="Both counts are window-scoped. Someone who signed up late and first wrote "
        "afterwards counts in the window they wrote in."
    ),
    # 1.9.0 (D-59). Emitted on the by-level slices only, because the caveat exists only
    # there: under All users no level is claimed and the sentence would be noise. It says
    # the quiet part of the split — every other number on the tab is resolved at usage
    # time, this one cannot be, because the people it counts may never have used anything.
    "signup_level_rule": Footnote(
        text="A signup has no conversation behind it, so its program level is read from the "
        "roster at the registration date rather than at usage time. Someone who signed up as "
        "a bachelor student and later moved to the master programme counts here as bachelor."
    ),
    "status_multi": Footnote(
        text="A student who moved from bachelor to master inside the selected window is counted "
        "under both levels, so the student counts can exceed the window total by a few."
    ),
    # 1.5.0 (D-53). Weeks active is bounded by the window it is read in — 4 in a four-week
    # slice, ~17 in a semester, the whole axis in all_time — so the shares are not comparable
    # across windows of different length. Same shape of caveat as user_class_window. In a
    # one-week slice the bound is 1, which makes the distribution degenerate rather than
    # merely incomparable; the dashboard withholds that card there (D-56).
    "weeks_active_window": Footnote(
        text="Weeks active counts only the ISO weeks inside the selected window, so a shorter "
        "window necessarily yields fewer weeks per student; the shares are not comparable "
        "between windows of different length."
    ),
    # 1.6.0 (D-54), cut to the boundary rule in D-59. The blocks are still four EQUAL
    # six-hour bins and that equality is still load-bearing (see DAYPARTS) — what changed
    # is only whether the note repeats it: both cards print each block's hour range beside
    # its own label ("Night 00–06"), and "Vienna local" is in the panel deck one line
    # above, so two of the three sentences restated what the reader could already see.
    "daypart_definition": Footnote(
        text="Each block counts the messages sent inside it, so a chat that runs past a "
        "boundary contributes to both."
    ),
    "semester_week_alignment": Footnote(
        text="Week 1 is the semester's first ISO week (the first week whose Thursday falls "
        "inside the semester), so the curves line up on teaching week rather than calendar "
        "date. Semesters draw largely different cohorts and differ in course structure — "
        "summer and winter especially — so compare the shape of a curve rather than its "
        "height. A semester still in progress ends where the data does."
    ),
    "duration_definition": Footnote(
        text="Session duration = last minus first server timestamp in the session; "
        "single-message sessions count as 0 minutes."
    ),
    "multi_label": Footnote(
        text="A message may carry several categories or themes, so topic counts do not "
        "sum to the message total."
    ),
    "label_provenance": Footnote(
        text="Topics come from automated classification; label_versions.classification "
        "names the exact classifier version."
    ),
    "status_rule": Footnote(
        text="Program level comes from coordinator roster lists; students who moved from "
        "bachelor to master are counted by their status at usage time (per session)."
    ),
    # 1.7.0 (D-55). Both texts appear wherever an enrolled total or a reach percentage is
    # shown. The scope caveat is the owner's wording and is not optional decoration: an
    # educator reading "3.3% of enrolled bachelor students" against their own lecture hall
    # would otherwise conclude the tool failed, when the denominator is the whole
    # programme rather than the statistics cohort.
    "enrollment_source": Footnote(
        text="Enrolled totals come from SSC-Psych records."
    ),
    "enrollment_scope": Footnote(
        text="The totals include all enrolled bachelor/master students, whereas only the "
        "first-year students take the statistics course — data for how many first-year "
        "students take it across instructors is not available."
    ),
    "level_scope": Footnote(
        text="This figure covers every program level; the program-level filter above does "
        "not narrow it."
    ),
    # 1.8.0 (D-56). Reach in a semester slice divides by the whole term's enrolled cohort,
    # because that is the only denominator a four-week window inside a term has. Without
    # this, "9% reach" in a one-week window reads as a term figure and looks like collapse.
    "reach_window_scope": Footnote(
        text="Reach is measured against the enrolled cohort of the semester this window "
        "belongs to, so in a shorter window it reads as the share of that cohort active "
        "during those weeks — not over the whole term."
    ),
    # Trends footnotes (schema 1.3.0, D-49). trend_method is versioned with the numbers
    # it quotes: changing a threshold means editing this text in the same commit.
    "trend_method": Footnote(
        text="Trends compares the selected period with the one before it across a fixed set of "
        "measures. A change is listed only if both periods clear the privacy floor, the change "
        "is large enough to matter for its measure, and it stays significant at p < .05 after "
        "Benjamini-Hochberg correction across every measure tested (marked robust) or at least "
        "before it (indicative). Survivors are ordered by how directly they bear on teaching "
        "decisions, not by how small their p-value is. These are all StatsBot users rather than "
        "a sample, so the tests guard against over-reading short-period noise; they are not "
        "inference to a wider population."
    ),
    "per_week_rate": Footnote(
        text="Volume measures are compared per covered week so periods of unequal length stay "
        "comparable. Variation in activity within a period (term start, exam weeks) is not "
        "corrected for, and a period still in progress is averaged over the weeks so far."
    ),
    "cohort_turnover": Footnote(
        text="Each semester draws a largely different cohort of students; a change between "
        "semesters may reflect who enrolled rather than a change in behavior."
    ),
}

# Display labels for deductive codes: the public manuscript names (codebook.py constant).
DEDUCTIVE_LABELS = {category_code(name): name for name in DEDUCTIVE_CATEGORY_NAMES}
_TOPIC_DOMAINS = ("deductive", "method_theme", "software_theme", "emergent_theme")


COHORT_TOTALS_PATH = Path(__file__).resolve().parent.parent / "cohort_totals.json"


def read_cohort_totals(path: Path | None = None) -> Enrollment:
    """Enrolled-cohort denominators from the committed table (D-55).

    Committed rather than imported from a corpus table on purpose: these are a handful of
    aggregate institutional headcounts, they need no pepper and no corpus lock, and a
    committed table is diffable in the go-live review gate. The identifier-bearing roster
    lists they come from stay outside the repo, exactly as D-39 requires.

    Raises rather than returning None when the file is missing. The table is committed, so
    absence means a broken checkout or an installed package that dropped a data file — not
    a configuration choice. Falling back silently would publish a document with no reach
    figures at all, and the only symptom would be percentages quietly vanishing from a
    dashboard nobody was looking at that closely.
    """
    source = path or COHORT_TOTALS_PATH
    if not source.is_file():
        raise FileNotFoundError(
            f"cohort totals table not found at {source}. It is committed to the repo "
            "(pipeline/cohort_totals.json); a missing file means a broken checkout, not an "
            "opt-out. Restore it, or pass enrollment=None explicitly to publish without reach."
        )
    raw = json.loads(source.read_text(encoding="utf-8"))
    return Enrollment.model_validate({"per_window": raw["per_window"]})


def floored_count(value: int, n_students: int, floor_n: int) -> OkCell | SuppressedCell:
    """The one and only construction path from corpus numbers to a published cell."""
    if value < 0 or n_students < 0 or floor_n < 1:
        raise ValueError(f"invalid floor inputs: value={value} n_students={n_students} floor_n={floor_n}")
    if value > 0 and n_students == 0:
        raise ValueError(f"incoherent cell: value={value} with no contributing students")
    if n_students == 0 or n_students >= floor_n:
        return ok(value)
    return suppressed()


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
        median=round(quantile_type2(vals, 0.5), 1),
        p25=round(quantile_type2(vals, 0.25), 1),
        p75=round(quantile_type2(vals, 0.75), 1),
        mean=mean,
        sd=sd,
    )


@dataclass(frozen=True)
class _Message:
    history_id: int
    pseudonym: str
    session: tuple[str, int]
    local: datetime  # Europe/Vienna
    week: str
    lang: str


@dataclass(frozen=True)
class _Session:
    pseudonym: str
    week: str  # week of the first message (D-08)
    n_messages: int
    duration_minutes: float
    # 1.7.0 (D-55). A session carries one program level because resolve_status is keyed on
    # the session's `started`, so every message inside it resolves the same way. That is
    # what makes a per-level conversation histogram coherent: no conversation ever has to
    # be split across two levels. "" means no roster was imported.
    status: str = ""


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
    """Bergmann typology (pinned operationalizations, bergmann-framework.md).

    Computed on Vienna-local timestamps for consistency with the document's
    timezone (the reference scripts used UTC; the thresholds are what is pinned).
    `frequent` is a subset of `monthly` (stats.is_frequent), so it is tallied
    alongside rather than inside the partition.
    """
    tally = {"one_time": 0, "monthly": 0, "sporadic": 0}
    frequent = 0
    for stamps in user_dates.values():
        tally[classify_user(stamps)] += 1
        if is_frequent(stamps):
            frequent += 1
    one_time, monthly, sporadic = tally["one_time"], tally["monthly"], tally["sporadic"]
    # Every class count is its own contributing-student count: one student, one class.
    return UserClasses(
        one_time=floored_count(one_time, one_time, floor_n),
        monthly=floored_count(monthly, monthly, floor_n),
        sporadic=floored_count(sporadic, sporadic, floor_n),
        frequent=floored_count(frequent, frequent, floor_n),
        footnote_ids=["user_class_definitions", "user_class_window"],
    )


def _window_weeks(window: Window, axis: list[str]) -> set[str]:
    if window.kind == "all_time":
        return set(axis)
    return set(window.weeks) & set(axis)


@dataclass(frozen=True)
class CorpusView:
    """The in-memory corpus every section and every finding is computed from.

    Read once per run and shared, so `preview-trends` and a real publish can never
    disagree about the data underneath them.
    """

    msgs: list[_Message]
    sessions: list[_Session]
    registrations: list[tuple[str, str]]  # (pseudonym, week)
    axis: list[str]
    windows: list[Window]
    first_week: str
    through_week: str
    positives: dict[str, dict[str, set[int]]]  # domain -> code -> history_ids
    first_seen: dict[str, date]  # pseudonym -> first message ever, PRE-axis rows included
    message_status: dict[int, str]  # history_id -> program level at usage time; {} = no roster
    # D-59: pseudonym -> program level on the REGISTRATION date; {} = no roster imported.
    # Separate from message_status rather than folded into `registrations` because the
    # weekly registrations series tallies (pseudonym, week) pairs and has no use for a
    # level — widening the tuple would touch `tally` to serve one caller.
    registration_status: dict[str, str]


def read_corpus_view(
    con: duckdb.DuckDBPyConnection,
    *,
    now: datetime,
    axis_start: date | None = None,
    classification_version: str | None = None,
) -> CorpusView:
    """Read the corpus into the structures the aggregation and trends passes share."""
    rows = con.execute(
        "SELECT m.history_id, m.pseudonym, m.session_started, m.created_at, l.code "
        "FROM messages m LEFT JOIN labels l ON l.history_id = m.history_id "
        "  AND l.label_version = ? AND l.domain = 'language'",
        [LANGUAGE_LABEL_VERSION],
    ).fetchall()
    if not rows:
        raise ValueError("corpus has no messages; nothing to aggregate")

    # Axis: complete ISO weeks only (invariant 3). data_through_week = the last week
    # fully elapsed before extraction last actually ran, in Vienna. Trailing quiet
    # weeks were measured (extraction covered them, found nothing) -> they publish as
    # ok(0); clipping them off would misencode a measured zero as "absent" (invariant
    # 2). That reasoning only holds against the real extraction watermark, not
    # wall-clock `now` at aggregate time: a re-aggregate with no fresh extract (e.g.
    # erase-student, or iterating on a new tab) would otherwise publish weeks past the
    # data as if they'd been measured, when extraction never reached them. Corpora
    # that never went through extract_new_rows (synthetic fixtures, tests) have no
    # watermark yet, so `now` is the honest fallback.
    extraction_time = read_last_extracted_at(con) or now
    now_week_monday = week_monday(date_to_week(extraction_time.astimezone(VIENNA).date()))
    through = date_to_week(now_week_monday - timedelta(days=7))
    through_monday = week_monday(through)

    msgs: list[_Message] = []
    first_seen: dict[str, date] = {}
    for history_id, pseudonym, session_started, created_at, lang in rows:
        local = created_at.replace(tzinfo=timezone.utc).astimezone(VIENNA)
        # Retention's baseline is deliberately read BEFORE the axis_start filter below:
        # a student who wrote during the 2024/25 pilot is not a new user in 2025S just
        # because the pilot weeks are unpublishable. Moving this line under the filter
        # would silently turn every returning user into a new one (D-50).
        earliest = first_seen.get(pseudonym)
        if earliest is None or local.date() < earliest:
            first_seen[pseudonym] = local.date()
        if axis_start is not None and local.date() < axis_start:
            continue  # pre-launch pilot traffic stays in the corpus, out of publishes
        week = date_to_week(local.date())
        if week_monday(week) > through_monday:
            continue  # current, incomplete week
        msgs.append(
            _Message(history_id, pseudonym, (pseudonym, session_started), local, week, lang or "undetermined")
        )
    if not msgs:
        raise ValueError("no corpus data within the publishable range (axis_start / complete weeks)")

    first = min(m.week for m in msgs)
    axis = weeks_range(first, through)
    windows = build_windows(axis)

    # Program level at usage time (D-39), resolved before sessions are built so a session
    # can carry its own level (D-55). Read here rather than inside the topics block where
    # it used to live: four sections publish a status split now, and availability must not
    # depend on whether Phase B labels exist. Empty dict = no roster imported, which every
    # section reads as "publish no by_status".
    status_rows = read_status(con)
    message_status = (
        {m.history_id: resolve_status(status_rows.get(m.pseudonym), m.session[1]) for m in msgs}
        if status_rows
        else {}
    )

    by_session: dict[tuple[str, int], list[_Message]] = defaultdict(list)
    for m in msgs:
        by_session[m.session].append(m)
    sessions = [
        _Session(
            pseudonym=key[0],
            week=min(group, key=lambda m: m.local).week,
            n_messages=len(group),
            duration_minutes=(max(m.local for m in group) - min(m.local for m in group)).total_seconds() / 60,
            status=message_status.get(group[0].history_id, ""),
        )
        for key, group in by_session.items()
    ]

    registrations: list[tuple[str, str]] = []  # (pseudonym, week)
    registration_status: dict[str, str] = {}
    for pseudonym, registered_at in con.execute("SELECT pseudonym, registered_at FROM students").fetchall():
        local_date = registered_at.replace(tzinfo=timezone.utc).astimezone(VIENNA).date()
        if axis_start is not None and local_date < axis_start:
            continue
        registrations.append((pseudonym, date_to_week(local_date)))
        # The D-39 rule at the registration instant (D-59). Same `status_at`, same
        # Beginnsemester boundary, different date — a signup is the one event a registrant
        # who never wrote still has. Left empty when no roster is imported, which every
        # section reads as "publish no by_status".
        if status_rows:
            registration_status[pseudonym] = status_at(status_rows.get(pseudonym), local_date)

    # Label positives, read here rather than inside the topics block: build_trends needs
    # exactly the same material, and a second query would be a second source of truth for
    # which message carries which code. Empty when nothing was classified.
    positives: dict[str, dict[str, set[int]]] = {domain: defaultdict(set) for domain in _TOPIC_DOMAINS}
    if classification_version is not None:
        for domain, code, history_id in con.execute(
            "SELECT domain, code, history_id FROM labels "
            "WHERE label_version = ? AND value = 1 AND domain IN ('deductive', 'method_theme', "
            "'software_theme', 'emergent_theme')",
            [classification_version],
        ).fetchall():
            positives[domain][code].add(history_id)

    return CorpusView(
        msgs=msgs,
        sessions=sessions,
        registrations=registrations,
        axis=axis,
        windows=windows,
        first_week=first,
        through_week=through,
        positives=positives,
        first_seen=first_seen,
        message_status=message_status,
        registration_status=registration_status,
    )


def build_aggregates(
    con: duckdb.DuckDBPyConnection,
    *,
    floor_n: int,
    now: datetime,
    provenance: Literal["synthetic", "production"],
    pipeline_version: str,
    axis_start: date | None = None,
    classification_version: str | None = None,
    theme_set_version: str | None = None,
    enrollment: Enrollment | None = None,
) -> Aggregates:
    view = read_corpus_view(
        con, now=now, axis_start=axis_start, classification_version=classification_version
    )
    msgs, sessions, registrations = view.msgs, view.sessions, view.registrations
    registration_status = view.registration_status
    axis, windows = view.axis, view.windows
    first, through = view.first_week, view.through_week
    positives = view.positives

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

    # Still needed by the semester profiles below and the registrations series; the three
    # temporal weekly series are built by temporal_weekly(), the same helper every program
    # level goes through.
    msg_counts, msg_students = tally([(m.pseudonym, m.week) for m in msgs])
    reg_counts, reg_students = tally(registrations)

    # ---- per-window sections ------------------------------------------------
    # 1.7.0 (D-55): every shape below is a function of a (messages, sessions) subset, so
    # the same code produces the cohort-wide window and each program level. That is the
    # shape topic_group() has had since 1.1.0, which is exactly why Topics could gain a
    # status split cheaply and the other four sections could not. Splitting a level is now
    # calling these again with a filtered subset — there is no second definition of a
    # daypart, a bin edge or a user class that could drift away from the first.
    temporal_windows: dict[str, TemporalUsageWindow] = {}
    usage_windows: dict[str, UsageContextWindow] = {}
    session_windows: dict[str, SessionsWindow] = {}
    per_student_windows: dict[str, PerStudentWindow] = {}
    language_windows: dict[str, LanguageWindow] = {}

    def daypart_shapes(subset: list[_Message]) -> tuple[DaypartGrid, DaypartTotals]:
        dp_counts: dict[tuple[int, str], int] = defaultdict(int)
        dp_students: dict[tuple[int, str], set[str]] = defaultdict(set)
        part_counts: dict[str, int] = defaultdict(int)
        part_students: dict[str, set[str]] = defaultdict(set)
        span_counts: dict[str, int] = defaultdict(int)
        span_students: dict[str, set[str]] = defaultdict(set)
        for m in subset:
            dow, hour = m.local.isoweekday(), m.local.hour
            part = _daypart_of(hour)
            dp_counts[(dow, part)] += 1
            dp_students[(dow, part)].add(m.pseudonym)
            part_counts[part] += 1
            part_students[part].add(m.pseudonym)
            span = "weekend" if dow >= 6 else "weekday"
            span_counts[span] += 1
            span_students[span].add(m.pseudonym)
        grid = DaypartGrid(
            cells=[
                DaypartCell(
                    dow=dow,
                    daypart=part.id,
                    cell=floored_count(
                        dp_counts.get((dow, part.id), 0),
                        len(dp_students.get((dow, part.id), set())),
                        floor_n,
                    ),
                )
                for dow in range(1, 8)
                for part in DAYPARTS
            ],
            footnote_ids=["daypart_definition"],
        )
        totals = DaypartTotals(
            by_daypart={
                part.id: floored_count(
                    part_counts.get(part.id, 0), len(part_students.get(part.id, set())), floor_n
                )
                for part in DAYPARTS
            },
            # Floored on their own student sets. Never weekday = total − weekend: that
            # subtraction would recover a suppressed side exactly (invariant 4).
            weekend=floored_count(
                span_counts.get("weekend", 0), len(span_students.get("weekend", set())), floor_n
            ),
            weekday=floored_count(
                span_counts.get("weekday", 0), len(span_students.get("weekday", set())), floor_n
            ),
            footnote_ids=["daypart_definition"],
        )
        return grid, totals

    def session_histograms(subset: list[_Session]) -> dict[str, Histogram]:
        return {
            "messages_per_session": _histogram(
                "sessions",
                MESSAGES_PER_SESSION_BINS,
                [(s.n_messages, float(s.n_messages), s.pseudonym) for s in subset],
                floor_n,
                ["chat_fragmentation"],
            ),
            "session_duration_minutes": _histogram(
                "sessions",
                SESSION_DURATION_BINS,
                [(int(s.duration_minutes), s.duration_minutes, s.pseudonym) for s in subset],
                floor_n,
                ["chat_fragmentation", "duration_definition"],
                # Resumed chats span days under the (student, started) session key,
                # so a duration mean is dominated by them; robust stats only.
                with_mean_sd=False,
            ),
        }

    def per_student_histograms(subset: list[_Message], sess: list[_Session]) -> dict[str, Histogram]:
        """One observation per student (1.5.0, D-53), so every bin's contributing-student
        count IS its value and the floor reduces to "fewer than N students in this bin".
        Sorted for a byte-stable document."""
        sessions_by_student: dict[str, int] = defaultdict(int)
        messages_by_student: dict[str, int] = defaultdict(int)
        weeks_by_student: dict[str, set[str]] = defaultdict(set)
        for s in sess:
            sessions_by_student[s.pseudonym] += 1
        for m in subset:
            messages_by_student[m.pseudonym] += 1
            weeks_by_student[m.pseudonym].add(m.week)
        return {
            "sessions_per_student": _histogram(
                "students",
                SESSIONS_PER_STUDENT_BINS,
                [(n, float(n), p) for p, n in sorted(sessions_by_student.items())],
                floor_n,
                ["chat_fragmentation"],
            ),
            "weeks_active_per_student": _histogram(
                "students",
                WEEKS_ACTIVE_BINS,
                [(len(w), float(len(w)), p) for p, w in sorted(weeks_by_student.items())],
                floor_n,
                ["weeks_active_window"],
            ),
            "messages_per_student": _histogram(
                "students",
                MESSAGES_PER_STUDENT_BINS,
                [(n, float(n), p) for p, n in sorted(messages_by_student.items())],
                floor_n,
            ),
        }

    def language_totals(subset: list[_Message]) -> LanguageTotals:
        totals: dict[str, OkCell | SuppressedCell] = {}
        for code in LANGUAGE_CODES:
            in_code = [m for m in subset if m.lang == code]
            totals[code] = floored_count(len(in_code), len({m.pseudonym for m in in_code}), floor_n)
        return LanguageTotals(**totals)

    def retention_pair(subset: list[_Message], window_start: date | None) -> tuple[CountCell, CountCell]:
        """New vs returning, under complementary suppression.

        new + returning = active_students and all three are published, so publishing one
        part beside a suppressed other would hand the reader the suppressed count by
        subtraction — the one shape where per-cell flooring is not enough. If either side
        is sub-floor, neither is published. A measured 0 is ok(0) and never triggers this
        (floored_count(0, 0) is ok by invariant 2).
        """
        active = {m.pseudonym for m in subset}
        new_users = {p for p in active if window_start is not None and view.first_seen[p] >= window_start}
        returning = active - new_users
        new_cell = floored_count(len(new_users), len(new_users), floor_n)
        returning_cell = floored_count(len(returning), len(returning), floor_n)
        if new_cell.status == "suppressed" or returning_cell.status == "suppressed":
            return suppressed(), suppressed()
        return new_cell, returning_cell

    def by_level(subset: list[_Message]) -> dict[str, list[_Message]]:
        """Messages grouped by program level, or {} when no roster is imported.

        A BA->MA transitioner active on both sides of their semester boundary appears in
        both groups (D-50 accepts the overlap; the status_multi footnote states it).
        """
        if not view.message_status:
            return {}
        grouped: dict[str, list[_Message]] = defaultdict(list)
        for m in subset:
            grouped[view.message_status[m.history_id]].append(m)
        return dict(sorted(grouped.items()))

    for window in windows:
        weeks = _window_weeks(window, axis)
        w_msgs = [m for m in msgs if m.week in weeks]
        w_sessions = [s for s in sessions if s.week in weeks]
        w_levels = by_level(w_msgs)

        heat_counts: dict[tuple[int, int], int] = defaultdict(int)
        heat_students: dict[tuple[int, int], set[str]] = defaultdict(set)
        for m in w_msgs:
            dow, hour = m.local.isoweekday(), m.local.hour
            heat_counts[(dow, hour)] += 1
            heat_students[(dow, hour)].add(m.pseudonym)
        grid, dp_totals = daypart_shapes(w_msgs)
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
            ),
            daypart_heatmap=grid,
            daypart_totals=dp_totals,
            # No per-level activity_heatmap: unrendered since D-54 and 44 KB on its own.
            by_status={
                level: TemporalUsageByStatus(
                    daypart_heatmap=level_grid, daypart_totals=level_totals
                )
                for level, group in w_levels.items()
                for level_grid, level_totals in [daypart_shapes(group)]
            }
            or None,
        )

        active = {m.pseudonym for m in w_msgs}
        new_regs = [p for p, week in registrations if week in weeks]
        user_dates: dict[str, list[datetime]] = defaultdict(list)
        for m in w_msgs:
            user_dates[m.pseudonym].append(m.local)

        # Retention: a window's first Monday is the boundary, not its first message —
        # a window with a quiet opening week must not count that week's absentees as new.
        window_start = week_monday(min(weeks)) if weeks else None
        new_cell, returning_cell = retention_pair(w_msgs, window_start)
        # Signup activation: registered in this window AND wrote in this window. Both sides
        # are window-scoped, so a published window never changes value on a later republish.
        activated = {p for p in set(new_regs) if p in active}

        def usage_by_status(
            level: str,
            level_msgs: list[_Message],
            sess: list[_Session] = w_sessions,
            start: date | None = window_start,
        ) -> UsageContextByStatus:
            students = {m.pseudonym for m in level_msgs}
            # Signups of this level (D-59), keyed on the registration date rather than on
            # a session — see `signup_level_rule`. `level_regs` is not a subset of
            # `students`: most of its members never wrote, which is the entire reason the
            # pair could not be split before.
            #
            # Known edge, pinned in tests: the by_status key set comes from this window's
            # MESSAGES, so a level that signed up and never wrote has no slice and its
            # signups appear only in the cohort-wide total. Deliberate — a slice is a slice
            # of activity, and manufacturing an all-zero level to carry a signup count
            # would put a row of zeros on every by-level card on the dashboard.
            level_regs = [p for p in new_regs if registration_status.get(p) == level]
            level_activated = {p for p in set(level_regs) if p in active}
            # Sessions *of this level*, not "sessions whose student is in this level": a
            # transitioner's pre-boundary conversations belong to bachelor even though the
            # same person also appears under master (resolve_status is session-keyed).
            level_sessions = [s for s in sess if s.status == level]
            level_new, level_returning = retention_pair(level_msgs, start)
            level_dates: dict[str, list[datetime]] = defaultdict(list)
            for m in level_msgs:
                level_dates[m.pseudonym].append(m.local)
            return UsageContextByStatus(
                active_students=floored_count(len(students), len(students), floor_n),
                messages=floored_count(len(level_msgs), len(students), floor_n),
                sessions=floored_count(
                    len(level_sessions), len({s.pseudonym for s in level_sessions}), floor_n
                ),
                new_users=level_new,
                returning_users=level_returning,
                user_classes=_user_classes(level_dates, floor_n),
                new_registrations=floored_count(len(level_regs), len(set(level_regs)), floor_n),
                new_registrations_active=floored_count(
                    len(level_activated), len(level_activated), floor_n
                ),
                footnote_ids=["status_rule", "status_multi", "signup_level_rule"],
            )

        usage_windows[window.id] = UsageContextWindow(
            totals=UsageContextTotals(
                active_students=floored_count(len(active), len(active), floor_n),
                messages=floored_count(len(w_msgs), len(active), floor_n),
                sessions=floored_count(len(w_sessions), len({s.pseudonym for s in w_sessions}), floor_n),
                new_registrations=floored_count(len(new_regs), len(set(new_regs)), floor_n),
                new_registrations_active=floored_count(len(activated), len(activated), floor_n),
                new_users=new_cell,
                returning_users=returning_cell,
                # D-58: one id per number in the tile row, so the dashboard can put each
                # caveat inside the cell it explains. `retention_all_time` is the only
                # window-dependent one — see its registry entry. `chat_fragmentation`
                # rides along with the sessions count here for the same reason it rides
                # along with the weekly sessions series.
                footnote_ids=[
                    "retention_definition",
                    *(["retention_all_time"] if window.kind == "all_time" else []),
                    "signup_activation",
                    "chat_fragmentation",
                ],
            ),
            user_classes=_user_classes(user_dates, floor_n),
            by_status={level: usage_by_status(level, group) for level, group in w_levels.items()} or None,
        )

        session_windows[window.id] = SessionsWindow(
            **session_histograms(w_sessions),
            by_status={
                level: SessionsByStatus(**session_histograms([s for s in w_sessions if s.status == level]))
                for level in w_levels
            }
            or None,
        )
        per_student_windows[window.id] = PerStudentWindow(
            **per_student_histograms(w_msgs, w_sessions),
            by_status={
                level: PerStudentByStatus(
                    **per_student_histograms(group, [s for s in w_sessions if s.status == level])
                )
                for level, group in w_levels.items()
            }
            or None,
        )
        language_windows[window.id] = LanguageWindow(
            totals=language_totals(w_msgs),
            by_status={level: language_totals(group) for level, group in w_levels.items()} or None,
        )

    # ---- semester profiles (1.6.0, D-54) ------------------------------------
    # Each semester re-indexed to teaching week so the curves overlay. Week 1 is
    # window.weeks[0] — the registry's full Thursday-rule membership, NOT the covered
    # subset: indexing on coverage would slide a semester with a quiet opening week one
    # week left and silently misalign every comparison the chart exists to make.
    # Weeks past the axis are simply absent; an in-progress semester ends where data does.
    axis_set = set(axis)
    semester_profiles = [
        SemesterProfile(
            window_id=window.id,
            label=window.label,
            kind="summer" if window.id.endswith("S") else "winter",
            points=[
                SemesterProfilePoint(
                    semester_week=index,
                    week=week,
                    messages=floored_count(
                        msg_counts.get(week, 0), len(msg_students.get(week, set())), floor_n
                    ),
                    active_students=floored_count(
                        len(msg_students.get(week, set())), len(msg_students.get(week, set())), floor_n
                    ),
                )
                for index, week in enumerate(window.weeks, start=1)
                if week in axis_set
            ],
            footnote_ids=["semester_week_alignment", "cohort_turnover"],
        )
        for window in windows
        if window.kind == "semester"
    ]

    def language_weekly(subset: list[_Message]) -> LanguageWeekly:
        series = {}
        for code in LANGUAGE_CODES:
            counts, students = tally([(m.pseudonym, m.week) for m in subset if m.lang == code])
            series[code] = weekly_series(counts, students)
        return LanguageWeekly(
            messages_by_language=MessagesByLanguage(**series, footnote_ids=["language_heuristic"])
        )

    def temporal_weekly(subset: list[_Message], sess: list[_Session]) -> TemporalUsageWeekly:
        m_counts, m_students = tally([(m.pseudonym, m.week) for m in subset])
        s_counts, s_students = tally([(s.pseudonym, s.week) for s in sess])
        return TemporalUsageWeekly(
            messages=weekly_series(m_counts, m_students),
            sessions=weekly_series(s_counts, s_students, ["chat_fragmentation"]),
            active_students=WeeklySeries(
                series=[
                    WeeklyEntry(
                        week=w,
                        cell=floored_count(
                            len(m_students.get(w, set())), len(m_students.get(w, set())), floor_n
                        ),
                    )
                    for w in axis
                ]
            ),
        )

    # Per-level weekly series (1.7.0, D-55). The weekly charts are document-level and
    # sliced client-side, so without these the level filter would narrow the dayparts and
    # leave the trend lines cohort-wide — a filter that scopes half a tab is worse than no
    # filter, because nothing on screen says which half.
    all_levels = by_level(msgs)
    weekly_by_status = {
        level: temporal_weekly(group, [s for s in sessions if s.status == level])
        for level, group in all_levels.items()
    } or None
    language_weekly_by_status = {
        level: language_weekly(group) for level, group in all_levels.items()
    } or None

    # ---- topics (Phase B, schema 1.1.0; by_status per D-39) -----------------
    topics_section: TopicsSection | None = None
    if classification_version is not None:
        # 1.2.0: emergent items carry their reviewed one-line definition from the
        # frozen theme set. Other domains publish no description — Bergmann
        # category definitions are unpublished research material (D-16).
        theme_descriptions: dict[str, str] = {}
        if theme_set_version is not None:
            theme_descriptions = dict(
                con.execute(
                    "SELECT code, description FROM theme_sets WHERE set_version = ?", [theme_set_version]
                ).fetchall()
            )

        def topic_distribution(domain: str, subset: list[_Message]) -> TopicDistribution:
            def display(code: str) -> str:
                return DEDUCTIVE_LABELS.get(code, code) if domain == "deductive" else code

            items = []
            for code in sorted(positives[domain], key=display):
                hits = [m for m in subset if m.history_id in positives[domain][code]]
                items.append(
                    TopicItem(
                        label=display(code),
                        cell=floored_count(len(hits), len({m.pseudonym for m in hits}), floor_n),
                        description=theme_descriptions.get(code) if domain == "emergent_theme" else None,
                    )
                )
            # D-59: no `status_rule` on a level slice. It rode along here since D-39 and
            # rendered as a third symbol on all four cards under a single level, restating
            # on every card what the filter above them already says. The one place on this
            # tab where the roster rule earns its symbol — the by-level comparison card —
            # resolves it from the registry directly, not from these ids.
            return TopicDistribution(
                items=items,
                n_total=floored_count(len(subset), len({m.pseudonym for m in subset}), floor_n),
                footnote_ids=["multi_label", "label_provenance"],
            )

        def topic_group(subset: list[_Message]) -> dict[str, Any]:
            return {
                "deductive": topic_distribution("deductive", subset),
                "method_themes": topic_distribution("method_theme", subset),
                "software_themes": topic_distribution("software_theme", subset),
                "emergent_themes": (
                    topic_distribution("emergent_theme", subset) if positives["emergent_theme"] else None
                ),
            }

        if any(positives[domain] for domain in _TOPIC_DOMAINS):
            topics_windows: dict[str, TopicsWindowEntry] = {}
            for window in windows:
                weeks = _window_weeks(window, axis)
                w_msgs = [m for m in msgs if m.week in weeks]
                topic_by_status: dict[str, TopicGroup] | None = None
                if view.message_status:
                    grouped: dict[str, list[_Message]] = defaultdict(list)
                    for m in w_msgs:
                        grouped[view.message_status[m.history_id]].append(m)
                    topic_by_status = {
                        status: TopicGroup(**topic_group(group_msgs))
                        for status, group_msgs in sorted(grouped.items())
                    }
                topics_windows[window.id] = TopicsWindowEntry(**topic_group(w_msgs), by_status=topic_by_status)
            topics_section = TopicsSection(per_window=topics_windows, theme_set_version=theme_set_version)

    label_versions = {"language": LANGUAGE_LABEL_VERSION}
    if topics_section is not None and classification_version is not None:
        label_versions["classification"] = classification_version

    # ---- trends (schema 1.3.0, D-49) ----------------------------------------
    # Last, and from the same in-memory structures every section above used: findings
    # are comparisons of published measures, so they must not be able to disagree with
    # the measures themselves.
    trends_section = build_trends(
        msgs=msgs,
        sessions=sessions,
        registrations=registrations,
        windows=windows,
        axis=axis,
        floor_n=floor_n,
        positives=positives if topics_section is not None else None,
        deductive_labels=DEDUCTIVE_LABELS,
    )

    return Aggregates(
        schema_version=SCHEMA_VERSION,
        generated_at=now.astimezone(timezone.utc),
        data_through_week=through,
        data_through_date=week_sunday(through),
        first_week=first,
        privacy_floor_n=floor_n,
        label_versions=label_versions,
        timezone="Europe/Vienna",
        data_provenance=provenance,
        pipeline_version=pipeline_version,
        windows=windows,
        dayparts=DAYPARTS,
        # Clipped to the windows this run actually built: the table is maintained by hand
        # and outlives any one axis, so a stale semester in it must not become a published
        # window id the registry never heard of.
        enrollment=(
            Enrollment(
                per_window={
                    wid: entry
                    for wid, entry in enrollment.per_window.items()
                    if wid in {w.id for w in windows if w.kind == "semester"}
                }
            )
            if enrollment is not None
            else None
        ),
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                # Same helper the per-level copies use: two builders for one shape is two
                # places for a footnote or a floor to drift, and the cohort-wide series is
                # the one every level's is compared against.
                weekly=temporal_weekly(msgs, sessions),
                per_window=temporal_windows,
                semester_profiles=semester_profiles or None,
                weekly_by_status=weekly_by_status,
            ),
            usage_context=UsageContext(
                weekly=UsageContextWeekly(
                    registrations=weekly_series(reg_counts, reg_students, ["bachelor_onboarding"])
                ),
                per_window=usage_windows,
            ),
            sessions=SessionsSection(per_window=session_windows),
            per_student=PerStudentSection(per_window=per_student_windows),
            language=LanguageSection(
                weekly=language_weekly(msgs),
                per_window=language_windows,
                weekly_by_status=language_weekly_by_status,
            ),
            topics=topics_section,
            trends=trends_section,
        ),
    )
