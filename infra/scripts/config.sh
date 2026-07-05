# shellcheck shell=bash
# Shared configuration for the statsboteval Azure scripts (D-26/D-28), sourced by 01-03.
# Override any value via environment, e.g. STORAGE_ACCOUNT=... ./01_infra.sh

RESOURCE_GROUP="${RESOURCE_GROUP:-statsboteval-rg}"
LOCATION="${LOCATION:-swedencentral}"
# Globally unique, 3-24 lowercase alphanumerics — change if taken.
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-statsbotevalsa}"
CONTAINER_NAME="${CONTAINER_NAME:-aggregates}"
APP_NAME="${APP_NAME:-statsboteval}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-statsboteval-env}"

# shellcheck disable=SC2034  # consumed by the sourcing scripts
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
