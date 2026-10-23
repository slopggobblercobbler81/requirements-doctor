"""requirements-doctor: Production-grade CLI and library to audit, lint, deduplicate, and clean requirements.txt files."""

__version__ = "0.1.0"

from requirements_doctor.auditor import (
    RequirementsAuditor,
    audit_content,
    audit_file,
)
from requirements_doctor.fixer import (
    RequirementsFixer,
    fix_content,
    fix_file,
)
from requirements_doctor.models import (
    AuditIssue,
    AuditReport,
    IssueCode,
    IssueSeverity,
    RequirementItem,
)
from requirements_doctor.parser import (
    RequirementsParser,
    canonicalize_name,
)

__all__ = [
    "__version__",
    "RequirementsAuditor",
    "RequirementsFixer",
    "RequirementsParser",
    "audit_content",
    "audit_file",
    "fix_content",
    "fix_file",
    "canonicalize_name",
    "AuditIssue",
    "AuditReport",
    "IssueCode",
    "IssueSeverity",
    "RequirementItem",
]
