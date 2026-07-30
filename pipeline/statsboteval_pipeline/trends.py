"""Period comparisons for the trends section (contract §7.6, D-49).

Two ideas carry this module, and they are deliberately separate:

**The gate decides what is admissible.** A candidate publishes only if both sides clear
the privacy floor on distinct contributing students, clear a minimum sample size, clear a
minimum effect size for its measure family, and clear p < .05 (Benjamini-Hochberg
adjusted for `robust`, unadjusted for `indicative`). One BH family per window covers
every candidate together (D-49 choice 7).

**Relevance decides what is shown.** Survivors sort by a pinned relevance tier first and
effect size only as the tie-break inside a tier, because the audience is a statistics
educator or a StatsBot evaluator asking "what should I look at?", not "what moved most?"
(D-49 choice 6). The tier is never published — the dashboard renders the order it
receives, since re-sorting would be re-aggregation (invariant 4).

Tiers were fixed *before* any dry run: they are a judgment about pedagogy, not an
empirical finding. The magnitude thresholds below are calibrated on one recorded
`preview-trends` pass and are PROVISIONAL until then.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .contract import (
    BaselineRef,
    Finding,
    MeasureValue,
    TrajectoryBaseline,
    TrajectoryPoint,
    TrendsSection,
    TrendsWindow,
    WeeksBaseline,
    Window,
    WindowBaseline,
    TREND_DEFAULT_TAB_CAP,
    TREND_MAX_FINDINGS,
    TREND_TAB_CAPS,
)
from .stats import benjamini_hochberg, classify_user, mann_whitney_u, median, poisson_rate_ratio, two_proportion_z
from .windows import TRAILING_WEEKS


class MessageLike(Protocol):
    """The message fields trends reads. Structural, so aggregate.py can import this
    module without this module importing aggregate.py."""

    @property
    def history_id(self) -> int: ...
    @property
    def pseudonym(self) -> str: ...
    @property
    def local(self) -> datetime: ...
    @property
    def week(self) -> str: ...
    @property
    def lang(self) -> str: ...


class SessionLike(Protocol):
    @property
    def pseudonym(self) -> str: ...
    @property
    def week(self) -> str: ...
    @property
    def n_messages(self) -> int: ...
    @property
    def duration_minutes(self) -> float: ...


# --- pinned thresholds and tiers (D-49) -----------------------------------------------

# Minimum absolute effect per measure *family*, not per kind (D-49 choice 11): language
# shares sit at 40-60% where 5 pp is an ordinary move, while an individual topic theme
# holds maybe 2-8% of messages, where 5 pp is unreachable. A single shares threshold
# would silently gate out exactly the tier-1 measures choices 8-9 promote.
MIN_ABS_EFFECT: dict[str, float] = {
    "language_share": 5.0,  # percentage points
    "timing_share": 5.0,  # percentage points
    "topic_share": 2.0,  # percentage points
    "user_share": 5.0,  # percentage points
    "volume_rate": 0.2231435513,  # |log ratio|; ln(1.25) = a 25% relative change
    "people_rate": 0.2231435513,
    "median": 0.2,  # |rank-biserial correlation|
}

# Small-base families additionally need a relative move, so a theme going 2.0 -> 4.1 pp
# qualifies while 30.0 -> 32.1 pp does not.
MIN_RELATIVE_CHANGE: dict[str, float] = {"topic_share": 0.30}

# Minimum observations per side: share denominators, rate counts, or sample sizes.
#
# `volume_rate` and `people_rate` are separate families for exactly this constant. The
# first counts events (messages, conversations — thousands per semester); the second counts
# *people* (active students, registrations — tens). A single rate min-n of 30 permanently
# gated active-students-per-week, which never has 30 "observations" in a window by
# construction. Found by the first preview-trends run, 2026-07-29.
MIN_N: dict[str, int] = {
    "language_share": 30,
    "timing_share": 30,
    "topic_share": 30,
    "user_share": 10,
    "volume_rate": 30,
    "people_rate": 8,
    "median": 10,
}

ALPHA = 0.05

# Deductive categories by tier. `Statistics Interaction` says whether the tool is being
# used for statistics at all; the politeness/greeting pair is linguistic texture with no
# teaching consequence. English/German Input are excluded outright — the Language tab
# already publishes that measure, and keeping both would put one phenomenon into the BH
# family twice and let it occupy two of five slots.
DEDUCTIVE_TIER_1 = ("statistics_interaction",)
DEDUCTIVE_TIER_3 = ("politeness_expression", "greeting_expression")
DEDUCTIVE_EXCLUDED = ("english_input", "german_input")

DAYPARTS: tuple[tuple[str, int, int], ...] = (
    ("morning", 6, 12),
    ("afternoon", 12, 18),
    ("evening", 18, 24),
    ("night", 0, 6),
)

_METHOD_NAMES = {
    "share": "two-proportion z",
    "rate": "Poisson log rate ratio",
    "median": "Mann-Whitney U",
}


# --- candidate declarations -----------------------------------------------------------


@dataclass(frozen=True)
class _Meta:
    id: str
    tab: str
    tier: int
    measure: str
    unit: str
    family: str
    footnote_ids: tuple[str, ...] = ()
    # Only the largest-effect member of a group competes for a slot (e.g. four dayparts
    # yield at most one finding, so a single shift cannot fill the tab).
    group: str | None = None
    rising: str = "rose"
    falling: str = "fell"


@dataclass(frozen=True)
class _ShareCandidate:
    meta: _Meta
    # weeks -> (numerator, denominator, students contributing to the numerator)
    extract: Callable[[frozenset[str]], tuple[int, int, set[str]]]
    kind: str = "share"


@dataclass(frozen=True)
class _RateCandidate:
    meta: _Meta
    # weeks -> (count, contributing students)
    extract: Callable[[frozenset[str]], tuple[int, set[str]]]
    kind: str = "rate"


@dataclass(frozen=True)
class _MedianCandidate:
    meta: _Meta
    # weeks -> (per-observation values, contributing students)
    extract: Callable[[frozenset[str]], tuple[list[float], set[str]]]
    kind: str = "median"


_Candidate = _ShareCandidate | _RateCandidate | _MedianCandidate


@dataclass(frozen=True)
class _Side:
    value: float
    n_students: int
    n_obs: int


@dataclass
class _Evaluated:
    meta: _Meta
    kind: str
    current: _Side
    baseline: _Side
    delta: float
    effect: float  # normalized magnitude for ranking
    p_value: float
    trajectory: list[TrajectoryPoint] | None = None
    p_adjusted: float = 1.0


# --- candidate pool -------------------------------------------------------------------


def _build_candidates(
    msgs: Sequence[MessageLike],
    sessions: Sequence[SessionLike],
    registrations: Sequence[tuple[str, str]],
    positives: Mapping[str, Mapping[str, set[int]]],
    deductive_labels: Mapping[str, str],
) -> list[_Candidate]:
    """The pinned candidate pool. One place, so the published footnote can describe it."""

    def in_weeks(weeks: frozenset[str]) -> list[MessageLike]:
        return [m for m in msgs if m.week in weeks]

    def sessions_in(weeks: frozenset[str]) -> list[SessionLike]:
        return [s for s in sessions if s.week in weeks]

    candidates: list[_Candidate] = []

    # ---- tier 1: what students need help with, and whether the tool is landing ----
    for domain, tab_label, tier in (("method_theme", "method", 1), ("emergent_theme", "theme", 1)):
        for code in sorted(positives.get(domain, {})):
            ids = positives[domain][code]
            candidates.append(
                _ShareCandidate(
                    meta=_Meta(
                        id=f"topics-{domain}-{code}",
                        tab="topics",
                        tier=tier,
                        measure=f"{code} ({tab_label}) share of messages",
                        unit="% of messages",
                        family="topic_share",
                        footnote_ids=("multi_label", "label_provenance"),
                    ),
                    extract=_share_of_messages(in_weeks, _labelled(ids)),
                )
            )

    for code, label in sorted(deductive_labels.items(), key=lambda kv: kv[1]):
        if code in DEDUCTIVE_EXCLUDED or code not in positives.get("deductive", {}):
            continue
        tier = 1 if code in DEDUCTIVE_TIER_1 else 3 if code in DEDUCTIVE_TIER_3 else 2
        candidates.append(
            _ShareCandidate(
                meta=_Meta(
                    id=f"topics-deductive-{code}",
                    tab="topics",
                    tier=tier,
                    measure=f"{label} share of messages",
                    unit="% of messages",
                    family="topic_share",
                    footnote_ids=("multi_label", "label_provenance"),
                ),
                extract=_share_of_messages(in_weeks, _labelled(positives["deductive"][code])),
            )
        )

    def one_time_share(weeks: frozenset[str]) -> tuple[int, int, set[str]]:
        stamps: dict[str, list[datetime]] = {}
        for m in in_weeks(weeks):
            stamps.setdefault(m.pseudonym, []).append(m.local)
        one_timers = {p for p, s in stamps.items() if classify_user(s) == "one_time"}
        return len(one_timers), len(stamps), one_timers

    candidates.append(
        _ShareCandidate(
            meta=_Meta(
                id="adoption-one-time-share",
                tab="adoption",
                tier=1,
                measure="One-time users among active students",
                unit="% of active students",
                family="user_share",
                footnote_ids=("user_class_definitions",),
            ),
            extract=one_time_share,
        )
    )

    # ---- tier 2: how students are working ----
    candidates.append(
        _MedianCandidate(
            meta=_Meta(
                id="engagement-messages-per-session",
                tab="engagement",
                tier=2,
                measure="Median messages per conversation",
                unit="messages",
                family="median",
                footnote_ids=("chat_fragmentation",),
                rising="lengthened",
                falling="shortened",
            ),
            extract=lambda weeks: (
                [float(s.n_messages) for s in sessions_in(weeks)],
                {s.pseudonym for s in sessions_in(weeks)},
            ),
        )
    )
    candidates.append(
        _MedianCandidate(
            meta=_Meta(
                id="engagement-session-duration",
                tab="engagement",
                tier=2,
                measure="Median conversation length",
                unit="minutes",
                family="median",
                footnote_ids=("chat_fragmentation", "duration_definition"),
                rising="lengthened",
                falling="shortened",
            ),
            extract=lambda weeks: (
                [s.duration_minutes for s in sessions_in(weeks)],
                {s.pseudonym for s in sessions_in(weeks)},
            ),
        )
    )
    for code in sorted(positives.get("software_theme", {})):
        candidates.append(
            _ShareCandidate(
                meta=_Meta(
                    id=f"topics-software_theme-{code}",
                    tab="topics",
                    tier=2,
                    measure=f"{code} (software) share of messages",
                    unit="% of messages",
                    family="topic_share",
                    footnote_ids=("multi_label", "label_provenance"),
                ),
                extract=_share_of_messages(in_weeks, _labelled(positives["software_theme"][code])),
            )
        )

    candidates.append(
        _ShareCandidate(
            meta=_Meta(
                id="timing-weekend-share",
                tab="timing",
                tier=2,
                measure="Weekend share of messages",
                unit="% of messages",
                family="timing_share",
            ),
            extract=_share_of_messages(in_weeks, lambda m: m.local.isoweekday() >= 6),
        )
    )
    for name, lo, hi in DAYPARTS:
        candidates.append(
            _ShareCandidate(
                meta=_Meta(
                    id=f"timing-daypart-{name}",
                    tab="timing",
                    tier=2,
                    measure=f"{name.capitalize()} share of messages ({lo:02d}-{hi:02d})",
                    unit="% of messages",
                    family="timing_share",
                    group="daypart",
                ),
                extract=_share_of_messages(in_weeks, _in_daypart(lo, hi)),
            )
        )

    # ---- tier 3: context ----
    for code, label in (("de", "German"), ("en", "English")):
        candidates.append(
            _ShareCandidate(
                meta=_Meta(
                    id=f"language-{code}-share",
                    tab="language",
                    tier=3,
                    measure=f"{label} share of messages",
                    unit="% of messages",
                    family="language_share",
                    footnote_ids=("language_heuristic",),
                    group="language",
                ),
                extract=_share_of_messages(in_weeks, _has_lang(code)),
            )
        )

    candidates.append(
        _RateCandidate(
            meta=_Meta(
                id="adoption-messages-per-week",
                tab="adoption",
                tier=3,
                measure="Messages per week",
                unit="per week",
                family="volume_rate",
                footnote_ids=("per_week_rate",),
            ),
            extract=lambda weeks: (len(in_weeks(weeks)), {m.pseudonym for m in in_weeks(weeks)}),
        )
    )
    candidates.append(
        _RateCandidate(
            meta=_Meta(
                id="adoption-sessions-per-week",
                tab="adoption",
                tier=3,
                measure="Conversations per week",
                unit="per week",
                family="volume_rate",
                footnote_ids=("per_week_rate", "chat_fragmentation"),
            ),
            extract=lambda weeks: (
                len(sessions_in(weeks)),
                {s.pseudonym for s in sessions_in(weeks)},
            ),
        )
    )
    candidates.append(
        _RateCandidate(
            meta=_Meta(
                id="adoption-active-students-per-week",
                tab="adoption",
                tier=3,
                measure="Active students per week",
                unit="per week",
                family="people_rate",
                footnote_ids=("per_week_rate",),
            ),
            extract=lambda weeks: (
                len({m.pseudonym for m in in_weeks(weeks)}),
                {m.pseudonym for m in in_weeks(weeks)},
            ),
        )
    )

    def regs(weeks: frozenset[str]) -> tuple[int, set[str]]:
        hits = [p for p, week in registrations if week in weeks]
        return len(hits), set(hits)

    candidates.append(
        _RateCandidate(
            meta=_Meta(
                id="adoption-registrations-per-week",
                tab="adoption",
                tier=3,
                measure="New registrations per week",
                unit="per week",
                family="people_rate",
                footnote_ids=("per_week_rate", "bachelor_onboarding"),
            ),
            extract=regs,
        )
    )
    return candidates


def _in_daypart(lo: int, hi: int) -> Callable[[MessageLike], bool]:
    return lambda m: lo <= m.local.hour < hi


def _has_lang(code: str) -> Callable[[MessageLike], bool]:
    return lambda m: m.lang == code


def _labelled(ids: set[int]) -> Callable[[MessageLike], bool]:
    return lambda m: m.history_id in ids


def _share_of_messages(
    in_weeks: Callable[[frozenset[str]], list[MessageLike]], keep: Callable[[MessageLike], bool]
) -> Callable[[frozenset[str]], tuple[int, int, set[str]]]:
    """(matching, total, students behind the matches) for a week set.

    Every share candidate is a predicate over messages, so there is one extractor and a
    family of predicate factories above it — label membership, language, daypart, weekend.
    """

    def extract(weeks: frozenset[str]) -> tuple[int, int, set[str]]:
        subset = in_weeks(weeks)
        hits = [m for m in subset if keep(m)]
        return len(hits), len(subset), {m.pseudonym for m in hits}

    return extract


# --- evaluation -----------------------------------------------------------------------


def _evaluate(candidate: _Candidate, current: frozenset[str], baseline: frozenset[str]) -> _Evaluated | None:
    """Compute both sides and the test. None when the measure is undefined on a side."""
    meta = candidate.meta
    if isinstance(candidate, _ShareCandidate):
        num_c, den_c, students_c = candidate.extract(current)
        num_b, den_b, students_b = candidate.extract(baseline)
        if den_c == 0 or den_b == 0:
            return None
        share_test = two_proportion_z(num_c, den_c, num_b, den_b)
        return _Evaluated(
            meta=meta,
            kind="share",
            current=_Side(num_c / den_c * 100.0, len(students_c), den_c),
            baseline=_Side(num_b / den_b * 100.0, len(students_b), den_b),
            delta=share_test.delta_pp,
            effect=abs(share_test.delta_pp),
            p_value=share_test.p_value,
        )

    if isinstance(candidate, _RateCandidate):
        count_c, students_c = candidate.extract(current)
        count_b, students_b = candidate.extract(baseline)
        if count_c == 0 or count_b == 0 or not current or not baseline:
            return None
        weeks_c, weeks_b = len(current), len(baseline)
        rate_test = poisson_rate_ratio(count_c, weeks_c, count_b, weeks_b)
        rate_c, rate_b = count_c / weeks_c, count_b / weeks_b
        return _Evaluated(
            meta=meta,
            kind="rate",
            current=_Side(rate_c, len(students_c), count_c),
            baseline=_Side(rate_b, len(students_b), count_b),
            delta=rate_c - rate_b,
            effect=abs(rate_test.log_ratio),
            p_value=rate_test.p_value,
        )

    values_c, students_c = candidate.extract(current)
    values_b, students_b = candidate.extract(baseline)
    if not values_c or not values_b:
        return None
    median_test = mann_whitney_u(values_c, values_b)
    median_c, median_b = median(values_c), median(values_b)
    return _Evaluated(
        meta=meta,
        kind="median",
        current=_Side(median_c, len(students_c), len(values_c)),
        baseline=_Side(median_b, len(students_b), len(values_b)),
        delta=median_c - median_b,
        effect=abs(median_test.rank_biserial),
        p_value=median_test.p_value,
    )


def _passes_effect_gate(ev: _Evaluated) -> bool:
    """Gate (c): the per-family minimum effect size, plus a relative floor where the base
    is small enough that percentage points alone would be the wrong scale."""
    family = ev.meta.family
    if ev.effect < MIN_ABS_EFFECT[family]:
        return False
    relative = MIN_RELATIVE_CHANGE.get(family)
    if relative is not None and ev.baseline.value > 0:
        if abs(ev.current.value - ev.baseline.value) / ev.baseline.value < relative:
            return False
    return True


def _title(ev: _Evaluated) -> str:
    """Template-generated from pinned measure names — never from chat text (D-49)."""
    direction = ev.meta.rising if ev.delta > 0 else ev.meta.falling
    return f"{ev.meta.measure} {direction}"


def _to_finding(ev: _Evaluated, *, evidence: str) -> Finding:
    footnotes = ["trend_method", *ev.meta.footnote_ids]
    if ev.trajectory is not None:
        footnotes.append("cohort_turnover")
    return Finding(
        id=ev.meta.id,
        tab=ev.meta.tab,  # type: ignore[arg-type]
        title=_title(ev),
        measure=ev.meta.measure,
        kind=ev.kind,  # type: ignore[arg-type]
        unit=ev.meta.unit,
        current=MeasureValue(value=round(ev.current.value, 1), n_students=ev.current.n_students),
        baseline=MeasureValue(value=round(ev.baseline.value, 1), n_students=ev.baseline.n_students),
        delta=round(ev.delta, 1),
        evidence=evidence,  # type: ignore[arg-type]
        method=f"{_METHOD_NAMES[ev.kind]}, BH-adjusted",
        trajectory=ev.trajectory,
        footnote_ids=footnotes,
    )


# Why a candidate did not publish. Reported by preview-trends so a threshold can be
# calibrated against what it actually excluded, rather than guessed at.
GATE_FLOOR = "floor"
GATE_MIN_N = "min-n"
GATE_EFFECT = "effect"
GATE_P = "p"
GATE_GROUP = "group"
GATE_CAP = "cap"


@dataclass(frozen=True)
class CandidateOutcome:
    """One candidate's fate in one window — a preview-trends row."""

    id: str
    tab: str
    tier: int
    kind: str
    family: str
    measure: str
    current: _Side
    baseline: _Side
    delta: float
    effect: float
    p_value: float
    p_adjusted: float
    verdict: str  # robust | indicative | one of the GATE_* reasons

    @property
    def published(self) -> bool:
        return self.verdict in ("robust", "indicative")


def _outcome(ev: _Evaluated, verdict: str) -> CandidateOutcome:
    return CandidateOutcome(
        id=ev.meta.id,
        tab=ev.meta.tab,
        tier=ev.meta.tier,
        kind=ev.kind,
        family=ev.meta.family,
        measure=ev.meta.measure,
        current=ev.current,
        baseline=ev.baseline,
        delta=ev.delta,
        effect=ev.effect,
        p_value=ev.p_value,
        p_adjusted=ev.p_adjusted,
        verdict=verdict,
    )


def _assess(evaluated: list[_Evaluated], floor_n: int) -> tuple[list[Finding], bool, list[CandidateOutcome]]:
    """Apply the gate, then rank by relevance.

    Returns (findings, insufficient_data, per-candidate outcomes). build_trends uses the
    first two; preview-trends uses the third. One implementation, so the dry run can
    never describe a different rule than the publish applies.

    For shares, `n_students` counts the students behind the **numerator**, matching how
    the same measure is floored in the topics section. That is required, not conventional:
    if Topics suppresses "Theme X" for having fewer than N contributing students, a Trends
    card reporting "Theme X share fell to 0.5%" would leak precisely what the suppression
    withheld. The consequence is deliberate — a measure that falls to exactly zero has no
    contributing students on that side and so publishes no finding.

    A candidate failing the floor or minimum-n gate was never testable, which is what
    distinguishes a break week's `insufficient_data` from a genuine "nothing changed".
    """
    outcomes: list[CandidateOutcome] = []
    testable: list[_Evaluated] = []
    for ev in evaluated:
        if ev.current.n_students < floor_n or ev.baseline.n_students < floor_n:
            outcomes.append(_outcome(ev, GATE_FLOOR))
            continue
        min_n = MIN_N[ev.meta.family]
        if ev.current.n_obs < min_n or ev.baseline.n_obs < min_n:
            outcomes.append(_outcome(ev, GATE_MIN_N))
            continue
        testable.append(ev)

    if not testable:
        # Nothing was testable at all — a break week, not a flat period. Unconditionally
        # true: reaching here with `evaluated` empty means no candidate was even defined
        # (every measure undefined on a side), which is *more* insufficient, not less.
        # Only assess_windows' `baseline is None` path may report False, and it returns
        # before calling this.
        return [], True, outcomes

    # One BH family per window, over every testable candidate (D-49 choice 7).
    for ev, q in zip(testable, benjamini_hochberg([ev.p_value for ev in testable]), strict=True):
        ev.p_adjusted = q

    survivors: list[_Evaluated] = []
    for ev in testable:
        if not _passes_effect_gate(ev):
            outcomes.append(_outcome(ev, GATE_EFFECT))
        elif ev.p_value >= ALPHA:
            outcomes.append(_outcome(ev, GATE_P))
        else:
            survivors.append(ev)

    # Within a compete-group only the largest effect proceeds, so four dayparts or two
    # language shares cannot spend several slots describing one shift.
    best_in_group: dict[str, _Evaluated] = {}
    winner_ids: set[str] = set()
    for ev in survivors:
        group = ev.meta.group
        if group is None:
            winner_ids.add(ev.meta.id)
        elif group not in best_in_group or ev.effect > best_in_group[group].effect:
            best_in_group[group] = ev
    winner_ids |= {ev.meta.id for ev in best_in_group.values()}
    for ev in survivors:
        if ev.meta.id not in winner_ids:
            outcomes.append(_outcome(ev, GATE_GROUP))

    # Relevance first, effect size only as the tie-break inside a tier (D-49 choice 6).
    contenders = sorted(
        (ev for ev in survivors if ev.meta.id in winner_ids),
        key=lambda ev: (ev.meta.tier, -ev.effect, ev.meta.id),
    )

    findings: list[Finding] = []
    per_tab: dict[str, int] = {}
    for ev in contenders:
        cap = TREND_TAB_CAPS.get(ev.meta.tab, TREND_DEFAULT_TAB_CAP)
        if len(findings) >= TREND_MAX_FINDINGS or per_tab.get(ev.meta.tab, 0) >= cap:
            outcomes.append(_outcome(ev, GATE_CAP))
            continue
        per_tab[ev.meta.tab] = per_tab.get(ev.meta.tab, 0) + 1
        evidence = "robust" if ev.p_adjusted < ALPHA else "indicative"
        findings.append(_to_finding(ev, evidence=evidence))
        outcomes.append(_outcome(ev, evidence))
    return findings, False, outcomes


# --- window pairing -------------------------------------------------------------------


def _semester_windows(windows: Sequence[Window]) -> list[Window]:
    """Semesters in chronological order (build_windows emits them in axis order)."""
    return [w for w in windows if w.kind == "semester"]


def _covered(window: Window, axis: Sequence[str]) -> frozenset[str]:
    if window.kind == "all_time":
        return frozenset(axis)
    return frozenset(window.weeks) & frozenset(axis)


def _pair_for(
    window: Window, windows: Sequence[Window], axis: Sequence[str]
) -> tuple[BaselineRef | None, frozenset[str]]:
    """The baseline reference and its week set, per the D-49 pairing table."""
    if window.kind == "all_time":
        semesters = _semester_windows(windows)
        if len(semesters) < 2:
            return None, frozenset()
        return TrajectoryBaseline(kind="trajectory"), _covered(semesters[0], axis)

    if window.kind == "semester":
        semesters = _semester_windows(windows)
        index = next((i for i, w in enumerate(semesters) if w.id == window.id), None)
        if index is None or index == 0:
            return None, frozenset()
        previous = semesters[index - 1]
        return WindowBaseline(kind="window", window_id=previous.id), _covered(previous, axis)

    # trailing_4: the TRAILING_WEEKS complete weeks immediately before it. Embedded as a
    # comparison rather than added to the registry — it is not something to select.
    if len(axis) < 2 * TRAILING_WEEKS:
        return None, frozenset()
    weeks = list(axis[-2 * TRAILING_WEEKS : -TRAILING_WEEKS])
    return WeeksBaseline(kind="weeks", from_=weeks[0], through=weeks[-1]), frozenset(weeks)


def _trajectory(
    candidate: _Candidate, semesters: Sequence[Window], axis: Sequence[str], floor_n: int
) -> list[TrajectoryPoint] | None:
    """One point per semester. None if any point is sub-floor or undefined — a gap would
    misrepresent the shape, and the contract requires every point to clear the floor."""
    points: list[TrajectoryPoint] = []
    for semester in semesters:
        weeks = _covered(semester, axis)
        ev = _evaluate(candidate, weeks, weeks)
        if ev is None or ev.current.n_students < floor_n:
            return None
        points.append(
            TrajectoryPoint(
                window_id=semester.id,
                value=round(ev.current.value, 1),
                n_students=ev.current.n_students,
            )
        )
    return points


@dataclass(frozen=True)
class WindowAssessment:
    window_id: str
    baseline: BaselineRef | None
    findings: list[Finding]
    insufficient_data: bool
    outcomes: list[CandidateOutcome]


def assess_windows(
    *,
    msgs: Sequence[MessageLike],
    sessions: Sequence[SessionLike],
    registrations: Sequence[tuple[str, str]],
    windows: Sequence[Window],
    axis: Sequence[str],
    floor_n: int,
    positives: Mapping[str, Mapping[str, set[int]]] | None = None,
    deductive_labels: Mapping[str, str] | None = None,
) -> list[WindowAssessment]:
    """Evaluate every candidate in every window, keeping the gate diagnostics.

    The single implementation behind both `build_trends` (which publishes the findings)
    and `preview-trends` (which prints why the rest were dropped).
    """
    candidates = _build_candidates(msgs, sessions, registrations, positives or {}, deductive_labels or {})
    semesters = _semester_windows(windows)

    assessments: list[WindowAssessment] = []
    for window in windows:
        baseline, baseline_weeks = _pair_for(window, windows, axis)
        if baseline is None:
            assessments.append(WindowAssessment(window.id, None, [], False, []))
            continue

        current_weeks = _covered(window, axis)
        if isinstance(baseline, TrajectoryBaseline):
            # Significance comes from the endpoint test (first vs last semester); the
            # full trajectory is published alongside. A trend test is a noted upgrade.
            current_weeks = _covered(semesters[-1], axis)

        evaluated: list[_Evaluated] = []
        for candidate in candidates:
            ev = _evaluate(candidate, current_weeks, baseline_weeks)
            if ev is None:
                continue
            if isinstance(baseline, TrajectoryBaseline):
                points = _trajectory(candidate, semesters, axis, floor_n)
                if points is None:
                    continue
                ev.trajectory = points
            evaluated.append(ev)

        findings, insufficient, outcomes = _assess(evaluated, floor_n)
        assessments.append(WindowAssessment(window.id, baseline, findings, insufficient, outcomes))
    return assessments


def build_trends(
    *,
    msgs: Sequence[MessageLike],
    sessions: Sequence[SessionLike],
    registrations: Sequence[tuple[str, str]],
    windows: Sequence[Window],
    axis: Sequence[str],
    floor_n: int,
    positives: Mapping[str, Mapping[str, set[int]]] | None = None,
    deductive_labels: Mapping[str, str] | None = None,
) -> TrendsSection:
    """Period comparisons for every published window (contract §7.6).

    Reuses the in-memory structures build_aggregates already has; no DuckDB access. Topic
    candidates appear only when a classification version was published, which is why
    `positives` is optional rather than empty-by-default.
    """
    assessments = assess_windows(
        msgs=msgs,
        sessions=sessions,
        registrations=registrations,
        windows=windows,
        axis=axis,
        floor_n=floor_n,
        positives=positives,
        deductive_labels=deductive_labels,
    )
    return TrendsSection(
        per_window={
            a.window_id: TrendsWindow(baseline=a.baseline, insufficient_data=a.insufficient_data, findings=a.findings)
            for a in assessments
        }
    )


_VERDICT_LEGEND = (
    ("robust", "published; significant after BH correction"),
    ("indicative", "published; significant before BH correction only"),
    (GATE_CAP, "passed every gate but displaced by a higher tier or a tab cap"),
    (GATE_GROUP, "lost to a larger sibling in its compete group (dayparts, languages)"),
    (GATE_P, "not significant at p < .05 even unadjusted"),
    (GATE_EFFECT, "change too small for its measure family"),
    (GATE_MIN_N, "too few observations on a side to test"),
    (GATE_FLOOR, "fewer than the privacy floor of contributing students on a side"),
)


def _describe_baseline(baseline: BaselineRef | None) -> str:
    if baseline is None:
        return "no earlier period to compare"
    if isinstance(baseline, WindowBaseline):
        return f"vs {baseline.window_id}"
    if isinstance(baseline, WeeksBaseline):
        return f"vs weeks {baseline.from_}..{baseline.through}"
    return "vs first semester (trajectory)"


def format_candidate_preview(
    assessments: Sequence[WindowAssessment], *, floor_n: int, only_window: str | None = None
) -> str:
    """The full pre-selection candidate table — what published, what didn't, and why.

    Written for threshold calibration (D-49): the thresholds in force are printed above
    the table so a run is self-documenting, and every dropped candidate names its gate so
    a change can be argued from what it actually excluded.
    """
    out: list[str] = ["Thresholds in force (trends.py constants, D-49)", ""]
    out.append(f"  {'family':<16}{'min effect':>12}{'relative':>11}{'min n':>8}")
    for family in sorted(MIN_ABS_EFFECT):
        relative = MIN_RELATIVE_CHANGE.get(family)
        out.append(
            f"  {family:<16}{MIN_ABS_EFFECT[family]:>12.4g}"
            f"{(f'{relative:.0%}' if relative else '—'):>11}{MIN_N[family]:>8}"
        )
    out.append(f"  alpha = {ALPHA}   privacy floor = {floor_n} students   cap = {TREND_MAX_FINDINGS}")
    out.append(
        f"  per-tab caps: {', '.join(f'{k}={v}' for k, v in sorted(TREND_TAB_CAPS.items()))}"
        f", default={TREND_DEFAULT_TAB_CAP}"
    )

    header = (
        f"{'tier':>4}  {'tab':<11}{'candidate':<52}{'base':>9}{'curr':>9}"
        f"{'delta':>9}{'effect':>8}{'p':>8}{'BH-p':>8}  {'n_stu':<9}{'n_obs':<13}verdict"
    )
    for assessment in assessments:
        if only_window is not None and assessment.window_id != only_window:
            continue
        out += ["", f"=== {assessment.window_id}  {_describe_baseline(assessment.baseline)} ==="]
        if assessment.baseline is None:
            out.append("  (empty state — nothing to compare)")
            continue
        if assessment.insufficient_data:
            out.append("  insufficient_data: no candidate was testable (break weeks or too little activity)")
        if not assessment.outcomes:
            out.append("  (no candidates)")
            continue
        out.append(header)
        rows = sorted(assessment.outcomes, key=lambda o: (o.tier, -o.effect, o.id))
        for o in rows:
            out.append(
                f"{o.tier:>4}  {o.tab:<11}{o.id[:51]:<52}"
                f"{o.baseline.value:>9.1f}{o.current.value:>9.1f}{o.delta:>+9.1f}{o.effect:>8.3f}"
                f"{o.p_value:>8.4f}{o.p_adjusted:>8.4f}  "
                f"{f'{o.baseline.n_students}/{o.current.n_students}':<9}"
                f"{f'{o.baseline.n_obs}/{o.current.n_obs}':<13}{o.verdict}"
            )
        tally: dict[str, int] = {}
        for o in rows:
            tally[o.verdict] = tally.get(o.verdict, 0) + 1
        published = sum(n for verdict, n in tally.items() if verdict in ("robust", "indicative"))
        detail = ", ".join(f"{verdict} {n}" for verdict, n in sorted(tally.items()))
        out.append(f"  -> {published} published of {len(rows)} candidates  ({detail})")

    out += ["", "verdicts:"]
    out += [f"  {verdict:<11}{gist}" for verdict, gist in _VERDICT_LEGEND]
    return "\n".join(out)


def iter_candidate_ids(
    positives: Mapping[str, Mapping[str, set[int]]] | None = None,
    deductive_labels: Mapping[str, str] | None = None,
) -> Iterable[str]:
    """Candidate ids in pool order, without needing a corpus to build them.

    Test-facing: it lets the pinned pool be asserted directly (which measures exist, what
    topic labels add, what is excluded) rather than inferred from a run's output.
    preview-trends prints the pool via format_candidate_preview, which needs the evaluated
    candidates, not just their ids.
    """
    return (c.meta.id for c in _build_candidates([], [], [], positives or {}, deductive_labels or {}))
