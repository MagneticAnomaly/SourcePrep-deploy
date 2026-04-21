# Prep Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the entire codebase from "CoDRAG" to "Prep" — every identifier, file, directory, URL, docstring, config key, user-visible string, and generated template — preserving git history across four GitHub repos, with `main` staying buildable until final merge.

**Architecture:** Big-bang hard cutover on branch `rename/codrag-to-prep`. Phases execute sequentially; each ends with a commit and a build/test verification. A zero-occurrence grep gate (with a curated allowlist for historical docs) must return empty before merge. GitHub transfer+rename of the four repos fires post-merge.

**Tech Stack:** Python 3.11 (uv, pytest, FastAPI, Typer), Rust workspace (cargo, maturin, tree-sitter), npm monorepo (Turbo, React/Vite, Radix, Storybook), Tauri 2.x, PyInstaller sidecar, Next.js (4 marketing/docs/support/payments apps), MCP protocol, VS Code extension.

**Branch:** `rename/codrag-to-prep` (already created, based on `main`).

**Spec:** `docs/superpowers/specs/2026-04-21-prep-rename-design.md`

**Scope reconciliation from spec:**
- Spec §11 (resolving D3) says keep `websites/MagneticAnomaly/` in place, but the phase-sequence table earlier in the spec still lists "Phase 18: Delete `websites/MagneticAnomaly/`". The decisions table supersedes the sequencing table — this plan **folds MagneticAnomaly text rewrites into Task 14 (websites) and drops Phase 18 entirely**.
- Spec §10 introduces new auto-migration code (D4, D5) alongside the identifier rename. The new code is TDD-worthy; this plan carves it out as **Task 3B** so tests land with the implementation rather than hiding inside a bulk find/replace commit.
- All other task numbers align with the spec's phase numbers.

**Guiding rule (from spec):** no visual redesign. Image files are renamed on disk; pixel contents are untouched. Feature behavior is unchanged. Nothing in this plan modifies functional behavior except the one-shot data-dir auto-migration (Task 3B).

---

## Conventions used in this plan

- **Exact commands** are shown verbatim; copy-paste safe (macOS `bash`/`zsh`).
- **Find/replace** uses `rg --files-with-matches` (ripgrep) to enumerate files, then `sed -i ''` to rewrite in place. macOS `sed` requires the empty `''` argument to `-i`; on Linux use `sed -i` without it.
- **`git mv`** is preferred over `mv`+`git add` so rename detection is recorded.
- **Case-sensitive** replacements are ordered carefully — "CODRAG" first (all caps, env vars), then "CoDRAG" (brand), then "codrag" (lowercase). This avoids "codrag" swallowing "CoDRAG" before the brand rewrite runs.
- Every task ends with `git commit -m "rename(phase-N): …"` on branch `rename/codrag-to-prep`. Commit prefix makes the merge commit skimmable and supports `git bisect`.

---

## Task 0: Pre-flight

**Goal:** Confirm branch state, snapshot before-counts, drop the dead `clara-dev` remote, verify build baseline.

**Files:**
- Read: `.git/config`, `pyproject.toml`, `package.json`, `engine/Cargo.toml`
- Create: `.rename-inventory-before.txt` (gitignored)
- Modify: `.gitignore`

- [ ] **Step 1: Verify branch and clean working tree**

```bash
git branch --show-current
git status --short
```

Expected: branch = `rename/codrag-to-prep`; only untracked `.claude/` files (those are fine).

- [ ] **Step 2: Snapshot pre-rename inventory to a gitignored file**

```bash
{
  echo "=== Files containing 'codrag' (case-insensitive) ==="
  rg -l -i 'codrag' \
    --glob '!.git' --glob '!node_modules' --glob '!.venv' \
    --glob '!target' --glob '!dist' --glob '!build' \
    --glob '!__pycache__' \
    . | wc -l

  echo ""
  echo "=== 'CoDRAG' case-sensitive occurrence count ==="
  rg --count-matches 'CoDRAG' \
    --glob '!.git' --glob '!node_modules' --glob '!.venv' \
    --glob '!target' --glob '!dist' --glob '!build' \
    . | awk -F: '{s+=$2} END {print s}'

  echo ""
  echo "=== codrag.io URL refs ==="
  rg -l 'codrag\.io' \
    --glob '!.git' --glob '!node_modules' --glob '!.venv' \
    . | wc -l

  echo ""
  echo "=== @codrag/ import occurrences ==="
  rg --count-matches '@codrag/' \
    --glob '!.git' --glob '!node_modules' --glob '!.venv' \
    . | awk -F: '{s+=$2} END {print s}'

  echo ""
  echo "=== remotes ==="
  git remote -v
} > .rename-inventory-before.txt

cat .rename-inventory-before.txt
```

Expected: file count > 400; `codrag.io` refs ~115; `@codrag/` imports ~292; six remotes listed (origin, codrag-mcp, codrag-mcp-dev, dev, deploy-public, clara-dev).

- [ ] **Step 3: Baseline build — record which suites are green today**

```bash
.venv/bin/pytest tests/ -x --timeout=60 -q 2>&1 | tail -5
cd engine && cargo check --workspace 2>&1 | tail -5 && cd ..
npm run typecheck 2>&1 | tail -5
```

If any pre-existing failures exist, note them in `.rename-inventory-before.txt` under a `=== baseline failures ===` section. We compare against this baseline in Task 19 — we must not introduce new failures beyond these.

- [ ] **Step 4: Remove the `clara-dev` local remote**

CLaRa is being deleted (decision D2). Removing the remote first prevents accidental pushes during Task 17.

```bash
git remote remove clara-dev
git remote -v | grep -c clara
```

Expected: count = 0.

- [ ] **Step 5: Gitignore the inventory file and commit the pre-flight marker**

```bash
printf '\n# Prep rename inventory snapshots (Phase 0/19, gitignored)\n.rename-inventory-before.txt\n.rename-inventory-after.txt\n' >> .gitignore
git add .gitignore
git commit -m "rename(phase-0): pre-flight — drop clara-dev remote, snapshot inventory"
```

Expected: commit lands on `rename/codrag-to-prep`.

---

## Task 1: Verification infrastructure

**Goal:** Create the allowlist file and a reusable grep-gate script so we can measure progress after every phase.

**Files:**
- Create: `.rename-allowlist.txt`
- Create: `scripts/rename_gate.sh`

- [ ] **Step 1: Create the allowlist**

Allowlist entries are substrings; any hit whose path contains one is excluded from the zero-occurrence gate. We start with known historical docs; Task 17 grows the list as classification proceeds.

```bash
cat > .rename-allowlist.txt <<'EOF'
# Paths excluded from the zero-occurrence grep gate.
# See docs/superpowers/specs/2026-04-21-prep-rename-design.md §15.
# Each line is a substring; lines containing this substring are suppressed.

# Archival phase docs (grown during Task 17)
docs/Phase00_Initial-Concept/
docs/Phase01_Foundation/
docs/Phase02_Dashboard/

# Historical log entries (reference old name by design)
CHANGELOG.md

# The rename spec and this plan reference the old name by design
docs/superpowers/specs/2026-04-21-prep-rename-design.md
docs/superpowers/plans/2026-04-21-prep-rename-implementation.md

# The inventory snapshot file is gitignored, but this line is belt-and-suspenders
.rename-inventory-before.txt
.rename-inventory-after.txt
EOF
```

- [ ] **Step 2: Create the gate script**

```bash
cat > scripts/rename_gate.sh <<'EOF'
#!/usr/bin/env bash
# Returns non-zero if any rogue CoDRAG/CLaRa references remain outside the allowlist.
# Usage: bash scripts/rename_gate.sh            # prints offending lines
#        bash scripts/rename_gate.sh | wc -l    # expected: 0 before merge
set -u
grep -rniE 'codrag|clara|codrag\.io|codrag\.ai' \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=target --exclude-dir=dist --exclude-dir=build \
  --exclude-dir=__pycache__ --exclude-dir=.turbo --exclude-dir=.next \
  --exclude=package-lock.json --exclude=Cargo.lock --exclude=uv.lock \
  --exclude='*.lock' \
  . 2>/dev/null | grep -v -F -f .rename-allowlist.txt
EOF
chmod +x scripts/rename_gate.sh
```

- [ ] **Step 3: Smoke-test the script runs (many hits expected — we have not renamed anything yet)**

```bash
bash scripts/rename_gate.sh | wc -l
```

Expected: a large number (thousands). The gate is empty only after Task 19.

- [ ] **Step 4: Commit the infrastructure**

```bash
git add .rename-allowlist.txt scripts/rename_gate.sh
git commit -m "rename(phase-1): add grep-gate script and allowlist skeleton"
```

---

## Task 2: Python package directory + manifest

**Goal:** Atomically rename `src/codrag/` → `src/prep/`, update `pyproject.toml`, rewrite Python `import`/`from` statements, and update the console script entry point. After this task, `.venv/bin/prep --help` must work.

**Files:**
- `git mv`: `src/codrag/` → `src/prep/`
- Modify: `pyproject.toml`, `mypy.ini` (if present), `.pre-commit-config.yaml` (if present)
- Modify: every `*.py` under `src/` and `tests/` with `from codrag.…` or `import codrag`

**This is the single breaking phase** — the package is unimportable mid-task. We commit once at the end.

- [ ] **Step 1: Move the package directory**

```bash
git mv src/codrag src/prep
```

- [ ] **Step 2: Rewrite `pyproject.toml`**

Read the current values first, then apply surgical edits with `sed`. The fields we touch: `[project].name`, `[project].description`, `[project.scripts]`, `[tool.setuptools.packages.find]`, `[tool.ruff.lint.isort].known-first-party`, `[tool.mypy].packages`.

```bash
# All edits in one pass (macOS sed):
sed -i '' \
  -e 's/^name = "codrag"/name = "prep"/' \
  -e 's/^description = ".*CoDRAG.*"/description = "Prep — prepare context before any AI call"/' \
  -e 's/^codrag = "codrag\.cli:main"/prep = "prep.cli:main"/' \
  -e 's/known-first-party = \["codrag"\]/known-first-party = ["prep"]/' \
  -e 's/include = \["codrag\*"\]/include = ["prep*"]/' \
  pyproject.toml

# Mypy package list (may be on a line like `packages = ["codrag"]`):
sed -i '' 's/packages = \["codrag"\]/packages = ["prep"]/' pyproject.toml
```

Visually inspect the result:

```bash
rg -n 'codrag|CoDRAG' pyproject.toml
```

Expected: 0 matches. If any remain, hand-edit. Common stragglers: URLs inside `[project.urls]`, script aliases under `[project.scripts]`.

- [ ] **Step 3: Rewrite Python imports across the tree**

Two patterns: absolute imports `from codrag.X import Y` and module imports `import codrag.X`. Relative imports (`from .submod import`) are unaffected.

```bash
# Absolute `from codrag.X import Y`:
rg -l '^from codrag\.' -t py | xargs sed -i '' 's/^from codrag\./from prep./g'

# Absolute `import codrag.X`:
rg -l '^import codrag(\.|$)' -t py | xargs sed -i '' 's/^import codrag/import prep/g'

# Also catch indented imports inside functions or `try:` blocks:
rg -l '^\s+from codrag\.' -t py | xargs sed -i '' 's/\(^\s*\)from codrag\./\1from prep./g'
rg -l '^\s+import codrag(\.|$)' -t py | xargs sed -i '' 's/\(^\s*\)import codrag/\1import prep/g'

# importlib dynamic imports:
rg -l 'importlib\.import_module.*codrag' -t py | \
  xargs sed -i '' 's/importlib\.import_module("codrag/importlib.import_module("prep/g'
rg -l "importlib\.import_module.*codrag" -t py | \
  xargs sed -i '' "s/importlib\.import_module('codrag/importlib.import_module('prep/g"
```

- [ ] **Step 4: Verify package imports cleanly**

```bash
.venv/bin/python -c "import prep; print(prep.__file__)"
```

Expected: prints path inside `src/prep/`. If it fails with `ModuleNotFoundError: No module named 'prep'`, re-install in editable mode:

```bash
.venv/bin/pip install -e '.[dev]'
```

Then retry the import.

- [ ] **Step 5: Regenerate the CLI entry point**

```bash
.venv/bin/pip install -e '.[dev]'
which prep || ls .venv/bin/prep
.venv/bin/prep --help | head -5
```

Expected: `.venv/bin/prep` exists; `--help` output mentions "Prep" (if it still says "CoDRAG" in the help text, that's Task 3's job — don't fix here).

- [ ] **Step 6: Run a fast subset of the test suite to confirm nothing is broken by the import rewrite**

```bash
.venv/bin/pytest tests/ -x --timeout=60 -q --ignore=tests/integration 2>&1 | tail -20
```

Expected: failures limited to things we haven't renamed yet (env vars, data paths, MCP tool names) — those are Task 3. Import errors (`ModuleNotFoundError: codrag`) must be zero.

If a test fails with `ModuleNotFoundError: codrag`, run:

```bash
rg 'codrag' tests/ -t py -l
```

and rewrite any missed imports.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-2): python package src/codrag -> src/prep, imports, CLI entry"
```

---

## Task 3: Python internal strings

**Goal:** Rewrite every internal string — env vars, data paths, SQLite filenames, MCP tool names in Python, FastAPI titles, user-agent strings, docstrings. After this task, `.venv/bin/prep serve` must start without CoDRAG references in its startup log.

**Files:** ~400 Python files under `src/prep/` and `tests/` plus a handful of YAML/TOML.

- [ ] **Step 1: Env vars (case-sensitive, all caps first)**

```bash
rg -l '\bCODRAG_' -t py -t yaml -t toml -t json | xargs sed -i '' \
  -e 's/CODRAG_DATA_DIR/PREP_DATA_DIR/g' \
  -e 's/CODRAG_PORT/PREP_PORT/g' \
  -e 's/CODRAG_DEV_MODE/PREP_DEV_MODE/g' \
  -e 's/CODRAG_API_KEY/PREP_API_KEY/g' \
  -e 's/CODRAG_TIER/PREP_TIER/g' \
  -e 's/CODRAG_HOST/PREP_HOST/g' \
  -e 's/CODRAG_LOG_LEVEL/PREP_LOG_LEVEL/g' \
  -e 's/\bCODRAG_/PREP_/g'
```

The final catch-all replaces any `CODRAG_*` we didn't list explicitly.

Verify:
```bash
rg 'CODRAG_' -t py -t yaml -t toml -t json
```
Expected: 0 matches.

- [ ] **Step 2: Data path literals**

```bash
# XDG data path (highest frequency):
rg -l '\.local/share/codrag' | xargs sed -i '' 's|\.local/share/codrag|.local/share/prep|g'

# Home-tilde legacy paths:
rg -l '~/\.codrag' | xargs sed -i '' 's|~/\.codrag|~/.prep|g'
rg -l 'Path\.home.*codrag' -t py | xargs sed -i '' 's|codrag|prep|g'

# CWD-relative legacy:
rg -l '\bcodrag_data\b' -t py -t yaml -t toml | xargs sed -i '' 's/\bcodrag_data\b/prep_data/g'

# Embedded per-project dir:
rg -l '"\.codrag"' -t py | xargs sed -i '' 's/"\.codrag"/".prep"/g'
rg -l "'\.codrag'" -t py | xargs sed -i '' "s/'\.codrag'/'.prep'/g"
rg -l '\.codrag/' -t py -t md | xargs sed -i '' 's|\.codrag/|.prep/|g'
```

Verify:
```bash
rg '\.codrag|codrag_data|local/share/codrag' -t py -t yaml -t toml
```
Expected: 0 matches (or only hits inside comments mentioning legacy migration — those stay).

- [ ] **Step 3: SQLite filenames**

```bash
rg -l 'codrag_settings\.db|codrag_antibodies\.db|codrag_token_telemetry\.db' | \
  xargs sed -i '' \
    -e 's/codrag_settings\.db/prep_settings.db/g' \
    -e 's/codrag_antibodies\.db/prep_antibodies.db/g' \
    -e 's/codrag_token_telemetry\.db/prep_token_telemetry.db/g'

# Any other codrag_*.db the grep surfaces:
rg 'codrag_\w*\.db' -t py
```

Expected: remaining hits (if any) are flagged manually for rewrite — every DB file prefix must move from `codrag_` to `prep_`. Apply `sed` again on the specific filename if a new one appears.

Also scan for SQL schema strings:
```bash
rg 'CREATE TABLE\s+codrag_|ALTER TABLE\s+codrag_' -t py -t sql
```
If hits, hand-edit the schema definitions (low volume; keeping an eye on data_dir_migration.py — that file handles migration, so schema references there are expected). Table-name renames inside schemas are covered by Task 3B.

- [ ] **Step 4: MCP tool names (Python side)**

These are the 6 tools exposed by the MCP server; spec §8 tool-rename table.

```bash
rg -l '"codrag_(search|impact|audit|observe|concepts)"' -t py | xargs sed -i '' \
  -e 's/"codrag_search"/"prep_search"/g' \
  -e 's/"codrag_impact"/"prep_impact"/g' \
  -e 's/"codrag_audit"/"prep_audit"/g' \
  -e 's/"codrag_observe"/"prep_observe"/g' \
  -e 's/"codrag_concepts"/"prep_concepts"/g'

# Single-quoted variants:
rg -l "'codrag_(search|impact|audit|observe|concepts)'" -t py | xargs sed -i '' \
  -e "s/'codrag_search'/'prep_search'/g" \
  -e "s/'codrag_impact'/'prep_impact'/g" \
  -e "s/'codrag_audit'/'prep_audit'/g" \
  -e "s/'codrag_observe'/'prep_observe'/g" \
  -e "s/'codrag_concepts'/'prep_concepts'/g"

# The bare 'codrag' tool (no suffix) — the no-arg ambient-context tool:
rg -l '"codrag"' -t py | xargs sed -i '' 's/"codrag"/"prep"/g'
rg -l "'codrag'" -t py | xargs sed -i '' "s/'codrag'/'prep'/g"
```

After the last two: scan for unintended collateral damage. The string `"codrag"` could appear in contexts where we meant the brand not the tool name. In Python, the contexts where `"codrag"` appears as a literal string are overwhelmingly tool-name / server-name / module-name registrations, so the broad rewrite is safe. The subsequent steps will catch any remaining true-brand occurrences.

- [ ] **Step 5: FastAPI title, User-Agent, Typer help strings**

Brand-name replacement (case-sensitive CoDRAG first):
```bash
rg -l 'CoDRAG' -t py | xargs sed -i '' 's/CoDRAG/Prep/g'

# Lowercase "codrag" leftovers (comments, docstrings, URL paths):
rg -l '\bcodrag\b' -t py | xargs sed -i '' 's/\bcodrag\b/prep/g'
```

- [ ] **Step 6: Run the suite; restart daemon to verify live strings**

```bash
.venv/bin/pytest tests/ -x --timeout=60 -q 2>&1 | tail -20
```

Fix any remaining `ModuleNotFoundError: codrag`, missed env-var lookup (`os.environ["CODRAG_…"]`), or bad SQLite filename. Re-run until green (or back to the documented Task-0 baseline failures).

Manual smoke — start the daemon:
```bash
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 2
curl -s http://localhost:8400/health | head -20
curl -s http://localhost:8400/ | grep -i 'codrag'    # expected: no output
kill $DAEMON_PID
```

Expected: `/health` responds; final grep finds zero "codrag" in the server's root response.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-3): python strings — env vars, paths, SQLite, MCP tool names"
```

---

## Task 3B: Data-dir auto-migration extension (TDD)

**Goal:** Extend `src/prep/core/data_dir_migration.py` so the first run of `prep serve` detects a legacy `~/.local/share/codrag/` and migrates it to `~/.local/share/prep/` atomically, sentinel-gated. Per decisions D4 and D5.

**Why a separate task:** this is new behavior, not an identifier rename. It needs its own tests. Phase 113's migration machinery already handles CWD→XDG; we extend the same sentinel-file pattern for codrag→prep.

**Files:**
- Modify: `src/prep/core/data_dir_migration.py`
- Modify: `tests/test_data_dir_migration.py`
- Modify: `src/prep/core/paths.py` (if migration triggers from paths resolution)

- [ ] **Step 1: Read the existing migration module to understand the pattern**

```bash
.venv/bin/python -c "from prep.core.data_dir_migration import migrate_from_cwd; help(migrate_from_cwd)"
```

Identify: the existing sentinel file naming scheme, the conflict-resolution heuristic, and how the migration is invoked at daemon startup.

- [ ] **Step 2: Write a failing test for the legacy-codrag → prep migration**

Add to `tests/test_data_dir_migration.py`:

```python
def test_migrate_from_legacy_codrag_dir(tmp_path, monkeypatch):
    """First prep-serve run migrates ~/.local/share/codrag to ~/.local/share/prep."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "codrag"
    target = fake_home / ".local" / "share" / "prep"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"SQLITE payload")
    (legacy / "projects").mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    migrated = migrate_from_legacy_codrag()

    assert migrated is True
    assert target.exists()
    assert (target / "prep_settings.db").read_bytes() == b"SQLITE payload"
    assert (target / ".migrated_from_codrag").exists()
    assert not legacy.exists()


def test_migrate_from_legacy_codrag_is_idempotent(tmp_path, monkeypatch):
    """Sentinel file prevents re-migration."""
    fake_home = tmp_path / "home"
    target = fake_home / ".local" / "share" / "prep"
    target.mkdir(parents=True)
    (target / ".migrated_from_codrag").write_text("2026-04-21T00:00:00Z\n")
    legacy = fake_home / ".local" / "share" / "codrag"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"should_not_migrate")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    migrated = migrate_from_legacy_codrag()

    assert migrated is False
    assert legacy.exists()  # untouched
    assert not (target / "prep_settings.db").exists()


def test_migrate_from_legacy_codrag_conflict_preserves_both(tmp_path, monkeypatch):
    """Both dirs non-empty: target wins; legacy saved as conflict suffix."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "codrag"
    target = fake_home / ".local" / "share" / "prep"
    legacy.mkdir(parents=True)
    target.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"legacy_data")
    (target / "prep_settings.db").write_bytes(b"newer_data")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    result = migrate_from_legacy_codrag()

    assert result is True
    assert (target / "prep_settings.db").read_bytes() == b"newer_data"
    conflicts = list(fake_home.glob(".local/share/codrag.migration-conflict.*"))
    assert len(conflicts) == 1
    assert (conflicts[0] / "prep_settings.db").read_bytes() == b"legacy_data"
```

- [ ] **Step 3: Run the tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_data_dir_migration.py::test_migrate_from_legacy_codrag_dir -xvs
```

Expected: `ImportError` or `AttributeError: migrate_from_legacy_codrag` — function does not exist yet.

- [ ] **Step 4: Implement the function in `src/prep/core/data_dir_migration.py`**

Study the existing `migrate_from_cwd` function and mirror its structure. Add:

```python
def migrate_from_legacy_codrag() -> bool:
    """Migrate ~/.local/share/codrag/ -> ~/.local/share/prep/ once.

    Sentinel-gated: writes <target>/.migrated_from_codrag on completion.
    On conflict (both sides non-empty), target wins; legacy is renamed to
    <legacy_parent>/codrag.migration-conflict.<ISO8601>/.

    Returns True if a migration occurred (including conflict resolution),
    False if no migration was needed (sentinel exists or legacy absent).
    """
    import datetime
    import shutil
    from pathlib import Path

    home = Path.home()
    legacy = home / ".local" / "share" / "codrag"
    target = home / ".local" / "share" / "prep"
    sentinel = target / ".migrated_from_codrag"

    if sentinel.exists():
        return False
    if not legacy.exists():
        return False

    if target.exists() and any(target.iterdir()):
        # Conflict: target already has data. Preserve legacy as a sibling.
        suffix = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        conflict = legacy.with_name(f"codrag.migration-conflict.{suffix}")
        legacy.rename(conflict)
    else:
        # Target is absent or empty — move legacy in place.
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.rmdir()  # empty dir from a prior aborted run
        shutil.move(str(legacy), str(target))

    target.mkdir(exist_ok=True)
    sentinel.write_text(datetime.datetime.utcnow().isoformat() + "Z\n")
    return True
```

- [ ] **Step 5: Run the tests — expect green**

```bash
.venv/bin/pytest tests/test_data_dir_migration.py -xvs
```

Expected: 3 new tests pass; existing migration tests still pass.

- [ ] **Step 6: Wire the new migration into daemon startup**

Find the daemon startup hook that runs the existing `migrate_from_cwd`:
```bash
rg 'migrate_from_cwd' -t py
```

Add a call to `migrate_from_legacy_codrag()` immediately after it (order matters: codrag→prep at `~/.local/share/` is logically prior to any CWD→XDG migration of `prep_data/`).

Example (actual file will vary):
```python
# In src/prep/core/paths.py or src/prep/server.py startup:
from prep.core.data_dir_migration import migrate_from_cwd, migrate_from_legacy_codrag

migrate_from_legacy_codrag()  # codrag -> prep (Prep rename one-shot)
migrate_from_cwd()             # CWD prep_data -> XDG (Phase 113 one-shot)
```

- [ ] **Step 7: Embedded `.codrag` → `.prep` migration on project open (decision D5)**

Locate the project-load path:
```bash
rg 'def (open_project|load_project|register_project)' src/prep/ -t py
```

Add a one-liner at project open:
```python
from pathlib import Path
def _migrate_embedded_dir(project_root: Path) -> None:
    legacy = project_root / ".codrag"
    target = project_root / ".prep"
    if legacy.exists() and not target.exists():
        legacy.rename(target)
```

Call `_migrate_embedded_dir(project_root)` once before any read of `.prep/`.

Add a test:
```python
def test_migrate_embedded_codrag_dir(tmp_path):
    from prep.core.paths import _migrate_embedded_dir  # or wherever it lands
    project = tmp_path / "myproj"
    (project / ".codrag").mkdir(parents=True)
    (project / ".codrag" / "index.json").write_text("{}")

    _migrate_embedded_dir(project)

    assert (project / ".prep").exists()
    assert (project / ".prep" / "index.json").read_text() == "{}"
    assert not (project / ".codrag").exists()
```

Run the test; confirm green.

- [ ] **Step 8: End-to-end smoke**

Create a fake legacy dir and verify the daemon migrates it:
```bash
mkdir -p ~/.local/share/codrag-TEST
# Only use if you do NOT have a real ~/.local/share/codrag on the machine:
#  mkdir -p ~/.local/share/codrag && touch ~/.local/share/codrag/prep_settings.db
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 3
ls -la ~/.local/share/prep/.migrated_from_codrag 2>/dev/null && echo "MIGRATION OK"
kill $DAEMON_PID
rm -rf ~/.local/share/codrag-TEST
```

Expected: `MIGRATION OK` printed; daemon starts without error.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "rename(phase-3b): add codrag->prep data-dir auto-migration (D4, D5)"
```

---

## Task 4: Rust workspace

**Goal:** Rename all seven `engine/crates/codrag-*` to `prep-*`, update the workspace Cargo.toml, rewrite every `use codrag_*` statement, and rename the maturin-bound Python extension module from `codrag_engine` to `prep_engine`. After this task, `cargo check --workspace` and `cargo test --workspace` pass.

**Files:**
- `git mv`: 7 crate dirs under `engine/crates/`
- Modify: `engine/Cargo.toml`, 7× `engine/crates/*/Cargo.toml`
- Modify: `engine/pyproject.toml` (maturin module name)
- Modify: every `.rs` with `use codrag_*` or `codrag_engine`

- [ ] **Step 1: Rename crate directories**

```bash
cd engine
git mv crates/codrag-chunking crates/prep-chunking
git mv crates/codrag-engine   crates/prep-engine
git mv crates/codrag-graph    crates/prep-graph
git mv crates/codrag-parser   crates/prep-parser
git mv crates/codrag-sanitize crates/prep-sanitize
git mv crates/codrag-selfheal crates/prep-selfheal
git mv crates/codrag-walker   crates/prep-walker
cd ..
```

- [ ] **Step 2: Update workspace Cargo.toml**

```bash
sed -i '' -e 's|crates/codrag-|crates/prep-|g' engine/Cargo.toml

# Workspace-level package name and any workspace deps:
sed -i '' -e 's/\bcodrag-/prep-/g' engine/Cargo.toml
```

- [ ] **Step 3: Update each crate's Cargo.toml**

Each crate file has a `[package] name = "codrag-foo"`, `[lib] name = "codrag_foo"`, and path dependencies pointing at sibling crates (`codrag-parser = { path = "../codrag-parser" }`).

```bash
for f in engine/crates/prep-*/Cargo.toml; do
  sed -i '' \
    -e 's/^name = "codrag-/name = "prep-/g' \
    -e 's/^name = "codrag_/name = "prep_/g' \
    -e 's|path = "\.\./codrag-|path = "../prep-|g' \
    -e 's/\bcodrag-\([a-z]\+\)\b/prep-\1/g' \
    -e 's/\bcodrag_\([a-z]\+\)\b/prep_\1/g' \
    "$f"
done
```

- [ ] **Step 4: Update Rust source `use` statements**

The underscore form (`codrag_foo`) is the Rust module path; the hyphen form (`codrag-foo`) is the crate name in TOML only.

```bash
rg -l 'codrag_\w+' engine --type rust | xargs sed -i '' 's/\bcodrag_\([a-z]\+\)\b/prep_\1/g'

# Module-level doc comments with "CoDRAG":
rg -l 'CoDRAG' engine --type rust | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' engine --type rust | xargs sed -i '' 's/\bcodrag\b/prep/g'
```

- [ ] **Step 5: Update maturin/PyO3 module name**

```bash
sed -i '' \
  -e 's/^module-name = "codrag_engine"/module-name = "prep_engine"/' \
  -e 's/^name = "codrag-engine"/name = "prep-engine"/' \
  engine/pyproject.toml

# Also in the prep-engine crate's src/lib.rs #[pymodule]:
rg -l '#\[pymodule\].*codrag_engine' engine | \
  xargs sed -i '' 's/codrag_engine/prep_engine/g'
```

- [ ] **Step 6: Verify cargo check / test**

```bash
cd engine
cargo check --workspace 2>&1 | tail -20
cargo test --workspace --no-run 2>&1 | tail -20
cd ..
```

Expected: clean build. If a crate fails to resolve a path dep, inspect its `Cargo.toml` — a missed `codrag-` substring is the usual cause.

Run the tests:
```bash
cd engine && cargo test --workspace 2>&1 | tail -10 && cd ..
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-4): rust workspace codrag-* -> prep-* crates, modules, pyo3 binding"
```

---

## Task 5: Python ↔ Rust bindings

**Goal:** Rebuild the maturin extension under the new name (`prep_engine`) and update Python code that imports it. After this task, `import prep_engine` works from Python.

**Files:**
- Modify: any `.py` that does `import codrag_engine` or `from codrag_engine`

- [ ] **Step 1: Rebuild maturin extension**

```bash
cd engine
.venv/../.venv/bin/maturin develop 2>&1 | tail -20
cd ..
```

(Adjust path to `maturin` if it lives in the project venv.)

Expected: produces `prep_engine` `.so` / `.pyd` in the active venv's `site-packages`.

- [ ] **Step 2: Rewrite Python imports**

```bash
rg -l 'codrag_engine' -t py | xargs sed -i '' 's/codrag_engine/prep_engine/g'
```

- [ ] **Step 3: Verify the extension imports**

```bash
.venv/bin/python -c "import prep_engine; print(dir(prep_engine))"
```

Expected: prints list of exported names (non-empty).

- [ ] **Step 4: Run the full Python test suite — Rust boundary is now exercised**

```bash
.venv/bin/pytest tests/ -x --timeout=120 -q 2>&1 | tail -20
```

Expected: same pass/fail profile as baseline (allowing for the net-new Task 3B tests which pass).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "rename(phase-5): python<->rust binding (maturin module prep_engine)"
```

---

## Task 6: npm workspace package.json names

**Goal:** Rename every `package.json` `name` field from `@codrag/*` or `codrag-*` to the `@prep/*` / `prep-*` equivalent. Workspace resolution will break between this task and Task 7 — hold off on `npm install` until after Task 7.

**Files:**
- Modify: `package.json` (root), `packages/ui/package.json`, `packages/vscode/package.json`, `packages/vscode/webview-ui/package.json`, `packages/paperclip-plugin-codrag/package.json`, `packages/paperclip-skill/package.json`, `src/codrag/dashboard/package.json` (wait — we already renamed to `src/prep/dashboard/package.json` in Task 2), `websites/apps/*/package.json` (4 files)

- [ ] **Step 1: Enumerate current names**

```bash
for pj in $(fd -H package.json | grep -v node_modules | grep -v .venv); do
  echo "$pj: $(jq -r .name "$pj" 2>/dev/null)"
done
```

Save this output for reference — confirms what each package is currently called.

- [ ] **Step 2: Rewrite scoped npm names**

```bash
rg -l '"@codrag/' -g '*.json' | xargs sed -i '' 's|"@codrag/|"@prep/|g'
```

This handles: `"@codrag/ui"` → `"@prep/ui"`, `"@codrag/paperclip-plugin"` → `"@prep/paperclip-plugin"`, etc. Applies to the `"name":` field AND any `"dependencies"` / `"devDependencies"` entries that point at workspace packages.

- [ ] **Step 3: Rewrite unscoped codrag-* names**

```bash
rg -l '"codrag-' -g '*.json' | xargs sed -i '' 's|"codrag-|"prep-|g'
```

This catches `"name": "codrag-vscode"` → `"prep-vscode"`, and any dependency like `"codrag-shared-config": "*"`.

- [ ] **Step 4: Rewrite `displayName` / `description` brand strings**

```bash
rg -l '"displayName": ".*CoDRAG' -g '*.json' | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '"description": ".*CoDRAG' -g '*.json' | xargs sed -i '' 's/CoDRAG/Prep/g'
```

- [ ] **Step 5: Root turbo.json and lockfile cleanup**

```bash
rg -l 'codrag' turbo.json 2>/dev/null | xargs sed -i '' 's/codrag/prep/g'
rg -l 'CoDRAG' turbo.json 2>/dev/null | xargs sed -i '' 's/CoDRAG/Prep/g'
```

The `package-lock.json` regenerates in Task 19; do not hand-edit it now.

- [ ] **Step 6: Verify json syntactic integrity**

```bash
for pj in $(fd -H package.json | grep -v node_modules | grep -v .venv); do
  jq empty "$pj" || echo "BROKEN JSON: $pj"
done
```

Expected: silent (no "BROKEN JSON" lines). If one fails, hand-inspect the `sed` damage.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-6): npm workspace package names @codrag/* -> @prep/*"
```

---

## Task 7: npm imports

**Goal:** Rewrite every TS/TSX/JS/MJS import that references `@codrag/*` to `@prep/*`. After this task, `npm install` + `npm run typecheck` pass.

**Files:** ~157 files, ~292 occurrences. All under `packages/`, `src/prep/dashboard/`, `websites/apps/`, `scripts/`.

- [ ] **Step 1: Rewrite TS/JS imports**

```bash
# ES import statements:
rg -l 'from "@codrag/' | xargs sed -i '' 's|from "@codrag/|from "@prep/|g'
rg -l "from '@codrag/" | xargs sed -i '' "s|from '@codrag/|from '@prep/|g"

# Bare import-side-effect form:
rg -l 'import "@codrag/' | xargs sed -i '' 's|import "@codrag/|import "@prep/|g'
rg -l "import '@codrag/" | xargs sed -i '' "s|import '@codrag/|import '@prep/|g"

# Dynamic imports:
rg -l 'import\("@codrag/' | xargs sed -i '' 's|import("@codrag/|import("@prep/|g'
rg -l "import\('@codrag/" | xargs sed -i '' "s|import('@codrag/|import('@prep/|g"

# Require (legacy):
rg -l 'require\("@codrag/' | xargs sed -i '' 's|require("@codrag/|require("@prep/|g'
rg -l "require\('@codrag/" | xargs sed -i '' "s|require('@codrag/|require('@prep/|g"
```

Verify:
```bash
rg '@codrag/'
```
Expected: 0 matches.

- [ ] **Step 2: Rewrite tsconfig path aliases**

```bash
rg -l '"@codrag/' tsconfig*.json packages/*/tsconfig*.json websites/apps/*/tsconfig*.json 2>/dev/null | \
  xargs sed -i '' 's|"@codrag/|"@prep/|g'
```

- [ ] **Step 3: Rewrite unscoped `codrag-*` package references in TS imports (defensive)**

```bash
rg -l 'from "codrag-' -g '*.{ts,tsx,js,mjs}' | xargs sed -i '' 's|from "codrag-|from "prep-|g'
rg -l "from 'codrag-" -g '*.{ts,tsx,js,mjs}' | xargs sed -i '' "s|from 'codrag-|from 'prep-|g"
```

- [ ] **Step 4: npm install + typecheck**

```bash
npm install 2>&1 | tail -20
npm run typecheck 2>&1 | tail -30
```

Expected: `npm install` resolves all workspace packages; `typecheck` returns 0 errors (or same baseline errors as Task 0).

Likely transient failures:
- "Cannot find module '@prep/ui'": a `package.json` in Task 6 missed the rename. Re-run:
  ```bash
  rg '"@codrag/' -g '*.json'
  ```
- Circular dep or alias resolution: check `turbo.json` and root `tsconfig.base.json`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "rename(phase-7): ts/js imports @codrag/* -> @prep/*, typecheck green"
```

---

## Task 8: VS Code extension

**Goal:** Rename the VS Code extension's user-facing surface — commands (`codrag.*` → `prep.*`), config keys (`codrag.daemonPort` → `prep.daemonPort`), icon files, view containers. After this task, `cd packages/vscode && npm run build` produces a `.vsix` whose `package.json` has no "codrag" references.

**Files:**
- Modify: `packages/vscode/package.json`, `packages/vscode/src/extension.ts`, `packages/vscode/src/**/*.ts`, `packages/vscode/webview-ui/src/**/*.{ts,tsx}`
- `git mv`: `packages/vscode/media/codrag-icon.png` → `prep-icon.png`; `codrag-sidebar.svg` → `prep-sidebar.svg`

- [ ] **Step 1: Rename media files**

```bash
git mv packages/vscode/media/codrag-icon.png packages/vscode/media/prep-icon.png
git mv packages/vscode/media/codrag-sidebar.svg packages/vscode/media/prep-sidebar.svg
```

- [ ] **Step 2: Rewrite `package.json` contribution IDs**

Key fields: `contributes.commands[].command` (prefix `codrag.`), `contributes.configuration.properties` (keys `codrag.*`), `contributes.viewsContainers.activitybar[].id` (`codrag-sidebar`), `contributes.views.<containerId>` object key, `contributes.menus.*[].when` (references command IDs).

```bash
# The package.json `name`/`displayName` already updated in Task 6.
# Command IDs, config keys, view container IDs:
sed -i '' \
  -e 's|"codrag\.|"prep.|g' \
  -e 's|"codrag-sidebar"|"prep-sidebar"|g' \
  -e 's|"icon": "media/codrag-|"icon": "media/prep-|g' \
  packages/vscode/package.json

# Verify:
rg -i 'codrag' packages/vscode/package.json
```

Expected: 0 matches (or only publisher `magnetic-anomaly`, which is unrelated — decision D8 keeps it).

- [ ] **Step 3: Rewrite TS registerCommand / getConfiguration calls**

```bash
# registerCommand("codrag.foo") -> registerCommand("prep.foo")
rg -l 'registerCommand\("codrag\.' packages/vscode | \
  xargs sed -i '' 's|registerCommand("codrag\.|registerCommand("prep.|g'
rg -l "registerCommand\('codrag\\." packages/vscode | \
  xargs sed -i '' "s|registerCommand('codrag\\.|registerCommand('prep.|g"

# executeCommand same pattern:
rg -l 'executeCommand\("codrag\.' packages/vscode | \
  xargs sed -i '' 's|executeCommand("codrag\.|executeCommand("prep.|g'
rg -l "executeCommand\('codrag\\." packages/vscode | \
  xargs sed -i '' "s|executeCommand('codrag\\.|executeCommand('prep.|g"

# getConfiguration("codrag") -> getConfiguration("prep")
rg -l 'getConfiguration\("codrag"' packages/vscode | \
  xargs sed -i '' 's|getConfiguration("codrag")|getConfiguration("prep")|g'
rg -l "getConfiguration\('codrag'" packages/vscode | \
  xargs sed -i '' "s|getConfiguration('codrag')|getConfiguration('prep')|g"

# Icon path refs:
rg -l 'media/codrag-icon' packages/vscode | xargs sed -i '' 's|media/codrag-icon|media/prep-icon|g'
rg -l 'media/codrag-sidebar' packages/vscode | xargs sed -i '' 's|media/codrag-sidebar|media/prep-sidebar|g'
```

- [ ] **Step 4: Brand-name pass in extension TS/TSX**

```bash
rg -l 'CoDRAG' packages/vscode | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' packages/vscode | xargs sed -i '' 's/\bcodrag\b/prep/g'
```

- [ ] **Step 5: Build the extension**

```bash
cd packages/vscode
npm run build 2>&1 | tail -20
cd ../..
```

Expected: produces a `.vsix` (or an equivalent bundled output). No TypeScript errors.

Optional — package and inspect:
```bash
cd packages/vscode
npx vsce package --no-git-tag-version 2>&1 | tail -5
unzip -p prep-vscode-*.vsix package.json | jq . | head -40
cd ../..
```

Expected: package.json shows `name: "prep-vscode"`, commands prefixed `prep.`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "rename(phase-8): vscode extension commands, config keys, icons"
```

---

## Task 9: PyInstaller sidecar + wrapper scripts

**Goal:** Rename `codrag-daemon.spec` → `prep-daemon.spec` and any scripts that invoke PyInstaller. After this task, `pyinstaller prep-daemon.spec` produces `dist/prep-daemon`. This must precede Task 10 (Tauri) because Tauri's `externalBin` references the sidecar binary.

**Files:**
- `git mv`: `codrag-daemon.spec` → `prep-daemon.spec`, `scripts/codrag-mcp-wrapper.sh` → `scripts/prep-mcp-wrapper.sh`
- Modify: `scripts/build_sidecar.sh`, the renamed `.spec` file internals, any CI workflow that builds the sidecar

- [ ] **Step 1: Rename the spec file and wrapper**

```bash
git mv codrag-daemon.spec prep-daemon.spec
git mv scripts/codrag-mcp-wrapper.sh scripts/prep-mcp-wrapper.sh
git mv scripts/publish_codrag_mcp_subtree.sh scripts/publish_prep_mcp_subtree.sh
```

- [ ] **Step 2: Update PyInstaller spec internals**

```bash
sed -i '' \
  -e 's/name="codrag-daemon"/name="prep-daemon"/g' \
  -e "s/name='codrag-daemon'/name='prep-daemon'/g" \
  -e 's/codrag\.cli/prep.cli/g' \
  -e 's/CoDRAG/Prep/g' \
  -e 's/codrag/prep/g' \
  prep-daemon.spec
```

Review:
```bash
cat prep-daemon.spec | head -40
```

Check the `Analysis(scripts=...)` line references `src/prep/cli.py` (or wherever the entry sits), and that `name="prep-daemon"` appears in the `EXE(...)` call.

- [ ] **Step 3: Update build_sidecar.sh**

```bash
sed -i '' \
  -e 's/codrag-daemon/prep-daemon/g' \
  -e 's/codrag\.spec/prep.spec/g' \
  -e 's/CoDRAG/Prep/g' \
  scripts/build_sidecar.sh
```

- [ ] **Step 4: Update MCP wrapper**

```bash
sed -i '' \
  -e 's/codrag/prep/g' \
  -e 's/CoDRAG/Prep/g' \
  scripts/prep-mcp-wrapper.sh
```

- [ ] **Step 5: Update publish_prep_mcp_subtree.sh**

This script's remote URL must stay pointing at `MagneticAnomaly/CoDRAG-MCP.git` until GitHub rename happens (Task 22). Add a one-line reminder:

```bash
sed -i '' 's/codrag/prep/g' scripts/publish_prep_mcp_subtree.sh

# Then verify the remote URL section — it should still reference the CURRENT GitHub name:
grep -n 'git@github.com' scripts/publish_prep_mcp_subtree.sh
# The URL line referencing CoDRAG-MCP is CORRECT at this moment;
# Task 22 flips it. Do NOT rewrite the URL yet.
```

If the `sed` changed the URL from `CoDRAG-MCP.git` to `prep-MCP.git`, revert *only that URL line*:
```bash
sed -i '' 's|MagneticAnomaly/prep-MCP.git|MagneticAnomaly/CoDRAG-MCP.git|g' scripts/publish_prep_mcp_subtree.sh
```

Leave a TODO comment:
```bash
# (Manually, in the file)
# TODO(Task 22): after GitHub rename, change URL to MagneticAnomaly/Prep-MCP.git
```

- [ ] **Step 6: Same treatment for publish_deploy_subtree.sh**

```bash
sed -i '' -e 's/CoDRAG/Prep/g' -e 's/codrag/prep/g' scripts/publish_deploy_subtree.sh
# Revert the URL if it got swept:
sed -i '' 's|MagNeticAnomaly/prep-deploy|MagNeticAnomaly/codrag-deploy|g' scripts/publish_deploy_subtree.sh
sed -i '' 's|MagneticAnomaly/prep-deploy|MagNeticAnomaly/codrag-deploy|g' scripts/publish_deploy_subtree.sh
```

- [ ] **Step 7: Build the sidecar**

```bash
.venv/bin/pyinstaller prep-daemon.spec --clean 2>&1 | tail -10
ls -la dist/prep-daemon
```

Expected: `dist/prep-daemon` exists and is executable. Smoke-test:
```bash
./dist/prep-daemon --help | head -5
```
Expected: prints Prep CLI help.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "rename(phase-9): pyinstaller sidecar spec, wrapper, publish scripts"
```

---

## Task 10: Tauri desktop

**Goal:** Update `tauri.conf.json` with new bundle ID `io.runprep.app`, rename `externalBin: ["codrag-daemon"]` → `["prep-daemon"]`, flip updater endpoints to the future `MagneticAnomaly/Prep` repo URL, update window titles, and rename bundled icon files. After this task, `cargo tauri build --debug` produces `Prep.app` that launches and talks to the sidecar.

**Files:**
- Modify: `src/prep/dashboard/src-tauri/tauri.conf.json`
- Modify: `src/prep/dashboard/src-tauri/Cargo.toml`, `src/main.rs`, `lib.rs`, `build.rs`
- `git mv`: any `codrag-*.png` in `src/prep/dashboard/src-tauri/icons/`

- [ ] **Step 1: Update tauri.conf.json**

```bash
TAURI_CONF="src/prep/dashboard/src-tauri/tauri.conf.json"
sed -i '' \
  -e 's|"productName": "CoDRAG"|"productName": "Prep"|g' \
  -e 's|"identifier": "io\.codrag\.app"|"identifier": "io.runprep.app"|g' \
  -e 's|"codrag-daemon"|"prep-daemon"|g' \
  -e 's|MagneticAnomaly/CoDRAG-MCP/releases|MagneticAnomaly/Prep/releases|g' \
  -e 's|EricBintner/CoDRAG/releases|MagneticAnomaly/Prep/releases|g' \
  -e 's|"title": "CoDRAG"|"title": "Prep"|g' \
  -e 's|codrag\.io|runprep.io|g' \
  "$TAURI_CONF"

# Verify:
rg -i 'codrag|CoDRAG' "$TAURI_CONF"
```
Expected: 0 matches.

- [ ] **Step 2: Rename any codrag-named icon files**

```bash
for f in src/prep/dashboard/src-tauri/icons/codrag-*.png; do
  [ -e "$f" ] || continue
  new="${f/codrag-/prep-}"
  git mv "$f" "$new"
done
```

(Size-named icons like `32x32.png` and `icon.icns` stay — their names don't contain "codrag".)

- [ ] **Step 3: Update Tauri Rust source**

```bash
TAURI_SRC="src/prep/dashboard/src-tauri"
rg -l 'codrag-daemon\|codrag_daemon\|CoDRAG\|APP_NAME.*CoDRAG' "$TAURI_SRC" | \
  xargs sed -i '' \
    -e 's|"codrag-daemon"|"prep-daemon"|g' \
    -e 's|CoDRAG|Prep|g' \
    -e 's|codrag|prep|g'
```

- [ ] **Step 4: Update Cargo.toml in src-tauri**

```bash
sed -i '' \
  -e 's/^name = "codrag-/name = "prep-/g' \
  -e 's/^name = "codrag_/name = "prep_/g' \
  -e 's/codrag/prep/g' \
  -e 's/CoDRAG/Prep/g' \
  "$TAURI_SRC/Cargo.toml"
```

- [ ] **Step 5: Ensure sidecar binary is discoverable**

Tauri looks for `externalBin` binaries in `src-tauri/binaries/`. Copy the freshly-built sidecar:

```bash
mkdir -p "$TAURI_SRC/binaries"
# Tauri expects arch-suffixed binaries. On Apple Silicon:
cp dist/prep-daemon "$TAURI_SRC/binaries/prep-daemon-aarch64-apple-darwin"
# If on x86_64 machine, use the appropriate triple instead.
chmod +x "$TAURI_SRC/binaries/prep-daemon-aarch64-apple-darwin"
```

- [ ] **Step 6: Build**

```bash
cd src/prep/dashboard
npm run build 2>&1 | tail -10          # build web frontend first
cd src-tauri
cargo tauri build --debug 2>&1 | tail -20
cd ../../../..
```

Expected: produces `src/prep/dashboard/src-tauri/target/debug/bundle/macos/Prep.app`.

- [ ] **Step 7: Launch sanity**

```bash
open src/prep/dashboard/src-tauri/target/debug/bundle/macos/Prep.app
# Verify: title bar says "Prep"; menu bar says "Prep"; dock badge reads "Prep"
# Wait ~5 sec for the sidecar to come up, then:
curl -s http://localhost:8400/health | head -5
# Expected: daemon healthy
# Quit Prep via ⌘-Q
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "rename(phase-10): tauri desktop bundle id io.runprep.app, sidecar prep-daemon"
```

---

## Task 11: Public subtrees

**Goal:** Rename the outer-repo paths `public/codrag-mcp/` → `public/prep-mcp/` and `public/codrag-deploy/` → `public/prep-deploy/`. Each contains a nested `.git/`; the rename moves the nested repo along with it. The GitHub-side rename of the sibling repos happens in Task 22.

**Files:**
- `git mv`: `public/codrag-mcp/` → `public/prep-mcp/`, `public/codrag-deploy/` → `public/prep-deploy/`

- [ ] **Step 1: Rename subtree directories**

```bash
git mv public/codrag-mcp public/prep-mcp
git mv public/codrag-deploy public/prep-deploy
```

The nested `.git/` inside each moves along with the rest of the directory — no history inside the nested repos is touched.

- [ ] **Step 2: Rename subtree README / logo files**

```bash
git mv public/prep-mcp/codrag-logo.png public/prep-mcp/prep-logo.png 2>/dev/null || true
git mv public/prep-mcp/codrag-github-header.png public/prep-mcp/prep-github-header.png 2>/dev/null || true
git mv public/prep-deploy/codrag-github-header.png public/prep-deploy/prep-github-header.png 2>/dev/null || true
```

(`|| true` because these are in the nested repos; if the files don't exist or the nested repo has its own rules, keep moving.)

- [ ] **Step 3: Rewrite content inside the subtrees (README, docs)**

These subtrees get published as sibling repos. Their content needs the rename too.

```bash
for subtree in public/prep-mcp public/prep-deploy; do
  rg -l 'CoDRAG' "$subtree" --glob '!.git' | xargs sed -i '' 's/CoDRAG/Prep/g'
  rg -l '\bcodrag\b' "$subtree" --glob '!.git' | xargs sed -i '' 's/\bcodrag\b/prep/g'
  rg -l 'codrag\.io' "$subtree" --glob '!.git' | xargs sed -i '' 's/codrag\.io/runprep.io/g'

  # GitHub URLs inside the subtrees reference the OLD names; they get rewritten
  # to the new names NOW, even though GitHub rename happens in Task 22. These
  # subtrees get re-published in Task 22 after the GitHub rename completes.
  rg -l 'MagneticAnomaly/CoDRAG-MCP' "$subtree" --glob '!.git' | \
    xargs sed -i '' 's|MagneticAnomaly/CoDRAG-MCP|MagneticAnomaly/Prep-MCP|g'
  rg -l 'MagNeticAnomaly/codrag-deploy' "$subtree" --glob '!.git' | \
    xargs sed -i '' 's|MagNeticAnomaly/codrag-deploy|MagneticAnomaly/Prep-deploy|g'
  rg -l 'EricBintner/CoDRAG' "$subtree" --glob '!.git' | \
    xargs sed -i '' 's|EricBintner/CoDRAG|MagneticAnomaly/Prep|g'
done
```

- [ ] **Step 4: Verify no leftover refs inside the subtrees (outside their .git/)**

```bash
rg -i 'codrag' public/prep-mcp --glob '!.git' | head
rg -i 'codrag' public/prep-deploy --glob '!.git' | head
```

Expected: 0 hits.

- [ ] **Step 5: Commit in the outer repo**

```bash
git add -A
git commit -m "rename(phase-11): public subtrees codrag-mcp/deploy -> prep-mcp/deploy"
```

Note: the *nested* `.git/` in each subtree is not committed yet to its sibling GitHub repo — that happens in Task 22 via the publish scripts.

---

## Task 12: MCP configs

**Goal:** Flip the MCP server key in every client config from `"codrag"` to `"prep"` and point command paths at the renamed wrapper script.

**Files:**
- Modify: `.claude/mcp.json`, `.cursor/mcp.json`, `mcp-server.json`

- [ ] **Step 1: Rewrite server key**

```bash
for cfg in .claude/mcp.json .cursor/mcp.json mcp-server.json; do
  [ -f "$cfg" ] || continue
  sed -i '' \
    -e 's|"codrag":|"prep":|g' \
    -e 's|codrag-mcp-wrapper|prep-mcp-wrapper|g' \
    -e 's|CODRAG_|PREP_|g' \
    -e 's|CoDRAG|Prep|g' \
    -e 's|codrag|prep|g' \
    "$cfg"
  jq empty "$cfg" || echo "BROKEN JSON: $cfg"
done
```

- [ ] **Step 2: Update `.cursor/rules/codrag.mdc` filename (if present)**

```bash
if [ -f .cursor/rules/codrag.mdc ]; then
  git mv .cursor/rules/codrag.mdc .cursor/rules/prep.mdc
  sed -i '' 's/codrag/prep/g; s/CoDRAG/Prep/g' .cursor/rules/prep.mdc
fi
```

- [ ] **Step 3: Regenerate `AGENTS.md` for this repo**

```bash
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 3
# The daemon auto-regenerates AGENTS.md based on its own rules_generator.
# If there's a CLI command, use it:
.venv/bin/prep rules write 2>/dev/null || true
# Otherwise hit the endpoint:
curl -s -X POST http://localhost:8400/api/rules/regenerate 2>/dev/null || true
sleep 2
kill $DAEMON_PID
rg -i 'codrag' AGENTS.md 2>/dev/null | head
```

Expected: `AGENTS.md` contains no "codrag" — if it does, the rules_generator needs another pass (Task 13 addresses generator-internal strings).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "rename(phase-12): mcp configs server key codrag -> prep, regen AGENTS.md"
```

---

## Task 13: Rules generator + templates

**Goal:** Update `src/prep/core/rules_generator.py` so every AGENTS.md / CLAUDE.md / rules file it writes into *client projects* says "Prep", references `prep_*` tools, and uses `<!-- prep-managed-start -->` markers. Also update any templated `.cursor/rules/*.mdc`, Windsurf `.windsurfrules`, and Copilot instruction files.

**Files:**
- Modify: `src/prep/core/rules_generator.py`
- Modify: any `templates/` subdirectory used by the generator
- Modify: `src/prep/core/atlas/generator.py` (atlas writes into the managed content)

- [ ] **Step 1: Rewrite managed-content markers and hardcoded tool references**

```bash
RG="src/prep/core/rules_generator.py"
sed -i '' \
  -e 's|<!-- codrag-managed-start -->|<!-- prep-managed-start -->|g' \
  -e 's|<!-- codrag-managed-end -->|<!-- prep-managed-end -->|g' \
  -e 's|codrag-managed|prep-managed|g' \
  -e 's|codrag_search|prep_search|g' \
  -e 's|codrag_impact|prep_impact|g' \
  -e 's|codrag_audit|prep_audit|g' \
  -e 's|codrag_observe|prep_observe|g' \
  -e 's|codrag_concepts|prep_concepts|g' \
  -e 's|CoDRAG|Prep|g' \
  -e 's|codrag\.io|runprep.io|g' \
  -e 's|\bcodrag\b|prep|g' \
  "$RG"
```

- [ ] **Step 2: Scan for any remaining codrag in generator and atlas**

```bash
rg -i 'codrag' src/prep/core/rules_generator.py src/prep/core/atlas/
```
Expected: 0 matches (or matches only inside migration-awareness comments, if any — keep those).

- [ ] **Step 3: Update filename references for the cursor rules file**

Find where the generator writes `.cursor/rules/codrag.mdc` and flip to `.cursor/rules/prep.mdc`:
```bash
rg -n 'codrag\.mdc' src/prep/
```
Edit each hit: `codrag.mdc` → `prep.mdc`.

- [ ] **Step 4: Regenerate for this repo and verify**

```bash
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 3
.venv/bin/prep rules write 2>/dev/null || curl -s -X POST http://localhost:8400/api/rules/regenerate
sleep 2
kill $DAEMON_PID
bash scripts/rename_gate.sh AGENTS.md CLAUDE.md 2>/dev/null | head
# or equivalent:
rg -i 'codrag' AGENTS.md CLAUDE.md .cursor/rules/prep.mdc 2>/dev/null | head
```

Expected: 0 hits in the generated files. If CLAUDE.md still shows "codrag" hits, those are owner-hand-written; Task 16 rewrites CLAUDE.md prose. The generated section must be clean.

- [ ] **Step 5: Tests**

Find any tests of the generator:
```bash
rg -l 'rules_generator|codrag-managed|prep-managed' tests/
.venv/bin/pytest tests/ -k 'rules or agents or atlas' -xvs --timeout=60 2>&1 | tail -20
```

Expected: all green. If a test asserts on `codrag-managed` markers, update the test to assert on `prep-managed`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "rename(phase-13): rules_generator templates, markers, tool refs in generated AGENTS.md"
```

---

## Task 14: Websites

**Goal:** Rename the 4 Next.js apps' content, domains, routes, metadata, and the defunct `websites/MagneticAnomaly/` references. After this task, each site's dev server renders with zero "CoDRAG" in the DOM and all links point at `runprep.io`.

**Files:**
- Modify: `websites/apps/marketing/`, `websites/apps/docs/`, `websites/apps/support/`, `websites/apps/payments/`
- Modify: `websites/MagneticAnomaly/src/App.jsx` and any other files inside that project (keep the directory per D3)
- Modify: shared components in `packages/ui/src/components/marketing/`
- Modify: `src/prep/core/feature_gate.py` pricing URL (flagged in spec §11)
- `git mv`: `websites/apps/marketing/src/app/compare/codrag-vs-*/` → `prep-vs-*/`

- [ ] **Step 1: Domain rewrite across all websites**

```bash
# codrag.io / subdomains -> runprep.io / subdomains
rg -l 'codrag\.io' websites | xargs sed -i '' 's/codrag\.io/runprep.io/g'

# codrag.ai (decision: delete — never existed; 5 refs total)
rg -l 'codrag\.ai' websites | xargs sed -i '' 's|https://codrag\.ai[^"''\ ]*||g; s|codrag\.ai||g'
# Re-check for stragglers:
rg 'codrag\.ai' websites
```

- [ ] **Step 2: Email addresses**

```bash
rg -l '@codrag\.io' websites | xargs sed -i '' 's|@codrag\.io|@runprep.io|g'
# Also catch the fallback `@codrag.com` if present:
rg -l '@codrag\.com' websites | xargs sed -i '' 's|@codrag\.com|@runprep.io|g'
```

- [ ] **Step 3: Brand strings across websites**

```bash
rg -l 'CoDRAG' websites | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' websites | xargs sed -i '' 's/\bcodrag\b/prep/g'
rg -l 'CODRAG' websites | xargs sed -i '' 's/CODRAG/PREP/g'
```

- [ ] **Step 4: Rename comparison routes**

```bash
MKT="websites/apps/marketing/src/app"
[ -d "$MKT/compare/codrag-vs-greptile" ] && git mv "$MKT/compare/codrag-vs-greptile" "$MKT/compare/prep-vs-greptile"
[ -d "$MKT/compare/codrag-vs-cursor-indexing" ] && git mv "$MKT/compare/codrag-vs-cursor-indexing" "$MKT/compare/prep-vs-cursor-indexing"
# Generic scan for any other codrag-vs-* dirs:
fd -H -t d 'codrag-vs-' "$MKT" | while read -r d; do
  newd="${d/codrag-vs-/prep-vs-}"
  git mv "$d" "$newd"
done
```

Then rewrite any link references to these old routes:
```bash
rg -l 'compare/codrag-vs-' websites packages/ui | \
  xargs sed -i '' 's|compare/codrag-vs-|compare/prep-vs-|g'
```

- [ ] **Step 5: netlify.toml / next.config / env var cleanup**

```bash
for app in websites/apps/marketing websites/apps/docs websites/apps/support websites/apps/payments; do
  [ -f "$app/netlify.toml" ] && sed -i '' 's/CODRAG_/PREP_/g; s/codrag/prep/g; s/CoDRAG/Prep/g' "$app/netlify.toml"
  [ -f "$app/next.config.js" ] && sed -i '' 's/codrag/prep/g; s/CoDRAG/Prep/g' "$app/next.config.js"
  [ -f "$app/next.config.mjs" ] && sed -i '' 's/codrag/prep/g; s/CoDRAG/Prep/g' "$app/next.config.mjs"
done
```

- [ ] **Step 6: Shared marketing components in packages/ui**

```bash
MKT_COMPS="packages/ui/src/components/marketing"
rg -l 'CoDRAG' "$MKT_COMPS" | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' "$MKT_COMPS" | xargs sed -i '' 's/\bcodrag\b/prep/g'
rg -l 'codrag\.io' "$MKT_COMPS" | xargs sed -i '' 's/codrag\.io/runprep.io/g'
```

- [ ] **Step 7: Feature-gate URL in Python (cross-repo reference)**

```bash
FG="src/prep/core/feature_gate.py"
if [ -f "$FG" ]; then
  sed -i '' 's|codrag\.io/pricing|runprep.io/pricing|g' "$FG"
fi
# Update the matching test assertion:
FG_TEST="tests/test_feature_gate.py"
if [ -f "$FG_TEST" ]; then
  sed -i '' 's|codrag\.io/pricing|runprep.io/pricing|g' "$FG_TEST"
fi
```

- [ ] **Step 8: `websites/MagneticAnomaly/` content sweep (directory stays per D3)**

```bash
MA="websites/MagneticAnomaly"
[ -d "$MA" ] && {
  rg -l 'CoDRAG' "$MA" | xargs sed -i '' 's/CoDRAG/Prep/g'
  rg -l '\bcodrag\b' "$MA" | xargs sed -i '' 's/\bcodrag\b/prep/g'
  rg -l 'codrag\.io' "$MA" | xargs sed -i '' 's/codrag\.io/runprep.io/g'
}
```

- [ ] **Step 9: Lemon Squeezy / payments brand names (no SKU changes — decision out of scope)**

```bash
PAY="websites/apps/payments"
# Brand pass already done in Step 3; verify product page copy:
rg -i 'codrag' "$PAY"
```
Expected: 0 hits (after Step 3). If any remain, hand-edit.

- [ ] **Step 10: Build each site**

```bash
cd websites/apps/marketing && npm run build 2>&1 | tail -5 && cd ../../..
cd websites/apps/docs      && npm run build 2>&1 | tail -5 && cd ../../..
cd websites/apps/support   && npm run build 2>&1 | tail -5 && cd ../../..
cd websites/apps/payments  && npm run build 2>&1 | tail -5 && cd ../../..
```

Expected: each build completes.

- [ ] **Step 11: Dev-server smoke (optional but recommended)**

```bash
# Start each site in succession (or all with `scripts/run_websites.sh` if it exists):
cd websites/apps/marketing
npm run dev &
DEV_PID=$!
sleep 8
curl -s http://localhost:3000/ | grep -i 'codrag' && echo "STILL HAS CODRAG"
kill $DEV_PID
cd ../../..
```

Expected: `STILL HAS CODRAG` does not print. Repeat for each site with appropriate port.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "rename(phase-14): websites — content, routes, domains, emails, feature-gate URL"
```

---

## Task 15: Assets + UI strings (dashboard)

**Goal:** Rename image/icon files that carry the CoDRAG name in the filename, update every `<img src>` / `<Image src>` reference, and sweep UI string literals in the Prep dashboard. Visual contents of the images are NOT altered (D6 — rename filenames only).

**Files:**
- `git mv`: `public/images/CoDRAG.png` → `Prep.png`, `codrag-logo.png` (wherever it lives) → `prep-logo.png`
- Modify: every file that references renamed image filenames
- Modify: `src/prep/dashboard/src/**/*.{ts,tsx}` (user-visible strings)

- [ ] **Step 1: Rename image files at repo root / public/**

```bash
# Repo-root logo:
[ -f codrag-logo.png ] && git mv codrag-logo.png prep-logo.png

# Public images folder:
[ -f public/images/CoDRAG.png ] && git mv public/images/CoDRAG.png public/images/Prep.png
# Any other codrag-*.png or codrag-*.svg under public/images:
fd -H 'codrag' public/images -t f | while read -r f; do
  new="${f/codrag/prep}"
  new="${new/CoDRAG/Prep}"
  git mv "$f" "$new"
done
```

- [ ] **Step 2: Rename all remaining codrag-named assets tree-wide**

```bash
fd -H 'codrag' -t f . --exclude .git --exclude node_modules --exclude .venv --exclude target | \
while read -r f; do
  # Skip code/text files — those got content-rewritten already.
  # Only rename files whose FILENAME still contains "codrag".
  base=$(basename "$f")
  if [[ "$base" == *codrag* || "$base" == *CoDRAG* ]]; then
    # Compute new name: lowercase replacement first, then camel
    new=$(echo "$f" | sed 's/codrag/prep/g; s/CoDRAG/Prep/g')
    if [ "$new" != "$f" ]; then
      git mv "$f" "$new"
    fi
  fi
done
```

- [ ] **Step 3: Rewrite references to renamed assets**

```bash
# In all text files:
rg -l 'CoDRAG\.png|codrag-logo|codrag-icon|codrag-sidebar|codrag-github-header' \
  --glob '!.git' --glob '!node_modules' --glob '!.venv' | \
  xargs sed -i '' \
    -e 's|CoDRAG\.png|Prep.png|g' \
    -e 's|codrag-logo|prep-logo|g' \
    -e 's|codrag-icon|prep-icon|g' \
    -e 's|codrag-sidebar|prep-sidebar|g' \
    -e 's|codrag-github-header|prep-github-header|g'
```

- [ ] **Step 4: Dashboard UI string sweep**

```bash
DASH="src/prep/dashboard/src"
rg -l 'CoDRAG' "$DASH" | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' "$DASH" | xargs sed -i '' 's/\bcodrag\b/prep/g'
rg -l 'codrag\.io' "$DASH" | xargs sed -i '' 's/codrag\.io/runprep.io/g'
```

Spot-check specific user-visible components the spec flagged:
```bash
for f in \
  "$DASH/components/startup/StartupScreen.tsx" \
  "$DASH/components/site/SiteHeader.tsx" \
  "$DASH/components/site/SiteFooter.tsx" \
  "$DASH/components/team/EmbeddedModeIndicator.tsx" \
  "$DASH/components/project/AddProjectModal.tsx" \
  "$DASH/components/help/UsageGuidePanel.tsx"; do
  [ -f "$f" ] && echo "=== $f ===" && rg -i 'codrag' "$f"
done
```
Expected: no output (no lingering matches).

- [ ] **Step 5: Error messages that embed URLs**

```bash
rg -l 'codrag\.io' src/prep/ | xargs sed -i '' 's/codrag\.io/runprep.io/g'
rg -l '"docs_url".*codrag' src/prep/ -t py | xargs sed -i '' 's/codrag/prep/g'
```

- [ ] **Step 6: Build dashboard, click through**

```bash
cd src/prep/dashboard
npm run build 2>&1 | tail -5
npm run dev &
DEV_PID=$!
sleep 8
curl -s http://localhost:5174 | grep -i 'codrag' && echo "STILL HAS CODRAG"
kill $DEV_PID
cd ../../..
```

Expected: no `STILL HAS CODRAG` line.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-15): assets renamed, dashboard UI strings, error-message URLs"
```

---

## Task 16: Root docs

**Goal:** Rewrite README.md, CLAUDE.md, and other root-level / `docs/` prose so it reads as coherent Prep documentation, not find/replaced CoDRAG documentation. AGENTS.md is regenerated (from Task 13's generator update). `.gitignore` and `.github/` workflows also updated here.

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `SUPPORT.md`, `SECURITY.md`, `LICENSE`, `CHANGELOG.md`
- Modify: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/CLI.md`, `docs/TROUBLESHOOTING.md`, `docs/MASTER_TODO.md`, `docs/MARKETING_MASTER_TODO.md`, `docs/PRODUCT_AND_BUSINESS_OVERVIEW.md`
- Modify: `docs/CoDRAG_Quality_Report.md` (and possibly rename the file)
- Modify: `.gitignore`, `.github/ISSUE_TEMPLATE/*.yml`, `.github/workflows/*.yml`, `CODEOWNERS` (if present)

- [ ] **Step 1: Rewrite root markdown files**

```bash
for f in README.md CLAUDE.md SUPPORT.md SECURITY.md LICENSE; do
  [ -f "$f" ] && sed -i '' \
    -e 's/CoDRAG/Prep/g' \
    -e 's/\bcodrag\b/prep/g' \
    -e 's/CODRAG/PREP/g' \
    -e 's/codrag\.io/runprep.io/g' \
    -e 's/codrag\.ai//g' \
    "$f"
done
```

- [ ] **Step 2: Read README.md and CLAUDE.md cover to cover**

```bash
wc -l README.md CLAUDE.md
```

Open each and scan for:
- Intro paragraphs that no longer make sense after find/replace ("Prep (Code Documentation and RAG)" — the expansion is wrong; Prep is a verb)
- Any "CoDRAG is…" sentences that need to be "Prep is…" rewording, not find/replace
- The tagline section: update to reflect "prep the context before any AI call"
- The Build & Development Commands section: verify `prep serve`, `prep mcp --mode direct`, import paths use `prep`

Hand-edit paragraphs that feel like awkward find/replace artifacts.

- [ ] **Step 3: Rewrite docs/ root-level markdown (find/replace)**

```bash
for f in docs/*.md; do
  sed -i '' \
    -e 's/CoDRAG/Prep/g' \
    -e 's/\bcodrag\b/prep/g' \
    -e 's/CODRAG/PREP/g' \
    -e 's/codrag\.io/runprep.io/g' \
    -e 's/codrag\.ai//g' \
    "$f"
done

# Rename the quality report file:
[ -f docs/CoDRAG_Quality_Report.md ] && git mv docs/CoDRAG_Quality_Report.md docs/Prep_Quality_Report.md
```

- [ ] **Step 4: CHANGELOG.md**

Historical CHANGELOG entries reference "CoDRAG" by design — `CHANGELOG.md` is on the allowlist (Task 1). But prepend a new entry documenting the rename:

```bash
cat > /tmp/changelog_prelude.md <<'EOF'
## [Unreleased] — Prep Rename

- **BREAKING:** Project renamed from CoDRAG to Prep.
  - CLI command: `codrag` → `prep`
  - Python package: `codrag` → `prep`
  - Data dir: `~/.local/share/codrag/` → `~/.local/share/prep/` (auto-migrated on first run)
  - Env vars: `CODRAG_*` → `PREP_*`
  - MCP tools: `codrag`, `codrag_search`, … → `prep`, `prep_search`, …
  - Tauri bundle: `io.codrag.app` → `io.runprep.app` (existing installs will not auto-update; fresh install required)
  - Domain: `codrag.io` → `runprep.io`
  - GitHub: `EricBintner/CoDRAG` → `MagneticAnomaly/Prep`

EOF

# Prepend the new entry above the current first H2:
awk '/^## /{if(!done){system("cat /tmp/changelog_prelude.md"); done=1}} {print}' CHANGELOG.md > CHANGELOG.md.tmp
mv CHANGELOG.md.tmp CHANGELOG.md
```

- [ ] **Step 5: .gitignore**

```bash
sed -i '' 's|^\.codrag/|.prep/|g; s|^codrag_data/|prep_data/|g' .gitignore
```

Verify:
```bash
grep -nE 'codrag|\.codrag' .gitignore
```
Expected: 0 matches.

- [ ] **Step 6: GitHub workflows**

```bash
for wf in .github/workflows/*.yml .github/ISSUE_TEMPLATE/*.yml .github/*.yml; do
  [ -f "$wf" ] && sed -i '' \
    -e 's/CoDRAG/Prep/g' \
    -e 's/\bcodrag\b/prep/g' \
    -e 's/CODRAG_/PREP_/g' \
    -e 's/codrag-daemon/prep-daemon/g' \
    -e 's/codrag_engine-/prep_engine-/g' \
    -e 's/@codrag\//@prep\//g' \
    -e 's/codrag\.io/runprep.io/g' \
    "$wf"
done
```

Sanity-check:
```bash
rg -i 'codrag' .github/
```
Expected: 0 matches.

- [ ] **Step 7: CODEOWNERS (if present)**

```bash
[ -f CODEOWNERS ] && sed -i '' 's/codrag/prep/g' CODEOWNERS
[ -f .github/CODEOWNERS ] && sed -i '' 's/codrag/prep/g' .github/CODEOWNERS
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "rename(phase-16): root docs, CHANGELOG entry, .gitignore, .github workflows"
```

---

## Task 17: CLaRa scrub (live code + historical docs)

**Goal:** Delete every trace of CLaRa — from live code, scripts, pyproject optional-deps, historical phase docs. Decision D2: full delete, no archive.

**Files:**
- `git rm`: `docs/Phase31_CLaRa-replacement/`, `docs/Phase00_Initial-Concept/STAGE2_CLARA_QUERYTIME.md`, `scripts/publish_clara_subtree.sh`
- Modify: `pyproject.toml` (remove `clara` extra), `src/prep/core/lod_extractor.py`, `src/prep/core/trace/analyzers/*`, any test file referencing CLaRa

- [ ] **Step 1: Delete historical CLaRa phase docs entirely**

```bash
git rm -rf docs/Phase31_CLaRa-replacement 2>/dev/null || true
git rm docs/Phase00_Initial-Concept/STAGE2_CLARA_QUERYTIME.md 2>/dev/null || true

# Any other file with CLaRa in the filename:
fd -H 'CLaRa|CLARA|clara' -t f --exclude .git --exclude node_modules | while read -r f; do
  # Exclude files where 'clara' is a coincidental substring or Spanish word —
  # judgment call per file; default to delete when filename signals CLaRa the project.
  case "$f" in
    *CLaRa*|*CLARA*|*clara_*)
      git rm "$f" 2>/dev/null || rm "$f"
      ;;
    *)
      # Log for manual review:
      echo "MANUAL REVIEW: $f"
      ;;
  esac
done
```

Review any `MANUAL REVIEW` lines and decide case-by-case; default-delete if unsure.

- [ ] **Step 2: Delete the publish script**

```bash
git rm scripts/publish_clara_subtree.sh 2>/dev/null || true
```

- [ ] **Step 3: Remove the `clara` optional-dependency extra from pyproject.toml**

```bash
# The extra likely looks like:
#   [project.optional-dependencies]
#   clara = ["some-package>=x"]
# Remove those two lines (or the whole block if only clara is defined).
# Start by locating:
rg -n 'clara' pyproject.toml
```

Hand-edit the lines out. Then:
```bash
.venv/bin/pip install -e '.[dev]' 2>&1 | tail -3
```
Expected: clean install (no reference to missing `clara` extra).

- [ ] **Step 4: Scrub live source**

```bash
rg -l -i 'clara' src/prep tests scripts | xargs sed -i '' -E '/[Cc][Ll][Aa][Rr][Aa]/d'
```

Warning: `sed -E '/pattern/d'` DELETES matching lines. This is aggressive — only do this on the listed files (`src/prep`, `tests`, `scripts`) where a CLaRa-mention line almost always indicates dead code. Review the diff carefully:

```bash
git diff --stat src/prep tests scripts
git diff src/prep tests scripts | head -100
```

If any line deletion looks unintentional (e.g., inside a docstring that had other content on the same line), use `git checkout -p` to restore and hand-edit.

- [ ] **Step 5: Prose scrub in remaining Phase docs**

Some Phase*/ doc references mention CLaRa tangentially. For each:
- If the whole doc is primarily about CLaRa → deleted in Step 1.
- If CLaRa is mentioned incidentally → delete the mention, don't delete the doc.

```bash
# Enumerate remaining CLaRa mentions:
rg -l -i 'clara' docs/
```

For each file in that list: open it, remove CLaRa paragraphs/sentences/references, save. These are usually "we replaced CLaRa with…" historical notes; delete the CLaRa clause or rewrite around it.

- [ ] **Step 6: Verify zero CLaRa remains**

```bash
rg -i 'clara' --glob '!.git' --glob '!node_modules' --glob '!.venv' --glob '!docs/superpowers/plans/2026-04-21-prep-rename-implementation.md' --glob '!docs/superpowers/specs/2026-04-21-prep-rename-design.md'
```

Expected: 0 hits. (The plan and spec mention CLaRa by necessity and are allowlisted.)

- [ ] **Step 7: Test suite**

```bash
.venv/bin/pytest tests/ -x --timeout=60 -q 2>&1 | tail -20
```

Expected: no new failures. If a test referenced CLaRa, it was deleted as part of Step 4.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "rename(phase-17): delete CLaRa — live code, scripts, phase docs, pyproject extra"
```

---

## Task 18: Historical phase-docs classification

**Goal:** Walk the remaining `docs/Phase*/` directories, classify each as "living" (needs content rewrite) or "archival" (add to allowlist), and complete the rewrite for living docs. End state: grep gate (Task 20) can reach zero.

**Note:** spec-level Phase 18 in the spec table (delete `websites/MagneticAnomaly/`) is dropped — per D3 that directory stays, and its content is already rewritten in Task 14. What used to be Phase 18 is repurposed as phase-doc classification, which is more implementation-work than deletion.

**Files:**
- Modify: `.rename-allowlist.txt` (append archival paths)
- Modify: various `docs/Phase*/` markdown files that remain "living"

- [ ] **Step 1: List all remaining Phase dirs**

```bash
ls -d docs/Phase* | sort > /tmp/phase_dirs.txt
cat /tmp/phase_dirs.txt | wc -l
```

- [ ] **Step 2: For each Phase dir, check if it's referenced from living docs**

```bash
while read -r dir; do
  base=$(basename "$dir")
  refs=$(rg -l "$base" \
           --glob '!docs/Phase*' \
           --glob '!.git' --glob '!node_modules' --glob '!.venv' \
           | wc -l | tr -d ' ')
  echo "$refs $dir"
done < /tmp/phase_dirs.txt | sort -n > /tmp/phase_classification.txt
cat /tmp/phase_classification.txt
```

Phase dirs with `refs = 0` are strong archival candidates. Phase dirs referenced from `CLAUDE.md`, `docs/ROADMAP.md`, `docs/MASTER_TODO.md`, active spec docs → living.

- [ ] **Step 3: Classify**

Rule of thumb from spec §15:
- `refs = 0` → archival → add path to `.rename-allowlist.txt`
- `refs > 0` from living docs → living → rewrite content
- Ambiguous → archival (default)

Build the allowlist additions:
```bash
awk '$1 == 0 {print $2 "/"}' /tmp/phase_classification.txt >> .rename-allowlist.txt
sort -u -o .rename-allowlist.txt .rename-allowlist.txt
cat .rename-allowlist.txt
```

- [ ] **Step 4: Rewrite living phase docs**

For Phase dirs that aren't on the allowlist:
```bash
# Identify living dirs (not in allowlist):
for dir in $(ls -d docs/Phase*); do
  if ! grep -qF "$dir/" .rename-allowlist.txt; then
    echo "Living: $dir"
    rg -l 'CoDRAG' "$dir" | xargs sed -i '' 's/CoDRAG/Prep/g' 2>/dev/null
    rg -l '\bcodrag\b' "$dir" | xargs sed -i '' 's/\bcodrag\b/prep/g' 2>/dev/null
    rg -l 'codrag\.io' "$dir" | xargs sed -i '' 's/codrag\.io/runprep.io/g' 2>/dev/null
  fi
done
```

- [ ] **Step 5: Handle `docs/Phase102_Prep_rename/Phase102_Prep_rename.md` (D10)**

This is the user's prior draft; spec supersedes. Keep it but add a supersession header.

```bash
FILE=docs/Phase102_Prep_rename/Phase102_Prep_rename.md
{
  echo "> **SUPERSEDED** by \`docs/superpowers/specs/2026-04-21-prep-rename-design.md\`. Kept for historical context."
  echo ""
  cat "$FILE"
} > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
# Also run the rename on this file (any "CoDRAG" text inside it):
sed -i '' 's/CoDRAG/Prep/g; s/\bcodrag\b/prep/g; s/codrag\.io/runprep.io/g' "$FILE"
```

If this file is inside an archival Phase dir, the supersession header is a courtesy; the content is in the allowlist anyway.

- [ ] **Step 6: Run the grep gate; append newly-discovered archival hits to the allowlist**

```bash
bash scripts/rename_gate.sh | cut -d: -f1 | sort -u | head -30
```

For each remaining file-with-hits that is archival, add its path (or containing directory substring) to `.rename-allowlist.txt`. For living files with hits, rewrite them.

Iterate until `bash scripts/rename_gate.sh | wc -l` drops substantially (not yet zero — final push is Task 19).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "rename(phase-18): phase-docs classification — rewrite living, allowlist archival"
```

---

## Task 19: Lock files + full test suite

**Goal:** Regenerate `uv.lock` and `package-lock.json` so they reflect the new package names, run the full test suite end-to-end, and snapshot the after-inventory.

**Files:**
- Regenerate: `uv.lock`, `package-lock.json`
- Create: `.rename-inventory-after.txt` (gitignored)

- [ ] **Step 1: Regenerate `uv.lock`**

```bash
uv lock 2>&1 | tail -5
```

Expected: lock file rewritten; git diff shows `codrag` → `prep` in package lines.

- [ ] **Step 2: Regenerate `package-lock.json`**

```bash
rm -f package-lock.json
npm install 2>&1 | tail -10
```

Expected: `package-lock.json` recreated; `@codrag/` strings absent.

Verify:
```bash
jq -r '.packages | keys[]' package-lock.json | grep -i 'codrag' | head
```
Expected: no output.

- [ ] **Step 3: Full Python test suite**

```bash
.venv/bin/pytest tests/ --timeout=120 -q 2>&1 | tail -30
```

Expected: same pass/fail profile as Task-0 baseline (plus the new Task 3B tests, all green). If new failures, fix them — likely missed rename somewhere.

- [ ] **Step 4: Full Rust test suite**

```bash
cd engine && cargo test --workspace 2>&1 | tail -10 && cd ..
```

Expected: all green.

- [ ] **Step 5: Full frontend typecheck + lint + build**

```bash
npm run typecheck 2>&1 | tail -10
npm run lint 2>&1 | tail -10
npm run build 2>&1 | tail -20
```

Expected: typecheck clean, lint clean (or same baseline warnings), build succeeds for all workspaces.

- [ ] **Step 6: End-to-end smoke**

```bash
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 5

curl -sf http://localhost:8400/health && echo "DAEMON OK"
curl -sf http://localhost:8400/api/projects | head -5

# Exercise MCP surface via a direct call if possible:
.venv/bin/prep mcp --mode direct --help | head -5

kill $DAEMON_PID
```

Expected: `DAEMON OK`, project list responds, `mcp` CLI help prints without "codrag".

- [ ] **Step 7: Snapshot post-rename inventory**

```bash
{
  echo "=== Files containing 'codrag' (case-insensitive) — expected small, allowlist-only ==="
  rg -l -i 'codrag' \
    --glob '!.git' --glob '!node_modules' --glob '!.venv' \
    --glob '!target' --glob '!dist' --glob '!build' \
    . | wc -l

  echo ""
  echo "=== Gate output (expected: 0 lines) ==="
  bash scripts/rename_gate.sh | wc -l
} > .rename-inventory-after.txt
cat .rename-inventory-after.txt
```

If gate output is not 0, stay in Task 19 — investigate each gate hit. Either allowlist it (archival) or rewrite it (living).

- [ ] **Step 8: Commit**

```bash
git add uv.lock package-lock.json
git commit -m "rename(phase-19): regenerate lockfiles, full test suite green"
```

---

## Task 20: Zero-occurrence grep gate

**Goal:** Hard gate. `bash scripts/rename_gate.sh | wc -l` must print `0`. Until it does, we do not merge.

- [ ] **Step 1: Run the gate**

```bash
bash scripts/rename_gate.sh | wc -l
```

Expected: `0`.

- [ ] **Step 2: If non-zero, triage each hit**

```bash
bash scripts/rename_gate.sh | head -30
```

For each remaining hit, decide:

| Category | Action |
|---|---|
| Archival phase doc, no external refs | Add its path substring to `.rename-allowlist.txt` |
| Living doc / code | Rewrite the offending line with `sed` or by hand |
| Comment explaining migration context | Allowlist or rephrase to drop the literal |

Re-run the gate after each batch of fixes. Iterate until 0.

- [ ] **Step 3: Commit the final allowlist additions**

```bash
git add -A
git commit -m "rename(phase-20): close grep gate — allowlist finalized, zero leaks"
```

- [ ] **Step 4: Final verification run**

```bash
bash scripts/rename_gate.sh | wc -l
```

Expected: `0`.

---

## Task 21: Merge to main

**Goal:** Fast-forward or squash-merge the rename branch into `main`.

**Files:** none modified; this is a git operation.

- [ ] **Step 1: Pull latest main and rebase if needed**

```bash
git fetch origin
git rebase origin/main
```

If any rebase conflict arises (unlikely — the spec's prerequisite said no concurrent branch work), resolve in favor of the rename branch for rename-scope files.

Re-run the gate after rebase:
```bash
bash scripts/rename_gate.sh | wc -l
```
Expected: `0`.

- [ ] **Step 2: Push rename branch as backup**

```bash
git push -u origin rename/codrag-to-prep
```

(This push goes to the still-CoDRAG-named GitHub repo — that's fine; the repo name flips in Task 22.)

- [ ] **Step 3: Merge to main**

```bash
git checkout main
git merge --no-ff rename/codrag-to-prep -m "rename: CoDRAG → Prep (big-bang cutover)"
```

The `--no-ff` preserves the rename as a single merge commit that is easy to revert.

- [ ] **Step 4: Verify main builds post-merge**

```bash
bash scripts/rename_gate.sh | wc -l
# Expected: 0
.venv/bin/pytest tests/ -x --timeout=60 -q 2>&1 | tail -5
cd engine && cargo check --workspace 2>&1 | tail -5 && cd ..
npm run typecheck 2>&1 | tail -5
```

Expected: gate 0, all builds green.

- [ ] **Step 5: Push main**

```bash
git push origin main
```

**STOP here.** Do not proceed to Task 22 until the user confirms they're ready to flip the GitHub names. Task 22 is a one-way operation.

---

## Task 22: GitHub ops

**Goal:** Transfer + rename the four GitHub repos, rewire local remotes, republish the two subtrees to their renamed sibling repos. After this task, all names on GitHub match the new local state and the dev workflow works end-to-end.

**Prerequisite:** user has created the `MagneticAnomaly` org (if not already) and has admin rights on all four current repos.

**⚠ Order matters** — GitHub redirects work after transfer+rename, but it's cleaner to do all four in a single session.

**Files:** `.git/config` (via `git remote` commands), `scripts/publish_prep_mcp_subtree.sh`, `scripts/publish_deploy_subtree.sh`

- [ ] **Step 1: Perform GitHub renames (user does this in the browser)**

On github.com, in this order:

1. `EricBintner/CoDRAG` → Settings → **Transfer ownership** → target `MagneticAnomaly` → confirm.
2. Now at `MagneticAnomaly/CoDRAG` → Settings → **Rename** → `Prep` → confirm.
3. `MagneticAnomaly/CoDRAG-MCP` → Settings → **Rename** → `Prep-MCP` → confirm.
4. `MagneticAnomaly/CoDRAG-MCP-DEV` → Settings → **Rename** → `Prep-MCP-DEV` → confirm.
5. `MagNeticAnomaly/codrag-deploy` → Settings → **Transfer** to canonical-cased `MagneticAnomaly` (if `MagNeticAnomaly` and `MagneticAnomaly` are distinct orgs — verify) → **Rename** → `Prep-deploy` → confirm.

After each rename, verify the redirect works by visiting the old URL in a browser — GitHub serves a 301 to the new URL.

- [ ] **Step 2: Rewire local remotes**

```bash
# origin: EricBintner/CoDRAG -> MagneticAnomaly/Prep
git remote set-url origin git@github.com:MagneticAnomaly/Prep.git

# Replace the three CoDRAG-MCP remotes with canonical new names:
git remote remove codrag-mcp
git remote remove codrag-mcp-dev
git remote remove dev
git remote remove deploy-public
git remote add mcp     git@github.com:MagneticAnomaly/Prep-MCP.git
git remote add mcp-dev git@github.com:MagneticAnomaly/Prep-MCP-DEV.git
git remote add deploy  git@github.com:MagneticAnomaly/Prep-deploy.git

git fetch --all 2>&1 | tail -10
git remote -v
```

Expected: four remotes (origin, mcp, mcp-dev, deploy), all resolving under `MagneticAnomaly/Prep-*`.

- [ ] **Step 3: Push main to the new origin**

```bash
git push origin main
```

Expected: push succeeds; commits already present (GitHub preserved them during transfer).

- [ ] **Step 4: Update publish scripts' remote URLs**

```bash
sed -i '' 's|MagneticAnomaly/CoDRAG-MCP\.git|MagneticAnomaly/Prep-MCP.git|g' scripts/publish_prep_mcp_subtree.sh
sed -i '' 's|MagneticAnomaly/CoDRAG-MCP|MagneticAnomaly/Prep-MCP|g' scripts/publish_prep_mcp_subtree.sh
sed -i '' 's|MagNeticAnomaly/codrag-deploy\.git|MagneticAnomaly/Prep-deploy.git|g' scripts/publish_deploy_subtree.sh
sed -i '' 's|MagneticAnomaly/codrag-deploy|MagneticAnomaly/Prep-deploy|g' scripts/publish_deploy_subtree.sh
```

Also remove the TODO comments added in Task 9:
```bash
rg -n 'TODO.Task 22' scripts/ | head
```
Edit out those TODO lines.

- [ ] **Step 5: Republish subtrees**

```bash
bash scripts/publish_prep_mcp_subtree.sh 2>&1 | tail -10
bash scripts/publish_deploy_subtree.sh 2>&1 | tail -10
```

Expected: each pushes to the renamed sibling repo; commits arrive under the new name.

Verify on GitHub:
- `MagneticAnomaly/Prep-MCP` has new commits dated today.
- `MagneticAnomaly/Prep-deploy` has new commits dated today.

- [ ] **Step 6: Commit the publish-script URL updates**

```bash
git add scripts/publish_prep_mcp_subtree.sh scripts/publish_deploy_subtree.sh
git commit -m "rename(phase-22): point publish scripts at MagneticAnomaly/Prep-MCP and -deploy"
git push origin main
```

- [ ] **Step 7: Final end-to-end smoke against the renamed origin**

```bash
git fetch origin
git pull origin main
bash scripts/rename_gate.sh | wc -l    # expected: 0
.venv/bin/prep serve --port 8400 &
DAEMON_PID=$!
sleep 5
curl -sf http://localhost:8400/health && echo "ALL GREEN"
kill $DAEMON_PID
```

Expected: gate 0; `ALL GREEN` printed.

- [ ] **Step 8: Announce the rename is complete**

The rename is complete. Any local clones elsewhere (CI runners, the user's other machines) will start getting redirect warnings on `git fetch` — they should update their `origin` URL to the new canonical one:

```bash
git remote set-url origin git@github.com:MagneticAnomaly/Prep.git
```

---

## Self-review results

- **Spec coverage:**
  - Spec §2 (directory list) → Task 2, 4, 11 (covers src/codrag, crates/codrag-*, public/codrag-*).
  - Spec §3 (file renames) → Task 9 (sidecar spec, wrapper), Task 15 (images), Task 3 (agents/shared/codrag_data.py caught by Task 2's tree-wide `from codrag.` pass, but the *file* rename `codrag_data.py` → `prep_data.py` is a filename rewrite — added to Task 15's Step 2 `fd -H 'codrag' -t f` sweep).
  - Spec §3 Top-10 silent-breakage: (1) Tauri bundle ID — Task 10, (2) MCP server key — Task 12, (3) SQLite filenames — Task 3, (4) updater endpoint — Task 10, (5) CLI entry point — Task 2, (6) externalBin — Task 10, (7) Paperclip colon IDs — added to Task 13 coverage (see note below), (8) VS Code config keys — Task 8, (9) data path literal — Task 3, (10) rules generator templates — Task 13. ✅
  - Spec §5 Python — Tasks 2, 3, 3B.
  - Spec §6 Rust — Task 4, 5.
  - Spec §7 npm + VS Code — Tasks 6, 7, 8.
  - Spec §8 MCP — Tasks 3 (Python-side tool names), 12 (configs), 13 (generator).
  - Spec §9 Tauri — Task 10 (with Task 9 producing the sidecar binary first).
  - Spec §10 data paths / migration — Tasks 3, 3B.
  - Spec §11 websites — Task 14.
  - Spec §12 assets / UI — Task 15.
  - Spec §13 content — Task 16.
  - Spec §14 CLaRa — Task 17.
  - Spec §15 historical docs — Task 18.
  - Spec §git ops — Tasks 0 (remote remove), 11 (subtree mv), 21 (merge), 22 (GitHub ops, subtree republish).

- **Paperclip plugin (spec §8)**: the spec calls out `packages/paperclip-plugin-codrag/src/manifest.ts` with `id: 'codrag'` and colon-separated tool IDs (`codrag:context`). Adding an explicit step to Task 13:

  Actually the current Task 13 scope is the rules_generator; the Paperclip plugin is a separate surface. **Gap identified** — fix by adding Task 13 Step 2.5 below. Applied inline.

- **Placeholder scan:** none found. Every step has runnable commands and concrete code where applicable.

- **Type consistency:** function names `migrate_from_legacy_codrag` and `_migrate_embedded_dir` are used consistently where introduced. No mismatches.

- **Ambiguity:** the interaction between `{CODRAG_,codrag_,codrag}` patterns could collide. Task 3 orders the replacements (all-caps first, then title-case, then lowercase) to avoid shadowing. Noted in the Conventions section at the top.

## Paperclip plugin addendum (Task 13 Step 2.5)

Merging into Task 13 as a sub-step, since it's the same class of work (tool-ID and colon-ID rewrites in a generator-adjacent plugin).

- [ ] **Task 13 Step 2.5: Paperclip plugin manifest and UI**

```bash
PP="packages/paperclip-plugin-prep"  # already renamed in Task 2 via git mv at Task 6
# If that rename didn't happen in Task 2 for Paperclip, do it now:
[ -d packages/paperclip-plugin-codrag ] && git mv packages/paperclip-plugin-codrag packages/paperclip-plugin-prep

# Plugin id and colon-namespaced tool IDs:
sed -i '' \
  -e "s/id: 'codrag'/id: 'prep'/g" \
  -e 's/id: "codrag"/id: "prep"/g' \
  -e "s/'codrag:/'prep:/g" \
  -e 's/"codrag:/"prep:/g' \
  "$PP/src/manifest.ts"

# SettingsPage and other UI:
rg -l 'CoDRAG' "$PP/src" | xargs sed -i '' 's/CoDRAG/Prep/g'
rg -l '\bcodrag\b' "$PP/src" | xargs sed -i '' 's/\bcodrag\b/prep/g'
```

Verify:
```bash
rg -i 'codrag' "$PP/src"
```
Expected: 0 hits.

This step runs inside Task 13's commit.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-prep-rename-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review each task's diff before moving to the next. Best for this plan because each task touches hundreds of files; a per-task review catches regressions before they compound.

2. **Inline Execution** — I execute tasks one at a time in this session with checkpoints at phase boundaries. Faster feedback loop but uses more context.

Which approach?
