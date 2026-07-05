#!/bin/bash
# Local end-to-end: Azurite -> synthetic publish -> API -> assertions.
# Requires: pipeline/.venv and api/.venv installed (uv pip install -e ".[dev]"), node/npx.
# Manual follow-up for eyeballing the page:
#   cd dashboard && NEXT_PUBLIC_API_BASE=http://localhost:8123 pnpm dev
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="$(mktemp -d)"
BLOB_PORT="${BLOB_PORT:-10321}"
API_PORT="${API_PORT:-8123}"
# Azurite's documented well-known dev key (public, not a secret).
KEY="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
CONN="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=$KEY;BlobEndpoint=http://127.0.0.1:$BLOB_PORT/devstoreaccount1;"

wait_port() { python3 -c '
import socket, sys, time
port = int(sys.argv[1])
for _ in range(120):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close(); sys.exit(0)
    except OSError:
        time.sleep(0.5)
sys.exit(f"port {port} never opened")
' "$1"; }

cleanup() {
  kill "${AZURITE_PID:-}" "${UVICORN_PID:-}" 2>/dev/null || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

echo "== starting Azurite (in-memory) on :$BLOB_PORT"
npx --yes --package azurite azurite-blob --blobHost 127.0.0.1 --blobPort "$BLOB_PORT" \
  --inMemoryPersistence --silent --skipApiVersionCheck >/dev/null 2>&1 &
AZURITE_PID=$!
wait_port "$BLOB_PORT"

echo "== publishing synthetic aggregates"
AZURE_STORAGE_CONNECTION_STRING="$CONN" "$ROOT/pipeline/.venv/bin/python" \
  -m statsboteval_pipeline.cli run-synthetic --corpus "$WORKDIR/corpus.duckdb" --upload

echo "== starting API on :$API_PORT"
(cd "$ROOT/api" && AZURE_STORAGE_CONNECTION_STRING="$CONN" DASHBOARD_DIST="$ROOT/dashboard/out" \
  .venv/bin/uvicorn 'app.main:create_app' --factory --port "$API_PORT" >"$WORKDIR/uvicorn.log" 2>&1) &
UVICORN_PID=$!
wait_port "$API_PORT"

echo "== assertions"
curl -sf "localhost:$API_PORT/healthz" | grep -q '"ok"'
curl -sf "localhost:$API_PORT/api/v1/aggregates" | python3 -c '
import json, sys
doc = json.load(sys.stdin)
assert doc["data_provenance"] == "synthetic", doc["data_provenance"]
series = doc["sections"]["temporal_usage"]["weekly"]["messages"]["series"]
weeks = [entry["week"] for entry in series]
assert len(weeks) == len(set(weeks)) and len(weeks) >= 4, weeks
statuses = {entry["cell"]["status"] for entry in series}
assert statuses == {"ok", "suppressed"}, statuses
print(f"aggregates OK: {len(weeks)} dense weeks, both cell states present")
'
if [ -f "$ROOT/dashboard/out/index.html" ]; then
  curl -sf "localhost:$API_PORT/" | grep -qi "<html" && echo "dashboard bundle served at /"
else
  echo "note: dashboard/out missing (run: cd dashboard && pnpm build) — API-only checks passed"
fi
echo "E2E-LOCAL: PASS"
