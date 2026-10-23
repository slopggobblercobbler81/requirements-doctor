"""Tests for rules, version comparison, and conflict logic."""

import pytest
from requirements_doctor.models import IssueCode, IssueSeverity, RequirementItem
from requirements_doctor.rules import (
    are_specs_conflicting,
    check_deprecated,
    check_unpinned_or_loose,
    check_url,
    compare_versions,
    parse_version_key,
    version_satisfies_op,
)


def test_version_key_and_comparison():
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.2.0", "1.10.0") == -1
    assert compare_versions("2.0.0", "1.99.9") == 1
    assert compare_versions("2.0.0rc1", "2.0.0") == -1
    assert compare_versions("2.0.0a1", "2.0.0b1") == -1
    assert compare_versions("1.0.0.post1", "1.0.0") == 1


def test_version_satisfies_op():
    assert version_satisfies_op("2.28.1", "==", "2.28.1")
    assert not version_satisfies_op("2.28.1", "==", "2.25.0")
    assert version_satisfies_op("2.28.1", ">=", "2.25.0")
    assert not version_satisfies_op("2.25.0", ">=", "2.28.0")
    assert version_satisfies_op("1.5.0", "<", "2.0.0")
    assert version_satisfies_op("2.28.1", "!=", "2.25.0")
    assert version_satisfies_op("2.28.1", "~=", "2.28.0")
    assert not version_satisfies_op("3.0.0", "~=", "2.28.0")


def test_are_specs_conflicting():
    # Identical exact pins - compatible
    conflicting, _ = are_specs_conflicting([("==", "2.28.0")], [("==", "2.28.0")])
    assert not conflicting

    # Different exact pins - conflicting
    conflicting, reason = are_specs_conflicting([("==", "2.28.0")], [("==", "2.25.1")])
    assert conflicting
    assert "Incompatible exact pins" in reason

    # Exact pin violating a range - conflicting
    conflicting, reason = are_specs_conflicting([(">=", "2.28.0")], [("==", "2.25.1")])
    assert conflicting
    assert "violates constraint" in reason

    # Compatible exact pin and range - compatible
    conflicting, _ = are_specs_conflicting([(">=", "2.20.0")], [("==", "2.25.1")])
    assert not conflicting

    # Disjoint ranges - conflicting
    conflicting, reason = are_specs_conflicting([("<", "2.0.0")], [(">=", "3.0.0")])
    assert conflicting
    assert "Disjoint version range" in reason


def test_check_unpinned():
    item = RequirementItem(
        raw="requests",
        line_number=1,
        name="requests",
        canonical_name="requests",
        specs=[],
    )
    issue = check_unpinned_or_loose(item)
    assert issue is not None
    assert issue.code == IssueCode.UNPINNED_DEPENDENCY
    assert issue.severity == IssueSeverity.WARNING


def test_check_loose_pin():
    # Unbounded lower pin
    item = RequirementItem(
        raw="requests>=2.28.0",
        line_number=1,
        name="requests",
        canonical_name="requests",
        specs=[(">=", "2.28.0")],
        spec_str=">=2.28.0",
    )
    issue = check_unpinned_or_loose(item)
    assert issue is not None
    assert issue.code == IssueCode.LOOSE_PIN
    assert issue.severity == IssueSeverity.WARNING

    # Bounded pin: no warning under standard mode
    bounded_item = RequirementItem(
        raw="requests>=2.28.0,<3.0.0",
        line_number=1,
        name="requests",
        canonical_name="requests",
        specs=[(">=", "2.28.0"), ("<", "3.0.0")],
        spec_str=">=2.28.0,<3.0.0",
    )
    assert check_unpinned_or_loose(bounded_item) is None

    # Strict pinning mode flags bounded non-exact pins
    strict_issue = check_unpinned_or_loose(bounded_item, strict_pinning=True)
    assert strict_issue is not None
    assert strict_issue.code == IssueCode.LOOSE_PIN
    assert strict_issue.severity == IssueSeverity.ERROR

    # Allow loose suppresses loose warning
    assert check_unpinned_or_loose(item, allow_loose=True) is None


def test_check_deprecated_packages():
    # Deprecated package with replacement
    sklearn_item = RequirementItem(
        raw="sklearn==0.0",
        line_number=1,
        name="sklearn",
        canonical_name="sklearn",
        specs=[("==", "0.0")],
    )
    issue = check_deprecated(sklearn_item)
    assert issue is not None
    assert issue.code == IssueCode.DEPRECATED_PACKAGE
    assert "scikit-learn" in issue.suggestion

    # Deprecated stdlib package
    typing_item = RequirementItem(
        raw="typing==3.7.4.3",
        line_number=2,
        name="typing",
        canonical_name="typing",
        specs=[("==", "3.7.4.3")],
    )
    issue_stdlib = check_deprecated(typing_item)
    assert issue_stdlib is not None
    assert issue_stdlib.code == IssueCode.DEPRECATED_PACKAGE
    assert "standard library" in issue_stdlib.suggestion


def test_check_url_insecure_and_direct():
    insecure_item = RequirementItem(
        raw="git://github.com/psf/requests.git",
        line_number=1,
        name="requests",
        url="git://github.com/psf/requests.git",
    )
    issues = check_url(insecure_item)
    assert any(i.code == IssueCode.INSECURE_URL for i in issues)
    assert any(i.code == IssueCode.DIRECT_URL for i in issues)

    secure_item = RequirementItem(
        raw="git+https://github.com/psf/requests.git",
        line_number=2,
        name="requests",
        url="git+https://github.com/psf/requests.git",
    )
    issues_sec = check_url(secure_item)
    assert not any(i.code == IssueCode.INSECURE_URL for i in issues_sec)
    assert any(i.code == IssueCode.DIRECT_URL for i in issues_sec)
