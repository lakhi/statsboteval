"""Hand-rolled statistics shared by aggregate.py and trends.py.

No numpy/scipy: the pipeline carries no numerical dependency and is not gaining one for
a handful of estimators. Every function reproduces a named published formula and is
unit-tested against worked examples with pinned expected values, so correctness does not
rest on library parity.

This module is deliberately dependency-free within the package. aggregate.py builds
sections and trends.py builds findings; both need the same median estimator and the same
user typology, and aggregate.py imports trends.py — so the shared estimators live below
both rather than in either (importing them from aggregate.py would be circular).

Framing for the hypothesis tests (D-49): this corpus is a census of StatsBot users, not
a sample drawn from a larger population. They are a guard against over-reading noise in
short periods, not inference to a population. They gate what may be published; the
*ranking* is by educator relevance, not by p-value.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal, NamedTuple


def quantile_type2(sorted_vals: Sequence[float], p: float) -> float:
    """R quantile type 2 — the estimator the Bergmann reference scripts use.

    Shared so that a median shown on the Engagement tab and the same median compared on
    the Trends tab can never disagree.
    """
    n = len(sorted_vals)
    h = n * p + 0.5
    lo = min(max(math.ceil(h - 0.5), 1), n)
    hi = min(max(math.floor(h + 0.5), 1), n)
    return (sorted_vals[lo - 1] + sorted_vals[hi - 1]) / 2


def median(values: Sequence[float]) -> float:
    """Type-2 median of an unsorted sample."""
    if not values:
        raise ValueError("median of an empty sample")
    return quantile_type2(sorted(values), 0.5)


UserClass = Literal["one_time", "monthly", "sporadic"]


class _Usage(NamedTuple):
    """The three quantities every Bergmann typology rule is written in terms of."""

    span_days: int  # calendar-day span, inclusive (their max_day - min_day + 1)
    within_24h: bool  # their timedif <= 24 (a difftime; the intent is 24 hours)
    gaps: list[int]  # their diff(days_since): day gaps between consecutive messages


def _usage(stamps: Sequence[datetime]) -> _Usage:
    if not stamps:
        raise ValueError("cannot classify a user with no activity")
    ordered = sorted(stamps)
    days = [s.date() for s in ordered]
    return _Usage(
        span_days=(days[-1] - days[0]).days + 1,
        within_24h=ordered[-1] - ordered[0] <= timedelta(hours=24),
        gaps=[(b - a).days for a, b in zip(days, days[1:], strict=False)],
    )


def classify_user(stamps: Sequence[datetime]) -> UserClass:
    """Bergmann engagement typology, the three classes that partition the users.

    Verified verbatim against OSF script `30_Analysis Step 3 - Table K1 & subgroup
    analysis.R` (Bergmann et al., 2026; re-checked 2026-07-30):

        one_time_user   <- all(span_days < 3) & all(timedif <= 24)
        occasional_user <- all(diffs < 30) & span_days >= 30      # the paper's "monthly"
        sporadic_user   <- one_time_user == 0 & occasional_user == 0

    Their script sets five *independent indicator flags*, not one exclusive class.
    These three happen to partition the users (one-time needs span < 3, occasional
    needs span >= 30, and sporadic is defined as the complement of both), which is
    why a single-valued classifier reproduces their counts exactly. `frequent` does
    NOT partition — see is_frequent.

    Shared with trends.py so the one-time-user share compared between periods is the
    same quantity the Adoption tab publishes.
    """
    usage = _usage(stamps)
    if usage.span_days < 3 and usage.within_24h:
        return "one_time"
    if all(g < 30 for g in usage.gaps) and usage.span_days >= 30:
        return "monthly"
    return "sporadic"


def is_frequent(stamps: Sequence[datetime]) -> bool:
    """Bergmann's `frequent_user <- all(diffs < 14) & span_days > 30`.

    A *sub-count of* monthly, not a fourth class: all gaps < 14 implies all gaps < 30,
    and span > 30 implies span >= 30, so every frequent user is also one of their
    occasional (= our monthly) users. Publishing it as an exclusive class would make
    our "monthly" stop meaning their `occasional_user` the moment one exists. n = 0 in
    their data and in ours; published so a future non-zero is visible rather than
    silently folded in.
    """
    usage = _usage(stamps)
    return all(g < 14 for g in usage.gaps) and usage.span_days > 30


def normal_sf(z: float) -> float:
    """Upper-tail probability of the standard normal, P(Z > z).

    erfc rather than 1 - erf: the complement keeps full precision in the tail, where
    1 - erf(z) cancels catastrophically.
    """
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_p(z: float) -> float:
    return min(1.0, 2.0 * normal_sf(abs(z)))


class ProportionTest(NamedTuple):
    z: float
    p_value: float
    delta_pp: float  # (p1 - p2) in percentage points — the effect size for shares


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> ProportionTest:
    """Pooled two-proportion z test, two-sided.

    z = (p1 - p2) / sqrt(p(1-p)(1/n1 + 1/n2)) with p the pooled proportion — the
    standard large-sample test for equality of two independent proportions. No
    continuity correction: that is the chi-square (Yates) analogue, and applying both
    double-counts the adjustment.

    Degenerate case: when nobody or everybody is a success in the combined sample the
    pooled variance is zero and the two proportions are necessarily equal, so there is
    nothing to detect — reported as z = 0, p = 1.
    """
    if n1 <= 0 or n2 <= 0:
        raise ValueError("two_proportion_z needs positive denominators")
    if not (0 <= x1 <= n1) or not (0 <= x2 <= n2):
        raise ValueError("successes must lie within their denominators")

    p1, p2 = x1 / n1, x2 / n2
    delta_pp = (p1 - p2) * 100.0
    pooled = (x1 + x2) / (n1 + n2)
    variance = pooled * (1.0 - pooled) * (1.0 / n1 + 1.0 / n2)
    if variance <= 0.0:
        return ProportionTest(z=0.0, p_value=1.0, delta_pp=delta_pp)
    z = (p1 - p2) / math.sqrt(variance)
    return ProportionTest(z=z, p_value=two_sided_p(z), delta_pp=delta_pp)


def _average_ranks(values: Sequence[float]) -> tuple[list[float], list[int]]:
    """Midranks (ties share their mean rank), plus the size of each group of ties."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    tie_sizes: list[int] = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        midrank = (i + j + 2) / 2.0  # ranks are 1-based: mean of (i+1) and (j+1)
        for k in range(i, j + 1):
            ranks[order[k]] = midrank
        if j > i:
            tie_sizes.append(j - i + 1)
        i = j + 1
    return ranks, tie_sizes


class MannWhitneyTest(NamedTuple):
    u: float  # U for the first sample
    z: float
    p_value: float
    rank_biserial: float  # (U1 - U2) / (n1 n2) ∈ [-1, 1] — the effect size for medians


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> MannWhitneyTest:
    """Mann–Whitney U, normal approximation with tie correction and continuity correction.

    U1 = R1 - n1(n1+1)/2 from midranks over the pooled sample; under H0,
    E[U] = n1 n2 / 2 and

        Var[U] = (n1 n2 / 12) * ((N + 1) - Σ(t³ - t) / (N(N - 1)))

    over tie groups of size t (Mann & Whitney 1947; tie correction per Siegel &
    Castellan). The continuity correction subtracts 0.5 from |U - E[U]|, which is
    conservative — the right direction for a noise gate.

    Effect size is the rank-biserial correlation (U1 - U2)/(n1 n2): -1 when every
    observation in `a` is below every observation in `b`, +1 when reversed, 0 at
    stochastic equality.

    Degenerate case: when every pooled value is identical the variance is zero and the
    samples are indistinguishable — reported as z = 0, p = 1, r = 0.
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("mann_whitney_u needs non-empty samples")

    ranks, tie_sizes = _average_ranks([*a, *b])
    n = n1 + n2
    u1 = sum(ranks[:n1]) - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    rank_biserial = (u1 - u2) / (n1 * n2)

    tie_term = sum(t**3 - t for t in tie_sizes) / (n * (n - 1)) if n > 1 else 0.0
    variance = (n1 * n2 / 12.0) * ((n + 1) - tie_term)
    if variance <= 0.0:
        return MannWhitneyTest(u=u1, z=0.0, p_value=1.0, rank_biserial=rank_biserial)

    centered = u1 - n1 * n2 / 2.0
    corrected = max(abs(centered) - 0.5, 0.0)
    z = math.copysign(corrected / math.sqrt(variance), centered)
    return MannWhitneyTest(u=u1, z=z, p_value=two_sided_p(z), rank_biserial=rank_biserial)


class RateRatioTest(NamedTuple):
    log_ratio: float  # log(rate1 / rate2) — |log_ratio| is the effect size for rates
    z: float
    p_value: float


def poisson_rate_ratio(count1: int, weeks1: float, count2: int, weeks2: float) -> RateRatioTest:
    """Log rate-ratio z test for two counts observed over different exposures.

    rate = count / weeks; z = log(rate1/rate2) / sqrt(1/count1 + 1/count2), the standard
    large-sample Poisson rate-ratio approximation (Rothman, *Modern Epidemiology*, ch. 14).

    **Assumes independent events, which message and session counts violate**: one student
    contributes many messages, so the counts are clustered and over-dispersed relative to
    Poisson, and this p-value is anti-conservative. It is used only as a coarse noise gate
    on tier-3 volume measures, behind a minimum relative-change floor that does the real
    filtering, and the `trend_method` footnote states the assumption. See D-49.
    """
    if weeks1 <= 0 or weeks2 <= 0:
        raise ValueError("poisson_rate_ratio needs positive exposures")
    if count1 <= 0 or count2 <= 0:
        raise ValueError("poisson_rate_ratio needs positive counts on both sides")

    log_ratio = math.log((count1 / weeks1) / (count2 / weeks2))
    z = log_ratio / math.sqrt(1.0 / count1 + 1.0 / count2)
    return RateRatioTest(log_ratio=log_ratio, z=z, p_value=two_sided_p(z))


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """BH-adjusted p-values (Benjamini & Hochberg 1995), returned in input order.

    q(i) = min over j >= i of (m / j) * p(j) on the ascending-sorted p-values, clamped
    to 1 and enforced monotone by the running minimum. Rejecting every q < alpha
    controls the false discovery rate at alpha — the guarantee we want when one family
    covers every candidate in a window (D-49 choice 7).
    """
    m = len(p_values)
    if m == 0:
        return []
    if any(not (0.0 <= p <= 1.0) for p in p_values):
        raise ValueError("p-values must lie in [0, 1]")

    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 1.0
    # Walk from the largest p-value down, so the running minimum enforces monotonicity.
    for steps, idx in enumerate(reversed(order)):
        rank = m - steps  # 1-based ascending rank of this p-value
        running = min(running, m / rank * p_values[idx])
        adjusted[idx] = min(running, 1.0)
    return adjusted
