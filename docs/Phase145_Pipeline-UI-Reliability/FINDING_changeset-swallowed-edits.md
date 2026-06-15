# Phase 145 Finding — Changeset never reports content edits (daemon-wide)

**Status:** Root-caused + fixed (manifest_store) + finalize hatch added. Backlog needs a one-time force-rebuild.
**Found:** 2026-06-15, dogfooding `SkyPath-Restart`. Confirmed across **all 13 local projects**.
**Severity:** High — silent correctness loss. Content edits to existing files were never re-enriched/finalized, no error, no UI signal.
**Tests:** `test_phase145_provenance_preserves_hash_algo.py`, `test_phase145_changeset_swallow.py`, `test_phase145_finalize_incremental_hatch.py`.

---

## 1. Symptom

Edited Swift source in `SkyPath-Restart` while the daemon was off, reactivated; the pipeline processed only a new markdown file and treated edited source as up-to-date. `git diff` confirmed the edits were real (`ARViewController.swift` +37, `SpikeMenuViewController.swift` +13), yet `changeset.json` had `modified: []`.

Breadth check across every registered project:

```
project            hash_algo   changeset
SourcePrep         None        added=1   modified=0   unchanged=2075
Halley             None        added=2361 modified=0
SkyPath-Restart    None        added=1   modified=0   unchanged=33
… (all 13)         None        modified=0
```

**Every project had `hash_algo: None` and `modified=0`.** Not one content edit, anywhere, ever detected as `modified`.

## 2. Root cause — one writer drops two builder keys

`TraceBuilder._build_manifest` writes `trace_manifest.json` with `built_at` **and** `hash_algo` (builder.py:699, 716). But the structural stage then writes its provenance into the *same file* via `ManifestStore.write_provenance` (STRUCTURAL branch), which merged preserving only:

```python
preserved_keys = ("file_hashes", "config", "file_errors")   # manifest_store.py:124 (before fix)
```

So `hash_algo` and `built_at` were **silently dropped** on every structural run. Consequences:

- **`hash_algo` gone →** `_emit_changeset` reads `prior_algo = None != CURRENT_HASH_ALGO` → takes **Case 3** ("can't compare → trust prior work"): every surviving file → `unchanged`, `modified = {}`. Case 2 (the real hash diff) was **dead code in production**. Content edits never detected.
- **`built_at` gone →** `check_index_staleness` (which read `built_at`) found no build time → the message-1 "always 0 stale" bug.

**One writer, both symptoms.** This is also why the manifest carries `finished_at`/`stage_id`/`elapsed_seconds` (provenance keys) instead of `built_at`.

## 3. The fix

**`manifest_store.py`** — add the two builder-owned keys to the preserved set:

```python
preserved_keys = ("file_hashes", "config", "file_errors", "hash_algo", "built_at")
```

New manifests stay tagged → `_emit_changeset` Case 2 runs → content edits detected → `check_index_staleness` finds `built_at` again. Pinned by `test_phase145_provenance_preserves_hash_algo.py`.

## 4. Why `_emit_changeset` is deliberately NOT changed

It is tempting to make `_emit_changeset` treat an untagged (`None`) prior manifest as the current algo and diff it. **We did not, for two reasons:**

1. **Unsafe.** A genuine pre-Phase-133 manifest is *also* untagged but its `file_hashes` are a different algo (sha256). Diffing it flags *every* file `modified` → the LLM-recall / "everything stale" storm explicitly guarded by `test_phase134_migration_cases.py::test_case3_pre_phase133_manifest_trusts_prior_work`. The dropped-tag case and the genuine-old-algo case are indistinguishable from the field alone.
2. **Useless for the backlog.** Case 3 writes the *fresh* file_hashes to the manifest while marking the file `unchanged`, so an already-swallowed edit leaves the baseline holding the *edited* hash. A later re-diff sees `current == baseline` → still `unchanged`. (Verified on `SkyPath-Restart`: manifest hash already equalled the edited content.)

So untagged manifests keep trusting prior work; the `manifest_store` fix stops new manifests from ever being untagged.

## 5. Backlog recovery (existing swallowed edits)

Already-poisoned baselines can only be cleared by a **one-time force-rebuild per affected project** (`POST /projects/{id}/pipeline/rebuild`, or Rebuild in the UI). Force-from-start routes every file through `added` (not `modified`), so workers reprocess **without** the "everything stale" dashboard flash (per the 2026-05-17 fix). After that, edits are detected normally because the manifest is freshly tagged.

## 6. Secondary bug fixed — Finalize never auto-chains on incremental runs

`run_finalize` lacked the Phase 89 incremental escape hatch that `run_deep_enrichment` has (orchestrator.py:956-970):

- `run_deep_enrichment`: `if resume >= len(stages)` → `if is_incremental: resume = 0`. ✅
- `run_finalize` (before fix): `if resume >= len(FINALIZE_STAGES): return False` unconditionally. ❌

So after an incremental deep run, finalize saw its 5 manifests present and bailed — atlas/rules/concepts/audit/antibodies never incorporated new/changed files, even with `auto_config.finalize=="auto"`. Confirmed via journal: `SkyPath-Restart` ran `fast_sync → deep_enrichment` twice on 2026-06-15 but no `finalize` since 2026-05-18.

**Fix:** new `PipelineOrchestrator._finalize_has_incremental_work(project_id)` reads the changeset (`cs.added or cs.modified`); `run_finalize` resets `resume=0` when it returns True. Loop-safe: the changeset only refreshes on the next structural run, finalize is only triggered by a deep completion (or explicit request), and finalize workers are idempotent via `should_process`. Pinned by `test_phase145_finalize_incremental_hatch.py`.

> Ordering: this is downstream of §2. With manifests now tagged, edited files reach `modified`, deep enrichment processes them, and the finalize hatch carries them through finalize.

## 7. Related: the mtime staleness tripwire (`check_index_staleness`)

`check_index_staleness` did an mtime-vs-build-time check independent of the changeset, but read the dropped `built_at` key. Two-part remediation: (a) `built_at` is now preserved (§3), and (b) a defensive `finished_at`/`started_at` fallback was added (`test_index_staleness.py::test_trace_manifest_finished_at_detects_stale`). In this incident the mtime check said "stale" while the changeset said "unchanged" — and `git` proved mtime right; it's a genuine independent tripwire worth keeping.

## 8. Reproduction

- **Unit (deterministic):**
  - `test_phase145_provenance_preserves_hash_algo.py` — the dropped-key root cause.
  - `test_phase145_changeset_swallow.py` — Case 2 happy path (restored) + the documented trust-prior limitations.
  - `test_phase145_finalize_incremental_hatch.py` — the finalize hatch.
- **Breadth check (live):**
  ```bash
  # every project's manifest hash_algo + changeset modified count
  python3 - <<'PY'
  import json, sqlite3, os
  from pathlib import Path
  con=sqlite3.connect(os.path.expanduser('~/.local/share/sourceprep/registry.db'))
  for pid,name,path,mode in con.execute("SELECT id,name,path,mode FROM projects"):
      idx=(Path(path)/".sourceprep") if mode=="embedded" else Path(os.path.expanduser('~/.local/share/sourceprep/projects'))/pid
      m=idx/"trace_manifest.json"; c=idx/"changeset.json"
      algo=json.loads(m.read_text()).get("hash_algo") if m.exists() else "—"
      mod=len(json.loads(c.read_text()).get("modified",[])) if c.exists() else "—"
      print(f"{name:20} hash_algo={algo} modified={mod}")
  PY
  ```
  Before the fix: all `hash_algo=None`. After the fix + one structural run per project: tagged, and edits show up in `modified`.
