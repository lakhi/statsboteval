"""Aggregates-file contract v1 — single source of truth for shapes.

Semantics are normative in docs/aggregates-contract.md; these models are the
law for shapes (contract §1). Exported to schema/aggregates.schema.json by
statsboteval_pipeline.export_schema.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, model_serializer, model_validator

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


class HistogramBin(BaseModel):
    lo: int
    hi: int | None  # None = open top bin ("8+")
    cell: CountCell

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        # dump_doc uses exclude_none, which would drop hi=None — but null IS the
        # open-bin marker (contract §5), so reinstate it unconditionally.
        data = handler(self)
        data["hi"] = self.hi
        return data


class OkSummaryStats(BaseModel):
    status: Literal["ok"]
    n_students: int = Field(ge=1)
    median: float
    p25: float
    p75: float
    mean: float | None = None  # filled where the Bergmann reference reports them
    sd: float | None = None


class SuppressedSummaryStats(BaseModel):
    status: Literal["suppressed"]


SummaryStats = Annotated[Union[OkSummaryStats, SuppressedSummaryStats], Field(discriminator="status")]


class Histogram(BaseModel):
    unit: str
    bins: list[HistogramBin]
    n_total: CountCell  # published explicitly: suppressed bins make it un-derivable
    summary: SummaryStats | None = None
    footnote_ids: list[FootnoteId] | None = None

    @model_validator(mode="after")
    def _bins_ascending_disjoint(self) -> "Histogram":
        for i, b in enumerate(self.bins):
            if b.hi is None and i != len(self.bins) - 1:
                raise ValueError("only the last bin may be open-ended (hi=null)")
            if b.hi is not None and b.hi < b.lo:
                raise ValueError(f"bin {i}: hi < lo")
            if i > 0:
                prev = self.bins[i - 1]
                if prev.hi is None or b.lo <= prev.hi:
                    raise ValueError(f"bin {i}: bins must be ascending and non-overlapping")
        return self


class HeatmapCell(BaseModel):
    dow: int = Field(ge=1, le=7)  # ISO: Monday = 1
    hour: int = Field(ge=0, le=23)  # local time per metadata.timezone
    cell: CountCell


class HeatmapGrid(BaseModel):
    cells: list[HeatmapCell]
    footnote_ids: list[FootnoteId] | None = None

    @model_validator(mode="after")
    def _dense_168(self) -> "HeatmapGrid":
        seen = {(c.dow, c.hour) for c in self.cells}
        if len(self.cells) != 168 or len(seen) != 168:
            raise ValueError("heatmap must contain exactly the 168 unique (dow, hour) cells")
        return self
