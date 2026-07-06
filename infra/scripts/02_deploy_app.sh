#!/bin/bash
# Deploy the thin slice to App Service Linux free tier (D-29): stage the same tree the
# Dockerfile builds (app/ + schema/ + static/), zip it, let Oryx install dependencies
# server-side. Re-running = redeploy from current source.
set -euo pipefail
# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

# --- stage the deployable tree (mirrors the Dockerfile layout) -----------------
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

(cd "$REPO_ROOT/dashboard" && pnpm install --frozen-lockfile && pnpm build)

cp -R "$REPO_ROOT/api/app" "$STAGING/app"
mkdir "$STAGING/schema"
cp "$REPO_ROOT/schema/aggregates.schema.json" "$STAGING/schema/"
cp -R "$REPO_ROOT/dashboard/out" "$STAGING/static"
# requirements.txt for Oryx, generated from the api project table (single source of truth)
"$REPO_ROOT/pipeline/.venv/bin/python" - "$REPO_ROOT/api/pyproject.toml" > "$STAGING/requirements.txt" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as fh:
    print("\n".join(tomllib.load(fh)["project"]["dependencies"]))
PY

(cd "$STAGING" && zip -qr app.zip app schema static requirements.txt)

# --- plan + app -----------------------------------------------------------------
az appservice plan create \
  --name "$APP_SERVICE_PLAN" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" \
  --is-linux --sku F1 --output none
echo "app service plan $APP_SERVICE_PLAN ready (F1)"

if ! az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  az webapp create \
    --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --plan "$APP_SERVICE_PLAN" \
    --runtime "PYTHON:3.12" --output none
fi
az webapp update --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --https-only true --output none
echo "web app $APP_NAME ready"

# App settings are App Service's secret mechanism (encrypted at rest, injected as env
# vars) — same trust level as the Container Apps secret fallback this replaces. RBAC
# for a managed identity is unavailable to RG-scoped Contributor (D-29).
CONNECTION_STRING="$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --output tsv)"
# Paths are relative: Oryx extracts the built package into a random /tmp dir at each
# boot and starts the app from there, so wwwroot-absolute paths don't exist at runtime.
az webapp config appsettings set \
  --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING" \
  AGGREGATES_CONTAINER="$CONTAINER_NAME" \
  SCHEMA_PATH=schema/aggregates.schema.json \
  DASHBOARD_DIST=static
az webapp config set --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none \
  --startup-file "python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"

# --- deploy (Oryx builds requirements.txt into antenv on the server) -------------
az webapp deploy --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
  --src-path "$STAGING/app.zip" --type zip

FQDN="$(az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query defaultHostName --output tsv)"
echo "deployed: https://$FQDN"
