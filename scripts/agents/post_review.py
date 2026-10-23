"""Post the PR review agent's findings to GitHub and decide whether the check fails.

The model only reports findings. This script, not the model, decides the outcome:
findings that breach a blocking hard rule fail the check (exit 1). Findings on files
that do not exist are discarded. Exit 2 means the agent run itself failed.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# HR3 (new dependency) is reported but never blocks: the owner may have approved it.
BLOCKING_RULES = frozenset({"HR1", "HR2", "HR4", "HR5", "HR6", "HR7", "HR8", "HR9"})
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class ReviewError(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    rule_id: str | None
    severity: str
    title: str
    detail: str
    suggestion: str

    @property
    def blocking(self) -> bool:
        return self.category == "hard_rule" and self.rule_id in BLOCKING_RULES

    def markdown(self) -> str:
        label = f"[{self.rule_id}] " if self.rule_id else ""
        outcome = ", blocks merge" if self.blocking else ""
        return (
            f"**{label}{self.title}** ({self.severity}, {self.category.replace('_', ' ')}"
            f"{outcome})\n\n{self.detail}\n\nSuggestion: {self.suggestion}"
        )


def load_findings(result_path: Path) -> tuple[str, list[Finding]]:
    # utf-8-sig tolerates the byte order mark Windows PowerShell adds on local runs.
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    if result.get("is_error"):
        raise ReviewError(f"agent run failed: {result.get('subtype') or result.get('result')}")
    output = result.get("structured_output")
    if not isinstance(output, dict):
        raise ReviewError("agent returned no structured output")
    try:
        findings = [Finding(**item) for item in output["findings"]]
        return str(output["summary"]), findings
    except (KeyError, TypeError) as exc:
        raise ReviewError(f"structured output does not match the schema: {exc}") from exc


def commentable_lines(diff: str) -> dict[str, set[int]]:
    """Map each file in a unified diff to the new-side line numbers GitHub can comment on."""
    lines: dict[str, set[int]] = {}
    current: set[int] | None = None
    number = 0
    for row in diff.splitlines():
        if row.startswith("+++ "):
            path = row[4:].removeprefix("b/")
            current = None if path == "/dev/null" else lines.setdefault(path, set())
        elif match := HUNK.match(row):
            number = int(match.group(1))
        elif current is not None and row[:1] in {"+", " "} and not row.startswith("+++"):
            current.add(number)
            number += 1
    return lines


def build_body(summary: str, findings: list[Finding], general: list[Finding], dropped: int) -> str:
    blocking = [f for f in findings if f.blocking]
    parts = ["## PR review agent", "", summary, ""]
    if blocking:
        parts.append(f"**{len(blocking)} blocking hard rule finding(s).** The check fails.")
    else:
        parts.append(f"{len(findings)} finding(s), none blocking.")
    if general:
        parts += ["", "### Findings outside the diff", ""]
        parts += [f"`{f.path}:{f.line}` {f.markdown()}\n" for f in general]
    if dropped:
        parts += ["", f"{dropped} finding(s) discarded: cited files do not exist."]
    parts += ["", "_Automated review. A human reviewer remains responsible for the merge._"]
    return "\n".join(parts)


def post_review(repo: str, pr: int, commit: str, body: str, comments: list[dict]) -> None:
    payload = {"commit_id": commit, "event": "COMMENT", "body": body, "comments": comments}
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls/{pr}/reviews",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--repo")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--commit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="print instead of posting")
    args = parser.parse_args(argv)

    try:
        summary, raw = load_findings(args.result)
    except (ReviewError, json.JSONDecodeError, OSError) as exc:
        print(f"Review failed: {exc}", file=sys.stderr)
        return 2

    findings = [f for f in raw if (args.root / f.path).is_file()]
    on_diff = commentable_lines(args.diff.read_text(encoding="utf-8-sig"))
    inline = [f for f in findings if f.line in on_diff.get(f.path, set())]
    general = [f for f in findings if f not in inline]
    body = build_body(summary, findings, general, len(raw) - len(findings))
    comments = [
        {"path": f.path, "line": f.line, "side": "RIGHT", "body": f.markdown()} for f in inline
    ]

    if args.dry_run:
        print(body)
        print(json.dumps(comments, indent=2))
    else:
        try:
            post_review(args.repo, args.pr, args.commit, body, comments)
        except urllib.error.HTTPError as exc:
            if exc.code != 422 or not comments:
                raise
            # GitHub rejected an inline position: fall back to a single summary comment.
            everything = build_body(summary, findings, findings, len(raw) - len(findings))
            post_review(args.repo, args.pr, args.commit, everything, [])

    if summary_file := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(body + "\n")
    return 1 if any(f.blocking for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
