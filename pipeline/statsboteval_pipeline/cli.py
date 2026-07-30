"""Pipeline CLI. Thin slice: `python -m statsboteval_pipeline.cli run-synthetic ...`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from importlib.metadata import version
from pathlib import Path

from .aggregate import build_aggregates
from .contract import Aggregates
from .corpus import open_corpus
from .fixtures import SYNTHETIC_THEME_SET_VERSION, seed_synthetic, seed_synthetic_labels
from .labels import CURRENT_LABEL_VERSION
from .publish import publish, render


def build_parser() -> argparse.ArgumentParser:
    """Every subcommand and flag, kept out of main() so dispatch reads as dispatch."""
    parser = argparse.ArgumentParser(prog="statsboteval-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-synthetic", help="seed a fresh synthetic corpus, aggregate, guard, write/upload")
    run.add_argument("--corpus", type=Path, required=True, help="path for a FRESH DuckDB corpus file")
    # 40 weeks (~9 months) always spans at least two semesters whatever today's date is,
    # which is what gives the synthetic run a Trends section to publish (T-6). Shorter
    # axes still work; they just produce the no-predecessor empty state everywhere.
    run.add_argument("--weeks", type=int, default=40)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--floor-n", type=int, default=3)
    run.add_argument("--out", type=Path, help="write the guarded document to this file")
    run.add_argument("--upload", action="store_true", help="publish via $AZURE_STORAGE_CONNECTION_STRING")
    run.add_argument("--with-labels", action="store_true", help="seed synthetic labels + statuses so topics publishes")
    ext = sub.add_parser("extract", help="ingest new production rows into the local corpus (read-only source)")
    ext.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file (created if missing)")
    ext.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    lang = sub.add_parser("detect-language", help="label unlabeled messages locally (lang-heuristic-v1)")
    lang.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    wk = sub.add_parser(
        "run-weekly", help="extract -> detect-language -> aggregate (production) -> guard -> write/upload"
    )
    wk.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file (created if missing)")
    wk.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    wk.add_argument("--floor-n", type=int, default=3)
    wk.add_argument(
        "--axis-start",
        type=date.fromisoformat,
        default=date(2025, 3, 1),
        help="publish weeks from this date on (default: production launch; pilot rows stay corpus-only)",
    )
    wk.add_argument("--out", type=Path, help="write the guarded document to this file (operator review)")
    wk.add_argument("--upload", action="store_true", help="publish via $AZURE_STORAGE_CONNECTION_STRING")
    wk.add_argument("--skip-extract", action="store_true", help="publish the corpus as-is (no VPN/source connection)")
    wk.add_argument("--skip-classify", action="store_true", help="skip the classification pass (no Azure OpenAI)")
    wk.add_argument(
        "--classification-version",
        default=CURRENT_LABEL_VERSION,
        help=f"label version aggregated into topics (default: {CURRENT_LABEL_VERSION}; topics omitted "
        "while no such labels exist). Point at an older version to roll the dashboard back.",
    )
    pv = sub.add_parser(
        "preview-trends",
        help="print the full trends candidate table for a corpus — what published, what didn't, and why "
        "(read-only; no aggregation output, no blob, no publish)",
    )
    pv.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    pv.add_argument("--floor-n", type=int, default=3)
    pv.add_argument(
        "--axis-start",
        type=date.fromisoformat,
        default=date(2025, 3, 1),
        help="same default as run-weekly, so the preview sees the publishable range",
    )
    pv.add_argument(
        "--classification-version",
        default=CURRENT_LABEL_VERSION,
        help=f"label version behind topic candidates (default: {CURRENT_LABEL_VERSION})",
    )
    pv.add_argument("--window", help="restrict the table to one window id")
    cf = sub.add_parser("classify", help="run the LLM classification pass (deductive + frozen themes)")
    cf.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    cf.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    gt = sub.add_parser("generate-themes", help="emergent stages 1+2: candidate codes -> draft theme list to review")
    gt.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    gt.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    gt.add_argument("--draft", type=Path, help="draft file path (default: data/theme-draft-<set_version>.md)")
    ft = sub.add_parser("freeze-themes", help="load the REVIEWED draft into theme_sets, stamp reviewed_at (D-33)")
    ft.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    ft.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    ft.add_argument("--draft", type=Path, required=True, help="the reviewed draft file")
    ft.add_argument("--set-version", help="override $CLASSIFIER_THEME_SET_VERSION")
    at = sub.add_parser("assign-themes", help="assign the frozen emergent theme set (refuses an unreviewed set)")
    at.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    at.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    ib = sub.add_parser("import-bergmann", help="import the public Stage-2 coded dataset as bergmann-v1")
    ib.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    ib.add_argument("--csv", type=Path, required=True, help="git-ignored local full_dataset.csv")
    va = sub.add_parser("validate", help="per-category MCC of one of our label versions vs bergmann-v1")
    va.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    va.add_argument(
        "--label-version",
        default=CURRENT_LABEL_VERSION,
        help=f"which of our label versions to score (default: {CURRENT_LABEL_VERSION}); versions coexist, "
        "so run once per version to compare them on the same 300 consensus messages",
    )
    st = sub.add_parser("import-status", help="import the roster-derived status CSV (uids HMAC'd in flight)")
    st.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    st.add_argument("--csv", type=Path, help="override $STUDENT_STATUS_CSV")
    st.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    er = sub.add_parser("erase-student", help="erase one student from the corpus, re-aggregate, republish (guarded)")
    er.add_argument("--corpus", type=Path, required=True, help="DuckDB corpus file")
    er.add_argument("--uid", required=True, help="the student's source uid (normalized + HMAC'd, never stored)")
    er.add_argument("--env-file", type=Path, default=Path(".env"), help="settings file (default: ./.env)")
    er.add_argument("--floor-n", type=int, default=3)
    er.add_argument("--axis-start", type=date.fromisoformat, default=date(2025, 3, 1))
    er.add_argument("--log", type=Path, default=Path("data/erasure.log"), help="git-ignored local erasure log")
    er.add_argument("--out", type=Path, help="write the re-aggregated document to this file")
    er.add_argument("--upload", action="store_true", help="republish via $AZURE_STORAGE_CONNECTION_STRING")
    return parser


def _write_and_upload(
    payload: bytes,
    doc: Aggregates,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    verb: str,
) -> None:
    """Honor --out/--upload for an already-guarded payload (render() ran the guard)."""
    if args.out:
        args.out.write_bytes(payload)
        print(f"wrote {args.out}")
    if args.upload:
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            parser.error("--upload requires AZURE_STORAGE_CONNECTION_STRING in the environment")
        immutable, latest = publish(doc, connection_string=connection_string)
        print(f"{verb} {immutable} and {latest}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "erase-student":
        from .config import ExtractSettings
        from .erase import erase_student

        settings = ExtractSettings(_env_file=args.env_file)
        con = open_corpus(args.corpus)
        deleted = erase_student(con, args.uid, pepper=settings.pseudonym_pepper, log_path=args.log)
        if deleted is None:
            return 0  # warned no-op; nothing to republish
        print("erased: " + " ".join(f"{table}={n}" for table, n in deleted.items()))
        doc = build_aggregates(
            con,
            floor_n=args.floor_n,
            now=datetime.now(timezone.utc),
            provenance="production",
            pipeline_version=version("statsboteval-pipeline"),
            axis_start=args.axis_start,
        )
        _write_and_upload(render(doc), doc, args, parser, verb="republished")
        if not args.upload:
            print("NOTE: the erased student may still be reflected in the published blob until you republish")
        return 0

    if args.command == "run-weekly":
        from .config import ExtractSettings
        from .extract import connect_source, extract_new_rows
        from .language import detect_languages

        settings = ExtractSettings(_env_file=args.env_file)
        con = open_corpus(args.corpus)
        if args.skip_extract:
            n_new = 0
        else:
            source = connect_source(settings)
            try:
                n_new = extract_new_rows(con, source, pepper=settings.pseudonym_pepper)
            finally:
                source.close()
        n_labeled = detect_languages(con)
        from .classify.config import ThemeSettings
        from .themes import reviewed_theme_labels

        theme_set = ThemeSettings(_env_file=args.env_file).classifier_theme_set_version
        themes_frozen = reviewed_theme_labels(con, theme_set) is not None  # raises if unreviewed
        if args.skip_classify:
            n_classified = n_assigned = 0
        else:
            from .classify import step as classify_step

            n_classified = classify_step.run_classification(con, env_file=args.env_file)
            n_assigned = classify_step.run_theme_assignment(con, env_file=args.env_file) if themes_frozen else 0
        # theme_set_version documents the set behind emergent_themes, so it rides
        # along only when the aggregator will actually emit that distribution.
        has_emergent = (
            con.execute(
                "SELECT 1 FROM labels WHERE label_version = ? AND domain = 'emergent_theme' AND value = 1 LIMIT 1",
                [args.classification_version],
            ).fetchone()
            is not None
        )
        doc = build_aggregates(
            con,
            floor_n=args.floor_n,
            now=datetime.now(timezone.utc),
            provenance="production",
            pipeline_version=version("statsboteval-pipeline"),
            axis_start=args.axis_start,
            classification_version=args.classification_version,
            theme_set_version=theme_set if themes_frozen and has_emergent else None,
        )
        payload = render(doc)  # guard runs here, before anything is written or uploaded
        print(
            f"extracted {n_new} new messages; language-labeled {n_labeled}; classified {n_classified}; "
            f"assigned emergent themes for {n_assigned}; data through {doc.data_through_week}"
        )
        _write_and_upload(payload, doc, args, parser, verb="uploaded")
        if not args.out and not args.upload:
            print("guard OK; pass --out and/or --upload to emit the document")
        return 0

    if args.command == "preview-trends":
        # Read-only and local: no source connection, so no pepper interlock is involved.
        from .aggregate import DEDUCTIVE_LABELS, read_corpus_view
        from .trends import assess_windows, format_candidate_preview

        con = open_corpus(args.corpus)
        view = read_corpus_view(
            con,
            now=datetime.now(timezone.utc),
            axis_start=args.axis_start,
            classification_version=args.classification_version,
        )
        classified = any(view.positives[domain] for domain in view.positives)
        assessments = assess_windows(
            msgs=view.msgs,
            sessions=view.sessions,
            registrations=view.registrations,
            windows=view.windows,
            axis=view.axis,
            floor_n=args.floor_n,
            positives=view.positives if classified else None,
            deductive_labels=DEDUCTIVE_LABELS,
        )
        print(
            f"corpus {args.corpus}: {len(view.msgs)} messages, {len(view.sessions)} conversations, "
            f"weeks {view.first_week}..{view.through_week}"
            + ("" if classified else f"  (no {args.classification_version} labels — no topic candidates)")
        )
        print(format_candidate_preview(assessments, floor_n=args.floor_n, only_window=args.window))
        return 0

    if args.command == "import-status":
        from .config import StatusSettings
        from .status import import_status_csv

        status_settings = StatusSettings(_env_file=args.env_file)
        csv_path = args.csv or (
            Path(status_settings.student_status_csv) if status_settings.student_status_csv else None
        )
        if csv_path is None:
            parser.error("no CSV given: pass --csv or set STUDENT_STATUS_CSV in the env file")
        result = import_status_csv(open_corpus(args.corpus), csv_path, pepper=status_settings.pseudonym_pepper)
        print(f"imported {result.imported} status rows; {result.unmatched_corpus_students} corpus students unmatched")
        if result.unmatched_corpus_students:
            print("note: unmatched students aggregate as 'unknown' — refresh the roster derivation per semester")
        return 0

    if args.command == "detect-language":
        from .language import LABEL_VERSION, detect_languages

        n = detect_languages(open_corpus(args.corpus))
        print(f"labeled {n} messages with {LABEL_VERSION}")
        return 0

    if args.command == "classify":
        from .classify import step as classify_step

        n = classify_step.run_classification(open_corpus(args.corpus), env_file=args.env_file)
        print(f"classified {n} messages")
        return 0

    if args.command == "generate-themes":
        from .classify import step as classify_step
        from .classify.config import ThemeSettings

        set_version = ThemeSettings(_env_file=args.env_file).classifier_theme_set_version
        draft = args.draft or Path(f"data/theme-draft-{set_version}.md")
        processed, entries = classify_step.run_theme_generation(
            open_corpus(args.corpus), env_file=args.env_file, draft_path=draft
        )
        print(f"generated candidates for {processed} messages; synthesized {len(entries)} draft themes")
        print(f"REVIEW the draft before freezing (D-33 privacy control): {draft}")
        return 0

    if args.command == "freeze-themes":
        from .classify.config import ThemeSettings
        from .themes import freeze_theme_set, parse_theme_table

        set_version = args.set_version or ThemeSettings(_env_file=args.env_file).classifier_theme_set_version
        entries = parse_theme_table(args.draft.read_text())
        n = freeze_theme_set(open_corpus(args.corpus), entries, set_version, now=datetime.now(timezone.utc))
        print(f"froze {n} themes as {set_version} (reviewed_at stamped)")
        return 0

    if args.command == "assign-themes":
        from .classify import step as classify_step

        n = classify_step.run_theme_assignment(open_corpus(args.corpus), env_file=args.env_file)
        print(f"assigned emergent themes for {n} messages")
        return 0

    if args.command == "import-bergmann":
        from .import_bergmann import import_bergmann_v1

        n = import_bergmann_v1(open_corpus(args.corpus), args.csv)
        print(f"imported bergmann-v1 labels for {n} messages")
        return 0

    if args.command == "validate":
        from .validate import format_validation_report, validate_against_bergmann

        report = validate_against_bergmann(open_corpus(args.corpus), label_version=args.label_version)
        print(format_validation_report(report))
        return 0

    if args.command == "extract":
        from .config import ExtractSettings
        from .extract import connect_source, extract_new_rows

        settings = ExtractSettings(_env_file=args.env_file)
        con = open_corpus(args.corpus)
        source = connect_source(settings)
        try:
            n = extract_new_rows(con, source, pepper=settings.pseudonym_pepper)
        finally:
            source.close()
        print(f"ingested {n} new messages into {args.corpus}")
        return 0

    if args.corpus.exists():
        parser.error(f"{args.corpus} already exists; run-synthetic expects a fresh corpus file")
    con = open_corpus(args.corpus)
    seed_synthetic(con, weeks=args.weeks, seed=args.seed)
    if args.with_labels:
        seed_synthetic_labels(con, seed=args.seed)
    doc = build_aggregates(
        con,
        floor_n=args.floor_n,
        now=datetime.now(timezone.utc),
        provenance="synthetic",
        pipeline_version=version("statsboteval-pipeline"),
        classification_version=CURRENT_LABEL_VERSION if args.with_labels else None,
        theme_set_version=SYNTHETIC_THEME_SET_VERSION if args.with_labels else None,
    )
    payload = render(doc)
    _write_and_upload(payload, doc, args, parser, verb="uploaded")
    if not args.out and not args.upload:
        sys.stdout.write(payload.decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
