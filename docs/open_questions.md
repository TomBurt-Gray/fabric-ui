# Open questions and assumptions

Do not guess these. Use the stated assumption until answered, and flag anything built on it.

## Internal dev environment (answer before M7 and M8)

| # | Question | Working assumption |
|:--|:--|:--|
| Q1 | Do we have network access into our internal Azure VNet (VPN or similar) to reach a private app? | If not, use `ingress_mode = ip_restricted` with our office or VPN egress IPs for internal dev only |
| Q2 | Is a Managed DevOps Pool quota available in our subscription? | If not, `deploy_agents = self_hosted` |
| Q3 | Which Fabric workspace and Lakehouse hold suitable internal gold tables? Any sensitive data in them? | Use non sensitive tables only; otherwise stub data |
| Q4 | Which mailbox sends issue emails and which receives them? Its domain must be listed on the tracker engagement for email intake | Console email sender until confirmed; placeholders in `config/support.example.yaml` |
| Q5 | Which Entra groups map to viewer, report_user, admin and support internally? | Create test groups in our tenant |
| Q6 | Approved Azure region for internal dev? | UK South |

## Raised during M0 planning (2026-10-23)

| # | Question | Status or working assumption |
|:--|:--|:--|
| Q7 | `fabric_connectivity` defaults to `public`, against hard rule 8. What did another client implement? | Awaiting answer. Do not build M7 networking on it yet |
| Q8 | Audit scope and shape. FR10 is changing from "every request" to business audit events shaped like the existing trade blotter audit schema (Context, Source, User, Device, Item, SubItem, BeforeValue, AfterValue, LifecycleStage, EventCategory, OrderID, IsTradeReconstructionEvent, AuditEventKey and timestamps). Open: generic core plus domain extension; whether other business applications send events to this service; which PoC actions (export, report run, issue raised) are audited | Answered: one table with core columns and typed payloads per event class (D20); this app provides the base class, features and client versions extend it; PoC events are access denied, data viewed, exports and report runs, issues raised. Trade lifecycle detail to follow |
| Q9 | `User` and `Device` (and client IP, user agent) are personal data. D12 says immutable stores hold the Entra object ID only | Answered: captured behind `capture_network`, default on, in the client's own database (D18); production use needs client compliance approval |
| Q10 | What happens if an audit write fails (e.g. Azure SQL serverless resuming)? Block the action or not? | Answered: the action does not happen; user sees Try again (D17) |
| Q11 | Roles: Entra app roles or group membership as primary? | Answered: app roles assigned to groups (D14), independent (D15) |
| Q12 | Support: in app ticket draft with captured context (URL, filters, correlation ID, visible rows), email carries the reference only. How is the draft generated (template or AI) and which ticketing system is the target? | Answered: template in config (D21), reference level email to our mailbox (D22), no user priority (D23), JSON Schema contract with pluggable delivery (D24) |
| Q13 | Microsoft ODBC Driver 18 requires accepting the Microsoft EULA (`ACCEPT_EULA=Y`). Who authorises this? | Install step commented out in the Dockerfile; blocks M5 |
| Q14 | mssql-django 2.x adds mssql-python as a dependency | Pinned 1.8.0 (pyodbc only); revisit as a separate decision |
| Q15 | CI agents need an Anthropic API key from Mirador's organisation (not a personal account), ideally a dedicated workspace with a spend limit. Who can issue it? | Agents disabled (`CLAUDE_AGENTS_ENABLED` unset) until a company key exists |
| Q16 | Which header carries the caller's IP on App Service behind a private endpoint? Not stated on Microsoft Learn | `client_ip_header: X-Forwarded-For` (first address); verify in internal dev (M8) |
| Q17 | Does Fabric mirroring support append only ledger tables? The limits page excludes "ledger history tables" (append only tables have none) but does not say explicitly | Do not rely on mirroring for the Lakehouse audit copy until verified |
| Q18 | Ledger rows can never be deleted. How do retention limits and GDPR erasure requests apply to IP addresses in the audit? | Client compliance to decide before enabling `capture_network` in production |
| Q19 | The audit ledger migration has only been checked by generating its SQL offline | Run against Azure SQL in M7/M8, including the `ENABLE LEDGER` permission for the migration identity |
| Q20 | The support tracker needs an importer for the `support_issue.v1` JSON attachment (schema and sample in `app/support/schemas/`) | Tracker team builds it; until then the readable email body still creates a ticket |
| Q21 | Graph Mail.Send for the app identity: who grants admin consent and scopes it to the sending mailbox (Exchange Online RBAC for Applications)? | Verify the scoping steps on Microsoft Learn in M7/M8 |
| Q22 | Issues land at the tracker's default priority until triaged, so a real outage waits on triage speed | Accepted for now; revisit if SLA breaches occur |

## Client (answered later via the Client Discovery Checklist)

These do not block the PoC. The Terraform inputs already cover each variant.

* Hub network, private DNS ownership, and how users route from VPN into Azure (`network_mode`, `private_dns_mode`, `ingress_mode`).
* Fabric Private Link and Block Public Internet Access tenant settings (`fabric_connectivity`).
* Azure Policy on naming, tags, SKUs, regions.
* Entra admin consent, service principal RBAC, Graph Mail.Send scoping.
* Audit retention period, regulatory requirements, whether support details may leave the tenant by email.
* Whether per user Fabric row level security is required (would change D05).
* Confirm only company managed devices can reach the app (network and Entra Conditional Access), and whether IP and user agent capture in the audit is approved (Q18).
* Entra ID P1 or higher, needed to assign groups to app roles (D14).
* Accounts in the client tenant with the `support` role for our support staff, so they can open issue details (D22).

## Deferred design topics

* Phase 2 trade workflow details: states, roles, approval limits.
* Natural language Q&A approach, pending compliance review.
* Fabric workspace bootstrapping with Terraform and fabric cicd for new clients.
* Copier template for spinning up new client repos from this foundation, once a second client exists.
