# Aggregates-Contract Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deliverable 2 of the D-19 contract gate: pydantic v2 models in `pipeline/` as the single source of truth for the aggregates-file shapes, exported as `schema/aggregates.schema.json`, with drift-check and round-trip validation tests.

**Architecture:** One module (`pipeline/statsboteval_pipeline/contract.py`) defines every shape in `docs/aggregates-contract.md` §3–§7 as pydantic models with discriminated unions for the tri-state cells; a small export script writes the JSON Schema artifact; pytest enforces (a) model semantics, (b) committed-schema-matches-models (drift guard), (c) round-trip equality on a full synthetic example. **No aggregation, publish, API, or dashboard code** — those are later plans.

**Tech Stack:** Python ≥3.11, pydantic ≥2.7, pytest, jsonschema (dev, to prove the exported artifact accepts real documents), ruff + mypy configured as in the health-research-agent-api reference.

## Global Constraints

- Normative spec: `docs/aggregates-contract.md` (v1, locked 2026-07-05). Field names, formats, and semantics below are copied from it — do not improvise.
- All JSON keys snake_case; week ids match `^\d{4}-W\d{2}$` (`"2025-W11"`); dates `YYYY-MM-DD`; timestamps RFC 3339 UTC.
- Suppressed cells carry **no** `value` field at all (contract invariant 2) — model this as two classes in a discriminated union, never as `value: int | None`.
- The exported JSON Schema must stay permissive to unknown fields (contract invariant 5: readers ignore unknown fields) — therefore **no** `extra="forbid"` on models; writer-side extras detection is the round-trip-equality test instead.
- Canonical serialization: `model_dump(mode="json", by_alias=True, exclude_none=True)` via the `dump_doc()` helper — absent optionals are *absent*, not `null`. Exception: `HistogramBin.hi` must serialize `null` for the open top bin (contract §5).
- Tooling per reference repo: setuptools build backend, ruff `line-length = 120`, mypy with `plugins = ["pydantic.mypy"]`, dev extras.
- Work from `pipeline/` for all Python commands (venv lives there); `schema/` is at the repo root.
- Commit after every task; messages in the repo's plain imperative style (no `feat:` prefixes).

---

### Task 1: Package scaffold

**Files:**
- Create: `pipeline/pyproject.toml`
- Create: `pipeline/statsboteval_pipeline/__init__.py`
- Create: `pipeline/tests/test_scaffold.py`

**Interfaces:**
- Consumes: nothing.
- Produces: installable package `statsboteval_pipeline`; dev env with pytest/ruff/mypy for all later tasks.

- [ ] **Step 1: Write `pipeline/pyproject.toml`**

```toml
[project]
name = "statsboteval-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
authors = [{ name = "Akshay Lakhi", email = "akshay.lakhi@univie.ac.at" }]
dependencies = ["pydantic>=2.7"]

[project.optional-dependencies]
dev = ["mypy", "ruff", "pytest", "jsonschema>=4.21"]

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["statsboteval_pipeline*"]

[tool.ruff]
line-length = 120
exclude = [".venv*"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401", "F403"]

[tool.mypy]
check_untyped_defs = true
no_implicit_optional = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]
exclude = [".venv*"]
```

- [ ] **Step 2: Create the package and a sanity test**

`pipeline/statsboteval_pipeline/__init__.py`:

```python
"""StatsBotEval weekly pipeline. Contract models: statsboteval_pipeline.contract."""
```

`pipeline/tests/test_scaffold.py`:

```python
def test_package_imports() -> None:
    import statsboteval_pipeline  # noqa: F401
```

- [ ] **Step 3: Create the env and verify**

Run:
```bash
cd pipeline && uv venv && uv pip install -e ".[dev]" && .venv/bin/pytest tests/ -v
```
Expected: `1 passed`.

- [ ] **Step 4: Ensure the venv is git-ignored**

Check `.gitignore` at repo root covers `pipeline/.venv/` (add a `.venv/` line if not already covered). Never weaken existing data exclusions.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pyproject.toml pipeline/statsboteval_pipeline/__init__.py pipeline/tests/test_scaffold.py .gitignore
git commit -m "Scaffold pipeline package (pydantic, pytest, ruff/mypy per reference pattern)"
```

---

### Task 2: Cell primitives and canonical serialization

**Files:**
- Create: `pipeline/statsboteval_pipeline/contract.py`
- Create: `pipeline/tests/test_contract_cells.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by every later task): `OkCell`, `SuppressedCell`, `CountCell` (discriminated union type alias), `count_cell_adapter: TypeAdapter`, helpers `ok(value: int) -> OkCell`, `suppressed() -> SuppressedCell`, `dump_doc(model: BaseModel) -> dict[str, Any]`, constant `SCHEMA_VERSION = "1.0.0"`.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_cells.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_cells.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` for `statsboteval_pipeline.contract`.

- [ ] **Step 3: Write `pipeline/statsboteval_pipeline/contract.py`**

```python
"""Aggregates-file contract v1 — single source of truth for shapes.

Semantics are normative in docs/aggregates-contract.md; these models are the
law for shapes (contract §1). Exported to schema/aggregates.schema.json by
statsboteval_pipeline.export_schema.
"""

from __future__ import annotations

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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_cells.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_cells.py
git commit -m "Add contract cell primitives: ok/suppressed discriminated union"
```

---

### Task 3: Week helpers and WeeklySeries

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_weeks.py`

**Interfaces:**
- Consumes: `CountCell`, `FootnoteId` (Task 2).
- Produces: `WeekId` (annotated str type), `parse_week(week: str) -> tuple[int, int]`, `week_monday(week: str) -> date`, `week_sunday(week: str) -> date`, `date_to_week(d: date) -> str`, `weeks_range(first: str, through: str) -> list[str]`, `WeeklyEntry(week, cell)`, `WeeklySeries(series, footnote_ids?)`.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_weeks.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_weeks.py -v`
Expected: FAIL — ImportError (`week_sunday` etc. not defined).

- [ ] **Step 3: Append to `contract.py`** (add `from datetime import date, timedelta` to the imports):

```python
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
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass (scaffold + cells + weeks).

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_weeks.py
git commit -m "Add ISO-week helpers and dense WeeklySeries model"
```

---

### Task 4: Histogram and SummaryStats

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_histogram.py`

**Interfaces:**
- Consumes: `CountCell`, `FootnoteId`, `ok`, `suppressed`, `dump_doc`.
- Produces: `HistogramBin(lo, hi, cell)`, `OkSummaryStats`, `SuppressedSummaryStats`, `SummaryStats` (union), `Histogram(unit, bins, n_total, summary?, footnote_ids?)`.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_histogram.py`:

```python
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import Histogram, HistogramBin, dump_doc, ok, suppressed


def make_hist(**overrides):
    base = dict(
        unit="sessions",
        bins=[
            HistogramBin(lo=1, hi=1, cell=ok(214)),
            HistogramBin(lo=2, hi=3, cell=ok(96)),
            HistogramBin(lo=4, hi=7, cell=suppressed()),
            HistogramBin(lo=8, hi=None, cell=ok(11)),
        ],
        n_total=ok(327),
    )
    base.update(overrides)
    return Histogram(**base)


def test_valid_histogram_parses() -> None:
    assert len(make_hist().bins) == 4


def test_open_bin_only_last() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=1, hi=None, cell=ok(1)), HistogramBin(lo=2, hi=3, cell=ok(1))])


def test_overlapping_bins_rejected() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=1, hi=3, cell=ok(1)), HistogramBin(lo=3, hi=5, cell=ok(1))])


def test_hi_below_lo_rejected() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=5, hi=2, cell=ok(1))])


def test_open_bin_serializes_hi_null() -> None:
    # exclude_none must NOT drop hi: null is the open-top-bin marker (contract §5).
    dumped = dump_doc(make_hist())
    assert dumped["bins"][-1]["hi"] is None


def test_summary_all_or_nothing() -> None:
    h = make_hist(summary={"status": "ok", "n_students": 74, "median": 2.0, "p25": 1.0, "p75": 4.0})
    dumped = dump_doc(h)
    assert dumped["summary"]["n_students"] == 74
    assert "mean" not in dumped["summary"]  # absent optionals are absent, not null
    h2 = make_hist(summary={"status": "suppressed"})
    assert dump_doc(h2)["summary"] == {"status": "suppressed"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_histogram.py -v`
Expected: FAIL — ImportError (`Histogram` not defined).

- [ ] **Step 3: Append to `contract.py`** (add `model_serializer`, `model_validator` to the pydantic import):

```python
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
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_histogram.py
git commit -m "Add Histogram (bins-in-data, explicit n_total) and all-or-nothing SummaryStats"
```

---

### Task 5: HeatmapGrid

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_heatmap.py`

**Interfaces:**
- Consumes: `CountCell`, `ok`, `suppressed`.
- Produces: `HeatmapCell(dow, hour, cell)`, `HeatmapGrid(cells, footnote_ids?)` — validated dense 168.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_heatmap.py`:

```python
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import HeatmapCell, HeatmapGrid, ok


def full_cells() -> list[HeatmapCell]:
    return [HeatmapCell(dow=d, hour=h, cell=ok((d * h) % 5)) for d in range(1, 8) for h in range(24)]


def test_dense_grid_parses() -> None:
    assert len(HeatmapGrid(cells=full_cells()).cells) == 168


def test_missing_cell_rejected() -> None:
    with pytest.raises(ValidationError):
        HeatmapGrid(cells=full_cells()[:-1])


def test_duplicate_cell_rejected() -> None:
    cells = full_cells()[:-1] + [HeatmapCell(dow=1, hour=0, cell=ok(1))]
    with pytest.raises(ValidationError):
        HeatmapGrid(cells=cells)


def test_dow_hour_bounds() -> None:
    with pytest.raises(ValidationError):
        HeatmapCell(dow=0, hour=0, cell=ok(1))
    with pytest.raises(ValidationError):
        HeatmapCell(dow=1, hour=24, cell=ok(1))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_heatmap.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Append to `contract.py`**:

```python
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
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_heatmap.py
git commit -m "Add dense 168-cell HeatmapGrid"
```

---

### Task 6: Windows registry models

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_windows.py`

**Interfaces:**
- Consumes: `WeekId`, `week_monday`.
- Produces: `Coverage(from_ [alias "from"], through)`, `AllTimeWindow`, `SemesterWindow`, `TrailingWindow`, `Window` (discriminated union on `kind`), `window_adapter: TypeAdapter`.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_windows.py`:

```python
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import Coverage, SemesterWindow, dump_doc, window_adapter


def test_coverage_uses_from_alias() -> None:
    cov = Coverage.model_validate({"from": "2025-W11", "through": "2025-W14"})
    assert cov.from_ == "2025-W11"
    assert dump_doc(cov) == {"from": "2025-W11", "through": "2025-W14"}


def test_coverage_rejects_reversed() -> None:
    with pytest.raises(ValidationError):
        Coverage.model_validate({"from": "2025-W14", "through": "2025-W11"})


def test_window_union_discriminates_on_kind() -> None:
    w = window_adapter.validate_python(
        {"id": "all_time", "kind": "all_time", "label": "All time", "coverage": {"from": "2025-W11", "through": "2025-W14"}}
    )
    assert w.kind == "all_time"
    assert not hasattr(w, "weeks")  # all_time carries no membership list (contract §6.1)


def test_semester_window_requires_dates_and_weeks() -> None:
    with pytest.raises(ValidationError):
        window_adapter.validate_python(
            {"id": "2025S", "kind": "semester", "label": "Summer semester 2025", "coverage": {"from": "2025-W11", "through": "2025-W14"}}
        )


def test_semester_window_round_trip() -> None:
    w = SemesterWindow(
        kind="semester",
        id="2025S",
        label="Summer semester 2025",
        start_date="2025-03-01",
        end_date="2025-06-30",
        weeks=["2025-W10", "2025-W11"],
        coverage={"from": "2025-W11", "through": "2025-W11"},
    )
    dumped = dump_doc(w)
    assert dumped["start_date"] == "2025-03-01"
    assert dumped["coverage"]["from"] == "2025-W11"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_windows.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Append to `contract.py`** (add `ConfigDict` to the pydantic import):

```python
class Coverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: WeekId = Field(alias="from")  # "from" is a Python keyword
    through: WeekId

    @model_validator(mode="after")
    def _ordered(self) -> "Coverage":
        if week_monday(self.from_) > week_monday(self.through):
            raise ValueError("coverage.from must not be after coverage.through")
        return self


class AllTimeWindow(BaseModel):
    kind: Literal["all_time"]
    id: str
    label: str
    coverage: Coverage


class SemesterWindow(BaseModel):
    kind: Literal["semester"]
    id: str
    label: str
    start_date: date
    end_date: date
    weeks: list[WeekId]  # full membership (Thursday rule); coverage = clipped to data range
    coverage: Coverage


class TrailingWindow(BaseModel):
    kind: Literal["trailing"]
    id: str
    label: str
    weeks: list[WeekId]
    coverage: Coverage


Window = Annotated[Union[AllTimeWindow, SemesterWindow, TrailingWindow], Field(discriminator="kind")]
window_adapter: TypeAdapter[AllTimeWindow | SemesterWindow | TrailingWindow] = TypeAdapter(Window)
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_windows.py
git commit -m "Add window registry models (all_time/semester/trailing, from-alias coverage)"
```

---

### Task 7: The five Phase A section models

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_sections.py`

**Interfaces:**
- Consumes: `WeeklySeries`, `Histogram`, `HeatmapGrid`, `CountCell`, `FootnoteId`.
- Produces: `TemporalUsage`, `UsageContext`, `SessionsSection`, `TokensSection`, `LanguageSection`, `Sections` (all five optional), plus their inner models exactly as named in the code below — Task 8 and 9 construct these.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_sections.py`:

```python
from statsboteval_pipeline.contract import (
    LanguageSection,
    LanguageTotals,
    LanguageWeekly,
    LanguageWindow,
    MessagesByLanguage,
    Sections,
    WeeklyEntry,
    WeeklySeries,
    dump_doc,
    ok,
)


def one_series() -> WeeklySeries:
    return WeeklySeries(series=[WeeklyEntry(week="2025-W11", cell=ok(3))])


def test_sections_all_optional() -> None:
    assert dump_doc(Sections()) == {}


def test_language_section_shape() -> None:
    lang = LanguageSection(
        weekly=LanguageWeekly(
            messages_by_language=MessagesByLanguage(
                de=one_series(), en=one_series(), other=one_series(), undetermined=one_series(),
                footnote_ids=["language_heuristic"],
            )
        ),
        per_window={"all_time": LanguageWindow(totals=LanguageTotals(de=ok(9), en=ok(4), other=ok(0), undetermined=ok(0)))},
    )
    dumped = dump_doc(lang)
    assert set(dumped["weekly"]["messages_by_language"].keys()) == {"de", "en", "other", "undetermined", "footnote_ids"}
    assert dumped["per_window"]["all_time"]["totals"]["other"] == {"status": "ok", "value": 0}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_sections.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Append to `contract.py`**:

```python
# --- sections (contract §7): one model tree per dashboard view ---


class TemporalUsageWeekly(BaseModel):
    messages: WeeklySeries
    sessions: WeeklySeries
    active_students: WeeklySeries


class TemporalUsageWindow(BaseModel):
    activity_heatmap: HeatmapGrid


class TemporalUsage(BaseModel):
    weekly: TemporalUsageWeekly
    per_window: dict[str, TemporalUsageWindow]


class UsageContextTotals(BaseModel):
    active_students: CountCell
    messages: CountCell
    sessions: CountCell
    new_registrations: CountCell


class UserClasses(BaseModel):
    one_time: CountCell
    monthly: CountCell
    sporadic: CountCell
    footnote_ids: list[FootnoteId] | None = None


class UsageContextWindow(BaseModel):
    totals: UsageContextTotals
    user_classes: UserClasses


class UsageContextWeekly(BaseModel):
    registrations: WeeklySeries


class UsageContext(BaseModel):
    weekly: UsageContextWeekly
    per_window: dict[str, UsageContextWindow]


class SessionsWindow(BaseModel):
    messages_per_session: Histogram
    session_duration_minutes: Histogram


class SessionsSection(BaseModel):
    per_window: dict[str, SessionsWindow]


class TokensWindow(BaseModel):
    completion_tokens_per_message: Histogram


class TokensSection(BaseModel):
    per_window: dict[str, TokensWindow]


class MessagesByLanguage(BaseModel):
    de: WeeklySeries
    en: WeeklySeries
    other: WeeklySeries
    undetermined: WeeklySeries
    footnote_ids: list[FootnoteId] | None = None


class LanguageWeekly(BaseModel):
    messages_by_language: MessagesByLanguage


class LanguageTotals(BaseModel):
    de: CountCell
    en: CountCell
    other: CountCell
    undetermined: CountCell


class LanguageWindow(BaseModel):
    totals: LanguageTotals


class LanguageSection(BaseModel):
    weekly: LanguageWeekly
    per_window: dict[str, LanguageWindow]


class Sections(BaseModel):
    # Every section optional: readers tolerate absence (invariant 5); Phase B adds "topics".
    temporal_usage: TemporalUsage | None = None
    usage_context: UsageContext | None = None
    sessions: SessionsSection | None = None
    tokens: TokensSection | None = None
    language: LanguageSection | None = None
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_sections.py
git commit -m "Add the five Phase A section models"
```

---

### Task 8: Root Aggregates model with cross-document validators

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (append)
- Create: `pipeline/tests/test_contract_root.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `Footnote(text)`, `Aggregates` (the root model) — validating: `data_through_date` = Sunday of `data_through_week`; unique window ids; every `per_window` key exists in the registry; every referenced footnote id exists; every weekly series dense over `[first_week, data_through_week]`.

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_contract_root.py`:

```python
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import (
    Aggregates,
    AllTimeWindow,
    Footnote,
    Sections,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    HeatmapCell,
    HeatmapGrid,
    WeeklyEntry,
    WeeklySeries,
    ok,
)

WEEKS = ["2025-W11", "2025-W12"]


def series(footnote_ids: list[str] | None = None) -> WeeklySeries:
    return WeeklySeries(series=[WeeklyEntry(week=w, cell=ok(3)) for w in WEEKS], footnote_ids=footnote_ids)


def grid() -> HeatmapGrid:
    return HeatmapGrid(cells=[HeatmapCell(dow=d, hour=h, cell=ok(0)) for d in range(1, 8) for h in range(24)])


def minimal_doc(**overrides) -> dict:
    base = dict(
        schema_version="1.0.0",
        generated_at=datetime(2025, 3, 24, 5, 0, tzinfo=timezone.utc),
        data_through_week="2025-W12",
        data_through_date=date(2025, 3, 23),
        first_week="2025-W11",
        privacy_floor_n=3,
        label_versions={"language": "lang-heuristic-v1"},
        timezone="Europe/Vienna",
        data_provenance="synthetic",
        pipeline_version="0.1.0",
        windows=[
            AllTimeWindow(
                kind="all_time", id="all_time", label="All time",
                coverage={"from": "2025-W11", "through": "2025-W12"},
            )
        ],
        footnotes={"chat_fragmentation": Footnote(text="Credit UI nudges new chats.")},
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=series(),
                    sessions=series(footnote_ids=["chat_fragmentation"]),
                    active_students=series(),
                ),
                per_window={"all_time": TemporalUsageWindow(activity_heatmap=grid())},
            )
        ),
    )
    base.update(overrides)
    return base


def test_valid_document_parses() -> None:
    agg = Aggregates(**minimal_doc())
    assert agg.privacy_floor_n == 3


def test_data_through_date_must_be_sunday_of_week() -> None:
    with pytest.raises(ValidationError, match="Sunday"):
        Aggregates(**minimal_doc(data_through_date=date(2025, 3, 22)))


def test_unknown_window_key_rejected() -> None:
    doc = minimal_doc()
    doc["sections"].temporal_usage.per_window["2099S"] = TemporalUsageWindow(activity_heatmap=grid())
    with pytest.raises(ValidationError, match="unknown window"):
        Aggregates(**doc)


def test_unknown_footnote_id_rejected() -> None:
    doc = minimal_doc(footnotes={})
    with pytest.raises(ValidationError, match="unknown footnote"):
        Aggregates(**doc)


def test_sparse_weekly_series_rejected() -> None:
    sparse = WeeklySeries(series=[WeeklyEntry(week="2025-W11", cell=ok(3))])
    doc = minimal_doc()
    doc["sections"].temporal_usage.weekly.messages = sparse
    with pytest.raises(ValidationError, match="dense"):
        Aggregates(**doc)


def test_naive_generated_at_rejected() -> None:
    with pytest.raises(ValidationError):
        Aggregates(**minimal_doc(generated_at=datetime(2025, 3, 24, 5, 0)))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_contract_root.py -v`
Expected: FAIL — ImportError (`Aggregates`, `Footnote` not defined).

- [ ] **Step 3: Append to `contract.py`** (add `AwareDatetime` to the pydantic import and `from collections.abc import Iterator` to the stdlib imports):

```python
class Footnote(BaseModel):
    text: str


def _iter_footnote_ids(node: Any) -> Iterator[str]:
    """Walk a dumped document and yield every footnote id referenced anywhere."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "footnote_ids" and isinstance(value, list):
                yield from value
            else:
                yield from _iter_footnote_ids(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_footnote_ids(item)


class Aggregates(BaseModel):
    """Root of the aggregates file. Shape law lives here; semantics in docs/aggregates-contract.md."""

    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    generated_at: AwareDatetime
    data_through_week: WeekId
    data_through_date: date
    first_week: WeekId
    privacy_floor_n: int = Field(ge=1)
    label_versions: dict[str, str]
    timezone: str
    data_provenance: Literal["synthetic", "production"]
    pipeline_version: str
    windows: list[Window]
    footnotes: dict[FootnoteId, Footnote]
    sections: Sections

    def _weekly_series(self) -> Iterator[tuple[str, WeeklySeries]]:
        s = self.sections
        if s.temporal_usage is not None:
            yield "temporal_usage.weekly.messages", s.temporal_usage.weekly.messages
            yield "temporal_usage.weekly.sessions", s.temporal_usage.weekly.sessions
            yield "temporal_usage.weekly.active_students", s.temporal_usage.weekly.active_students
        if s.usage_context is not None:
            yield "usage_context.weekly.registrations", s.usage_context.weekly.registrations
        if s.language is not None:
            mbl = s.language.weekly.messages_by_language
            for lang in ("de", "en", "other", "undetermined"):
                yield f"language.weekly.messages_by_language.{lang}", getattr(mbl, lang)

    def _per_window_maps(self) -> Iterator[tuple[str, dict[str, Any]]]:
        s = self.sections
        for name in ("temporal_usage", "usage_context", "sessions", "tokens", "language"):
            section = getattr(s, name)
            if section is not None:
                yield name, section.per_window

    @model_validator(mode="after")
    def _cross_document_consistency(self) -> "Aggregates":
        if week_sunday(self.data_through_week) != self.data_through_date:
            raise ValueError("data_through_date must be the Sunday of data_through_week")
        window_ids = {w.id for w in self.windows}
        if len(window_ids) != len(self.windows):
            raise ValueError("window ids must be unique")
        for name, per_window in self._per_window_maps():
            unknown = set(per_window) - window_ids
            if unknown:
                raise ValueError(f"sections.{name}.per_window references unknown windows: {sorted(unknown)}")
        referenced = set(_iter_footnote_ids(dump_doc(self.sections)))
        unknown_footnotes = referenced - set(self.footnotes)
        if unknown_footnotes:
            raise ValueError(f"unknown footnote ids referenced: {sorted(unknown_footnotes)}")
        expected = weeks_range(self.first_week, self.data_through_week)
        for path, weekly in self._weekly_series():
            if [entry.week for entry in weekly.series] != expected:
                raise ValueError(f"sections.{path} must be dense over [{self.first_week}, {self.data_through_week}]")
        return self
```

- [ ] **Step 4: Run all tests to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/statsboteval_pipeline/contract.py pipeline/tests/test_contract_root.py
git commit -m "Add root Aggregates model with cross-document validators"
```

---

### Task 9: Full synthetic example and round-trip guarantee

**Files:**
- Create: `pipeline/tests/factories.py`
- Create: `pipeline/tests/test_round_trip.py`

**Interfaces:**
- Consumes: everything from `contract.py`.
- Produces: `make_synthetic_aggregates() -> Aggregates` — a complete, valid, clearly-synthetic document exercising all five sections; used again by Task 10's schema-conformance test.

- [ ] **Step 1: Write the factory** — `pipeline/tests/factories.py`:

```python
"""SYNTHETIC fixture factory — no real student data, ever (repo policy)."""

from datetime import date, datetime, timezone

from statsboteval_pipeline.contract import (
    Aggregates,
    AllTimeWindow,
    Footnote,
    HeatmapCell,
    HeatmapGrid,
    Histogram,
    HistogramBin,
    LanguageSection,
    LanguageTotals,
    LanguageWeekly,
    LanguageWindow,
    MessagesByLanguage,
    SCHEMA_VERSION,
    Sections,
    SemesterWindow,
    SessionsSection,
    SessionsWindow,
    TemporalUsage,
    TemporalUsageWeekly,
    TemporalUsageWindow,
    TokensSection,
    TokensWindow,
    TrailingWindow,
    UsageContext,
    UsageContextTotals,
    UsageContextWeekly,
    UsageContextWindow,
    UserClasses,
    WeeklyEntry,
    WeeklySeries,
    ok,
    suppressed,
    weeks_range,
)

WEEKS = ["2025-W11", "2025-W12", "2025-W13", "2025-W14"]
WINDOW_IDS = ("all_time", "2025S", "trailing_4")

FOOTNOTES = {
    "chat_fragmentation": Footnote(text="The credit-limit UI nudges students toward starting new chats."),
    "bachelor_onboarding": Footnote(text="Bachelor students had access only from 16 May 2025."),
    "language_heuristic": Footnote(text="Language detected locally by a statistical heuristic (lang-heuristic-v1)."),
    "user_class_definitions": Footnote(text="One-time/monthly/sporadic per the Bergmann Stage-2 definitions."),
    "duration_definition": Footnote(text="Duration = last minus first server timestamp; single-message sessions = 0."),
}


def series(values: list[int | None], footnote_ids: list[str] | None = None) -> WeeklySeries:
    entries = [
        WeeklyEntry(week=w, cell=suppressed() if v is None else ok(v)) for w, v in zip(WEEKS, values, strict=True)
    ]
    return WeeklySeries(series=entries, footnote_ids=footnote_ids)


def grid() -> HeatmapGrid:
    cells = [
        HeatmapCell(dow=d, hour=h, cell=suppressed() if (d == 7 and h < 6) else ok((d * h) % 9))
        for d in range(1, 8)
        for h in range(24)
    ]
    return HeatmapGrid(cells=cells)


def histogram(unit: str, footnote_ids: list[str] | None = None) -> Histogram:
    return Histogram(
        unit=unit,
        bins=[
            HistogramBin(lo=1, hi=1, cell=ok(214)),
            HistogramBin(lo=2, hi=3, cell=ok(96)),
            HistogramBin(lo=4, hi=7, cell=suppressed()),
            HistogramBin(lo=8, hi=None, cell=ok(11)),
        ],
        n_total=ok(327),
        summary={"status": "ok", "n_students": 74, "median": 2.0, "p25": 1.0, "p75": 4.0, "mean": 2.4, "sd": 2.1},
        footnote_ids=footnote_ids,
    )


def window_totals() -> UsageContextTotals:
    return UsageContextTotals(active_students=ok(58), messages=ok(412), sessions=ok(163), new_registrations=ok(21))


def make_synthetic_aggregates() -> Aggregates:
    per_window_temporal = {wid: TemporalUsageWindow(activity_heatmap=grid()) for wid in WINDOW_IDS}
    per_window_usage = {
        wid: UsageContextWindow(
            totals=window_totals(),
            user_classes=UserClasses(
                one_time=ok(31), monthly=ok(6), sporadic=ok(21), footnote_ids=["user_class_definitions"]
            ),
        )
        for wid in WINDOW_IDS
    }
    per_window_sessions = {
        wid: SessionsWindow(
            messages_per_session=histogram("sessions", ["chat_fragmentation"]),
            session_duration_minutes=histogram("sessions", ["chat_fragmentation", "duration_definition"]),
        )
        for wid in WINDOW_IDS
    }
    per_window_tokens = {wid: TokensWindow(completion_tokens_per_message=histogram("messages")) for wid in WINDOW_IDS}
    per_window_language = {
        wid: LanguageWindow(totals=LanguageTotals(de=ok(280), en=ok(120), other=ok(0), undetermined=suppressed()))
        for wid in WINDOW_IDS
    }
    return Aggregates(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime(2025, 4, 7, 5, 0, tzinfo=timezone.utc),
        data_through_week="2025-W14",
        data_through_date=date(2025, 4, 6),
        first_week="2025-W11",
        privacy_floor_n=3,
        label_versions={"language": "lang-heuristic-v1"},
        timezone="Europe/Vienna",
        data_provenance="synthetic",
        pipeline_version="0.1.0",
        windows=[
            AllTimeWindow(
                kind="all_time", id="all_time", label="All time",
                coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
            SemesterWindow(
                kind="semester", id="2025S", label="Summer semester 2025",
                start_date=date(2025, 3, 1), end_date=date(2025, 6, 30),
                weeks=weeks_range("2025-W10", "2025-W26"),
                coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
            TrailingWindow(
                kind="trailing", id="trailing_4", label="Last 4 weeks",
                weeks=WEEKS, coverage={"from": "2025-W11", "through": "2025-W14"},
            ),
        ],
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=series([41, None, 0, 87]),
                    sessions=series([18, None, 0, 33], ["chat_fragmentation"]),
                    active_students=series([12, None, 0, 19], ["bachelor_onboarding"]),
                ),
                per_window=per_window_temporal,
            ),
            usage_context=UsageContext(
                weekly=UsageContextWeekly(registrations=series([9, 4, 0, None])),
                per_window=per_window_usage,
            ),
            sessions=SessionsSection(per_window=per_window_sessions),
            tokens=TokensSection(per_window=per_window_tokens),
            language=LanguageSection(
                weekly=LanguageWeekly(
                    messages_by_language=MessagesByLanguage(
                        de=series([30, None, 0, 60]),
                        en=series([11, None, 0, 27]),
                        other=series([0, 0, 0, 0]),
                        undetermined=series([0, None, 0, 0]),
                        footnote_ids=["language_heuristic"],
                    )
                ),
                per_window=per_window_language,
            ),
        ),
    )
```

- [ ] **Step 2: Write the round-trip tests** — `pipeline/tests/test_round_trip.py`:

```python
from statsboteval_pipeline.contract import Aggregates, dump_doc

from .factories import make_synthetic_aggregates


def test_factory_produces_valid_document() -> None:
    assert make_synthetic_aggregates().data_provenance == "synthetic"


def test_round_trip_equality() -> None:
    doc = dump_doc(make_synthetic_aggregates())
    assert dump_doc(Aggregates.model_validate(doc)) == doc


def test_round_trip_strips_unknown_fields() -> None:
    # Readers ignore unknown fields (invariant 5); the writer-side extras guard is
    # exactly this asymmetry: extras never survive validate->dump.
    doc = dump_doc(make_synthetic_aggregates())
    doc["sections"]["temporal_usage"]["weekly"]["messages"]["stray_field"] = "should not survive"
    assert dump_doc(Aggregates.model_validate(doc)) != doc


def test_generated_at_serializes_utc_z() -> None:
    doc = dump_doc(make_synthetic_aggregates())
    assert doc["generated_at"].endswith("Z")
```

Note: `tests/` needs to be a package for the relative import — create an empty `pipeline/tests/__init__.py` if pytest raises an import error, or change the import to `from factories import make_synthetic_aggregates` (pytest rootdir insertion); prefer adding `__init__.py`.

- [ ] **Step 3: Run to verify pass**

Run: `cd pipeline && .venv/bin/pytest tests/test_round_trip.py -v`
Expected: 4 passed. (If `test_generated_at_serializes_utc_z` fails with `+00:00` instead of `Z` on the installed pydantic version, update `docs/aggregates-contract.md` §3's timestamp wording to `RFC 3339 UTC` without the `Z` example and adjust the assertion to accept either — the contract requirement is RFC 3339 UTC, the exact suffix is cosmetic. Note the choice in the commit message.)

- [ ] **Step 4: Run the full suite**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/tests/factories.py pipeline/tests/test_round_trip.py pipeline/tests/__init__.py
git commit -m "Add full synthetic example factory and round-trip guarantee tests"
```

---

### Task 10: Schema export, committed artifact, drift check

**Files:**
- Create: `pipeline/statsboteval_pipeline/export_schema.py`
- Create: `schema/aggregates.schema.json` (generated, committed)
- Create: `pipeline/tests/test_schema_export.py`

**Interfaces:**
- Consumes: `Aggregates`, `dump_doc`, `make_synthetic_aggregates`.
- Produces: `generate_schema() -> dict[str, Any]`, `SCHEMA_PATH: Path`; the committed artifact the API validates against and the dashboard generates TS types from (later plans).

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_schema_export.py`:

```python
import json

import jsonschema

from statsboteval_pipeline.contract import dump_doc
from statsboteval_pipeline.export_schema import SCHEMA_PATH, generate_schema

from .factories import make_synthetic_aggregates


def test_committed_schema_matches_models() -> None:
    # THE drift guard: regenerating must produce exactly the committed artifact.
    # If this fails: run `python -m statsboteval_pipeline.export_schema` and commit the diff
    # (after confirming the model change was additive — contract §10).
    assert json.loads(SCHEMA_PATH.read_text()) == generate_schema()


def test_synthetic_example_validates_against_committed_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(dump_doc(make_synthetic_aggregates()), schema)


def test_schema_declares_dialect_and_id() -> None:
    schema = generate_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("schema/aggregates.schema.json")


def test_schema_is_permissive_to_unknown_fields() -> None:
    # Invariant 5: readers ignore unknown fields — the exported schema must not
    # forbid additional properties anywhere.
    def walk(node):
        if isinstance(node, dict):
            assert node.get("additionalProperties") is not False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(generate_schema())
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline && .venv/bin/pytest tests/test_schema_export.py -v`
Expected: FAIL — ImportError for `statsboteval_pipeline.export_schema`.

- [ ] **Step 3: Write `pipeline/statsboteval_pipeline/export_schema.py`**

```python
"""Export the contract JSON Schema artifact.

Run from pipeline/: python -m statsboteval_pipeline.export_schema
Writes schema/aggregates.schema.json at the repo root (contract §1).
"""

import json
from pathlib import Path
from typing import Any

from statsboteval_pipeline.contract import Aggregates

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "aggregates.schema.json"


def generate_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://raw.githubusercontent.com/lakhi/statsboteval/main/schema/aggregates.schema.json",
        **Aggregates.model_json_schema(),
    }


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the artifact, then verify all tests pass**

Run:
```bash
cd pipeline && .venv/bin/python -m statsboteval_pipeline.export_schema && .venv/bin/pytest tests/ -v
```
Expected: `wrote …/schema/aggregates.schema.json`, then all tests pass — including the drift test against the just-written artifact. If `test_schema_is_permissive_to_unknown_fields` fails, find the model setting `extra="forbid"` and remove it (Global Constraints).

- [ ] **Step 5: Sanity-check the artifact and commit**

Open `schema/aggregates.schema.json` and confirm: `$defs` contains `OkCell`, `SuppressedCell`, `Aggregates`; `CountCell` unions use `discriminator`/`oneOf`-style mapping; `Coverage` exposes property `"from"` (not `from_`).

```bash
git add pipeline/statsboteval_pipeline/export_schema.py pipeline/tests/test_schema_export.py schema/aggregates.schema.json
git commit -m "Export aggregates JSON Schema artifact with drift check"
```

---

### Task 11: Lint, type-check, cross-link docs

**Files:**
- Modify: `pipeline/statsboteval_pipeline/contract.py` (fixes only, if any)
- Modify: `docs/aggregates-contract.md:1-11` (status header)

**Interfaces:**
- Consumes: everything.
- Produces: clean `ruff` + `mypy` runs; contract doc points at the implementation.

- [ ] **Step 1: Run linters and fix findings**

Run:
```bash
cd pipeline && .venv/bin/ruff check . && .venv/bin/mypy statsboteval_pipeline
```
Expected: no errors (fix any findings; re-run tests after fixes).

- [ ] **Step 2: Update the contract doc header**

In `docs/aggregates-contract.md`, extend the status paragraph's last sentence so the doc names the concrete artifacts:

Change: `If prose and models ever disagree on a *shape*, the models win and this doc gets fixed; for *semantics* (what a value means, when it may be published) this doc is the law.`

To: `If prose and models ever disagree on a *shape*, the models win and this doc gets fixed; for *semantics* (what a value means, when it may be published) this doc is the law. Implemented: models in `pipeline/statsboteval_pipeline/contract.py`; artifact regenerated via `python -m statsboteval_pipeline.export_schema`; drift-checked by `pipeline/tests/test_schema_export.py`.`

- [ ] **Step 3: Full suite one last time**

Run: `cd pipeline && .venv/bin/pytest tests/ -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add pipeline/ docs/aggregates-contract.md
git commit -m "Lint/type-clean contract module; cross-link implementation from contract doc"
```

---

## Out of scope (later plans, per docs/plans/2026-06-12-milestone-1-phase-a.md)

Aggregation SQL and the publish guard's floor computation (they *consume* these models), blob upload/`latest.json` protocol, FastAPI service, dashboard + TypeScript type generation (`schema/aggregates.schema.json` is its input), synthetic `students`/`history` fixture generator, CI workflow.
