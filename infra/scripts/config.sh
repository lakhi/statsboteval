# shellcheck shell=bash
# Shared configuration for the statsboteval Azure scripts (D-26/D-28), sourced by 01-03.
# Override any value via environment, e.g. STORAGE_ACCOUNT=... ./01_infra.sh

# MOPS subscription: operator access is Contributor scoped to the shared RG
# "Lehrprojekt" (no RG-create rights), so resources live there, named statsboteval*.
RESOURCE_GROUP="${RESOURCE_GROUP:-Lehrprojekt}"
LOCATION="${LOCATION:-swedencentral}"
# Globally unique, 3-24 lowercase alphanumerics — change if taken.
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-statsbotevalsa}"
CONTAINER_NAME="${CONTAINER_NAME:-aggregates}"
# App Service (D-29): Microsoft.App is unregistered in MOPS and RG-scoped Contributor
# cannot register it, so the thin slice runs on the free F1 plan instead of Container Apps.
APP_NAME="${APP_NAME:-statsboteval}"  # globally unique on *.azurewebsites.net
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-statsboteval-plan}"

# shellcheck disable=SC2034  # consumed by the sourcing scripts
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
