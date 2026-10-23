"""Requirements file parser conforming to PEP 508 and pip requirements syntax."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from requirements_doctor.models import RequirementItem


def canonicalize_name(name: str) -> str:
    """Normalize a package name according to PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


# Regex components
# Flags e.g. -r, --requirement, -c, --constraint, -i, --index-url, etc.
FLAG_REGEX = re.compile(
    r"^(-[rcei]|--(?:requirement|constraint|index-url|extra-index-url|find-links|trusted-host|no-index|pre))\b\s*(.*)$"
)

# Editable flag: -e / --editable
EDITABLE_REGEX = re.compile(r"^(-e|--editable)\s+(.+)$")

# Direct URL pattern: http://, https://, git+, svn+, hg+, bzr+, ftp://
URL_SCHEME_REGEX = re.compile(r"^(?:(?:git|svn|hg|bzr)\+)?(?:https?|git|ftp|ssh)://", re.IGNORECASE)

# Direct reference PEP 508: name [extras] @ url ; markers
PEP508_DIRECT_URL_REGEX = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([^\]]+)\])?\s*@\s*(.+)$"
)

# Standard package specifier pattern
# Group 1: package name
# Group 2: optional extras in brackets [extra1,extra2]
# Group 3: version specifier list e.g. ==1.0, >=2.0,<3.0
PACKAGE_SPEC_REGEX = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([^\]]+)\])?\s*([<>=!~].*)?$"
)

# Operator and version split regex
SPEC_SPLIT_REGEX = re.compile(r"(===|==|!=|<=|>=|~=|<|>)\s*([^\s,;]+)")


class RequirementsParser:
    """Parses requirements.txt content into structured RequirementItem objects."""

    @classmethod
    def parse_content(cls, content: str) -> List[RequirementItem]:
        """Parses a full requirements string into a list of RequirementItem."""
        lines = content.splitlines()
        items: List[RequirementItem] = []
        raw_buffer = ""
        buffer_start_line = 0

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Handle line continuation with trailing backslash
            if stripped.endswith("\\"):
                if not raw_buffer:
                    buffer_start_line = line_idx
                raw_buffer += stripped[:-1].rstrip() + " "
                continue

            if raw_buffer:
                full_line = raw_buffer + stripped
                start_line = buffer_start_line
                raw_buffer = ""
            else:
                full_line = line
                start_line = line_idx

            item = cls.parse_line(full_line, start_line)
            items.append(item)

        return items

    @classmethod
    def parse_line(cls, line: str, line_number: int) -> RequirementItem:
        """Parses a single requirement line."""
        original_raw = line
        clean_line = line.strip()

        # 1. Empty lines
        if not clean_line:
            return RequirementItem(raw=original_raw, line_number=line_number, is_empty=True)

        # 2. Pure comment lines
        if clean_line.startswith("#"):
            return RequirementItem(
                raw=original_raw,
                line_number=line_number,
                is_comment=True,
                inline_comment=clean_line[1:].strip(),
            )

        # 3. Extract inline comment if present
        # Care must be taken not to split inside URLs (e.g. #egg=foo)
        # In pip, inline comment is marked by whitespace followed by #
        inline_comment: Optional[str] = None
        comment_idx = clean_line.find(" #")
        if comment_idx != -1:
            inline_comment = clean_line[comment_idx + 2 :].strip()
            clean_line = clean_line[:comment_idx].rstrip()

        # 4. Environment markers: separated by ';'
        environment_marker: Optional[str] = None
        if ";" in clean_line:
            parts = clean_line.split(";", 1)
            clean_line = parts[0].strip()
            environment_marker = parts[1].strip()

        # 5. Check for editable flag (-e / --editable)
        is_editable = False
        editable_match = EDITABLE_REGEX.match(clean_line)
        if editable_match:
            is_editable = True
            clean_line = editable_match.group(2).strip()

        # 6. Check for other pip flags (-r, -c, -i, etc.)
        flag_match = FLAG_REGEX.match(clean_line)
        if flag_match and not is_editable:
            flag_type = flag_match.group(1)
            flag_val = flag_match.group(2).strip()
            return RequirementItem(
                raw=original_raw,
                line_number=line_number,
                is_flag=True,
                flag_type=flag_type,
                flag_value=flag_val,
                inline_comment=inline_comment,
            )

        # 7. Check for Direct URL format: name [extras] @ url
        pep508_url = PEP508_DIRECT_URL_REGEX.match(clean_line)
        if pep508_url:
            name = pep508_url.group(1)
            extras_raw = pep508_url.group(2)
            url_target = pep508_url.group(3).strip()
            extras = [e.strip() for e in extras_raw.split(",") if e.strip()] if extras_raw else []

            return RequirementItem(
                raw=original_raw,
                line_number=line_number,
                name=name,
                canonical_name=canonicalize_name(name),
                extras=extras,
                url=url_target,
                is_editable=is_editable,
                environment_marker=environment_marker,
                inline_comment=inline_comment,
            )

        # 8. Check for raw URL requirement without package name (e.g. git+https://...#egg=pkg) or local path
        if URL_SCHEME_REGEX.match(clean_line) or clean_line.startswith("."):
            pkg_name = None
            # Check for #egg=package_name in URL fragment
            if "#egg=" in clean_line:
                egg_part = clean_line.split("#egg=", 1)[1]
                pkg_name = egg_part.split("&", 1)[0].strip()

            return RequirementItem(
                raw=original_raw,
                line_number=line_number,
                name=pkg_name,
                canonical_name=canonicalize_name(pkg_name) if pkg_name else None,
                url=clean_line,
                is_editable=is_editable,
                environment_marker=environment_marker,
                inline_comment=inline_comment,
            )

        # 9. Standard package requirement: name[extras] specs
        pkg_match = PACKAGE_SPEC_REGEX.match(clean_line)
        if pkg_match:
            name = pkg_match.group(1)
            extras_raw = pkg_match.group(2)
            spec_raw = pkg_match.group(3)

            extras = [e.strip() for e in extras_raw.split(",") if e.strip()] if extras_raw else []
            specs: List[Tuple[str, str]] = []
            spec_str = None

            if spec_raw:
                spec_str = spec_raw.strip()
                matches = SPEC_SPLIT_REGEX.findall(spec_str)
                for op, ver in matches:
                    specs.append((op, ver.strip()))

            return RequirementItem(
                raw=original_raw,
                line_number=line_number,
                name=name,
                canonical_name=canonicalize_name(name),
                extras=extras,
                specs=specs,
                spec_str=spec_str,
                is_editable=is_editable,
                environment_marker=environment_marker,
                inline_comment=inline_comment,
            )

        # 10. Fallback: unparsed or custom line treated as raw / flag
        return RequirementItem(
            raw=original_raw,
            line_number=line_number,
            is_flag=True,
            flag_value=clean_line,
            inline_comment=inline_comment,
        )
