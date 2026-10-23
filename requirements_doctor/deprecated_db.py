"""Database of deprecated, legacy, or superseded Python packages."""

from __future__ import annotations

from typing import Dict, NamedTuple, Optional


class DeprecationInfo(NamedTuple):
    replacement: Optional[str]
    reason: str
    is_stdlib: bool = False


# Canonical (lowercase, dashes) package name -> DeprecationInfo
DEPRECATED_PACKAGES: Dict[str, DeprecationInfo] = {
    "sklearn": DeprecationInfo(
        replacement="scikit-learn",
        reason="'sklearn' is a deprecated placeholder package. Use 'scikit-learn'.",
    ),
    "pil": DeprecationInfo(
        replacement="Pillow",
        reason="'PIL' is legacy/unmaintained. The modern active fork is 'Pillow'.",
    ),
    "bs4": DeprecationInfo(
        replacement="beautifulsoup4",
        reason="'bs4' is a dummy redirect package. Use 'beautifulsoup4' directly.",
    ),
    "yaml": DeprecationInfo(
        replacement="PyYAML",
        reason="'yaml' package does not exist or is obsolete. Use 'PyYAML'.",
    ),
    "dateutil": DeprecationInfo(
        replacement="python-dateutil",
        reason="'dateutil' package name is ambiguous or deprecated. Use 'python-dateutil'.",
    ),
    "pycrypto": DeprecationInfo(
        replacement="pycryptodome",
        reason="'pycrypto' is unmaintained and contains known CVE vulnerabilities. Use 'pycryptodome'.",
    ),
    "crypto": DeprecationInfo(
        replacement="pycryptodome",
        reason="'crypto' is unmaintained or a legacy squat. Use 'pycryptodome' or 'cryptography'.",
    ),
    "pep8": DeprecationInfo(
        replacement="pycodestyle",
        reason="'pep8' was renamed to 'pycodestyle' to avoid confusing the tool with PEP 8 itself.",
    ),
    "discord": DeprecationInfo(
        replacement="discord.py",
        reason="'discord' is unofficial or deprecated. The official package is 'discord.py'.",
    ),
    "opencv": DeprecationInfo(
        replacement="opencv-python",
        reason="'opencv' is not the official distribution. Use 'opencv-python' or 'opencv-python-headless'.",
    ),
    "attr": DeprecationInfo(
        replacement="attrs",
        reason="'attr' is a dummy redirection package. Install 'attrs' directly.",
    ),
    "dotenv": DeprecationInfo(
        replacement="python-dotenv",
        reason="'dotenv' is obsolete. The standard package is 'python-dotenv'.",
    ),
    "jose": DeprecationInfo(
        replacement="python-jose",
        reason="'jose' is outdated. The active Python JOSE package is 'python-jose'.",
    ),
    "jwt": DeprecationInfo(
        replacement="PyJWT",
        reason="'jwt' is an unmaintained redirect. Use 'PyJWT'.",
    ),
    # Standard library packages that should not be in Python 3+ requirements
    "typing": DeprecationInfo(
        replacement=None,
        reason="'typing' is built into the Python standard library (Python 3.5+). Remove this dependency.",
        is_stdlib=True,
    ),
    "pathlib": DeprecationInfo(
        replacement=None,
        reason="'pathlib' is built into the Python standard library (Python 3.4+). Remove this dependency.",
        is_stdlib=True,
    ),
    "mock": DeprecationInfo(
        replacement=None,
        reason="'mock' is built into the standard library as 'unittest.mock' (Python 3.3+). Remove or use unittest.mock.",
        is_stdlib=True,
    ),
    "ipaddress": DeprecationInfo(
        replacement=None,
        reason="'ipaddress' is built into the Python standard library (Python 3.3+). Remove this dependency.",
        is_stdlib=True,
    ),
    "futures": DeprecationInfo(
        replacement=None,
        reason="'futures' is a Python 2 backport of 'concurrent.futures' (Python 3.2+). Remove this dependency.",
        is_stdlib=True,
    ),
    "enum34": DeprecationInfo(
        replacement=None,
        reason="'enum34' is a Python 2 backport of 'enum' (Python 3.4+). Remove this dependency.",
        is_stdlib=True,
    ),
    "contextlib2": DeprecationInfo(
        replacement=None,
        reason="'contextlib2' features are included in Python standard library 'contextlib'. Remove this dependency.",
        is_stdlib=True,
    ),
    "funcsigs": DeprecationInfo(
        replacement=None,
        reason="'funcsigs' is a Python 2 backport of 'inspect.signature' (Python 3.3+). Remove this dependency.",
        is_stdlib=True,
    ),
}


def lookup_deprecated(canonical_name: str) -> Optional[DeprecationInfo]:
    """Check if a canonical package name is in the deprecation database."""
    return DEPRECATED_PACKAGES.get(canonical_name.lower().replace("_", "-"))
