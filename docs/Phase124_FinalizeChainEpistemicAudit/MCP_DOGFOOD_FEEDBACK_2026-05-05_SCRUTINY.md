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

## Honest meta-observation about the scrutiny

The most useful thing this exercise produced was catching that I had *quoted a number wrong*. The "0 active, 1590 seeds" claim from May 2 was confidently asserted but came from misreading a category-sum as a status-sum. That's exactly the kind of soft-confidence error agents make when they read trailers as structured data without parsing them.

This is itself product feedback: **the `prep` trailer format is parseable-looking enough that an agent will treat it as structured, but ambiguous enough that the parsing can be wrong.** A machine-readable variant (or just a `[concepts: active/total, rationale: active/total]` strict format) would prevent this class of error.
