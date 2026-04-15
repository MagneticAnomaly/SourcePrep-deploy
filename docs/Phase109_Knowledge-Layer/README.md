# Phase 109 -- Knowledge Layer: Concepts, Audit & Immune System

> **Scope:** Complete the concepts lifecycle, harden the audit pipeline, and wire the immune system end-to-end.
> **Prior art:** Phases 74, 80, 83, 84, 85, 87
> **Status:** Research & TODO (**reality-checked 2026-04-15** — see §1.5; ~70% integrated, quality unvalidated)
> **Date:** 2026-04-15

> **⚠️ Reality-check delta (2026-04-15):** The knowledge layer is **further along than the first draft implies**. Phase 84 concept formalization (assertion, doc_links, supersede) is **SHIPPED** (`concept_store.py:89-91, 320-322`; MCP wiring at `server.py:1697, 1739, 1747`; commit `02cb7d9e`). SARIF enrichment is **SHIPPED** (`980fa9e9`). Immune system core is **SHIPPED**: `antibody_store.init()` IS called at `server.py:835` (the Phase 108 reality-check misread; Phase 109 review confirmed). `tool_antibodies` auto-seeds (`508a7643`). `immune_watcher.evaluate_changes` is wired (`watch.py:202`) with e2e test (`test_immune_watcher.py`). **What remains genuinely open:** (a) concept quality has never been validated on any real project — this is the single biggest risk; (b) audit severity recalibration (§4.3) is 0/7; (c) L2 scoped context filtering (§4.6) is 0/5; (d) `AMBIENT_INJECT` response type is defined but not wired into `codrag` ambient context. See §1.5 for full verdict.

---

## 1. Problem Statement

CoDRAG's knowledge layer has three major subsystems -- Concepts, Audit, and the Immune System (Antibodies). Each has been individually designed, partially implemented, and partially tested. But they have never been validated as an integrated system. The gap between "code exists" and "feature works end-to-end" is the defining issue.

**Concepts:**
- `concept_store.py` (1,146 lines): SQLite-backed store with FTS5 search, staleness, 11 categories. Exists and works.
- `concept_seeder.py` (861 lines): LLM-powered extraction with swarm + sequential paths. Exists, wired to pipeline Stage 13.
- `concept_conflicts.py` (67 lines): Detects potential conflicts between constraint/architecture concepts sharing anchors. Exists.
- `concept_promotion.py`: Exists but unreviewed.
- **MCP exposure:** `codrag_concepts` tool exists. Phase 82 dogfooding result: "N/A -- feature not adopted yet" (empty).
- **Dashboard panel:** Designed (Phase 74, doc 04_UI_Design.md) but never verified as working.
- **Key gap:** Nobody has ever run `seed_concepts` on a real project and verified the output quality.

**Audit:**
- Phase 83 redesigned the audit as a structural intelligence + enrichment layer.
- Phase 85 designed SARIF enrichment for external tool findings.
- Phase 96 fixed Tier 2 synthesis (`synth.synthesize()` AttributeError, F-18) and swarm wiring.
- **Key gap:** Audit severity calibration is broken (32 "critical" findings on healthy repos).

**Immune System (Antibodies):**
- `antibodies.py` (189 lines): Trigger/Response/Severity dataclasses, `evaluate_trigger` function.
- `antibody_derivation.py`: Derives antibodies from constraint/architecture concepts.
- `antibody_store.py`: SQLite-backed store.
- `immune_watcher.py` (110 lines): Evaluates antibodies against changed files, pushes alerts to `alert_queue`.
- Phase 96 fixed: F-37 (antibody_store.init never called), F-38 (wrong argument types).
- **Key gap:** The store was initialized but the MCP server can't read antibodies (Phase 83 finding). The watcher integration (`immune_watcher.evaluate_changes`) is wired but has never been tested on a real project.

## 1.5 Reality Check Against Current Code (2026-04-15)

| Claim (from §1–§2) | Verdict | Evidence |
|---|---|---|
| §1 "Nobody has ever run `seed_concepts` on a real project and verified output quality" | **STILL-OPEN (highest risk)** | Tests mock LLM calls (`test_concept_seeder_swarm.py:49-51`). No quality snapshots. No Phase 74/84 evaluation notes. |
| §1 "dashboard panel designed but never verified working" | **PARTIALLY WIRED** | `ConceptsPanel.tsx` fully implemented with categories, stats, buttons. `useDashboardPanels.tsx:70` imports + renders. `useConceptSystem.ts:31-72` fetches `/projects/{id}/concepts`. Live render with real data untested. |
| §1 "audit severity broken — 32 critical findings on healthy repos" | **CONFIRMED** | `audit/analyzers/large_files.py:12-13` still marks ≥80K as critical; thresholds untouched since Phase 96 |
| §1 "immune system watcher never tested on real project" | **STALE** | `test_immune_watcher.py:25-37` has e2e test; `watch.py:202` calls `mark_stale_batch` which fires `evaluate_changes`; alerts land in `alert_queue` |
| §1 "antibody store initialized but MCP can't read" (Phase 83 finding) | **FIXED** | `mcp/server.py:835` calls `_antibody_store.init(_antibody_store_db_path)` at startup. `tool_antibodies` at `server.py:2088` auto-seeds if empty (`508a7643`). |
| §2.1 "11 categories" | **CONFIRMED** | `concept_store.py:50-62` (architecture, domain, product, epistemic, process, brand, security, technical, pattern, constraint, decision) |
| §2.2 "Sequential + Swarm seeder paths" | **CONFIRMED** | `concept_seeder.py` — both paths; `MIN_MODULES_FOR_SWARM=3` |
| §2.3 "5 antibody trigger types" | **CONFIRMED** | `antibodies.py:18-23` (IMPORT_ADDED, FILE_CREATED, FILE_MODIFIED, PATTERN_MATCH, COUPLING_THRESHOLD) |
| §2.4 "Stage 13/14/15 pipeline wiring" | **CONFIRMED (via 105b)** | Phase 105b unified Regenerate across atlas/concepts/audit (`67863620`); Finalize group workers for rules/concepts/audit/antibodies added in `3e13caba` |
| Phase 84 concept formalization (assertion / doc_links / supersede) | **SHIPPED** | `concept_store.py:89-91` (fields), `:320-322` (schema migrations), `:656+` `supersede()`; MCP wired `server.py:1697, 1739, 1747`; commit `02cb7d9e` |
| SARIF enrichment (§4.4) | **SHIPPED** | `mcp/server.py:2244` `tool_audit_enrich_sarif`; auto-dispatch at `:3973`; full SARIF-in/SARIF-out |
| §4.6 L2 scoped context (working_dir filtering for observations + concepts) | **STILL-OPEN** | `_inject_observations()` has no working_dir param; `concept_store.list_concepts()` (`:879`) has no working_dir param; `tool_concepts` (`server.py:1697`) has no working_dir |
| AMBIENT_INJECT antibody response type pushes into codrag context | **STILL-OPEN** | `antibodies.py:26-29` defines enum; `de4a6463` wired alert injection into ambient context — verify in Phase 111 QA whether this flows through to `tool_codrag` responses |
| Concept conflicts detection | **SHIPPED** | `concept_conflicts.py` complete; surfaced as audit findings (`530d40c6`); `test_concept_conflicts.py` |
| Concept observation→promotion | **SHIPPED** | `concept_promotion.py` (`8cea7ee4`) |

**Commits landed after first draft:**
- `67863620` feat(phase105b): unified Regenerate across atlas/concepts/audit
- `ea25b9e2` docs(phase105): Concepts as third UI-triggered stage + re-seed semantics
- `3e13caba` feat(P96): Finalize group workers — rules, concepts, audit, antibodies
- `508a7643` feat(immune): `tool_antibodies` reads from store with auto-seed + status updates
- `de4a6463` feat(immune): wire alert injection into ambient context, antibody management
- `980fa9e9` feat(sarif): SARIF auto-detection + enrichment into MCP dispatch
- `d8526603` feat(immune): watcher-driven antibody evaluation
- `f6317cf6` feat(immune): persistent antibody store (SQLite)
- `30c80cce` fix(concepts): API router passthrough, severity enum
- `02cb7d9e` feat(concepts): wire assertion, doc_links, supersede through MCP handlers
- `530d40c6` feat(audit): surface concept conflicts as structural audit findings
- `8cea7ee4` feat(concepts): observation-to-concept promotion logic

**Bottom line:** The plumbing is largely in place. The knowledge layer's **weakness is quality validation**, not implementation. Prioritize §4.1 (run seed_concepts on 3+ real repos, grade output), §4.3 (audit severity calibration fixtures + thresholds), and the AMBIENT_INJECT final wiring verification.

## 2. Current Infrastructure (from source inspection)

### 2.1 Concept Categories

From `concept_store.py:50-63`:
```
architecture, domain, product, epistemic, process, brand, security,
technical, pattern, constraint, decision
```

11 categories. This is comprehensive. The `constraint` and `architecture` categories are special -- they're the ones that can generate antibodies.

### 2.2 Concept Seeder Paths

From `concept_seeder.py`:
- **Sequential path:** Single LLM call with global context prompt. Always available.
- **Swarm path:** Decomposes into per-module work items, fans out across LLM workers. Requires >= 3 modules, swarm-capable model, scheduler budget >= 3.
- `MIN_MODULE_FILES = 5` for sequential, `MIN_MODULE_FILES_FOR_SWARM = 1` for swarm.

### 2.3 Antibody Trigger Types

From `antibodies.py:18-23`:
```
IMPORT_ADDED, FILE_CREATED, FILE_MODIFIED, PATTERN_MATCH, COUPLING_THRESHOLD
```

And response types:
```
AMBIENT_INJECT, AUDIT_FINDING, OBSERVATION_AUTO
```

This is a solid foundation. The `AMBIENT_INJECT` response type means antibodies can push context into `codrag` tool responses -- this is the killer feature for AI agents.

### 2.4 Pipeline Stage Wiring

From `stages.py`:
- Stage 13: `CONCEPTS` (LLM, uses "large" model slot)
- Stage 14: `AUDIT` (LLM, uses "large" model slot)
- Stage 15: `ANTIBODIES` (RUST queue type -- no LLM, derives from concepts)

The pipeline wiring exists. The question is whether it produces useful output.

## 3. Proposed Solutions

### Solution A: Concept Quality Validation Sprint

Run `seed_concepts` on 3-5 real projects of varying sizes. Grade output on:
1. **Completeness:** Does it capture the key architectural decisions?
2. **Accuracy:** Are the anchors correct?
3. **Actionability:** Would an AI agent find these concepts useful?
4. **Category distribution:** Are concepts spread across categories or clustered?

Then iterate on the seeder prompts based on findings.

### Solution B: Audit Severity Recalibration

Create a severity calibration test suite:
- Healthy small repo (50 files): expect 0-2 critical findings
- Healthy medium repo (500 files): expect 0-5 critical findings
- Intentionally unhealthy repo (circular deps, hub concentration): expect 10+ critical findings

Adjust thresholds until the calibration suite passes.

### Solution C: Immune System End-to-End Test

1. Seed concepts on test repo (must include some `constraint`/`architecture` concepts)
2. Run antibody derivation (Stage 15)
3. Verify antibodies exist in store
4. Modify a file that should trigger an antibody
5. Verify alert appears in `alert_queue`
6. Verify `codrag_audit(action="antibodies")` returns the alert via MCP

### Solution D: MemPalace L2 Scoped Context (Phase 80)

Phase 80 research found that L2 module-scoped retrieval (observations + concepts scoped to the current working directory) is a "DO THIS" priority. The `working_dir` param already exists on `codrag` and `codrag_search`. The gap is that observations and concepts aren't filtered by `working_dir` proximity.

## 4. TODO

### 4.1 Concept Quality Validation — **HIGHEST-RISK OPEN SECTION (0/8)**
Plumbing is shipped; the knowledge layer has simply never been fed a real corpus and graded.
- [ ] Run `seed_concepts` on CoDRAG itself — inspect output quality, category distribution, anchor accuracy — **[STILL-OPEN]**
- [ ] Run `seed_concepts` on 2 external test repos (different languages/sizes) — **[STILL-OPEN]**
- [ ] Grade each run: completeness, accuracy, actionability (1-5 scale) — **[STILL-OPEN]**
- [ ] If quality < 3 on any dimension, iterate seeder prompts in `concept_seeder.py` — **[STILL-OPEN]**
- [ ] Verify `codrag_concepts(action="get")` returns seeded concepts via MCP — **[PARTIAL]** handler wired; no live-output test
- [ ] Verify concept staleness: modify anchored file, confirm stale — **[PARTIAL]** `mark_stale_batch` at `concept_store.py:797` called from `watch.py:202`; no explicit e2e assertion
- [ ] Verify concept conflicts: two contradicting constraint concepts on same file — **[PARTIAL]** `concept_conflicts.py` complete; audit integration via `530d40c6`; live test missing
- [ ] Run concept promotion flow — **[PARTIAL]** `concept_promotion.py` complete (`8cea7ee4`); MCP handler wired; live test missing

### 4.2 Concept Dashboard Panel
- [ ] Verify ConceptsPanel renders with seeded data — **[NEEDS-VERIFICATION]** (component fully implemented; no live screenshot/test)
- [ ] Verify count, cluster summary, coverage bar display — **[NEEDS-VERIFICATION]**
- [x] Verify "Initialize Concepts" button triggers Stage 13 through orchestrator — **[FIXED: 67863620]** (Phase 105b unified Regenerate)
- [ ] Verify pending question count badge — **[NEEDS-VERIFICATION]**
- [ ] Verify inline answer capability — **[NEEDS-VERIFICATION]** (callback exists; backend endpoint not verified)
- [ ] Fix rendering issues if broken — **[BLOCKED on verification pass]**

### 4.3 Audit Severity Recalibration — **STILL-OPEN (0/7)**
The single remaining audit-critical section. Lock-file basename filter is in; severity thresholds are not.
- [ ] Create severity calibration fixture: healthy-small, healthy-medium, unhealthy repos — **[STILL-OPEN]**
- [ ] Run `codrag_audit(action="scan")` on each; record finding counts by severity — **[STILL-OPEN]**
- [ ] Adjust thresholds in `large_files.py`, `circular_deps`, `hub_concentration` — **[STILL-OPEN]** (`large_files.py:76-82` still marks 80K+ as critical)
- [x] Lock files excluded as findings — **[PARTIAL]** EXPECTED_LARGE_BASENAMES at `large_files.py:20-35` excludes common lock files (package-lock.json, yarn.lock, etc.); nested & less common lock formats may slip through
- [ ] Log files excluded as findings — **[STILL-OPEN]** (no `.log` filter visible)
- [ ] Healthy repos < 5 critical findings after calibration — **[STILL-OPEN]**
- [ ] Regression test for severity calibration — **[STILL-OPEN]**

### 4.4 SARIF Enrichment (Phase 85) — **SHIPPED (3 core items)**
- [x] `codrag_audit(findings=[{...}])` enrichment — **[FIXED: 980fa9e9]** (`mcp/server.py:2244`)
- [x] Enrichment adds dependent count, hub status, concepts, risk score — **[FIXED]** (enrichment.py)
- [x] SARIF-in/SARIF-out for CI — **[FIXED]** (`mcp/server.py:3973` auto-detect)
- [ ] Test with ruff output on CoDRAG repo — **[STILL-OPEN]** (no snapshot test)
- [ ] Test with eslint output on TS project — **[STILL-OPEN]**
- [ ] Document CI pipeline integration — **[STILL-OPEN]**

### 4.5 Immune System End-to-End — **MOSTLY SHIPPED (6/8)**
- [x] `antibody_store.init()` called on MCP startup — **[FIXED]** (`mcp/server.py:835`)
- [x] `derive_antibodies_for_project` produces antibodies — **[FIXED]** (`antibody_derivation.py`; auto-seed in `tool_antibodies`)
- [x] Antibodies stored — **[FIXED]** (`services/antibody_store.py`; verified at `server.py:2146-2147`)
- [x] `immune_watcher.evaluate_changes` fires on file mods — **[FIXED]** (`test_immune_watcher.py:25-37`; `watch.py:202`)
- [x] Alerts in `alert_queue` — **[FIXED]** (`test_immune_watcher.py:35-37`)
- [x] `codrag_audit(action="antibodies")` returns active antibodies via MCP — **[FIXED: 508a7643]** (`server.py:2088`, auto-seeds if empty)
- [ ] **AMBIENT_INJECT pushes into `codrag` responses** — **[STILL-OPEN]** enum defined at `antibodies.py:26-29`; `de4a6463` wired alert injection into "ambient context" but whether that flows into `tool_codrag` responses needs verification. **This is the killer feature for AI agents.**
- [ ] End-to-end integration test: seed → derive → modify → verify alert in codrag response — **[STILL-OPEN]**

### 4.6 L2 Scoped Context (Phase 80) — **STILL-OPEN (0/5)**
- [ ] Filter observations by working_dir proximity — **[STILL-OPEN]** `_inject_observations()` has no working_dir param
- [ ] Filter concepts by anchor proximity — **[STILL-OPEN]** `concept_store.list_concepts()` has no working_dir param
- [ ] Add working_dir to observation query — **[STILL-OPEN]**
- [ ] Test: observation anchored to `core/index.py`, called with `working_dir="core/"` — appears — **[STILL-OPEN]**
- [ ] Test: called with `working_dir="api/"` — does NOT appear — **[STILL-OPEN]**

### 4.7 Concept Formalization (Phase 84) — **MOSTLY SHIPPED (4/5)**
- [x] `assertion` field on concepts — **[FIXED]** (`concept_store.py:89`, schema `:320`)
- [x] `doc_links` field — **[FIXED]** (`concept_store.py:90`, schema `:321`; MCP wired `server.py:1739`)
- [x] `supersede` lifecycle — **[FIXED]** (`concept_store.py:91`, `supersede()` at `:656+`; MCP `server.py:1747`)
- [x] Schema migrations applied — **[FIXED]**
- [ ] **Wire assertion checking into audit: violations = audit findings** — **[STILL-OPEN]** Assertion field exists but violation-to-finding pipeline not built. Decide: ship with Phase 109 or defer.

## 5. Links to Prior Work

| Phase | What it built | Status | Gap this phase addresses |
|---|---|---|---|
| 74 | Concepts system design (5 docs) | **Code complete**; quality unvalidated on real corpus | §4.1 + §4.2 verification |
| 80 | MemPalace (L2 scoped context) | Research flagged "DO THIS"; **not implemented** | §4.6 (0/5) |
| 83 | Audit Redesign | Design complete; severity still broken | §4.3 (0/7) |
| 84 | Concepts Formalization | **Assertion / doc_links / supersede SHIPPED** (`02cb7d9e`) | §4.7 — only assertion-to-audit wiring remains |
| 85 | SARIF Enrichment | **SHIPPED** (`980fa9e9`) | §4.4 — snapshot tests remain |
| 87 | Codebase Immune System | **Core SHIPPED** (store init, watcher, MCP read, auto-seed) | §4.5 — AMBIENT_INJECT verification + e2e test remain |

## 6. Success Criteria

1. `seed_concepts` produces >= 3.5/5 quality on all dimensions across 3+ repos
2. `codrag_concepts` returns useful data for AI agents
3. Audit produces < 5 critical findings on healthy repos
4. SARIF enrichment works with ruff output
5. Immune system fires antibody alerts on file modifications, accessible via MCP
6. L2 scoped context returns proximity-filtered observations and concepts
