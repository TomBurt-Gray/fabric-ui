# Decisions

Decisions already agreed. Do not change these without asking; propose an alternative with evidence instead.

| ID | Decision | Rationale | Rejected alternatives |
|:--|:--|:--|:--|
| D01 | Build a custom UI rather than extend Power BI | Users find Power BI clunky; needs granular per interaction audit, custom workflows (phase 2) and built in issue reporting | Power BI with translytical task flows (GA March 2026; viable for simple write back but less control over audit and UX) |
| D02 | Django 5.2 LTS, server rendered, with vendored HTMX | Security support until April 2028; no npm dependency tree; team already uses Django; Python matches the data team | React or Next.js (largest dependency surface and churn); Blazor (sound, but a language switch for no clear gain) |
| D03 | Azure SQL Database for app data, with ledger tables for audit | Real transactions fix the VBA concurrency corruption; ledger gives tamper evidence auditors can verify; official Microsoft Django backend (mssql django) supports it with managed identity | .txt files; app tables in Fabric (would tie app availability to Fabric capacity). Fabric SQL database stays an option later, same backend |
| D04 | Read gold data via the Lakehouse SQL analytics endpoint | Schema discovery and server side paging over one connection; suits a dynamic viewer | API for GraphQL (tables must be exposed per API item; better for fixed screens later); OneLake direct Delta reads (no SQL engine) |
| D05 | App reads Fabric with its own managed identity; authorisation in Django | Simple for under 20 users | Per user on behalf of queries (revisit only if Fabric row level security per user is required) |
| D06 | Email support issues via Microsoft Graph, after commit, through an outbox | Records are never lost; structured JSON lets support create tickets | Direct SMTP (fallback if a client forbids Graph Mail.Send) |
| D07 | App Service for the web app, Container Apps job for scheduled work, one image | Simple, private networking supported, no cluster to run | AKS (overkill); Task Scheduler on a service account (the thing being replaced) |
| D08 | Terraform with Azure Verified Modules, one stack, per environment tfvars; Terraform deploys, not just documents | Plan output doubles as the client approval artefact; no drift; clean teardown | Hand built portal resources; Bicep (team has some Terraform experience) |
| D09 | Private by default, with an `ip_restricted` ingress fallback | Minimises security review resistance; fallback covers clients whose VPN has no route into Azure | Public app with Entra only |
| D10 | Client differences in config only (tfvars, YAML) | Fast bootstrapping for new clients; no forks | Per client code branches |
| D11 | Fabric infrastructure as code out of scope for now | Focus on UI and Azure infra PoC | Terraform Fabric provider and fabric cicd (revisit later for workspace bootstrapping) |
| D12 | Pseudonymous user IDs (Entra object ID) in immutable stores | Lets GDPR erasure be handled in the mutable profile table | Names or emails in ledger and WORM storage |
| D13 | PoC on our internal environment and data | No client data risk during build and demo | Building against client data before approval |
