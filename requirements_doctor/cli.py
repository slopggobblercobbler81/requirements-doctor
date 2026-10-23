"""CLI interface for requirements-doctor."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from requirements_doctor import __version__
from requirements_doctor.auditor import audit_file
from requirements_doctor.fixer import fix_file
from requirements_doctor.models import AuditReport, IssueSeverity

# ANSI colors for terminal output
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def supports_color() -> bool:
    """Detects whether standard output supports ANSI colors."""
    return sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    """Wraps text with ANSI color code if stdout supports color."""
    if supports_color():
        return f"{color}{text}{COLOR_RESET}"
    return text


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="requirements-doctor",
        description="Audit, lint, deduplicate, and clean requirements.txt files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Audit requirements.txt and fail if issues are detected
  requirements-doctor requirements.txt

  # Automatically fix, deduplicate, and sort requirements in-place
  requirements-doctor --fix requirements.txt

  # Show unified diff without modifying files
  requirements-doctor --diff requirements.txt

  # Audit with strict production pinning (all packages must use ==)
  requirements-doctor --strict-pinning requirements.txt

  # Output report as JSON for CI/CD integration
  requirements-doctor --check --json requirements.txt
""",
    )

    parser.add_argument(
        "files",
        nargs="*",
        default=[],
        help="Path to requirements file(s). If omitted, searches for requirements*.txt in current directory.",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="Audit requirement files and exit with non-zero if issues are found (default behavior).",
    )
    mode_group.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="Automatically fix issues, deduplicate entries, modernize deprecated packages, and sort.",
    )
    mode_group.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help="Display unified diff of proposed fixes without modifying files.",
    )

    parser.add_argument(
        "--strict-pinning",
        action="store_true",
        default=False,
        help="Enforce exact pinning ('==') for all dependencies. Flags '>=' and '~=' as errors.",
    )

    parser.add_argument(
        "--allow-loose",
        action="store_true",
        default=False,
        help="Allow loose or unbounded version pins without issuing warnings.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output audit reports as machine-readable JSON.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Display verbose diagnostics and info messages.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write fixed requirements to specified output file instead of modifying in-place.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"requirements-doctor {__version__}",
    )

    return parser


def discover_requirement_files() -> List[Path]:
    """Finds requirement files in the current working directory."""
    cwd = Path.cwd()
    patterns = ["requirements*.txt", "*requirements.txt"]
    found: List[Path] = []
    for pattern in patterns:
        for p in cwd.glob(pattern):
            if p.is_file() and p not in found:
                found.append(p)
    return sorted(found)


def format_text_report(report: AuditReport, verbose: bool = False) -> str:
    """Formats an AuditReport into human-friendly colored terminal output."""
    lines: List[str] = []
    header = f"Auditing {report.file_path} ({report.total_requirements} packages, {report.total_lines} lines):"
    lines.append(colorize(header, COLOR_BOLD))

    if report.is_clean:
        lines.append(colorize("  ✓ All requirements healthy! No issues detected.", COLOR_GREEN))
        return "\n".join(lines)

    for issue in report.issues:
        if issue.severity == IssueSeverity.INFO and not verbose:
            continue

        if issue.severity == IssueSeverity.ERROR:
            badge = colorize("[ERROR]", COLOR_RED)
        elif issue.severity == IssueSeverity.WARNING:
            badge = colorize("[WARN] ", COLOR_YELLOW)
        else:
            badge = colorize("[INFO] ", COLOR_CYAN)

        loc = f"line {issue.line_number}: " if issue.line_number is not None else ""
        lines.append(f"  {badge} {loc}{issue.message}")
        if issue.suggestion:
            suggestion_text = colorize(f"         Suggestion: {issue.suggestion}", COLOR_CYAN)
            lines.append(suggestion_text)

    # Summary footer
    err_count = len(report.errors)
    warn_count = len(report.warnings)
    summary_parts = []
    if err_count:
        summary_parts.append(colorize(f"{err_count} error{'s' if err_count != 1 else ''}", COLOR_RED))
    if warn_count:
        summary_parts.append(colorize(f"{warn_count} warning{'s' if warn_count != 1 else ''}", COLOR_YELLOW))

    lines.append(f"  Summary: {', '.join(summary_parts)}")
    return "\n".join(lines)


def run_diff(file_path: Path) -> str:
    """Computes unified diff for a requirement file."""
    from requirements_doctor.fixer import fix_content

    original = file_path.read_text(encoding="utf-8")
    fixed = fix_content(original)

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"a/{file_path.name}",
        tofile=f"b/{file_path.name}",
    )
    return "".join(diff)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the requirements-doctor CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    target_paths: List[Path] = [Path(p) for p in args.files]
    if not target_paths:
        target_paths = discover_requirement_files()

    if not target_paths:
        if not args.json:
            print(
                colorize("No requirements files specified or found in current directory.", COLOR_YELLOW),
                file=sys.stderr,
            )
            print("Usage: requirements-doctor [path/to/requirements.txt]", file=sys.stderr)
        else:
            print(json.dumps({"error": "No requirement files found", "reports": []}))
        return 1

    # Diff mode
    if args.diff:
        has_diff = False
        for path in target_paths:
            if not path.is_file():
                print(colorize(f"File not found: {path}", COLOR_RED), file=sys.stderr)
                return 1
            diff_text = run_diff(path)
            if diff_text:
                has_diff = True
                print(diff_text, end="")
        return 1 if has_diff else 0

    # Fix mode
    if args.fix:
        if args.output and len(target_paths) > 1:
            print(colorize("Cannot use --output with multiple input files.", COLOR_RED), file=sys.stderr)
            return 1

        total_changed = 0
        for path in target_paths:
            if not path.is_file():
                print(colorize(f"File not found: {path}", COLOR_RED), file=sys.stderr)
                return 1
            changed, _ = fix_file(path, output_path=args.output)
            if changed:
                total_changed += 1
                dest = args.output or str(path)
                print(colorize(f"✓ Fixed and formatted: {dest}", COLOR_GREEN))
            else:
                print(colorize(f"- Already clean: {path}", COLOR_CYAN))

        return 0

    # Audit mode (default / --check)
    reports: List[AuditReport] = []
    has_issues = False

    for path in target_paths:
        if not path.is_file():
            print(colorize(f"File not found: {path}", COLOR_RED), file=sys.stderr)
            return 1
        report = audit_file(
            path,
            strict_pinning=args.strict_pinning,
            allow_loose=args.allow_loose,
        )
        reports.append(report)
        if not report.is_clean:
            has_issues = True

    if args.json:
        output_data = {
            "version": __version__,
            "total_files": len(reports),
            "clean": not has_issues,
            "reports": [r.to_dict() for r in reports],
        }
        print(json.dumps(output_data, indent=2))
    else:
        for idx, report in enumerate(reports):
            if idx > 0:
                print()
            print(format_text_report(report, verbose=args.verbose))

    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
