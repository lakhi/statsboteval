"""Bergmann codebook + frozen theme lists, loaded from git-ignored local materials.

The category *definitions* are unpublished research material and stay out of git
(D-16); only their *names* are public (Stage-2 manuscript) and may appear in code
and in published aggregates. The operator materializes `BERGMANN_PROMPTS_DIR` from
the local Bergmann docs (Declarative Statement from manuscript Table 1 — its block
is missing from the public prompt file) and the public Stage-2 theme lists.

Expected directory layout:

    wrapper.txt            shared deductive wrapper (kept for per-category splits)
    categories.md          one block per category:
                               ## <Category Name>
                               - Brief: ...
                               - Full: ...
                               - Code 1: ...
                               - Code 0: ...
                               - Example: ...
                           (field values may wrap onto indented continuation lines)
    method_themes.txt      one frozen theme per line (21 in the real materials)
    software_themes.txt    one frozen theme per line (9 in the real materials)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

# Public names (Stage-2 manuscript Table 1); definitions load from disk at runtime.
DEDUCTIVE_CATEGORY_NAMES: tuple[str, ...] = (
    "Statistics Interaction",
    "Specific Method",
    "Data Analysis Software",
    "Reference to a Prior Content",
    "Multiple Choice",
    "Question Posed",
    "Instruction Given",
    "Capability Request",
    "Declarative Statement",
    "English Input",
    "German Input",
    "Politeness Expression",
    "Greeting Expression",
)

_FIELDS = {
    "Brief": "brief",
    "Full": "full",
    "Code 1": "when_1",
    "Code 0": "when_0",
    "Example": "example",
}


class CodebookError(ValueError):
    """The materials directory is missing or malformed."""


class Category(NamedTuple):
    name: str  # display name, e.g. "Statistics Interaction"
    code: str  # label-table code, e.g. "statistics_interaction"
    brief: str
    full: str
    when_1: str
    when_0: str
    example: str


class Codebook(NamedTuple):
    wrapper: str
    categories: tuple[Category, ...]
    method_themes: tuple[str, ...]
    software_themes: tuple[str, ...]


def category_code(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_codebook(directory: Path, *, expected_categories: Sequence[str] | None = None) -> Codebook:
    """Parse the materials directory; strict — any deviation raises CodebookError."""
    if not directory.is_dir():
        raise CodebookError(
            f"Codebook materials directory not found: {directory} (check BERGMANN_PROMPTS_DIR in pipeline/.env)"
        )
    wrapper = _read(directory, "wrapper.txt").strip()
    if not wrapper:
        raise CodebookError("wrapper.txt is empty")
    categories = _parse_categories(_read(directory, "categories.md"))
    if expected_categories is not None:
        got = [c.name for c in categories]
        missing = [n for n in expected_categories if n not in got]
        extra = [n for n in got if n not in expected_categories]
        if missing or extra:
            raise CodebookError(f"category names do not match expected list (missing: {missing}, extra: {extra})")
    return Codebook(
        wrapper=wrapper,
        categories=categories,
        method_themes=_parse_themes(_read(directory, "method_themes.txt"), "method_themes.txt"),
        software_themes=_parse_themes(_read(directory, "software_themes.txt"), "software_themes.txt"),
    )


def synthetic_codebook() -> Codebook:
    """A tiny, clearly-synthetic codebook for tests and fixtures — no real definitions."""
    categories = tuple(
        Category(
            name=name,
            code=category_code(name),
            brief=f"Synthetic brief for {name}?",
            full=f"Synthetic full definition for {name}, used only in tests.",
            when_1=f"if the synthetic condition for {name} holds.",
            when_0=f"if the synthetic condition for {name} does not hold.",
            example=f"A synthetic example message for {name}.",
        )
        for name in ("Synthetic Alpha", "Synthetic Beta", "Synthetic Gamma")
    )
    return Codebook(
        wrapper="You are a synthetic coder. Rate the category '<CATEGORY>' for each message.",
        categories=categories,
        method_themes=("synthetic method one", "synthetic method two"),
        software_themes=("synthetic software one", "synthetic software two"),
    )


def _read(directory: Path, filename: str) -> str:
    path = directory / filename
    if not path.is_file():
        raise CodebookError(f"missing materials file: {path}")
    return path.read_text(encoding="utf-8")


def _parse_categories(text: str) -> tuple[Category, ...]:
    categories: list[Category] = []
    name: str | None = None
    fields: dict[str, str] = {}
    current_field: str | None = None

    def close_block() -> None:
        nonlocal fields, current_field
        if name is None:
            return
        missing = [label for label in _FIELDS if _FIELDS[label] not in fields]
        if missing:
            raise CodebookError(f"category '{name}': missing field(s) {missing}")
        categories.append(Category(name=name, code=category_code(name), **fields))
        fields, current_field = {}, None

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            close_block()
            name = line[3:].strip()
            if not name:
                raise CodebookError("empty category name after '## '")
            continue
        field_match = re.match(r"- ([^:]+):\s*(.*)$", line)
        if field_match:
            if name is None:
                raise CodebookError(f"field line before any category header: {line!r}")
            label, value = field_match.group(1), field_match.group(2).strip()
            if label not in _FIELDS:
                raise CodebookError(f"category '{name}': unknown field {label!r}")
            if _FIELDS[label] in fields:
                raise CodebookError(f"category '{name}': duplicate field {label!r}")
            fields[_FIELDS[label]] = value
            current_field = _FIELDS[label]
        elif line.strip():
            if name is None or current_field is None:
                raise CodebookError(f"unexpected content outside a field: {line!r}")
            # Continuation of a wrapped field value.
            fields[current_field] = f"{fields[current_field]} {line.strip()}".strip()
    close_block()

    if not categories:
        raise CodebookError("categories.md contains no category blocks")
    empty = [(c.name, f) for c in categories for f in ("brief", "full", "when_1", "when_0", "example") if not getattr(c, f)]
    if empty:
        raise CodebookError(f"empty field value(s): {empty}")
    names = [c.name for c in categories]
    if len(set(names)) != len(names):
        raise CodebookError(f"duplicate category name(s) in categories.md: {sorted({n for n in names if names.count(n) > 1})}")
    return tuple(categories)


def _parse_themes(text: str, filename: str) -> tuple[str, ...]:
    themes = tuple(line.strip() for line in text.splitlines() if line.strip())
    if not themes:
        raise CodebookError(f"{filename} contains no themes")
    if len(set(themes)) != len(themes):
        raise CodebookError(f"duplicate theme(s) in {filename}: {sorted({t for t in themes if themes.count(t) > 1})}")
    return themes
