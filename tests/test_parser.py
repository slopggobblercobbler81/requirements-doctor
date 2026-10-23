"""Tests for requirements parser."""

import pytest
from requirements_doctor.models import RequirementItem
from requirements_doctor.parser import RequirementsParser, canonicalize_name


def test_canonicalize_name():
    assert canonicalize_name("Requests") == "requests"
    assert canonicalize_name("Scikit_Learn") == "scikit-learn"
    assert canonicalize_name("zope.interface") == "zope-interface"
    assert canonicalize_name("foo--bar__baz..qux") == "foo-bar-baz-qux"


def test_parse_simple_package():
    line = "requests==2.28.1"
    item = RequirementsParser.parse_line(line, 1)
    assert item.name == "requests"
    assert item.canonical_name == "requests"
    assert item.specs == [("==", "2.28.1")]
    assert item.spec_str == "==2.28.1"
    assert item.is_package_requirement()


def test_parse_extras():
    line = "fastapi[all,security]>=0.80.0,<1.0.0"
    item = RequirementsParser.parse_line(line, 2)
    assert item.name == "fastapi"
    assert item.canonical_name == "fastapi"
    assert sorted(item.extras) == ["all", "security"]
    assert item.specs == [(">=", "0.80.0"), ("<", "1.0.0")]


def test_parse_comments_and_whitespace():
    # Pure comment
    c_item = RequirementsParser.parse_line("  # Core dependencies", 1)
    assert c_item.is_comment
    assert c_item.inline_comment == "Core dependencies"
    assert not c_item.is_package_requirement()

    # Empty line
    e_item = RequirementsParser.parse_line("   ", 2)
    assert e_item.is_empty
    assert not e_item.is_package_requirement()

    # Inline comment
    pkg_item = RequirementsParser.parse_line("pytest>=7.0.0  # Testing framework", 3)
    assert pkg_item.name == "pytest"
    assert pkg_item.specs == [(">=", "7.0.0")]
    assert pkg_item.inline_comment == "Testing framework"


def test_parse_environment_marker():
    line = "pywin32>=300; sys_platform == 'win32'"
    item = RequirementsParser.parse_line(line, 4)
    assert item.name == "pywin32"
    assert item.specs == [(">=", "300")]
    assert item.environment_marker == "sys_platform == 'win32'"


def test_parse_pip_flags():
    req_flag = RequirementsParser.parse_line("-r base.txt", 1)
    assert req_flag.is_flag
    assert req_flag.flag_type == "-r"
    assert req_flag.flag_value == "base.txt"

    idx_flag = RequirementsParser.parse_line("--index-url https://pypi.org/simple", 2)
    assert idx_flag.is_flag
    assert idx_flag.flag_type == "--index-url"
    assert idx_flag.flag_value == "https://pypi.org/simple"


def test_parse_direct_urls():
    # PEP 508 direct reference @
    pep508_line = "pip @ https://github.com/pypa/pip/archive/22.0.tar.gz"
    p_item = RequirementsParser.parse_line(pep508_line, 1)
    assert p_item.name == "pip"
    assert p_item.url == "https://github.com/pypa/pip/archive/22.0.tar.gz"

    # Git URL with egg
    git_line = "git+https://github.com/psf/requests.git@v2.28.1#egg=requests"
    g_item = RequirementsParser.parse_line(git_line, 2)
    assert g_item.name == "requests"
    assert g_item.canonical_name == "requests"
    assert g_item.url == git_line


def test_parse_editable():
    ed_item = RequirementsParser.parse_line("-e .", 1)
    assert ed_item.is_editable

    ed_git = RequirementsParser.parse_line("-e git+https://github.com/psf/requests.git#egg=requests", 2)
    assert ed_git.is_editable
    assert ed_git.name == "requests"


def test_parse_line_continuation():
    content = "requests==2.28.1 \\\n  # comment on continuation\nflask==2.2.0\n"
    items = RequirementsParser.parse_content(content)
    assert len(items) == 2
    assert items[0].name == "requests"
    assert items[1].name == "flask"


def test_format_line():
    item = RequirementItem(
        raw="",
        line_number=1,
        name="requests",
        canonical_name="requests",
        extras=["socks", "security"],
        specs=[(">=", "2.25.0"), ("<", "3.0.0")],
        environment_marker="python_version >= '3.8'",
        inline_comment="network client",
    )
    formatted = item.format_line()
    assert formatted == "requests[security,socks]>=2.25.0,<3.0.0; python_version >= '3.8'  # network client"
