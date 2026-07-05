#!/bin/bash
# Build (in the cloud) + deploy the single container app; wire managed identity (D-28).
# Re-running = redeploy from current source.
set -euo pipefail
# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

az containerapp up \
  --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" \
  --environment "$ENVIRONMENT_NAME" --source "$REPO_ROOT" \
  --ingress external --target-port 8000

az containerapp identity assign \
  --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --system-assigned --output none

PRINCIPAL_ID="$(az containerapp identity show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query principalId --output tsv)"
STORAGE_SCOPE="$(az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query id --output tsv)"
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Reader" --scope "$STORAGE_SCOPE" --output none \
  || echo "(role assignment may already exist — fine)"

az containerapp update \
  --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "STORAGE_ACCOUNT_URL=https://$STORAGE_ACCOUNT.blob.core.windows.net" \
                 "AGGREGATES_CONTAINER=$CONTAINER_NAME" --output none

FQDN="$(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn --output tsv)"
echo "deployed: https://$FQDN"
