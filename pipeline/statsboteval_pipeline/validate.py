"""Classifier validation: per-category MCC of one of our label versions vs bergmann-v1 (D-30).

The label version is a parameter, not a literal: D-07's `labels` PK lets versions
coexist, so scoring v1 and v2 against the same 300 consensus messages is just two
calls. Every report states which version it scored — a saved report that does not
say cannot be told apart from another version's later (D-45 mints v2 beside v1).

Ground truth is the 300-row human-consensus sample (`provenance='human_consensus'`
in the bergmann-v1 import); agreement on the GPT-5-coded remainder would measure
model-vs-model, not correctness, so those rows never enter the score. MCC is
computed by hand; a zero-variance denominator yields NA (Bergmann's Multiple
Choice was NA the same way). Frozen/emergent themes are deliberately not scored
(Bergmann validated themes by expert similarity rating, not MCC).

The report's caveat records the two-way conflation (D-30): an MCC gap vs the
published values mixes model differences AND our consolidated-prompt departure
from their one-category-per-prompt design. The validation report itself is a
git-ignored local artifact (D-16).
"""

from __future__ import annotations

import math
from typing import NamedTuple

import duckdb

from statsboteval_pipeline.labels import CURRENT_LABEL_VERSION

CAVEAT = (
    "MCC gaps vs the published Bergmann values conflate two differences at once: the "
    "classifier model AND the consolidated multi-label prompt (theirs coded one "
    "category per prompt). Themes are not MCC-scored (Bergmann validated themes by "
    "expert similarity, not MCC); emergent themes have no Bergmann counterpart."
)


class CategoryResult(NamedTuple):
    tp: int
    tn: int
    fp: int
    fn: int
    mcc: float | None  # None = NA (zero-variance denominator)


class ValidationReport(NamedTuple):
    label_version: str  # the version of ours that was scored
    n_messages: int  # human-consensus messages with labels on both sides
    per_category: dict[str, CategoryResult]
    model_tags: set[str]  # provenance values seen under `label_version`
    average_mcc: float | None  # mean over scoreable categories; NA ones are excluded, not zeroed
    caveat: str


def validate_against_bergmann(
    con: duckdb.DuckDBPyConnection, *, label_version: str = CURRENT_LABEL_VERSION
) -> ValidationReport:
    rows = con.execute(
        "SELECT b.code, b.value, o.value FROM labels b "
        "JOIN labels o ON o.history_id = b.history_id AND o.domain = b.domain AND o.code = b.code "
        "WHERE b.label_version = 'bergmann-v1' AND b.provenance = 'human_consensus' "
        "  AND b.domain = 'deductive' AND o.label_version = ? "
        "ORDER BY b.code, b.history_id",
        [label_version],
    ).fetchall()
    if not rows:
        raise ValueError(
            f"no overlapping human-consensus rows between bergmann-v1 and {label_version} "
            "— import bergmann-v1 and classify the same messages first"
        )
    counts: dict[str, list[int]] = {}
    for code, theirs, ours in rows:
        tally = counts.setdefault(code, [0, 0, 0, 0])  # tp, tn, fp, fn
        if theirs == 1 and ours == 1:
            tally[0] += 1
        elif theirs == 0 and ours == 0:
            tally[1] += 1
        elif theirs == 0 and ours == 1:
            tally[2] += 1
        else:
            tally[3] += 1
    per_category = {code: CategoryResult(tp, tn, fp, fn, _mcc(tp, tn, fp, fn)) for code, (tp, tn, fp, fn) in counts.items()}
    n_messages_row = con.execute(
        "SELECT count(DISTINCT b.history_id) FROM labels b "
        "JOIN labels o ON o.history_id = b.history_id AND o.label_version = ? "
        "WHERE b.label_version = 'bergmann-v1' AND b.provenance = 'human_consensus'",
        [label_version],
    ).fetchone()
    model_tags = {
        row[0]
        for row in con.execute(
            "SELECT DISTINCT provenance FROM labels WHERE label_version = ?", [label_version]
        ).fetchall()
    }
    # The headline number D-42/D-45 quote: the mean of the per-category MCCs, with NA
    # categories dropped rather than counted as zero (a zero-variance category is
    # unmeasured, not failed — scoring it 0 would have cost the .71 figure ~.05).
    scoreable = [r.mcc for r in per_category.values() if r.mcc is not None]
    return ValidationReport(
        label_version=label_version,
        n_messages=n_messages_row[0] if n_messages_row else 0,
        per_category=per_category,
        model_tags=model_tags,
        average_mcc=sum(scoreable) / len(scoreable) if scoreable else None,
        caveat=CAVEAT,
    )


def format_validation_report(report: ValidationReport) -> str:
    lines = [
        f"Validation of {report.label_version} vs bergmann-v1 human consensus "
        f"(n = {report.n_messages} messages)",
        f"Classifier: {', '.join(sorted(report.model_tags))}",
        "",
        f"{'category':<32} {'MCC':>6}   tp   tn   fp   fn",
    ]
    for code in sorted(report.per_category):
        result = report.per_category[code]
        mcc = "NA" if result.mcc is None else f"{result.mcc:.3f}"
        lines.append(f"{code:<32} {mcc:>6}  {result.tp:>3}  {result.tn:>3}  {result.fp:>3}  {result.fn:>3}")
    scored = sum(1 for r in report.per_category.values() if r.mcc is not None)
    average = "NA" if report.average_mcc is None else f"{report.average_mcc:.3f}"
    lines += ["", f"{f'AVERAGE ({scored} scoreable)':<32} {average:>6}", "", f"Caveat: {report.caveat}"]
    return "\n".join(lines)


def _mcc(tp: int, tn: int, fp: int, fn: int) -> float | None:
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denominator == 0:
        return None
    return (tp * tn - fp * fn) / denominator
