# SourcePrep Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand user-facing product from **RunPrep** to **SourcePrep** (domain `sourceprep.io`, config folder `.sourceprep/`) while preserving the code-level `prep` identifier unchanged (CLI binary, MCP tool names, Python package, npm `@prep/*`, Rust crates, `PREP_*` env vars, internal routing).

**Architecture:**
- **Code-level `prep` stays** — no touches to CLI binary, Python imports, MCP tool names, npm scope, Rust crates, env var prefix, `prep://` URI, sidecar binary name, sentinel files, wrapper scripts, VS Code extension package name `prep-vscode`, VS Code marketplace publisher `magnetic-anomaly`.
- **Brand prose sweep** — mechanical `RunPrep → SourcePrep` / `runprep.io → sourceprep.io` across UI, dashboard, marketing, docs, README, LICENSE, pyproject metadata, VS Code extension user-visible strings, Tauri `productName` / bundle identifier.
- **Migration chain extended** — `.runprep/` → `.sourceprep/` (embedded) and `~/.local/share/runprep/` → `~/.local/share/sourceprep/` (XDG), layered on top of existing codrag→runprep migration.
- **History preservation** — commits remain SHA-stable; remotes rewired via fast-forward push to new `MagneticAnomaly/SourcePrep*` repos.

**Tech Stack:** Python 3.11 (FastAPI, Typer, pytest), TypeScript (Turbo workspaces, Vite, Next.js, React), Rust (cargo, maturin), Tauri 2.x, bash.

**Branch:** `rename/runprep-to-sourceprep` (already created off `main`).

**Starting baseline:** Commit `e1d8191d` on `main` already did a partial prose sweep (55 files: AGENTS.md, CLAUDE.md, .cursor/rules/prep.mdc, marketing hero + dashboard `App.tsx` + settings overlay, docs concepts/guides, marketing site pages `faq`/`pricing`/`research`/`integrations`, logo assets). This plan is trusted-on-top-of: Phases that touch files `e1d8191d` edited just layer their additional changes in.

**Spec:** `docs/superpowers/specs/2026-04-22-sourceprep-rename-design.md`

---

## File Structure (inventory by phase)

| Phase | Files / paths touched |
|---|---|
| 0. Allowlist prep | `.rename-allowlist.txt` |
| 1. Migration chain | `src/prep/core/paths.py`, `src/prep/core/data_dir_migration.py`, `src/prep/cli.py`, `src/prep/server.py`, `tests/test_paths.py`, `tests/test_data_dir_migration.py`, `.gitignore` |
| 2. Codrag cleanup | `AGENTS.md`, `CLAUDE.md`, `packages/vscode/codrag-vscode-0.1.0.vsix` (delete) |
| 3a. Tauri | `src/prep/dashboard/src-tauri/tauri.conf.json` |
| 3b. VS Code manifest | `packages/vscode/package.json` |
| 3c. VS Code source | `packages/vscode/src/statusBar.ts`, `extension.ts`, `client.ts`, `commands.ts`, `daemon.ts`, `views/projectsTree.ts`, `webview/*.ts` |
| 3d. Release workflow | `.github/workflows/release.yml` |
| 4a. pyproject | `pyproject.toml` |
| 4b. Repo docs | `README.md`, `SUPPORT.md`, `LICENSE`, `CHANGELOG.md`, `docs/*.md` (top-level only) |
| 4c. Dashboard | `src/prep/dashboard/src/**/*.{ts,tsx,css}` |
| 4d. packages/ui | `packages/ui/src/**/*.{ts,tsx}` (excluding already-updated hero components) |
| 4e. Marketing | `websites/apps/marketing/src/**/*.{ts,tsx}`, `websites/apps/marketing/netlify.toml`, `websites/apps/marketing/scripts/*.js` |
| 4f. Docs site | `websites/apps/docs/src/**/*.{ts,tsx}` |
| 4g. Support site | `websites/apps/support/**/*.{ts,tsx,toml,md}` |
| 4h. Payments site | `websites/apps/payments/**/*.{ts,tsx,toml}` |
| 4i. MagneticAnomaly site | `websites/MagneticAnomaly/**` |
| 4j. GitHub templates | `.github/ISSUE_TEMPLATE/*.yml`, `.github/workflows/*.yml` |
| 4k. Repo identity | `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/prep.mdc`, `.claude/skills/prep.md` |
| 4l. Server log prose | `src/prep/server.py` (error messages only) |
| 5. Logo assets | `websites/apps/marketing/public/prep-logo*.png`, `websites/MagneticAnomaly/public/Prep-Logo2.png`, `websites/MagneticAnomaly/app-content/Prep.md` |
| 6. Gate tightening | `scripts/rename_gate.sh`, `.rename-allowlist.txt` |
| 7. Stale artifacts | `packages/vscode/codrag-vscode-0.1.0.vsix` (delete if not done in Phase 2) |
| 8. Remote rewire | git remotes + backup tag |
| 9. Verification | all test suites |

---

## Execution Strategy

**Bulk sweep pattern (Phases 4a–4l):** Each task runs a scoped `sed` across its subdirectory, reviews the diff, hand-fixes anomalies, then commits. macOS BSD `sed` is assumed (`-i ''`).

**Sweep template** — the canonical three-substitution block used across prose tasks:

```bash
# Replace case-matched occurrences. \b enforces word boundaries so "prep" (code
# identifier) is not mis-caught.
find <SCOPE> -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.md' -o -name '*.mdx' -o -name '*.html' -o -name '*.css' -o -name '*.json' -o -name '*.toml' -o -name '*.yml' -o -name '*.yaml' -o -name '*.py' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' ! -path '*/dist/*' ! -path '*/build/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

**Review convention:** after every sweep, run `git diff --stat <SCOPE>` and `git diff <SCOPE> | head -80`, spot-check any surprises, and revert identifiers that slipped (e.g., `prep-daemon`, `@prep/*`, `prep_data_dir`).

**Test discipline:** Phase 1 (migration code) is TDD. Phases 3a–3d and 4a are hand-edits with explicit code blocks. Bulk sweeps (4b–4l) are diff-reviewed. Phase 9 runs the full validation suite.

**Commit discipline:** one commit per task unless explicitly noted. Commit messages: `rename(phase-N-<label>): <short summary>`. Do not include `Co-Authored-By` trailers (user preference).

---

## Phase 0 — Rename gate allowlist prep

### Task 0.1: Extend allowlist for incoming `runprep` and spec/plan references

**Files:**
- Modify: `.rename-allowlist.txt`

- [ ] **Step 1: Read current allowlist**

Run: `cat .rename-allowlist.txt`

Expected: existing entries including `docs/Phase*/` directory list, migration-test files, prior-rename artifacts.

- [ ] **Step 2: Append new allowlist entries (below last existing line)**

Append these lines to `.rename-allowlist.txt`:

```
docs/superpowers/plans/2026-04-22-sourceprep-rename-implementation.md
docs/superpowers/specs/2026-04-22-sourceprep-rename-design.md
docs/Phase102_Prep_rename/SOURCEPREP_RENAME_INSTRUCTIONS.md
```

(These are self-references and migration-source docs that will contain both `runprep` and `sourceprep` strings after Phase 6 tightens the gate.)

- [ ] **Step 3: Verify gate stays green on current tree**

Run: `bash scripts/rename_gate.sh | wc -l`
Expected: `0` (gate regex hasn't been tightened yet, so current `runprep` refs don't break it).

- [ ] **Step 4: Commit**

```bash
git add .rename-allowlist.txt
git commit -m "rename(phase-0): allowlist new rename spec/plan files before regex tightening"
```

---

## Phase 1 — Data-dir migration chain

### Task 1.1: Add failing test for `migrate_from_legacy_runprep()` XDG migration

**Files:**
- Test: `tests/test_data_dir_migration.py`

- [ ] **Step 1: Read current test file to find append location**

Run: `grep -n "def test_" tests/test_data_dir_migration.py | tail -5`

Append new tests at the bottom of the file.

- [ ] **Step 2: Append failing test**

Add to `tests/test_data_dir_migration.py`:

```python
def test_migrate_from_legacy_runprep_moves_xdg_dir(tmp_path, monkeypatch):
    """~/.local/share/runprep/ -> ~/.local/share/sourceprep/ when sentinel absent."""
    from prep.core.data_dir_migration import migrate_from_legacy_runprep

    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "runprep"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_text("legacy-db")

    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: fake_home))
    # Also override the default XDG target derivation inside migration
    monkeypatch.setenv("PREP_DATA_DIR", str(fake_home / ".local" / "share" / "sourceprep"))

    assert migrate_from_legacy_runprep() is True

    target = fake_home / ".local" / "share" / "sourceprep"
    assert (target / "prep_settings.db").read_text() == "legacy-db"
    assert (target / ".migrated_from_runprep").exists()
    assert not legacy.exists()


def test_migrate_from_legacy_runprep_idempotent(tmp_path, monkeypatch):
    """Second call is a no-op after sentinel is written."""
    from prep.core.data_dir_migration import migrate_from_legacy_runprep

    fake_home = tmp_path / "home"
    target = fake_home / ".local" / "share" / "sourceprep"
    target.mkdir(parents=True)
    (target / ".migrated_from_runprep").touch()

    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: fake_home))
    monkeypatch.setenv("PREP_DATA_DIR", str(target))

    assert migrate_from_legacy_runprep() is False
```

- [ ] **Step 3: Run tests — expect failure**

Run: `.venv/bin/pytest tests/test_data_dir_migration.py::test_migrate_from_legacy_runprep_moves_xdg_dir -v`
Expected: FAIL with `ImportError` or `AttributeError` — `migrate_from_legacy_runprep` not yet defined.

### Task 1.2: Implement `migrate_from_legacy_runprep()` and rename target to sourceprep

**Files:**
- Modify: `src/prep/core/data_dir_migration.py`

- [ ] **Step 1: Update `_migrate_xdg_legacy` to use sourceprep as target**

The existing helper (defined at line ~307) hard-codes `runprep` as the target. Generalise it. Read current signature first:

Run: `sed -n '303,360p' src/prep/core/data_dir_migration.py`

- [ ] **Step 2: Change hard-coded target from `runprep` to `sourceprep`**

In `src/prep/core/data_dir_migration.py`, find these two lines inside `_migrate_xdg_legacy`:

```python
        target = home / ".local" / "share" / "runprep"
```

```python
        logger.info(
            "%s->runprep dir migration: legacy=%s → target=%s",
            legacy_name, legacy, target,
        )
```

Replace all three `runprep` references inside the function body with `sourceprep`. There are six total in log strings and the target Path. Use ripgrep to confirm the exact count before editing:

Run: `grep -n 'runprep' src/prep/core/data_dir_migration.py`

Expected output (before edit): 9 lines, all inside `_migrate_xdg_legacy` log strings (5), the `target =` line (1), and the docstring for `_migrate_xdg_legacy` (1), and the two new `_LEGACY_*_SENTINEL`-referencing helpers (2).

Edit each occurrence in `_migrate_xdg_legacy` and its docstring from `runprep` → `sourceprep`.

- [ ] **Step 3: Add `_LEGACY_RUNPREP_SENTINEL` constant and `migrate_from_legacy_runprep()` helper**

Add below the existing `_LEGACY_PREP_SENTINEL = ".migrated_from_prep"` line:

```python
_LEGACY_RUNPREP_SENTINEL = ".migrated_from_runprep"
```

Add below the existing `migrate_from_legacy_prep()` function:

```python
def migrate_from_legacy_runprep() -> bool:
    """Migrate ~/.local/share/runprep/ -> ~/.local/share/sourceprep/ once.

    Handles the RunPrep -> SourcePrep brand rename for installs that saw the
    prep -> runprep rename but not yet runprep -> sourceprep.
    """
    return _migrate_xdg_legacy("runprep", _LEGACY_RUNPREP_SENTINEL)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_data_dir_migration.py::test_migrate_from_legacy_runprep_moves_xdg_dir tests/test_data_dir_migration.py::test_migrate_from_legacy_runprep_idempotent -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/data_dir_migration.py tests/test_data_dir_migration.py
git commit -m "rename(phase-1a): migrate ~/.local/share/runprep/ -> ~/.local/share/sourceprep/"
```

### Task 1.3: Rename XDG default in `paths.py` to `sourceprep`

**Files:**
- Modify: `src/prep/core/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Update the default XDG constant**

In `src/prep/core/paths.py`, change line 29:

```python
_XDG_DEFAULT = Path.home() / ".local" / "share" / "runprep"
```

to:

```python
_XDG_DEFAULT = Path.home() / ".local" / "share" / "sourceprep"
```

Also update the module docstring (line ~19) from `~/.local/share/runprep/` to `~/.local/share/sourceprep/`.

- [ ] **Step 2: Update test expectations**

In `tests/test_paths.py`, the tests currently assert `Path.home() / ".local" / "share" / "runprep"`. Update all occurrences (lines 42, 77 per current file) to `"sourceprep"`.

- [ ] **Step 3: Update docstring in test file**

Line 22 (`test_env_var_overrides_default`) and line 37 (`test_default_is_xdg`) reference `~/.local/share/runprep`. Change both to `~/.local/share/sourceprep`.

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/paths.py tests/test_paths.py
git commit -m "rename(phase-1b): paths.data_dir() default ~/.local/share/runprep -> sourceprep"
```

### Task 1.4: Add embedded `.runprep/` -> `.sourceprep/` migration

**Files:**
- Modify: `src/prep/core/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Append failing test**

Add to the bottom of `tests/test_paths.py`:

```python
def test_migrate_embedded_runprep_to_sourceprep(tmp_path: Path) -> None:
    """_migrate_embedded_dir renames `.runprep/` to `.sourceprep/` when target absent."""
    from prep.core.paths import _migrate_embedded_dir

    legacy = tmp_path / ".runprep"
    legacy.mkdir()
    (legacy / "project.json").write_text('{"id": "x"}')

    _migrate_embedded_dir(tmp_path)

    target = tmp_path / ".sourceprep"
    assert target.is_dir()
    assert (target / "project.json").read_text() == '{"id": "x"}'
    assert not legacy.exists()


def test_migrate_embedded_prefers_target_when_both_exist(tmp_path: Path) -> None:
    """If both `.runprep/` and `.sourceprep/` exist, target wins; legacy untouched."""
    from prep.core.paths import _migrate_embedded_dir

    legacy = tmp_path / ".runprep"
    target = tmp_path / ".sourceprep"
    legacy.mkdir()
    target.mkdir()
    (legacy / "old.txt").write_text("legacy")
    (target / "new.txt").write_text("target")

    _migrate_embedded_dir(tmp_path)

    # Legacy preserved, target untouched
    assert legacy.is_dir()
    assert target.is_dir()
    assert (target / "new.txt").read_text() == "target"
```

- [ ] **Step 2: Run tests — expect failure**

Run: `.venv/bin/pytest tests/test_paths.py::test_migrate_embedded_runprep_to_sourceprep -v`
Expected: FAIL — current `_migrate_embedded_dir` migrates `.codrag -> .runprep`, not `.runprep -> .sourceprep`.

- [ ] **Step 3: Extend `_migrate_embedded_dir` to chain both migrations**

In `src/prep/core/paths.py`, replace the current `_migrate_embedded_dir` (lines ~56-67) with:

```python
def _migrate_embedded_dir(project_root: Path) -> None:
    """Chain legacy embedded-dir renames up to the current target.

    Performs in order (each step is idempotent and only acts when the source
    exists and the target does not):

      .codrag/    -> .runprep/      (codrag -> prep rename)
      .runprep/   -> .sourceprep/   (RunPrep -> SourcePrep rename)

    Called once per project open before any ``.sourceprep/`` read. No-op when
    a given source is absent or the downstream target already exists.
    """
    # codrag -> runprep
    codrag_legacy = project_root / ".codrag"
    runprep_intermediate = project_root / ".runprep"
    if codrag_legacy.exists() and not runprep_intermediate.exists():
        codrag_legacy.rename(runprep_intermediate)

    # runprep -> sourceprep
    sourceprep_target = project_root / ".sourceprep"
    if runprep_intermediate.exists() and not sourceprep_target.exists():
        runprep_intermediate.rename(sourceprep_target)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: all tests PASS (new migration tests + existing tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/paths.py tests/test_paths.py
git commit -m "rename(phase-1c): chain embedded .runprep/ -> .sourceprep/ migration"
```

### Task 1.5: Update `.runprep` literal references in callers to `.sourceprep`

**Files:**
- Modify: `src/prep/core/project_registry.py`

- [ ] **Step 1: Find all `.runprep` path literals in live code (excluding migration markers)**

Run: `grep -rn '"\.runprep"\|'"'"'\.runprep'"'" src/prep/ | grep -v data_dir_migration.py | grep -v paths.py`

Expected: matches in `project_registry.py` (line ~499 `.runprep` read), possibly a few other files.

- [ ] **Step 2: Update project_registry.py `read_codrag_pointer` to read `.sourceprep` first with `.runprep` fallback**

In `src/prep/core/project_registry.py`, around line 497-499, change:

```python
        pointer_path = Path(directory).expanduser().resolve() / ".runprep" / _POINTER_FILENAME
```

to:

```python
        pointer_path = Path(directory).expanduser().resolve() / ".sourceprep" / _POINTER_FILENAME
```

(The migration in `_migrate_embedded_dir` runs immediately before this read, so `.sourceprep/` is guaranteed present for any project that had `.runprep/` or `.codrag/`.)

- [ ] **Step 3: Rename the function if needed**

The function is named `read_codrag_pointer`. Rename it to `read_project_pointer`:

```bash
grep -rn read_codrag_pointer src/ tests/
```

Update all callers. Expected: ~3-5 call sites. Rename both the definition and every caller.

- [ ] **Step 4: Find any other `.runprep` path writers**

Run: `grep -rn '"\.runprep"\|'"'"'\.runprep'"'"'/\|\.runprep/' src/prep/ | grep -v data_dir_migration.py | grep -v paths.py | grep -v test_`

Expected: possibly `watcher.py` (ignore-rule for `.runprep/` inside watched project), other registry write paths.

For each hit that is NOT a migration-source marker (i.e., not in paths.py/data_dir_migration.py/tests for those), change `.runprep` to `.sourceprep`. Where the code also has a `.codrag` literal next to it, update both to reflect the new chain:

- `.codrag/` and `.runprep/` references in ignore/filter logic → keep both plus add `.sourceprep/`.
- `.runprep/` path construction → `.sourceprep/`.

- [ ] **Step 5: Run broader test suite to catch regressions**

Run: `.venv/bin/pytest tests/ -v -x 2>&1 | tail -40`
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add -u src/prep/
git commit -m "rename(phase-1d): .runprep/ path literals -> .sourceprep/ in live code"
```

### Task 1.6: Wire new migration into daemon startup

**Files:**
- Modify: `src/prep/cli.py`
- Modify: `src/prep/server.py`

- [ ] **Step 1: Find existing migration wiring**

Run: `grep -n "migrate_from_legacy" src/prep/cli.py src/prep/server.py`

Expected:
- `src/prep/cli.py:237: migrate_from_legacy_codrag()`
- `src/prep/server.py:43: _migrate_from_codrag()`

(Call sites may differ — the grep finds the current wiring.)

- [ ] **Step 2: Add the new call in `cli.py` after the existing codrag migration**

Read the context around the existing call:

Run: `sed -n '230,245p' src/prep/cli.py`

Add a new line immediately after `migrate_from_legacy_codrag()`:

```python
    migrate_from_legacy_runprep()  # runprep -> sourceprep XDG dirs (rename one-shot, S1)
```

Update the import at the top of the startup block to include the new function:

```python
    from prep.core.data_dir_migration import (
        migrate_from_legacy_codrag,
        migrate_from_legacy_prep,
        migrate_from_legacy_runprep,
        migrate_legacy_data_dir,
    )
```

(Preserve existing order; add `migrate_from_legacy_runprep` alphabetically.)

- [ ] **Step 3: Add the new call in `server.py` after the existing codrag migration**

Read context:

Run: `sed -n '40,50p' src/prep/server.py`

After `_migrate_from_codrag()`, add:

```python
_migrate_from_runprep()  # runprep -> sourceprep XDG dirs (rename one-shot, S1)
```

Add import at the top near existing migration imports:

```python
from prep.core.data_dir_migration import migrate_from_legacy_runprep as _migrate_from_runprep
```

- [ ] **Step 4: Manual smoke — start daemon cleanly**

Run: `.venv/bin/prep serve --port 18400 &` (background) then `sleep 2 && curl -s localhost:18400/health && kill %1`

Expected: Health endpoint returns `{"status":"ok"}` or similar; no tracebacks in stderr; `~/.local/share/sourceprep/` is created on disk.

Run: `ls -la ~/.local/share/sourceprep/`

Expected: directory exists. If `~/.local/share/runprep/` existed before and had content, it was moved and `.migrated_from_runprep` sentinel is present.

- [ ] **Step 5: Commit**

```bash
git add src/prep/cli.py src/prep/server.py
git commit -m "rename(phase-1e): wire migrate_from_legacy_runprep() into daemon startup"
```

### Task 1.7: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Check current state**

Run: `grep -E '\.runprep|\.sourceprep|\.codrag' .gitignore`

Expected: `.runprep/`, `.codrag/` entries present.

- [ ] **Step 2: Add `.sourceprep/` entry; keep legacy entries for migration**

Edit `.gitignore` — find the `.runprep/` line and add `.sourceprep/` directly above (or below) it. Keep both legacy entries (`.codrag/`, `.runprep/`) for in-flight installs that may still have those directories on disk.

Example diff:
```diff
 .codrag/
 .runprep/
+.sourceprep/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "rename(phase-1f): .gitignore .sourceprep/ (keep .runprep/ and .codrag/ for migration)"
```

---

## Phase 2 — Leftover codrag cleanup

### Task 2.1: Fix stale `src/codrag/` references in AGENTS.md and CLAUDE.md atlas blocks

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Locate stale atlas strings**

Run: `grep -n 'src/codrag' AGENTS.md CLAUDE.md`

Expected:
- `AGENTS.md:75: Active zones: ... src/codrag/core/, src/codrag/dashboard/, src/codrag/services/`
- `CLAUDE.md:311: Active zones: ... src/codrag/core/, src/codrag/dashboard/, src/codrag/services/`

These are auto-generated atlas snippets that didn't re-emit after the codrag→prep Python package rename.

- [ ] **Step 2: Hand-edit both lines**

In `AGENTS.md` line 75 and `CLAUDE.md` line 311, replace each occurrence of `src/codrag/` with `src/prep/`. After edit, re-run:

Run: `grep -n 'src/codrag' AGENTS.md CLAUDE.md`

Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "rename(phase-2): purge stale src/codrag/ atlas references from AGENTS/CLAUDE.md"
```

### Task 2.2: Delete stale VS Code extension VSIX artifact

**Files:**
- Delete: `packages/vscode/codrag-vscode-0.1.0.vsix`

- [ ] **Step 1: Confirm file exists**

Run: `ls -la packages/vscode/codrag-vscode-0.1.0.vsix`

Expected: file present (compiled extension bundle from the CoDRAG era).

- [ ] **Step 2: Remove it**

Run: `git rm packages/vscode/codrag-vscode-0.1.0.vsix`

- [ ] **Step 3: Verify no references to the file exist**

Run: `grep -rn 'codrag-vscode-0.1.0.vsix' --exclude-dir=.git --exclude-dir=node_modules .`

Expected: no matches (it was a build artifact, not referenced).

- [ ] **Step 4: Commit**

```bash
git commit -m "rename(phase-2): delete stale codrag-vscode-0.1.0.vsix build artifact"
```

### Task 2.3: Rename `hi_codrag` MCP alias identifier to `hi_prep`

**Context:** The spec (§2 "Leftover codrag in live code") requires renaming `hi_codrag` → `hi_prep`. The identifier appears in live code across: the MCP tool alias map, the tool schema shown to clients, the tool-hi module's user-visible prompt strings, the direct-mode dispatch, and one comment in the trace router. This is a code-level identifier (users type it, but it follows the `prep`/`prep_search` convention), so it renames to `hi_prep`, not `hi_sourceprep`. No backwards-compat alias — the `codrag` brand is gone and the rename gate will enforce that.

**Files:**
- Modify: `src/prep/mcp/tool_hi.py:2,408,416`
- Modify: `src/prep/mcp_tools.py:465,745-746` (alias dispatch map + public schema)
- Modify: `src/prep/mcp_direct.py:377,382,448` (user-visible prompt strings + dispatch branch)
- Modify: `src/prep/api/routers/trace_routes/query.py:606,649` (comments)

- [ ] **Step 1: Inventory current refs**

Run: `grep -rn 'hi_codrag' src/prep/ --include='*.py'`

Expected: 9 matches across the four files above.

- [ ] **Step 2: Update `src/prep/mcp/tool_hi.py`**

Replace the string `hi_codrag` with `hi_prep` in lines 2, 408, 416. These are: the module docstring line (`Project overview and context discovery tool (hi_codrag).`), and two user-visible prompt strings in `_ai_note` text (`"STANDALONE (user only said 'hi_codrag')..."` and `"WITH A QUESTION (user said 'hi_codrag' AND asked something)..."`).

After edit: `grep -n 'hi_codrag' src/prep/mcp/tool_hi.py` — expected: 0 matches.

- [ ] **Step 3: Update `src/prep/mcp_tools.py` alias map**

At line 465, change the alias map entry from:
```python
    "hi_codrag":           "prep",
```
to:
```python
    "hi_prep":             "prep",
```

- [ ] **Step 4: Update `src/prep/mcp_tools.py` public tool schema**

At line 745, change `"name": "hi_codrag"` to `"name": "hi_prep"`. At line 746 (the description), replace the two occurrences of `'hi_codrag'` inside the description string with `'hi_prep'`, and replace the branded word `CodRAG`/`codrag` if present. (Read the exact line before editing to preserve surrounding text.)

After edits: `grep -n 'hi_codrag\|codrag' src/prep/mcp_tools.py` — expected: 0 matches.

- [ ] **Step 5: Update `src/prep/mcp_direct.py`**

Replace `hi_codrag` with `hi_prep` in the two prompt strings (lines 377, 382) and the dispatch branch (`elif name == "hi_codrag":` at line 448 → `elif name == "hi_prep":`).

After edit: `grep -n 'hi_codrag' src/prep/mcp_direct.py` — expected: 0 matches.

- [ ] **Step 6: Update `src/prep/api/routers/trace_routes/query.py` comments**

Replace `hi_codrag` with `hi_prep` in the two comments at lines 606 and 649. These are source comments, not user-facing strings.

After edit: `grep -n 'hi_codrag' src/prep/api/routers/trace_routes/query.py` — expected: 0 matches.

- [ ] **Step 7: Verify no `hi_codrag` remains in live code**

Run: `grep -rn 'hi_codrag' src/ tests/ --include='*.py'`

Expected: matches only inside `tests/test_codrag_hi.py` and `tests/test_codrag_hi_scenario.py` (those files are renamed + updated in Task 2.4).

- [ ] **Step 8: Run tests that exercise the alias**

Run: `.venv/bin/pytest tests/test_codrag_hi.py -v -k "alias"`

Expected: tests that reference `hi_codrag` will now FAIL because the alias was renamed. This is expected — Task 2.4 updates the tests. Note the failures but do not fix here.

- [ ] **Step 9: Commit**

```bash
git add src/prep/mcp/tool_hi.py src/prep/mcp_tools.py src/prep/mcp_direct.py src/prep/api/routers/trace_routes/query.py
git commit -m "rename(phase-2): rename hi_codrag MCP alias identifier to hi_prep"
```

### Task 2.4: Rename `test_codrag_hi*.py` test files and update internal refs

**Context:** Two test files still have `codrag` in their filename and contents. Per spec §2, rename both files to `test_prep_hi*.py` and update all internal `hi_codrag` / `codrag` references to `hi_prep` / `prep`. After Task 2.3 renamed the alias, these tests are broken; this task fixes them and aligns filenames.

**Files:**
- Rename: `tests/test_codrag_hi.py` → `tests/test_prep_hi.py`
- Rename: `tests/test_codrag_hi_scenario.py` → `tests/test_prep_hi_scenario.py`

- [ ] **Step 1: Rename both files via `git mv`**

```bash
git mv tests/test_codrag_hi.py tests/test_prep_hi.py
git mv tests/test_codrag_hi_scenario.py tests/test_prep_hi_scenario.py
```

- [ ] **Step 2: Replace `hi_codrag` identifier throughout both files**

Run (macOS BSD sed):
```bash
sed -i '' 's/hi_codrag/hi_prep/g' tests/test_prep_hi.py tests/test_prep_hi_scenario.py
```

Verify:
```bash
grep -n 'hi_codrag' tests/test_prep_hi.py tests/test_prep_hi_scenario.py
```

Expected: 0 matches.

- [ ] **Step 3: Replace test method/class names that embed `codrag`**

`tests/test_prep_hi.py` has test methods `test_codrag_listed_in_tools_list`, `test_codrag_schema_no_required_params`, and `test_ai_note_mentions_codrag_tool` (lines 442, 451, 912). Replace with `test_prep_listed_in_tools_list`, `test_prep_schema_no_required_params`, `test_ai_note_mentions_prep_tool` respectively.

Run (macOS BSD sed):
```bash
sed -i '' 's/test_codrag_listed_in_tools_list/test_prep_listed_in_tools_list/g; s/test_codrag_schema_no_required_params/test_prep_schema_no_required_params/g; s/test_ai_note_mentions_codrag_tool/test_ai_note_mentions_prep_tool/g' tests/test_prep_hi.py
```

Verify:
```bash
grep -n 'test_codrag\|codrag' tests/test_prep_hi.py tests/test_prep_hi_scenario.py
```

Expected: 0 matches.

- [ ] **Step 4: Run the renamed tests**

```bash
.venv/bin/pytest tests/test_prep_hi.py tests/test_prep_hi_scenario.py -v
```

Expected: tests pass (same count as before the rename). If any test fails on an assertion like `assert "hi_codrag" not in tool_names` — that's an assertion on the new `hi_prep` alias being absent from `tools/list`, which is still correct after Step 2 because `hi_codrag` became `hi_prep` in both the assertion and the source. Investigate any real failures.

- [ ] **Step 5: Confirm filename rename is complete**

```bash
ls tests/test_codrag_hi*.py tests/test_prep_hi*.py 2>&1
```

Expected: `test_codrag_hi*.py` — "No such file or directory"; `test_prep_hi*.py` — two files.

- [ ] **Step 6: Commit**

```bash
git add tests/test_prep_hi.py tests/test_prep_hi_scenario.py
git commit -m "rename(phase-2): rename test_codrag_hi tests to test_prep_hi and update internal refs"
```

### Task 2.5: Audit remaining `codrag` identifiers in live src/

**Context:** Spec §2 lists multiple source files with codrag references to audit. Task 2.3 handled `hi_codrag`. This task handles the remaining ones: anything in `src/prep/` that still contains the string `codrag` (outside allowlisted migration-source markers). Most will be stale comments, log strings, or docstrings.

**Files (audit targets per spec §2):**
- `src/prep/mcp/server.py`
- `src/prep/a2a/handler.py`
- `src/prep/adapters/push_engine.py`, `paperclip_adapter.py`, `pm_adapter.py`
- `src/prep/api/routers/query.py`, `system.py`, `opportunities.py`, `projects/build.py`
- `src/prep/services/pipeline_metadata.py`, `config_manager.py`
- `src/prep/cli.py`
- `src/prep/server.py`
- `src/prep/core/stage_manifest.py`, `provenance.py`, `project_registry.py`, `repo_profile.py`, `rules_generator.py`, `__init__.py`

- [ ] **Step 1: Inventory all remaining `codrag` refs in live src**

Run:
```bash
grep -rn 'codrag' src/prep/ --include='*.py' | grep -v 'paths.py\|data_dir_migration.py\|watcher.py'
```

Expected: a list of matches. Save this output — it drives the sweep.

- [ ] **Step 2: Classify each match**

For each hit, decide:
- **Code identifier** (function name, dict key, class name, variable, tool name) → rename to `prep`
- **User-visible prose** (error message shown to end user, log message surfaced in UI, docstring the user sees) → rename to `SourcePrep`
- **Historical comment** (Phase-N reference, changelog pointer) → leave or update to `prep` (preserve the Phase reference)
- **Legitimate migration-source marker** not already in the allowlist carve-out → skip (do not rename)

Create a short mapping file or mental checklist before editing.

- [ ] **Step 3: Apply sweep per-file**

For mechanical identifier renames (pure `codrag` → `prep` substitution, no prose), use sed per-file:
```bash
sed -i '' 's/codrag/prep/g' <file>
```

For files with mixed content (some prose, some identifiers), hand-edit with the `Edit` tool to apply the correct replacement per occurrence.

After each file is edited:
```bash
grep -n 'codrag' <file>
```

Expected: 0 matches, or only intentional historical references that should be added to the allowlist (rare).

- [ ] **Step 4: Type-check and run tests**

```bash
.venv/bin/mypy src/prep/ --exclude tests
.venv/bin/pytest tests/ -x --ignore=tests/eval
```

Expected: both clean (or only pre-existing failures unrelated to this sweep).

- [ ] **Step 5: Verify allowlist still covers everything**

```bash
grep -rn 'codrag' src/prep/ --include='*.py' > /tmp/codrag_remaining.txt
```

Every line in `/tmp/codrag_remaining.txt` must be matched by a pattern in `.rename-allowlist.txt`. If not, either add it to the allowlist (with a comment explaining why it's a migration-source marker) or rename it.

- [ ] **Step 6: Commit**

```bash
git add -u src/prep/
git commit -m "rename(phase-2): purge remaining codrag identifiers from live src/"
```

### Task 2.6: Update `tests/fixtures/mini_repo/.runprep/` fixture path

**Context:** Per spec §2, the mini_repo test fixture uses `.runprep/` (a fresh fixture, not a migration source), so it should rename to `.sourceprep/` along with any test refs.

**Files:**
- Rename: `tests/fixtures/mini_repo/.runprep/` → `tests/fixtures/mini_repo/.sourceprep/`

- [ ] **Step 1: Confirm fixture exists**

```bash
ls -la tests/fixtures/mini_repo/ | grep -E '\.runprep|\.sourceprep'
```

Expected: `.runprep/` present, `.sourceprep/` absent.

- [ ] **Step 2: Inventory test refs to the fixture**

```bash
grep -rn 'mini_repo/.runprep\|mini_repo/\.runprep' tests/ src/
```

Note every reference that will need updating after the rename.

- [ ] **Step 3: Rename via `git mv`**

```bash
git mv tests/fixtures/mini_repo/.runprep tests/fixtures/mini_repo/.sourceprep
```

- [ ] **Step 4: Update test refs**

For each file found in Step 2, replace `mini_repo/.runprep` with `mini_repo/.sourceprep`:
```bash
sed -i '' 's|mini_repo/\.runprep|mini_repo/.sourceprep|g' <file>
```

- [ ] **Step 5: Run fixture-dependent tests**

```bash
.venv/bin/pytest tests/ -v -k "mini_repo" 2>&1 | tail -40
```

Expected: tests that were passing still pass.

- [ ] **Step 6: Commit**

```bash
git add -u tests/ src/
git commit -m "rename(phase-2): rename mini_repo fixture .runprep -> .sourceprep"
```

---

## Phase 3 — App identity

### Task 3.1: Update Tauri config (productName, identifier, updater, window title)

**Files:**
- Modify: `src/prep/dashboard/src-tauri/tauri.conf.json`

- [ ] **Step 1: Read current config**

Run: `cat src/prep/dashboard/src-tauri/tauri.conf.json | python3 -m json.tool | head -80`

- [ ] **Step 2: Edit the four rename fields**

In `src/prep/dashboard/src-tauri/tauri.conf.json`:

- Line 9: `"productName": "RunPrep"` → `"productName": "SourcePrep"`
- Line 42: `"identifier": "io.runprep.app"` → `"identifier": "io.sourceprep.app"`
- Line 68: `"https://github.com/MagneticAnomaly/RunPrep/releases/latest/download/latest.json"` → `"https://github.com/MagneticAnomaly/SourcePrep/releases/latest/download/latest.json"`
- Line 75: `"title": "RunPrep"` → `"title": "SourcePrep"`

Do NOT touch:
- Line 33: `"binaries/prep-daemon"` (sidecar, code-level)
- Line 22: `"scope": ["http://127.0.0.1:8400/*"]` (daemon port, code-level)
- Line 66: `"pubkey": "..."` (updater signing key — still valid)

- [ ] **Step 3: JSON-validate**

Run: `python3 -c 'import json; json.load(open("src/prep/dashboard/src-tauri/tauri.conf.json"))'`
Expected: no output (valid JSON).

- [ ] **Step 4: Commit**

```bash
git add src/prep/dashboard/src-tauri/tauri.conf.json
git commit -m "rename(phase-3a): Tauri productName+identifier+updater+window title -> SourcePrep"
```

### Task 3.2: Update VS Code extension manifest

**Files:**
- Modify: `packages/vscode/package.json`

- [ ] **Step 1: Hand-edit user-facing fields**

In `packages/vscode/package.json`:

- Line 3: `"displayName": "RunPrep — Local Code Context Engine"` → `"displayName": "SourcePrep — Local Code Context Engine"`
- Line 4: `"description": "Local-first semantic code search, context assembly, and structural trace for AI workflows. No code upload. RunPrep works with Copilot, Cursor, Windsurf via MCP."` → replace the single `RunPrep` with `SourcePrep`.
- Line 10: `"url": "https://github.com/MagneticAnomaly/RunPrep"` → `"url": "https://github.com/MagneticAnomaly/SourcePrep"`
- Line 13: `"url": "https://github.com/MagneticAnomaly/RunPrep/issues"` → `"url": "https://github.com/MagneticAnomaly/SourcePrep/issues"`
- Line 15: `"homepage": "https://runprep.io"` → `"homepage": "https://sourceprep.io"`
- Line 41: `"title": "RunPrep"` (viewsContainers.activitybar title) → `"title": "SourcePrep"`
- Line 281: `"title": "RunPrep"` (configuration section title) → `"title": "SourcePrep"`
- Lines 285, 290, 295, 300, 305: `"description"` fields mentioning `RunPrep daemon` / `RunPrep status` / `RunPrep executable` → replace each `RunPrep` with `SourcePrep`.
- Line 321: `"fullName": "RunPrep"` (chatParticipants) → `"fullName": "SourcePrep"`
- Line 322: `"description": "Ask questions about your codebase using RunPrep's semantic index."` → replace `RunPrep` with `SourcePrep`.

Do NOT touch:
- Line 2: `"name": "prep-vscode"` (npm identity, code-level)
- Line 6: `"publisher": "magnetic-anomaly"` (marketplace publisher, frozen)
- Lines 29, 35, 41, etc: all `"command": "prep.search"`-style command IDs (code-level, MCP-adjacent)
- Keywords array line 29: retain the literal `"prep"` keyword (product code identifier).
- Line 35: `"icon": "media/prep-icon.png"` (asset path, code-level)
- Line 42: `"icon": "media/prep-sidebar.svg"` (asset path, code-level)
- Line 319: `"id": "prep.chat"` (chat participant ID, code-level)
- Line 320: `"name": "prep"` (chat participant invocation name, code-level)

- [ ] **Step 2: JSON-validate**

Run: `python3 -c 'import json; json.load(open("packages/vscode/package.json"))'`
Expected: no output.

- [ ] **Step 3: Typecheck VS Code workspace**

Run: `cd packages/vscode && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/vscode/package.json
git commit -m "rename(phase-3b): VS Code manifest displayName+URLs+configuration title -> SourcePrep"
```

### Task 3.3: Sweep VS Code extension source files

**Files:**
- Modify: `packages/vscode/src/statusBar.ts`, `extension.ts`, `client.ts`, `commands.ts`, `daemon.ts`, `views/projectsTree.ts`, `webview/searchResults.ts`, `webview/tracePanel.ts`, `webview/contextPreview.ts`, `webview/helper.ts`, `webview/styles.ts`

- [ ] **Step 1: Run the sweep**

```bash
find packages/vscode/src -type f \( -name '*.ts' -o -name '*.tsx' \) -print0 | \
  xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review diff for identifier false-positives**

Run: `git diff --stat packages/vscode/src/`
Expected: ~11 files changed, ~30-40 line additions/deletions.

Run: `git diff packages/vscode/src/ | head -80`

Spot-check: confirm the `RunPrep` → `SourcePrep` changes are all in user-visible strings (statusBar text, tooltip, webview title, output channel name, error messages). Command IDs (`prep.startDaemon` etc.) should be untouched because they are lowercase with dots (no word boundary match).

- [ ] **Step 3: Typecheck**

Run: `cd packages/vscode && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/vscode/src/
git commit -m "rename(phase-3c): VS Code source user-visible strings RunPrep -> SourcePrep"
```

### Task 3.4: Update release workflow (Tauri bundle paths derive from productName)

**Files:**
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Review current path references**

Run: `grep -n 'Prep\|RunPrep\|runprep' .github/workflows/release.yml`

Expected matches:
- Line 128: `releaseName: 'Prep v__VERSION__'` → `releaseName: 'SourcePrep v__VERSION__'`
- Line 132: `https://github.com/MagneticAnomaly/RunPrep/compare/` → `https://github.com/MagneticAnomaly/SourcePrep/compare/`
- Line 134: `https://github.com/MagneticAnomaly/RunPrep/blob/main/CHANGELOG.md` → replace RunPrep with SourcePrep
- Lines 140-141: download table `Prep_*_aarch64.dmg`, `Prep_*_x64-setup.exe` → `SourcePrep_*_…`
- Line 157: `"$APP_PATH"` pointing to `.../Prep.app` → `.../SourcePrep.app`
- Line 158: `APP_PATH=` string literal `Prep.app` → `SourcePrep.app`
- Line 161: `SIDCAR_PATH="$APP_PATH/Contents/MacOS/prep-daemon"` → **DO NOT touch** (sidecar name, code-level)
- Line 169: check path `$APP_PATH/Contents/MacOS/Prep` → `$APP_PATH/Contents/MacOS/SourcePrep`
- Lines 182-183: `$exePath = "src/prep/dashboard/src-tauri/target/release/bundle/nsis/Prep_*_x64-setup.exe"`, `$msiPath = ".../Prep_*.msi"` → `SourcePrep_*`
- Line 192: `$sidecarPath = ".../prep-daemon.exe"` → **DO NOT touch** (sidecar)

- [ ] **Step 2: Run targeted sed**

```bash
sed -i '' \
  -e 's/Prep v__VERSION__/SourcePrep v__VERSION__/g' \
  -e "s|MagneticAnomaly/RunPrep|MagneticAnomaly/SourcePrep|g" \
  -e 's/Prep_\*_aarch64/SourcePrep_*_aarch64/g' \
  -e 's/Prep_\*_x64-setup/SourcePrep_*_x64-setup/g' \
  -e 's/Prep_\*\.msi/SourcePrep_*.msi/g' \
  -e 's|/Prep\.app|/SourcePrep.app|g' \
  -e 's|/MacOS/Prep"|/MacOS/SourcePrep"|g' \
  .github/workflows/release.yml
```

- [ ] **Step 3: Verify sidecar paths were NOT touched**

Run: `grep -n 'prep-daemon' .github/workflows/release.yml`

Expected: lines 161, 192 still reference `prep-daemon` / `prep-daemon.exe` — these are sidecar binary paths (code-level).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "rename(phase-3d): release workflow Prep.app/Prep_*/RunPrep URLs -> SourcePrep"
```

---

## Phase 4 — Brand + URL sweep

All tasks in this phase follow the sweep pattern defined in Execution Strategy. After each sed, spot-check `git diff --stat` and `git diff | head -100` for anomalies before committing.

### Task 4.1: pyproject.toml metadata

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Hand-edit the four metadata fields**

In `pyproject.toml`:

- Line 8: `description = "Prep — prepare context before any AI call"` → `description = "SourcePrep — prepare context before any AI call"`
- Line 13: `{ name = "Prep Team" }` → `{ name = "SourcePrep Team" }`
- Line 102: `Homepage = "https://github.com/MagneticAnomaly/RunPrep"` → `Homepage = "https://github.com/MagneticAnomaly/SourcePrep"`
- Line 103: `Documentation = "https://github.com/MagneticAnomaly/RunPrep#readme"` → same URL sub
- Line 104: `Repository = "https://github.com/MagneticAnomaly/RunPrep"` → same URL sub
- Line 105: `Issues = "https://github.com/MagneticAnomaly/RunPrep/issues"` → same URL sub

Do NOT touch:
- Line 6: `name = "prep"` (PyPI-compatible package identity, code-level)
- Line 99: `prep = "prep.cli:main"` (CLI entry, code-level)
- Line 108: `packages = ["src/prep"]` (package root, code-level)
- Line 128: `known-first-party = ["prep"]` (ruff config, code-level)

- [ ] **Step 2: Validate TOML**

Run: `python3 -c 'import tomllib; tomllib.load(open("pyproject.toml","rb"))'`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "rename(phase-4a): pyproject.toml description+authors+URLs -> SourcePrep"
```

### Task 4.2: Repo-level prose documentation

**Files:**
- Modify: `README.md`, `SUPPORT.md`, `LICENSE`, `CHANGELOG.md`, every `*.md` in `docs/` that is NOT under `docs/Phase*/` or `docs/superpowers/specs/2026-04-21-*` / `docs/superpowers/plans/2026-04-21-*`.

- [ ] **Step 1: List in-scope files**

```bash
find README.md SUPPORT.md LICENSE CHANGELOG.md \
  docs -maxdepth 1 -type f -name '*.md' \
  -print 2>/dev/null
```

Expected: top-level README/SUPPORT/LICENSE/CHANGELOG + files directly in `docs/`.

- [ ] **Step 2: Run sweep**

```bash
for f in README.md SUPPORT.md LICENSE CHANGELOG.md; do
  [ -f "$f" ] && sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g' \
    "$f"
done
find docs -maxdepth 1 -type f -name '*.md' -print0 | \
  xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 3: Spot-check**

Run: `git diff --stat README.md SUPPORT.md LICENSE CHANGELOG.md`
Run: `git diff --stat docs/*.md`

Read any substantive diffs in README.md (user-facing). If the content was already updated by commit `e1d8191d`, the diff here will be smaller.

- [ ] **Step 4: Commit**

```bash
git add -u README.md SUPPORT.md LICENSE CHANGELOG.md docs/
git commit -m "rename(phase-4b): repo-level docs RunPrep -> SourcePrep"
```

### Task 4.3: Dashboard UI strings

**Files:**
- Modify: `src/prep/dashboard/src/**/*.{ts,tsx,css,html}`

- [ ] **Step 1: Run sweep**

```bash
find src/prep/dashboard/src -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.css' -o -name '*.html' \) \
  ! -path '*/node_modules/*' ! -path '*/dist/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review diff**

Run: `git diff --stat src/prep/dashboard/src/`

Inspect: `git diff src/prep/dashboard/src/App.tsx | head -40` (already touched by `e1d8191d`; this sweep should be a small delta).

- [ ] **Step 3: Dashboard typecheck**

Run: `cd src/prep/dashboard && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add -u src/prep/dashboard/src/
git commit -m "rename(phase-4c): dashboard UI strings RunPrep -> SourcePrep"
```

### Task 4.4: packages/ui sweep

**Files:**
- Modify: `packages/ui/src/**/*.{ts,tsx}` (excluding Storybook snapshots, already-updated components)

- [ ] **Step 1: Run sweep**

```bash
find packages/ui/src -type f \( -name '*.ts' -o -name '*.tsx' \) \
  ! -path '*/node_modules/*' ! -path '*/storybook-static/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review diff, with special attention to MarketingHero**

Run: `git diff --stat packages/ui/src/`
Run: `git diff packages/ui/src/components/MarketingHero.tsx 2>/dev/null | head -40`

Note: `packages/ui/src/components/MarketingHero.tsx` was already updated by `e1d8191d`. This sweep may touch leftover occurrences. Per the rename-spec "Frozen" rule, the marketing *home-page hero* is off-limits for autonomous edits — but a *mechanical rebrand* (same copy, only swapping brand word) is faithful rebranding, not copy editing. If the diff looks like pure brand substitution, accept. If it looks like it altered hero structure, revert.

- [ ] **Step 3: UI typecheck**

Run: `cd packages/ui && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add -u packages/ui/src/
git commit -m "rename(phase-4d): packages/ui user-visible strings RunPrep -> SourcePrep"
```

### Task 4.5: Marketing site sweep (excluding home-page hero file)

**Files:**
- Modify: `websites/apps/marketing/**/*.{ts,tsx,md,mdx,toml,js}` except `websites/apps/marketing/src/app/page.tsx`

- [ ] **Step 1: Save home-page hero before the sweep**

```bash
cp websites/apps/marketing/src/app/page.tsx /tmp/page.tsx.pre-sweep
```

- [ ] **Step 2: Run sweep**

```bash
find websites/apps/marketing -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.md' -o -name '*.mdx' -o -name '*.toml' -o -name '*.js' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' ! -path '*/dist/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 3: Review changes to `src/app/page.tsx`**

Run: `diff /tmp/page.tsx.pre-sweep websites/apps/marketing/src/app/page.tsx | head -60`

If the diff shows *only* literal `RunPrep` → `SourcePrep` and `runprep.io` → `sourceprep.io` substitutions (no other prose/structure changes), accept. Otherwise, revert just that file:

```bash
git checkout HEAD -- websites/apps/marketing/src/app/page.tsx
# Then hand-edit page.tsx to apply only the brand substitutions.
```

- [ ] **Step 4: Review sweep diff**

Run: `git diff --stat websites/apps/marketing/`

- [ ] **Step 5: Marketing typecheck**

Run: `cd websites/apps/marketing && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
rm /tmp/page.tsx.pre-sweep
git add -u websites/apps/marketing/
git commit -m "rename(phase-4e): marketing site RunPrep -> SourcePrep, URLs to sourceprep.io"
```

### Task 4.6: Docs site sweep

**Files:**
- Modify: `websites/apps/docs/**/*.{ts,tsx,md,mdx}`

- [ ] **Step 1: Run sweep**

```bash
find websites/apps/docs -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.md' -o -name '*.mdx' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review diff**

Run: `git diff --stat websites/apps/docs/`

- [ ] **Step 3: Docs typecheck**

Run: `cd websites/apps/docs && npm run typecheck && cd -`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add -u websites/apps/docs/
git commit -m "rename(phase-4f): docs site RunPrep -> SourcePrep, URLs to sourceprep.io"
```

### Task 4.7: Support site sweep

**Files:**
- Modify: `websites/apps/support/**/*.{ts,tsx,md,mdx,toml}`

- [ ] **Step 1: Run sweep**

```bash
find websites/apps/support -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.md' -o -name '*.mdx' -o -name '*.toml' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review and commit**

Run: `git diff --stat websites/apps/support/`

```bash
git add -u websites/apps/support/
git commit -m "rename(phase-4g): support site RunPrep -> SourcePrep"
```

### Task 4.8: Payments site sweep

**Files:**
- Modify: `websites/apps/payments/**/*.{ts,tsx,md,mdx,toml}`

- [ ] **Step 1: Run sweep**

```bash
find websites/apps/payments -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.md' -o -name '*.mdx' -o -name '*.toml' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review and commit**

Run: `git diff --stat websites/apps/payments/`

```bash
git add -u websites/apps/payments/
git commit -m "rename(phase-4h): payments site RunPrep -> SourcePrep"
```

### Task 4.9: MagneticAnomaly parent site sweep

**Files:**
- Modify: `websites/MagneticAnomaly/**/*.{jsx,tsx,ts,js,md,mdx,html,json}`

- [ ] **Step 1: Confirm site directory exists**

Run: `ls -la websites/MagneticAnomaly/ 2>&1 | head -10`

If absent or empty, skip this task.

- [ ] **Step 2: Run sweep**

```bash
find websites/MagneticAnomaly -type f \( -name '*.jsx' -o -name '*.tsx' -o -name '*.ts' -o -name '*.js' -o -name '*.md' -o -name '*.mdx' -o -name '*.html' -o -name '*.json' \) \
  ! -path '*/node_modules/*' ! -path '*/.next/*' ! -path '*/dist/*' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 3: Review and commit**

```bash
git add -u websites/MagneticAnomaly/
git commit -m "rename(phase-4i): MagneticAnomaly parent site RunPrep -> SourcePrep"
```

### Task 4.10: GitHub templates and workflows

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/config.yml`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, any non-release workflow

- [ ] **Step 1: Run sweep (release.yml already handled in Phase 3d)**

```bash
find .github -type f \( -name '*.yml' -o -name '*.yaml' \) \
  ! -name 'release.yml' \
  -print0 | xargs -0 sed -i '' \
    -e 's/RunPrep/SourcePrep/g' \
    -e 's/runprep\.io/sourceprep.io/g' \
    -e 's/\brunprep\b/sourceprep/g'
```

- [ ] **Step 2: Review**

Run: `git diff --stat .github/`
Run: `git diff .github/ISSUE_TEMPLATE/config.yml`

Expected: substitutions in contact_links URLs (discussions, troubleshooting docs, support hub, mailto emails).

- [ ] **Step 3: Commit**

```bash
git add -u .github/
git commit -m "rename(phase-4j): .github templates + non-release workflows -> SourcePrep"
```

### Task 4.11: Repo identity files (CLAUDE.md, AGENTS.md, .cursor/rules, .claude/skills)

**Files:**
- Modify: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/prep.mdc`, `.claude/skills/prep.md`

- [ ] **Step 1: Run targeted sweep**

```bash
sed -i '' \
  -e 's/RunPrep/SourcePrep/g' \
  -e 's/runprep\.io/sourceprep.io/g' \
  -e 's/\brunprep\b/sourceprep/g' \
  AGENTS.md CLAUDE.md .cursor/rules/prep.mdc .claude/skills/prep.md
```

- [ ] **Step 2: Review diff — distinguish brand strings from code paths**

Run: `git diff AGENTS.md CLAUDE.md .cursor/rules/prep.mdc .claude/skills/prep.md | head -80`

Expected: updates to prose only. The `project_id` UUIDs, `prep_project_id` key, `prep`/`prep_search`/`prep_impact`/etc MCP tool names, `src/prep/` module paths must remain unchanged. Revert any accidental identifier edits.

- [ ] **Step 3: Commit**

```bash
git add -u AGENTS.md CLAUDE.md .cursor/rules/prep.mdc .claude/skills/prep.md
git commit -m "rename(phase-4k): repo identity files (AGENTS/CLAUDE/.cursor/.claude) -> SourcePrep"
```

### Task 4.12: Server log/error strings in src/prep/server.py

**Files:**
- Modify: `src/prep/server.py`

- [ ] **Step 1: Grep for user-visible strings**

Run: `grep -n 'RunPrep\|runprep\.io' src/prep/server.py`

Expected: user-visible error messages, log strings containing the brand. Does NOT include code-level identifiers like `prep_settings.db` or `prep://`.

- [ ] **Step 2: Run targeted sweep on just this file**

```bash
sed -i '' \
  -e 's/RunPrep/SourcePrep/g' \
  -e 's/runprep\.io/sourceprep.io/g' \
  src/prep/server.py
```

Note: `\brunprep\b` (lowercase) is intentionally NOT applied here — any lowercase `runprep` in server.py would be a code-level migration marker, not brand prose.

- [ ] **Step 3: Run Python tests**

Run: `.venv/bin/pytest tests/ -v -x 2>&1 | tail -20`
Expected: all passing.

- [ ] **Step 4: Commit**

```bash
git add src/prep/server.py
git commit -m "rename(phase-4l): src/prep/server.py user-visible error/log strings -> SourcePrep"
```

---

## Phase 5 — Brand asset file renames

### Task 5.1: Rename marketing-site logo PNGs and update refs

**Files:**
- Rename: `websites/apps/marketing/public/prep-logo.png` → `sourceprep-logo.png`
- Rename: `websites/apps/marketing/public/prep-logo-dark.png` → `sourceprep-logo-dark.png`
- Modify: files referencing those logos (found by grep)

- [ ] **Step 1: Confirm source files exist**

Run: `ls -la websites/apps/marketing/public/prep-logo*.png 2>&1`

- [ ] **Step 2: Find references**

Run: `grep -rn 'prep-logo' websites/apps/marketing/src/ | head -20`

Expected: references in `page.tsx`, `layout.tsx`, `ClientLayout.tsx`, or similar (img src, Open Graph metadata).

- [ ] **Step 3: Rename files with git**

```bash
git mv websites/apps/marketing/public/prep-logo.png websites/apps/marketing/public/sourceprep-logo.png
git mv websites/apps/marketing/public/prep-logo-dark.png websites/apps/marketing/public/sourceprep-logo-dark.png
```

- [ ] **Step 4: Update references**

```bash
grep -rln 'prep-logo\.png\|prep-logo-dark\.png' websites/apps/marketing/ --include='*.ts' --include='*.tsx' --include='*.md' --include='*.mdx' \
  | xargs sed -i '' \
      -e 's|prep-logo-dark\.png|sourceprep-logo-dark.png|g' \
      -e 's|prep-logo\.png|sourceprep-logo.png|g'
```

- [ ] **Step 5: Verify no dangling references**

Run: `grep -rn 'prep-logo\(-dark\)\?\.png' websites/apps/marketing/ | grep -v node_modules | grep -v '.next'`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add -u websites/apps/marketing/
git commit -m "rename(phase-5a): marketing logo assets prep-logo*.png -> sourceprep-logo*.png"
```

### Task 5.2: Rename MagneticAnomaly parent site assets

**Files:**
- Rename: `websites/MagneticAnomaly/public/Prep-Logo2.png` → `SourcePrep-Logo2.png`
- Rename: `websites/MagneticAnomaly/app-content/Prep.md` → `SourcePrep.md`

- [ ] **Step 1: Confirm source files exist**

Run: `ls -la websites/MagneticAnomaly/public/Prep-Logo2.png websites/MagneticAnomaly/app-content/Prep.md 2>&1`

If either is absent, skip that half of this task.

- [ ] **Step 2: Find references**

Run: `grep -rn 'Prep-Logo2\|RunPrep-Logo2\|Prep\.md' websites/MagneticAnomaly/ --include='*.jsx' --include='*.tsx' --include='*.ts' --include='*.js' --include='*.json'`

Note: `App.jsx:799` may reference `/RunPrep-Logo2.png` — a dangling reference (file is `Prep-Logo2.png` currently). The rename here fixes the dangling ref incidentally.

- [ ] **Step 3: Rename files**

```bash
[ -f websites/MagneticAnomaly/public/Prep-Logo2.png ] && \
  git mv websites/MagneticAnomaly/public/Prep-Logo2.png websites/MagneticAnomaly/public/SourcePrep-Logo2.png
[ -f websites/MagneticAnomaly/app-content/Prep.md ] && \
  git mv websites/MagneticAnomaly/app-content/Prep.md websites/MagneticAnomaly/app-content/SourcePrep.md
```

- [ ] **Step 4: Update references**

```bash
grep -rln 'Prep-Logo2\|RunPrep-Logo2\|Prep\.md' websites/MagneticAnomaly/ \
  --include='*.jsx' --include='*.tsx' --include='*.ts' --include='*.js' \
  | xargs sed -i '' \
      -e 's|RunPrep-Logo2|SourcePrep-Logo2|g' \
      -e 's|Prep-Logo2|SourcePrep-Logo2|g' \
      -e 's|Prep\.md|SourcePrep.md|g'
```

- [ ] **Step 5: Verify**

Run: `grep -rn 'Prep-Logo2\|RunPrep-Logo2\b' websites/MagneticAnomaly/ | grep -v node_modules | grep -v SourcePrep`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add -u websites/MagneticAnomaly/
git commit -m "rename(phase-5b): MagneticAnomaly site assets Prep-Logo2/Prep.md -> SourcePrep-*"
```

---

## Phase 6 — Rename gate tightening

### Task 6.1: Extend gate regex to block `runprep`

**Files:**
- Modify: `scripts/rename_gate.sh`

- [ ] **Step 1: Read current script**

Run: `cat scripts/rename_gate.sh`

The current regex is `'codrag|\bclara\b|codrag\.io|codrag\.ai'`.

- [ ] **Step 2: Extend the regex**

Edit `scripts/rename_gate.sh` line 6 from:

```bash
grep -rniE 'codrag|\bclara\b|codrag\.io|codrag\.ai' \
```

to:

```bash
grep -rniE 'codrag|\bclara\b|codrag\.io|codrag\.ai|\brunprep\b|runprep\.io' \
```

- [ ] **Step 3: Run the gate**

Run: `bash scripts/rename_gate.sh | head -20`

Expected: may find 0 hits if the sweep was complete; any hits are real misses.

- [ ] **Step 4: Triage each hit**

For each reported line:
- **Legitimate migration marker** (inside `paths.py`, `data_dir_migration.py`, `watcher.py`, migration tests, function names like `migrate_from_legacy_runprep`) — add a pattern-based exception to `.rename-allowlist.txt` (the allowlist uses `grep -v -F -f` substring match). E.g., `migrate_from_legacy_runprep` or `.migrated_from_runprep`.
- **Real miss** (a prose RunPrep, URL, or stale string) — hand-edit the file.

Iterate until `bash scripts/rename_gate.sh | wc -l` returns `0`.

- [ ] **Step 5: Commit gate change and any allowlist/code updates together**

```bash
git add -u scripts/rename_gate.sh .rename-allowlist.txt
git add -u .  # any remaining sweep fixes
git commit -m "rename(phase-6): gate now blocks runprep/runprep.io; final sweep fixes included"
```

### Task 6.2: Gate must pass on clean tree

- [ ] **Step 1: Run gate**

Run: `bash scripts/rename_gate.sh | wc -l`
Expected: `0`.

If non-zero, go back to Task 6.1 Step 4.

---

## Phase 7 — Stale artifact cleanup

### Task 7.1: Confirm no old-brand build artifacts remain

- [ ] **Step 1: Search for stale brand artifacts**

Run:
```bash
find . -type f \( -name '*runprep*' -o -name '*RunPrep*' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.venv*' -not -path '*/target/*' -not -path '*/dist/*' \
  -not -path '*/.next/*' -not -path '*/.turbo/*' -not -path '*/.runprep/*' \
  -not -path '*/logs/*' -not -path '*/overnight_results/*' \
  -not -path '*/worktrees/*' -not -path '*/docs/Phase*' \
  2>/dev/null
```

Expected: no tracked files with `runprep` in the filename (directory name `.runprep/` is allowed — it's a working-tree migration source).

- [ ] **Step 2: If any tracked file remains with stale brand in its name, rename or delete**

For each file, decide: rename to `sourceprep-<name>` (if it's an active asset we missed in Phase 5) or `git rm` (if it's a stale artifact).

- [ ] **Step 3: Commit if anything changed**

```bash
# only if step 2 produced changes
git add -u .
git commit -m "rename(phase-7): clean up stale runprep-named artifacts"
```

---

## Phase 8 — Git remote rewire

**WARNING:** this phase changes remote URLs. The user should execute these steps manually; the subagent should surface the commands but NOT execute pushes without explicit user approval.

### Task 8.1: Tag pre-rename backup

- [ ] **Step 1: Tag current HEAD on main as pre-sourceprep-rename**

Run: `git fetch origin main && git tag pre-sourceprep-rename origin/main`

(Tags the commit that was the tip of main when this branch was cut — the exact rollback target.)

- [ ] **Step 2: Push the tag to the current remote**

Run: `git push origin pre-sourceprep-rename`

Expected: tag pushed successfully.

### Task 8.2: Surface remote-rewire commands (user executes)

- [ ] **Step 1: Print the rewiring plan**

The rename branch merges back to main first (via PR or fast-forward). Remote URL changes happen *after* merge:

```bash
# Planned commands — DO NOT EXECUTE without explicit approval:

# 1. Update origin to new SourcePrep repo
git remote set-url origin git@github.com:MagneticAnomaly/SourcePrep.git
git push origin main
git push origin --tags

# 2. Update mcp-dev / mcp (subtree publish remotes)
git remote set-url mcp-dev git@github.com:MagneticAnomaly/SourcePrep-MCP-DEV.git
git remote set-url mcp     git@github.com:MagneticAnomaly/SourcePrep-MCP.git

# 3. Update deploy-dev / deploy
git remote set-url deploy-dev git@github.com:MagneticAnomaly/SourcePrep-deploy.git
git remote set-url deploy     git@github.com:MagneticAnomaly/SourcePrep-deploy.git

# 4. Re-run subtree publishes to populate new remotes
scripts/publish_prep_mcp_subtree.sh
scripts/publish_deploy_subtree.sh
```

Print this block to the user and wait for their go-ahead before running step 2 onward.

---

## Phase 9 — Full verification

### Task 9.1: Rename gate green

- [ ] **Step 1:** Run `bash scripts/rename_gate.sh | wc -l`. Expected: `0`.

### Task 9.2: Python test suite

- [ ] **Step 1:** Run `.venv/bin/pytest tests/ -v 2>&1 | tail -30`. Expected: all pass.

### Task 9.3: Python type-check and lint

- [ ] **Step 1:** Run `.venv/bin/ruff check src/`. Expected: no errors.
- [ ] **Step 2:** Run `.venv/bin/mypy src/prep 2>&1 | tail -20`. Expected: no new errors vs baseline.

### Task 9.4: TypeScript typecheck across workspaces

- [ ] **Step 1:** Run `npm run typecheck 2>&1 | tail -40`. Expected: all workspaces pass.

### Task 9.5: TypeScript lint

- [ ] **Step 1:** Run `npm run lint 2>&1 | tail -40`. Expected: no errors.

### Task 9.6: Daemon smoke test

- [ ] **Step 1:** Run `.venv/bin/prep serve --port 18400 &` then `sleep 2 && curl -s localhost:18400/health`.
- [ ] **Step 2:** Verify `~/.local/share/sourceprep/` exists: `ls ~/.local/share/sourceprep/`. Expected: directory with data dir files.
- [ ] **Step 3:** Kill daemon: `kill %1 2>/dev/null`.

### Task 9.7: Tauri dev launch smoke (manual)

- [ ] **Step 1:** In `src/prep/dashboard/`, run `npm run tauri dev`. Wait for window to open.
- [ ] **Step 2:** Verify window title reads **"SourcePrep"** (not RunPrep).
- [ ] **Step 3:** Verify dashboard UI header renders **"SourcePrep"**.
- [ ] **Step 4:** Close window; confirm clean shutdown.

### Task 9.8: Final commit (if any verification fixes)

If any of the above surfaced a fix, commit it:

```bash
git add -u
git commit -m "rename(phase-9): verification fixes"
```

### Task 9.9: Branch push and PR

- [ ] **Step 1:** Push the rename branch:

```bash
git push -u origin rename/runprep-to-sourceprep
```

- [ ] **Step 2:** Open PR with title `rename: RunPrep -> SourcePrep brand sweep` and body referencing the spec `docs/superpowers/specs/2026-04-22-sourceprep-rename-design.md`. User reviews and merges to main (fast-forward, preserving history).

---

## Summary

- **Phase 0** locks in allowlist prep (1 commit).
- **Phase 1** lands the migration chain with TDD (6 commits).
- **Phase 2** removes leftover codrag debris (2 commits).
- **Phase 3** updates app identity surfaces: Tauri, VS Code, release workflow (4 commits).
- **Phase 4** sweeps brand prose + URLs across 12 scoped areas (12 commits).
- **Phase 5** renames logo asset files and references (2 commits).
- **Phase 6** tightens the rename gate (1-2 commits).
- **Phase 7** cleans up stale artifacts (0-1 commits).
- **Phase 8** rewires git remotes (tag push + manual remote-url commands).
- **Phase 9** verifies everything (0-1 commits).

Total expected commits on branch: ~30.
