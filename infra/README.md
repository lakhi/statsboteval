# Azure infrastructure (Part 2 thin slice)

az-CLI scripts, no Bicep (D-28: few resources; these scripts are the reproducible
record). Everything lives in the shared **Lehrprojekt** resource group on the MOPS
subscription (operator access is RG-scoped Contributor), resources named `statsboteval*`.

**Demo URL: <https://statsboteval.azurewebsites.net>** — synthetic data, clearly bannered.
First deployed 2026-07-06.

## Hosting: App Service F1 now, Container Apps later (D-29)

The planned Container Apps deploy (D-26/D-28) is blocked until the subscription admin
registers the `Microsoft.App` resource provider (requested 2026-07-06; a one-time,
subscription-scope action RG Contributor cannot perform). Interim hosting is a **free
Linux App Service** serving the same tree the Dockerfile builds. Known F1 limits: the app
unloads when idle (cold starts ~30 s+), daily CPU quota — a crash-looping deploy can
disable the site until the quota resets. Fine for a synthetic-data demo; migrate before
sharing the URL around (the Container Apps script is preserved at commit `2fd5f1e`).

## What exists after a full run

| Resource | Name (default, `scripts/config.sh`) | Notes |
|---|---|---|
| Resource group | `Lehrprojekt` (pre-existing, shared) | **never** delete/teardown wholesale |
| Storage account | `statsbotevalsa` | blob public access disabled (D-18); private container `aggregates` |
| App Service plan | `statsboteval-plan` | Linux F1 (free) |
| Web app | `statsboteval` | Python 3.12, Oryx server-side build, HTTPS-only |

Teardown = delete only our resources:
`az webapp delete -n statsboteval -g Lehrprojekt && az appservice plan delete -n statsboteval-plan -g Lehrprojekt -y && az storage account delete -n statsbotevalsa -g Lehrprojekt -y`

Credentials: the app reads the blob via a **connection string stored as an app setting**
(encrypted at rest; managed-identity RBAC needs role-assignment rights the operator lacks
— D-29). The operator publishes with an ad-hoc connection string fetched by
`03_publish_synthetic.sh`; it is never written to disk.

## Usage (in order, from anywhere; requires `az login`)

```bash
infra/scripts/01_infra.sh              # storage + container (+ operator RBAC where permitted)
infra/scripts/02_deploy_app.sh         # build dashboard, stage app/schema/static, zip-deploy
infra/scripts/03_publish_synthetic.sh  # publish a synthetic aggregates doc to the real blob
```

- Redeploy after code changes: re-run `02_deploy_app.sh`.
- Republish data: re-run `03_publish_synthetic.sh` (immutable blob + `latest.json`, contract §9).
- Verify: `curl https://statsboteval.azurewebsites.net/healthz`,
  `curl https://statsboteval.azurewebsites.net/api/v1/aggregates | jq .data_provenance`
  (must be `"synthetic"` until the Part 4 go-live gates close), dashboard in a browser.

## Operational gotchas (learned the hard way, 2026-07-06)

- Oryx extracts the built package into a random `/tmp` directory at each boot and starts
  the app there — `SCHEMA_PATH`/`DASHBOARD_DIST` must stay **relative** (they resolve
  against the extracted app root), never `/home/site/wwwroot`-absolute.
- If the site shows `state: QuotaExceeded` (`az webapp show -n statsboteval -g Lehrprojekt
  --query state`), the F1 quota is burned — usually by a crash loop; it resets on the hour
  boundary of the daily window (ours: 09:00 UTC). Logs: `az webapp log download`.
