"""Rule definitions, version comparison, and conflict detection logic."""

from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple

from requirements_doctor.deprecated_db import lookup_deprecated
from requirements_doctor.models import (
    AuditIssue,
    IssueCode,
    IssueSeverity,
    RequirementItem,
)


def parse_version_key(version_str: str) -> Tuple[Any, ...]:
    """
    Parses a version string into a comparable tuple without external dependencies.
    Handles semantic versions, epochs, pre-releases, and dev versions.
    """
    cleaned = version_str.strip()
    epoch = 0
    if "!" in cleaned:
        epoch_str, cleaned = cleaned.split("!", 1)
        try:
            epoch = int(epoch_str)
        except ValueError:
            pass

    # Split into numeric and alphabetic tokens
    raw_tokens = re.findall(r"(\d+|[a-zA-Z]+)", cleaned)
    parsed_tokens: List[Any] = []

    # Map pre-release tags to relative orders: a < b < rc < normal release
    pre_order = {
        "dev": -4,
        "a": -3,
        "alpha": -3,
        "b": -2,
        "beta": -2,
        "rc": -1,
        "c": -1,
        "post": 1,
    }

    for token in raw_tokens:
        if token.isdigit():
            parsed_tokens.append(int(token))
        else:
            token_lower = token.lower()
            parsed_tokens.append(pre_order.get(token_lower, token_lower))

    return (epoch, tuple(parsed_tokens))


def compare_versions(v1: str, v2: str) -> int:
    """
    Compares two version strings.
    Returns:
       -1 if v1 < v2
        0 if v1 == v2
        1 if v1 > v2
    """
    k1 = parse_version_key(v1)
    k2 = parse_version_key(v2)

    # Pad shorter sequence with 0s for integer parts comparison
    seq1, seq2 = list(k1[1]), list(k2[1])
    max_len = max(len(seq1), len(seq2))

    for i in range(max_len):
        val1 = seq1[i] if i < len(seq1) else 0
        val2 = seq2[i] if i < len(seq2) else 0

        # Handle comparisons between int and string safely
        if isinstance(val1, int) and isinstance(val2, int):
            if val1 < val2:
                return -1
            if val1 > val2:
                return 1
        else:
            s1, s2 = str(val1), str(val2)
            if s1 < s2:
                return -1
            if s1 > s2:
                return 1

    if k1[0] < k2[0]:
        return -1
    if k1[0] > k2[0]:
        return 1

    return 0


def version_satisfies_op(ver: str, op: str, target: str) -> bool:
    """Evaluates whether version `ver` satisfies `op target`."""
    cmp = compare_versions(ver, target)

    if op in ("==", "==="):
        return cmp == 0
    if op == "!=":
        return cmp != 0
    if op == "<=":
        return cmp <= 0
    if op == ">=":
        return cmp >= 0
    if op == "<":
        return cmp < 0
    if op == ">":
        return cmp > 0
    if op == "~=":
        # Compatible release: ~= X.Y means >= X.Y and == X.*
        if cmp < 0:
            return False
        parts = target.split(".")
        if len(parts) > 1:
            # Prefix must match all parts except last
            prefix = ".".join(parts[:-1])
            return ver.startswith(prefix)
        return True

    return True


def are_specs_conflicting(specs1: Sequence[Tuple[str, str]], specs2: Sequence[Tuple[str, str]]) -> Tuple[bool, Optional[str]]:
    """
    Determines if two sets of version specifications are contradictory.
    Returns (True, reason) if conflicting, (False, None) if compatible.
    """
    # 1. Multiple exact pins with different versions
    exacts1 = [ver for op, ver in specs1 if op in ("==", "===")]
    exacts2 = [ver for op, ver in specs2 if op in ("==", "===")]

    if exacts1 and exacts2:
        for e1 in exacts1:
            for e2 in exacts2:
                if compare_versions(e1, e2) != 0:
                    return (
                        True,
                        f"Incompatible exact pins: '=={e1}' vs '=={e2}'.",
                    )

    # 2. Exact pin on one side that violates ranges on the other side
    if exacts1:
        for e1 in exacts1:
            for op2, ver2 in specs2:
                if not version_satisfies_op(e1, op2, ver2):
                    return (
                        True,
                        f"Pin '=={e1}' violates constraint '{op2}{ver2}'.",
                    )

    if exacts2:
        for e2 in exacts2:
            for op1, ver1 in specs1:
                if not version_satisfies_op(e2, op1, ver1):
                    return (
                        True,
                        f"Pin '=={e2}' violates constraint '{op1}{ver1}'.",
                    )

    # 3. Disjoint ranges: e.g. < 2.0 and >= 3.0
    for op1, ver1 in specs1:
        for op2, ver2 in specs2:
            if op1 in ("<", "<=") and op2 in (">", ">="):
                # e.g., < 2.0 and >= 2.0 or > 2.0
                cmp = compare_versions(ver1, ver2)
                if cmp < 0 or (cmp == 0 and (op1 == "<" or op2 == ">")):
                    return (
                        True,
                        f"Disjoint version range: '{op1}{ver1}' and '{op2}{ver2}'.",
                    )
            elif op1 in (">", ">=") and op2 in ("<", "<="):
                cmp = compare_versions(ver2, ver1)
                if cmp < 0 or (cmp == 0 and (op2 == "<" or op1 == ">")):
                    return (
                        True,
                        f"Disjoint version range: '{op1}{ver1}' and '{op2}{ver2}'.",
                    )

    return (False, None)


def check_unpinned_or_loose(
    item: RequirementItem,
    strict_pinning: bool = False,
    allow_loose: bool = False,
) -> Optional[AuditIssue]:
    """Validates if a requirement has missing or loose version pinning."""
    if not item.is_package_requirement() or item.url:
        return None

    name = item.name or "package"

    # 1. Completely unpinned
    if not item.specs:
        severity = IssueSeverity.ERROR if strict_pinning else IssueSeverity.WARNING
        return AuditIssue(
            code=IssueCode.UNPINNED_DEPENDENCY,
            severity=severity,
            message=f"Package '{name}' has no version pin specified.",
            line_number=item.line_number,
            package_name=name,
            suggestion=f"Pin to an exact or bounded version (e.g., '{name}==1.0.0').",
        )

    if allow_loose and not strict_pinning:
        return None

    # 2. Strict pinning check: must have exact `==` or `===`
    operators = [op for op, _ in item.specs]
    has_exact = any(op in ("==", "===") for op in operators)

    if strict_pinning and not has_exact:
        return AuditIssue(
            code=IssueCode.LOOSE_PIN,
            severity=IssueSeverity.ERROR,
            message=f"Package '{name}' has non-exact pin '{item.spec_str}'. Strict pinning requires '=='.",
            line_number=item.line_number,
            package_name=name,
            suggestion=f"Pin exact version with '==' (e.g., '{name}==...').",
        )

    # 3. Unbounded lower/exclusion pin: e.g. >=2.0 without any upper limit (< or <=)
    has_upper = any(op in ("<", "<=") for op in operators)
    has_compatible = any(op == "~=" for op in operators)
    has_lower_only = any(op in (">=", ">") for op in operators) and not (has_upper or has_compatible or has_exact)

    if has_lower_only:
        return AuditIssue(
            code=IssueCode.LOOSE_PIN,
            severity=IssueSeverity.WARNING,
            message=f"Package '{name}' has unbounded lower pin '{item.spec_str}', which can cause breaking changes on major releases.",
            line_number=item.line_number,
            package_name=name,
            suggestion=f"Add an upper bound or exact pin, e.g. '{name}>=X.Y,<(X+1).0'.",
        )

    return None


def check_deprecated(item: RequirementItem) -> Optional[AuditIssue]:
    """Checks if requirement uses a known deprecated, dummy, or stdlib package."""
    if not item.canonical_name:
        return None

    dep_info = lookup_deprecated(item.canonical_name)
    if not dep_info:
        return None

    name = item.name or item.canonical_name
    if dep_info.is_stdlib:
        suggestion = "Remove this entry because it is part of Python's standard library."
    elif dep_info.replacement:
        suggestion = f"Replace '{name}' with '{dep_info.replacement}'."
    else:
        suggestion = "Remove this dependency."

    return AuditIssue(
        code=IssueCode.DEPRECATED_PACKAGE,
        severity=IssueSeverity.WARNING,
        message=dep_info.reason,
        line_number=item.line_number,
        package_name=name,
        suggestion=suggestion,
    )


def check_url(item: RequirementItem) -> List[AuditIssue]:
    """Checks for direct URLs or insecure protocols."""
    issues: List[AuditIssue] = []
    if not item.url:
        return issues

    url = item.url.lower()

    # Insecure URL check
    if url.startswith("http://") or url.startswith("git://") or "git://@" in url:
        issues.append(
            AuditIssue(
                code=IssueCode.INSECURE_URL,
                severity=IssueSeverity.ERROR,
                message=f"Insecure protocol detected in URL: '{item.url}'. Use HTTPS or SSH instead.",
                line_number=item.line_number,
                package_name=item.name,
                suggestion="Change protocol to 'https://' or 'git+ssh://'.",
            )
        )

    # Direct URL warning (VCS or direct tarball)
    issues.append(
        AuditIssue(
            code=IssueCode.DIRECT_URL,
            severity=IssueSeverity.WARNING,
            message=f"Direct URL dependency detected: '{item.url}'. Direct URLs may cause build non-reproducibility.",
            line_number=item.line_number,
            package_name=item.name,
            suggestion="Prefer standard PyPI packages or vendor dependencies cleanly.",
        )
    )

    return issues
