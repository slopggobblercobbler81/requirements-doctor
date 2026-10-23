"""Tests for auto-fixer logic."""

from requirements_doctor.fixer import fix_content, fix_file


def test_fix_deduplication_and_sorting():
    content = """
# Project dependencies
requests==2.25.1
click==8.1.3
requests==2.28.1
boto3==1.24.0
"""
    fixed = fix_content(content)
    lines = fixed.strip().splitlines()

    # Checks header kept
    assert "# Project dependencies" in lines

    # Checks sorted alphabetically: boto3, click, requests
    pkg_lines = [l for l in lines if l and not l.startswith("#")]
    assert pkg_lines[0] == "boto3==1.24.0"
    assert pkg_lines[1] == "click==8.1.3"
    # Deduplicated requests chose higher version 2.28.1
    assert pkg_lines[2] == "requests==2.28.1"


def test_fix_merges_extras_and_comments():
    content = """
requests[security]==2.28.1  # security features
requests[socks]==2.28.1  # socks proxy
"""
    fixed = fix_content(content)
    pkg_line = [l for l in fixed.splitlines() if l and not l.startswith("#")][0]
    assert "requests[security,socks]==2.28.1" in pkg_line
    assert "# security features; socks proxy" in pkg_line


def test_fix_deprecated_package():
    content = """
sklearn==0.0
PIL==1.1.7
typing==3.7.4.3
requests==2.28.1
"""
    fixed = fix_content(content)
    # sklearn replaced with scikit-learn
    assert "scikit-learn==0.0" in fixed
    # PIL replaced with Pillow
    assert "Pillow==1.1.7" in fixed
    # typing removed as stdlib
    assert "typing==" not in fixed
    assert "# Removed 'typing' (built-in to Python standard library)" in fixed


def test_fix_preserves_flags():
    content = """
-r base.txt
--index-url https://pypi.org/simple

urllib3==1.26.12
certifi==2022.9.24
"""
    fixed = fix_content(content)
    lines = fixed.strip().splitlines()
    assert "-r base.txt" in lines
    assert "--index-url https://pypi.org/simple" in lines
    pkg_lines = [l for l in lines if "==" in l]
    assert pkg_lines[0] == "certifi==2022.9.24"
    assert pkg_lines[1] == "urllib3==1.26.12"


def test_fix_file_in_place(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.25.0\nrequests==2.28.1\n", encoding="utf-8")

    changed, fixed = fix_file(req_file)
    assert changed
    assert fixed.strip() == "requests==2.28.1"
    assert req_file.read_text(encoding="utf-8").strip() == "requests==2.28.1"

    # Running fix on already clean file returns changed=False
    changed2, _ = fix_file(req_file)
    assert not changed2


def test_fix_file_with_output_path(tmp_path):
    req_file = tmp_path / "req.txt"
    out_file = tmp_path / "out.txt"
    req_file.write_text("requests==2.28.1\n", encoding="utf-8")

    changed, _ = fix_file(req_file, output_path=out_file)
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8").strip() == "requests==2.28.1"
