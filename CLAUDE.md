# Fabric Gold UI: project context

## What this is

A secure web app for browsing, reporting on and exporting Microsoft Fabric gold data, with built in audit logging and support issue reporting, plus the Terraform that deploys its Azure infrastructure.

Stage now: PoC, built in OUR internal dev environment (our tenant, our Fabric workspace, our internal data). Later it is deployed into client Azure subscriptions by changing only tfvars and config files, never code.

## Read before working

* Requirements and phases: @docs/requirements.md
* Architecture and component design: @docs/architecture.md
* Decisions already made (do not revisit without asking): @docs/decisions.md
* Build plan, milestones and acceptance criteria: @docs/build_plan.md
* Open questions and assumptions: @docs/open_questions.md

## Hard rules

1. Never commit secrets, keys, passwords, connection strings, tenant IDs or subscription IDs. Use managed identity or Entra tokens. Config comes from environment variables; provide `.env.example` with placeholders only.
2. No client data anywhere in this repo: not in fixtures, tests, screenshots or docs. Stub data is synthetic.
3. Minimal dependencies. No npm, no Node toolchain, no frontend build step. Ask before adding any runtime Python package and state why.
4. Django 5.2 LTS, Python 3.12. HTMX is vendored as a static file, never loaded from a CDN.
5. Every user action is audited (see architecture). A feature is not done until its audit events exist and are tested.
6. SQL identifiers (table and column names) come only from the discovered allow list. Values are always parameterised. Never build SQL from raw user input.
7. Client specifics live in config (tfvars, YAML). Never branch on client name in code.
8. Terraform defaults are the most secure option. Relaxing any control requires an explicit input variable with a comment explaining the risk.
9. Fabric infrastructure as code is out of scope for now. The app only reads from an existing Fabric workspace.
10. If a requirement is unclear, check `docs/open_questions.md`, then ask. Do not guess business rules.

## Target repo layout

```
app/                  Django project
  fabric_ui/          Django project package: settings, urls, wsgi
  core/               auth (Easy Auth principal), roles, layout, correlation IDs
  audit/              audit events, middleware, archive export
  support/            issue reporting, outbox, Graph email
  catalog/            data source interface, Fabric and stub sources, table viewer
  reports/            saved views, exports, scheduled snapshots
  templates/ static/  server rendered templates, vendored htmx.min.js
config/
  tables.example.yaml per environment display config (friendly names, hidden columns, formats)
infra/
  bootstrap/          Terraform state storage (applied once, separately)
  modules/            thin wrappers around Azure Verified Modules
  stack/              root module composing everything
  envs/               one tfvars per environment, e.g. internal_dev.tfvars
pipelines/            Azure DevOps YAML (infra plan/apply, app build/deploy)
docs/                 these context files (human owned)
  generated/          written only by the docs sync agent; never edit by hand
.claude/              CI agent skills and settings (see docs/agents.md)
scripts/agents/       deterministic checks for the CI agents
.github/workflows/    CI agent wrappers (GitHub Actions)
Dockerfile
```

## Commands

Keep this section updated as tooling is added. Python tooling uses uv (dev and build only; `uv.lock` is committed).

* Install: `uv sync`
* Lock after changing dependencies: `uv lock`
* Lint and format: `uv run ruff check .` and `uv run ruff format .`
* Tests: `uv run pytest`
* Run locally: copy `.env.example` to `.env` (enables the dev sign in shim; set `DEV_AUTH_ROLES` to test roles), then `uv run --env-file .env python app/manage.py migrate` and `uv run --env-file .env python app/manage.py runserver` (stub data mode by default)
* Every view needs an access rule from `core.access` (`require_roles`, `any_role` or `public`); undeclared views are denied and a test fails
* Container: `docker build -t fabric-ui .`
* Terraform: `terraform fmt -check`, `terraform validate`, `tflint`, then `terraform plan -var-file=../envs/internal_dev.tfvars` from `infra/stack`

## Style

* UK English in UI copy and docs. Concise.
* Python: type hints, small functions, ruff defaults.
* Tests: pytest with pytest-django (dev dependencies only). Unit tests run on SQLite with stub data; integration tests against Azure SQL and Fabric are marked and skipped unless configured.
