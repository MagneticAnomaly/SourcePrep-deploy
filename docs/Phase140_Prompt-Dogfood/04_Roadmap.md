# Roadmap

Sequencing recommendation for the Phase 140 long-term project. Not a commitment — picks may shuffle based on findings — but a defensible "what to do next" so we don't paralyze on choice.

## Selection principles

When picking the next site to audit, balance four factors:

| Factor | Why it matters |
|---|---|
| **Methodology fit** | Early sprints should validate the snapshot/iterate/verdict discipline. Pick sites whose outputs are easy to capture, diff, and judge before tackling sites where comparison itself is hard. |
| **Iteration speed** | A site that requires a 30-minute full deep-pipeline rebuild burns research time. Prefer sites whose pipeline stage is fast to rerun, or whose outputs can be generated via direct invocation (see methodology Path B). |
| **Hypothesis density** | Sites where the grounding doc ([`03_PromptEngineeringGrounding.md`](./03_PromptEngineeringGrounding.md)) or memory records give us concrete, testable hypotheses are higher-EV than sites where "let's see what happens" is the best we can do. |
| **Blast radius** | High blast radius (e.g., AGENTS.md ships to every client project) means small wins compound. But blast radius also means iterations need extra-careful review — pair with mature methodology. |

## Sprint 1 — methodology shakedown (two sites)

Do these *before* attempting any deep-pipeline site. The goal is to prove the snapshot/iterate/verdict loop works end-to-end on the easy cases.

### Sprint 1A: [`rules-agents-md`](./prompts/rules-agents-md.md)

**Why first:** AGENTS.md content is **template-rendered, not LLM-generated**. No daemon rebuild needed — regenerating AGENTS.md is fast (`prep rules` or equivalent CLI). This lets us exercise the snapshot capture, diff workflow, and verdict-gate discipline without waiting on cloud-LLM latency or budget.

**Caveat:** Because there's no LLM behavior to study, this sprint produces no prompt-engineering insight per se. Its value is purely procedural — *we learn how to run the loop.*

**Concrete first iteration (suggested):** Audit the brand split (memory: `project_brand_split.md`). The managed block in AGENTS.md should consistently say "SourcePrep" (user-facing) and `prep` (code-level). Snapshot the current AGENTS.md across slot A (self) and slot B (a fresh small repo with `prep` initialized), check for slug leakage, and propose a single brand-split fix as the first iteration. Verdict on whether the fix improved consistency without introducing new drift.

**Sprint 1A success criteria:**
- Baseline outputs captured and committed for two repos.
- One iteration block written with hypothesis → diff → outputs → verdict.
- Snapshot directory structure works as designed in [`00_Methodology.md`](./00_Methodology.md).
- No methodology surprises left unresolved.

### Sprint 1B: [`atlas-single-doc`](./prompts/atlas-single-doc.md)

**Why second:** Smallest LLM-driven prompt site we have. One artifact per run (a single atlas doc). Pipeline stage is "fast" — should complete in minutes, not the 900-1500s the synthesizer takes. Output is plain text, easy to diff and read.

**Concrete first iteration (suggested):** Apply persona-skepticism finding from grounding §6. The atlas system prompt opens with a senior-architect persona. Run two variants on slot A + slot B + slot C:
- Variant A: current prompt (persona intact)
- Variant B: persona line removed, all other instructions identical

Capture outputs. Read side-by-side. Verdict: did persona removal materially change quality? If no measurable difference, **drop the persona** (it's costing tokens for no benefit). If quality dropped, **keep it** with note explaining the observed effect.

**Sprint 1B success criteria:**
- Multi-repo capture works (3 repos minimum).
- A grounded hypothesis (citing Zheng et al. 2024) was tested against real outputs.
- Verdict is defensible without invoking memory or vibes.
- The iteration block in `atlas-single-doc.md` reads like research, not a journal.

## Sprint 2 — first deep-pipeline audit

Once Sprint 1A and 1B are complete and the methodology is debugged, move to deep-pipeline sites where the grounding doc identified high-density hypotheses.

### Recommended Sprint 2 candidate: [`concept-validate`](./prompts/concept-validate.md)

**Why:** The grounding doc surfaced multiple concrete, independent hypotheses for this site:
1. **Confidence calibration** (grounding §7) — verify rationale-before-score ordering; if missing, that's a clean fix with literature backing.
2. **Self-preference bias** (grounding §8) — if the same model generates and validates, we may be rubber-stamping; test with a different model for validate.
3. **Few-shot omission** — Validate has no few-shot examples; T3 Refine does. Test adding 2-3 examples (accept / reject / partial).
4. **Reject-rate sanity check** (grounding §9) — instrument the validate step to report acceptance %. If <5% or >40%, the criteria are off.

Each of these is its own iteration block. Sprint 2 may legitimately have 3-4 iterations on the same site before moving on.

**Why not concept-synthesize first?** Wall-time regression (`project_synthesizer_wall_time_regression.md`) makes full reruns expensive (~1500s). Save it for after we have confidence in the methodology and have tightened up concept-validate (which feeds synthesize anyway).

## Sprint 3+ — open backlog

Order TBD based on findings from Sprint 1-2. Likely high-priority candidates:

- **`concept-t3-refine`** — few-shot examples are load-bearing; grounding §2 (Min et al. 2022) suggests they may be teaching format more than content.
- **`batch-cluster`** — cluster names are user-facing in `prep` output; "max 4 words" instruction is a cheap experiment.
- **`batch-edges`** — hallucination risk on inferred edges; grounding §10 has concrete verification suggestions.
- **`audit-tech-debt`** — verify spaghetti-scan integration (memory: `project_audit_spaghetti_migration.md`); roadmap fabrication risk.
- **`atlas-root` + `atlas-segment`** — only meaningful once Sprint 1B has shaken out atlas-single-doc; share grounding.

## Capture mechanics — getting ready for Sprint 1A

Before Sprint 1A starts, we need:

1. **Slot B picked.** [`02_TestRepos.md`](./02_TestRepos.md) — a small repo (~50 files) for AGENTS.md regeneration. Can be anything where you can run `prep` against. Recommend: pick something you already have on disk to avoid setup overhead.

2. **Capture protocol decided.** Two options for AGENTS.md:
   - **Direct copy** — after running `prep rules` (or however AGENTS.md is regenerated for a project), `cp <project>/AGENTS.md docs/Phase140_Prompt-Dogfood/snapshots/2026-05-17_baseline/outputs/rules-agents-md/<repo>.md`. Simple, no scripting.
   - **Capture script** — a small bash/Python helper under `scripts/phase140_capture.sh` that takes a site slug + repo path and writes the output to the right place. Worth investing in once we have ≥3 sites being captured regularly; YAGNI for Sprint 1A.

3. **Daemon environment recorded.** Update `snapshots/2026-05-17_baseline/README.md` Environment table with the actual values (Python version, cloud LLM model, etc.) before first capture, so the baseline is reproducible.

## Capture mechanics — getting ready for Sprint 1B

For atlas-single-doc:

1. **Slot B and Slot C need to be small enough.** Indexing slot A (SourcePrep itself) is ~minutes; if slot B or C indexes are slow, the iteration loop drags. Use `--fast` if SourcePrep supports a fast-only mode that produces an atlas without doing deep enrichment.

2. **Atlas output capture.** After daemon completes fast pass, the atlas lives at `~/.local/share/sourceprep/projects/<project-id>/atlas.md` (or similar — verify path on first capture). Copy to `snapshots/2026-05-17_baseline/outputs/atlas-single-doc/<repo-slug>.md`.

3. **A/B comparison setup.** For the persona-removal experiment, two ways to run the variant:
   - **Branch the prompt file** — `git checkout -b phase140-atlas-persona-ablation`, edit `src/prep/core/atlas/prompts.py` to remove the persona line, run rebuild, capture, then `git switch -` back to main. Clean but requires the daemon to pick up the change (which means a daemon restart per memory: `feedback_restart_daemon_before_live_validation.md`).
   - **Direct invocation harness** — write a small Python script that imports `ATLAS_SYSTEM`/`ATLAS_PROMPT`, allows overrides, runs the call with synthetic grounding, prints output. Faster iteration but grounding isn't truly production. See [`00_Methodology.md`](./00_Methodology.md) Path B.

For Sprint 1B, **Path A (branch + restart)** is the right choice — we want truthful outputs because we're producing a kept/reverted verdict.

## When the methodology breaks (and what to do)

Sprint 1A or 1B may surface methodology bugs. Common ones to expect:

- **Outputs aren't stable run-to-run.** LLM nondeterminism + retrieval ordering noise + cloud-model versioning all contribute. The fix isn't "fight the noise" — it's "capture N runs per variant and report distribution, not point estimate." Update [`00_Methodology.md`](./00_Methodology.md) if we have to add this.
- **Diff is unreadable.** If 2-page atlas docs differ in every word due to LLM rephrasing, plain `diff` is useless. Workaround: ask an LLM-as-judge for "which version better satisfies the IDENTITY/STACK/WORKSPACE-MAP/CROSS-CUTTING contract?" with position-shuffled comparison (grounding §8). Update methodology with the judge prompt.
- **Snapshot directories grow unwieldy.** If each iteration produces hundreds of MB of outputs, switch to git-lfs or store outputs as gzipped JSON. Decision deferred until it actually bites.

## Status

| Sprint | Status |
|---|---|
| 1A — `rules-agents-md` | ⏳ ready to start (waiting on slot B pick) |
| 1B — `atlas-single-doc` | ⏳ ready to start (waiting on slot B + C picks) |
| 2 — `concept-validate` | ⏳ blocked by Sprint 1A+1B completion |
| 3+ — open backlog | — |
