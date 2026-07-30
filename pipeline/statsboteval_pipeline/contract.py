"""Aggregates-file contract v1 — single source of truth for shapes.

Semantics are normative in docs/aggregates-contract.md; these models are the
law for shapes (contract §1). Exported to schema/aggregates.schema.json by
statsboteval_pipeline.export_schema.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Annotated, Any, Literal, Union

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, model_serializer, model_validator

SCHEMA_VERSION = "1.5.0"

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
    # 1.4.0 (D-50). `new_registrations` keeps its name and meaning — accounts created
    # in the window — because renaming a published field is a major break; the tab
    # relabels it "New signups". The two additions below are the numbers a reader
    # would otherwise be tempted to derive by subtracting cells (invariant 4).
    new_registrations_active: CountCell | None = None  # of those, sent >=1 message in-window
    new_users: CountCell | None = None  # actives whose first-ever message is in this window
    returning_users: CountCell | None = None  # actives who were active before it
    footnote_ids: list[FootnoteId] | None = None  # notes for the tiles that need one


class UserClasses(BaseModel):
    one_time: CountCell
    monthly: CountCell
    sporadic: CountCell
    # 1.4.0 (D-50): a sub-count of `monthly`, not a fourth class — see stats.is_frequent.
    # The three above still sum to active_students; this one does not add to them.
    frequent: CountCell | None = None
    footnote_ids: list[FootnoteId] | None = None


class UsageContextByStatus(BaseModel):
    """Adoption by program level (1.4.0, D-50; the D-39 usage-time rule)."""

    active_students: CountCell
    messages: CountCell
    # Repeated on every status entry, as TopicDistribution does: the note belongs to the
    # figure, and a dict-of-groups has no other place to hang it.
    footnote_ids: list[FootnoteId] | None = None


class UsageContextWindow(BaseModel):
    totals: UsageContextTotals
    user_classes: UserClasses
    # Keyed by 'bachelor' | 'master' | 'staff' | 'unknown'; absent when no roster is
    # imported, exactly as topics.by_status is (D-39).
    by_status: dict[str, UsageContextByStatus] | None = None


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


class PerStudentWindow(BaseModel):
    """Engagement breadth: one observation per student, not per session (1.5.0, D-53).

    The `sessions` section above bins sessions; these bin the students behind them.
    Nothing here is derivable from that section or from `usage_context.totals`:
    dividing two floored totals yields a mean and says nothing about the spread,
    which for every one of these three is where the finding lives (invariant 4).
    """

    sessions_per_student: Histogram
    weeks_active_per_student: Histogram
    messages_per_student: Histogram


class PerStudentSection(BaseModel):
    per_window: dict[str, PerStudentWindow]


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


class TopicItem(BaseModel):
    label: str
    cell: CountCell
    # 1.2.0: reviewed one-line definition of the label (emergent themes only for
    # now — Bergmann category definitions stay unpublished per D-16).
    description: str | None = None


class TopicDistribution(BaseModel):
    # Multi-label counts: a message may carry several categories/themes, so item
    # cells do not sum to n_total (the multi_label footnote states so).
    items: list[TopicItem]
    n_total: CountCell
    footnote_ids: list[FootnoteId] | None = None


class TopicGroup(BaseModel):
    deductive: TopicDistribution
    method_themes: TopicDistribution
    software_themes: TopicDistribution
    emergent_themes: TopicDistribution | None = None  # Stage 2 (D-38); absence is a designed state


STATUS_KEYS = ("bachelor", "master", "staff", "unknown")


class TopicsWindowEntry(TopicGroup):
    # D-39: optional program-level split; every cell floored independently —
    # the floor, not the schema, is the small-group defense.
    by_status: dict[str, TopicGroup] | None = None

    @model_validator(mode="after")
    def _status_keys_known(self) -> "TopicsWindowEntry":
        if self.by_status is not None:
            unexpected = set(self.by_status) - set(STATUS_KEYS)
            if unexpected:
                raise ValueError(f"by_status keys must be among {STATUS_KEYS}: unexpected {sorted(unexpected)}")
        return self


class TopicsSection(BaseModel):
    per_window: dict[str, TopicsWindowEntry]
    theme_set_version: str | None = None  # reviewed set behind emergent_themes (D-33)


# --- trends (contract §7.6, schema 1.3.0 — D-49) ---

TREND_TABS = ("topics", "adoption", "engagement", "timing", "language")
TREND_MAX_FINDINGS = 5
# Topics carries most of tier 1 (method + emergent themes); capping it at 2 like the
# rest would push lower-tier findings onto the page by construction (D-49 choice 9).
TREND_TAB_CAPS = {"topics": 3}
TREND_DEFAULT_TAB_CAP = 2


class MeasureValue(BaseModel):
    # Deliberately NOT CountCell: a finding's sides are derived floats (rates, shares,
    # medians), and a sub-floor candidate is dropped before publication rather than
    # marked suppressed — so there is no suppressed state to represent (invariant 2 is
    # satisfied by absence, not by a marker). n_students rides along so every number
    # stays citable and the publish guard can re-check the floor.
    value: float
    n_students: int = Field(ge=1)


class TrajectoryPoint(BaseModel):
    window_id: str
    value: float
    n_students: int = Field(ge=1)


class WindowBaseline(BaseModel):
    kind: Literal["window"]
    window_id: str


class WeeksBaseline(BaseModel):
    # trailing_4's baseline: the 4 complete weeks before it. Embedded here rather than
    # added to the window registry — it is a comparison, not something to select.
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["weeks"]
    from_: WeekId = Field(alias="from")
    through: WeekId

    @model_validator(mode="after")
    def _ordered(self) -> "WeeksBaseline":
        if week_monday(self.from_) > week_monday(self.through):
            raise ValueError("baseline.from must not be after baseline.through")
        return self


class TrajectoryBaseline(BaseModel):
    # all_time: every finding carries its per-semester trajectory instead of one baseline.
    kind: Literal["trajectory"]


BaselineRef = Annotated[Union[WindowBaseline, WeeksBaseline, TrajectoryBaseline], Field(discriminator="kind")]


class Finding(BaseModel):
    id: str  # stable slug, e.g. "language-de-share"
    tab: Literal["topics", "adoption", "engagement", "timing", "language"]
    title: str  # template-generated from pinned measure names — never chat-derived (D-49)
    measure: str
    kind: Literal["rate", "share", "median"]
    unit: str
    current: MeasureValue
    baseline: MeasureValue
    delta: float  # in unit terms (pp, per-week, minutes…)
    evidence: Literal["robust", "indicative"]  # BH-adjusted p<.05 vs unadjusted only
    method: str
    trajectory: list[TrajectoryPoint] | None = None  # only under a trajectory baseline
    footnote_ids: list[FootnoteId] | None = None


class TrendsWindow(BaseModel):
    baseline: BaselineRef | None = None  # null = no predecessor to compare against
    # True when a baseline exists but no candidate was even testable (every one fell
    # below the floor or the minimum n). Distinct from an empty findings list, which
    # means tested and flat — break weeks must not read as "nothing changed" (D-49).
    insufficient_data: bool = False
    findings: list[Finding] = Field(default_factory=list, max_length=TREND_MAX_FINDINGS)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        # dump_doc uses exclude_none, which would drop baseline=None — but null IS the
        # "no predecessor" marker the dashboard branches on (contract §7.6), so
        # reinstate it. Same reasoning as HistogramBin.hi.
        data = handler(self)
        if self.baseline is None:
            data["baseline"] = None
        return data

    @model_validator(mode="after")
    def _coherent(self) -> "TrendsWindow":
        if self.baseline is None:
            if self.findings:
                raise ValueError("findings require a baseline to compare against")
            if self.insufficient_data:
                raise ValueError("insufficient_data is meaningless without a baseline")
        if self.insufficient_data and self.findings:
            raise ValueError("insufficient_data must be false when findings are published")

        by_tab: dict[str, int] = {}
        for finding in self.findings:
            by_tab[finding.tab] = by_tab.get(finding.tab, 0) + 1
        for tab, count in by_tab.items():
            cap = TREND_TAB_CAPS.get(tab, TREND_DEFAULT_TAB_CAP)
            if count > cap:
                raise ValueError(f"at most {cap} findings from tab {tab!r}: got {count}")

        # The tagged union already says whether this window is a trajectory comparison;
        # per-finding trajectories must agree with it.
        wants_trajectory = self.baseline is not None and self.baseline.kind == "trajectory"
        for finding in self.findings:
            if finding.trajectory is not None and not wants_trajectory:
                raise ValueError(f"finding {finding.id!r} carries a trajectory without a trajectory baseline")
            if finding.trajectory is None and wants_trajectory:
                raise ValueError(f"finding {finding.id!r} must carry a trajectory under a trajectory baseline")
        return self


class TrendsSection(BaseModel):
    per_window: dict[str, TrendsWindow]


class Sections(BaseModel):
    # Every section optional: readers tolerate absence (invariant 5).
    temporal_usage: TemporalUsage | None = None
    usage_context: UsageContext | None = None
    sessions: SessionsSection | None = None
    # 1.5.0 (D-53): `tokens` (completion tokens per message) was removed here. It measured
    # the model's verbosity rather than student engagement, and no view rendered it. The
    # column still lands in the corpus, so reinstating the section is aggregation-only.
    per_student: PerStudentSection | None = None
    language: LanguageSection | None = None
    topics: TopicsSection | None = None  # Phase B (schema 1.1.0); 1.0.0 readers ignore it
    trends: TrendsSection | None = None  # schema 1.3.0 (D-49); 1.2.0 readers ignore it


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
        # Every per_window-shaped section must be listed, or its window ids go unchecked.
        for name in ("temporal_usage", "usage_context", "sessions", "per_student", "language", "topics", "trends"):
            section = getattr(s, name)
            if section is not None:
                yield name, section.per_window

    def _check_trends(self, window_ids: set[str]) -> None:
        """Floor and registry checks for findings (contract §7.6).

        Findings publish derived floats with no suppressed state, so the floor cannot be
        re-read off the cell the way floored_count() guarantees elsewhere — every side
        is checked explicitly here instead.
        """
        trends = self.sections.trends
        if trends is None:
            return
        all_time_ids = {w.id for w in self.windows if w.kind == "all_time"}
        for window_id, entry in trends.per_window.items():
            baseline = entry.baseline
            if isinstance(baseline, WindowBaseline) and baseline.window_id not in window_ids:
                raise ValueError(
                    f"trends.per_window.{window_id}.baseline references unknown window {baseline.window_id!r}"
                )
            if isinstance(baseline, TrajectoryBaseline) and window_id not in all_time_ids:
                raise ValueError(
                    f"trends.per_window.{window_id}: a trajectory baseline belongs only to the all_time window"
                )
            for finding in entry.findings:
                sides = [("current", finding.current.n_students), ("baseline", finding.baseline.n_students)]
                sides += [(f"trajectory[{p.window_id}]", p.n_students) for p in finding.trajectory or ()]
                for side, n_students in sides:
                    if n_students < self.privacy_floor_n:
                        raise ValueError(
                            f"trends.per_window.{window_id} finding {finding.id!r} side {side} has "
                            f"n_students={n_students} below the floor of {self.privacy_floor_n}"
                        )
                for point in finding.trajectory or ():
                    if point.window_id not in window_ids:
                        raise ValueError(
                            f"trends.per_window.{window_id} finding {finding.id!r} trajectory "
                            f"references unknown window {point.window_id!r}"
                        )

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
        self._check_trends(window_ids)
        referenced = set(_iter_footnote_ids(dump_doc(self.sections)))
        unknown_footnotes = referenced - set(self.footnotes)
        if unknown_footnotes:
            raise ValueError(f"unknown footnote ids referenced: {sorted(unknown_footnotes)}")
        expected = weeks_range(self.first_week, self.data_through_week)
        for path, weekly in self._weekly_series():
            if [entry.week for entry in weekly.series] != expected:
                raise ValueError(f"sections.{path} must be dense over [{self.first_week}, {self.data_through_week}]")
        return self
