# 00 — The Problem

**Phase:** 115 — Filter Universality & Self-Ingestion Prevention
**Drafted:** 2026-04-17
**Status:** Drafting (evidence captured, fix not yet written)

## TL;DR

Prep's Deep Reasoning stage just spent the night reasoning over storybook-static, node_modules-adjacent build output, and a sea of `.d.ts` declaration files. The filter pipeline *exists* — it's layered (L1 code defaults, L2 repo_policy.json, L3 trace.ignore_patterns) and is *merged at most callsites* — but it has four concrete bugs that collectively defeat universality:

1. **`repo_policy.json` was baked at project-create time** (2026-04-11) with a directory default list that had no entry for `storybook-static`, `prep_data/**`, `coverage`, `out`, `.turbo`, `.vercel`, etc. New defaults added to the code later are **not** back-propagated — the auto-migrate in `ensure_repo_policy()` only unions **dir-derived** globs, not the `DEFAULT_EXCLUDE_FILE_GLOBS` sequence.
2. **`TraceBuilder` has a hardcoded include/exclude list** (`trace/builder.py:66-85`) that shadows whatever `repo_policy.json` says when a caller doesn't pass `include_globs` explicitly.
3. **`epistemic_enrichment.load_trace_nodes()`** slurps every node from `trace_nodes.jsonl` with **no filter applied**. Even if a rebuild correctly excluded a path, a later enrichment pass pulls it back in.
4. **Rust walker defaults have drifted.** `prep-walker/src/lib.rs:89-98` lists only 8 exclude globs against Python's 35+. Rust-path consumers (selfheal) also don't read L3 (`trace.ignore_patterns`) at all.

On top of those, Prep **ingests its own outputs**. `prep_data/` (daemon-wide SQLite + JSON logs + telemetry) sits at the repo root, isn't in `.gitignore`, and isn't in the default dir-name set. The only thing pushing it out of trace is a single file-glob (`**/prep_data/ui_config.json`). Everything else under `prep_data/` is fair game for indexing.

## Evidence

### E1 — Deep Reasoning just ingested storybook-static

`run-3639f940ba9f` (in flight at time of writing, stage `group_reasoning` 95% complete). Pipeline status telemetry lists these in `synthetic_reasons.batch_parse_failure`:

```
packages/ui/storybook-static/assets/arrow-right-D76xP_m8.js
packages/ui/storybook-static/assets/arrow-up-Bo7eO7DF.js
packages/ui/storybook-static/assets/book-open-C_TI0RTe.js
packages/ui/storybook-static/assets/bot-DhdZiCgD.js
packages/ui/storybook-static/assets/check-circle-DKmRqjAp.js
packages/ui/storybook-static/assets/chevron-down-xFIJM9ow.js
packages/ui/storybook-static/assets/chevron-right-DQeNUO3R.js
packages/ui/storybook-static/assets/chevron-up-DoCq2bXV.js
packages/ui/storybook-static/assets/cloud-D8Qet7Wb.js
packages/ui/storybook-static/assets/cloud-off-Do-d761c.js
packages/ui/storybook-static/assets/code-2-DCUEONsE.js
packages/ui/storybook-static/assets/copy-CiFpBFcK.js
packages/ui/storybook-static/assets/minus-Bd4yRTqW.js
packages/ui/storybook-static/assets/network-DpFqDBNx.js
packages/ui/storybook-static/assets/play-BfQA5A_j.js
packages/ui/storybook-static/assets/plus-B0ZBLhon.js
packages/ui/storybook-static/components/llm/EndpointManager.d.ts
packages/ui/storybook-static/components/llm/LLMAssignmentBlockCard.d.ts
packages/ui/storybook-static/components/llm/LLMAssignmentsPipeline.d.ts
packages/ui/storybook-static/components/llm/ModelCard.d.ts
packages/ui/storybook-static/components/team/ServerModeIndicator.d.ts
packages/ui/storybook-static/components/team/SyncStatusCard.d.ts
packages/ui/storybook-static/components/team/TeamConfigStatus.d.ts
packages/ui/storybook-static/components/team/TeamSyncIndicator.d.ts
```

These are a storybook build-output artifact — minified bundled JS chunks and bundler-generated `.d.ts` files. Not source. The LLM is burning context window reasoning about `arrow-right-D76xP_m8.js`.

### E2 — The current repo_policy excludes list, verbatim

`/Volumes/4TB-BAD/HumanAI/Prep/.prep/repo_policy.json` (created 2026-04-11):

```json
"exclude_globs": [
  "**/*.lock", "**/*.log", "**/.*", "**/.DS_Store",
  "**/.aider/**", "**/.bundle/**", "**/.cache/**",
  "**/.claude/**", "**/.prep/**", "**/.cody/**",
  "**/.continue/**", "**/.coverage/**", "**/.cursor/**",
  "**/.env/**", "**/.git/**", "**/.gradle/**",
  "**/.mypy_cache/**", "**/.next/**", "**/.pytest_cache/**",
  "**/.ruff_cache/**", "**/.tox/**", "**/.venv/**",
  "**/.windsurf/**", "**/Carthage/**", "**/DerivedData/**",
  "**/Pods/**", "**/__pycache__/**", "**/bower_components/**",
  "**/build/**", "**/bundle/**", "**/dist/**", "**/env/**",
  "**/fresh_venv/**", "**/htmlcov/**", "**/node_modules/**",
  "**/target/**", "**/vendor/**", "**/venv/**"
]
```

Missing (any of which would have caught the E1 files):

- `**/storybook-static/**`
- `**/prep_data/**`
- `**/coverage/**`
- `**/out/**`
- `**/.turbo/**`
- `**/.vercel/**`
- `**/.parcel-cache/**`
- `**/.svelte-kit/**`
- `**/.astro/**`
- `**/.nuxt/**`
- `**/*.d.ts` (file glob — not dir)
- `**/*.min.*`
- `**/*.map`

### E3 — include_globs quietly dropped `.js` and `.jsx`

Same `repo_policy.json`:

```json
"include_globs": [
  "**/*.bash", "**/*.c", "**/*.cc", "**/*.cpp",
  "**/*.go", "**/*.h", "**/*.hpp", "**/*.kt",
  "**/*.kts", "**/*.markdown", "**/*.md",
  "**/*.py", "**/*.rs", "**/*.rst", "**/*.sh",
  "**/*.swift", "**/*.ts", "**/*.tsx", "**/*.zsh"
]
```

No `.js` / `.jsx`. This is because `profile_repo()` (`repo_profile.py:400-401`) only adds `.js`/`.jsx` when `"javascript"` is in `detected_languages`, and TypeScript wins that detection branch (`repo_profile.py:336-339`). For the dogfood repo that's arguably correct — but then E1 shows `.js` files being reasoned over anyway. **So the include list is not the filter that matters at the Deep Reasoning stage**; something downstream is bypassing it. See F4.

## The four bugs

### F1 — `ensure_repo_policy` auto-merges dir globs but not file globs

`core/repo_policy.py:151-163`:

```python
current_excludes = set(_normalize_globs(existing.get("exclude_globs")))
# Construct default globs from the centralized list
default_excludes = {f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES}
default_excludes.add("**/.*")

# Merge defaults if missing
if not default_excludes.issubset(current_excludes):
    existing["exclude_globs"] = sorted(list(current_excludes | default_excludes))
    write_repo_policy(path, existing)
```

Only `DEFAULT_EXCLUDE_DIR_NAMES` is auto-unioned. `DEFAULT_EXCLUDE_FILE_GLOBS` (the `AGENTS.md`, `CLAUDE.md`, `prep_data/ui_config.json` list) is *never* merged into an existing policy. New file-glob entries we add to the Python source will not reach an old project without a forced re-profile.

**Fix:** extend auto-merge to include `DEFAULT_EXCLUDE_FILE_GLOBS`.

### F2 — `TraceBuilder` has a hardcoded include/exclude list

`core/trace/builder.py:66-100`:

```python
self.include_globs = include_globs or [
    "**/*.py",
    "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
    "**/*.go",
    ...
]

if exclude_globs is None:
    exclude_globs = [f"**/{d}/**" for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES)]
    exclude_globs.append("**/.*")
    exclude_globs.extend(["**/*.lock", "**/*.log", "**/.DS_Store"])
    exclude_globs.extend(DEFAULT_EXCLUDE_FILE_GLOBS)
```

Two problems:

- The include list is **different** from what `profile_repo()` produces (this one unconditionally includes `.js`/`.jsx`, which is why E1's `.js` files slip through even though `repo_policy.json` doesn't list them).
- Callers that don't pass explicit globs get the hardcoded list. So the canonical source of truth is *not* `repo_policy.json`; it's whichever of the two lists the caller happens to hit.

**Fix:** remove the hardcoded defaults. `TraceBuilder` must load from `repo_policy.json` (via `ensure_repo_policy`) or accept explicit globs. No silent third list.

### F3 — `epistemic_enrichment.load_trace_nodes()` has no filter

From `core/epistemic_enrichment.py:290-300` (per prior audit): `load_trace_nodes()` reads every line of `trace_nodes.jsonl` and returns it. Even if `TraceBuilder` had excluded a path correctly in a prior run, a subsequent enrichment pass would still consider it — **and** a path that entered `trace_nodes.jsonl` via any earlier bypass remains on disk forever until wiped.

**Fix:** `load_trace_nodes()` must apply the same `_is_relevant()` check that `TraceBuilder` applies during the walk, with all three filter layers unioned.

### F4 — Rust walker defaults drifted + Rust selfheal skips L3

`engine/crates/prep-walker/src/lib.rs:89-98`, `WalkConfig::default().exclude_globs`:

```rust
exclude_globs: vec![
    "**/node_modules/**".into(),
    "**/.git/**".into(),
    "**/venv/**".into(),
    "**/.venv/**".into(),
    "**/__pycache__/**".into(),
    "**/dist/**".into(),
    "**/build/**".into(),
    "**/target/**".into(),
],
```

Eight entries. Python has 35+. The Rust walker is what fast-path indexing uses. It's also what Rust selfheal uses. Selfheal (`prep-selfheal/src/main.rs:93-103`) reads `repo_policy.json.exclude_globs` and unions with Rust defaults, but **never** reads `project.config.trace.ignore_patterns` (L3 — the user's Knowledge Scope / FolderTree exclusions).

**Fix:**
- Sync Rust walker defaults with the Python canonical list (single source of truth, via a shared JSON or generator).
- Rust selfheal must read L3 and union it into exclude_globs before walking.

## The self-ingestion problem

Prep writes files. Many of them. Top-level outputs today:

| Path | Writer | Currently excluded? |
|------|--------|---------------------|
| `.prep/**` | Per-project index | Yes (`**/.prep/**`) |
| `prep_data/*.db` | Daemon SQLite stores | **No** |
| `prep_data/*.json` (roster, telemetry, etc.) | Daemon state | Partially (`ui_config.json` only) |
| `prep_data/logs/*.log` | Daemon logs | Via `**/*.log` glob, but not dir |
| `AGENTS.md` | `rules_generator.py` | Yes (in DEFAULT_EXCLUDE_FILE_GLOBS) |
| `CLAUDE.md` | User-authored + Prep-managed block | Yes |
| `.cursor/rules/*.mdc` | Per-IDE writers | Yes |

`prep_data/` is the glaring gap. It's also the daemon-wide store — on the same machine, every project shares it. Indexing it produces a feedback loop: the SQLite journal tables describe every pipeline run; indexing them teaches the LLM about the indexer, not about the repo.

The fix is a central registry — `PREP_OUTPUT_DIRS` and `PREP_OUTPUT_FILE_GLOBS` in `repo_profile.py` — from which `DEFAULT_EXCLUDE_DIR_NAMES` and `DEFAULT_EXCLUDE_FILE_GLOBS` derive. Any new output Prep adds must be added to the registry; the excludes update automatically. A self-ingestion test (Step 11) guards the invariant.

## Why this is worse than "just a bug"

Three compounding reasons:

- **Universality.** Every Prep user's project has the same issue. The dogfood repo is the canary but fixing the dogfood copy's `repo_policy.json` by hand helps nobody else.
- **Cost.** Deep Reasoning is LLM-cost-bound. Every `.d.ts` slurped is $ paid for a batch parse failure. The failure rate in E1 is roughly 100%: LLMs cannot structurally reason about bundler output.
- **Retroactivity.** Once a bad path enters `trace_nodes.jsonl`, every downstream stage (enrichment, clustering, atlas) re-reads it. A single leak cascades into all 10 Deep Enrichment + Finalize stages.

## Out of scope for this phase

- Changing the *content* of include/exclude lists per-language-preset (presets are fine).
- Reorganizing `.prep/` internals (that is Phase 113).
- Moving `prep_data/` to `~/.local/share/prep/` (tracked separately; strengthens tier enforcement but independent of filter correctness).
- UI changes to the Knowledge Scope / FolderTree.

## Acceptance gates for Phase 115

1. `DEFAULT_EXCLUDE_DIR_NAMES` and `DEFAULT_EXCLUDE_FILE_GLOBS` both derive from a central `PREP_OUTPUT_*` registry.
2. Adding a new output directory in the registry and running a rebuild excludes it from trace without any other code change.
3. `ensure_repo_policy()` back-fills new default excludes (both dirs and file globs) into existing `repo_policy.json` on daemon start.
4. `TraceBuilder` has no hardcoded include/exclude list; it loads from the policy.
5. `epistemic_enrichment.load_trace_nodes()` applies the three-layer filter; no trace node that was excluded by the walk can be re-introduced by enrichment.
6. Rust walker's `WalkConfig::default().exclude_globs` is a superset of the Python-derived dir-exclude globs (parity test).
7. Rust selfheal unions `trace.ignore_patterns` into its walk config.
8. A rebuild of the dogfood repo produces zero `storybook-static/**`, `prep_data/**`, or `**/*.d.ts` paths in `trace_nodes.jsonl` (integration test).
9. No path matching `PREP_OUTPUT_DIRS` appears in `trace_nodes.jsonl` after a full rebuild (regression test).
