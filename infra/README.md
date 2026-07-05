# Azure infrastructure (Part 2 thin slice)

az-CLI scripts, no Bicep (D-28: three resources; these scripts are the reproducible
record). Everything lands in one dedicated resource group in Sweden Central (D-26).

## What exists after a full run

| Resource | Name (default, `scripts/config.sh`) | Notes |
|---|---|---|
| Resource group | `statsboteval-rg` | teardown = `az group delete -n statsboteval-rg` |
| Storage account | `statsbotevalsa` | blob public access disabled (D-18); private container `aggregates` |
| Container Apps env + app | `statsboteval-env` / `statsboteval` | built from source by `az containerapp up` (auto-provisions an ACR); scale-to-zero |
| ACR | auto-created by `containerapp up` | ~€5/mo (Basic) — the only fixed cost; compute sits in the free grant |

Credentials: the app reads the blob via **system-assigned managed identity**
(Storage Blob Data Reader) — no secret in the app. The operator publishes with an
ad-hoc connection string fetched by `03_publish_synthetic.sh`.

## Usage (in order, from anywhere; requires `az login`)

```bash
infra/scripts/01_infra.sh              # RG + storage + container + operator RBAC
infra/scripts/02_deploy_app.sh         # cloud-build image from repo source, deploy, wire identity
infra/scripts/03_publish_synthetic.sh  # publish a synthetic aggregates doc to the real blob
```

- Redeploy after code changes: re-run `02_deploy_app.sh`.
- Republish data: re-run `03_publish_synthetic.sh` (immutable blob + `latest.json`, contract §9).
- Verify: `curl https://<fqdn>/healthz`, `curl https://<fqdn>/api/v1/aggregates | jq .data_provenance`
  (must be `"synthetic"` until the Part 4 go-live gates close), dashboard in a browser at the FQDN.

Demo URL: _recorded after the first deploy (Task 11)._
