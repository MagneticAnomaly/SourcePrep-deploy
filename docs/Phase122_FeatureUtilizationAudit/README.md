# Phase 122 -- Feature Utilization Audit

> **Scope:** Find the features, scripts, and tools we have built but
> aren't actually using in production paths. For each, decide: wire
> it up, retire it, or leave it dormant with a documented reason.
> **Prior art:** Phase 95 (path weights advertised but not implemented),
> Phase 110 §1.5 (intent classification ‑ multiple shipped components
> not yet wired through retrieval).
> **Status:** Research & TODO
> **Date:** 2026-04-30

---

## 1. Problem Statement

The codebase has accumulated significant tooling over 119+ phases, and
some of it is silently inert. The Phase 119 swarm-quality investigation
surfaced one concrete example:

```text
.sourceprep/audit/   (PowerMate run)
├── ARCHITECTURE_ANALYSIS.md
├── AUDIT_SUMMARY.md
├── COMPONENT_INVENTORY.md
├── GAP_ANALYSIS.md
├── TECH_DEBT_REPORT.md
└── spaghetti.json     ← present

.sourceprep/audit/   (SourcePrep run, same code path)
├── ARCHITECTURE_ANALYSIS.md
├── AUDIT_SUMMARY.md
├── COMPONENT_INVENTORY.md
├── GAP_ANALYSIS.md
└── TECH_DEBT_REPORT.md  ← spaghetti.json missing
```

`src/prep/core/audit/spaghetti_scorer.py` is a fully-implemented module
with `run_spaghetti_scan()` and `save_spaghetti()` — but its only
production caller is the `/audit` REST endpoint, **not** the pipeline's
audit worker. So the structured spaghetti score gets written when a UI
button or API client triggers it, never during the automatic
finalize/audit stage. PowerMate has it because something (probably a
manual probe) hit the endpoint; SourcePrep doesn't because that path
wasn't exercised.

Naive grep for "core modules with no external imports" surfaces 15+
candidates: `roadmap_miner.py`, `treatment_registry.py`,
`antibody_derivation.py`, `swarm_optimizer.py`, `lod_extractor.py`,
`concept_promotion.py`, `github_sync.py`, `budget_enforcement.py`,
`chunking.py`, `inferred_edges.py`, `batch_profiles.py`,
`rules_generator.py`, `context_config.py`, `swarm_registry.py`,
`concept_seeder.py`. Some are false positives (re-exported via
`__init__.py` which the heuristic missed); the rest deserve a real
look.

The hypothesis: **we built more than we wired up**, and the diff
between "built" and "wired up" is a quality lever and a maintenance
liability that grows quietly.

---

## 2. Goals

1. **Inventory** every potentially-underutilized capability with
   evidence (production callers, API consumers, test coverage,
   marketing claims).
2. **Triage** each into one of: KEEP-AND-WIRE / KEEP-AS-IS /
   DEPRECATE / DELETE / NEEDS-OWNER.
3. **Ship** the WIRE-UP fixes for high-value cases (spaghetti.json
   into the audit pipeline is the prototype).
4. **Document** dormant features that we're keeping intentionally so
   the next audit doesn't re-surface them.

## 3. Non-goals

- Refactoring functioning features that are merely "verbose" or
  "complex".
- Pursuing 100% code coverage.
- Auditing third-party dependencies.
- Brand-new feature work — this phase only acts on what already exists.

---

## 4. Methodology

### 4.1 Detection passes

For each artifact class, define a "wired-up" signal and find the gap.

| Class | "Wired up" means | Detection |
|---|---|---|
| Python module under `src/prep/core/` | imported at least once outside its own package | `grep -rE "from prep.core.X import\|import prep.core.X" --include='*.py' --exclude-dir=tests` |
| FastAPI route (`@router.*`) | called from `packages/ui/src/api/client.ts` OR an MCP tool OR documented in AGENTS.md | path-string search across UI + MCP files |
| MCP tool (in `mcp_tools.py`) | listed in AGENTS.md AND called by at least one test or has integration evidence | manual cross-check |
| Storybook story | a corresponding component is rendered in a real dashboard route | grep stories' component name in `src/prep/dashboard/src` |
| Pipeline output file (`*.json`, `*.jsonl` in `.sourceprep/`) | the dashboard or another stage reads it | grep filename in src/prep + packages/ui |
| Stage in `STAGE_TASK_ID` | enabled by default in pipeline group config | check `stages.py` + `pipeline_orchestrator.py` |

### 4.2 Triage protocol

For each candidate, fill out:

```yaml
- name: spaghetti_scorer
  path: src/prep/core/audit/spaghetti_scorer.py
  built_in_phase: ?
  current_callers: [/audit REST endpoint]
  expected_callers: [audit pipeline worker]
  evidence_of_value: HIGH (PowerMate spaghetti.json had structured
                          findings the markdown reports lacked)
  decision: KEEP-AND-WIRE
  owner: ?
  next_step: call run_spaghetti_scan in audit_worker after the
             markdown reports are generated; persist to audit/spaghetti.json
  effort: ~30 LoC
```

### 4.3 Deliverable

A markdown table with all candidates triaged, plus a punch list of
WIRE-UP PRs ordered by ROI.

---

## 5. Initial candidate list (seed)

Items found during Phase 119 recon. Treat as starting points; the audit
will broaden it.

### A. Confirmed under-wired (high priority)

| Candidate | Built-in callers | Expected | Status |
|---|---|---|---|
| `core/audit/spaghetti_scorer.py` | only REST | pipeline audit worker | **KEEP-AND-WIRE** |

### B. Likely under-wired (need investigation)

| Candidate | Heuristic flag | Investigate |
|---|---|---|
| `core/roadmap_miner.py` | no external imports detected | what does it do, who's supposed to call it |
| `core/treatment_registry.py` | no external imports detected | likely re-exported via `__init__`; verify |
| `core/antibody_derivation.py` | no external imports detected | antibodies are working — is this called via re-export? |
| `core/swarm_optimizer.py` | no external imports detected | distinct from `swarm_orchestrator`; what is it? |
| `core/lod_extractor.py` | no external imports detected | Phase 95 LOD work; was it finished? |
| `core/concept_promotion.py` | no external imports detected | observation→concept promotion path; UI evidence? |
| `core/github_sync.py` | no external imports detected | does anything still call it? |
| `core/budget_enforcement.py` | no external imports detected | budgets exist in UI; how are they enforced |
| `core/chunking.py` | no external imports detected | semantic chunking shipped Phase 110; verify wiring |
| `core/inferred_edges.py` | no external imports detected | pipeline stage exists; ensure edge inference runs |
| `core/batch_profiles.py` | imports detected via `prep.core` | likely wired; confirm |

### C. Potentially over-built surfaces

| Surface | Approximate size | Audit |
|---|---|---|
| FastAPI routes under `src/prep/api/routers/` | 279 routes | which are unused by UI + MCP |
| Storybook stories | 79 stories | which components don't render in any real route |
| Phase-specific code paths (e.g., `# Phase 96B: ...`) | many | which are still load-bearing vs vestigial |

---

## 6. Tasks

| ID | Task | Output |
|---|---|---|
| T1 | Build a `tools/feature_audit.py` script that runs the detection passes from §4.1 | reproducible report |
| T2 | Fix the false-positive bug in the "no external imports" heuristic (re-exports through `__init__.py`) | accurate triage list |
| T3 | Apply triage protocol §4.2 to each candidate (15-30 items expected) | markdown spreadsheet |
| T4 | Wire `spaghetti_scorer` into the pipeline audit worker (proof-of-concept WIRE-UP) | code + test |
| T5 | For DELETE / DEPRECATE items, write removal PRs | reduced surface area |
| T6 | For KEEP-AND-WIRE items, file follow-up issues with effort estimates | backlog |
| T7 | Land `docs/INTENTIONALLY_DORMANT.md` listing features kept inert with reasons | future-proofing |
| T8 | Audit FastAPI routes (§5.C) — produce the unused-endpoints list | route triage |
| T9 | Audit Storybook stories vs real dashboard usage | story triage |

## 7. Open questions

1. **Unit of triage:** module-level vs function-level? Some files have
   live functions next to dead ones. Start at module level; refine if
   needed.
2. **What counts as "in production"?** The pipeline path is canonical;
   "tested" is not the same as "called by a real run." Use pipeline
   logs + telemetry as the bar.
3. **Marketing claims as a third axis?** Phase 110 found "advertised
   but not shipped" cases. Cross-reference `websites/apps/marketing`
   to catch these.
4. **Cross-cutting CLI commands** (`prep …` subcommands) — are any of
   them undocumented or unused? Not clear yet.

## 8. Out-of-scope follow-ups

- Replacing the audit format from `.md` files to a richer structured
  format (separate concern from "spaghetti.json missing").
- Generalized dead-code analysis beyond Python (TS unused exports
  belong to `tsc --noUnusedLocals` / a separate JS pass).
- Marketing site claim accuracy audit beyond the cross-reference in §7.

---

## 9. Cross-references

- `src/prep/core/audit/spaghetti_scorer.py` — example of unwired tool
- `src/prep/api/routers/audit.py:146-169` — current sole caller
- Phase 110 §1.5 — pattern of "advertised but not implemented"
- Phase 121 — Ollama UX gaps (parallel UX-truth investigation)
