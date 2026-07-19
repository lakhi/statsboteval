"""Phase B Task 7: strict Markdown-table response parsing.

A silent mis-parse would corrupt labels, so every deviation raises
ClassifierParseError; only benign whitespace/pipe-padding is tolerated.
"""

import pytest

from statsboteval_pipeline.classify.parse import ClassifierParseError, parse_deductive, parse_themes

CATS = ["Synthetic Alpha", "Synthetic Beta"]

GOOD = """\
| Message | Synthetic Alpha | Synthetic Beta |
|---------|-----------------|----------------|
| 1 | 1 | 0 |
| 2 | 0 | 0 |
| 3 | 1 | 1 |
"""


def test_good_table_parses_to_matrix() -> None:
    got = parse_deductive(GOOD, CATS, 3)
    assert got == [
        {"Synthetic Alpha": 1, "Synthetic Beta": 0},
        {"Synthetic Alpha": 0, "Synthetic Beta": 0},
        {"Synthetic Alpha": 1, "Synthetic Beta": 1},
    ]


def test_surrounding_prose_is_ignored() -> None:
    text = f"Here is the coding table:\n\n{GOOD}\nAll messages coded."
    assert parse_deductive(text, CATS, 3) == parse_deductive(GOOD, CATS, 3)


def test_ragged_whitespace_and_message_prefix_parse() -> None:
    text = (
        "|Message|  Synthetic Alpha |Synthetic Beta|\n"
        "|---|---|---|\n"
        "|  Message 1 |1| 0|\n"
        "| 2   |  0 |0 |\n"
    )
    assert parse_deductive(text, CATS, 2) == [
        {"Synthetic Alpha": 1, "Synthetic Beta": 0},
        {"Synthetic Alpha": 0, "Synthetic Beta": 0},
    ]


def test_row_order_independence() -> None:
    shuffled = GOOD.replace("| 1 | 1 | 0 |\n| 2 | 0 | 0 |", "| 2 | 0 | 0 |\n| 1 | 1 | 0 |")
    assert parse_deductive(shuffled, CATS, 3) == parse_deductive(GOOD, CATS, 3)


def test_missing_row_raises() -> None:
    with pytest.raises(ClassifierParseError, match=r"missing messages \[4\]"):
        parse_deductive(GOOD, CATS, 4)


def test_duplicate_row_raises() -> None:
    text = GOOD + "| 3 | 0 | 0 |\n"
    with pytest.raises(ClassifierParseError, match="[Dd]uplicate"):
        parse_deductive(text, CATS, 3)


def test_wrong_header_raises() -> None:
    with pytest.raises(ClassifierParseError, match="header"):
        parse_deductive(GOOD.replace("Synthetic Beta", "Synthetic Delta"), CATS, 3)


def test_extra_column_raises() -> None:
    text = GOOD.replace("| 2 | 0 | 0 |", "| 2 | 0 | 0 | 1 |")
    with pytest.raises(ClassifierParseError, match=r"\| 2 \|"):
        parse_deductive(text, CATS, 3)


def test_non_binary_value_raises() -> None:
    text = GOOD.replace("| 2 | 0 | 0 |", "| 2 | yes | 0 |")
    with pytest.raises(ClassifierParseError, match="yes"):
        parse_deductive(text, CATS, 3)


def test_non_numeric_message_id_raises() -> None:
    text = GOOD.replace("| 2 | 0 | 0 |", "| two | 0 | 0 |")
    with pytest.raises(ClassifierParseError, match="two"):
        parse_deductive(text, CATS, 3)


def test_no_table_raises() -> None:
    with pytest.raises(ClassifierParseError, match="table"):
        parse_deductive("I could not code these messages.", CATS, 3)


THEMES = ["synthetic method one", "synthetic method two"]

GOOD_THEMES = """\
| Message | Labels |
|---|---|
| 1 | 1 |
| 2 | none |
| 3 | 1; 2 |
"""


def test_good_theme_table_parses() -> None:
    assert parse_themes(GOOD_THEMES, THEMES, 3) == [
        {"synthetic method one"},
        set(),
        {"synthetic method one", "synthetic method two"},
    ]


def test_out_of_range_theme_number_raises() -> None:
    text = GOOD_THEMES.replace("| 2 | none |", "| 2 | 3 |")
    with pytest.raises(ClassifierParseError, match=r"'3'"):
        parse_themes(text, THEMES, 3)


def test_theme_name_instead_of_number_raises() -> None:
    # The model must answer with list numbers; names (or commentary) are rejected.
    text = GOOD_THEMES.replace("| 2 | none |", "| 2 | synthetic method one |")
    with pytest.raises(ClassifierParseError, match="synthetic method one"):
        parse_themes(text, THEMES, 3)


def test_theme_missing_row_raises() -> None:
    with pytest.raises(ClassifierParseError, match=r"missing messages \[4\]"):
        parse_themes(GOOD_THEMES, THEMES, 4)


def test_theme_case_of_none_is_tolerated() -> None:
    text = GOOD_THEMES.replace("| 2 | none |", "| 2 | None |")
    assert parse_themes(text, THEMES, 3)[1] == set()


def test_theme_empty_cell_raises() -> None:
    text = GOOD_THEMES.replace("| 2 | none |", "| 2 |  |")
    with pytest.raises(ClassifierParseError):
        parse_themes(text, THEMES, 3)
