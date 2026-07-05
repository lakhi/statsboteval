import pytest
from hypothesis import given
from hypothesis import strategies as st

from statsboteval_pipeline.contract import OkCell, SuppressedCell
from statsboteval_pipeline.aggregate import floored_count


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
