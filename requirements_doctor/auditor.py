"""Auditor module that inspects requirements and generates comprehensive reports."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

from requirements_doctor.models import (
    AuditIssue,
    AuditReport,
    IssueCode,
    IssueSeverity,
    RequirementItem,
)
from requirements_doctor.parser import RequirementsParser
from requirements_doctor.rules import (
    are_specs_conflicting,
    check_deprecated,
    check_unpinned_or_loose,
    check_url,
)


class RequirementsAuditor:
    """Audits requirement items against health, security, and reproducibility rules."""

    def __init__(self, strict_pinning: bool = False, allow_loose: bool = False):
        self.strict_pinning = strict_pinning
        self.allow_loose = allow_loose

    def audit_items(self, items: List[RequirementItem], file_path: str = "<memory>") -> AuditReport:
        """Audits a parsed list of RequirementItems and returns an AuditReport."""
        issues: List[AuditIssue] = []
        package_groups: Dict[str, List[RequirementItem]] = defaultdict(list)
        total_reqs = 0

        # Pass 1: Individual item checks and grouping by package name
        for item in items:
            if not item.is_package_requirement():
                continue

            total_reqs += 1

            # Check individual rules
            loose_issue = check_unpinned_or_loose(
                item,
                strict_pinning=self.strict_pinning,
                allow_loose=self.allow_loose,
            )
            if loose_issue:
                issues.append(loose_issue)

            dep_issue = check_deprecated(item)
            if dep_issue:
                issues.append(dep_issue)

            url_issues = check_url(item)
            issues.extend(url_issues)

            if item.canonical_name:
                package_groups[item.canonical_name].append(item)

        # Pass 2: Duplicate and conflict detection
        for canonical_name, group in package_groups.items():
            if len(group) <= 1:
                continue

            # We have duplicates!
            lines_str = ", ".join(f"line {it.line_number} ('{it.raw.strip()}')" for it in group)
            display_name = group[0].name or canonical_name

            issues.append(
                AuditIssue(
                    code=IssueCode.DUPLICATE_ENTRY,
                    severity=IssueSeverity.WARNING,
                    message=f"Duplicate entries found for package '{display_name}' across {lines_str}.",
                    line_number=group[0].line_number,
                    package_name=display_name,
                    suggestion=f"Consolidate duplicate '{display_name}' entries into a single requirement pin.",
                )
            )

            # Check for conflicting specifications between pairs of duplicate entries
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    item_a, item_b = group[i], group[j]
                    # Direct URLs conflict with standard PyPI or different URLs
                    if item_a.url or item_b.url:
                        if item_a.url != item_b.url:
                            issues.append(
                                AuditIssue(
                                    code=IssueCode.CONFLICTING_SPEC,
                                    severity=IssueSeverity.ERROR,
                                    message=f"Conflicting sources for '{display_name}': line {item_a.line_number} vs line {item_b.line_number}.",
                                    line_number=item_b.line_number,
                                    package_name=display_name,
                                    suggestion="Standardize on a single source or repository URL.",
                                )
                            )
                        continue

                    # If both have specs, check if specs conflict
                    if item_a.specs and item_b.specs:
                        conflicting, reason = are_specs_conflicting(item_a.specs, item_b.specs)
                        if conflicting:
                            issues.append(
                                AuditIssue(
                                    code=IssueCode.CONFLICTING_SPEC,
                                    severity=IssueSeverity.ERROR,
                                    message=f"Conflicting version specifications for '{display_name}' on line {item_a.line_number} ('{item_a.spec_str}') and line {item_b.line_number} ('{item_b.spec_str}'). {reason}",
                                    line_number=item_b.line_number,
                                    package_name=display_name,
                                    suggestion="Resolve conflicting pins to a single compatible version.",
                                )
                            )

        # Sort issues by line number, then severity
        severity_order = {IssueSeverity.ERROR: 0, IssueSeverity.WARNING: 1, IssueSeverity.INFO: 2}
        issues.sort(key=lambda x: (x.line_number or 0, severity_order[x.severity]))

        return AuditReport(
            file_path=str(file_path),
            total_lines=len(items),
            total_requirements=total_reqs,
            issues=issues,
        )


def audit_content(
    content: str,
    file_path: str = "<memory>",
    strict_pinning: bool = False,
    allow_loose: bool = False,
) -> AuditReport:
    """Parses and audits a requirements string."""
    items = RequirementsParser.parse_content(content)
    auditor = RequirementsAuditor(strict_pinning=strict_pinning, allow_loose=allow_loose)
    return auditor.audit_items(items, file_path=file_path)


def audit_file(
    file_path: Union[str, Path],
    strict_pinning: bool = False,
    allow_loose: bool = False,
) -> AuditReport:
    """Reads and audits a requirements file from disk."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Requirements file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return audit_content(
        content,
        file_path=str(path),
        strict_pinning=strict_pinning,
        allow_loose=allow_loose,
    )
