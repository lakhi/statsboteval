"""Pipeline CLI. Thin slice: `python -m statsboteval_pipeline.cli run-synthetic ...`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from importlib.metadata import version
from pathlib import Path

from .aggregate import build_aggregates
from .corpus import open_corpus
from .fixtures import seed_synthetic
from .publish import publish, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="statsboteval-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-synthetic", help="seed a fresh synthetic corpus, aggregate, guard, write/upload")
    run.add_argument("--corpus", type=Path, required=True, help="path for a FRESH DuckDB corpus file")
    run.add_argument("--weeks", type=int, default=8)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--floor-n", type=int, default=3)
    run.add_argument("--out", type=Path, help="write the guarded document to this file")
    run.add_argument("--upload", action="store_true", help="publish via $AZURE_STORAGE_CONNECTION_STRING")
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
        payload = render(doc)
        if args.out:
            args.out.write_bytes(payload)
            print(f"wrote {args.out}")
        if args.upload:
            connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            if not connection_string:
                parser.error("--upload requires AZURE_STORAGE_CONNECTION_STRING in the environment")
            immutable, latest = publish(doc, connection_string=connection_string)
            print(f"republished {immutable} and {latest}")
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
        doc = build_aggregates(
            con,
            floor_n=args.floor_n,
            now=datetime.now(timezone.utc),
            provenance="production",
            pipeline_version=version("statsboteval-pipeline"),
            axis_start=args.axis_start,
        )
        payload = render(doc)  # guard runs here, before anything is written or uploaded
        print(f"extracted {n_new} new messages; labeled {n_labeled}; data through {doc.data_through_week}")
        if args.out:
            args.out.write_bytes(payload)
            print(f"wrote {args.out}")
        if args.upload:
            connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            if not connection_string:
                parser.error("--upload requires AZURE_STORAGE_CONNECTION_STRING in the environment")
            immutable, latest = publish(doc, connection_string=connection_string)
            print(f"uploaded {immutable} and {latest}")
        if not args.out and not args.upload:
            print("guard OK; pass --out and/or --upload to emit the document")
        return 0

    if args.command == "import-status":
        from .config import StatusSettings
        from .status import import_status_csv

        status_settings = StatusSettings(_env_file=args.env_file)
        csv_path = args.csv or (Path(status_settings.student_status_csv) if status_settings.student_status_csv else None)
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
    doc = build_aggregates(
        con,
        floor_n=args.floor_n,
        now=datetime.now(timezone.utc),
        provenance="synthetic",
        pipeline_version=version("statsboteval-pipeline"),
    )
    payload = render(doc)
    if args.out:
        args.out.write_bytes(payload)
        print(f"wrote {args.out}")
    if args.upload:
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            parser.error("--upload requires AZURE_STORAGE_CONNECTION_STRING in the environment")
        immutable, latest = publish(doc, connection_string=connection_string)
        print(f"uploaded {immutable} and {latest}")
    if not args.out and not args.upload:
        sys.stdout.write(payload.decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
