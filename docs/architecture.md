# Architecture

## Overview

Users on the client network sign in with Entra ID and reach a private App Service. The app reads gold tables from the Fabric Lakehouse SQL analytics endpoint, stores its own data (audit, issues, report runs) in Azure SQL, archives to immutable blob storage, and emails support issues via Microsoft Graph. Everything in Azure is deployed by one Terraform stack.

Request path: user laptop → corporate VPN → client hub network → private endpoint → App Service (Easy Auth) → Django.
Outbound path: App Service VNet integration → client network and egress firewall → Fabric SQL endpoint, Microsoft Graph.

## Azure components

| Component | Purpose | Key settings |
|:--|:--|:--|
| App Service (Linux, container) | Runs Django | Built in auth (Entra, require authentication), private endpoint inbound, VNet integration outbound with route all, HTTPS only, TLS 1.2, user assigned managed identity |
| Container Apps job | Scheduled report snapshots, audit archive, outbox retry | Same container image as the app, VNet integrated environment, same managed identity |
| Azure SQL Database | App data: audit, issues, report runs, user profiles | Entra only auth, ledger enabled for audit tables, private endpoint, public access off, small serverless tier |
| Storage account | Audit archives, report snapshots | Immutable container (time based retention; unlocked in dev, locked in prod), shared key access disabled, private endpoint |
| Key Vault | Django secret key and non identity settings | RBAC, soft delete, purge protection in prod, private endpoint |
| Container registry | App image | Premium tier (needed for private endpoints), admin user off, pull by managed identity |
| Log Analytics + Application Insights | Diagnostics | Diagnostic settings on every resource |
| VNet (spoke) | Isolation | Subnets: app integration (delegated), container apps, private endpoints, build agents (delegated) |
| Private DNS zones | Resolve private endpoints | Created by us, or supplied by client (input) |
| Managed DevOps Pool | Build agents inside the VNet | Needed because hosted agents cannot reach private resources; quota defaults to 0 |

## Django app structure

| App | Responsibility |
|:--|:--|
| `core` | Reads the Easy Auth principal, maps Entra roles to Django permissions, correlation ID middleware, base layout, error pages |
| `audit` | `AuditEvent` model, request audit middleware, `audit.record(action, target, detail)` helper for domain events, archive job |
| `support` | `SupportIssue` and `EmailOutbox` models, "Report an issue" HTMX modal on every page, Graph email sender, retry job |
| `catalog` | `DataSource` interface, `FabricSqlSource`, `StubSource`, table catalogue and viewer views |
| `reports` | Report definitions from YAML, on demand runs, exports, scheduled snapshots, `ReportRun` model |

### Authentication

* Production: App Service built in authentication with Entra, set to require authentication. Django reads the principal headers injected by the platform (`X-MS-CLIENT-PRINCIPAL`, base64 JSON with claims including roles; `X-MS-CLIENT-PRINCIPAL-ID`). Verify header names and claim shapes against current Microsoft Learn docs before implementing.
* Trust those headers only when Easy Auth is enforced. The private endpoint plus require authentication means requests cannot bypass it.
* Local dev: a dev auth shim injects a fake principal from settings. It must refuse to load when `DEBUG` is false or when running on App Service (detect the `WEBSITE_SITE_NAME` environment variable).
* `UserProfile` (mutable) maps Entra object ID to display name and email for the UI. Immutable stores only ever hold the object ID.

### Data source interface

```python
class DataSource(Protocol):
    def list_tables(self) -> list[TableInfo]: ...
    def describe(self, table: str) -> list[ColumnInfo]: ...
    def query(self, table: str, columns: list[str], filters: list[Filter],
              sort: list[Sort], offset: int, limit: int) -> QueryResult: ...
    def count(self, table: str, filters: list[Filter]) -> int: ...
```

* `StubSource`: synthetic tables (generated or loaded from CSV in `app/catalog/stub_data/`). Default locally.
* `FabricSqlSource`: pyodbc with Microsoft ODBC Driver 18. Get an Entra token from `azure-identity` (`DefaultAzureCredential`: Azure CLI locally, managed identity in Azure) and pass it as the access token connection attribute. Short lived connections; refresh tokens before expiry. Set `MARS_Connection=no`. Verify the token scope and paging syntax against current Fabric docs.
* Discovery from `INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS`, cached briefly.
* Identifiers are validated against discovered names and quoted; values are parameters. Filters are built from a typed whitelist of operators per column type.
* The SQL analytics endpoint is read only. Report logic that needs SQL lives in views created in the Lakehouse SQL endpoint, not in the app.

### Display config (YAML, per environment)

```yaml
source: fabric            # fabric | stub
schema_allow: [dbo, gold]
page_size: 50
query_timeout_seconds: 30
tables:
  gold.fact_trades:
    label: Trades
    description: Daily trades from the gold layer
    hidden_columns: [_load_ts]
    columns:
      notional: {label: Notional, format: currency, currency: GBP}
      trade_date: {label: Trade date, format: date}
    default_sort: [{column: trade_date, direction: desc}]
reports:
  daily_trades:
    label: Daily trades
    table: gold.fact_trades
    columns: [trade_date, notional]
    filters: [{column: trade_date, op: eq, value: "@today"}]
    schedule: "0 7 * * 1-5"   # MVP
hidden_tables: [gold.tmp_staging]
```

Validate the YAML on startup with clear errors. Unknown tables or columns are logged and ignored, not fatal.

### Audit

* `AuditEvent`: id, timestamp (UTC), actor object ID, role, action, target, detail (JSON), correlation ID, client IP, user agent, outcome.
* Middleware writes one event per request; domain helpers write richer events (export, report run, issue raised).
* On Azure SQL, the table is an append only ledger table, created by a migration that runs only when the database vendor is Microsoft. On SQLite the model blocks update and delete in code.
* Ledger digests stored in the immutable storage account. Note: ledger cannot be disabled once enabled.
* Daily job exports the previous day's events as JSON lines to the immutable container.

### Support issues

* `SupportIssue`: reference (human friendly, e.g. date plus sequence), status, category, severity, description, page URL, filters, correlation ID, user agent, actor object ID, created time, version.
* `EmailOutbox`: issue, status (pending, sent, failed), attempts, last error, next attempt time.
* Flow: save issue and outbox row in one transaction; `transaction.on_commit` triggers the send; failures stay pending for the retry job.
* Email via Microsoft Graph `sendMail` from a configured sending mailbox using the managed identity. The Mail.Send application permission must be scoped to that one mailbox, never tenant wide.
* Email body: readable summary plus a JSON payload, for example:

```json
{"schema": "support_issue.v1", "reference": "SUP-20261022-0007", "environment": "internal_dev",
 "category": "data", "severity": "medium", "description": "...", "page": "/tables/gold.fact_trades",
 "filters": {}, "correlation_id": "...", "created_utc": "..."}
```

* Option for strict clients: email carries only the reference; details are viewed in the app by the `support` role.

### Reports and exports

* Exports stream from the data source in pages to avoid memory spikes. CSV uses the standard library; .xlsx uses openpyxl (write only mode).
* Scheduled snapshots (MVP) run in the Container Apps job, write to the immutable container, and record a `ReportRun`.

## Terraform

### Layout

* `infra/bootstrap`: state storage account, applied once.
* `infra/modules`: thin wrappers around Azure Verified Modules, pinned to exact versions, with our secure defaults.
* `infra/stack`: root module composing modules from inputs.
* `infra/envs/*.tfvars`: one file per environment. Now `internal_dev.tfvars`; later per client `client_dev.tfvars`, `client_prod.tfvars` (anonymised names).

Pin Terraform, providers (azurerm, azapi if needed) and AVM module versions exactly. Run `fmt`, `validate`, `tflint` and a static security scan (for example Checkov or Trivy) in CI.

### Inputs

| Input | Default | Options |
|:--|:--|:--|
| `environment` | dev | dev, prod |
| `location` | required | approved region |
| `name_prefix`, `tags` | our convention | client convention and mandatory tags |
| `network_mode` | create | create (new spoke, optional hub peering), existing (client subnet IDs) |
| `private_dns_mode` | create | create, existing (client zone IDs map) |
| `ingress_mode` | private | private, ip_restricted (public endpoint limited to VPN egress IPs, plus Conditional Access) |
| `fabric_connectivity` | public | public (Entra over TLS), private_link |
| `app_sku`, `sql_sku` | small tiers for under 20 users | any allowed SKU |
| `deploy_agents` | managed_pool | managed_pool, self_hosted |
| `entra_group_ids` | required | map of role to group ID |
| `support_mailbox` | required | sending and receiving mailboxes |
| `audit_retention_days` | required | per compliance |
| `immutability_locked` | false | true for prod only |
| `purge_protection` | false | true for prod |
| `delete_lock` | false | true for prod |

### Secure defaults

Public network access disabled on all PaaS; private endpoints only; managed identities only; SQL Entra only; storage shared keys off; HTTPS only; TLS 1.2; Key Vault RBAC; diagnostics everywhere; registry admin off; workload identity federation from Azure DevOps (no pipeline secrets).

### Tear down

`terraform destroy` removes everything with dev defaults. Exceptions: a locked immutability policy blocks storage deletion until retention expires; purge protection keeps a deleted vault name reserved; delete locks block destroy. Outside Terraform: state storage, Entra app registrations made by an admin, and the app identity's Fabric workspace access.

## CI/CD (Azure DevOps)

* `infra` pipeline: fmt, validate, lint, scan, plan (artefact), manual approval, apply.
* `app` pipeline: lint, test, build image, push to registry, deploy to App Service and job, smoke test.
* Runs on agents inside the VNet. Authenticates with workload identity federation.
