# CI agents

Two Claude Code agents run in CI, outside any developer's session. The model writes text; deterministic scripts check it and decide outcomes.

| Agent | Trigger | Model may | Script decides |
|:--|:--|:--|:--|
| Docs sync | Push to `main` (except `docs/generated/**`), or manual run | Read the repo; write only `docs/generated/**` | Citations are real (`check_citations.py`); nothing outside `docs/generated/` changed; opens or updates one PR on branch `docs/sync` |
| PR review | PR into `main`, not draft, not from a fork | Read the repo and the diff | Posts comments; fails the check only on blocking hard rules (`post_review.py`) |

Human written docs in `docs/*.md` (requirements, decisions, ADRs, threat model) are never edited by an agent.

## Files

| Path | Purpose |
|:--|:--|
| `.claude/skills/docs-sync/SKILL.md` | What the docs agent generates and its rules |
| `.claude/skills/pr-review/SKILL.md` | Review rules and hard rule IDs (HR1 to HR9) |
| `.claude/skills/pr-review/findings.schema.json` | JSON schema the review output must match |
| `.claude/ci-settings.json` | CI only restrictions: no Bash, no web access, no reading `.env` or key files |
| `.claude/settings.json` | Shared restriction for all sessions: no reading `.env` or key files |
| `scripts/agents/check_citations.py` | Fails if a generated doc lacks the header, has no citations, or cites a missing file or line |
| `scripts/agents/post_review.py` | Posts findings; exit 1 on blocking hard rules (all except HR3), exit 2 if the agent run failed |
| `scripts/agents/licences.py` | Writes installed package licences for the dependency inventory |
| `.github/workflows/docs-sync.yml`, `pr-review.yml` | GitHub Actions wrappers |

## Guardrails

* **Tools:** read only tools, plus edits limited to `docs/generated/**` for the docs agent. Bash and web access are denied.
* **Untrusted input:** PR content is treated as untrusted. The review uses `CLAUDE.md`, `.claude/` and `scripts/agents/` from `main`, so a PR cannot weaken its own review.
* **Forks:** the API key is never exposed to pull requests from forks.
* **Costs:** capped by `--max-budget-usd` (a client side estimate that can overshoot slightly), job timeouts and concurrency cancellation. Each run's estimated cost is shown in the job summary.
* **Version pins:** Claude Code, uv and `actions/checkout` (by commit SHA) are pinned in the workflow `env` blocks.
* **Residual risk:** the model can miss issues or be misled by crafted content. The review is advisory evidence; a human stays responsible for each merge.

## Configuration

* **On/off switch:** repository variable `CLAUDE_AGENTS_ENABLED` set to `true`. When unset, both jobs are skipped.
* **Repository secret:** `ANTHROPIC_API_KEY`, issued from Mirador's Anthropic organisation, never a personal account (open question Q15).
* **Repository setting:** "Allow GitHub Actions to create and approve pull requests" must be on, so the docs agent can open its PR.
* **Workflow `env` blocks:** model, budget and version pins.
* **Docs PR does not trigger workflows:** PRs opened with the workflow token do not trigger other workflows, so the docs PR is not reviewed by the review agent.

## Run locally

Needs Claude Code signed in. Uses your account's usage.

```bash
claude -p "/docs-sync" --settings .claude/ci-settings.json --allowedTools "Read,Glob,Grep,Edit(./docs/generated/**),Write(./docs/generated/**)" --permission-mode dontAsk
```

```bash
uv run python scripts/agents/check_citations.py docs/generated
```

For a review, write a diff to `.agent/pr.diff` first, then run with `--output-format json --json-schema "<schema>"` and pass the output to `post_review.py --dry-run`.

## Porting to Azure Pipelines

The skills, settings and scripts are platform neutral. Only the wrappers change:

| GitHub Actions | Azure Pipelines |
|:--|:--|
| `secrets.ANTHROPIC_API_KEY` | Secret variable in a variable group, ideally linked to Key Vault |
| `pull_request` trigger | Branch policy build validation on `main` |
| `post_review.py` GitHub reviews API | Azure DevOps pull request threads API (needs a small adapter) |
| `gh pr create` | `az repos pr create` |
| `GITHUB_STEP_SUMMARY` | Pipeline logs or `##vso[task.uploadsummary]` |

Verify the Azure DevOps API details when porting.
