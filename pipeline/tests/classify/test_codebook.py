"""Phase B Task 5: codebook + frozen theme-list loading.

All materials constructed here are SYNTHETIC — the real Bergmann definitions are
git-ignored local files (D-16) and never appear in tests.
"""

from pathlib import Path

import pytest

from statsboteval_pipeline.classify.codebook import (
    DEDUCTIVE_CATEGORY_NAMES,
    Codebook,
    CodebookError,
    category_code,
    load_codebook,
    synthetic_codebook,
)


def write_materials(directory: Path, codebook: Codebook) -> None:
    """Materialize a codebook into the on-disk layout `load_codebook` expects."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "wrapper.txt").write_text(codebook.wrapper, encoding="utf-8")
    blocks = []
    for cat in codebook.categories:
        blocks.append(
            f"## {cat.name}\n"
            f"- Brief: {cat.brief}\n"
            f"- Full: {cat.full}\n"
            f"- Code 1: {cat.when_1}\n"
            f"- Code 0: {cat.when_0}\n"
            f"- Example: {cat.example}\n"
        )
    (directory / "categories.md").write_text("\n".join(blocks), encoding="utf-8")
    (directory / "method_themes.txt").write_text("\n".join(codebook.method_themes) + "\n", encoding="utf-8")
    (directory / "software_themes.txt").write_text("\n".join(codebook.software_themes) + "\n", encoding="utf-8")


def test_synthetic_codebook_well_formed() -> None:
    cb = synthetic_codebook()
    assert cb.wrapper
    assert len(cb.categories) >= 2
    for cat in cb.categories:
        assert cat.name and cat.brief and cat.full and cat.when_1 and cat.when_0 and cat.example
        assert cat.code == category_code(cat.name)
        assert "synthetic" in cat.full.lower()  # never real definitions
    assert cb.method_themes and cb.software_themes
    assert len({c.code for c in cb.categories}) == len(cb.categories)


def test_category_code_slug() -> None:
    assert category_code("Statistics Interaction") == "statistics_interaction"
    assert category_code("Reference to a Prior Content") == "reference_to_a_prior_content"


def test_load_round_trips_synthetic_materials(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb)
    loaded = load_codebook(tmp_path)
    assert loaded == cb


def test_all_13_real_names_load_with_synthetic_definitions(tmp_path: Path) -> None:
    # The 13 names are public (Stage-2 manuscript); definitions here are synthetic.
    assert len(DEDUCTIVE_CATEGORY_NAMES) == 13
    base = synthetic_codebook()
    cats = tuple(
        base.categories[0]._replace(name=name, code=category_code(name)) for name in DEDUCTIVE_CATEGORY_NAMES
    )
    write_materials(tmp_path, base._replace(categories=cats))
    loaded = load_codebook(tmp_path, expected_categories=DEDUCTIVE_CATEGORY_NAMES)
    assert [c.name for c in loaded.categories] == list(DEDUCTIVE_CATEGORY_NAMES)
    assert "statistics_interaction" in {c.code for c in loaded.categories}


def test_expected_categories_mismatch_raises(tmp_path: Path) -> None:
    write_materials(tmp_path, synthetic_codebook())
    with pytest.raises(CodebookError, match="Statistics Interaction"):
        load_codebook(tmp_path, expected_categories=DEDUCTIVE_CATEGORY_NAMES)


def test_missing_field_raises(tmp_path: Path) -> None:
    write_materials(tmp_path, synthetic_codebook())
    text = (tmp_path / "categories.md").read_text(encoding="utf-8")
    (tmp_path / "categories.md").write_text(text.replace("- Full: ", "- Fool: ", 1), encoding="utf-8")
    with pytest.raises(CodebookError):
        load_codebook(tmp_path)


def test_duplicate_field_raises(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb)
    path = tmp_path / "categories.md"
    first = cb.categories[0]
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f"- Brief: {first.brief}\n", f"- Brief: {first.brief}\n- Brief: again\n", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(CodebookError, match="[Dd]uplicate"):
        load_codebook(tmp_path)


def test_empty_field_value_raises(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb)
    path = tmp_path / "categories.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(f"- Example: {cb.categories[0].example}", "- Example:"),
        encoding="utf-8",
    )
    with pytest.raises(CodebookError):
        load_codebook(tmp_path)


def test_duplicate_category_name_raises(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb._replace(categories=(cb.categories[0], cb.categories[0])))
    with pytest.raises(CodebookError, match="[Dd]uplicate"):
        load_codebook(tmp_path)


def test_wrapped_field_lines_join(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb)
    path = tmp_path / "categories.md"
    first = cb.categories[0]
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f"- Full: {first.full}\n", "- Full: a definition that\n  wraps across lines\n", 1
        ),
        encoding="utf-8",
    )
    loaded = load_codebook(tmp_path)
    assert loaded.categories[0].full == "a definition that wraps across lines"


def test_empty_theme_list_raises(tmp_path: Path) -> None:
    write_materials(tmp_path, synthetic_codebook())
    (tmp_path / "method_themes.txt").write_text("\n", encoding="utf-8")
    with pytest.raises(CodebookError, match="method_themes"):
        load_codebook(tmp_path)


def test_duplicate_theme_raises(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    write_materials(tmp_path, cb)
    (tmp_path / "software_themes.txt").write_text(
        "\n".join(cb.software_themes + (cb.software_themes[0],)) + "\n", encoding="utf-8"
    )
    with pytest.raises(CodebookError, match="[Dd]uplicate"):
        load_codebook(tmp_path)


def test_missing_directory_raises_clearly(tmp_path: Path) -> None:
    with pytest.raises(CodebookError, match="BERGMANN_PROMPTS_DIR"):
        load_codebook(tmp_path / "nope")
