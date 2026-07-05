from datetime import date

import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    WeeklyEntry,
    WeeklySeries,
    date_to_week,
    ok,
    week_sunday,
    weeks_range,
)


def test_week_id_format_enforced() -> None:
    with pytest.raises(ValidationError):
        WeeklyEntry.model_validate({"week": "2025-11", "cell": {"status": "ok", "value": 1}})


def test_week_sunday() -> None:
    assert week_sunday("2026-W27") == date(2026, 7, 5)


def test_date_to_week_january_edge() -> None:
    # 2026-01-01 falls in ISO week 2026-W01; 2027-01-01 falls in 2026-W53.
    assert date_to_week(date(2026, 1, 1)) == "2026-W01"
    assert date_to_week(date(2027, 1, 1)) == "2026-W53"


def test_weeks_range_crosses_year_boundary() -> None:
    assert weeks_range("2025-W52", "2026-W02") == ["2025-W52", "2026-W01", "2026-W02"]


def test_weeks_range_rejects_reversed() -> None:
    with pytest.raises(ValueError):
        weeks_range("2026-W02", "2025-W52")


def test_weekly_series_shape() -> None:
    s = WeeklySeries(series=[WeeklyEntry(week="2025-W11", cell=ok(3))])
    from statsboteval_pipeline.contract import dump_doc

    assert dump_doc(s) == {"series": [{"week": "2025-W11", "cell": {"status": "ok", "value": 3}}]}
