"""GL3: local language detection -> lang-heuristic-v1 labels (synthetic strings only)."""

from pathlib import Path

import pytest

from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.labels import read_labels
from statsboteval_pipeline.language import LABEL_VERSION, build_detector, classify_text, detect_languages

GERMAN = "Wie berechne ich bitte den Mittelwert und die Standardabweichung in SPSS?"
ENGLISH = "How do I compute the mean and the standard deviation for my dataset?"
FRENCH = "Bonjour, pouvez-vous m'expliquer comment calculer la moyenne de mes données ?"


@pytest.fixture(scope="module")
def detector():
    return build_detector()


def test_clear_german_is_de(detector) -> None:
    assert classify_text(detector, GERMAN) == "de"


def test_clear_english_is_en(detector) -> None:
    assert classify_text(detector, ENGLISH) == "en"


def test_third_language_is_other(detector) -> None:
    assert classify_text(detector, FRENCH) == "other"


def test_short_input_is_undetermined(detector) -> None:
    assert classify_text(detector, "ok") == "undetermined"
    assert classify_text(detector, "  ja   \n ") == "undetermined"


def seed(con) -> None:
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 09:00:00')")
    rows = [
        (1, "syn-0001", 1000, "2025-03-03 10:00:00", GERMAN, "answer", 10, 20),
        (2, "syn-0001", 1000, "2025-03-03 10:05:00", ENGLISH, "answer", 10, 20),
        (3, "syn-0001", 2000, "2025-03-04 10:00:00", "ok", "answer", 10, 20),
    ]
    con.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


def test_detect_languages_writes_versioned_labels(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con)
    assert detect_languages(con) == 3
    got = read_labels(con, LABEL_VERSION)
    assert [(r.history_id, r.domain, r.code, r.value) for r in got] == [
        (1, "language", "de", 1),
        (2, "language", "en", 1),
        (3, "language", "undetermined", 1),
    ]


def test_detect_languages_is_idempotent(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con)
    detect_languages(con)
    assert detect_languages(con) == 0  # already labeled: nothing re-detected
    assert len(read_labels(con, LABEL_VERSION)) == 3


def test_new_messages_get_labeled_on_rerun(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con)
    detect_languages(con)
    con.execute("INSERT INTO messages VALUES (4, 'syn-0001', 3000, '2025-03-05 10:00:00', ?, 'a', 10, 20)", [FRENCH])
    assert detect_languages(con) == 1
    got = {r.history_id: r.code for r in read_labels(con, LABEL_VERSION)}
    assert got[4] == "other"
