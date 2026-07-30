#!/bin/bash
# Publish a PRODUCTION aggregates document to the real blob (§9 protocol).
#
# The real-data sibling of 03_publish_synthetic.sh. Same credential posture (D-28): the
# connection string is fetched ad hoc from Azure and never written to disk.
#
# Two modes, and the difference is the operator review gate (D-37, classification runbook):
#
#   --from FILE   Upload a document that already exists and has been reviewed. No
#                 re-aggregation: the publish guard re-runs on those exact bytes, so what
#                 was read is what goes live. This is the normal path.
#
#   (no --from)   Aggregate now, write the document, print its headline numbers, upload it.
#                 Every remaining argument is passed through to `run-weekly`, so the caller
#                 decides whether to touch the production DB (--skip-extract) or spend on
#                 classification (--skip-classify). Use when nothing needs reviewing —
#                 e.g. re-publishing after a presentation-only change.
#
# Examples:
#   infra/scripts/04_publish_production.sh --from pipeline/data/aggregates-review.json
#   infra/scripts/04_publish_production.sh --skip-extract --skip-classify
#
# Why not just `run-weekly --upload`? Because that re-aggregates, so the document uploaded
# is a second, freshly computed one — close to the reviewed document but not provably it
# (a run crossing an ISO-week boundary changes the axis). --from removes that gap.
set -euo pipefail
# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

PY="$REPO_ROOT/pipeline/.venv/bin/python"
CORPUS="${CORPUS:-$REPO_ROOT/pipeline/data/corpus.duckdb}"

FROM=""
if [ "${1:-}" = "--from" ]; then
  FROM="${2:?--from needs a path}"
  shift 2
  [ -f "$FROM" ] || { echo "no such document: $FROM" >&2; exit 1; }
fi

echo "== fetching the storage connection string (ad hoc, never written to disk)"
CONNECTION_STRING="$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --output tsv)"

if [ -z "$FROM" ]; then
  FROM="$REPO_ROOT/pipeline/data/aggregates-publish-$(date -u +%Y%m%dT%H%M%SZ).json"
  echo "== aggregating (run-weekly $*)"
  "$PY" -m statsboteval_pipeline.cli run-weekly --corpus "$CORPUS" --out "$FROM" "$@"
fi

echo "== the document about to go live"
AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING" "$PY" - "$FROM" <<'PY'
import json
import sys

from statsboteval_pipeline.contract import Aggregates
from statsboteval_pipeline.publish import publish

path = sys.argv[1]
# model_validate is a real gate, not a formality: an edited or stale-schema file dies here
# rather than reaching the container.
doc = Aggregates.model_validate(json.loads(open(path, encoding="utf-8").read()))
window = doc.sections.usage_context.per_window["all_time"].totals if doc.sections.usage_context else None
print(f"   schema {doc.schema_version}  provenance {doc.data_provenance}  floor N>={doc.privacy_floor_n}")
print(f"   axis {doc.first_week} -> {doc.data_through_week}   labels {doc.label_versions}")
if window is not None and window.active_students.status == "ok":
    print(f"   all-time active users {window.active_students.value}, messages {window.messages.value}")
if doc.data_provenance != "production":
    sys.exit(f"refusing to publish: data_provenance is {doc.data_provenance!r}, not 'production'")

import os

immutable, latest = publish(doc, connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"])
print(f"== published {immutable} and {latest}")
PY

echo "== verifying what the public URL now serves"
FQDN="$(az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
  --query defaultHostName --output tsv)"
# F1 unloads when idle, so the first request after a quiet spell is a ~30 s cold start.
curl -sf --max-time 120 "https://$FQDN/healthz" >/dev/null && echo "   healthz OK"
# Single-quoted heredoc, not -c with nested quotes: an f-string's braces and the shell's
# quoting fight each other and the escape only breaks at the end of a real publish.
curl -sf --max-time 120 "https://$FQDN/api/v1/aggregates" | "$PY" <<'PY'
import json
import sys

doc = json.load(sys.stdin)
print("   live: schema {}, {}, through {}".format(
    doc["schema_version"], doc["data_provenance"], doc["data_through_week"]
))
PY
echo "PUBLISHED: https://$FQDN"
