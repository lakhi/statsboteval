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

SCHEMA_VERSION = "1.8.0"

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


class Daypart(BaseModel):
    """One block of the day, in the registry at document root (1.6.0, D-54).

    Boundaries live in the document rather than in dashboard code for the same reason
    footnote texts do: a definition is versioned with the numbers it governs, and an
    archived blob must still say what its own cells meant. `from_hour` is inclusive,
    `to_hour` exclusive; the registry partitions 0..24 contiguously, so no block wraps
    midnight and `hour // width` is a valid lookup.
    """

    id: str
    label: str
    from_hour: int = Field(ge=0, le=23)
    to_hour: int = Field(ge=1, le=24)

    @model_validator(mode="after")
    def _forward(self) -> "Daypart":
        if self.to_hour <= self.from_hour:
            raise ValueError(f"daypart {self.id!r}: to_hour must be after from_hour (no midnight wrap)")
        return self


class DaypartCell(BaseModel):
    dow: int = Field(ge=1, le=7)  # ISO: Monday = 1
    daypart: str  # resolves against the document's dayparts registry
    cell: CountCell


class DaypartGrid(BaseModel):
    """Weekday x daypart activity (1.6.0, D-54) — the coarse twin of HeatmapGrid.

    Density is checked at document root, not here: it is 7 x len(dayparts) and only the
    root knows the registry. HeatmapGrid can self-check because 24 is a constant.
    """

    cells: list[DaypartCell]
    footnote_ids: list[FootnoteId] | None = None

    @model_validator(mode="after")
    def _unique_pairs(self) -> "DaypartGrid":
        seen = {(c.dow, c.daypart) for c in self.cells}
        if len(seen) != len(self.cells):
            raise ValueError("daypart grid contains duplicate (dow, daypart) cells")
        return self


class DaypartTotals(BaseModel):
    # weekend/weekday are floored on their own contributing-student sets, never derived
    # from each other — a difference across a suppressed cell would leak it (invariant 4).
    by_daypart: dict[str, CountCell]
    weekend: CountCell
    weekday: CountCell
    footnote_ids: list[FootnoteId] | None = None


class Coverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: WeekId = Field(alias="from")  # "from" is a Python keyword
    through: WeekId

    @model_validator(mode="after")
    def _ordered(self) -> "Coverage":
        if week_monday(self.from_) > week_monday(self.through):
            raise ValueError("coverage.from must not be after coverage.through")
        return self


# `label` is self-contained (it names its own semester); `short_label` is what a reader sees
# when the surrounding context already names the parent — inside the picker's group heading.
# Both are authored here rather than in the client so wording can change on a blob upload
# with no code deploy, which is how D-52 shipped a rename.
#
# `short_label` is OPTIONAL on the two pre-1.8.0 kinds, and that is a deployment property,
# not laziness. The API validates every fetched blob against the schema it ships with
# (contract §11), so a required field here would make the currently-published document fail
# validation the moment the new API is deployed — a 500, not a degraded render, for however
# long the blob upload trails the deploy. Optional keeps the sequence safe in the order that
# is actually available: deploy first, publish second. Readers fall back to `label`.
class AllTimeWindow(BaseModel):
    kind: Literal["all_time"]
    id: str
    label: str
    short_label: str | None = None
    coverage: Coverage


class SemesterWindow(BaseModel):
    kind: Literal["semester"]
    id: str
    label: str
    short_label: str | None = None
    start_date: date
    end_date: date
    weeks: list[WeekId]  # full membership (Thursday rule); coverage = clipped to data range
    coverage: Coverage


class SemesterSliceWindow(BaseModel):
    """The closing stretch of one semester (1.8.0, D-56).

    Replaces `TrailingWindow`, which was anchored on the axis and therefore advanced with
    extraction whether or not anyone was in class — across a break it drifted into weeks
    holding almost nothing, which is where "recent" was least useful and most looked at.
    A slice is anchored inside its semester instead, so during teaching weeks it is exactly
    what the trailing window showed and across breaks it keeps pointing at the last weeks
    that meant something.

    `weeks` is always a contiguous tail of the parent's *covered* weeks, so the id is stable
    forever once the semester ends — `2026S.last1` names the same span in every later
    publish, which `trailing_4` never did.
    """

    kind: Literal["semester_slice"]
    id: str
    label: str
    short_label: str
    parent_window_id: str  # the semester this slices; validated against the registry
    weeks: list[WeekId]
    # [first, last], 1-based, within the parent's FULL Thursday-rule membership — never its
    # coverage (the D-54 invariant). Published, deliberately unrendered: SS terms run 17
    # weeks and WS terms 18, so "final 4 weeks" spans different teaching weeks on each side
    # of a cross-semester comparison, and the document should say so itself.
    #
    # A length-bounded list rather than a tuple: pydantic exports a tuple as `prefixItems`,
    # which the dashboard's type generator renders as `[unknown, unknown]` — a published
    # field that arrives untyped on the client is worse than one modelled slightly loosely.
    semester_weeks: list[int] = Field(min_length=2, max_length=2)
    coverage: Coverage


class TrailingWindow(BaseModel):
    """DEPRECATED, unemitted since 1.8.0 (D-56) — kept so the *previous* publish still parses.

    Semester slices replaced this window, and deleting the member outright looked free
    because nothing produces one. It is not: the API validates every blob it fetches
    against the schema it ships with (contract §11), so the moment a 1.8.0 API met the
    1.7.0 document already sitting in the blob, `kind: "trailing"` would match no member of
    the union and the dashboard would go down with a 500 — until the new blob was uploaded,
    with no safe order to do the two halves in.

    So it stays for one release. Remove it once no reachable blob contains one, which
    includes the rollback target.

    What this does and does not buy, stated exactly, because the difference matters when
    someone is reading it under pressure: it makes the *deploy* safe in one direction —
    ship the bundle and API first, and the 1.7.0 document already in the blob keeps
    parsing, so there is no window where the site is down waiting for the upload. It does
    NOT make a rollback free once the 1.8.0 blob has been uploaded: a rolled-back 1.7.0 API
    cannot parse `semester_slice`, so after publishing, reverting the code means restoring
    the previous blob in the same move. Blobs are immutable and versioned, so that is
    available — it is a step to remember, not a trap.
    """

    kind: Literal["trailing"]
    id: str
    label: str
    weeks: list[WeekId]
    coverage: Coverage


Window = Annotated[
    Union[AllTimeWindow, SemesterWindow, SemesterSliceWindow, TrailingWindow], Field(discriminator="kind")
]
window_adapter: TypeAdapter[AllTimeWindow | SemesterWindow | SemesterSliceWindow | TrailingWindow] = TypeAdapter(
    Window
)


# --- sections (contract §7): one model tree per dashboard view ---


class TemporalUsageWeekly(BaseModel):
    messages: WeeklySeries
    sessions: WeeklySeries
    active_students: WeeklySeries


class TemporalUsageByStatus(BaseModel):
    """Timing for one program level (1.7.0, D-55).

    `activity_heatmap` is deliberately absent: the 7x24 grid has been unrendered since
    D-54 and is 44 KB of the document on its own, so three more copies would buy nothing.
    A split that leaves it out is not a smaller version of the cohort-wide window — it is
    the part the dashboard actually draws.
    """

    daypart_heatmap: DaypartGrid
    daypart_totals: DaypartTotals


class TemporalUsageWindow(BaseModel):
    # 1.6.0 (D-54): the dashboard renders `daypart_heatmap`; `activity_heatmap` stays
    # published and unread. It is a *required field of a section that stays*, and §10
    # forbids removing that within a major version — the 1.5.0 exception covers
    # withdrawing a whole optional section only. Also the rollback path.
    activity_heatmap: HeatmapGrid
    daypart_heatmap: DaypartGrid | None = None
    daypart_totals: DaypartTotals | None = None
    # 1.7.0 (D-55). Keyed by STATUS_KEYS; absent when no roster is imported, exactly as
    # topics.by_status is. A level appears only when it has messages in the window.
    by_status: dict[str, TemporalUsageByStatus] | None = None


class SemesterProfilePoint(BaseModel):
    semester_week: int = Field(ge=1)
    week: WeekId  # the real ISO week behind the index, so the tooltip can name it
    messages: CountCell
    active_students: CountCell


class SemesterProfile(BaseModel):
    """One semester re-indexed to teaching week, for the cross-semester overlay (1.6.0).

    `messages` is what the dashboard plots; `active_students` rides along because cohorts
    differ in size (2025S 165 vs 2026S 117) and it is the size-robust read — publishing
    both means a later toggle is a dashboard change, not another schema bump.
    """

    window_id: str  # resolves against the windows registry; must be a semester window
    label: str
    kind: Literal["summer", "winter"]
    points: list[SemesterProfilePoint]
    # Repeated on every profile, as UsageContextByStatus does: the note belongs to the
    # figure, and a bare list of profiles has no other place to hang it.
    footnote_ids: list[FootnoteId] | None = None


class TemporalUsage(BaseModel):
    weekly: TemporalUsageWeekly
    per_window: dict[str, TemporalUsageWindow]
    # Deliberately not per_window: the whole point is comparing across windows, so the
    # window picker does not apply. The dashboard renders it under all_time only (D-54).
    semester_profiles: list[SemesterProfile] | None = None
    # 1.7.0 (D-55). The weekly series are document-level and sliced client-side, so a
    # program-level filter cannot narrow them without its own copy — without this the
    # Timing tab would show level-scoped dayparts beside cohort-wide trend lines, which
    # is the exact way a global filter starts lying. `semester_profiles` gets no split:
    # it is rendered under All users only, where the filter does not apply.
    weekly_by_status: dict[str, TemporalUsageWeekly] | None = None


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
    """Adoption by program level (1.4.0, D-50; the D-39 usage-time rule).

    1.7.0 (D-55) widens this from the two measures the by-level card needed to what the
    KPI tiles need, because the level filter now scopes the whole tab. `new_registrations`
    is *not* here and will not be: a registration has no session, so the usage-time rule
    does not reach it, and splitting only the `_active` half of that pair would be worse
    than not splitting — the tile renders under All users only instead.
    """

    active_students: CountCell
    messages: CountCell
    sessions: CountCell | None = None  # 1.7.0
    new_users: CountCell | None = None  # 1.7.0, same complementary suppression as totals
    returning_users: CountCell | None = None  # 1.7.0
    user_classes: UserClasses | None = None  # 1.7.0
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


class SessionsByStatus(BaseModel):
    """Conversation depth for one program level (1.7.0, D-55)."""

    messages_per_session: Histogram
    session_duration_minutes: Histogram


class SessionsWindow(BaseModel):
    messages_per_session: Histogram
    session_duration_minutes: Histogram
    by_status: dict[str, SessionsByStatus] | None = None  # 1.7.0


class SessionsSection(BaseModel):
    per_window: dict[str, SessionsWindow]


class PerStudentByStatus(BaseModel):
    """Engagement breadth for one program level (1.7.0, D-55)."""

    sessions_per_student: Histogram
    weeks_active_per_student: Histogram
    messages_per_student: Histogram


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
    # 1.7.0 (D-55). A BA->MA transitioner active on both sides of their boundary
    # contributes one observation to each level, so the per-level n_students sum can
    # exceed the window's — the status_multi footnote already states exactly that.
    by_status: dict[str, PerStudentByStatus] | None = None


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
    by_status: dict[str, LanguageTotals] | None = None  # 1.7.0 (D-55)


class LanguageSection(BaseModel):
    weekly: LanguageWeekly
    per_window: dict[str, LanguageWindow]
    # 1.7.0 (D-55), same reasoning as temporal_usage.weekly_by_status: the weekly chart
    # is the tab's main figure and is sliced client-side from a document-level series.
    weekly_by_status: dict[str, LanguageWeekly] | None = None


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
    # An arbitrary week range as a comparison — embedded here rather than added to the
    # window registry, because it is something to compare against, not something to select.
    #
    # Nothing emits one as of 1.8.0: it was trailing_4's baseline (the 4 complete weeks
    # before it), and trailing_4 is gone (D-56). Kept in the union because deciding slice
    # pairing — the open question that blocks un-hiding Trends — may well land on
    # "the weeks immediately preceding this slice", and re-adding a removed union member
    # is a second breaking change for the same feature.
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


class EnrollmentEntry(BaseModel):
    """How many students were enrolled in a program level during one window (1.7.0, D-55).

    Not a measurement, which is why this lives outside `sections` and carries plain ints
    rather than CountCells. Nothing here passes floored_count because there is nothing to
    floor: an institutional headcount is not a count over students who wrote messages, and
    dressing it as a cell would invite exactly that misreading.
    """

    bachelor: int = Field(ge=0)
    master: int = Field(ge=0)
    source: str  # which roster snapshot, so a published number can be traced back
    as_of: date


class Enrollment(BaseModel):
    # Semester windows only: all_time spans three semesters of cohort turnover, so it has
    # no defensible denominator. The dashboard states that in words rather than drawing an
    # empty card. Semester slices (1.8.0) are NOT keyed here and must not be: a slice lies
    # entirely inside one semester, so the denominator it needs is its parent's — the
    # reader follows `parent_window_id` rather than this map carrying the same
    # institutional headcount under seven keys.
    per_window: dict[str, EnrollmentEntry]


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
    # 1.6.0 (D-54). Optional so a 1.5.0-shaped document still validates; required in
    # practice whenever any daypart cell is published (checked in _check_dayparts).
    dayparts: list[Daypart] | None = None
    # 1.7.0 (D-55). Optional: absent when no cohort table is configured, and a 1.6.0
    # document stays valid without it.
    enrollment: Enrollment | None = None
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
        # 1.7.0 (D-55): the per-level copies are sliced by the same client code as the
        # cohort-wide ones, so they carry the same density obligation. Listing them here
        # is what makes a short per-level series a validation failure rather than a
        # trend line that silently starts late.
        if s.temporal_usage is not None and s.temporal_usage.weekly_by_status is not None:
            for level, weekly in s.temporal_usage.weekly_by_status.items():
                yield f"temporal_usage.weekly_by_status.{level}.messages", weekly.messages
                yield f"temporal_usage.weekly_by_status.{level}.sessions", weekly.sessions
                yield f"temporal_usage.weekly_by_status.{level}.active_students", weekly.active_students
        if s.language is not None and s.language.weekly_by_status is not None:
            for level, lang_weekly in s.language.weekly_by_status.items():
                mbl = lang_weekly.messages_by_language
                for lang in ("de", "en", "other", "undetermined"):
                    yield f"language.weekly_by_status.{level}.messages_by_language.{lang}", getattr(mbl, lang)

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

    def _check_dayparts(self) -> None:
        """Registry partitions the day, and every daypart cell resolves against it.

        The grid's own validator cannot do this — density is 7 x len(dayparts) and only
        the root sees the registry (the same reason trends' floor checks live here).
        """
        temporal = self.sections.temporal_usage
        windows_with_dayparts = (
            [(wid, w) for wid, w in temporal.per_window.items() if w.daypart_heatmap or w.daypart_totals]
            if temporal is not None
            else []
        )
        if not windows_with_dayparts:
            return
        if not self.dayparts:
            raise ValueError("daypart cells are published but the dayparts registry is missing")

        ids = [d.id for d in self.dayparts]
        if len(set(ids)) != len(ids):
            raise ValueError("daypart ids must be unique")
        cursor = 0
        for part in sorted(self.dayparts, key=lambda d: d.from_hour):
            if part.from_hour != cursor:
                raise ValueError(f"dayparts must tile 0..24 contiguously: gap or overlap at hour {cursor}")
            cursor = part.to_hour
        if cursor != 24:
            raise ValueError(f"dayparts must cover the whole day: coverage ends at hour {cursor}")

        known = set(ids)
        for window_id, window in windows_with_dayparts:
            grid = window.daypart_heatmap
            if grid is not None:
                unknown = {c.daypart for c in grid.cells} - known
                if unknown:
                    raise ValueError(
                        f"temporal_usage.per_window.{window_id}.daypart_heatmap references "
                        f"unknown dayparts: {sorted(unknown)}"
                    )
                if len(grid.cells) != 7 * len(known):
                    raise ValueError(
                        f"temporal_usage.per_window.{window_id}.daypart_heatmap must hold exactly "
                        f"{7 * len(known)} cells (7 weekdays x {len(known)} dayparts), got {len(grid.cells)}"
                    )
            totals = window.daypart_totals
            if totals is not None and set(totals.by_daypart) != known:
                raise ValueError(
                    f"temporal_usage.per_window.{window_id}.daypart_totals.by_daypart must hold "
                    f"exactly the registry ids {sorted(known)}"
                )

    def _check_semester_profiles(self, window_ids: set[str]) -> None:
        temporal = self.sections.temporal_usage
        if temporal is None or temporal.semester_profiles is None:
            return
        semesters = {w.id for w in self.windows if w.kind == "semester"}
        for profile in temporal.semester_profiles:
            if profile.window_id not in window_ids:
                raise ValueError(f"semester_profiles references unknown window {profile.window_id!r}")
            if profile.window_id not in semesters:
                raise ValueError(f"semester_profiles.{profile.window_id} is not a semester window")
            indices = [p.semester_week for p in profile.points]
            if indices != sorted(indices) or len(set(indices)) != len(indices):
                raise ValueError(f"semester_profiles.{profile.window_id}: semester_week must ascend uniquely")

    def _check_status_keys(self) -> None:
        """Every by_status map anywhere in the document uses the closed key set.

        TopicsWindowEntry has validated its own keys since 1.1.0. 1.7.0 puts by_status in
        six more places, and six copies of that validator is six chances to drift — one
        walk of the dumped document catches them all, including any added later.
        """
        def walk(node: Any, path: str) -> Iterator[tuple[str, str]]:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("by_status", "weekly_by_status") and isinstance(value, dict):
                        for level in value:
                            yield f"{path}.{key}", level
                    yield from walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    yield from walk(item, f"{path}[{i}]")

        for where, level in walk(dump_doc(self.sections), "sections"):
            if level not in STATUS_KEYS:
                raise ValueError(f"{where} uses unknown program level {level!r}; expected one of {STATUS_KEYS}")

    def _check_windows(self) -> None:
        """Slices resolve against their parent, and their teaching-week span is the
        parent's own index (1.8.0, D-56).

        The `semester_weeks` check is the one that earns its keep: indexing a slice against
        *covered* weeks instead of full membership yields a plausible-looking pair that is
        wrong by however many opening weeks fall outside the axis, and every cross-semester
        alignment built on it would slide by that much — invisibly, since each span still
        reads as a sane number on its own (the D-54 invariant, restated as a check).
        """
        semesters = {w.id: w for w in self.windows if w.kind == "semester"}
        for window in self.windows:
            if window.kind != "semester_slice":
                continue
            parent = semesters.get(window.parent_window_id)
            if parent is None:
                raise ValueError(
                    f"windows.{window.id}.parent_window_id references {window.parent_window_id!r}, "
                    "which is not a semester window in this registry"
                )
            if not window.weeks:
                raise ValueError(f"windows.{window.id} has no weeks")
            membership = parent.weeks
            missing = [w for w in window.weeks if w not in membership]
            if missing:
                raise ValueError(f"windows.{window.id} holds weeks outside {parent.id}: {missing}")
            if window.weeks != membership[membership.index(window.weeks[0]) : membership.index(window.weeks[-1]) + 1]:
                raise ValueError(f"windows.{window.id} is not a contiguous run of {parent.id}'s weeks")
            expected = [membership.index(window.weeks[0]) + 1, membership.index(window.weeks[-1]) + 1]
            if window.semester_weeks != expected:
                raise ValueError(
                    f"windows.{window.id}.semester_weeks is {window.semester_weeks}, but its weeks are "
                    f"{parent.id} teaching weeks {expected} — indexed against coverage rather than "
                    "full membership?"
                )
            if (window.coverage.from_, window.coverage.through) != (window.weeks[0], window.weeks[-1]):
                raise ValueError(f"windows.{window.id}.coverage must span exactly its weeks")

    def _check_enrollment(self, window_ids: set[str]) -> None:
        if self.enrollment is None:
            return
        semesters = {w.id for w in self.windows if w.kind == "semester"}
        for window_id in self.enrollment.per_window:
            if window_id not in window_ids:
                raise ValueError(f"enrollment.per_window references unknown window {window_id!r}")
            if window_id not in semesters:
                raise ValueError(
                    f"enrollment.per_window.{window_id} is not a semester window; enrolled-cohort "
                    "denominators are keyed by semester only (D-55). A semester slice inherits its "
                    "parent's entry through parent_window_id (D-56) rather than being keyed here"
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
        self._check_windows()
        self._check_trends(window_ids)
        self._check_dayparts()
        self._check_semester_profiles(window_ids)
        self._check_status_keys()
        self._check_enrollment(window_ids)
        referenced = set(_iter_footnote_ids(dump_doc(self.sections)))
        unknown_footnotes = referenced - set(self.footnotes)
        if unknown_footnotes:
            raise ValueError(f"unknown footnote ids referenced: {sorted(unknown_footnotes)}")
        expected = weeks_range(self.first_week, self.data_through_week)
        for path, weekly in self._weekly_series():
            if [entry.week for entry in weekly.series] != expected:
                raise ValueError(f"sections.{path} must be dense over [{self.first_week}, {self.data_through_week}]")
        return self
