# Open questions and assumptions

Do not guess these. Use the stated assumption until answered, and flag anything built on it.

## Internal dev environment (answer before M7 and M8)

| # | Question | Working assumption |
|:--|:--|:--|
| Q1 | Do we have network access into our internal Azure VNet (VPN or similar) to reach a private app? | If not, use `ingress_mode = ip_restricted` with our office or VPN egress IPs for internal dev only |
| Q2 | Is a Managed DevOps Pool quota available in our subscription? | If not, `deploy_agents = self_hosted` |
| Q3 | Which Fabric workspace and Lakehouse hold suitable internal gold tables? Any sensitive data in them? | Use non sensitive tables only; otherwise stub data |
| Q4 | Which mailbox sends issue emails and which receives them? | Console email sender until confirmed |
| Q5 | Which Entra groups map to viewer, report_user, admin and support internally? | Create test groups in our tenant |
| Q6 | Approved Azure region for internal dev? | UK South |

## Raised during M0 planning (2026-10-23)

| # | Question | Status or working assumption |
|:--|:--|:--|
| Q7 | `fabric_connectivity` defaults to `public`, against hard rule 8. What did another client implement? | Awaiting answer. Do not build M7 networking on it yet |
| Q8 | Audit scope and shape. FR10 is changing from "every request" to business audit events shaped like the existing trade blotter audit schema (Context, Source, User, Device, Item, SubItem, BeforeValue, AfterValue, LifecycleStage, EventCategory, OrderID, IsTradeReconstructionEvent, AuditEventKey and timestamps). Open: generic core plus domain extension; whether other business applications send events to this service; which PoC actions (export, report run, issue raised) are audited | Plain request logging goes to Application Insights, not the audit store. Settle at M2 planning, then update requirements and architecture |
| Q9 | `User` and `Device` (and client IP, user agent) are personal data. D12 says immutable stores hold the Entra object ID only | Store object ID only until agreed |
| Q10 | What happens if an audit write fails (e.g. Azure SQL serverless resuming)? Block the action or not? | Undecided; settle at M2 planning |
| Q11 | Roles: Entra app roles or group membership as primary? | Undecided; settle at M1 planning |
| Q12 | Support: in app ticket draft with captured context (URL, filters, correlation ID, visible rows), email carries the reference only. How is the draft generated (template or AI) and which ticketing system is the target? | Settle at M3 planning, then update requirements and architecture |
| Q13 | Microsoft ODBC Driver 18 requires accepting the Microsoft EULA (`ACCEPT_EULA=Y`). Who authorises this? | Install step commented out in the Dockerfile; blocks M5 |
| Q14 | mssql-django 2.x adds mssql-python as a dependency | Pinned 1.8.0 (pyodbc only); revisit as a separate decision |
| Q15 | CI agents need an Anthropic API key from Mirador's organisation (not a personal account), ideally a dedicated workspace with a spend limit. Who can issue it? | Agents disabled (`CLAUDE_AGENTS_ENABLED` unset) until a company key exists |

## Client (answered later via the Client Discovery Checklist)

These do not block the PoC. The Terraform inputs already cover each variant.

* Hub network, private DNS ownership, and how users route from VPN into Azure (`network_mode`, `private_dns_mode`, `ingress_mode`).
* Fabric Private Link and Block Public Internet Access tenant settings (`fabric_connectivity`).
* Azure Policy on naming, tags, SKUs, regions.
* Entra admin consent, service principal RBAC, Graph Mail.Send scoping.
* Audit retention period, regulatory requirements, whether support details may leave the tenant by email.
* Whether per user Fabric row level security is required (would change D05).

## Deferred design topics

* Phase 2 trade workflow details: states, roles, approval limits.
* Natural language Q&A approach, pending compliance review.
* Fabric workspace bootstrapping with Terraform and fabric cicd for new clients.
* Copier template for spinning up new client repos from this foundation, once a second client exists.
