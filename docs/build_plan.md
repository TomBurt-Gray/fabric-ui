# Build plan

Work one milestone at a time. Start each in plan mode, confirm the plan, then build. Update the "Status" column and `CLAUDE.md` commands as you go.

| # | Milestone | Status |
|:--|:--|:--|
| M0 | Repo scaffold | ruff, pytest and `manage.py check` pass; Docker build pending (Docker not installed) |
| M1 | Django foundation: auth, roles, layout, correlation IDs | Done locally (77 tests); claim types to verify in internal dev |
| M2 | Audit | Done locally (120 tests); ledger migration to run on Azure SQL in M7/M8 |
| M3 | Support issues and email | Done locally (167 tests, browser checked); Graph sending to verify in M8 |
| M4 | Catalogue and dynamic table viewer on stub data | Not started |
| M5 | Fabric SQL endpoint data source | Not started |
| M6 | Exports and on demand reports | Not started |
| M7 | Terraform: bootstrap, modules, stack, internal_dev.tfvars | Not started |
| M8 | Azure DevOps pipelines and first deploy to internal dev | Not started |
| M9 | Demo polish and demo script | Not started |

## M0 Repo scaffold

* Layout as in `CLAUDE.md`; `pyproject.toml` with runtime and dev dependencies; ruff and pytest config; `.env.example`; `.gitignore` (includes `.env`, `*.tfstate*`, `.terraform/`); Dockerfile (slim Python 3.12 base, ODBC Driver 18, non root user, gunicorn).
* Runtime dependencies to start: `Django` (5.2.x), `mssql-django`, `pyodbc`, `azure-identity`, `openpyxl`, `PyYAML`, `gunicorn`, `whitenoise`. Anything else: ask first.
* Done when: `ruff check .` and `pytest` pass on an empty project; Docker image builds.

## M1 Django foundation

* Easy Auth principal parsing, role mapping, dev auth shim (refuses to load on App Service or with DEBUG off), `UserProfile`.
* Correlation ID middleware (reuse incoming header if present, else generate); include it in logs and responses.
* Base layout with navigation and the "Report an issue" entry point placeholder. Accessible, clean, client brandable via config (name, logo, colours).
* Done when: tests prove unauthenticated and wrong role requests are rejected, and the shim cannot load in production settings.

## M2 Audit

* `AuditEvent` model, typed event classes with a registry, `record()` and `audited_action()`, failure page with Try again, access denied events.
* Ledger migration conditional on Microsoft vendor; model, queryset and SQLite triggers block updates and deletes elsewhere.
* Done when: an audit write failure rolls back the business change in tests; every 403 writes an event; update and delete attempts fail in tests, including raw SQL.

## M3 Support issues and email

* HTMX dialog on every page; auto captures page, filters, correlation ID, user agent.
* `SupportIssue`, `Delivery` outbox, Graph sender behind an interface with a console sender for local dev; support role views.
* Management command `send_outbox` to retry (later run by the Container Apps job).
* Done when: an issue is saved even if the sender raises; retry sends it; payload validates against `support_issue.v1` and carries no issue content.

## M4 Catalogue and viewer on stub data

* `DataSource` interface, `StubSource` with 3 synthetic tables of different shapes (one over 10,000 rows).
* YAML display config with validation.
* Catalogue page; table view with paging, sorting, type aware formatting, filters; state in the URL; HTMX partial updates.
* Done when: hidden tables and columns never render; invalid identifiers are rejected; paging never loads a full table.

## M5 Fabric SQL endpoint data source

* `FabricSqlSource` using pyodbc and an Entra token from `DefaultAzureCredential`.
* Integration tests marked and skipped unless `FABRIC_SQL_ENDPOINT` is set.
* Done when: the viewer works against our internal Lakehouse by switching `source: fabric` in config.

## M6 Exports and reports

* CSV and .xlsx export of the current view, streamed in pages, audited with row count.
* Report definitions from YAML; on demand run page.
* Done when: export output matches on screen filters in tests.

## M7 Terraform

* Bootstrap state storage. Modules wrapping AVM with secure defaults. Stack with the inputs listed in `architecture.md`.
* `internal_dev.tfvars` for our environment.
* Done when: `fmt`, `validate`, `tflint` and the security scan pass; plan is clean; apply then destroy works end to end in internal dev.

## M8 Pipelines and first deploy

* Infra pipeline (plan artefact, approval, apply) and app pipeline (test, build, push, deploy, smoke test) on VNet agents with workload identity federation.
* Done when: a commit to main deploys to internal dev with no manual steps after approval.

## M9 Demo polish

* Demo script: sign in, browse catalogue, filter a large table, export, run a report, raise an issue (stub content), show the audit trail, show the Terraform plan.
* Short README section for the client walkthrough.
* Tighten repository controls before the demo: remove owner bypass on the `main` ruleset, make the PR review agent a required status check, require 1 approval once a second developer joins, consider signed commits and code scanning.
