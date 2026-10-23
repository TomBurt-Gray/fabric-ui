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
* Implemented (M1): `core.principal` parses the principal (accepts short and mapped URI claim types); `core.middleware.EasyAuthMiddleware` returns 401 without a principal and enforces per view access rules from `core.access` (`require_roles`, `any_role`, `public`). Views without a rule are denied. No `django.contrib.auth` or sessions (D16).
* Verify in internal dev (M8): the exact claim types App Service emits for object ID and roles, and whether `/healthz` must be excluded from Easy Auth for health probes.
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

Implemented in M2 (`app/audit/`).

* **One table, typed payloads (D20).** `AuditEvent` holds core columns mapped from the legacy trade blotter schema: `event_id` (AuditEventKey), `occurred_at` and `recorded_at` (Date, Time, AuditDateTime, Store_Datetime), `event_type`, `category` (EventCategory), `outcome`, `schema_version`, `source_system` and `environment` (Source, Context), `actor_object_id` and `actor_roles` (User), `target` and `target_detail` (Item, SubItem), `before` and `after` (BeforeValue, AfterValue), `message` (LongText), `correlation_id`, `client_ip` and `user_agent` (Device). JSON columns are stored as text (`nvarchar(max)`) so the table stays eligible for Fabric mirroring.
* **Event classes.** Each feature declares events as frozen dataclasses subclassing `audit.events.AuditEventType`, decorated with `@register`. Their typed fields become `detail.fields`; `static_fields` from the audit config become `detail.context`. Trade specific legacy fields (OrderID, WorkbookType, WorkbookRole, LifecycleStage, IsTradeReconstructionEvent) become fields of trade event classes in Phase 2. `python app/manage.py audit_events` prints the catalogue.
* **Same transaction (D17).** Features wrap changes in `audit.service.audited_action(request, event)`: the change and the audit row commit together or not at all. `record()` is used directly only where nothing changes (access denied, before streaming an export). Audit write failures raise `AuditUnavailable`, which `AuditFailureMiddleware` turns into a 503 page with Try again.
* **Access denied.** Every 403 writes `auth.access_denied`; the denial stands even if that write fails. 401s are not audited (no identity; Entra sign in logs cover them).
* **Append only.** On Azure SQL the migration creates an append only ledger table (`WITH (LEDGER = ON (APPEND_ONLY = ON))`, needs `ENABLE LEDGER`; ledger cannot be disabled once enabled). On SQLite the model, queryset and database triggers refuse updates and deletes.
* **Config.** `config/audit.example.yaml` (path from `AUDIT_CONFIG`): `source_system`, `environment`, `capture_network`, `client_ip_header`, `static_fields`.
* **Later.** Ledger digests to the immutable storage account and the daily JSON lines archive need storage (M7). Lakehouse reporting copy via Fabric mirroring once support for append only ledger tables is confirmed (D19).

### Support issues

Implemented in M3 (`app/support/`).

* **Capture.** "Report an issue" on every page opens a dialog (HTMX, with a full page fallback at `/support/new`). Users choose a type (Incident, Service request, Defect, Enhancement; values match the support tracker), subject, description, optional expected and actual behaviour, steps and workaround, and impact flags. No priority (D23). Captured automatically: page path and its query string as filters, the page's correlation ID, user agent, requester from the principal. Rate limited per user per hour.
* **Store first (FR07, D06).** `support.service.raise_issue` saves `SupportIssue`, a `Delivery` outbox row and a `support.issue_raised` audit event in one `audited_action` transaction. Reference `{prefix}-{YYYYMMDD}-{id:06d}`, for example `FUI-20261023-000007`, never in square brackets so it cannot clash with the tracker's own `[INC-23]` threading.
* **Contract (D24).** `app/support/schemas/support_issue.v1.json` (JSON Schema) with a sample beside it. Reference level only: reference, environment, source system, type, subject, requester name and email, impact flags, created time, correlation ID, link to the issue in the app. No description, page, filters or data (D22). The tracker imports idempotently using the reference as its external reference.
* **Delivery (FR08).** `Sender` interface: `ConsoleSender` locally, `GraphSender` in Azure (`POST /users/{sender}/sendMail` with the managed identity; JSON attachment; `x-fui-reference` header). First attempt after commit; `manage.py send_outbox` retries with backoff (1, 5, 15, 60 minutes, then hourly; failed after 10 attempts). Rows are locked while sending so runners never double send. A tracker API sender can replace email without other changes. Mail.Send must be scoped to the sending mailbox only, never tenant wide.
* **Email wording** comes from `config/support.example.yaml` (`email_body` with whitelisted placeholders, validated at startup). Changes go through an enhancement ticket and a release (D21).
* **Support role.** `/support/issues` and `/support/issues/<reference>` show full detail and delivery status; each detail view is audited (`support.issue_viewed`).

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
