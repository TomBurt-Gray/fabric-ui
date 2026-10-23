import json
from pathlib import Path

import pytest
from agents import post_review
from agents.post_review import Finding, commentable_lines

DIFF = """\
diff --git a/app/views.py b/app/views.py
--- a/app/views.py
+++ b/app/views.py
@@ -1,3 +1,4 @@
 import os
-OLD = 1
+NEW = 1
+SECRET = "x"
 def view(): ...
diff --git a/app/gone.py b/app/gone.py
--- a/app/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-x = 1
"""


def _finding(**overrides: object) -> dict:
    base = {
        "path": "app/views.py",
        "line": 3,
        "category": "bug",
        "rule_id": None,
        "severity": "medium",
        "title": "Title",
        "detail": "Detail",
        "suggestion": "Fix",
    }
    return base | overrides


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "views.py").write_text("x\n" * 10, encoding="utf-8")
    (tmp_path / "pr.diff").write_text(DIFF, encoding="utf-8")
    return tmp_path


def _run(repo: Path, findings: list[dict], **result: object) -> int:
    payload = {"is_error": False, "structured_output": {"summary": "S", "findings": findings}}
    payload |= result
    (repo / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    return post_review.main(
        [
            "--result",
            str(repo / "result.json"),
            "--diff",
            str(repo / "pr.diff"),
            "--root",
            str(repo),
            "--dry-run",
        ]
    )


def test_commentable_lines_tracks_new_side() -> None:
    assert commentable_lines(DIFF) == {"app/views.py": {1, 2, 3, 4}}


def test_no_findings_passes(repo: Path) -> None:
    assert _run(repo, []) == 0


def test_bug_does_not_block(repo: Path) -> None:
    assert _run(repo, [_finding()]) == 0


def test_blocking_hard_rule_fails(repo: Path) -> None:
    assert _run(repo, [_finding(category="hard_rule", rule_id="HR1", severity="high")]) == 1


def test_dependency_rule_does_not_block(repo: Path) -> None:
    assert _run(repo, [_finding(category="hard_rule", rule_id="HR3")]) == 0


def test_finding_on_missing_file_is_discarded(repo: Path) -> None:
    finding = _finding(path="app/invented.py", category="hard_rule", rule_id="HR6")
    assert _run(repo, [finding]) == 0


def test_agent_error_exits_2(repo: Path) -> None:
    assert _run(repo, [], is_error=True) == 2


def test_missing_structured_output_exits_2(repo: Path) -> None:
    assert _run(repo, [], structured_output=None) == 2


def test_schema_mismatch_exits_2(repo: Path) -> None:
    assert _run(repo, [{"path": "app/views.py"}]) == 2


def test_markdown_marks_blocking() -> None:
    finding = Finding(**_finding(category="hard_rule", rule_id="HR6"))
    assert "[HR6]" in finding.markdown()
    assert "blocks merge" in finding.markdown()
