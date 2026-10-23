from pathlib import Path

import pytest
from agents import check_citations
from agents.check_citations import HEADER


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "views.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    return tmp_path


def _write_doc(repo: Path, name: str, body: str, header: bool = True) -> Path:
    path = repo / "docs" / name
    path.write_text((HEADER + "\n" if header else "") + body, encoding="utf-8")
    return path


def _run(repo: Path) -> int:
    return check_citations.main([str(repo / "docs"), "--root", str(repo)])


@pytest.mark.parametrize(
    "citation",
    ["(src: app/views.py)", "(src: app/views.py:3)", "(src: app/views.py:1-3)", "(src: app)"],
)
def test_valid_citations_pass(repo: Path, citation: str) -> None:
    _write_doc(repo, "a.md", f"A fact {citation}.\n")
    assert _run(repo) == 0


@pytest.mark.parametrize(
    "citation",
    [
        "(src: app/missing.py)",
        "(src: app/views.py:4)",
        "(src: app/views.py:3-1)",
        "(src: ../outside.py)",
        "(src: app:2)",
    ],
)
def test_invalid_citations_fail(repo: Path, citation: str) -> None:
    (repo.parent / "outside.py").write_text("x\n", encoding="utf-8")
    _write_doc(repo, "a.md", f"A fact {citation}.\n")
    assert _run(repo) == 1


def test_ci_working_files_cannot_be_cited(repo: Path) -> None:
    (repo / ".agent").mkdir()
    (repo / ".agent" / "changed_files.txt").write_text("a\n", encoding="utf-8")
    _write_doc(repo, "a.md", "Fact (src: .agent/changed_files.txt).\n")
    assert _run(repo) == 1


def test_several_citations_all_checked(repo: Path) -> None:
    _write_doc(repo, "a.md", "Fact (src: app/views.py:1; src: app/nope.py:2).\n")
    assert _run(repo) == 1


def test_missing_header_fails(repo: Path) -> None:
    _write_doc(repo, "a.md", "Fact (src: app/views.py:1).\n", header=False)
    assert _run(repo) == 1


def test_uncited_document_fails(repo: Path) -> None:
    _write_doc(repo, "a.md", "An unsupported claim.\n")
    assert _run(repo) == 1


def test_index_and_changelog_need_no_citations(repo: Path) -> None:
    _write_doc(repo, "README.md", "Index.\n")
    _write_doc(repo, "CHANGELOG.md", "* Change (abc1234)\n")
    assert _run(repo) == 0


def test_empty_docs_dir_fails(repo: Path) -> None:
    assert _run(repo) == 1
