"""Local language detection -> lang-heuristic-v1 labels (Phase A language tab).

Runs entirely on this machine; no chat text leaves it. Codes: de / en / other /
undetermined. Very short or low-confidence inputs are undetermined (the
registered `language_heuristic` footnote). The detector set is broad enough
that `other` is reachable, but not all 75 lingua languages — German/English
plus languages plausibly typed by students in Vienna.
"""

from __future__ import annotations

import duckdb
from lingua import Language, LanguageDetector, LanguageDetectorBuilder

from .labels import LabelRow, write_labels

LABEL_VERSION = "lang-heuristic-v1"
DOMAIN = "language"
PROVENANCE = "lingua-py"

MIN_CHARS = 10  # shorter inputs carry too little signal
MIN_CONFIDENCE = 0.6

_LANGUAGES = [
    Language.GERMAN,
    Language.ENGLISH,
    Language.FRENCH,
    Language.SPANISH,
    Language.ITALIAN,
    Language.PORTUGUESE,
    Language.DUTCH,
    Language.POLISH,
    Language.CZECH,
    Language.SLOVAK,
    Language.HUNGARIAN,
    Language.ROMANIAN,
    Language.CROATIAN,
    Language.BOSNIAN,
    Language.SERBIAN,
    Language.TURKISH,
    Language.RUSSIAN,
    Language.UKRAINIAN,
]


def build_detector() -> LanguageDetector:
    return LanguageDetectorBuilder.from_languages(*_LANGUAGES).build()


def classify_text(detector: LanguageDetector, text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) < MIN_CHARS:
        return "undetermined"
    confidences = detector.compute_language_confidence_values(normalized)
    if not confidences or confidences[0].value < MIN_CONFIDENCE:
        return "undetermined"
    top = confidences[0].language
    if top == Language.GERMAN:
        return "de"
    if top == Language.ENGLISH:
        return "en"
    return "other"


def detect_languages(con: duckdb.DuckDBPyConnection) -> int:
    """Label every not-yet-labeled message; returns how many were labeled (idempotent)."""
    rows = con.execute(
        "SELECT m.history_id, m.sent FROM messages m "
        "WHERE NOT EXISTS (SELECT 1 FROM labels l WHERE l.history_id = m.history_id "
        "  AND l.label_version = ? AND l.domain = ?) "
        "ORDER BY m.history_id",
        [LABEL_VERSION, DOMAIN],
    ).fetchall()
    if not rows:
        return 0
    detector = build_detector()
    write_labels(
        con,
        [
            LabelRow(history_id, LABEL_VERSION, DOMAIN, classify_text(detector, sent), 1, PROVENANCE)
            for history_id, sent in rows
        ],
    )
    return len(rows)
