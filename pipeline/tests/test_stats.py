"""Estimators behind the trends section (D-49).

Every expected value is either hand-computable in closed form or a published worked
example, pinned as a literal. The point of hand-rolling these (no scipy in the pipeline)
is that correctness has to be demonstrated rather than inherited, so tests assert against
the source formula's own arithmetic, never against a second implementation.
"""

import math

import pytest

from statsboteval_pipeline.stats import (
    benjamini_hochberg,
    mann_whitney_u,
    normal_sf,
    poisson_rate_ratio,
    two_proportion_z,
    two_sided_p,
)

# --- normal tail ----------------------------------------------------------------------


def test_normal_sf_at_textbook_quantiles() -> None:
    # The three quantiles every table lists: two-sided 5%, 10% and 1%.
    assert normal_sf(0.0) == pytest.approx(0.5)
    assert normal_sf(1.959963985) == pytest.approx(0.025, abs=1e-9)
    assert normal_sf(1.644853627) == pytest.approx(0.05, abs=1e-9)
    assert normal_sf(2.575829304) == pytest.approx(0.005, abs=1e-9)


def test_normal_sf_survives_the_far_tail() -> None:
    # 1 - erf(z) would have collapsed to 0 here; erfc keeps the value.
    assert normal_sf(10.0) == pytest.approx(7.619853e-24, rel=1e-5)


def test_two_sided_p_is_symmetric_and_bounded() -> None:
    assert two_sided_p(2.5) == two_sided_p(-2.5)
    assert two_sided_p(0.0) == 1.0


# --- two-proportion z -----------------------------------------------------------------


def test_two_proportion_z_hand_computed() -> None:
    # 45/100 vs 30/100: pooled p = .375, var = .375 * .625 * .02 = .0046875,
    # se = .0684653, z = .15 / se = 2.1909.
    result = two_proportion_z(45, 100, 30, 100)
    assert result.z == pytest.approx(2.1909, rel=1e-4)
    assert result.p_value == pytest.approx(0.02847, abs=5e-5)
    assert result.delta_pp == pytest.approx(15.0)


def test_two_proportion_z_is_antisymmetric() -> None:
    forward = two_proportion_z(45, 100, 30, 100)
    reverse = two_proportion_z(30, 100, 45, 100)
    assert reverse.z == pytest.approx(-forward.z)
    assert reverse.p_value == pytest.approx(forward.p_value)
    assert reverse.delta_pp == pytest.approx(-forward.delta_pp)


def test_equal_proportions_are_not_a_finding() -> None:
    result = two_proportion_z(30, 100, 60, 200)
    assert result.z == pytest.approx(0.0)
    assert result.p_value == pytest.approx(1.0)
    assert result.delta_pp == pytest.approx(0.0)


@pytest.mark.parametrize("x", [0, 100])
def test_degenerate_pooled_variance_reports_no_effect(x: int) -> None:
    # Nobody (or everybody) is a success: the proportions cannot differ.
    assert two_proportion_z(x, 100, x, 100) == (0.0, 1.0, 0.0)


def test_larger_samples_make_the_same_gap_more_detectable() -> None:
    small = two_proportion_z(45, 100, 30, 100)
    large = two_proportion_z(450, 1000, 300, 1000)
    assert large.delta_pp == pytest.approx(small.delta_pp)
    assert large.p_value < small.p_value


@pytest.mark.parametrize("args", [(1, 0, 1, 10), (1, 10, 1, 0), (11, 10, 1, 10), (-1, 10, 1, 10)])
def test_two_proportion_z_rejects_incoherent_input(args: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError):
        two_proportion_z(*args)


# --- Mann-Whitney U -------------------------------------------------------------------


def test_complete_separation() -> None:
    # No ties: U1 = 0, U2 = 25, E[U] = 12.5, sigma = sqrt(25 * 11 / 12) = 4.7871355,
    # z = -(12.5 - 0.5) / sigma = -2.50672.
    result = mann_whitney_u([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])
    assert result.u == pytest.approx(0.0)
    assert result.z == pytest.approx(-2.50672, rel=1e-5)
    assert result.p_value == pytest.approx(0.012186, abs=1e-6)
    assert result.rank_biserial == pytest.approx(-1.0)


def test_tie_correction_hand_computed() -> None:
    # [1,1,2] vs [1,2,2]: pooled 1,1,1,2,2,2 -> midranks 2,2,2 and 5,5,5.
    # R1 = 2 + 2 + 5 = 9, U1 = 9 - 6 = 3, E[U] = 4.5.
    # Ties t = [3, 3]: sum(t^3 - t) = 48, so
    # Var = (9/12) * (7 - 48/30) = .75 * 5.4 = 4.05, sigma = 2.0124612,
    # z = -(1.5 - 0.5) / sigma = -0.496904.
    result = mann_whitney_u([1, 1, 2], [1, 2, 2])
    assert result.u == pytest.approx(3.0)
    assert result.z == pytest.approx(-0.496904, rel=1e-5)
    assert result.rank_biserial == pytest.approx((3.0 - 6.0) / 9.0)


def test_ignoring_ties_would_overstate_significance() -> None:
    # The tie term only ever reduces the variance, so a tie-corrected z is larger in
    # magnitude than the naive one. Guard against silently dropping the correction.
    tied = mann_whitney_u([1, 1, 1, 2, 2], [2, 2, 3, 3, 3])
    n1 = n2 = 5
    naive_sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    centered = tied.u - n1 * n2 / 2.0
    naive_z = math.copysign(max(abs(centered) - 0.5, 0.0) / naive_sigma, centered)
    assert abs(tied.z) > abs(naive_z)


def test_all_values_identical_is_not_a_finding() -> None:
    result = mann_whitney_u([4, 4, 4], [4, 4, 4])
    assert result == (4.5, 0.0, 1.0, 0.0)


def test_u_statistics_are_complementary() -> None:
    a, b = [3.0, 1.0, 4.0, 1.0, 5.0], [2.0, 7.0, 1.0, 8.0]
    forward = mann_whitney_u(a, b)
    reverse = mann_whitney_u(b, a)
    assert forward.u + reverse.u == pytest.approx(len(a) * len(b))
    assert forward.rank_biserial == pytest.approx(-reverse.rank_biserial)
    assert forward.p_value == pytest.approx(reverse.p_value)


def test_rank_biserial_is_order_invariant_within_a_sample() -> None:
    assert mann_whitney_u([5, 1, 3], [2, 9]).u == mann_whitney_u([1, 3, 5], [9, 2]).u


@pytest.mark.parametrize("args", [([], [1.0]), ([1.0], [])])
def test_mann_whitney_rejects_empty_samples(args: tuple[list[float], list[float]]) -> None:
    with pytest.raises(ValueError):
        mann_whitney_u(*args)


# --- Poisson rate ratio ---------------------------------------------------------------


def test_rate_ratio_normalizes_by_exposure() -> None:
    # 200 over 10 weeks vs 200 over 20 weeks: rates 20/wk vs 10/wk, ratio 2.
    result = poisson_rate_ratio(200, 10, 200, 20)
    assert result.log_ratio == pytest.approx(math.log(2.0))
    # se = sqrt(1/200 + 1/200) = 0.1, so z = log(2) / 0.1 = 6.9315.
    assert result.z == pytest.approx(math.log(2.0) / 0.1, rel=1e-12)
    assert result.p_value < 1e-10


def test_equal_rates_over_unequal_exposure_are_not_a_finding() -> None:
    result = poisson_rate_ratio(100, 10, 200, 20)
    assert result.log_ratio == pytest.approx(0.0)
    assert result.p_value == pytest.approx(1.0)


def test_rate_ratio_is_antisymmetric() -> None:
    forward = poisson_rate_ratio(300, 12, 200, 16)
    reverse = poisson_rate_ratio(200, 16, 300, 12)
    assert reverse.log_ratio == pytest.approx(-forward.log_ratio)
    assert reverse.p_value == pytest.approx(forward.p_value)


@pytest.mark.parametrize("args", [(0, 10, 5, 10), (5, 10, 0, 10), (5, 0, 5, 10), (5, 10, 5, -1)])
def test_rate_ratio_rejects_incoherent_input(args: tuple[int, float, int, float]) -> None:
    with pytest.raises(ValueError):
        poisson_rate_ratio(*args)


# --- Benjamini-Hochberg ---------------------------------------------------------------

# The worked example from Benjamini & Hochberg (1995) §4, table 1 (m = 15).
BH_1995 = [
    0.0001,
    0.0004,
    0.0019,
    0.0095,
    0.0201,
    0.0278,
    0.0298,
    0.0344,
    0.0459,
    0.3240,
    0.4262,
    0.5719,
    0.6528,
    0.7590,
    1.0000,
]


def test_bh_1995_rejects_four_hypotheses_at_five_percent() -> None:
    # The paper's headline result: BH rejects 4 where Bonferroni rejects 3.
    adjusted = benjamini_hochberg(BH_1995)
    assert sum(1 for q in adjusted if q < 0.05) == 4


def test_bh_1995_adjusted_values() -> None:
    # q(i) = min over j >= i of (15/j) * p(j):
    # q1 = 15 * .0001, q2 = 7.5 * .0004, q3 = 5 * .0019, q4 = 3.75 * .0095.
    adjusted = benjamini_hochberg(BH_1995)
    assert adjusted[:4] == pytest.approx([0.0015, 0.0030, 0.0095, 0.035625])
    assert adjusted[-1] == pytest.approx(1.0)


def test_bh_returns_input_order_not_sorted_order() -> None:
    shuffled = [0.0095, 0.0001, 1.0000, 0.0004, 0.0019]
    adjusted = benjamini_hochberg(shuffled)
    ascending = benjamini_hochberg(sorted(shuffled))
    assert adjusted[1] == pytest.approx(ascending[0])  # .0001 is smallest in both
    assert adjusted[2] == pytest.approx(ascending[-1])  # 1.0 is largest in both


def test_bh_is_monotone_in_the_sorted_p_values() -> None:
    adjusted = benjamini_hochberg(BH_1995)  # input is already ascending
    assert adjusted == sorted(adjusted)


def test_bh_never_shrinks_a_p_value_and_never_exceeds_one() -> None:
    for raw, q in zip(BH_1995, benjamini_hochberg(BH_1995), strict=True):
        assert q >= raw - 1e-12
        assert q <= 1.0


def test_bh_of_a_single_test_is_the_test_itself() -> None:
    assert benjamini_hochberg([0.031]) == pytest.approx([0.031])


def test_bh_of_nothing_is_nothing() -> None:
    assert benjamini_hochberg([]) == []


def test_bh_rejects_values_outside_the_unit_interval() -> None:
    with pytest.raises(ValueError):
        benjamini_hochberg([0.5, 1.5])


def test_a_bigger_family_raises_the_bar() -> None:
    # D-49 choice 7: one family per window. Adding candidates makes each survivor's
    # adjusted p larger — the cost the two-tier evidence marker exists to absorb.
    alone = benjamini_hochberg([0.01])[0]
    crowded = benjamini_hochberg([0.01] + [0.6] * 20)[0]
    assert crowded > alone
