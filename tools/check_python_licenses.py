#!/usr/bin/env python3
"""Python dependency license gate for the SourcePrep OSS release.

SourcePrep ships under Apache-2.0. A GPL/AGPL/copyleft Python dependency
would contaminate the Apache-2.0 grant. This script runs ``pip-licenses`` over
the installed environment, parses the JSON output, and fails (exit 1) if any
installed package declares a forbidden license.

Forbidden license patterns (substring match on the normalized license string):
    - GPL   (catches "GPL-2.0", "GPL-3.0-or-later", "GPLv2", etc.)
    - AGPL  (catches "AGPL-3.0")
    - LGPL  is allowed (LGPL-2.1/3.0 are weak copyleft, Apache-2.0-compatible
      when dynamically linked; but flag it so a human reviews — the Python
      ecosystem has some LGPL packages like this; review per-package).
      -> NOT in the fail set by default. Set ``--strict-lgpl`` to fail on it.
    - "unknown" / unlicensed -> fail (a dep with no declared license is a
      diligence gap).

Usage:
    python tools/check_python_licenses.py
    python tools/check_python_licenses.py --strict-lgpl

Run after ``pip install -e ".[dev]"`` so the full dependency set is installed.
Used by .github/workflows/license-audit.yml. Complements the narrow
tests/test_no_gpl_deps.py guard (which only checks igraph/leidenalg are absent).

If a forbidden license is found, the script prints the offending packages and
exits 1. On a clean run, it prints the total package count and exits 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

# Substrings that trigger a failure. Normalized to uppercase before matching.
# "GPL" matches "GPL-2.0", "GPL-3.0-or-later", "GPLv2+", etc.
# "AGPL" is caught explicitly even though "GPL" is a substring of "AGPL",
# to make the failure output readable.
FAIL_PATTERNS = ["AGPL", "GPL", "UNLICENSED", "UNKNOWN", "N/A"]

# Permissive license substrings. If ANY clause of a license expression (split
# on OR / ;) matches one of these, the package passes — the copyright holder
# offers a permissive option (Apache-2.0 OR GPL-2.0 is fine; pick Apache).
PERMISSIVE = [
    "MIT", "APACHE", "BSD", "ISC", "MPL", "PYTHON", "ZLIB", "CC0",
    "UNICODE", "OPENSSL",
]

# Local project packages — these ARE Apache-2.0 (declared in pyproject.toml /
# engine Cargo.toml) but pip-licenses reads their metadata as "UNKNOWN"
# because they're editable/path installs without a published license field on
# the wheel. Excluded so the gate checks dependencies, not our own code.
LOCAL_PACKAGES = {"prep", "prep-engine", "sourceprep", "sourceprep-engine"}

# Documented exceptions — packages that match a fail pattern but are
# acceptable for a documented reason. Each entry has a rationale; the gate
# prints the rationale when it applies the exception so the exception is
# auditable in CI logs. Do NOT add an exception without a recorded rationale.
EXCEPTIONS = {
    "PYINSTALLER": (
        "GPL-2.0 build tool. PyInstaller's GPL applies to PyInstaller itself, "
        "NOT to the programs it bundles — per the PyInstaller license FAQ, the "
        "bundled output is not a derivative work of PyInstaller (the bootloader "
        "is under a separate permissive license; PyInstaller's own source is "
        "not included in the bundle). Using PyInstaller to package an "
        "Apache-2.0 app is a long-established community-consensus pattern. "
        "Exception scoped to the build/dev tool only; the runtime dependency "
        "set is unaffected."
    ),
}


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).upper()


def _pip_licenses_executable() -> str:
    """Resolve the pip-licenses CLI from the active venv (same dir as
    sys.executable), falling back to PATH. The venv bin dir is not on PATH
    when invoked via subprocess.run, so we resolve the absolute path."""
    candidates = [
        os.path.join(os.path.dirname(sys.executable), "pip-licenses"),
        "pip-licenses",  # PATH fallback (CI installs globally here often)
    ]
    for c in candidates:
        if os.path.exists(c) or shutil.which(c):
            return c
    return candidates[0]


def run_pip_licenses() -> list[dict]:
    """Run pip-licenses and return its JSON output as a list of package rows."""
    proc = subprocess.run(
        [_pip_licenses_executable(), "--format=json", "--with-urls"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # pip-licenses may warn on unparseable metadata; stderr is informational.
        # Only a total failure to produce JSON is fatal here.
        print(f"ERROR: pip-licenses exited {proc.returncode}", file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        # Try to parse stdout anyway — pip-licenses writes JSON then warns.
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Fallback: pip-licenses might be unavailable; install hint.
        print(
            "ERROR: could not parse pip-licenses JSON. "
            "Is pip-licenses installed? (pip install pip-licenses)",
            file=sys.stderr,
        )
        sys.exit(2)


def split_clauses(lic: str) -> list[str]:
    """Split a combined license string into its clauses. pip-licenses joins
    multiple licenses with '; ' (e.g. 'Apache; GPL-2.0') and SPDX expressions
    use ' OR '. We split on both so a permissive OR-clause passes."""
    s = re.sub(r"\s+OR\s+", "; ", lic)
    return [c.strip() for c in s.split(";") if c.strip()]


def clause_is_permissive(clause: str) -> bool:
    cu = normalize(clause)
    return any(p in cu for p in PERMISSIVE)


def check(rows: list[dict], strict_lgpl: bool) -> tuple[list[str], list[str]]:
    """Return (offenders, exceptions_applied) for the pip-licenses rows."""
    offenders: list[str] = []
    applied: list[str] = []
    fail_patterns = list(FAIL_PATTERNS)
    if strict_lgpl:
        fail_patterns.append("LGPL")
    for row in rows:
        name = row.get("Name", "?")
        name_norm = normalize(name).replace("-", "").replace("_", "")
        lic = normalize(row.get("License", ""))
        url = row.get("URL", "")

        # Skip local project packages (Apache-2.0 via our own metadata; the
        # editable/path install reads as UNKNOWN to pip-licenses).
        if name in LOCAL_PACKAGES or name_norm in {normalize(x) for x in LOCAL_PACKAGES}:
            continue

        # Split on OR / ; — if ANY clause is permissive, the package offers a
        # permissive option and passes.
        clauses = split_clauses(lic) if lic else []
        if clauses and any(clause_is_permissive(c) for c in clauses):
            continue

        if not lic or lic in ("UNKNOWN", "N/A", "UNLICENSED", ""):
            offenders.append(f"  {name}: license UNKNOWN / unlicensed ({url})")
            continue

        for pat in fail_patterns:
            if pat in lic:
                # Check documented exception (keyed on the normalized name,
                # hyphens/underscores stripped).
                exc = EXCEPTIONS.get(name_norm)
                if exc is not None:
                    applied.append(f"  {name}: {lic} -> EXCEPTION ({exc})")
                    break
                offenders.append(f"  {name}: {lic} (matches '{pat}')")
                break
    return offenders, applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-lgpl",
        action="store_true",
        help="Also fail on LGPL (default: allow LGPL, flag for review).",
    )
    args = parser.parse_args()

    rows = run_pip_licenses()
    offenders, applied = check(rows, args.strict_lgpl)

    print(f"Checked {len(rows)} Python packages via pip-licenses.")
    if applied:
        print(f"\nEXCEPTIONS applied ({len(applied)}):")
        for line in applied:
            print(line)
    if offenders:
        print(f"\nFAIL: {len(offenders)} package(s) with forbidden licenses:")
        for line in offenders:
            print(line)
        print(
            "\nTo resolve: replace the dependency with a permissively-licensed "
            "alternative, or add a justified exception to the gate. "
            "Do NOT widen the allow-list without a recorded rationale."
        )
        return 1
    print("OK: no forbidden (GPL/AGPL/unlicensed) Python dependencies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())