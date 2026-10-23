"""Auto-fixer to deduplicate, sort, modernize deprecated packages, and format requirements."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from requirements_doctor.deprecated_db import lookup_deprecated
from requirements_doctor.models import RequirementItem
from requirements_doctor.parser import RequirementsParser, canonicalize_name
from requirements_doctor.rules import compare_versions


class RequirementsFixer:
    """Repairs and normalizes requirements files."""

    @classmethod
    def fix_content(cls, content: str) -> str:
        """Fixes, deduplicates, and sorts requirements content string."""
        items = RequirementsParser.parse_content(content)

        flags_and_headers: List[str] = []
        package_items_by_name: Dict[str, List[RequirementItem]] = OrderedDict()
        stdlib_removals: List[str] = []

        # Categorize lines
        for item in items:
            if item.is_flag and not item.name:
                flags_and_headers.append(item.raw.strip())
            elif item.is_comment and not package_items_by_name:
                # Top-level comments before any packages
                flags_and_headers.append(item.raw.strip())
            elif item.is_empty and not package_items_by_name:
                if flags_and_headers and flags_and_headers[-1] != "":
                    flags_and_headers.append("")
            elif item.is_package_requirement():
                name = item.canonical_name or (canonicalize_name(item.name) if item.name else "unnamed")

                # Check if this package is a standard library module in Python 3
                dep_info = lookup_deprecated(name)
                if dep_info and dep_info.is_stdlib:
                    stdlib_removals.append(
                        f"# Removed '{item.name or name}' (built-in to Python standard library)"
                    )
                    continue

                if name not in package_items_by_name:
                    package_items_by_name[name] = []
                package_items_by_name[name].append(item)
            elif item.is_comment:
                # Comment inside or after packages
                pass

        # Deduplicate and consolidate each package
        consolidated_requirements: List[RequirementItem] = []

        for canonical_name, group in package_items_by_name.items():
            consolidated = cls._merge_package_group(canonical_name, group)
            consolidated_requirements.append(consolidated)

        # Sort alphabetically by canonical name
        consolidated_requirements.sort(key=lambda r: (r.canonical_name or "").lower())

        # Build output lines
        output_lines: List[str] = []

        if flags_and_headers:
            output_lines.extend(flags_and_headers)
            if output_lines[-1] != "":
                output_lines.append("")

        if stdlib_removals:
            output_lines.extend(stdlib_removals)
            output_lines.append("")

        for req in consolidated_requirements:
            output_lines.append(req.format_line())

        # Ensure single trailing newline
        return "\n".join(output_lines).rstrip() + "\n"

    @classmethod
    def _merge_package_group(
        cls,
        canonical_name: str,
        group: List[RequirementItem],
    ) -> RequirementItem:
        """Consolidates duplicate items for a single canonical package."""
        first = group[0]
        original_name = first.name or canonical_name

        # Check for deprecation replacement
        dep_info = lookup_deprecated(canonical_name)
        if dep_info and dep_info.replacement:
            original_name = dep_info.replacement
            canonical_name = canonicalize_name(dep_info.replacement)

        # Merge extras
        all_extras: Set[str] = set()
        for it in group:
            all_extras.update(it.extras)

        # Collect comments
        comments: List[str] = []
        for it in group:
            if it.inline_comment and it.inline_comment not in comments:
                comments.append(it.inline_comment)

        # Collect environment markers
        markers: List[str] = []
        for it in group:
            if it.environment_marker and it.environment_marker not in markers:
                markers.append(it.environment_marker)

        # Handle direct URLs
        urls = [it.url for it in group if it.url]
        if urls:
            # Prefer last URL or HTTPS URL
            chosen_url = urls[-1]
            return RequirementItem(
                raw="",
                line_number=first.line_number,
                name=original_name,
                canonical_name=canonical_name,
                extras=sorted(all_extras),
                url=chosen_url,
                is_editable=any(it.is_editable for it in group),
                environment_marker=" and ".join(markers) if markers else None,
                inline_comment="; ".join(comments) if comments else None,
            )

        # Consolidate version specs
        all_specs: List[Tuple[str, str]] = []
        for it in group:
            all_specs.extend(it.specs)

        final_specs = cls._resolve_specs(all_specs)

        spec_str = ",".join(f"{op}{ver}" for op, ver in final_specs) if final_specs else None

        return RequirementItem(
            raw="",
            line_number=first.line_number,
            name=original_name,
            canonical_name=canonical_name,
            extras=sorted(all_extras),
            specs=final_specs,
            spec_str=spec_str,
            is_editable=any(it.is_editable for it in group),
            environment_marker=" and ".join(markers) if markers else None,
            inline_comment="; ".join(comments) if comments else None,
        )

    @classmethod
    def _resolve_specs(cls, specs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Resolves duplicate or redundant specs into a clean minimal list."""
        if not specs:
            return []

        # Deduplicate identical pairs
        unique_specs = list(OrderedDict.fromkeys(specs))

        # Check for exact '==' pins
        exact_pins = [ver for op, ver in unique_specs if op in ("==", "===")]
        if exact_pins:
            # Pick highest version
            best_ver = exact_pins[0]
            for v in exact_pins[1:]:
                if compare_versions(v, best_ver) > 0:
                    best_ver = v
            return [("==", best_ver)]

        # Otherwise clean duplicate operators
        # For example, if multiple '>=', keep the highest lower bound
        gte_pins = [ver for op, ver in unique_specs if op == ">="]
        lte_pins = [ver for op, ver in unique_specs if op == "<="]
        lt_pins = [ver for op, ver in unique_specs if op == "<"]
        gt_pins = [ver for op, ver in unique_specs if op == ">"]
        other_pins = [(op, ver) for op, ver in unique_specs if op not in (">=", "<=", "<", ">")]

        resolved: List[Tuple[str, str]] = []

        if gte_pins:
            best_gte = gte_pins[0]
            for v in gte_pins[1:]:
                if compare_versions(v, best_gte) > 0:
                    best_gte = v
            resolved.append((">=", best_gte))
        elif gt_pins:
            best_gt = gt_pins[0]
            for v in gt_pins[1:]:
                if compare_versions(v, best_gt) > 0:
                    best_gt = v
            resolved.append((">", best_gt))

        if lte_pins:
            best_lte = lte_pins[0]
            for v in lte_pins[1:]:
                if compare_versions(v, best_lte) < 0:
                    best_lte = v
            resolved.append(("<=", best_lte))
        elif lt_pins:
            best_lt = lt_pins[0]
            for v in lt_pins[1:]:
                if compare_versions(v, best_lt) < 0:
                    best_lt = v
            resolved.append(("<", best_lt))

        resolved.extend(other_pins)
        return resolved


def fix_content(content: str) -> str:
    """Fixes requirements content string."""
    return RequirementsFixer.fix_content(content)


def fix_file(
    file_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, str]:
    """
    Fixes a requirements file.
    Writes to output_path if specified, or overwrites file_path in-place.
    Returns (changed: bool, fixed_content: str).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    original = path.read_text(encoding="utf-8")
    fixed = fix_content(original)

    target_path = Path(output_path) if output_path else path
    changed = original != fixed

    if changed or output_path:
        target_path.write_text(fixed, encoding="utf-8")

    return changed, fixed
