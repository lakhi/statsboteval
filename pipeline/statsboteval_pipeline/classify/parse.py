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
    """Parse a numeric label-assignment table into one set of allowed labels per message.

    Cells carry semicolon-separated label numbers (1-based into `allowed`) or "none";
    anything else — names, commentary, out-of-range numbers — raises.
    """
    rows = _table_rows(text, expected_columns=["Labels"], n=n)
    result: list[set[str]] = []
    for number in range(1, n + 1):
        cells, raw = rows[number]
        cell = cells[0]
        if cell.lower() == "none":
            result.append(set())
            continue
        tokens = [part.strip() for part in cell.split(";")]
        if not tokens or "" in tokens:
            raise ClassifierParseError(f"empty label in row: {raw}")
        labels: set[str] = set()
        for token in tokens:
            if not token.isdigit() or not 1 <= int(token) <= len(allowed):
                raise ClassifierParseError(
                    f"label token {token!r} is not a number from the list (1..{len(allowed)}) in row: {raw}"
                )
            labels.add(allowed[int(token) - 1])
        result.append(labels)
    return result


_CANDIDATE_MAX_WORDS = 5
_CANDIDATE_MAX_CHARS = 60


def parse_candidates(text: str, n: int) -> list[list[str]]:
    """Parse a candidate-code table into one normalized code list per message.

    Codes are free text (unlike theme numbers), so validation is structural:
    non-empty, short (<=5 words / 60 chars — long cells smell like quoted chat
    text), normalized to lowercase with collapsed whitespace, deduplicated.
    """
    rows = _table_rows(text, expected_columns=["Codes"], n=n)
    result: list[list[str]] = []
    for number in range(1, n + 1):
        cells, raw = rows[number]
        cell = cells[0]
        if cell.lower() == "none":
            result.append([])
            continue
        codes: list[str] = []
        for part in cell.split(";"):
            code = " ".join(part.lower().split())
            if not code:
                raise ClassifierParseError(f"empty code in row: {raw}")
            if len(code.split()) > _CANDIDATE_MAX_WORDS or len(code) > _CANDIDATE_MAX_CHARS:
                raise ClassifierParseError(
                    f"code {code!r} exceeds {_CANDIDATE_MAX_WORDS} words/{_CANDIDATE_MAX_CHARS} chars in row: {raw}"
                )
            if code not in codes:
                codes.append(code)
        result.append(codes)
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
