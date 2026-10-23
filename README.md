# requirements-doctor 🩺

[![CI](https://github.com/slopggobblercobbler81/requirements-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/requirements-doctor/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://pypi.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-grade CLI utility and Python library to audit, lint, deduplicate, and clean `requirements.txt` files.

Zero external dependencies. Blazing fast. Deterministic.

---

## 🚀 Features

- **🔍 Conflict & Duplicate Detection**:
  - Catches duplicate package declarations across requirement files.
  - Detects contradictory version pins (e.g. `requests>=2.28` vs `requests==2.25.1` or incompatible exact pins).
- **🛡️ Production Pin Auditing**:
  - Flags bare / unpinned packages (`requests`).
  - Identifies loose unbounded lower pins (`requests>=2.0`) that threaten reproducible production deployments.
  - `--strict-pinning` mode to enforce exact `==` pinning across your entire dependency manifest.
- **📦 Deprecated & Legacy Package Modernization**:
  - Automatically identifies obsolete packages and dummy redirect packages (e.g., `sklearn` → `scikit-learn`, `PIL` → `Pillow`, `bs4` → `beautifulsoup4`, `yaml` → `PyYAML`).
  - Detects Python 2 backports that now belong to the Python standard library (e.g., `typing`, `pathlib`, `mock`, `futures`, `enum34`).
- **🔒 Security & URL Auditing**:
  - Flags insecure protocols (`git://`, unencrypted `http://`).
  - Warns about direct VCS/tarball references that break deterministic build caches.
- **✨ Automated Fixer (`--fix`)**:
  - Automatically deduplicates and merges multiple constraints, extras, environment markers, and comments.
  - Modernizes legacy package names in-place.
  - Strips unnecessary stdlib backports.
  - Formats and alphabetically sorts dependencies.
- **🤖 CI/CD Ready**:
  - `--check` flag with non-zero exit codes for gating pull requests.
  - `--diff` to review proposed fixes in unified diff format.
  - `--json` machine-readable output for automated workflows.

---

## 📦 Installation

```bash
pip install requirements-doctor
```

Or install in editable mode from source:

```bash
git clone https://github.com/slopggobblercobbler81/requirements-doctor.git
cd requirements-doctor
pip install -e .
```

---

## 🛠️ CLI Usage

### 1. Audit Requirement Files (Default / Check Mode)

```bash
# Check all requirements*.txt in the current directory
requirements-doctor

# Check specific files
requirements-doctor requirements.txt requirements-dev.txt

# Audit with strict production pinning (fails if any package does not use ==)
requirements-doctor --strict-pinning requirements.txt
```

Example output:
```text
Auditing requirements.txt (4 packages, 5 lines):
  [WARN]  line 1: Package 'requests' has unbounded lower pin '>=2.28.0', which can cause breaking changes on major releases.
         Suggestion: Add an upper bound or exact pin, e.g. 'requests>=X.Y,<(X+1).0'.
  [WARN]  line 3: Package 'sklearn' is a deprecated placeholder package. Use 'scikit-learn'.
         Suggestion: Replace 'sklearn' with 'scikit-learn'.
  [ERROR] line 4: Conflicting version specifications for 'requests' on line 1 ('>=2.28.0') and line 4 ('==2.25.1'). Pin '==2.25.1' violates constraint '>=2.28.0'.
         Suggestion: Resolve conflicting pins to a single compatible version.
  Summary: 1 error, 2 warnings
```

### 2. Auto-Fix and Format (`--fix`)

Automatically resolves duplicate pins, selects compatible versions, updates deprecated package names, removes obsolete stdlib packages, and sorts requirements:

```bash
# Fix in-place
requirements-doctor --fix requirements.txt

# Fix and write to a new file
requirements-doctor --fix requirements.txt -o requirements.clean.txt
```

### 3. Preview Proposed Changes (`--diff`)

```bash
requirements-doctor --diff requirements.txt
```

Output:
```diff
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,4 +1,3 @@
-requests>=2.28.0
-boto3==1.24.0
-sklearn==0.0
-requests==2.25.1
+boto3==1.24.0
+requests==2.28.0
+scikit-learn==0.0
```

### 4. Machine-Readable JSON Output (`--json`)

```bash
requirements-doctor --check --json requirements.txt
```

```json
{
  "version": "0.1.0",
  "total_files": 1,
  "clean": false,
  "reports": [
    {
      "file_path": "requirements.txt",
      "total_lines": 4,
      "total_requirements": 4,
      "is_clean": false,
      "error_count": 1,
      "warning_count": 2,
      "issues": [
        {
          "code": "CONFLICTING_SPEC",
          "severity": "error",
          "message": "Conflicting version specifications for 'requests' on line 1 and line 4.",
          "line_number": 4,
          "package_name": "requests",
          "suggestion": "Resolve conflicting pins to a single compatible version."
        }
      ]
    }
  ]
}
```

---

## 🐍 Python API

You can also use `requirements-doctor` directly inside your Python applications, pre-commit hooks, or custom build scripts:

```python
from requirements_doctor import audit_content, fix_content

raw_requirements = """
requests>=2.28.0
requests==2.28.1
sklearn==0.0
"""

# Audit requirements string
report = audit_content(raw_requirements)
print(f"Clean? {report.is_clean}")
for issue in report.issues:
    print(f"[{issue.severity.value.upper()}] {issue.message}")

# Auto-fix requirements
cleaned_requirements = fix_content(raw_requirements)
print(cleaned_requirements)
# Output:
# requests==2.28.1
# scikit-learn==0.0
```

---

## 📋 Command Line Reference

| Flag | Description |
|---|---|
| `files...` | Requirement files to inspect. Defaults to `requirements*.txt` in cwd. |
| `--check` | Audit mode. Returns exit code `1` if issues exist (default). |
| `--fix` | Automatically fix, deduplicate, modernize, and sort requirements in-place. |
| `--diff` | Print unified diff of proposed changes without writing to disk. |
| `-o`, `--output` | Destination path when running `--fix`. |
| `--strict-pinning` | Require exact `==` pinning for all packages. |
| `--allow-loose` | Suppress loose / unbounded lower pin warnings. |
| `--json` | Output diagnostic report in structured JSON format. |
| `-v`, `--verbose` | Output detailed verbose diagnostics. |
| `--version` | Display version information. |

---

## 🧪 Testing

Run unit tests locally with `pytest`:

```bash
pytest -v
```

Run test suite with coverage:

```bash
pytest --cov=requirements_doctor --cov-report=term-missing
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
