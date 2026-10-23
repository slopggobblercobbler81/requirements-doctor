"""Additional edge case tests for requirements-doctor."""

import pytest
from pathlib import Path
from requirements_doctor.auditor import audit_content, audit_file
from requirements_doctor.fixer import fix_content
from requirements_doctor.models import IssueCode, IssueSeverity
from requirements_doctor.cli import main, discover_requirement_files


def test_empty_content_audit_and_fix():
    report = audit_content("")
    assert report.is_clean
    assert report.total_requirements == 0

    fixed = fix_content("")
    assert fixed == "\n"


def test_comments_only_audit_and_fix():
    content = "# Just a header\n# Another comment\n"
    report = audit_content(content)
    assert report.is_clean
    assert report.total_requirements == 0

    fixed = fix_content(content)
    assert "# Just a header" in fixed
    assert "# Another comment" in fixed


def test_mixed_case_duplicate_detection():
    content = """
Requests==2.28.1
requests==2.28.1
"""
    report = audit_content(content)
    assert not report.is_clean
    dup_issues = [i for i in report.issues if i.code == IssueCode.DUPLICATE_ENTRY]
    assert len(dup_issues) == 1


def test_conflicting_direct_url_and_pypi():
    content = """
requests==2.28.1
requests @ https://github.com/psf/requests/archive/master.zip
"""
    report = audit_content(content)
    assert report.has_errors
    conflict_issues = [i for i in report.issues if i.code == IssueCode.CONFLICTING_SPEC]
    assert len(conflict_issues) == 1
    assert "Conflicting sources" in conflict_issues[0].message


def test_fix_resolves_multiple_bounds():
    content = """
pkg>=1.0.0
pkg>=1.5.0
pkg<=3.0.0
pkg<=2.5.0
"""
    fixed = fix_content(content)
    # Highest lower bound is 1.5.0, lowest upper bound is 2.5.0
    assert "pkg>=1.5.0,<=2.5.0" in fixed


def test_cli_verbose_output(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.28.1\n", encoding="utf-8")

    code = main([str(req_file), "-v"])
    assert code == 0
    captured = capsys.readouterr()
    assert "All requirements healthy" in captured.out


def test_cli_discover_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("pytest==7.0.0\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("flake8==5.0.0\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("something\n", encoding="utf-8")

    found = discover_requirement_files()
    assert len(found) == 2
    filenames = [p.name for p in found]
    assert "requirements.txt" in filenames
    assert "requirements-dev.txt" in filenames
