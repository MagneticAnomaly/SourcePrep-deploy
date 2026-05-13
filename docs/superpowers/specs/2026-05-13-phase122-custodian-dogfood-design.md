# Phase 122 — Custodian Dogfood Design

**Status:** Spec (awaiting user review)
**Date:** 2026-05-13
**Phase:** 122 — Feature Utilization Audit (continuation)
**Prior art:** `docs/Phase122_FeatureUtilizationAudit/README.md`

---

## 1. Context & motivation

Phase 122 was scaffolded on 2026-04-30 with nine tasks (T1–T9). Between
then and now, two things changed:

1. **T4 (wire `spaghetti_scorer` into the audit worker) shipped under Phase 124 T5**
   (`src/prep/services/pipeline/workers.py:1397-1515`). The headline
   WIRE-UP proof-of-concept is complete.
2. **A production "discover unwired code" pipeline already exists**:
   `src/prep/agents/custodian/engine.py` — a discover → verify → plan →
   (optional) execute → report pipeline with an LLM safety verifier and
   an archive manifest. It is wired at
   `POST /projects/{project_id}/agents/custodian/run`
   (`src/prep/api/routers/agents.py:316`). A Phase-122-anchored concept
   captures the design intent: *"LLM-based safety verification replaces
   missing static analysis because 'unwired' features evade traditional
   dead code detection."*

This spec scopes the remaining Phase 122 work to **finish the triage of
the 11 pending modules** in `docs/INTENTIONALLY_DORMANT.md` by
**dogfooding the existing Custodian engine** rather than building a
static-analysis script that would compete with it (the original T1).

The dogfood pass also exercises a real product bug surfaced during
planning — `prep_impact` returns `0 dependents` for every module under
`src/prep/core/` that is consumed via `from prep.core.X import Y`,
including `__init__.py` itself. That bug is filed separately
(`MASTER_TODO.md` P122-D1/D2/D3); this phase works around it by
relying on LLM verification + human grep confirmation.

## 2. Scope

### In scope
- Run the existing Custodian engine against the 11 candidate modules
  under "Other modules under audit" in `docs/INTENTIONALLY_DORMANT.md`
  that still need a decision. The list is: `roadmap_miner.py`,
  `treatment_registry.py`, `swarm_optimizer.py`, `lod_extractor.py`,
  `github_sync.py`, `budget_enforcement.py`, `chunking.py`,
  `inferred_edges.py`, `batch_profiles.py`, `swarm_registry.py`,
  `context_config.py`. (The three entries already marked WIRED —
  `antibody_derivation.py`, `rules_generator.py`, `concept_seeder.py` —
  are out of scope and will be cleaned out of the registry as part of
  this pass.)
- Triage each module to a decision (WIRED / KEEP-DORMANT / NEEDS-OWNER /
  DEPRECATE / DELETE) and record the decision in
  `docs/INTENTIONALLY_DORMANT.md`.
- For DEPRECATE / DELETE / NEEDS-OWNER modules, add a tracker line to
  `docs/MASTER_TODO.md`.
- Capture the Custodian run log to disk for future reference.
- Surface the `prep_impact` dogfood bug (already done — kept here for
  cross-reference).

### Out of scope (deferred / handled elsewhere)
- **Executing** any deletion, wiring, or deprecation. Each downstream
  action is owned by whichever phase picks it up from
  `MASTER_TODO.md`. Decisions-only.
- Building a static-analysis script (`tools/feature_audit.py` from the
  original T1). The Custodian's LLM verifier is the canonical answer
  to the "dead-code" question per the existing design concept.
- Adding new `prep_audit` analyzers or new audit categories.
- The FastAPI route audit (279 routes) and Storybook story audit
  (79 stories) — original T8/T9, deferred to a follow-up phase.
- Fixing the `prep_impact` bug itself (filed as P122-D1/D2/D3, not
  closed by this phase).

## 3. Approach (Section A — Custodian invocation)

A small driver script at `tools/phase122_custodian_run.py` (~40 LoC)
imports `CustodianEngine` directly. The REST endpoint is unsuitable
because it pulls findings from disk via `_get_audit_findings`, and
today's `prep_audit` does not emit findings with the categories the
Custodian filters for (`dead_code` / `orphan` / `deprecated` /
`unused_export`). We feed the Custodian a hand-built findings list
synthesized from `INTENTIONALLY_DORMANT.md`.

```python
findings = [
    {
        "id": "P122-roadmap_miner",
        "category": "dead_code",
        "affected_files": ["src/prep/core/roadmap_miner.py"],
        "description": "Phase 119 recon: no external imports detected; "
                       "needs LLM verification.",
    },
    # ... one per pending candidate
]
plan = engine.run(findings, llm_fn, dry_run=True)
```

**Inputs:**
- `project_id`: `f1636374-abc6-410d-99ee-822120379e79`
- `index_dir`: resolved via the daemon's `_get_engine_context` helper
  in `src/prep/api/routers/agents.py`.
- `llm_fn`: the same `_get_llm_fn(pid)` factory the REST endpoint uses.
  The driver imports these helpers from `prep.api.routers.agents`
  rather than re-implementing them — keeps the dogfood path identical
  to production wiring. If those helpers aren't import-safe (they may
  depend on FastAPI request state), the fallback is to invoke the
  endpoint over HTTP after writing a synthetic findings file into
  the index dir. The implementation plan will pick one.

**Outputs:**
- Stdout: human-readable summary (file → classification → reason).
- `docs/Phase122_FeatureUtilizationAudit/custodian_run.json`: full
  plan with each candidate's `classification` and `reason` text,
  preserved for future cross-reference.

**Safety guarantees:**
- `dry_run=True` always. No archive / branch / execution stage runs.
- `max_files=20` (well above our 11). No risk of runaway scope.
- The Custodian's six-question heuristic is biased toward false
  positives — it prefers `needs_review` over `safe_to_delete` when in
  doubt.

**Known limitation (filed bug):**
- The Custodian's `_get_impact()` will return `dependent_count=0` for
  every Phase 122 candidate because of the `prep_impact` bug
  (P122-D1). The LLM verifier therefore must classify from file
  contents alone. The human confirmation pass in Section B catches
  any miss.

## 4. Triage workflow (Section B)

Per candidate:

1. Read the Custodian's classification + reason.
2. **Confirmation pass (the bug workaround):**
   - `grep -rn "from prep.core.<mod>\|import prep.core.<mod>\|\"prep.core.<mod>\"" src/ tests/ scripts/ tools/`
     — catches re-exports, dynamic imports, and string references the
     LLM verifier might miss.
   - Skim the file's module docstring + `git log --oneline -- <file> | head -3`.
     A module built in a phase whose follow-up died is a DEPRECATE
     candidate.
   - Check `websites/apps/marketing/` for the feature name. Marketing
     claims promote a module to NEEDS-OWNER regardless of caller count.

3. Apply the rubric:

| Custodian says | Confirmation finds | Bucket |
|---|---|---|
| `keep` | Real callers exist (graph was wrong) | **WIRED** — drop from `INTENTIONALLY_DORMANT.md` |
| `keep` | No callers, but planned UI/MCP path | **KEEP-DORMANT** |
| `needs_review` | No callers, no documented plan | **NEEDS-OWNER** |
| `safe_to_delete` | Truly orphaned, last meaningful change > 6 months | **DELETE** |
| `safe_to_delete` | Recent, no plan, low-cost to remove | **DEPRECATE** |
| any | Marketing copy claims the feature | **NEEDS-OWNER** (escalate) |

4. Update artifacts. `docs/INTENTIONALLY_DORMANT.md` entry (matches the
   existing `concept_promotion.py` shape):

   ```markdown
   ## roadmap_miner.py
   - **Path:** `src/prep/core/roadmap_miner.py` (NNN LoC)
   - **Public API:** <symbols from module-level AST>
   - **Production callers:** N (verified 2026-05-13 via Phase 122 Custodian run)
   - **Custodian classification:** safe_to_delete
   - **Custodian reason:** "<LLM verbatim, ≤300 chars>"
   - **Triage decision:** DEPRECATE
   - **Why:** ...
   - **State (2026-05-13):** ...
   - **Trigger to wire / removal target:** ...
   - **Owner:** unassigned.
   ```

   `docs/MASTER_TODO.md` tracker line (one per DEPRECATE / DELETE /
   NEEDS-OWNER decision; KEEP-DORMANT entries are doc-only):

   ```
   - Phase 122 follow-up [DEPRECATE]: `roadmap_miner.py` (NNN LoC) — orphaned since Phase 70, no plan, delete next quarter.
   ```

   WIRED items are removed from `INTENTIONALLY_DORMANT.md` and noted
   in the Phase 122 `RESULTS.md` (Section 5 below) with a one-line
   "moved off dormant list" rationale.

**Error handling:**
- If `verify_candidate` raises (LLM JSON parse failure), record
  `classification: INVESTIGATION_FAILED` and hand-triage that file
  without LLM input.
- If the LLM hallucinates a "real caller" that doesn't exist, the
  grep pass in step 2 catches it.

**Stopping condition:** every module listed under "Other modules under
audit" in `INTENTIONALLY_DORMANT.md` has a triage decision and is no
longer marked "pending." No partial state.

## 5. Bug handling & deliverables (Section C)

### `prep_impact` bug (already filed)

Reproduction (2026-05-13):
- `prep_impact(file_path="src/prep/core/<X>.py", direction="dependents")`
  returns `0 dependents` for all 11 pending Phase 122 candidates AND
  for `src/prep/core/__init__.py` (which has hundreds of consumers).
- Control case `src/prep/services/pipeline/workers.py` correctly
  returns 2 dependents.
- `prep_search type=symbol "roadmap_miner"` reveals the graph is
  bimodal: a `file` node (`src/prep/core/roadmap_miner.py`) and a
  separate `external_module` node (`prep.core.roadmap_miner` with
  empty path). Incoming `from prep.core.X import Y` edges land on
  the `external_module` sister; `prep_impact dependents` queries
  only the file-node side and misses them.

Filed:
- `prep_observe` bug id `bd79badde4d2` (anchor:
  `src/prep/mcp/server.py`).
- `MASTER_TODO.md` entries **P122-D1** (fixture reproduction),
  **P122-D2** (fix the aggregation), **P122-D3** (return "not
  indexed" instead of silent 0).

This phase does **not** fix the bug. The workaround is the grep pass
in Section 4.

### Deliverables

| # | Artifact | Path | Type |
|---|---|---|---|
| 1 | Custodian driver script | `tools/phase122_custodian_run.py` | new file, ~40 LoC |
| 2 | Custodian run log | `docs/Phase122_FeatureUtilizationAudit/custodian_run.json` | new file, machine-readable |
| 3 | Phase results summary | `docs/Phase122_FeatureUtilizationAudit/RESULTS.md` | new file, ~150 LoC |
| 4 | Updated dormant registry | `docs/INTENTIONALLY_DORMANT.md` | edit — 11 entries promoted from "pending" to triaged |
| 5 | Follow-up tracker lines | `docs/MASTER_TODO.md` | edit — N lines (estimate 5–8) |
| 6 | `prep_impact` bug entries | `MASTER_TODO.md` P122-D1/D2/D3 | **DONE 2026-05-13** |
| 7 | `prep_observe` bug observation | id `bd79badde4d2` | **DONE 2026-05-13** |
| 8 | Phase close-out commit message | git | summarizes the above |

### Definition of done

- Every "pending" entry under "Other modules under audit" in
  `docs/INTENTIONALLY_DORMANT.md` has a triage decision.
- `RESULTS.md` exists and documents (a) what the Custodian found, (b)
  what human confirmation changed, and (c) which modules moved buckets
  versus stayed dormant.
- `MASTER_TODO.md` has a tracker line for every DEPRECATE / DELETE /
  NEEDS-OWNER decision.
- The `prep_impact` bug is filed in both `prep_observe` and
  `MASTER_TODO.md`. (Already done as of this spec.)

### Scope estimate

- 11 LLM verifications (one cloud call each).
- ~3 hours of human investigation (~15 min/module average).
- ~2 hours of writing the entries + `RESULTS.md`.
- One commit-set / one PR.

## 6. Cross-references

- `docs/Phase122_FeatureUtilizationAudit/README.md` — original phase
  scaffolding (2026-04-30).
- `docs/INTENTIONALLY_DORMANT.md` — registry being updated.
- `src/prep/agents/custodian/engine.py` — engine being dogfooded.
- `src/prep/agents/custodian/prompts.py` — six-question heuristic
  rationale.
- `src/prep/services/pipeline/workers.py:1397-1515` — Phase 124 T5,
  the WIRE-UP of `spaghetti_scorer` that closed Phase 122's T4.
- `docs/MASTER_TODO.md` — Phase 122 dogfooding entry (2026-05-13)
  with P122-D1/D2/D3.
