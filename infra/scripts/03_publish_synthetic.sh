#!/bin/bash
# Publish a synthetic aggregates document to the real blob (§9 protocol).
# The connection string is fetched ad hoc and never written to disk (D-28).
set -euo pipefail
# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

CONNECTION_STRING="$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --output tsv)"

AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING" \
  "$REPO_ROOT/pipeline/.venv/bin/python" -m statsboteval_pipeline.cli run-synthetic \
  --corpus "$WORKDIR/corpus.duckdb" --upload "$@"
