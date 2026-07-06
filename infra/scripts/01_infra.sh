#!/bin/bash
# Resource group + private storage + operator RBAC. Idempotent-ish: safe to re-run.
set -euo pipefail
# shellcheck source=./config.sh
source "$(dirname "$0")/config.sh"

if [ "$(az group exists --name "$RESOURCE_GROUP")" = "true" ]; then
  echo "resource group $RESOURCE_GROUP exists"
else
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
  echo "resource group $RESOURCE_GROUP created"
fi

az storage account create \
  --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 \
  --allow-blob-public-access false --min-tls-version TLS1_2 --output none
echo "storage account $STORAGE_ACCOUNT ready (blob public access disabled — D-18)"

az storage container create \
  --account-name "$STORAGE_ACCOUNT" --name "$CONTAINER_NAME" --auth-mode key --output none
echo "container $CONTAINER_NAME ready"

# Operator publishes from the local pipeline (03_publish_synthetic.sh).
OPERATOR_ID="$(az ad signed-in-user show --query id --output tsv)"
STORAGE_SCOPE="$(az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query id --output tsv)"
az role assignment create \
  --assignee "$OPERATOR_ID" --role "Storage Blob Data Contributor" --scope "$STORAGE_SCOPE" --output none \
  || echo "(role assignment unavailable — publishes use the account key via show-connection-string, which Contributor permits)"
echo "operator access ready"
