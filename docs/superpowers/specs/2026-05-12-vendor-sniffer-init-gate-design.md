# Vendor-Dir Sniffer + Init Gate — Design

**Status:** Design finalized, pending user sign-off
**Date:** 2026-05-12
**Author:** brainstormed with Eric
**Related concepts:**
- Preset-based onboarding is a forced constraint (Phase 00 opportunities.md)
- TraceBuilder retains language-specific glob fallback to prevent zero-coverage pathological policies (trace/builder.py)
- Auto-merge of default globs into existing policies (Phase 115, repo_policy.py)
- Immune system UX: never block — ambient alerts only (Phase 87, MASTER_ROADMAP.md)

## Problem

When a user adds a project to SourcePrep and clicks Initialize, the indexer can recursively trace thousands of files in vendored dependency directories (e.g. `vcpkg/`, `cesium-native/`, `Pods/`) when the user's `.gitignore` doesn't cover them. The Rust walker already respects `.gitignore` (`engine/crates/prep-walker/src/lib.rs:171` — `respect_gitignore: true` is the default), so the problem is concentrated in repos with absent or incomplete `.gitignore` files — exactly the SkyPath case (a C++/iOS project with vendored `vcpkg/` (2.7 GB), `cesium-native/` (1.7 GB), and CMake `build/` (497 MB), none of which are gitignored at the time of project creation).

The existing `scan_for_presets` (`src/prep/core/repo_profile.py:239`) handles the *include* side of the auto-detect contract: it determines which language presets to enable. There is no symmetric handler for the *exclude* side. The product DNA mandates preset-based onboarding (zero free-form config); the symmetric defense against catastrophic over-indexing is missing.

## Goals

1. Detect vendored / dependency / build-output directories before the first index runs.
2. Auto-exclude high-confidence cases. Propose ambiguous cases via a one-shot confirmation modal at Initialize-click time.
3. Nudge users to fix `.gitignore` when it has clear hygiene gaps — fixing gitignore helps the user's whole toolchain, not only SourcePrep.
4. Preserve Phase 115's additive-merge contract: defaults never overwrite user-set excludes.
5. Never block legitimate user code from being indexed without explicit user choice.

## Non-Goals

- Auto-writing to `.gitignore` on the user's behalf (deferred to v2; risk of unexpected commit diffs and line-ending issues).
- Full DSL parsing of `CMakeLists.txt` to extract `add_subdirectory()` / `FetchContent_Declare()` (deferred to v2).
- Storage-class-aware thresholds (per `feedback_no_storage_speed_assumptions.md`).
- Replacing or duplicating the walker's existing `.gitignore` respect.

## Design Overview

A two-gate flow inserted between the Initialize click and the actual build kickoff. Detection runs as a background scan at project creation (and on-demand at Initialize-click if cache is stale or missing). Results are persisted as a project-record cache.

```
Click Initialize
  │
  ├─ scan cache fresh? ─ no → re-scan, await
  │
  ├─ Gate 1: Gitignore hygiene (only if git repo AND clear suspicious gaps)
  │   ├─ [Cancel Initialize] → exit
  │   └─ [Continue Anyway] → ↓
  │
  ├─ Gate 2: Vendor sniffer proposals exist?
  │   ├─ [X / Esc] → modal closes, Initialize NOT fired
  │   ├─ [Apply N Excludes & Initialize] → merge excludes, fire build
  │   └─ [Skip Excludes & Initialize] → fire build as-is (explicit choice)
  │
  └─ Build starts
```

If neither gate has anything to surface, the click flows directly to build with no UI surface — preserving zero-friction for well-configured repos.

## Architecture

### New module: `src/prep/core/vendor_sniffer/`

```
src/prep/core/vendor_sniffer/
  __init__.py        # public: scan_for_vendor_dirs(root) -> VendorScanResult
  scanner.py         # orchestrator; piggybacks on prep_engine.walk_repo accumulators
  signals.py         # tier-1/2/3 signal evaluators
  manifests.py       # per-ecosystem parser dispatch
  models.py          # VendorScanResult, VendorCandidate, dataclasses
```

Public API:
```python
def scan_for_vendor_dirs(root: Path) -> VendorScanResult:
    """
    Scan a project root for vendored / dependency / build-output directories.
    Pure function: no side effects, no persistence. Returns structured result.
    """
```

`VendorScanResult` shape:
```python
@dataclass
class VendorCandidate:
    path: str           # absolute path
    rel_path: str       # repo-relative
    size_bytes: int
    file_count: int
    reason: str         # short, human-readable; concrete signal name
    tier: Literal["auto", "propose"]
    in_gitignore: bool
    is_git_repo: bool   # is this dir a git repo (own .git/)?

@dataclass
class VendorScanResult:
    auto_excluded: list[str]              # globs ready to merge
    proposed: list[VendorCandidate]       # surfaced in modal
    gitignore_gaps: list[VendorCandidate] # subset of (auto_excluded + proposed) that aren't in root .gitignore
    scanned_at: float                     # epoch
    status: Literal["complete", "pending", "failed"]
    error: str | None
```

### Updated module: `src/prep/api/routers/projects/crud.py`

Insert sniffer dispatch immediately after the existing `scan_for_presets` block (lines 132–148). Two changes:

1. **`scan_for_presets` is upgraded to surface errors.** The current silent `try/except logger.warning` (line 147) becomes a `ScanFailure` recorded on the project record. A scan failure is a visible state, not a swallowed one.
2. **Sniffer runs async.** Project creation does NOT block on the walk. Returns immediately with `vendor_scan: { status: "pending", scan_id: <uuid> }`. A background task computes the result and writes it back to the project record.

### New endpoints

```
GET  /projects/{id}/vendor_scan
     → returns current cached VendorScanResult (or { status: "pending" })

POST /projects/{id}/vendor_scan/rescan
     → forces a fresh scan; returns the new result

POST /projects/{id}/exclude_proposals/apply
     body: { exclude: [rel_paths], dismiss: [rel_paths], add_to_gitignore: [rel_paths] }
     → unions excluded paths into exclude_globs (Phase 115 contract)
       dismissed paths are recorded so they don't re-surface on rescan
       add_to_gitignore is currently a no-op stub (v2 will write to .gitignore)
       returns updated config + status
```

### New UI components

| Component | Location | Purpose |
|---|---|---|
| `GitignoreHygieneModal.tsx` | `packages/ui/src/components/project/` | Gate 1 — gitignore nudge |
| `InitExcludeReviewModal.tsx` | `packages/ui/src/components/project/` | Gate 2 — vendor proposals |
| `VendorScanIndicator.tsx` | `packages/ui/src/components/project/` | Inline status strip (Sources page re-run surface) |

### Updated UI

| File | Change |
|---|---|
| `packages/ui/src/components/dashboard/IndexStatusCard.tsx` | Initialize button gates on vendor_scan state; click handler routes through Gate 1 → Gate 2 → build |
| `src/prep/dashboard/src/components/settings/v2/pages/Sources.tsx` | New "Scan for Vendor Dirs" button next to "Auto-Detect Stack"; inline strip rendering of last scan result |

## Detection Heuristic (Signal-Based, Tiered)

Evaluated against every immediate-child directory of the project root. Deeper recursion is not used — vendor dirs are conventionally top-level, and deep recursion is slow and false-positive-prone.

### Tier 1 — Auto-exclude (merged immediately, user is notified but not asked)

Any one of:
- Name in canonical package-manager install-dir whitelist: `node_modules`, `Pods`, `Carthage`, `vendor`, `bower_components`, `.bundle`, `vcpkg_installed`, `.build`, `target`, `__pycache__`, `.venv`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `htmlcov`
- Listed in repo-root `.gitmodules` as a submodule path
- Listed in repo-root `.gitignore` with a directory pattern (user already declared it ignorable, but the walker can't deduce this when gitignore is e.g. `.gitignore`-ignored itself — defensive belt-and-suspenders)
- Contains a `.git/` (must be `is_dir()`, not just `exists()` — see worktree caveat below) **AND** is listed in `.gitmodules` **OR** in root `.gitignore`
- Contains a CMake-build marker: `CMakeCache.txt`, `build.ninja`, `compile_commands.json` at its root
- Contains a `.gitignore` whose first non-comment line is `*` (the "ignore everything" build-output convention)

Whitelist lives next to `DEFAULT_EXCLUDE_DIR_NAMES` in `repo_profile.py` so additions are colocated with the existing exclude list.

### Tier 2 — Propose with confirmation (Gate 2 modal)

Any one of, AND not classified as Tier 1, AND not Tier 3 user-code:
- Contains a `.git/` (`is_dir()`) but NOT in `.gitmodules` and NOT in `.gitignore` → "nested git repo, possibly vendored"
- Contains its own project-anchor file (e.g. `package.json`, `Cargo.toml`, `pyproject.toml`) AND that anchor is NOT referenced as a workspace member by the root manifest → "separate sub-project, not in root workspaces"
- **Fallback only:** size > 100 MB OR file count > 5,000, AND no project anchor present, AND no other signal classified it → "large directory, no classification signal"

The fallback is the only place size matters, and the modal reason string makes that explicit so the user can judge.

### Tier 3 — Skip entirely (never proposed, never auto-excluded)

- Contains a project anchor (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.xcodeproj`, `*.xcworkspace`, `Package.swift`, `*.sln`, `*.csproj`, `Gemfile`, `composer.json`, `pubspec.yaml`) AND that anchor is referenced as a workspace member by the root manifest → user code
- Already covered by an existing `exclude_globs` entry → no point re-surfacing
- Already covered by `DEFAULT_EXCLUDE_DIR_NAMES` in `repo_profile.py` → no point re-surfacing

### Manifest parsers (v1 scope)

| File | Parser | Used for |
|---|---|---|
| `.gitmodules` | INI-style line scanner | `path = ...` extraction → Tier 1 submodule list |
| `.gitignore` (root only) | Line-pattern matcher | Top-level directory pattern lookup |
| `package.json` (root) | JSON parse | `workspaces:` array → Tier 3 user-code list |
| `Cargo.toml` (root) | TOML parse | `[workspace] members =` → Tier 3 user-code list |
| `go.work` (root) | Simple grammar | `use (...)` block → Tier 3 user-code list |
| `Podfile` (root) | Existence check only | Hint that `Pods/` is a CocoaPods dir (no parsing required) |

Failure to parse any manifest is non-fatal: the parser logs and returns empty results; the directory's classification falls through to structural and size signals.

**Deferred to v2:** `CMakeLists.txt` `add_subdirectory`/`FetchContent_Declare` parsing, `vcpkg.json` parsing, `.csproj`/`.sln` parsing for .NET, `composer.json` for PHP, `Gemfile` for Ruby. v1 covers the user-listed common ecosystems; v2 fills gaps when use cases warrant.

## Gate 1: Gitignore Hygiene Modal

Fires ONLY if both:
- Repo IS a git repo (`<root>/.git/` exists as dir or file)
- `vendor_scan.gitignore_gaps` is non-empty AND contains at least one canonical-name match (`node_modules`, `Pods`, `vcpkg_installed`, `target`, `.venv`, etc.) OR a build-output dir (CMake marker present)

The "clearly suspicious" gate is narrow on purpose: it does NOT fire on `cesium-native/`-style project-specific names (those a user might intentionally vendor), only on universally-conventional ignorables.

**Modal content:**
```
Title: Your .gitignore looks incomplete

Body: SourcePrep detected directories at your project root that are
typically gitignored but aren't in your .gitignore. Adding them helps
every tool that reads your repo — not just SourcePrep.

Found (not in .gitignore):
  • node_modules/        (450 MB, 21,400 files)
  • vcpkg_installed/     (1.2 GB, 8,900 files)

Recommended additions (copy/paste into .gitignore):
  ┌─────────────────────────┐
  │ node_modules/           │
  │ vcpkg_installed/        │  [Copy]
  └─────────────────────────┘

Buttons:
  [Cancel Initialize]   [Continue Anyway]
```

**Behavior:**
- `Cancel Initialize` — closes modal, Initialize NOT fired. User edits gitignore themselves, re-clicks Initialize. On re-click, scan re-runs (cache freshness check) and the modal won't fire if the gaps are now covered.
- `Continue Anyway` — closes modal, flow proceeds to Gate 2. Items remain on `vendor_scan.gitignore_gaps` for next session (we don't pretend they're not gaps).
- `X` / Esc / outside click — same as `Cancel Initialize` (safe default).

## Gate 2: Vendor Sniffer Modal (`InitExcludeReviewModal`)

Fires if `vendor_scan.proposed` is non-empty. The modal also shows the Tier-1 auto-excluded items in a collapsed-by-default section — informationally, not actionably, so the user can see what we did silently and isn't surprised after Initialize.

**Modal content:**
```
Title: Review what to exclude before indexing

Body: SourcePrep found directories that may not need to be indexed.
Tier-1 items are excluded automatically; review the proposals below
and confirm before we build the index.

[Auto-excluded section, collapsed by default]
  ✓ Pods/                          (CocoaPods install dir)
  ✓ build/                         (CMake build output, CMakeCache.txt present)
  ✓ <repo>/embedded-tool/.git/...  (nested git submodule)

[Review proposals — checkboxes, default checked]
  ☑ cesium-native/  1.7 GB, 12,304 files   Nested git repo, possibly vendored
  ☑ vcpkg/          2.7 GB,  8,210 files   Nested git repo, possibly vendored
  ☐ webgl-component/ 80 MB, 230 files      Separate project (own package.json),
                                            not in root workspaces

Footer:
  Selected: 2 of 3 proposals    [Apply 2 Excludes & Initialize]   [Skip Excludes & Initialize]
```

**Behavior:**
- `X` / Esc / outside click — closes modal, Initialize NOT fired. User must explicitly choose one of the action buttons to proceed. No silent dismissal-into-build.
- `Apply N Excludes & Initialize` — unions checked items into `exclude_globs` (Phase 115 contract), records unchecked items as dismissed (won't re-surface on rescan), fires build.
- `Skip Excludes & Initialize` — fires build with no exclude changes. Items remain in `vendor_scan.proposed` for the user to revisit via the Settings re-scan surface.

The default-checked state for proposals leans toward "exclude" because that's the safer-from-runaway-indexing default; the user opts out per row for the rare case they want to index a vendored dir.

**Size-fallback proposals** (the "large directory, no classification signal" reason) are still default-checked, but the modal renders them with a different visual treatment (e.g. a question-mark icon) to signal weaker evidence. If user feedback shows over-exclusion on size-fallback items, we can change the default to unchecked for that subset specifically in a later iteration.

## State & Lifecycle

### Persistence

`VendorScanResult` is stored on the project record under a new `vendor_scan` field (single object, not a separate table). The `dismissed_proposals` list (paths the user opted not to exclude) is also persisted on the project record — this prevents re-surfacing the same items on rescan.

### Cache freshness

At Initialize click, compute repo root mtime (cheap stat). If `mtime > vendor_scan.scanned_at`, kick off rescan, show "Scanning…" state on Initialize button, await fresh result before evaluating gates. Otherwise use cached result directly.

### Async scan at project creation

`POST /projects` returns immediately with `vendor_scan: { status: "pending" }`. A background task runs the scan and writes the result to the project record. If the user clicks Initialize before the scan completes, the click handler awaits the in-flight scan rather than re-triggering.

### Legacy projects (pre-feature)

Any project record with `vendor_scan: null` (created before this feature deployed) triggers a fresh scan when the user first clicks Initialize. SkyPath is exactly this case.

### Scan failure handling

If the scan fails (Rust engine error, disk error, parse error), `vendor_scan.status: "failed"` with `error: <message>`. The Initialize button shows a "Scan failed — retry?" state. User can retry; if they explicitly choose to bypass, Initialize proceeds without gate logic. The failure event is logged at WARN level with the error and project id.

## Performance Notes

- The scan piggybacks on `prep_engine.walk_repo` traversal results: `scan_for_presets` and `scan_for_vendor_dirs` share a single walk, accumulating per-top-level-directory file counts and total sizes during the existing walk. This avoids a second traversal.
- Manifest parsing happens after the walk completes, against parsed file contents read in-process. Total overhead: ~10–50ms on typical projects.
- For very large projects (SkyPath's vcpkg/cesium-native combined are 4.4 GB), the walker is already the dominant cost; sniffer overhead is rounding error.
- No storage-class-aware branching. Flat thresholds apply uniformly. (Per `feedback_no_storage_speed_assumptions.md`.)

## Edge Cases & Caveats

- **Git worktrees** (`<root>/.git` is a *file*, not a dir, pointing to the real `.git/` elsewhere). Tier-1 nested-`.git/` check uses `is_dir()` not `exists()`. The worktree's root is correctly treated as a git repo for Gate 1 purposes.
- **Non-git repos.** Gate 1 is skipped entirely. Gate 2 runs as designed.
- **Monorepos with workspaces.** Root `package.json` `workspaces:` array, root `Cargo.toml` `[workspace] members`, root `go.work` `use (...)` — all mark their listed directories as Tier-3 user code, never proposed or auto-excluded.
- **User intentionally vendors a library.** They want `cesium-native/` indexed because they edit it. The Gate 2 modal lets them uncheck it. Once unchecked, it's recorded as a dismissed proposal and won't resurface unless the user rescans manually from Settings.
- **`node_modules/` committed on purpose** (rare but exists). Gate 1 fires; user clicks `Continue Anyway`. Gate 2 fires with `node_modules/` as Tier-1 auto-excluded — user can't override Tier-1 from the modal in v1. **Known v1 limitation.** Workaround: user manually removes `**/node_modules/**` from `exclude_globs` in Settings after Initialize. Caveat to the workaround: a future rescan (manual or post-mtime-change) would re-merge it via Phase 115 union — the workaround sticks only until a rescan happens. v2 will add a `tier1_overrides` list on the project record so demoting a Tier-1 item is sticky across rescans.

## Justification for Gating (vs. "Never Block" Principle)

The Phase 87 Immune System concept states: *"Immune system UX: Never block. Ambient alerts only. Feels like a helpful colleague, not a CI gate."* The vendor-sniffer modals *do* block Initialize. This is a deliberate exception:

- The "never block" principle applies to **ongoing operations** (audit findings, antibody alerts, search results) where blocking would impede daily work.
- First-time configuration is **a different mode**. Phase 105's "managed pipeline stage runs" already establish gates at stage boundaries when configuration decisions are required.
- The gates here resolve a configuration question (what to index), which is fundamentally different from a constraint check (did you write good code?).
- Modals are one-shot; once the user makes a choice, ongoing operations are unblocked.

This exception is documented in the spec to prevent future drift toward "we never gate anything, even at config time."

## Testing Strategy

### Unit tests (pure-function sniffer)

- `tests/test_vendor_sniffer/test_signals.py` — each signal evaluator against synthetic directory fixtures (whitelist name, nested `.git/`, build marker, etc.)
- `tests/test_vendor_sniffer/test_manifests.py` — each parser against representative fixture files (well-formed, malformed, empty)
- `tests/test_vendor_sniffer/test_scanner.py` — end-to-end on small synthetic project trees
- `tests/test_vendor_sniffer/test_skypath_fixture.py` — a SkyPath-shaped fixture (xcworkspace + nested-.git/ vendor dirs + CMake build/ + webgl-component sibling) confirming expected Tier 1/2/3 classification

### Integration tests

- `tests/test_projects_vendor_scan_endpoints.py` — `GET /projects/{id}/vendor_scan`, `POST /rescan`, `POST /apply` against a test daemon
- Async-creation race test: hit `GET /vendor_scan` immediately after `POST /projects`, confirm `pending` status, await completion, confirm result

### E2E (Playwright)

- `tests/e2e/init_gate_flow.spec.ts` — create project with vendor dirs, click Initialize, both modals render, Apply path merges excludes, Skip path doesn't, Cancel exits cleanly

### Live-validation (per `feedback_restart_daemon_before_live_validation.md`)

- Restart daemon before validating; daemon has no hot-reload
- Validate on SkyPath itself (live dogfooding) — expected modal contents documented in PR

## Open Questions (intentionally left for implementation phase)

- Exact JSON shape of the `apply` endpoint response — derive when implementing
- Whether the Settings re-scan surface deserves its own card or just lives inline above the existing exclude_globs editor
- Whether to add a `tooltip` in the Gate 2 modal showing the full glob that will be added to `exclude_globs` per row (probably yes, but small detail)

## Open Risks

- **Manifest-parsing scope creep.** v1 list is deliberately small; the temptation to add "just one more parser" should be resisted in implementation.
- **Modal fatigue.** Two modals before Initialize is the maximum; if a third gate becomes desirable later, that's a signal to revisit Approach B's `init_readiness` endpoint pattern instead of stacking modals.
- **Cesium-native and similar project-specific names** could become a steady stream of Tier 2 proposals across projects. Long-term, an opt-in shared registry of "commonly vendored library names" could elevate them to Tier 1, but that's out of scope for v1.

## Out of Scope (v1) / Future Work

- Auto-writing `.gitignore` (v2 candidate; needs UX work on commit-diff handling)
- `CMakeLists.txt` DSL parsing
- `.csproj` / `.sln` / `composer.json` / `Gemfile` / `pubspec.yaml` parsers
- Storage-aware thresholds (rejected per memory)
- Tier-1 "override in modal" affordance (rejected for v1; manual settings edit is the workaround)
- Telemetry: dismiss-rate tracking on proposals (useful for auto-tuning heuristics in v2)

## Files Touched (Expected)

**New:**
- `src/prep/core/vendor_sniffer/__init__.py`
- `src/prep/core/vendor_sniffer/scanner.py`
- `src/prep/core/vendor_sniffer/signals.py`
- `src/prep/core/vendor_sniffer/manifests.py`
- `src/prep/core/vendor_sniffer/models.py`
- `src/prep/api/routers/projects/vendor_scan.py` (new sub-router; mounted under existing `/projects/{id}/vendor_scan/*`)
- `packages/ui/src/components/project/GitignoreHygieneModal.tsx`
- `packages/ui/src/components/project/InitExcludeReviewModal.tsx`
- `packages/ui/src/components/project/VendorScanIndicator.tsx`
- `tests/test_vendor_sniffer/...` (multiple)
- `tests/e2e/init_gate_flow.spec.ts`

**Modified:**
- `src/prep/api/routers/projects/crud.py` (insert sniffer dispatch; surface scan_for_presets errors)
- `src/prep/api/routers/projects/__init__.py` (mount new sub-router)
- `src/prep/core/repo_profile.py` (small additions: whitelist, helper exports)
- `packages/ui/src/components/dashboard/IndexStatusCard.tsx` (Initialize click handler routes through gates)
- `src/prep/dashboard/src/components/settings/v2/pages/Sources.tsx` (new "Scan for Vendor Dirs" button + inline strip)
- Project record schema (add `vendor_scan` and `dismissed_proposals` fields)
