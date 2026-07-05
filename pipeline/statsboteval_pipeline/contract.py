"""Aggregates-file contract v1 — single source of truth for shapes.

Semantics are normative in docs/aggregates-contract.md; these models are the
law for shapes (contract §1). Exported to schema/aggregates.schema.json by
statsboteval_pipeline.export_schema.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

SCHEMA_VERSION = "1.0.0"

FootnoteId = str


class OkCell(BaseModel):
    status: Literal["ok"]
    value: int = Field(ge=0)


class SuppressedCell(BaseModel):
    # No value field exists: a sub-floor number is structurally unrepresentable (invariant 2).
    status: Literal["suppressed"]


CountCell = Annotated[Union[OkCell, SuppressedCell], Field(discriminator="status")]
count_cell_adapter: TypeAdapter[OkCell | SuppressedCell] = TypeAdapter(CountCell)


def ok(value: int) -> OkCell:
    return OkCell(status="ok", value=value)


def suppressed() -> SuppressedCell:
    return SuppressedCell(status="suppressed")


def dump_doc(model: BaseModel) -> dict[str, Any]:
    """Canonical serialization: JSON types, aliases, absent (not null) optionals."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


WeekId = Annotated[str, Field(pattern=r"^\d{4}-W\d{2}$")]


def parse_week(week: str) -> tuple[int, int]:
    year, w = week.split("-W")
    return int(year), int(w)


def week_monday(week: str) -> date:
    year, w = parse_week(week)
    return date.fromisocalendar(year, w, 1)


def week_sunday(week: str) -> date:
    year, w = parse_week(week)
    return date.fromisocalendar(year, w, 7)


def date_to_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def weeks_range(first: str, through: str) -> list[str]:
    """Dense, inclusive list of ISO week ids — the weekly-series axis (contract §5)."""
    cursor, end = week_monday(first), week_monday(through)
    if cursor > end:
        raise ValueError(f"first week {first} is after {through}")
    out: list[str] = []
    while cursor <= end:
        out.append(date_to_week(cursor))
        cursor += timedelta(days=7)
    return out


class WeeklyEntry(BaseModel):
    week: WeekId
    cell: CountCell


class WeeklySeries(BaseModel):
    series: list[WeeklyEntry]
    footnote_ids: list[FootnoteId] | None = None
