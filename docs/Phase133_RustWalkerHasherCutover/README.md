# Phase 133 — Complete the Rust Walker/Hasher Cutover

> **Scope:** Finish the half-shipped migration from Python's `os.walk` +
> `fnmatch` + `hashlib.sha256` to the Rust `prep-walker` crate's
> `walk_repo` + `blake3` for the Graph Scope coverage path. Kill the
> divergence between Python `compute_trace_coverage` and the Rust
> structural rebuild walker, which today silently disagree on file
> eligibility along six concrete surfaces.
>
> **Prior art:** Phase 115 Step 9 (`tests/test_walker_parity.py` —
> default-exclude string parity). Phase 96 / F-40 (watcher swapped
> `pathlib.Path.match` → `pathspec.gitwildmatch` for the same bug
> class). Phase 118 U16 / U19 (force_from_start clears watcher-derived
> `_changed_paths`; logs the gap so divergence is visible — this phase
> removes the *source* of that divergence). Phase 132 Followup dogfooding
> doc (`docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md`, "filter
> divergence is real" finding).
>
> **Status:** Spec approved 2026-05-09. Implementation pending.
>
> **Framing:** Resumption, not fresh design. Every Rust primitive this
> phase needs already exists in the codebase. The PyO3 bindings are
> already wired (`prep_engine.walk_repo`, `prep_engine.hash_content`).
> The only missing work is the Python-side cutover and the manifest
> hash-algo migration.
>
> **Trigger incident:** 2026-05-09 live debugging session — user
> reported "watcher never auto-triggers." Investigation surfaced the
> watcher gate bug (fixed in same session) AND a deeper divergence:
> Python `compute_trace_coverage` and the Rust walker disagree on which
> files are "in scope," which means the Graph Scope panel can correctly
> mark a file as stale while the rebuild silently skips it. The
> Phase 118 U19 logging was added as a *symptom mitigation*; this phase
> removes the *root cause*.

---

## What this phase completes

The work was started, primitives shipped, and stopped one cutover short.
This phase performs the cutover.

### What's already in place (do not rebuild)

| Primitive | Location | State |
|---|---|---|
| Rust `walk_repo()` — globset/gitignore-correct file walking | `engine/crates/prep-walker/src/lib.rs:180` | ✅ Built, used by `build_trace` (so structural rebuilds already use it) |
| `prep_engine.walk_repo` PyO3 binding | `engine/crates/prep-engine/src/lib.rs:34, 891` | ✅ Exposed, never called from Python |
| Rust `hash_content()` — BLAKE3 over UTF-8 bytes | `engine/crates/prep-walker/src/lib.rs:322` | ✅ Built |
| `prep_engine.hash_content` PyO3 binding | `engine/crates/prep-engine/src/lib.rs:91, 892` | ✅ Exposed, never called from Python |
| `tests/test_walker_parity.py` — default-exclude string-list parity | `tests/test_walker_parity.py` | ✅ 3 tests pinning Rust ⊇ Python L1 excludes |
| Defensive "preserve file_hashes before Rust overwrites manifest" | `src/prep/core/trace/builder.py:375-386, 446-449` | ✅ Fingerprint of the half-done cutover — Python recomputes hashes after every Rust trace build because Rust hashes are incompatible |

### What this phase changes

| Change | Surface |
|---|---|
| **(a)** `compute_trace_coverage` calls `prep_engine.walk_repo` for the file-set, drops `os.walk` + `fnmatch` blocks | `src/prep/core/trace/coverage.py:236-303` |
| **(b)** Hash callers switch from `stable_file_hash` to `prep_engine.hash_content` | `src/prep/core/trace/coverage.py:163, 354`; `src/prep/core/trace/builder.py:218, 481` |
| **(c)** Manifest schema gains `hash_algo` field (`"sha256-64"` legacy, `"blake3-128"` going forward) | `src/prep/core/manifest.py`; `src/prep/core/trace/builder.py` write path |
| **(d)** Coverage compares `manifest.hash_algo` against current algo; mismatch → treat all hashed files as stale once (self-heal) | `src/prep/core/trace/coverage.py` (new branch in stale-detection block) |
| **(e)** Update / add tests | `tests/test_walker_parity.py` (extended); new `tests/test_phase133_*.py` |
| **(f)** Migrate `_compute_file_hashes` to `prep_engine.walk_repo` so both walk paths agree, then add a temporary one-shot assertion that the "preserve + merge" defensive logic produces zero additions. Actual deletion of the now-dead defensive logic deferred to a follow-up patch one release cycle later (so we have a release in production with the assertion green before removing the safety net). | `src/prep/core/trace/builder.py:375-388, 451-457, 466-489` |

### What this phase does NOT do (deferred or out of scope)

| Deferred item | Why |
|---|---|
| Watcher's pathspec filter (`watcher.py:_load_policy_globs`, `_is_relevant`) | The watcher captures *events*, not *file scope*. F-40 already fixed it to use pathspec. Touching it expands blast radius without solving any reported bug. Tracked separately. |
| Rust `hash_files()` parallel batch binding | The per-file `hash_content` call site is fine for coverage (small to medium repos). Batch binding is a perf optimization for a future phase if profiling shows hashing is the bottleneck. |
| `trace_nodes.jsonl` schema changes | Manifest gains one field (`hash_algo`). The trace nodes themselves are unchanged. Avoids triggering downstream consumers' schema-version checks. |
| Eliminating Python's `stable_file_hash` entirely from `src/prep/core/ids.py` | `stable_file_hash` is used by `coverage.py` and `builder.py` for the `file_hashes` map (this phase migrates those to BLAKE3). It is also used elsewhere — `cluster.py`, `embedder.py`, `epistemic_score.py`, etc. — for content-addressing inside the embedding/clustering pipeline. Those uses are correct as SHA-256-64 (they're not compared against any Rust output). Leave them alone. |
| One-time bulk hash rotation across all projects | Path A is self-healing per-project on first coverage call. Bulk rotation has no benefit and adds complexity. |

---

## Architecture

### Today (the divergence)

```
Graph Scope panel  ─→  GET /trace/coverage  ─→  compute_trace_coverage()
                                                    │
                                                    ├─→  os.walk + fnmatch (Python, custom)
                                                    └─→  hashlib.sha256[:16]  (Python)

Structural rebuild ─→  TraceBuilder._rust_path  ─→  prep_engine.build_trace()
                                                    │
                                                    └─→  prep_walker::walk_repo (Rust, globset/ignore)

                       After Rust build: TraceBuilder recomputes file_hashes  ─→  hashlib.sha256[:16]  (Python)
```

Two filter implementations. Two walks (or one walk + one re-hash). Six
concrete divergence surfaces (see "Divergence map" below).

### After this phase

```
Graph Scope panel  ─→  GET /trace/coverage  ─→  compute_trace_coverage()
                                                    │
                                                    ├─→  prep_engine.walk_repo()    ← UNIFIED
                                                    └─→  prep_engine.hash_content() ← UNIFIED

Structural rebuild ─→  TraceBuilder._rust_path  ─→  prep_engine.build_trace()
                                                    │
                                                    └─→  prep_walker::walk_repo (same)

                       After Rust build: TraceBuilder writes file_hashes  ─→  prep_engine.hash_content()  ← UNIFIED
```

One filter implementation. One hash function. Divergence becomes
impossible by construction for the file-set definition.

The categorization layer (`traced` / `stale` / `untraced` / `excluded` /
`pending_embedding`) stays in Python. The HTTP envelope, caching,
backfill-from-`trace_nodes.jsonl`, and embedded-paths intersection
all stay where they are. Only the disk-touching primitives move.

### Divergence map (what we're killing)

For each surface below, "Rust wins" means the post-cutover behavior
matches what the rebuild already does today. The Graph Scope panel
catches up to the rebuild's truth.

| # | Surface | Rust walker | Today's `compute_trace_coverage` | After cutover |
|---|---|---|---|---|
| 1 | **Glob engine** | `OverrideBuilder` from ripgrep's `ignore` crate (proper `**` recursion, gitignore semantics) | stdlib `fnmatch` + a band-aid that strips leading `**/` | Rust wins (kills the F-40 bug class on this code path) |
| 2 | **Hidden dirs** | `.hidden(false)` — walks `.foo` dirs, relies on gitignore + exclude globs | `dirs[:] = [d for d in dirs if … not d.startswith(".")]` — silently prunes ALL `.foo` dirs | Rust wins (stops silently dropping `.github/workflows/*` etc.) |
| 3 | **Glob anchor** | matches against full repo-relative path | tries `fnmatch(rel_path, p)` OR `fnmatch(base, p)` — more lenient on basename matches | Rust wins (consistent semantics) |
| 4 | **Backfill carve-out** | none | "if rel_path not in manifest_hashes: continue" — manifest-hashed files bypass include_globs check | The carve-out moves to the categorization layer where it belongs (any file in `manifest_hashes` is included for hash comparison regardless of current globs — but discovery is uniform) |
| 5 | **`max_files` cap** | 100 000 ceiling (`WalkConfig::default().max_files`) | unbounded | Rust cap applies to coverage too. Surface a WARNING in coverage response when cap is hit so operators see it. |
| 6 | **Nested .gitignore** | ripgrep's full ignore stack (root + nested + global + git/info/exclude) | only root `.gitignore` loaded explicitly | Rust wins (correct on monorepos with subdirectory .gitignores) |

---

## Hash format problem and Migration Path A

### The problem

Today's manifest stores hashes as 16-hex-char SHA-256 prefixes:

```python
# src/prep/core/ids.py:6-11
def stable_sha256(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[: int(length)]

def stable_file_hash(text: str) -> str:
    return stable_sha256(text, length=16)
```

→ 16 hex chars = 64-bit truncated SHA-256.

The Rust binding produces 32-hex-char BLAKE3 prefixes:

```rust
// engine/crates/prep-walker/src/lib.rs:322-325
pub fn hash_content(content: &str) -> String {
    let hash = blake3::hash(content.as_bytes());
    hash.to_hex()[..32].to_string()  // 32 hex chars = 128 bits
}
```

**Different algorithm, different length.** A direct cutover would make
every hash in every existing `trace_manifest.json` worthless — every
file would compare-mismatch and look "stale."

### Path A — `hash_algo` field, self-heal on mismatch

Add a `hash_algo` field to the manifest that names the algorithm + bit
length used to compute the values in `file_hashes`. Coverage reads the
field on manifest load; if it doesn't match the current
`CURRENT_HASH_ALGO = "blake3-128"` constant, the comparison branch
treats every hashed file as stale once (no hash computed, no false
negatives), and the next structural rebuild rewrites the manifest with
the new algo.

**Concrete shape:**

```json
{
  "version": "1",
  "built_at": "2026-05-09T22:00:00Z",
  "hash_algo": "blake3-128",
  "file_hashes": {
    "src/foo.py": "a3f2c1d8…(32 hex chars)",
    "src/bar.py": "b1e4d6a9…(32 hex chars)"
  },
  ...
}
```

**Coverage logic:**

```python
manifest_algo = manifest.get("hash_algo", "sha256-64")  # back-compat default
algo_mismatch = manifest_algo != CURRENT_HASH_ALGO

# ... during the per-file stale check:
if algo_mismatch:
    # Self-healing path: don't compute current hash; mark stale.
    # Next structural rebuild will rewrite manifest with new algo.
    stale_files.append(file_info)
    continue

if needs_hash:
    current_hash = prep_engine.hash_content(source)
    if current_hash != prev_hash:
        stale_files.append(file_info)
    else:
        traced_files.append(file_info)
```

**Builder logic** (writing the manifest):

```python
manifest_obj = build_manifest(
    file_hashes=file_hashes,
    hash_algo=CURRENT_HASH_ALGO,  # always tag what we wrote
    ...
)
```

### Why Path A over B and C

- **Path B (mirror SHA-256 in Rust):** Adds a "compatibility hash" maintained forever, loses the BLAKE3 perf win, and locks the codebase into a slower hash for no reason once the migration is complete. Net negative.
- **Path C (big-bang rotation):** Adds a startup migration path that has to handle every manifest in `~/.local/share/sourceprep/projects/<id>/`. More code, more failure modes, no benefit over A. Also fights against the "self-healing" pattern the codebase already uses extensively.
- **Path A:** Uses the existing F-66/check_coverage_gap → structural rebuild → manifest rewrite path that the system runs all the time anyway. The "files all look stale once" effect is cosmetic; the rebuild that follows is exactly what you'd want regardless. ~10 lines of code in coverage.py. Zero new failure modes.

### Edge cases Path A handles correctly

| Scenario | Behavior |
|---|---|
| Manifest predates this phase (no `hash_algo` field) | Defaults to `"sha256-64"`. Mismatches current. Marks all hashed files stale. Self-heals on next rebuild. |
| Manifest has `hash_algo: "blake3-128"` (post-cutover) | Matches current. Hash compare proceeds normally. |
| User downgrades daemon to pre-Phase-133 | Manifest with `hash_algo: "blake3-128"` is read by old code, which ignores the field and tries to compare Python SHA-256 against Rust BLAKE3 hashes — every file shows stale. Old code's response: trigger a rebuild. Old code rewrites manifest with SHA-256 hashes. Re-upgrade re-triggers self-heal. **Acceptable degradation** — no data corruption, cosmetic stale flag. |
| Manifest hash_algo field is corrupted / unknown value | Defaults to "treat as mismatch" → self-heal. Same as the predates-phase case. |
| Two daemons writing the same manifest concurrently with different algos | Already excluded by the existing `_backfill_lock` in coverage.py. Last writer wins; consistent end state. |
| Migration during an active pipeline run | The rebuild that's already in progress completes and writes the new algo. No additional handling needed. |

### Edge case Path A does NOT handle

If `prep_engine.hash_content` returns a value that — for some bizarre
content — happens to *equal* the truncated SHA-256 of that same
content, the file would be falsely judged "fresh" if the algo field
were missing AND the hash algo were assumed to match. **This is
impossible by construction** because the algo defaults to
`"sha256-64"` (mismatch with `"blake3-128"`) when the field is absent.
Listed for completeness; no mitigation needed.

---

## Detailed change manifest

| Task | File(s) | Summary |
|------|---------|---------|
| 1 | `src/prep/core/manifest.py` | Add `hash_algo: Optional[str] = None` parameter to `build_manifest`. Always emit the field when `file_hashes` is set. Add `CURRENT_HASH_ALGO` module constant (`"blake3-128"`). |
| 2 | `src/prep/core/trace/coverage.py` | Replace `os.walk` + `fnmatch` blocks (lines ~227-303) with a single `prep_engine.walk_repo(repo_root, include_globs, exclude_globs, max_file_bytes)` call. Iterate the returned `FileEntry` list to build `traced/untraced/stale/excluded` lists. Replace `stable_file_hash(source)` calls (lines 163, 354) with `prep_engine.hash_content(source)`. Read `manifest.get("hash_algo", "sha256-64")`; if mismatch, mark all previously-hashed files stale without computing. |
| 3 | `src/prep/core/trace/builder.py` | Replace `stable_file_hash` calls at lines 218, 481 with `prep_engine.hash_content`. Pass `hash_algo=CURRENT_HASH_ALGO` to `build_manifest` at lines 312, 356. **Do NOT yet delete** the "preserve file_hashes before Rust overwrites" logic at lines 375-388, 451-457 — that's defense-in-depth against the divergence Task 4 closes; deleting it before Task 4 lands removes the safety net while the bug it guards against still exists. |
| 4 | `src/prep/core/trace/builder.py` (Rust path: `_build_rust` and `_compute_file_hashes`) | Migrate `_compute_file_hashes` (line 466) from `self._enumerate_files()` (Python `os.walk`) to `prep_engine.walk_repo`. Same primitive used by Rust's `build_trace` internally → both walks produce identical file sets by construction. The "preserve + merge" logic in `_build_rust` becomes truly dead code at this point. |
| 4b | `src/prep/core/trace/builder.py` | After Task 4 lands, add a temporary one-shot assertion at the merge site (line 451-457): `assert len(set(saved_file_hashes) - set(new_hashes)) == 0, "merge produced additions — Rust/Python walker divergence still present"`. Run on real fixture repos + the live SourcePrep repo. When green for one full release cycle, delete the assertion AND the "preserve + merge" defensive logic. |
| 5 | `tests/test_walker_parity.py` | Extend with **behavior** parity tests, not just default-exclude string parity: build a fixture repo with the divergence-trigger files (`.github/workflows/ci.yml`, nested `.gitignore`, files at exactly 100k count, etc.); assert `prep_engine.walk_repo(...)` and the post-cutover `compute_trace_coverage(...)` return identical file sets. **Phase 125c forward-look:** include explicit bimodal coverage — one test passes the source-indexing exclude set (CLAUDE.md / `.cursor/rules/*.mdc` excluded) and asserts those files do NOT appear; a second test passes a doc-discovery exclude set (those globs removed) and asserts they DO appear. Locks in the walker primitive's flexibility for the future Phase 125c doc-discovery caller. |
| 6 | `tests/test_phase133_hash_migration.py` (new) | Path A self-heal: write a manifest with `hash_algo: "sha256-64"` and SHA-256 file_hashes; call `compute_trace_coverage`; assert all files marked stale, no hashes computed. After a structural rebuild: assert manifest has `hash_algo: "blake3-128"` and BLAKE3 hashes; second `compute_trace_coverage` call returns them as `traced` (not stale). |
| 7 | `tests/test_phase133_coverage_uses_rust_walker.py` (new) | Direct test that `compute_trace_coverage` calls `prep_engine.walk_repo` (mock the binding, assert it was called with the expected args). Locks in the cutover. |
| 8 | `tests/test_phase133_hidden_dirs.py` (new) | Regression guard for divergence #2: a `.github/workflows/ci.yml` not in any exclude glob and not gitignored must appear in coverage results post-cutover (it currently doesn't because of `not d.startswith(".")` pruning). |
| 9 | `tests/test_phase133_max_files_warning.py` (new) | When the Rust walker hits its 100k cap, the coverage response surfaces a WARNING (truncated count + signal in the response envelope). |
| 10 | `docs/Phase133_RustWalkerHasherCutover/IMPLEMENTATION_PLAN.md` | Created by `superpowers:writing-plans` after this spec is approved. |
| 11 | `docs/MASTER_TODO.md` | Append Phase 133 entry to the recent-phases index. |

**Note on dropped CLI sub-task:** an earlier spec draft included a
`prep diagnose hash-algo` CLI command. Dropped after researching
`src/prep/cli.py` — the CLI today uses a flat `@app.command()`
pattern with no `diagnose` subcommand group. Adding a one-off
single-purpose command for what is a *one-time* migration validation
creates persistent CLI surface to maintain. The Migration validation
section below uses an inline `jq` one-liner instead. If we later need
real diagnostic surface, that's a separate phase that designs the
`diagnose` subcommand namespace properly rather than growing it
ad-hoc.

---

## Testing strategy

### TDD discipline

Per the `superpowers:test-driven-development` skill (and the
`feedback_test_full_import_chain.md` memory: "for cross-module
features, at least one test must not mock the seam under test"), the
test plan is layered:

1. **Unit / mock layer** — verify each function's contract in
   isolation. `test_phase133_coverage_uses_rust_walker.py` mocks
   `prep_engine.walk_repo` to assert call shape and the categorization
   logic is fed correctly.
2. **Real-binding integration layer** — at least one test per task
   exercises the actual `prep_engine` PyO3 binding against a temp-dir
   fixture repo. No mocks at the seam between Python and Rust. This
   catches binding ABI drift, hash-format regressions, and walker
   behavior changes that mocks cannot.
3. **Migration layer** — `test_phase133_hash_migration.py` writes a
   pre-cutover manifest, runs through the cutover code path, asserts
   the self-heal behavior end-to-end.
4. **Parity contract layer** — `tests/test_walker_parity.py` already
   pins string parity. We extend it with **behavior parity** for the
   six divergence surfaces above, on real fixture repos with
   intentional divergence triggers.

### Test fixtures

A new `tests/fixtures/walker_parity_repo/` with:
- a `.github/workflows/ci.yml` (divergence #2 trigger)
- a nested subdir with its own `.gitignore` excluding `*.tmp` (divergence #6 trigger)
- a top-level file matching `*.lock` and a basename-only-matching glob test (divergence #3 trigger)
- a file just over `max_file_bytes` (existing behavior — should be skipped on both sides)
- a file matching `**/*.py` deep in the tree (divergence #1 trigger — fnmatch fails on this)
- a top-level `CLAUDE.md` and a `.cursor/rules/sample.mdc` (Phase 125c forward-look —
  source indexing excludes these via `DEFAULT_EXCLUDE_FILE_GLOBS`, but the walker primitive
  itself must handle them correctly when a future caller chooses *not* to exclude them.
  Source-indexing test asserts they're excluded; doc-discovery-style test (caller passes
  `exclude_globs=[]` for these) asserts they appear)

The fixture is git-tracked. Tests run both the Rust walker and the
post-cutover Python coverage, assert byte-for-byte agreement on the
emitted file set.

---

## Migration validation

After the cutover lands, an operator should be able to verify the
self-heal worked correctly with these probes:

```bash
# 1. Pre-deploy: snapshot manifest hash_algo state per project
for dir in ~/.local/share/sourceprep/projects/*/; do
  echo "$dir: $(jq -r '.hash_algo // "absent"' "$dir/trace_manifest.json")"
done

# 2. Deploy Phase 133 + restart daemon

# 3. Trigger a coverage call per project (e.g. via dashboard load,
#    or curl GET /projects/<id>/trace/coverage). The first call after
#    deploy should show all-files-stale in the response.

# 4. The structural rebuild that fires (if fast_sync is auto) or the
#    user's manual rebuild rewrites the manifest with
#    hash_algo: "blake3-128".

# 5. Post-deploy: verify migration completed
for dir in ~/.local/share/sourceprep/projects/*/; do
  echo "$dir: $(jq -r '.hash_algo' "$dir/trace_manifest.json")"
done
# All should print "blake3-128"
```

This is a one-time validation. No CLI sub-command needed (see "Note
on dropped CLI sub-task" in the change manifest above).

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Rust walker behaves slightly differently from Python on a real-world file** the parity tests didn't anticipate | Path A makes "differently" = "marked stale once" = "rebuild fixes it." Cosmetic blast radius only. |
| **PyO3 binding ABI breaks** between dev and prod (e.g. wheels built against different Python minor) | Same risk that already exists for `build_trace` etc. No new exposure. CI pins Python 3.11 per `pyproject.toml`. |
| **`prep_engine` import not available in some test environments** | Existing fallback in `src/prep/core/__init__.py:24-34` ("PREP_ENGINE=rust but prep_engine not installed; falling back to Python"). Coverage path needs an analogous fallback: if `prep_engine.walk_repo` import fails, fall back to a minimal `os.walk` + `pathspec` implementation (NOT `fnmatch` — pathspec is correct, just slower than Rust). Document the fallback as a development-mode safety net, not a production path. |
| **Performance regression** (PyO3 boundary crossing per file is non-trivial) | `walk_repo` returns the full file list in one call (single boundary crossing). `hash_content` is per-file but coverage already iterates per-file in the categorization loop — no extra crossings. If profiling shows hashing is the bottleneck, Phase X (future) adds the `hash_files` batch binding. |
| **Loss of the backfill carve-out** (today: files in `manifest_hashes` but not matching include_globs are still counted) | The carve-out moves up a layer. After `walk_repo` returns the file set, the categorization loop adds: `for path in manifest_hashes: if path not in walked_set and (repo_root / path).exists(): walked_set.add(path)`. Same end result, expressed at the categorization layer instead of the discovery filter. |
| **Hidden-dir behavior change surprises a user** (`.github/workflows/*.yml` suddenly counted as untraced) | Document in the phase changelog. If a user's intent was to exclude these, they add the appropriate exclude glob (which now correctly applies on both sides). The "silent prune" was always a bug, not a feature. |
| **Manifest schema change breaks an external consumer** | Manifest is internal to the daemon; `~/.local/share/sourceprep/projects/<id>/trace_manifest.json` is not a public API. Adding an optional field with a back-compat default is a non-breaking change. |

---

## Rollback story

If the cutover causes user-visible problems and we need to back out:

1. **Code rollback:** revert the Phase 133 commits. The Python `os.walk`
   + `fnmatch` + `stable_file_hash` code is restored exactly.
2. **Data rollback:** existing manifests now have `hash_algo:
   "blake3-128"` and BLAKE3 hashes. Reverted code reads them as
   "absent algo, treat as SHA-256," compares Python SHA-256 against
   stored BLAKE3 → all files mismatch → all files appear stale →
   triggers a rebuild → rebuild rewrites manifest with SHA-256 hashes
   and (because reverted code doesn't write the field) no `hash_algo`.
   Self-healing in both directions.
3. **No data loss.** The `trace_nodes.jsonl` and downstream artifacts
   are unaffected. Only `trace_manifest.json::file_hashes` and
   `hash_algo` rotate.

The bidirectional self-heal is a property of Path A specifically —
this is one of the reasons to prefer it over B/C.

---

## Out-of-scope items flagged for future phases

| Item | Why deferred |
|---|---|
| Migrate watcher's pathspec filter to Rust | The watcher captures *events*, not *file scope*. F-40 already correctness-fixed it. Touching it expands blast radius without solving any reported bug. Track as a Phase 134+ candidate if perf profiling shows watcher startup or per-event cost matters. |
| Bind Rust `hash_files()` parallel batch and use it in coverage | Per-file `hash_content` is fine for normal repo sizes. Profile first; if hashing dominates coverage time on big repos, add the binding then. |
| Migrate `cluster.py`, `embedder.py`, `epistemic_score.py` away from Python `stable_file_hash` | Those uses are content-addressing inside the embedding/clustering pipeline, not compared against Rust output. They're correct as SHA-256-64. No reason to touch them. |
| `trace_nodes.jsonl` schema additions (e.g. embedding the BLAKE3 hash in each node) | This phase keeps the node schema unchanged. Schema changes there require a downstream consumer audit (augmenter, knowledge stage, atlas, etc.) — separate phase. |
| Replacing the `hidden(false)` semantics with the user's actual intent | The current bug (`not d.startswith(".")`) is "ALL hidden dirs pruned." The fix is "only the exclude_globs apply." If a user wants a curated allowlist of hidden dirs that survive (e.g., `.github` yes, `.cache` no), that's a UX feature for a future phase. |
| Rebuilding `tests/test_walker_parity.py` from string-parity to byte-parity (i.e. asserting the Rust walker's *output* against Python's *intended* output, not just the exclude lists agreeing) | This phase does the inverse — Python conforms to Rust. After the cutover, byte-parity is trivially true (Python *is* the Rust walker). The right successor test is "does Python's coverage call exactly match the Rust walker's output for the categorization layer to consume," which is exactly what the new tests do. |
| **Phase 125c doc-discovery walker swap** (third caller migrating to `prep_engine.walk_repo`) | Phase 125c (Quality-Checked Concept Swarm, opened 2026-05-09) needs a walker over `**/*.md` / `**/*.mdc` to feed its Generate-swarm grounding load. It will compose its own tailored exclude set from `repo_profile.DEFAULT_EXCLUDE_DIR_NAMES` *minus* `.claude` / `.cursor` / `.windsurf` / `.github` (those contain agent instructions which are PRIME planning material — opposite policy from source indexing). Deferred to land after this phase so the cutover sequencing stays linear: 125c's T1 ships with a Python walker; the swap to `walk_repo` happens as a follow-up patch once 133 lands. |

---

## Success criteria

The phase is done when:

1. ✅ `compute_trace_coverage` calls `prep_engine.walk_repo` and `prep_engine.hash_content`. The `os.walk` + `fnmatch` + `stable_file_hash` blocks in `coverage.py` are deleted.
2. ✅ `TraceBuilder` writes `hash_algo: "blake3-128"` and BLAKE3 hashes. `_compute_file_hashes` uses `prep_engine.walk_repo` for discovery (Task 4).
3. ✅ The "preserve + merge" defensive logic in `_build_rust` carries the temporary assertion (Task 4b) and is verified to produce zero additions on real fixture repos + the live SourcePrep repo. Deletion of the dead code is deferred to a follow-up patch one release cycle after the assertion ships green.
4. ✅ `tests/test_walker_parity.py` extended with behavior-parity tests over the six divergence surfaces; all green.
5. ✅ New `tests/test_phase133_*.py` files (4 of them per the change manifest) all green.
6. ✅ All existing tests still green (or pre-existing failures documented as not-our-fault).
7. ✅ Daemon restarts cleanly. First coverage call on a pre-cutover manifest shows all-files-stale; structural rebuild rewrites manifest; second coverage call shows fresh state. Verified by the inline `jq` probes in the Migration validation section.
8. ✅ The Phase 132 follow-up dogfooding doc (`docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md`) gets a closing note: "filter divergence root cause closed in Phase 133."
9. ✅ Phase 125c forward-look: the bimodal walker test (Task 5) ships green, proving the walker primitive supports both source-indexing-mode and doc-discovery-mode exclude sets without code changes to the primitive itself.

---

## Cross-references

- **Phase 115 Step 9** — `tests/test_walker_parity.py` baseline (string parity).
- **Phase 96 / F-40** — pathspec.gitwildmatch fix on the watcher; same bug class as
  divergence #1 here.
- **Phase 118 U16 / U19** — `force_from_start` symptom mitigation; this phase removes
  the root cause.
- **Phase 125c (Quality-Checked Concept Swarm)** — opened 2026-05-09. Becomes the third
  caller of `prep_engine.walk_repo` (over `**/*.md` / `**/*.mdc` for doc-grounding). Uses
  a tailored exclude policy (deliberately *includes* AI instruction files like CLAUDE.md
  and `.cursor/rules/*.mdc` that source indexing excludes). 125c's walker swap is
  deferred until after 133 lands; until then 125c uses a Python walker with the same
  composed exclude-set shape so swap is a small follow-up patch.
- **Phase 132 Followup dogfood** — `docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md`
  ("filter divergence is real" finding). Closing note added on completion.

---

## Open questions (none — resolved during brainstorming)

All design decisions were resolved in the brainstorming session. If
new questions arise during implementation, they go in the
`IMPLEMENTATION_PLAN.md` under "Decisions to make during execution"
and not back into this spec.
