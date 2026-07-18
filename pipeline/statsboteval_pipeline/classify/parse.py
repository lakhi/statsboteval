"""Strict parsing of classifier Markdown-table responses.

Silent mis-parses would corrupt labels, so every structural deviation raises
ClassifierParseError carrying the offending row. Tolerated: surrounding prose
outside the table, ragged whitespace/pipe-padding, a "Message N" prefix in the
number column, and row order (rows are keyed by message number, not position).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_ROW_ID = re.compile(r"^(?:Message\s+)?(\d+)$", re.IGNORECASE)


class ClassifierParseError(ValueError):
    """The model response deviates from the requested table format."""


def parse_deductive(text: str, categories: Sequence[str], n: int) -> list[dict[str, int]]:
    """Parse a binary coding table into one {category: 0|1} dict per message, ordered 1..n."""
    rows = _table_rows(text, expected_columns=list(categories), n=n)
    matrix: list[dict[str, int]] = []
    for number in range(1, n + 1):
        cells, raw = rows[number]
        coded: dict[str, int] = {}
        for category, cell in zip(categories, cells, strict=True):
            if cell not in ("0", "1"):
                raise ClassifierParseError(f"non-binary value {cell!r} in row: {raw}")
            coded[category] = int(cell)
        matrix.append(coded)
    return matrix


def parse_themes(text: str, allowed: Sequence[str], n: int) -> list[set[str]]:
    """Parse a label-assignment table into one set of allowed labels per message, ordered 1..n."""
    rows = _table_rows(text, expected_columns=["Labels"], n=n)
    allowed_set = set(allowed)
    result: list[set[str]] = []
    for number in range(1, n + 1):
        cells, raw = rows[number]
        cell = cells[0]
        if cell.lower() == "none":
            result.append(set())
            continue
        labels = {part.strip() for part in cell.split(";")}
        if not labels or "" in labels:
            raise ClassifierParseError(f"empty label in row: {raw}")
        unknown = labels - allowed_set
        if unknown:
            raise ClassifierParseError(f"label(s) not in the allowed list {sorted(unknown)} in row: {raw}")
        result.append(labels)
    return result


def _table_rows(text: str, *, expected_columns: list[str], n: int) -> dict[int, tuple[list[str], str]]:
    """Extract table rows keyed by message number; validate header, count, and width."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if not lines:
        raise ClassifierParseError("no Markdown table found in the response")

    header = _cells(lines[0])
    if len(header) != len(expected_columns) + 1 or header[1:] != expected_columns:
        raise ClassifierParseError(f"unexpected table header: {lines[0]} (expected columns {expected_columns})")

    rows: dict[int, tuple[list[str], str]] = {}
    for raw in lines[1:]:
        cells = _cells(raw)
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue  # separator line
        id_match = _ROW_ID.match(cells[0])
        if not id_match:
            raise ClassifierParseError(f"unparseable message number in row: {raw}")
        number = int(id_match.group(1))
        if number in rows:
            raise ClassifierParseError(f"duplicate row for message {number}: {raw}")
        if len(cells) != len(expected_columns) + 1:
            raise ClassifierParseError(f"expected {len(expected_columns) + 1} columns in row: {raw}")
        rows[number] = (cells[1:], raw)

    expected_ids = set(range(1, n + 1))
    if set(rows) != expected_ids:
        missing = sorted(expected_ids - set(rows))
        extra = sorted(set(rows) - expected_ids)
        raise ClassifierParseError(f"row set mismatch (missing messages {missing}, unexpected {extra})")
    return rows


def _cells(line: str) -> list[str]:
    parts = [cell.strip() for cell in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts
