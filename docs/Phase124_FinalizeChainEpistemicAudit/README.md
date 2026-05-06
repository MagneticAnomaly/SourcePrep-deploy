# Phase 124 — Finalize Chain Epistemic Audit

> **Scope:** Treat stages 11–15 (Atlas → Rules → Concepts → Audit →
> Antibodies) as a single epistemological chain, not five
> independent stages. Audit the chain end-to-end on real codebases,
> close the docs→module evidence loop that currently leaves planning
> markdown structurally orphaned, and absorb the Finalize-chain
> wire-up gaps surfaced by Phase 122.
> **Status:** Scaffolded — **not started**
> **Date opened:** 2026-05-01
> **Companion phase:** Phase 123 (concept synthesis prompt tuning) —
> ships in parallel; this phase strengthens the *inputs* that Phase
> 123 then tunes against.

---

## 0. Getting started (next agent, read this first)

This phase is broader than Phase 123 but every task in §6 is
independently shippable. **Do not** try to land it as one PR — treat
the backlog as a punch list. The first session's job is to capture
baseline measurements, not to change behavior.

### Recommended first session (≤2 hours)

1. **Read §1 and §2** to internalize the "chain, not five stages"
   framing. Without it the rest reads as five disconnected fixes
   and you will be tempted to bundle them.
2. **Run the grading harness on stages 11-15** for SourcePrep plus
   one external project (PowerMate or Halley). Build it as the first
   PR (T1) — Phase 82's rubric in
   `docs/Phase82_MCP-Dogfooding/README.md` is the template. Don't
   tune anything yet; capture what the pipeline currently writes to
   disk for each of the five stages.
3. **Inspect `.sourceprep/atlas_segments/` for an external project
   with a deep planning tree.** Halley has `docs/architecture/` and
   `docs/decisions/`. Confirm or refute H2 (§3) with hard evidence:
   count `.md` files in segments where the segment's modules have
   zero edges from those `.md` files.
4. **Open T1 (grading harness) as the first PR.** Everything else
   in §6 depends on having reproducible measurements before/after.

### What this phase explicitly does NOT do

- Re-architect the atlas segmentation algorithm. Directory-based
  segmentation stays. We only add cross-links *on top* of it.
- Tune the concept synthesis prompt — that is Phase 123's scope.
  This phase changes the *worker* prompt (input enrichment), not
  the *synthesis* prompt (output dedup).
- Touch atlas role projection or the role-lens panel. Phase 104
  owns that surface.
- Add a new pipeline stage. The chain stays at 15.
- Build a "Docs Hub" UI panel. That's a future phase that depends
  on T2 (markdown link parser) landing first.
- Embedding-based doc↔code matching. Path-mention parsing is
  cheap, deterministic, and good enough for the first pass.

### Companion-phase coordination (Phase 123)

Phase 123 and Phase 124 share one anchor file
(`src/prep/core/concept_seeder.py`). Sequence to avoid a merge
conflict and to keep cause/effect attribution clean:

1. **124's T4 lands first** — worker prompt receives linked-doc
   excerpts. Concept output gets richer inputs but the synthesis
   step is unchanged.
2. **123's T2/T3 lands second** — synthesis dedup tightening,
   measured against the new doc-aware worker output.
3. **Joint acceptance criterion** — the 30-80 concept target in
   Phase 123 §8 only counts as met when measured *after* 124's T4.
   Co-authored §5 of Phase 123's acceptance.

---

## 1. Problem statement

Stages 11–15 are the *entire* surface area an external AI agent
sees: the atlas it consumes, the AGENTS.md it reads, the concepts
and antibodies that frame its judgment, the audit findings it
should act on. They are not five independent stages — they are a
single epistemological pipeline:

```
       ┌──────► RULES (12) ──────────────────────┐
       │                                          ▼
ATLAS (11) ──► CONCEPTS (13) ──► ANTIBODIES (15) ──► MCP prep() ambient
       │              │                                  ▲
       └──► AUDIT (14) ◄─────────────────────────────────┘
```

Three concrete symptoms point at the same root cause — the chain is
under-fed structural and prose evidence:

1. **Concepts compress to ~13** on a 1,848-file codebase
   (Phase 123 finding). The per-module worker prompt in
   `concept_seeder.py:562-592` receives `module_data` only — never
   the contents of `docs/Phase*/` files that contain explicit
   "this exists because…" rationale. The model is paid LLM compute
   to invent WHY language we already wrote down by hand.
2. **Atlas segmentation is directory-based with no cross-links.**
   `.md` files in deep planning trees become standalone
   "documentation"-tagged components and get merged into a sibling
   segment by edge count, not by what they describe. Their content
   never reaches the concept worker for the modules they document.
3. **Stage 14 AUDIT is missing `spaghetti.json`** in production
   pipeline runs (Phase 122 finding). `concept_promotion.py` and
   `antibody_derivation.py` show "no external imports" — the
   observation→concept→antibody flywheel may be silently inert.

Treating these as three separate fixes (Phase 123 owns concept
prompt; Phase 122 owns wire-ups; "future" owns docs handling)
leaves the chain broken in three places and tunes the visible end
(concepts) without the inputs (docs) or the consumers (antibodies,
audit) catching up. **This phase fixes the chain as a chain.**

---

## 2. The chain (what each stage actually does)

| # | Stage | Reads | Writes | Consumed by |
|---|---|---|---|---|
| 11 | ATLAS | `trace_modules.jsonl` | `atlas.json`, `atlas_segments/`, `atlas_roles/`, `atlas_routing.json` | RULES, MCP `prep()` |
| 12 | RULES | atlas + concepts | `AGENTS.md`, per-IDE rule files | external agents |
| 13 | CONCEPTS | `trace_modules.jsonl` (via `_build_module_context`) | concept store rows + `concepts_manifest.json` | ANTIBODIES, MCP `prep_concepts` |
| 14 | AUDIT | `trace_*.jsonl` | `audit/*.md`, **missing** `audit/spaghetti.json` | dashboard panel, MCP `prep_audit` |
| 15 | ANTIBODIES | concept store (constraint + architecture rows) | `antibodies_manifest.json` | MCP `prep()` ambient alerts |

### Implicit cross-links today

- ATLAS references modules from CLUSTERING (Stage 8). Modules
  reference files. Files have edges only via imports / calls /
  contains.
- CONCEPTS anchor to file paths. Anchors are validated against the
  file system but not against the atlas segments those files
  belong to.
- ANTIBODIES derive from concepts that have `assertion` + `anchors`.
  If concepts have shallow anchors, antibodies have shallow
  blast-radius scopes.

### Missing cross-links (this phase fixes)

- No back-link from a code module → planning `.md` files that
  describe it.
- No forward-link from a `.md` file → modules / files it
  references in prose.
- No structural propagation: a concept anchored to `src/foo.py`
  does not surface as evidence in the atlas segment containing
  `src/foo.py`.

These three missing links are the entire reason the chain feels
hollow even though every stage individually "works."

---

## 3. Hypotheses (test these in order — falsify cheaply)

### H1 — Workers extract concepts blind to docs/ prior art

**Test:** instrument `_build_module_context` (or a one-shot script)
to count, per module, how many `.md` files anywhere in the project
mention any file in `module.member_files`. Expectation: many
modules have multiple relevant docs that the worker prompt never
sees today.

**If true:** T4 (pipe linked docs into worker prompt) is the
highest-leverage change in this phase.

### H2 — Atlas segmentation orphans deep planning trees

**Test:** for SourcePrep and one external project, dump
`atlas_segments/` and grep for `.md` files. Compute the % that
land in a segment whose code they reference vs. a segment chosen
purely by directory adjacency.

**If true:** T2 (markdown code-path link parser) is the structural
fix.

### H3 — Antibodies are sparse because concepts are sparse, not because the derivation logic is broken

**Test:** after Phase 123 lands its prompt tuning and concept count
rises to 30-80, count the antibodies derived. If the
`antibodies / constraint-category-concepts` ratio is stable
pre/post, derivation is fine.

**If false:** Phase 122's `antibody_derivation.py` flag is real and
needs investigation in T7.

**Result (2026-05-01, harness-confirmed): REFUTED early.**
Stage 15 scored 9.0/10 in the T1 baseline run.
**5 of 5** eligible (constraint + architecture) concepts produced
antibodies — 100% conversion ratio. Derivation is not broken;
sparse antibodies are a direct function of sparse concepts.
T7 collapses from "investigate" to "verify ratio holds after
Phase 123 lands." Phase 122's "no external imports" flag on
`antibody_derivation.py` is almost certainly a re-export false
positive (Phase 122 §0 explicitly notes this risk).

### H4 — Audit markdown reports waste the structural signal

**Test:** read `audit/AUDIT_SUMMARY.md` for SourcePrep. Compare to
`audit/spaghetti.json` from PowerMate (the structured equivalent
that exists because some manual probe hit the REST endpoint). The
markdown is for humans; the JSON is what an MCP consumer can
actually act on.

**If true:** wiring `spaghetti_scorer.py` into the audit worker
(absorbed from Phase 122 T4) belongs in this phase.

---

## 4. Methodology

### 4.1 Dogfood grading harness (T1)

Adopt Phase 82's rubric verbatim, but scope it to **stage outputs**
rather than MCP tool outputs:

| Dimension | Question for stages 11–15 |
|---|---|
| Signal quality | Does the output help an agent reason about the codebase? |
| Noise ratio | What % of bytes is filler / restatement of code? |
| Consistency | Does the same project produce stable output across runs? |
| Actionability | Can an agent act on this without re-reading the source? |
| Completeness | Are important files / decisions / constraints missing? |

Build `tools/finalize_chain_audit.py`:

- Runs against a project's `.sourceprep/` (or standalone project) directory.
- Reads each Stage-11-15 output file (`atlas.json`,
  `atlas_segments/*.json`, `AGENTS.md`, concept rows, `audit/*.md`,
  `antibodies_manifest.json`).
- Emits per-stage scores + per-stage notes + per-stage anti-pattern
  flags (e.g., "concept count < 20 on >500-file project",
  "atlas segment has no concepts anchored to its members").
- Diffs against a previous baseline JSON so reruns show
  improvement / regression numerically.
- Single output file: `audit/finalize_chain_audit.json` per project.

### 4.2 Markdown link parser (T2)

Add a deterministic markdown scanner — `atlas/markdown_links.py`:

- For each `.md` file in the project, extract:
  - **Code-path mentions** via regex
    (`\b[A-Za-z0-9_./-]+\.(py|ts|tsx|rs|js|jsx|md)\b`)
  - **Markdown links** to source files (`[label](path)`)
  - **Inline code spans** matching valid file paths (`` `src/foo.py` ``)
- Validate each candidate against the file system / trace nodes —
  a path is only kept if it resolves to a real, indexed file.
- Emit `atlas_markdown_links.json`:
  ```json
  {
    "docs/Phase104_SubAtlas/README.md": [
      "src/prep/core/atlas/role_projection.py",
      "src/prep/core/atlas/routing.py",
      "src/prep/dashboard/src/hooks/useAtlasLens.ts"
    ]
  }
  ```
- Build the reverse index lazily at consume time:
  `module_id → list of .md files that mention any member_file`.

This is **not** an LLM step. Runs in seconds. Lives in the ATLAS
stage so its output is on disk for RULES, CONCEPTS, AUDIT
downstream.

### 4.3 Atlas surfaces docs per segment (T3)

Extend the atlas response (the existing
`AtlasSegmentStatus` payload from Phase 104) with one new field:

```ts
docs_for_segment?: { path: string; mention_count: number }[];
```

Populated from `atlas_markdown_links.json` aggregated by segment.
Limited to top-N (5?) by mention count to control payload size.
Read-only in v1 — no UI write path.

### 4.4 Concept worker enrichment (T4)

Extend `_build_module_context` in `concept_seeder.py` to attach
linked-doc excerpts:

```python
ctx["relevant_docs"] = [
    {
        "path": p,
        "excerpt": _extract_relevant_section(p, member_files),
    }
    for p in markdown_links_for_module(module_id)
][:5]   # cap to control prompt size
```

Tune the worker prompt (`concept_seeder.py:569-592`) to add:

> "If `relevant_docs` is non-empty, prefer rationale stated
> explicitly in those documents over rationale you would infer
> from the code shape alone. When elevating a claim to high
> confidence, quote from `relevant_docs` and put the doc path in
> the concept's `anchors`."

**Budget math:** ~500 chars/doc × 5 docs/module = ~2.5K extra
prompt tokens per worker. Stays inside the existing 4000
`num_predict` budget without crowding the JSON output.

**Excerpt extraction (v1):** simple line-window — N lines before
and after each path mention, deduped, joined. A section-header-aware
extractor is T9 (stretch).

### 4.5 Phase 122 wire-ups absorbed (T5–T7)

Three Phase 122 candidates that live in the Finalize chain — pull
them into this phase's scope rather than letting them drift:

- **T5 — `spaghetti_scorer.py`** → call `run_spaghetti_scan(...)`
  directly in `_audit_worker` after `save_findings` and before the
  Tier 2 LLM block. **~12 LoC** — slightly more than the
  initially-estimated 5 because `run_health_scan` and `run_audit`
  have **different return types** (`List[ActionItem]` vs
  `AuditResult`); a naive swap would break `save_findings`. The
  direct-call approach reuses `run_spaghetti_scan` (a public
  convenience entry that loads ctx + scores), accepts one duplicate
  ctx-load (~5s), and leaves `run_audit`'s contract untouched.
  Background: `memory/project_audit_spaghetti_migration.md` — the
  panel-era unified entry point exists but its return type
  diverged. **Status:** ✅ landed
  (`workers.py:1081-1108`). Lands spaghetti **upstream** of the
  LLM Tier 2 synthesis so T5b can consume it. T5b can also collapse
  the duplicate ctx-load by refactoring to share ctx between the
  spaghetti pass and the Tier 2 synthesizer.
- **T5b — Tier 2 synthesizer consumes spaghetti findings** →
  separate PR after T5. Pass `result.spaghetti` into
  `AuditSynthesizer` so the markdown reports cite spaghetti
  hotspots structurally instead of re-deriving them from raw
  findings. ~80 LoC. Architecturally enabled by T5's
  before-the-LLM placement; impossible if T5 had run in parallel.
- **T6 — `concept_promotion.py`** → audit whether the
  observation→concept promotion path is reachable from any caller.
  If yes, log promotion attempts and confirm they fire. If no,
  decide KEEP-AND-WIRE vs DELETE per Phase 122 §4.2 protocol.
- **T7 — `antibody_derivation.py`** → confirm derivation runs
  against the concepts produced post-Phase-123 tuning. Fix the
  import-path heuristic flag if it's a false positive (re-export
  via `__init__.py`), or wire it up if it isn't.

### 4.6 Validation (T8)

- Re-run `tools/finalize_chain_audit.py` and diff scores against
  the §0 baseline.
- Drive the dashboard Concepts panel + Atlas panel + Audit panel
  headlessly via the `playwright-smoke` skill to confirm new
  fields render and no panels regress.
- Ship `docs/Phase124_FinalizeChainEpistemicAudit/RESULTS.md`
  with the before/after numbers and any unanticipated regressions.

---

## 5. Backlog (one-tuning-knob-per-PR)

In priority order. Finish T1 instrumentation before changing any
behavior — without baseline numbers we cannot prove improvement.

| ID | Change | Risk | Est LoC | Status |
|---|---|---|---|---|
| T1 | `tools/finalize_chain_audit.py` grading harness | low  | ~590 | ✅ landed |
| T2 | Markdown link parser → `atlas_markdown_links.json` | low  | ~340 + 23 tests | ✅ landed |
| T3 | Atlas response surfaces `docs_for_segment` field | low  | ~80 + 5 tests | ✅ landed |
| T4 | Concept worker prompt receives linked-doc excerpts | med  | ~70 in seeder | ✅ landed |
| T5 | Direct `run_spaghetti_scan` call in `_audit_worker` | low  | ~12 | ✅ landed |
| T5b | Tier 2 synthesizer consumes spaghetti findings as prompt input | low  | ~150 + 10 tests | ✅ landed |
| T6 | Audit `concept_promotion.py` reachability + log | low  | docs only | ✅ landed (KEEP-AS-IS dormant) |
| T7 | ~~Audit `antibody_derivation.py` reachability~~ — verify ratio post-123 | low  | docs only | ✅ landed (false positive in 122) |
| T8 | Playwright validation + RESULTS.md | low  | ~100 | pending |
| T9 | (stretch) AGENTS.md template surfaces "Top docs by module" | med  | ~85 | ✅ landed |
| T10 | (stretch) Section-header-aware excerpt extractor (default-on, line-window opt-out) | low | ~70 + 5 tests | ✅ landed |
| T11 | Verbose telemetry (`pipeline_telemetry.jsonl`) at every Phase 124 wire-up site | low | ~190 + 11 tests | ✅ landed |
| T12 | Harness `--compare A B` + `--show-events` + per-stage metric deltas | low | ~150 | ✅ landed |

---

## 6. Tasks (operational checklist)

| ID | Task | Output / Done When |
|---|---|---|
| T1 | ✅ Build grading harness; capture baseline | `tools/finalize_chain_audit.py`; `scorecard_baseline.json` (overall 7.8/10; 4 anti-patterns flagged) |
| T2 | ✅ Markdown link parser + `atlas_markdown_links.json` | `src/prep/core/atlas/markdown_links.py` + 23 tests; first run on SourcePrep: 243 md → 1,277 valid links |
| T3 | ✅ Atlas API exposes `docs_for_segment` per segment + reset preserves `atlas_markdown_links.json` | `aggregate_for_segments` in `markdown_links.py`; `_serialize_segments` injects `docs_for_segment`; STAGE_OUTPUTS[ATLAS] updated; live: 9/10 segments have ≥1 doc |
| T4 | ✅ Concept worker prompt enrichment + `_build_module_context` extension | wired in `seed_concepts_swarm`; live measurement of "≥30% workers receive ≥1 linked doc" awaits next pipeline run |
| T5 | ✅ Direct `run_spaghetti_scan` call in `_audit_worker` | inserted at `workers.py:1090-1108` between `save_findings` and Tier 2; live mtime alignment awaits daemon restart |
| T5b | Synthesizer consumes spaghetti | `AUDIT_SUMMARY.md` cites at least one spaghetti hotspot by file/score |
| T6 | ✅ concept_promotion triaged → KEEP-AS-IS (zero callers, complementary to seeder, dormant pending UI flow) | `docs/INTENTIONALLY_DORMANT.md` |
| T7 | ✅ antibody_derivation: H3 refuted by harness (594 antibodies derived; 1:1 ratio with eligible concepts). Phase 122 flag is re-export false positive | `docs/INTENTIONALLY_DORMANT.md` |
| T8 | Re-run harness; Playwright dashboard sweep; RESULTS.md | before/after report committed in this phase dir |
| T9 | (stretch) AGENTS.md "Top docs per module" rendering | rules output includes a docs section per top-N modules |
| T10 | (stretch) Section-header-aware excerpt extractor | drop-in replacement for line-window; harness scores improve |

---

## 7. Acceptance for "done"

This phase ships when, simultaneously:

1. `tools/finalize_chain_audit.py` produces a deterministic per-stage
   scorecard for any indexed project, and `RESULTS.md` shows
   non-trivial improvement on every dimension across SourcePrep +
   ≥1 external project.
2. SourcePrep concept count is in the **30–80** range — joint
   acceptance with Phase 123 — AND ≥40% of concepts have at least
   one anchor that matches a file mentioned in a linked doc (this
   phase's specific contribution to the joint criterion).
3. `audit/spaghetti.json` is present after every pipeline run.
4. `concept_promotion.py` and `antibody_derivation.py` each have an
   explicit triage entry: either wired up (with evidence in logs)
   or recorded in `docs/INTENTIONALLY_DORMANT.md` with a reason.
5. Playwright smoke confirms the Concepts panel, Atlas panel, and
   Audit panel all render the new fields without regression.
6. `RESULTS.md` documents before/after grading-harness numbers and
   any anti-patterns the harness flagged that we *chose not* to
   fix in this phase (with rationale).

A "partial ship" (T1–T5 only, deferring T6–T8) is acceptable if T6
or T7 surface load-bearing complexity that would balloon scope —
they then become Phase 125 candidates with the harness baseline as
their measurement infrastructure.

---

## 8. Out of scope for this phase

- New atlas segmentation algorithm. Directory-based segmentation
  stays exactly as it is.
- New pipeline stage. Still 15.
- "Docs Hub" cross-cutting view in the dashboard. Deferred to a
  later phase that depends on T2 landing first.
- Embedding-based doc↔code matching. Path-mention parsing only.
- Marketing site / external docs site rendering changes.
- VS Code extension changes.
- Concept synthesis prompt tuning (Phase 123 owns this — only
  the *worker* prompt is in scope here).
- Atlas role projection / role-lens panel (Phase 104 owns this).
- Multi-repo docs. If a project's docs live in a sibling repo
  we don't see them. Acknowledged limitation, not a problem to
  solve here.
- TS/TSX JSDoc parsing. Same machinery would work but markdown
  alone is enough to validate the design.

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Markdown link parser yields false positives (paths that look like files but aren't) | low | validate against trace nodes; require resolution to a real, indexed file before linking |
| Doc excerpts blow worker-prompt token budget | med | hard cap: 500 chars × 5 docs / module; truncate at next blank line |
| Phase 123 tuning + this phase's enrichment compound and concept count overshoots 80 | med | sequencing: 124 T4 lands first; 123 measures against the new baseline; 123's "however many" prompt is then anchored |
| Playwright run flakes on dashboard reload | low | re-use existing `playwright_smoke` infrastructure; flake budget of 1 retry |
| External project benchmark requires re-indexing | low | reuse existing `.sourceprep/` if present; only rebuild on missing manifests |
| `spaghetti_scorer` wire-up bloats audit-worker latency | low | gate with try/except; downgrade to log-and-continue on failure |
| Concept-anchor field gets bloated by doc-path additions | low | keep `anchors` as code-files only; doc-path mentions go in a new `evidence_docs` field |

---

## 10. Open questions

1. **Doc excerpt strategy:** start with line-window (T4); upgrade to
   section-header-aware (T10) only if the harness shows the simple
   version is leaving signal on the table.
2. **TS/TSX JSDoc:** many React components have rich JSDoc that the
   same parser could pick up. Out of scope for v1 — markdown only.
3. **Multi-repo docs:** if docs live in a sibling repo we don't see
   them. Acknowledged limitation; out of scope.
4. **Concept anchor validation against atlas segments:** should we
   validate that a concept anchored to `src/foo.py` lives in the
   segment containing `src/foo.py`? Useful future telemetry, not in
   this phase.
5. **Should the grading harness be part of `prep_audit` itself?**
   Probably eventually. For now keep it as `tools/` so it can iterate
   without changing the MCP surface.
6. **What counts as "mention" in T2?** Inline code spans only? Bare
   path mentions in prose? Markdown link targets? Start permissive
   (all three) and let the trace-node validation filter false
   positives.

---

## 11. Pointers

| What | Where |
|---|---|
| Stage definitions (the 15 stages) | `src/prep/services/pipeline/stages.py:13-32` |
| Stage groups | `src/prep/services/pipeline/stages.py:54-78` |
| Atlas generator entry | `src/prep/core/atlas/generator.py` |
| Atlas segmentation | `src/prep/core/atlas/routing.py:100-144` (`compute_segments`) |
| Atlas segment grouping | `src/prep/core/atlas/routing.py:278-299` (`_group_by_directory`) |
| Atlas role projection | `src/prep/core/atlas/role_projection.py:79` (`.md` → `documentation` tag) |
| Module clustering (Stage 8 → `trace_modules.jsonl`) | `src/prep/core/clustering.py` |
| Concept seeder entry | `src/prep/core/concept_seeder.py:62 seed_concepts(...)` |
| Concept swarm path | `src/prep/core/concept_seeder.py:355 seed_concepts_swarm(...)` |
| Concept **worker** prompt (this phase tunes this) | `src/prep/core/concept_seeder.py:562-592` |
| Concept **synthesis** prompt (Phase 123 tunes this) | `src/prep/core/concept_seeder.py:494-516` |
| `_build_module_context` (extend with `relevant_docs`) | `src/prep/core/concept_seeder.py` (search for `_build_module_context`) |
| Concept storage | `src/prep/services/concept_store.py` |
| Audit worker (T5 wires here) | `src/prep/services/pipeline/workers.py` `_audit_worker` |
| Spaghetti scorer (built but unwired) | `src/prep/core/audit/spaghetti_scorer.py` |
| Concept promotion (suspect dormant) | `src/prep/core/concept_promotion.py` |
| Antibody derivation (suspect dormant) | `src/prep/core/antibody_derivation.py` |
| Rules generator (T9 stretch) | `src/prep/core/rules_generator.py` `_build_managed_content()` |
| Phase 82 dogfooding rubric (template for T1) | `docs/Phase82_MCP-Dogfooding/README.md` |
| Phase 122 candidate triage protocol | `docs/Phase122_FeatureUtilizationAudit/README.md` §4.2 |
| Phase 123 concept-prompt tuning | `docs/Phase123_ConceptQualityRefinement/README.md` |

---

## 12. Cross-references

- **Phase 82 (MCP Dogfooding)** — methodology template. This phase
  applies the same five-dimension rubric to *stage outputs* rather
  than to MCP tool outputs. Phase 82 graded the surface; this
  phase grades the source.
- **Phase 104 (SubAtlas)** — concurrent with this phase's atlas
  routing changes. Coordinate on the `AtlasSegmentStatus` payload
  shape so the new `docs_for_segment` field doesn't conflict with
  the existing role-overrides work.
- **Phase 110 §1.5 (intent classification)** — `prep_search` was
  observed during the research pass to fail on structural list
  queries ("list me all stages"); a `discover` intent fall-through
  would have helped. Filed as a Phase 110 follow-up, not in this
  phase's scope.
- **Phase 113 (folder reorganize / XDG state)** — `.sourceprep/`
  vs `~/.local/share/sourceprep/` location matters for T1's harness;
  read it from `prep_data_dir()` rather than hard-coding either.
- **Phase 122 (FeatureUtilizationAudit)** — Finalize-chain candidates
  (`spaghetti_scorer`, `concept_promotion`, `antibody_derivation`)
  absorbed into this phase's T5–T7. Phase 122 keeps its non-Finalize
  scope (FastAPI route triage, Storybook story triage, etc.).
- **Phase 123 (ConceptQualityRefinement)** — companion phase. T4
  here lands first; Phase 123 then tunes the synthesis prompt
  against the doc-aware worker output. Joint acceptance criterion
  documented in §7 of both phases.

---

## 13. Dogfooding notes captured during scoping

- `prep_search "15 stage pipeline order — what are stages 11 12 13 14 15"`
  returned **No symbols found**. Auto-classified as LOCATE; should
  have fallen through to DISCOVER. Symbols don't have to literally
  exist for the question to be answerable from `stages.py`.
  → Phase 110 follow-up, not blocking.
- `prep_search "previous dogfooding phase workflow"` correctly
  surfaced Phase 82, 83, 84 docs at 0.72-0.75 — strong signal,
  validating the semantic-search path.
- `prep()` ambient context flagged
  *"Concepts: 1 active, 12 seeds … 7 questions pending"* — the
  seed/active distinction means `concept_promotion.py` really is
  inert (zero seeds promoted to active). Concrete in-session
  evidence supporting H3 and the T6 audit.
- `prep_search "docs sub-atlas generation"` returned the Phase 104
  swarm-clustering plan and Phase 105 git-evidence atlas spec —
  good cross-referencing between phases. Worth noting that the
  retrieval understood "sub-atlas" as a structural concept, not a
  literal token.
- `prep_audit(action="antibodies")` not exercised in scoping; T7
  should run it as part of the reachability audit.
