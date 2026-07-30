"""SYNTHETIC corpus fixture generator — no real student data, ever (repo policy).

Deterministic (seeded RNG + explicit anchor). Guarantees the shapes the thin slice
must exercise end-to-end: a zero-activity week (published 0), a 1-2-student week
(suppressed at N=3), and multi-message sessions keyed by (pseudonym, session_started).

On an axis long enough to span two semesters it additionally plants between-semester
shifts in language, engagement and topic mix (T-6), so the Trends tab has findings to
render. On a shorter axis the planting is inert and the corpus is the time-invariant one
the Phase A tests were written against.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from random import Random

import duckdb

from .classify.codebook import DEDUCTIVE_CATEGORY_NAMES, category_code
from .contract import date_to_week, week_monday
from .labels import CURRENT_LABEL_VERSION, LabelRow, write_labels
from .language import detect_languages
from .windows import _semester_of

# Synthetic theme labels only — the real frozen/generated lists are git-ignored
# local materials (D-16/D-33) and never enter the repo.
_METHOD_THEMES = ["SYNTHETIC regression theme", "SYNTHETIC ANOVA theme", "SYNTHETIC correlation theme"]
_SOFTWARE_THEMES = ["SYNTHETIC software R-like", "SYNTHETIC software SPSS-like"]
_EMERGENT_THEMES = ["SYNTHETIC exam-prep theme", "SYNTHETIC homework theme", "SYNTHETIC concept-confusion theme"]
SYNTHETIC_THEME_SET_VERSION = "statsboteval-themes-v1"

_DE_SENT = [
    "SYNTHETIC: Wie berechne ich den Median?",
    "SYNTHETIC: Was bedeutet ein p-Wert von 0.03?",
    "SYNTHETIC: Wann verwende ich einen t-Test?",
    "SYNTHETIC: Wie interpretiere ich die Standardabweichung?",
]
_EN_SENT = [
    "SYNTHETIC: How do I compute a confidence interval?",
    "SYNTHETIC: What does statistical power mean?",
    "SYNTHETIC: When should I use ANOVA?",
]
_RECEIVED = [
    "SYNTHETIC reply: here is a worked explanation of the concept.",
    "SYNTHETIC reply: let us go through this step by step.",
    "SYNTHETIC reply: consider the following example dataset.",
]

# Message timestamps stay inside [Mon 06:00, Sun 18:00] UTC of their week so the
# UTC->Europe/Vienna conversion (+1/+2h) can never spill a message across an
# ISO-week boundary — the zero-week guarantee depends on this.
_WEEK_START_OFFSET_MIN = 6 * 60
_WEEK_END_OFFSET_MIN = (6 * 24 + 18) * 60


# --- planted between-semester shifts (T-6) --------------------------------------------
#
# Each pair is (before, after) and is sized to clear its family's gate in trends.py by a
# comfortable margin — the fixture's job is to make the tab deterministically non-empty,
# so a marginal shift that some seeds miss would be a worse fixture, not a more realistic
# one. Values are invented; nothing here is modelled on the real corpus.
#
# The `before` element of every pair is the value this generator used before T-6, so a
# one-semester axis (phase 0 throughout) still emits the exact corpus the Phase A tests
# and their committed expectations were written against.
_GERMAN_SHARE = (0.7, 0.35)  # language share: 35 pp against a 5 pp gate
_MESSAGES_PER_SESSION = ((1, 10), (5, 18))  # engagement median: ~5 -> ~11 messages
_SESSION_GAP_MINUTES = ((1, 15), (3, 30))  # session duration follows from the gaps
_METHOD_THEME_SHIFT = (0.35, 0.65)  # topic share for _METHOD_THEMES[0]


def _phase_by_week(axis: Sequence[str]) -> dict[str, int]:
    """0 for weeks before the last semester on the axis, 1 from it onward.

    Keying the planted shifts on this (rather than on a week offset) is what makes them
    land exactly on the boundary Trends compares across, and what makes them inert on a
    one-semester axis: no second semester, no phase 1, no shift.
    """
    order: list[str] = []
    for week in axis:
        semester = _semester_of(week)
        if semester is not None and semester.id not in order:
            order.append(semester.id)
    if len(order) < 2:
        return dict.fromkeys(axis, 0)

    last, phase, out = order[-1], 0, {}
    for week in axis:
        semester = _semester_of(week)
        if semester is not None and semester.id == last:
            phase = 1  # break weeks after the boundary stay on the near side of it
        out[week] = phase
    return out


def fixture_weeks(anchor: date, weeks: int) -> list[str]:
    """The last `weeks` complete ISO weeks strictly before the anchor's week."""
    through_monday = week_monday(date_to_week(anchor)) - timedelta(days=7)
    return [date_to_week(through_monday - timedelta(days=7 * i)) for i in range(weeks)][::-1]


def seed_synthetic(
    con: duckdb.DuckDBPyConnection,
    *,
    weeks: int = 8,
    seed: int = 42,
    anchor: date | None = None,
    n_students: int = 30,
) -> None:
    if weeks < 4:
        raise ValueError("need at least 4 weeks to include the zero and suppression shapes")
    rng = Random(seed)
    axis = fixture_weeks(anchor or date.today(), weeks)
    zero_week = axis[-3]
    suppressed_week = axis[-2]
    first_monday = week_monday(axis[0])
    phase = _phase_by_week(axis)

    students: list[tuple[str, datetime]] = []
    for i in range(n_students):
        pseudonym = f"syn-{i + 1:04d}"
        if i < 20:  # registered before the axis: always eligible for activity
            registered = datetime.combine(first_monday, datetime.min.time()) - timedelta(
                days=rng.randint(1, 60), minutes=rng.randint(0, 1439)
            )
        else:  # registered inside the axis: exercises registrations-per-week later
            registered = datetime.combine(week_monday(rng.choice(axis)), datetime.min.time()) + timedelta(
                minutes=rng.randint(_WEEK_START_OFFSET_MIN, _WEEK_END_OFFSET_MIN)
            )
        students.append((pseudonym, registered))
    con.executemany("INSERT INTO students VALUES (?, ?)", students)

    messages: list[tuple] = []
    history_id = 0
    for week in axis:
        if week == zero_week:
            continue
        monday = datetime.combine(week_monday(week), datetime.min.time())
        eligible = [p for p, registered in students if registered < monday]
        # Planted parameters for this week's semester; identical for every week on a
        # one-semester axis, so the Phase A corpora are unchanged.
        german = _GERMAN_SHARE[phase[week]]
        lo_messages, hi_messages = _MESSAGES_PER_SESSION[phase[week]]
        lo_gap, hi_gap = _SESSION_GAP_MINUTES[phase[week]]
        if week == suppressed_week:
            active = rng.sample(eligible, 2)
        else:
            active = rng.sample(eligible, rng.randint(5, min(15, len(eligible))))
        for pseudonym in active:
            for _ in range(rng.randint(1, 3)):  # sessions this week
                start_offset = rng.randint(_WEEK_START_OFFSET_MIN, _WEEK_END_OFFSET_MIN - 180)
                session_start = monday + timedelta(minutes=start_offset)
                session_started = int(session_start.timestamp() * 1000)  # client epoch ms
                created_at = session_start
                prompt_tokens = rng.randint(50, 300)
                for _ in range(rng.randint(lo_messages, hi_messages)):  # messages this session
                    history_id += 1
                    messages.append(
                        (
                            history_id,
                            pseudonym,
                            session_started,
                            created_at,
                            rng.choice(_DE_SENT if rng.random() < german else _EN_SENT),
                            rng.choice(_RECEIVED),
                            prompt_tokens,
                            rng.randint(20, 400),
                        )
                    )
                    created_at += timedelta(minutes=rng.randint(lo_gap, hi_gap))
                    prompt_tokens += rng.randint(100, 600)  # context re-sent, grows per exchange
    con.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", messages)
    # The real heuristic, not a table of pretend verdicts: language detection is local and
    # cheap, it runs on every real corpus before aggregation, and running it here is what
    # carries the planted German/English shift through to the labels the Language and
    # Trends tabs read. It also gives the fixture a genuine `undetermined` share, which a
    # hand-assigned mapping would have had to invent.
    detect_languages(con)


def seed_synthetic_labels(con: duckdb.DuckDBPyConnection, *, seed: int = 42) -> None:
    """Deterministic synthetic labels (all four domains) + status rows for E2E/demo.

    Deductive uses the public category names with explicit 0/1 per message
    (mirroring the runner); themes and statuses are invented. Lets the Topics
    tab render fully populated — including by_status — without any API call.
    """
    rng = Random(seed)
    codes = [category_code(name) for name in DEDUCTIVE_CATEGORY_NAMES]
    rows: list[LabelRow] = []
    # The planted topic shift needs each message's week, which only the corpus knows —
    # labels are written in a separate pass, so the phase map is rebuilt here from the
    # messages that exist rather than threaded through from seed_synthetic.
    labelled = con.execute("SELECT history_id, created_at FROM messages ORDER BY history_id").fetchall()
    weeks = {history_id: date_to_week(created_at.date()) for history_id, created_at in labelled}
    phase = _phase_by_week(sorted(set(weeks.values())))
    for history_id, _ in labelled:
        for i, code in enumerate(codes):
            value = 1 if rng.random() < 0.75 / (i + 1.3) else 0
            rows.append(LabelRow(history_id, CURRENT_LABEL_VERSION, "deductive", code, value, "synthetic-fixture"))
        shifted = _METHOD_THEME_SHIFT[phase[weeks[history_id]]]
        for domain, themes, p in (
            ("method_theme", _METHOD_THEMES, 0.35),
            ("software_theme", _SOFTWARE_THEMES, 0.2),
            ("emergent_theme", _EMERGENT_THEMES, 0.45),
        ):
            for theme in themes:
                # Only the first method theme carries the shift; the rest stay flat, so
                # the fixture also exercises candidates that correctly publish nothing.
                probability = shifted if theme == _METHOD_THEMES[0] else p
                if rng.random() < probability:
                    rows.append(LabelRow(history_id, CURRENT_LABEL_VERSION, domain, theme, 1, "synthetic-fixture"))
    write_labels(con, rows)
    # Reviewed synthetic theme set: aggregation publishes each emergent item's
    # description (1.2.0) from here, mirroring the real freeze-themes output.
    con.executemany(
        "INSERT OR REPLACE INTO theme_sets VALUES (?, ?, ?, now(), now())",
        [
            (SYNTHETIC_THEME_SET_VERSION, theme, f"Synthetic one-line description of {theme}.")
            for theme in _EMERGENT_THEMES
        ],
    )
    statuses: list[tuple[str, str, str | None, str]] = []
    for (pseudonym,) in con.execute("SELECT pseudonym FROM students ORDER BY pseudonym").fetchall():
        roll = rng.random()
        if roll < 0.35:
            statuses.append((pseudonym, "bachelor", None, "synthetic-roster"))
        elif roll < 0.45:  # BA→MA transitioner: resolves per session at usage time
            statuses.append((pseudonym, "bachelor", "2025W", "synthetic-roster"))
        elif roll < 0.92:
            statuses.append((pseudonym, "master", None, "synthetic-roster"))
        elif roll < 0.97:
            statuses.append((pseudonym, "staff", None, "synthetic-roster"))
        # else: no row -> resolves to 'unknown' (exercises the unknown group)
    con.executemany("INSERT OR REPLACE INTO student_status VALUES (?, ?, ?, ?)", statuses)
