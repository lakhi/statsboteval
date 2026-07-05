import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import OkCell, SuppressedCell, count_cell_adapter, dump_doc, ok, suppressed


def test_ok_cell_parses() -> None:
    cell = count_cell_adapter.validate_python({"status": "ok", "value": 23})
    assert isinstance(cell, OkCell) and cell.value == 23


def test_zero_is_publishable() -> None:
    assert count_cell_adapter.validate_python({"status": "ok", "value": 0}).value == 0


def test_negative_value_rejected() -> None:
    with pytest.raises(ValidationError):
        count_cell_adapter.validate_python({"status": "ok", "value": -1})


def test_ok_without_value_rejected() -> None:
    with pytest.raises(ValidationError):
        count_cell_adapter.validate_python({"status": "ok"})


def test_suppressed_parses_and_has_no_value_attr() -> None:
    cell = count_cell_adapter.validate_python({"status": "suppressed"})
    assert isinstance(cell, SuppressedCell)
    assert not hasattr(cell, "value")  # invariant 2: nothing to leak


def test_suppressed_dumps_status_only() -> None:
    assert dump_doc(suppressed()) == {"status": "suppressed"}


def test_ok_helper_round_trips() -> None:
    assert dump_doc(ok(7)) == {"status": "ok", "value": 7}
