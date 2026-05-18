# Part 02 — Implementation strategy (tactical playbook)

> **Companion to:** `IMPLEMENTATION_PLAN.md` (the design spec)
> **Status:** **BLOCKED 2026-05-17** — implementation surfaced a worse
> diagnosis than the original spec; the real bug is upstream of the
> handler/index layer.  Code changes reverted.  Strategy revised below.
> **Goal:** ship a working fix for the prep_impact undercount end-to-end
> (code + tests + live MCP probe verification) in a single session.

## 2026-05-17 corrected diagnosis

Implementation attempt against the live `.sourceprep/` index returned
results that **falsified the original "bimodal-node twins" diagnosis**.
Live evidence:

1. **No `external_module` twins exist for Python files in the current
   graph.** `idx.search_nodes("prep.core.augmenter", kind="external_module")`
   → empty.  The external_module nodes that DO exist are CSS / JS
   frontend imports (`./globals.css`, `./DesignSystem.css`, etc.) — not
   Python module twins.
2. **`augmenter.py` only has 23 in-edges total: 2 `imports`, 21
   `references`.** Not 4-vs-29 with mixed kinds; the structural
   `imports` count is genuinely tiny.
3. **The two captured Python importers (`__init__.py`,
   `epistemic_enrichment.py`) both use TOP-LEVEL relative imports**
   (`from .augmenter import X` at module scope).
4. **`deep_analysis.py` does `from .augmenter import AugmentationEntry`
   at lines 192 and 312 — both INDENTED inside method bodies.** No edge
   captured. Confirmed by inspecting its out-edges (25 total, zero
   pointing at augmenter).
5. **Test files have ZERO out-edges.** `tests/test_augmenter.py`,
   `tests/test_batch_e2e.py`, `tests/test_phase134_stage_cutover.py`
   all show 0 out-edges. Imports inside `tests/` aren't being indexed
   at all.

## What the real bug is — DEFINITIVE DIAGNOSIS 2026-05-17/18

After deep code investigation: **one real parser bug + one config
finding + the original twin theory is dead.**

### REAL BUG — Indented imports dropped (Gap A)

Located in `engine/crates/prep-parser/src/python.rs:42-63`:

```rust
// Walk top-level children
let mut cursor = root_node.walk();
for child in root_node.children(&mut cursor) {
    match child.kind() {
        "function_definition" => extract_function(...),
        "class_definition" => extract_class(...),
        "import_statement" => extract_import(...),
        "import_from_statement" => extract_import_from(...),
        _ => {}
    }
}
```

The Rust tree-sitter walker iterates only direct children of the
module root. `extract_function` (line 123-198) emits a `contains`
edge to the symbol but **never walks the function body**.
`extract_class` (line 200-315) walks the class body but only for
nested `function_definition` / `decorated_definition` — not for
imports.

**Result:** any `import` or `from X import Y` nested inside a
function, method, conditional, or `if TYPE_CHECKING:` block is
silently dropped from the trace graph.

Verified by direct probe: `deep_analysis.py:192` has
`from .augmenter import AugmentationEntry` indented inside a method —
the Python-side fallback analyzer (`python_analyzer.py:144 ast.walk`)
captures it correctly, but the Rust parser misses it. Live graph
confirms: zero `imports` edges from `deep_analysis.py` to
`augmenter.py` exist on disk despite the source code clearly
importing it.

### NOT A BUG — Tests excluded by user config (Gap B reclassified)

Tests files have 0 nodes/edges in the graph not because of a parser
issue but because the project's stored config has:

```
project.config["trace"]["ignore_patterns"] = [
    "tests", "tests/**",
    "src/codrag", "src/codrag/**",  ← stale, legacy codename
    "scripts", "scripts/**",
    "tmp", "tmp/**", "logs", "logs/**",
    "overnight_results", "overnight_results/**",
    "websites/MagneticAnomaly", "websites/MagneticAnomaly/**",
    "websites/LLC-Docs", "websites/LLC-Docs/**",
    "websites/trash", "websites/trash/**",
]
project.config["exclude_globs"] += ["**/tests/**"]
```

These are user-configured exclusions in the Exclude Tree / Patterns
settings tab. The `src/codrag` entries are stale (legacy codename
that no longer exists in the tree post-rename). Cleaning those is a
trivial config edit, not a code change.

**This Part will NOT include tests in the graph** — that's a deliberate
choice, not a bug. If the user wants tests indexed, they remove the
`tests` pattern from the Exclude Tree.

### FALSIFIED — Bimodal-node twins (original spec)

The original Part 02 spec assumed Python files appeared as both a
`file:` node and an `external_module` twin (with empty `file_path`).
The current graph contains **zero Python external_module twins** —
`search_nodes("prep.core.augmenter", kind="external_module")` returns
empty. The 2026-05-11 baseline that observed twins is no longer
reproducible after the Phase 134/135 changeset-driven rebuild.

The original diagnosis is dead. The new diagnosis (indented imports)
explains the same observed symptom (undercount of Python importers)
through a different and verified mechanism.

## What was tried and reverted

Implementation that landed and then was reverted (HEAD restored on
`src/prep/core/trace/index.py`):

- `_path_to_dotted_module` / `_dotted_to_path` helpers
- `_find_node_twins` (engine-agnostic via `search_nodes` / `get_node`)
- `get_impact_graph` BFS multi-seed + file-path dedup

The code itself is correct and defensible (verified twin-discovery
logic against a synthetic case; dedup is sound). It just **does
nothing** on the current graph because the assumed twins don't
exist. Adding 120 LOC for a non-bug is overengineering. Better to
diagnose the real cause first.

## Revised path forward

Three sub-investigations needed before any code lands:

### Sub-investigation A — Indented import capture

- Find the Rust parser stage that emits `imports` edges
  (`engine/crates/prep-parser/` likely).
- Determine whether the AST walker visits function bodies or stops
  at top-level statements.
- If it stops: extend the walker to recurse into nested scopes;
  emit `imports` edges from any `Import` / `ImportFrom` AST node
  regardless of nesting.
- Cost: probably contained, but it's a Rust-side change.

### Sub-investigation B — Test indexing

- Verify `repo_policy.json` or walker include/exclude config doesn't
  blacklist `tests/`.
- Verify the trace-builder doesn't have a separate "skip tests"
  policy when emitting edges (it may index them as file nodes but
  skip parsing).
- If a deliberate exclusion, decide: do we want test files'
  imports as edges? (Yes — `prep_impact` should show that
  `tests/test_X.py` depends on `src/prep/X.py`.)

### Sub-investigation C — Verify twin status

- After fixing A and B, re-probe `augmenter.py`. If dependents
  jump to the expected count (~10+ Python files), the original
  Part 02 bimodal-node theory was either wrong or
  superseded — no twin-aggregation fix needed.
- If a gap remains, run a new survey: are there ANY Python
  external_module twins anywhere in the graph? `search_nodes('',
  kind='external_module', limit=500)` and grep for dotted-name
  shapes.

## Step ledger (revised 2026-05-18)

| # | Step | Verification | Status |
|---|---|---|---|
| 0 | Confirm root cause against the live trace graph | observe `prep.core.augmenter` external_module node alongside `file:src/prep/core/augmenter.py` | ❌ **falsified** — no external_module twin exists in current graph |
| 0a | Confirm REAL bug: Rust parser drops indented imports | `python.rs:42-63` walks only root children; `extract_function` never recurses into body | ✅ confirmed via code read |
| 0b | Confirm tests-absence is config, not parser | `project.config["trace"]["ignore_patterns"]` lists `"tests", "tests/**"` (also stale `src/codrag`) | ✅ confirmed via daemon registry probe |
| 1 | Implement `extract_all_imports` recursive helper in `python.rs` | unit test in Rust crate: indented `from .X import Y` produces an edge | ⬜ |
| 2 | Replace top-level-only walk with the recursive helper | existing tests in `prep-parser/tests/` continue to pass | ⬜ |
| 3 | Rebuild Rust binding (`maturin develop`) and restart daemon | `prep` MCP server reconnects | ⬜ |
| 4 | Live MCP probe: `prep_impact augmenter.py dependents` shows `deep_analysis.py` and other indented importers | dependent count rises from 2 Python → ≥4 Python | ⬜ |
| 5 | Audit project config — clean up stale `src/codrag` entries from `trace.ignore_patterns` (out of code scope; user action) | settings UI Exclude Tree edit | ⬜ |
| 6 | Verify P122-D3 not-indexed header still works (already landed in `server.py`) | unchanged, sanity check | ⬜ |

## Rollback completed

Reverted: `src/prep/core/trace/index.py` (`git checkout`). 0 LOC of
Part-02 code remains in the working tree as of 2026-05-17 17:30 PT.
The P122-D3 cosmetic fix at `server.py:1744-1761` stays — that's a
genuine, verified improvement.

## Lessons (process notes)

- The IMPLEMENTATION_PLAN.md spec was based on the 2026-05-11
  baseline. Six days later, the Phase 134/135 rebuild changed the
  graph schema. The spec wasn't re-verified against the current
  graph before implementation started.
- Always re-run the dogfood probe DURING implementation, not just
  at the start of the phase. Plans grow stale faster than expected.
- The implementation work was small (~120 LOC) and the revert was
  clean — this iteration cost was acceptable. If the change had
  been larger or harder to revert, the cost of trusting an outdated
  spec would have been much higher.


## Why this doc

`IMPLEMENTATION_PLAN.md` is the design — what we're building and why.
This doc is the tactical execution — the ordered sequence of steps,
each with an explicit verification gate.  Update this doc as steps
land so the next session (or a reviewer) can see exactly where the
work stopped.

## Step ledger

| # | Step | Verification | Status |
|---|---|---|---|
| 0 | Confirm root cause against the live trace graph | observe `prep.core.augmenter` external_module node alongside `file:src/prep/core/augmenter.py` | ✅ confirmed 2026-05-17 (probe in `00_Status_2026-05-17.md`) |
| 1 | Add `_path_to_dotted_module` helper to `TraceIndex` | unit test: `_path_to_dotted_module("src/prep/core/augmenter.py") == "prep.core.augmenter"` | ⬜ |
| 2 | Add `_dotted_to_path` helper to `TraceIndex` | unit test: round-trip on a graph that has both node twins | ⬜ |
| 3 | Add `_find_node_twins(node_id) -> list[str]` to `TraceIndex` | unit test: given a graph with both twins, returns both ids | ⬜ |
| 4 | Modify `get_impact_graph` to BFS-seed from ALL twins | unit test on fixture: `from pkg.a import foo` from `consumer.py` shows up as dependent of `pkg/a.py` | ⬜ |
| 5 | Add file-path dedup so a dependent reachable via both twins counts once | unit test: no duplicate file_paths in result | ⬜ |
| 6 | Live MCP probe — `prep_impact augmenter.py dependents` shows real Python importers, not just `__init__.py` and `epistemic_enrichment.py` | post-fix probe pastes more Python dependents than 2026-05-17 baseline | ⬜ |
| 7 | Verify P122-D3 "not indexed" header path (already landed) still produces the explicit message on unindexed inputs | dispatch via `prep_impact(file_path="nonexistent.py")` returns the explicit indicator | ⬜ |

## Step 1 — `_path_to_dotted_module`

**Goal:** translate a file path under `src/` (Python convention) into
its dotted module name as used by `external_module` graph nodes.

**Edge cases to handle:**
- Non-Python files → return None
- `__init__.py` files → drop the `__init__` segment (e.g.
  `src/prep/core/__init__.py` → `prep.core`)
- Files outside `src/` → still attempt (some scripts live at repo root)
- Leading slashes / Windows paths → normalize to `/`-separated

**Implementation:** ~10 LOC, pure function, no side effects.

**Verification:** add a unit test in `tests/test_trace_node_twins.py`
covering the four edge cases above plus the canonical case.

## Step 2 — `_dotted_to_path`

**Goal:** given a dotted module name, find the file: node id that
corresponds, if any.

**Strategy:** probe candidate paths in order — `src/<rel>.py`,
`<rel>.py`, `src/<rel>/__init__.py` — and return the first that
exists in `self._nodes` (which requires `self.load()` to have run).
Returns `None` if no twin exists in the graph.

**Why probe rather than reverse the construction:** the trace graph
doesn't carry a metadata field linking external_module → file_path.
The dotted name is the only signal; we have to search.

**Cost note:** this is called from `_find_node_twins` which is itself
called from `get_impact_graph`.  At most three dict lookups per call —
cheap.

## Step 3 — `_find_node_twins`

**Goal:** given an arbitrary node_id (either `file:X.py` or a dotted
external_module name), return a list of all twin node_ids that exist
in the graph.

**Cases:**
1. `node_id` starts with `file:` AND `_path_to_dotted_module` returns
   a non-None dotted name AND that name appears as the `name` field
   of an `external_module` node → return both node_ids
2. `node_id` is the name of an `external_module` node (no `file:`
   prefix) AND `_dotted_to_path` returns a path that exists as a
   `file:` node → return both node_ids
3. Otherwise → return `[node_id]` alone

**Cost note:** Case 1 currently iterates `self._nodes.items()` to
find the external_module match.  For 28k-node graphs that's ~28k
dict iterations per call.  Acceptable for now; flag a follow-up
to cache an `external_module_by_name` dict at load time if profiling
shows this hot.

## Step 4 — `get_impact_graph` multi-seed BFS

**Change:** instead of seeding the BFS with one node_id, seed it with
the full list from `_find_node_twins(node_id)`.  Mark all twins as
visited initially so the BFS doesn't reach one twin from the other
twin (which would generate a self-loop).

**Subtle correctness point:** the BFS already deduplicates nodes by
adding to `visited`.  But two twins of one file are two DIFFERENT
nodes with different ids — both have to be in `visited` from the
start to prevent traversal between them.

## Step 5 — File-path dedup

**Why needed:** if `consumer.py` has both `from pkg.a import foo`
AND `import pkg.a` (two different import shapes targeting the same
file), it shows up as two distinct edges — one to `file:pkg/a.py`,
one to `pkg.a` (external_module).  BFS-from-both-twins would visit
`consumer.py` twice, producing duplicate entries.

**Fix:** maintain `seen_files: set[str]` keyed by `dep_info["path"]`.
Skip duplicates after the first.  Order-preserving (first edge wins).

## Step 6 — Live MCP probe verification

**Pre-fix baseline (2026-05-17, from `00_Status_2026-05-17.md`):**

```
prep_impact src/prep/core/augmenter.py dependents
→ 14 direct dependents:
    src/prep/core/__init__.py [imports]
    src/prep/core/epistemic_enrichment.py [imports]
    + 12 markdown docs [references]
```

**Post-fix expected:** at least these additional Python files appear:
- `src/prep/core/index.py`
- `src/prep/services/pipeline/orchestrator.py` (or similar pipeline path)
- `src/prep/services/pipeline/workers/__init__.py`
- some tests under `tests/`

If any are missing, the fix is incomplete — investigate which
import shape lands which edge somewhere else and adjust
`_find_node_twins` accordingly.

## Step 7 — P122-D3 verification

The empty-parens cosmetic fix at `src/prep/mcp/server.py:1744-1761`
already landed earlier this session.  After the trace-index fix,
re-test the "not indexed" path against a path that doesn't exist
in the graph — should produce `Impact analysis: <id> — node not
found in trace graph` instead of `Impact analysis for:  ()`.

## Out of scope (deliberately deferred)

- **Index-time twin unification.** A cleaner fix would be to collapse
  the twins at graph-build time.  Bigger refactor.  Not needed to
  close the dogfood finding.
- **Symmetric fix for `tool_trace_neighbors`.** If that handler uses
  a different code path and has the same bug, add as a follow-up
  Part — out of scope here.
- **External_module-name index cache.** Performance optimization
  noted in Step 3.  Defer until profiling shows it matters.

## Rollback plan

All changes are additive: new helpers + a modified `get_impact_graph`.
If the fix produces over-counts or causes test failures in
`test_trace_search.py` / `test_impact_smoke.py`, revert the three
files in `src/prep/core/trace/index.py` to HEAD.  No data on disk
changes; no migration concerns.
