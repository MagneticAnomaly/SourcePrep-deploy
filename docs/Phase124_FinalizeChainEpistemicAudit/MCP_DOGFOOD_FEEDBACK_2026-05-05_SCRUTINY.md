# MCP Dogfood Feedback — Scrutiny Pass — 2026-05-05

Companion to `MCP_DOGFOOD_FEEDBACK_2026-05-02.md`. The user asked me to second-guess and scrutinize the prior feedback. I re-ran the same `prep` call plus two probes (`prep_audit(action="antibodies")` and `prep_concepts(...)`). Two of three prior claims were wrong. Two new findings emerged. This doc supersedes the prior doc where they conflict — see the cross-reference table at the end.

---

## Reproducer

```python
prep(project_id="f1636374-...", task="conduct a full security audit of the SourcePrep codebase", role="security")
prep_audit(project_id="f1636374-...", action="antibodies")
prep_concepts(project_id="f1636374-...", action="get", status="active")
prep_concepts(project_id="f1636374-...", action="get", category="security")
```

---

## Correction to prior #1 — "0 active / 1590 seeds" was a misread

**Prior claim.** Concept promotion appears stuck at `0 active / 1590 seeds`.

**Today's trailer reads:**

> `[21 concepts (17 active, 4 seed) + 180 module rationale (0 active, 180 seed) — browseable via prep_search — architecture: 8, decision: 4, constraint: 3, security: 2, +4 more.]`

**What was actually happening.**
- The "1,590" number I quoted was a **sum of category counts** (`architecture: 350 + technical: 235 + product: 204 + process: 203 + ...`), not a count of seeds. I conflated category breakdown with status breakdown.
- Reality: regular concepts have a healthy promotion ratio (**17 of 21 active = 81%**).
- Where there *is* a real 0-promotion problem: **module rationale** (180 seed, 0 active). These appear to be a separate, auto-generated corpus.

**Residual real issue.** The trailer aggregates two semantically distinct stores (`concepts` and `module rationale`) into one line, then breaks down by *category* without breaking down by *status* per store. That is precisely the format that misled me. An agent reading "0 active, 1590 seeds" as I did in May 2 will draw exactly the wrong conclusion: that the entire concept promotion pipeline is broken, when in fact only one of the two stores is at zero.

**Open question — not a bug yet.** Is `module rationale` *supposed* to be all-seed (i.e. these are bulk auto-summaries that never get promoted), or should they go through the same promotion path? If the former, the line item is fine but the trailer should label it as such. If the latter, there's a real backlog of 180 unpromoted rationales.

**Severity: Medium** — output format ambiguity that produced a false agent inference. Cheap fix (split status from category in the trailer; or split the two stores into two lines).

---

## Correction to prior #3 — antibodies aren't silent, they crash

**Prior claim.** No antibody alerts surface on a security-framed `prep` call; possibly downstream of broken concept promotion.

**Reality.** `prep_audit(action="antibodies")` returned a hard error:

```
MCP error -32603: AntibodyStore not initialized.
Call antibody_store.init(db_path) first.
```

**Why this is worse than I thought.**
- The store isn't empty — it's not initialized. That's a daemon-bootstrap or lazy-init bug, not a "no concepts ⇒ no antibodies" symptom.
- There ARE 17 active concepts, including **two security-tagged constraints** that should be generating antibodies:
  1. `Custodian agent as manifest-enforcing governance layer` — assertion: *"Agent execution without custodian manifest validation, or custodian bypass via direct adapter instantiation"*
  2. `Observation attribution as non-repudiable provenance for agent artifacts` (seed) — assertion: *"Agent-generated artifact without cryptographically bound observation chain"*
- So the substrate exists, the constraints exist, but the antibody store never gets initialized to derive them.

**Mismatch between `prep` (no error) and `prep_audit(action="antibodies")` (hard error).** The role-projected `prep` view simply omitted the immune-system block — no error surfaced — but the dedicated tool throws. This means an agent calling only `prep` will conclude "no antibodies, fine" while `prep_audit` is screaming. Tool surfaces should agree.

**Severity: High** — a flagship feature (immune system) is non-functional via the documented entry point. Worth a Phase 124/125 ticket.

---

## Prior #2 stands — role projection still leaks marketing modules

**Re-confirmed today.** With `role="security"`, the "Modules in scope" list still includes:

- Guerrilla Marketing Copy Engine (13 files)
- Community-Driven User Acquisition Campaign Engine (12 files)
- Developer Community Launch Campaign Engine (10 files)
- Prep Product Go-to-Market Content Engine (9 files)
- Developer-Facing Marketing Content Pipeline (6 files)
- Marketing Site SEO & Content Governance Layer (5 files)
- Marketing Website Presentation Layer (7 files)
- Multi-Tenant Next.js Web Properties (10 files)
- Tremor Theme Preview Sandbox (9 files)

The "Relevant Files" tail block IS correctly weighted (security audit docs, license/payment, Tauri config, webview CSP, audit_log.py). So the role weighting is plumbed into file ranking but not module ordering.

**No change to the original recommendation.** Either apply role weights to module emission or label the modules section as role-agnostic.

**Severity: Low–Medium** — agents that read top-down will form a generic mental model from the longest section in the response.

---

## NEW — #4: Role projection output contains a leaked LLM prompt fragment

**This is the biggest find of the scrutiny pass.** The "Security Engineer View" header — which should contain a security-framed orientation paragraph — instead contained:

> `[Security Engineer View]`
> `I need to write a concise project orientation header based on the provided data, following strict rules: plain text only, no markdown, no bold, no headers, no bullet characters, no asterisks. every claim from provided data, exact names, maximally dense,ooooooooo short, under 2570 characters, no invented info.`

**What this means.**
- The LLM's own instructions to itself were rendered into the user-visible output verbatim.
- Note the typo: `maximally dense,ooooooooo short` — looks like a stuck-key in the source prompt template. That typo is now leaking to every consumer.
- This is the *primary* role-view output. The role projection is effectively non-functional — it's emitting prompt boilerplate instead of generated text.

**Likely causes (worth investigating in this order).**
1. The role-view LLM call failed/empty-returned and the formatter fell back to printing the prompt as the result.
2. The prompt template uses a placeholder that wasn't substituted, so the literal instructions reached the output stream.
3. The LLM is genuinely returning its own instructions (rare; would point at prompt-engineering issue).

**Severity: High** — public-facing output quality regression in the most user-prominent slot of the role view.

**Audit trail.** First call (May 2) had a coherent IDENTITY/STACK paragraph in the same slot. Second call (May 5) has the leaked prompt. So this regressed in the last 3 days OR is non-deterministic and we're catching it on a bad sample. Either way: needs a deterministic check.

---

## NEW — #5: Module counts drift between consecutive calls

**Observed.** Comparing identical `prep(role="security")` calls 3 days apart:

| Module | May 2 | May 5 |
|---|---|---|
| Enterprise Security & Licensing Governance | 22 files | 24 files |
| Enterprise Security Audit & Compliance Dashboard | 20 files | 14 files |
| Enrichment Pipeline Orchestrator & State Machine | 25 files | 25 files |
| (smaller modules tail) | 115 + 483 | 193 + 715 |

The smaller-modules tail nearly doubled (115 → 193 and 483 → 715) — that scale of change in 3 days is implausible from organic code growth alone. Either:

- The atlas was rebuilt with different module-clustering thresholds (legitimate), or
- The clustering is non-deterministic across rebuilds (bug — agents will see structure shifting under them), or
- Index drift / stale cache is mixing fresh and old segments.

**Severity: Medium** — affects agent trust. If structural maps are unstable across hours/days, agents can't reason about them as ground truth.

**Suggested next step.** Add a determinism test: rebuild atlas twice on identical input; assert module count, file-per-module count, and ordering match. If clustering is intentionally probabilistic (e.g. embeddings-driven), document that and stamp the atlas with a generation seed/timestamp.

---

## Cross-reference with 2026-05-02 doc

| 2026-05-02 claim | Status today | Note |
|---|---|---|
| #1 Concepts 0/1590, promotion broken | **Wrong** — was a category sum, not a status sum. Real ratio is 17/21 (active concepts) and 0/180 (module rationale). Trailer aggregation is the actual bug. | Correction above |
| #2 Role projection leaks marketing modules | **Correct, re-confirmed** | Carry forward |
| #3 Antibodies silent on security call | **Partly wrong** — they're not silent; the dedicated tool throws `AntibodyStore not initialized`. | More serious bug than I described |
| (none) | **#4 NEW** — role view emits leaked LLM prompt verbatim | Highest-impact find |
| (none) | **#5 NEW** — module counts drift across calls | Worth a determinism check |

---

## Resolution status (2026-05-06)

Two of the five findings landed code fixes this session.

### #4 (HIGH) — Atlas role-projection prompt leak: **FIXED**

Root cause confirmed by inspecting `.sourceprep/atlas.json` directly: the cached `content` field contained the model's first-person prompt restatement ("I need to write a concise project orientation header...") followed by 1500+ chars of `加油` repetition (a token-loop sampler artifact). The existing quality gate at `src/prep/core/atlas/generator.py:567` only checked for **short** content (`len < MIN_ATLAS_CHARS // 2`). Long-but-garbage output passed and was persisted, then served to every MCP client thereafter.

Fix:

- New module `src/prep/core/atlas/validators.py` with three detectors: prompt-leak (first-person openers), repeat-attack (single-char + 2-4-char n-gram loops, observed-loop-aware threshold), missing-section markers.
- Wired into all four LLM call sites in `generator.py` (single-doc, root, segment, segment-with-angle) — bad output now triggers the existing structural fallback.
- `load()` re-runs the validator over cached content; poisoned caches return `None` so `is_stale()` reports stale and regen self-heals on the next pipeline pass.
- 22 unit tests in `tests/test_atlas_validators.py` + 2 integration tests in `tests/test_atlas.py::TestLLMAtlas` covering the actual observed bad-content shape.
- Existing 91 atlas tests still pass.

The poisoned cache on this repo (`/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/atlas.json`) does not need manual deletion — `load()` will reject it and the next `prep` regen will overwrite.

### #3 (HIGH) — `AntibodyStore not initialized`: **PARTIALLY FIXED**

Root cause: the MCP server runs in a separate process from the FastAPI daemon (server-mode default). `server.py:972` initializes `antibody_store` at daemon startup, but the MCP-side singleton in the separate process was never reached. `_require_conn()` threw on the first `prep_audit(action="antibodies")` call.

Fix landed:

- `src/prep/services/antibody_store.py` `_require_conn()` now lazy-initializes from the canonical `data_dir() / "prep_antibodies.db"` when called on an uninitialized store. Falls back to the old explicit-error message only if `data_dir()` itself fails.
- 3 tests in `tests/test_antibody_store_lazy_init.py` covering: lazy-init from data_dir, save+list after lazy-init, and verifying explicit `init()` (the daemon path) still works.

**Remaining work** (filed as Task #6 follow-up): even with init working, derived antibodies stay invisible to `prep()` because of a separate status-field mismatch — `antibody_derivation.py:59,77` writes `status='testing'` but `immune_watcher.py:50` queries `status='active'`. Master TODO tracks this as a Phase 125 §13 candidate; semantics differ from concept promotion enough to warrant its own phase.

### Pre-existing test failures noted, not addressed

`tests/test_atlas_endpoints.py` has 5 pre-existing failures (`_FakeAtlas` mock missing `index_dir` attr — a Phase 124 T3 fixture issue). `tests/test_resume_strategy.py` has flaky failures unrelated to this work. `tests/test_concept_store_save_many.py`, `tests/test_temporal_validity.py`, `tests/test_concept_seeder_swarm.py`, `tests/test_agent_prep_data.py`, `tests/test_agent_core.py` each have 1-2 failures that reproduce on `main` with my changes stashed. Out of scope for this session.

### 2026-05-06 scrutiny pass — additional gaps caught and closed

A second-pass review caught three real gaps in the original fixes:

1. **Segment atlas load was unvalidated.** The original Task #2 fix added the validator to `load()` for the root atlas only. `_load_segment()` and `load_segments()` still served poisoned cached segment content. Closed: both methods now run the validator and skip rejected entries; new `test_load_segments_skips_poisoned_caches` covers the behaviour.

2. **ConceptStore + ObservationStore had the same lazy-init vulnerability.** The original Task #1 fix only patched AntibodyStore. Both other stores have an identical `_require_conn` pattern that throws when reached from a non-daemon process (e.g. standalone MCP). Closed: same lazy-init bootstrap added to both; `test_concept_store_lazy_init` and `test_observation_store_lazy_init` cover them.

3. **Test fixtures used unrealistic atlas/segment content** that the new validator correctly flagged. Updated five fixtures in `test_atlas.py` to use realistic `IDENTITY:` / `SEGMENT:` markers instead of placeholder strings. The validator-rejection messages were the diagnostic — fixtures, not validator, were wrong.

**What was deliberately NOT fixed.** Master TODO Task #7 (`antibody_derivation.py:59,77` writes `status='testing'` while `immune_watcher.py:50` queries `status='active'`) is now reachable since lazy-init works, but master TODO recommends keeping it as a separate phase: the `testing` status is intentional (auto-derived antibodies need a vetting period). Changing semantics here is a product decision, not a bug fix. Tracked as Task #7 for now.

After this scrutiny pass: **149/149 touched-area tests pass, 0 regressions introduced** (verified by stashing changes and re-running — same 8 failures on `main` without my work).

---

## Honest meta-observation about the scrutiny

The most useful thing this exercise produced was catching that I had *quoted a number wrong*. The "0 active, 1590 seeds" claim from May 2 was confidently asserted but came from misreading a category-sum as a status-sum. That's exactly the kind of soft-confidence error agents make when they read trailers as structured data without parsing them.

This is itself product feedback: **the `prep` trailer format is parseable-looking enough that an agent will treat it as structured, but ambiguous enough that the parsing can be wrong.** A machine-readable variant (or just a `[concepts: active/total, rationale: active/total]` strict format) would prevent this class of error.
