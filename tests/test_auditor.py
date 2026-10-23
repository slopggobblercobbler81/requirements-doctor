"""Tests for auditor and reporting logic."""

import pytest
from requirements_doctor.auditor import audit_content, audit_file
from requirements_doctor.models import IssueCode, IssueSeverity


def test_clean_requirements():
    content = """
# Clean dependencies
click==8.1.3
requests==2.28.1
urllib3==1.26.12
"""
    report = audit_content(content)
    assert report.is_clean
    assert len(report.issues) == 0
    assert report.total_requirements == 3


def test_detect_duplicate_entries():
    content = """
requests==2.28.1
flask==2.2.0
requests==2.28.1
"""
    report = audit_content(content)
    assert not report.is_clean
    dup_issues = [i for i in report.issues if i.code == IssueCode.DUPLICATE_ENTRY]
    assert len(dup_issues) == 1
    assert "requests" in dup_issues[0].message


def test_detect_conflicting_spec():
    content = """
requests>=2.28.0
flask==2.2.0
requests==2.25.1
"""
    report = audit_content(content)
    assert report.has_errors
    conflict_issues = [i for i in report.issues if i.code == IssueCode.CONFLICTING_SPEC]
    assert len(conflict_issues) == 1
    assert "Conflicting version specifications" in conflict_issues[0].message


def test_detect_unpinned_and_loose():
    content = """
click
fastapi>=0.85.0
"""
    report = audit_content(content)
    assert any(i.code == IssueCode.UNPINNED_DEPENDENCY for i in report.issues)
    assert any(i.code == IssueCode.LOOSE_PIN for i in report.issues)


def test_detect_deprecated_and_urls():
    content = """
sklearn==0.0
git://github.com/example/repo.git#egg=example
"""
    report = audit_content(content)
    assert any(i.code == IssueCode.DEPRECATED_PACKAGE for i in report.issues)
    assert any(i.code == IssueCode.INSECURE_URL for i in report.issues)
    assert any(i.code == IssueCode.DIRECT_URL for i in report.issues)


def test_audit_file(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.28.1\nrequests==2.25.0\n", encoding="utf-8")

    report = audit_file(req_file)
    assert not report.is_clean
    assert report.has_errors
    data = report.to_dict()
    assert data["total_requirements"] == 2
    assert not data["is_clean"]


def test_audit_file_not_found():
    with pytest.raises(FileNotFoundError):
        audit_file("non_existent_requirements_file_12345.txt")
