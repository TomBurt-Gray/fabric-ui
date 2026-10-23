# Requirements

## Business context

Typical client current state (anonymised):

* Reports are produced by Windows Task Scheduler on an automation service account, which opens an Excel workbook and runs a macro.
* A VBA tool is used to propose, authorise and sign off trades. It writes audit records to .txt files. Concurrent use corrupts data.
* Power BI is in use but users find it clunky.
* Data is already processed by a Fabric medallion architecture; gold tables sit in a Lakehouse.

Goal: replace these with one secure, maintainable web app over Fabric gold data, with audit and support built in from day one. The same foundation must be reusable for every client, with client differences handled by configuration.

Commercial approach: build a working PoC internally, demo it to the client with the proposed infrastructure, then deploy into their environment after approval.

## Users

* Client staff signing in with Entra ID, on company laptops connected to a corporate VPN.
* Under 20 concurrent users.
* Roles: `viewer` (browse), `report_user` (browse, export, run reports), `admin` (audit viewer, config), `support` (our team; view issues).
* Roles come from Entra app roles assigned to groups, never assigned inside the app (D14). Roles are independent: no role implies another (D15).

## Phases

| Phase | Where | Scope |
|:--|:--|:--|
| PoC (now) | Our internal dev environment, our data | Sign in, table catalogue, dynamic table viewer, export, on demand reports, issue reporting with email, audit logging, stub data mode, Terraform for all Azure infra |
| MVP | Client subscription, client gold data | PoC scope plus scheduled report snapshots, audit viewer, "my issues" list, production hardening, client tfvars and config |
| Phase 2 | Client | Trade propose, authorise, sign off workflow; write back; natural language Q&A; triggering Fabric pipelines |

## Functional requirements

| ID | Requirement | Phase | Acceptance |
|:--|:--|:--|:--|
| FR01 | Sign in with Entra ID via App Service built in authentication. Roles from Entra. | PoC | Unauthenticated requests never reach Django views. Role checks enforced server side on every view. |
| FR02 | Table catalogue lists gold tables discovered from the Fabric SQL analytics endpoint, with friendly names and descriptions from config. | PoC | A new table added to the Lakehouse appears without code change. Hidden tables in config never appear. |
| FR03 | Table viewer: server side paging, sort, type aware formatting (numbers, dates, currency), filters by column type. | PoC | Works on a table larger than one page without loading it whole. URL holds view state so it can be shared. |
| FR04 | Export the current filtered view as CSV or .xlsx. | PoC | Export matches the on screen filters. Every export writes an audit event with table, filters and row count. |
| FR05 | Reports: saved views (table, columns, filters, sort) defined in config, run on demand. | PoC | Report definitions change by editing YAML only. |
| FR06 | Scheduled report snapshots written to immutable storage. | MVP | A job runs on schedule, writes the file, records a ReportRun, and audits it. |
| FR07 | "Report an issue" available on every page. User gives type (Incident, Service request, Defect, Enhancement), subject, description, optional detail and impact flags; no priority. Page, filters, correlation ID, user agent and timestamp captured automatically. | PoC | Issue saved to the database before any email is attempted. User sees a reference number. Support role sees full detail in the app. |
| FR08 | Each new issue sends an email to the configured support mailbox with a readable summary and a `support_issue.v1` JSON attachment the support tracker imports. The email carries no issue content (D22). | PoC | Email sent only after the database commit. Failed sends are retried from an outbox. No issue is lost if email fails. |
| FR09 | Users can see their own issues and status. | MVP | |
| FR10 | Every business action writes an audit event to an append only store in the same transaction as the action: access denied, data viewed, exports and report runs, issues raised, config changes (trade lifecycle events in Phase 2). Plain request logs go to Application Insights, not the audit store. | PoC | Audit rows cannot be updated or deleted (SQL ledger append only table in Azure; model and database triggers on SQLite). If the audit write fails, the action does not happen and the user sees an error with Try again. |
| FR11 | Admin audit viewer with filters by user, action, date. | MVP | |
| FR12 | Stub data mode: the catalogue and viewer read synthetic tables instead of Fabric, switched by config. | PoC | Full demo possible with no Fabric connection. |
| FR20 | Trade workflow: proposed, authorised, signed off, with segregation of duties (proposer cannot authorise own trade) and optimistic locking. | Phase 2 | Design the audit and roles now so this is additive. |
| FR21 | Write back to an operational store (Azure SQL or Fabric SQL database), merged into gold by a pipeline. Never write directly to gold. | Phase 2 | |
| FR22 | Natural language Q&A over gold data. | Phase 2 | Requires client compliance review first; Fabric data agent MCP is preview and may process data outside the Fabric compliance boundary. |
| FR23 | Trigger Fabric pipelines from the app. | Phase 2 | |

## Non functional requirements

| ID | Requirement |
|:--|:--|
| NFR01 Security | Private by default: no public endpoints, managed identities, no keys or passwords, Entra only auth on SQL, HTTPS only, TLS 1.2 minimum. |
| NFR02 Maintainability | Django LTS, vendored HTMX, minimal runtime dependencies. Upgrades planned LTS to LTS. |
| NFR03 Auditability | Tamper evident audit (SQL ledger) in the client's own Azure SQL, periodic archive to immutable blob storage, retention set per client. Immutable stores identify users by Entra object ID, not names or emails. Client IP and user agent are captured behind a config switch (`capture_network`) for security investigation; enabling it in production needs client compliance approval because ledger rows cannot be erased (D18). |
| NFR04 Concurrency | Database transactions everywhere; optimistic locking (version column) on any editable record. Fixes the VBA corruption problem by design. |
| NFR05 Configurability | Client and environment differences only in tfvars and YAML. |
| NFR06 Performance | Server side paging (default 50 rows per page) and a query timeout (default 30 seconds). Both configurable. |
| NFR07 Tear down | `terraform destroy` removes all PoC resources. Prod protections (locked immutability, purge protection, delete locks) are opt in. |
| NFR08 Data handling | No client data outside the client environment. Demo issue emails contain stub content only. |
| NFR09 Regulatory | Clients are FCA regulated and subject to GDPR. Retention and record keeping rules are confirmed by client compliance before MVP. |
