"""Phase B Task 6: consolidated multi-label + theme-assignment prompt builders."""

import pytest

from statsboteval_pipeline.classify.codebook import synthetic_codebook
from statsboteval_pipeline.classify.prompts import (
    BATCH_LIMIT,
    build_deductive_prompt,
    build_theme_prompt,
)

BATCH = ["What is an ANOVA?", "Danke!", "Show me R code for a t-test."]


def test_deterministic_render() -> None:
    cb = synthetic_codebook()
    assert build_deductive_prompt(cb, BATCH) == build_deductive_prompt(cb, BATCH)
    themes = cb.method_themes
    assert build_theme_prompt(themes, BATCH, "statistics methods") == build_theme_prompt(
        themes, BATCH, "statistics methods"
    )


def test_all_category_headers_and_column_order_present() -> None:
    cb = synthetic_codebook()
    prompt = build_deductive_prompt(cb, BATCH)
    for cat in cb.categories:
        assert f"### {cat.name}" in prompt
        assert cat.full in prompt
    # The requested column order names every category once, in codebook order.
    header = " | ".join(c.name for c in cb.categories)
    assert header in prompt


def test_message_numbering_is_1_to_n() -> None:
    prompt = build_deductive_prompt(synthetic_codebook(), BATCH)
    for i, text in enumerate(BATCH, start=1):
        assert f"Message {i}:" in prompt
        assert text in prompt
    assert f"Message {len(BATCH) + 1}:" not in prompt


def test_codebook_precedes_messages() -> None:
    # Static content first, messages last — prompt-cache friendly (D-30).
    cb = synthetic_codebook()
    prompt = build_deductive_prompt(cb, BATCH)
    assert prompt.index(cb.categories[-1].full) < prompt.index("Message 1:")


def test_category_grouping_parameter_selects_subset() -> None:
    cb = synthetic_codebook()
    subset = cb.categories[:2]
    prompt = build_deductive_prompt(cb, BATCH, categories=subset)
    assert f"### {subset[0].name}" in prompt
    assert f"### {cb.categories[2].name}" not in prompt


def test_over_batch_limit_raises() -> None:
    cb = synthetic_codebook()
    with pytest.raises(ValueError, match=str(BATCH_LIMIT)):
        build_deductive_prompt(cb, ["m"] * (BATCH_LIMIT + 1))
    with pytest.raises(ValueError, match=str(BATCH_LIMIT)):
        build_theme_prompt(cb.method_themes, ["m"] * (BATCH_LIMIT + 1), "statistics methods")


def test_empty_batch_raises() -> None:
    cb = synthetic_codebook()
    with pytest.raises(ValueError):
        build_deductive_prompt(cb, [])
    with pytest.raises(ValueError):
        build_theme_prompt(cb.method_themes, [], "statistics methods")


def test_theme_prompt_embeds_list_verbatim_and_domain() -> None:
    cb = synthetic_codebook()
    prompt = build_theme_prompt(cb.software_themes, BATCH, "data analysis software")
    for theme in cb.software_themes:
        assert f"- {theme}" in prompt
    assert "data analysis software" in prompt
    assert "Message 1:" in prompt


def test_empty_theme_list_raises() -> None:
    with pytest.raises(ValueError):
        build_theme_prompt((), BATCH, "statistics methods")
