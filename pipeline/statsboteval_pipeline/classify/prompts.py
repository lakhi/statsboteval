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
    """Assign each message zero-or-more labels from a fixed numbered list.

    The model answers with label NUMBERS, not names — exact-string echoes of long
    labels proved fragile in practice (the model paraphrases or annotates them);
    numbers keep the frozen list authoritative on our side.
    """
    if not themes:
        raise ValueError("no themes to assign")
    _check_batch(batch)
    n = len(batch)
    listing = "\n".join(f"{i}. {t}" for i, t in enumerate(themes, start=1))
    example_cell = "1" if len(themes) == 1 else f"1; {len(themes)}"
    return (
        "You are an experienced qualitative coder. Read the chat messages below and assign each "
        f"message to zero or more {domain} from the given numbered list; assign a label only "
        "when the message clearly matches it.\n\n"
        f"The numbered list of {domain}:\n{listing}\n\n"
        "Output exactly one Markdown table with one row per message. The first column is the "
        f"message number (1..{n}); the second column is a semicolon-separated list of the "
        f"NUMBERS of the assigned labels (1..{len(themes)}), or the single word \"none\" if no "
        "label applies. Output numbers only — never label names, never commentary.\n"
        "Example:\n"
        "| Message | Labels |\n"
        "|---|---|\n"
        f"| 1 | {example_cell} |\n"
        "| 2 | none |\n\n"
        f"Here are the {n} chat messages:\n\n"
        f"{_render_messages(batch)}"
    )


def build_candidate_prompt(batch: Sequence[str]) -> str:
    """Stage 1 of the emergent pass (D-33): short candidate codes per message.

    Codes must be generic and non-identifying — the instruction matters because
    everything generated here derives from real chat text; the parser enforces
    shape and the operator review of the synthesized list is the final control.
    """
    _check_batch(batch)
    n = len(batch)
    return (
        "You are an experienced qualitative coder performing open coding. Read the chat messages "
        "below — students in a university statistics course talking to an AI assistant — and give "
        "each message 1 to 3 short candidate codes capturing what the message is about.\n\n"
        "Rules for codes:\n"
        "- English, lowercase, at most 5 words each.\n"
        "- Generic topic wording only — never names, never verbatim quotes, never message-specific "
        "details (numbers, datasets, titles) that could identify a person or a piece of work.\n"
        "- Messages in other languages still get English codes.\n"
        "- Use the single word \"none\" for messages with no codable content.\n\n"
        "Output exactly one Markdown table with one row per message. The first column is the "
        f"message number (1..{n}); the second column is a semicolon-separated list of the codes, "
        "or \"none\". No other text.\n"
        "Example:\n"
        "| Message | Codes |\n"
        "|---|---|\n"
        "| 1 | interpreting regression output; asking for examples |\n"
        "| 2 | none |\n\n"
        f"Here are the {n} chat messages:\n\n"
        f"{_render_messages(batch)}"
    )


def build_synthesis_prompt(code_frequencies: Sequence[tuple[str, int]], *, target: tuple[int, int] = (12, 20)) -> str:
    """Stage 2 of the emergent pass: consolidate candidate codes into draft themes.

    Input is the distinct candidate-code list with frequencies — codes only, no
    chat text is re-sent (asserted in tests). The output table becomes the
    operator's review draft, never a published list directly.
    """
    if not code_frequencies:
        raise ValueError("no candidate codes to synthesize")
    lo, hi = target
    listing = "\n".join(f"- {code} ({count})" for code, count in code_frequencies)
    return (
        "You are an experienced qualitative coder. Below are candidate codes from open coding of "
        "chat messages by students in a university statistics course, each with its frequency. "
        f"Consolidate them into roughly {lo}-{hi} themes covering the codes' content.\n\n"
        "Rules for themes:\n"
        "- Short generic English labels (at most 6 words) with a one-line description each.\n"
        "- No names, no identifying specifics; merge near-duplicates; drop codes too rare or too "
        "vague to form a theme.\n\n"
        "Output exactly one Markdown table, one row per theme, no other text:\n"
        "| Theme | Description |\n"
        "|---|---|\n\n"
        f"The candidate codes:\n{listing}"
    )


def _check_batch(batch: Sequence[str]) -> None:
    if not batch:
        raise ValueError("empty message batch")
    if len(batch) > BATCH_LIMIT:
        raise ValueError(f"batch of {len(batch)} exceeds the limit of {BATCH_LIMIT} messages per call")


def _render_messages(batch: Sequence[str]) -> str:
    return "\n\n".join(f'Message {i}:\n"""\n{text}\n"""' for i, text in enumerate(batch, start=1))
