import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from statsboteval_pipeline.contract import (
    OkCell,
    SuppressedCell,
    TrendsSection,
    week_monday,
    weeks_range,
)
from statsboteval_pipeline.aggregate import floored_count
from statsboteval_pipeline.trends import build_trends
from statsboteval_pipeline.windows import build_windows


@given(
    n_students=st.integers(min_value=0, max_value=50),
    extra=st.integers(min_value=0, max_value=1000),
    floor_n=st.integers(min_value=1, max_value=10),
)
def test_floor_property(n_students: int, extra: int, floor_n: int) -> None:
    # Coherent cell: a count of things contributed by k students is >= k (0 students -> 0 things).
    value = 0 if n_students == 0 else n_students + extra
    cell = floored_count(value, n_students, floor_n)
    if 1 <= n_students < floor_n:
        assert isinstance(cell, SuppressedCell)  # contract §11: sub-floor cells never survive
    else:
        assert isinstance(cell, OkCell) and cell.value == value


def test_zero_students_zero_value_publishes_zero() -> None:
    cell = floored_count(0, 0, 3)
    assert isinstance(cell, OkCell) and cell.value == 0


def test_incoherent_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        floored_count(5, 0, 3)  # things without contributing students is a pipeline bug
    with pytest.raises(ValueError):
        floored_count(-1, 1, 3)
    with pytest.raises(ValueError):
        floored_count(0, 0, 0)


# --- the same property for trends findings (T-5) ---------------------------------------
#
# floored_count() cannot cover this section: findings publish derived floats with no
# suppressed state, so the floor is enforced by *dropping* candidates rather than by
# rewriting a cell. That makes the guarantee a property of the whole selection pipeline
# instead of one function, which is what these generate corpora to attack.

AXIS = weeks_range("2025-W20", "2025-W45")  # 2025S + 2025W, so every window pairs


@dataclass(frozen=True)
class _Msg:
    history_id: int
    pseudonym: str
    local: datetime
    week: str
    lang: str


@dataclass(frozen=True)
class _Sess:
    pseudonym: str
    week: str
    n_messages: int
    duration_minutes: float


def _trends_for(rows: list[tuple[int, int, str, int]], floor_n: int) -> TrendsSection:
    msgs: list[_Msg] = []
    sessions: list[_Sess] = []
    for index, (student, week_index, lang, hour) in enumerate(rows):
        week = AXIS[week_index]
        stamp = datetime.combine(week_monday(week) + timedelta(days=index % 7), time(hour))
        pseudonym = f"stu{student:02d}"
        msgs.append(_Msg(index + 1, pseudonym, stamp, week, lang))
        sessions.append(_Sess(pseudonym, week, 1 + index % 5, 1.0 + index % 30))

    return build_trends(
        msgs=msgs,
        sessions=sessions,
        registrations=[(m.pseudonym, m.week) for m in msgs[::3]],
        windows=build_windows(AXIS),
        axis=AXIS,
        floor_n=floor_n,
        # Half the messages carry a topic, assigned by a stride so membership spreads
        # across students instead of concentrating on the first one (which the floor
        # would mask, hiding the very candidates this is meant to attack).
        positives={"method_theme": {"Regression": {m.history_id for m in msgs[::2]}}},
        deductive_labels={"statistics_interaction": "Statistics Interaction"},
    )


def _assert_no_sub_floor(section: TrendsSection, floor_n: int) -> int:
    published = 0
    for window_id, entry in section.per_window.items():
        for finding in entry.findings:
            published += 1
            where = f"{window_id}/{finding.id}"
            assert finding.current.n_students >= floor_n, where
            assert finding.baseline.n_students >= floor_n, where
            for point in finding.trajectory or ():
                assert point.n_students >= floor_n, f"{where}@{point.window_id}"
        # A window with no baseline can carry neither findings nor the "we looked and
        # nothing was testable" flag — there was nothing to look at.
        if entry.baseline is None:
            assert not entry.findings and not entry.insufficient_data, window_id
    return published


# Cohorts stay small and straddle the floor: the interesting corpora are the ones where a
# measure is carried by two or three students, not the comfortable ones.
_rows = st.tuples(
    st.integers(min_value=0, max_value=9),  # student
    st.integers(min_value=0, max_value=len(AXIS) - 1),  # week
    st.sampled_from(("de", "en", "other")),
    st.integers(min_value=0, max_value=23),  # hour, feeding the daypart candidates
)


@settings(max_examples=200, deadline=None)
@given(
    rows=st.lists(_rows, min_size=0, max_size=400),
    floor_n=st.integers(min_value=1, max_value=5),
)
def test_no_generated_corpus_publishes_a_sub_floor_finding(rows: list[tuple[int, int, str, int]], floor_n: int) -> None:
    _assert_no_sub_floor(_trends_for(rows, floor_n), floor_n)


def test_the_sub_floor_property_is_not_vacuous() -> None:
    """The same property over corpora large enough to actually publish.

    Hypothesis shrinks toward small inputs, and small corpora fail `min_n` long before the
    floor is consulted — so the test above can pass by never reaching a published finding.
    This one is deterministic and asserts the coverage explicitly: a change that silently
    stopped Trends from publishing anything would turn the property green and this red.
    """
    rng = random.Random(20260730)
    published = 0
    for _ in range(100):
        rows = [
            (rng.randint(0, 9), rng.randint(0, len(AXIS) - 1), rng.choice(["de", "en", "other"]), rng.randint(0, 23))
            for _ in range(rng.randint(0, 400))
        ]
        floor_n = rng.randint(1, 5)
        published += _assert_no_sub_floor(_trends_for(rows, floor_n), floor_n)
    assert published >= 25, f"only {published} findings published across 100 corpora — property is barely exercised"
