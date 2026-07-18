"""Prompt builders: consolidated multi-label deductive + theme assignment (D-30).

One deductive call covers a whole category group (all 13 by default) over a batch
of ≤50 messages — departing from Bergmann's one-category-per-prompt (recorded as a
validation caveat). The category→call grouping is a parameter so a fragile
category can later be split into its own call without a rewrite. Static codebook
content renders first and the messages last (prompt-cache friendly).
"""

from __future__ import annotations

from collections.abc import Sequence

from statsboteval_pipeline.classify.codebook import Category, Codebook

# Bergmann's validation fixed 50 messages/prompt (50 beat 100 for GPT-4o, kept for GPT-5).
BATCH_LIMIT = 50


def build_deductive_prompt(
    codebook: Codebook, batch: Sequence[str], *, categories: Sequence[Category] | None = None
) -> str:
    cats = tuple(categories) if categories is not None else codebook.categories
    if not cats:
        raise ValueError("no categories to code")
    _check_batch(batch)
    n = len(batch)
    names = [c.name for c in cats]
    blocks = "\n\n".join(
        f"### {c.name}\n"
        f"- Brief: {c.brief}\n"
        f"- Full: {c.full}\n"
        f"- Code 1: {c.when_1}\n"
        f"- Code 0: {c.when_0}\n"
        f"- Example for Yes: {c.example}"
        for c in cats
    )
    header = " | ".join(names)
    example_row = " | ".join(["1"] + ["0"] * (len(names) - 1))
    return (
        "You are an experienced qualitative coder. First, review the codebook below. Then read the "
        f"{n} provided chat messages and decide, for each message and for EACH of the {len(cats)} "
        "categories, whether the message falls into that category (code 1) or not (code 0).\n\n"
        "Each codebook entry lists the category name, Brief Definition, Full Definition, when to "
        "code 1 (yes), when to code 0 (no), and an example for yes.\n\n"
        f"Codebook:\n\n{blocks}\n\n"
        "Output exactly one Markdown table with one row per message. The first column is the "
        f"message number (1..{n}); the remaining columns are the categories in exactly this "
        f"order: {header}. Every value must be 0 or 1 — no other text, no omitted rows.\n"
        "Example:\n"
        f"| Message | {header} |\n"
        f"|{'---|' * (len(names) + 1)}\n"
        f"| 1 | {example_row} |\n\n"
        f"Here are the {n} chat messages:\n\n"
        f"{_render_messages(batch)}"
    )


def build_theme_prompt(themes: Sequence[str], batch: Sequence[str], domain: str) -> str:
    """Assign each message zero-or-more labels from a fixed list (frozen or generated set)."""
    if not themes:
        raise ValueError("no themes to assign")
    _check_batch(batch)
    n = len(batch)
    listing = "\n".join(f"- {t}" for t in themes)
    return (
        "You are an experienced qualitative coder. Read the chat messages below and assign each "
        f"message to zero or more {domain} from the given list. Use ONLY labels from the list, "
        "spelled exactly as given; assign a label only when the message clearly matches it.\n\n"
        f"The list of {domain}:\n{listing}\n\n"
        "Output exactly one Markdown table with one row per message. The first column is the "
        f"message number (1..{n}); the second column is a semicolon-separated list of assigned "
        'labels, or the single word "none" if no label applies. No other text.\n'
        "Example:\n"
        "| Message | Labels |\n"
        "|---|---|\n"
        f"| 1 | {themes[0]} |\n"
        "| 2 | none |\n\n"
        f"Here are the {n} chat messages:\n\n"
        f"{_render_messages(batch)}"
    )


def _check_batch(batch: Sequence[str]) -> None:
    if not batch:
        raise ValueError("empty message batch")
    if len(batch) > BATCH_LIMIT:
        raise ValueError(f"batch of {len(batch)} exceeds the limit of {BATCH_LIMIT} messages per call")


def _render_messages(batch: Sequence[str]) -> str:
    return "\n\n".join(f'Message {i}:\n"""\n{text}\n"""' for i, text in enumerate(batch, start=1))
