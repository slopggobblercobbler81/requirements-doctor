"""Data models for requirements-doctor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class IssueSeverity(str, Enum):
    """Severity levels for audit findings."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCode(str, Enum):
    """Machine-readable codes for audit issues."""
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    CONFLICTING_SPEC = "CONFLICTING_SPEC"
    UNPINNED_DEPENDENCY = "UNPINNED_DEPENDENCY"
    LOOSE_PIN = "LOOSE_PIN"
    DEPRECATED_PACKAGE = "DEPRECATED_PACKAGE"
    DIRECT_URL = "DIRECT_URL"
    INSECURE_URL = "INSECURE_URL"
    SYNTAX_ERROR = "SYNTAX_ERROR"


@dataclass
class RequirementItem:
    """Represents a single parsed line in a requirements file."""
    raw: str
    line_number: int
    is_empty: bool = False
    is_comment: bool = False
    is_flag: bool = False
    flag_type: Optional[str] = None  # e.g., "-r", "-i", "-e"
    flag_value: Optional[str] = None
    name: Optional[str] = None
    canonical_name: Optional[str] = None
    extras: List[str] = field(default_factory=list)
    specs: List[Tuple[str, str]] = field(default_factory=list)  # e.g. [("==", "2.28.1")]
    spec_str: Optional[str] = None  # e.g. "==2.28.1"
    environment_marker: Optional[str] = None  # e.g. "python_version >= '3.8'"
    inline_comment: Optional[str] = None
    url: Optional[str] = None
    is_editable: bool = False

    def is_package_requirement(self) -> bool:
        """Returns True if this item represents a concrete package requirement."""
        return not (self.is_empty or self.is_comment or (self.is_flag and not self.name))

    def format_line(self) -> str:
        """Formats the requirement item back into a clean string representation."""
        if self.is_empty:
            return ""
        if self.is_comment:
            return self.raw.strip()
        if self.is_flag and not self.name:
            return self.raw.strip()

        parts: List[str] = []
        if self.is_editable:
            parts.append("-e ")

        if self.url and not self.name:
            parts.append(self.url)
        else:
            name_part = self.name or ""
            if self.extras:
                name_part += f"[{','.join(sorted(self.extras))}]"
            parts.append(name_part)

            if self.specs:
                spec_parts = [f"{op}{ver}" for op, ver in self.specs]
                parts.append(",".join(spec_parts))
            elif self.url:
                parts.append(f" @ {self.url}")

        if self.environment_marker:
            parts.append(f"; {self.environment_marker}")

        line = "".join(parts)
        if self.inline_comment:
            line += f"  # {self.inline_comment}"

        return line


@dataclass
class AuditIssue:
    """Represents a diagnosed problem in a requirements file."""
    code: IssueCode
    severity: IssueSeverity
    message: str
    line_number: Optional[int] = None
    package_name: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "line_number": self.line_number,
            "package_name": self.package_name,
            "suggestion": self.suggestion,
        }


@dataclass
class AuditReport:
    """Comprehensive report produced by auditing one requirements file."""
    file_path: str
    total_lines: int
    total_requirements: int
    issues: List[AuditIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    @property
    def infos(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.INFO]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_lines": self.total_lines,
            "total_requirements": self.total_requirements,
            "is_clean": self.is_clean,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [i.to_dict() for i in self.issues],
        }
