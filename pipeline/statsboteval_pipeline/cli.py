"""Pipeline CLI. Thin slice: `python -m statsboteval_pipeline.cli run-synthetic ...`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
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
    args = parser.parse_args(argv)

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
