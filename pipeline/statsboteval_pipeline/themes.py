"""Versioned, operator-reviewed theme sets (migration 005, D-33).

The synthesis step writes a draft Markdown table for the operator to edit;
`freeze_theme_set` loads the reviewed file and stamps `reviewed_at`. Assignment
refuses any set without that stamp — the review is the privacy control keeping
labels derived from real chat text out of published aggregates.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import duckdb

from .classify.parse import ClassifierParseError, _cells

# Sanity bounds for a theme list (synthesis guidance is ~12-20; the operator may
# trim or extend at review, but an empty or sprawling list is a mistake).
MIN_THEMES = 3
MAX_THEMES = 40
MAX_LABEL_CHARS = 80


class ThemeSetError(ValueError):
    """A theme set is missing, unreviewed, or already frozen."""


class ThemeEntry(NamedTuple):
    label: str
    description: str


def parse_theme_table(text: str) -> list[ThemeEntry]:
    """Parse a `| Theme | Description |` table (synthesis output or the edited draft).

    Strict like the classifier parsers — raises ClassifierParseError on any
    structural deviation so the retry ladder (and the freeze CLI) reject it.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if not lines:
        raise ClassifierParseError("no Markdown table found")
    header = _cells(lines[0])
    if [h.lower() for h in header] != ["theme", "description"]:
        raise ClassifierParseError(f"unexpected table header: {lines[0]} (expected | Theme | Description |)")
    entries: list[ThemeEntry] = []
    seen: set[str] = set()
    for raw in lines[1:]:
        cells = _cells(raw)
        if all(c and set(c) <= set(":-") for c in cells):
            continue  # separator line
        if len(cells) != 2:
            raise ClassifierParseError(f"expected 2 columns in row: {raw}")
        label, description = cells
        if not label or not description:
            raise ClassifierParseError(f"empty theme or description in row: {raw}")
        if len(label) > MAX_LABEL_CHARS:
            raise ClassifierParseError(f"theme label over {MAX_LABEL_CHARS} characters in row: {raw}")
        if label.casefold() in seen:
            raise ClassifierParseError(f"duplicate theme label in row: {raw}")
        seen.add(label.casefold())
        entries.append(ThemeEntry(label, description))
    if not MIN_THEMES <= len(entries) <= MAX_THEMES:
        raise ClassifierParseError(f"expected {MIN_THEMES}-{MAX_THEMES} themes, got {len(entries)}")
    return entries


def write_draft(entries: list[ThemeEntry], path: Path, *, set_version: str) -> None:
    """Write the git-ignored review file. The operator edits it in place, then freezes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(f"| {e.label} | {e.description} |" for e in entries)
    path.write_text(
        f"# Draft emergent themes — {set_version} (REVIEW BEFORE FREEZING)\n"
        "\n"
        "This list was synthesized from candidate codes derived from REAL chat text\n"
        "(D-33). Review every label: merge, rename, or cut freely; keep labels short,\n"
        "generic, and non-identifying (no names, no quotes, no specifics that could\n"
        "point to a person). Then run `freeze-themes` to make the set assignable.\n"
        "\n"
        "| Theme | Description |\n"
        "|---|---|\n"
        f"{rows}\n"
    )


def freeze_theme_set(
    con: duckdb.DuckDBPyConnection, entries: list[ThemeEntry], set_version: str, *, now: datetime
) -> int:
    """Load a reviewed theme list and stamp `reviewed_at`. A frozen version is immutable."""
    if con.execute("SELECT 1 FROM theme_sets WHERE set_version = ? LIMIT 1", [set_version]).fetchone():
        raise ThemeSetError(f"theme set {set_version!r} already exists; bump the version instead of editing it")
    con.executemany(
        "INSERT INTO theme_sets (set_version, code, description, created_at, reviewed_at) VALUES (?, ?, ?, ?, ?)",
        [(set_version, e.label, e.description, now, now) for e in entries],
    )
    return len(entries)


def reviewed_theme_labels(con: duckdb.DuckDBPyConnection, set_version: str) -> list[str] | None:
    """The set's labels if it exists AND is reviewed; None if absent; raises if unreviewed."""
    rows = con.execute(
        "SELECT code, reviewed_at FROM theme_sets WHERE set_version = ? ORDER BY code", [set_version]
    ).fetchall()
    if not rows:
        return None
    if any(reviewed_at is None for _, reviewed_at in rows):
        raise ThemeSetError(f"theme set {set_version!r} exists but is not reviewed; run freeze-themes first")
    return [code for code, _ in rows]
