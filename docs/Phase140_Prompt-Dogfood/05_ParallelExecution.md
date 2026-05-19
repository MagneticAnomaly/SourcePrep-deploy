# Parallel execution plan — split work between two AI sessions

**Created:** 2026-05-19
**Status:** plan, not yet executing
**Pattern:** 30 sites → groups of 3 → 10 pipeline-test cycles → split 15/15 between AI A and AI B

## Goal

Phase 140 has 30 prompt sites to audit. The methodology (snapshot → analyze → hypothesize → edit → rebuild → re-capture → verdict) takes ~1-2 hours per group of 3 sites when edits are non-trivial, plus a ~6-7 minute pipeline rerun (PowerMate finalize-group) or 20-30 minutes (deep pipeline if augment/epistemic stages touched).

Doing all 10 cycles in one AI session is feasible but slow. Splitting the 30 sites between two AI sessions cuts wall-clock roughly in half.

This doc tells **AI A** (a fresh session, not the one that wrote Phase 140 so far) exactly what to do, and tells **AI B** (the existing session continuing this work) where to focus. It's self-contained: an AI dropped into this repo with no prior context can read this doc + the four it references and start working.

## The split

15 sites each, grouped into 5 groups of 3. Each group ends with one PowerMate pipeline rerun + diff.

### AI A — 15 sites (5 groups)

| Group | Sites | Pipeline stage hit by rerun |
|---|---|---|
| **A1** | `atlas-single-doc`, `atlas-root`, `atlas-segment` | atlas (fast — ~15s) |
| **A2** | `audit-summary`, `audit-architecture`, `audit-gaps` | audit (~210s) |
| **A3** | `audit-inventory`, `audit-tech-debt`, `batch-symbol` | audit + augment (deep ~30 min) |
| **A4** | `batch-file`, `batch-doc`, `batch-narrative` | augment (deep ~30 min) |
| **A5** | `researcher-topic`, `researcher-research`, `researcher-plan` | researcher agent invocation only — no full rebuild |

### AI B — 15 sites (5 groups) — the existing session

| Group | Sites | Pipeline stage hit by rerun |
|---|---|---|
| **B1** | `concept-validate`, `concept-synthesize`, `concept-t3-refine` | concepts (~165s) — already analyzed Validate, see Iteration #1 |
| **B2** | `concept-generate`, `batch-edges`, `batch-cluster` | concepts + augment (deep) |
| **B3** | `batch-epi-code`, `batch-epi-doc`, `epistemic-code` | augment + epistemic (deep) |
| **B4** | `epistemic-doc`, `hr-agents-md`, `hr-soul-md` | epistemic + HR agent |
| **B5** | `hr-auto-roles`, `custodian-safety`, `rules-agents-md` | HR + Custodian + rules (~0.01s) — already cleaned PowerMate AGENTS.md, see Iteration #1 |

### Why this split

- **AI A gets fresh families.** Atlas, audit, researcher have no existing iteration work. A fresh perspective avoids confirmation bias. AI A also gets the doc-focused batched prompts (file/doc/narrative), which pair with audit thematically.
- **AI B continues what it started.** Concept family (already analyzed Validate), rules-agents-md (already cleaned PowerMate AGENTS.md), and the graph/epistemic-focused batched prompts (edges/cluster/epi-code/epi-doc).
- **Batched 8-prompt family split 4/4** to balance the heaviest family across AIs.
- **Atlas → AI A** even though AI B already captured atlas baseline — fresh persona-removal A/B test (see [`03_PromptEngineeringGrounding.md`](./03_PromptEngineeringGrounding.md) §6) belongs to a fresh reader.

## Required reading (both AIs, in order)

Before touching any prompt or running any pipeline:

1. **[`README.md`](./README.md)** — phase overview, status table, cross-refs.
2. **[`00_Methodology.md`](./00_Methodology.md)** — the five non-negotiables (snapshot before mutating, one prompt at a time, verdict gate, multi-repo discipline, file-based output capture). Read this slowly. Iterations that skip these rules produce un-defensible verdicts.
3. **[`01_Inventory.md`](./01_Inventory.md)** — master table of all 30 sites. Find your assigned sites in this table; click through to the `prompts/<slug>.md` page for each.
4. **[`02_TestRepos.md`](./02_TestRepos.md)** — PowerMate is Slot B and is the primary test repo until further notice. Slot A (SourcePrep self) and Slot C are still TBD.
5. **[`03_PromptEngineeringGrounding.md`](./03_PromptEngineeringGrounding.md)** — 12 sections of research canon mapped to our P1-P10 pattern buckets. Cite from here when proposing iterations; do not propose "feels better" changes.
6. **[`04_Roadmap.md`](./04_Roadmap.md)** — sequencing intent + Sprint 1/1B/2 status. Tells you what's already done so you don't re-do it.
7. **[`snapshots/2026-05-17_baseline/capture-notes.md`](./snapshots/2026-05-17_baseline/capture-notes.md)** — exactly what's been captured for Slot B, what's stale (`batch-*` from Apr 29-30 if you need them for audit), what's missing.
8. **Existing iteration examples** — open these to see the expected style and rigor:
   - [`prompts/rules-agents-md.md`](./prompts/rules-agents-md.md) Iteration #1 — structural finding, user declined to fix in code
   - [`prompts/concept-validate.md`](./prompts/concept-validate.md) Iteration #1 — substantive analysis with quoted evidence, two-path recommendation
   - [`findings/concept-pipeline-grounding-gap.md`](./findings/concept-pipeline-grounding-gap.md) — example of a cross-cutting finding written when a pattern affects ≥3 sites

You don't need to read every per-site stub. You'll open them as you work each group.

## The cycle per group of 3 (concrete steps)

For each of your 5 groups, in order:

1. **Read the 3 baseline captures.** Open each site's `prompts/<slug>.md`, follow the Snapshot section link to the PowerMate output file under `snapshots/2026-05-17_baseline/outputs/<slug>/`. Read all three baselines before forming hypotheses — patterns often emerge across sites.

2. **Open the prompt source for each.** The site stub gives you the file path + line numbers. Read the prompt copy.

3. **Form a hypothesis per site** that cites the grounding doc when possible. Write it in a new iteration block in `prompts/<slug>.md` (template in [`prompts/README.md`](./prompts/README.md)). Hypothesis must name the failure mode it addresses.

4. **Decide for each site: edit-and-test, or analysis-only.**
   - **Analysis-only** is fine when the right fix is structural / upstream (like B's Iteration #1 on concept-validate). Document the finding, link to `findings/` if cross-cutting, no prompt edit. Verdict = "analysis (no edit)."
   - **Edit-and-test** when the change is a clean prompt-copy edit. Edit the prompt source file. Single change per iteration block — no batching.

5. **If any of the 3 had a prompt edit**, run the pipeline once:
   - **Restart the daemon first** (memory `feedback_restart_daemon_before_live_validation.md` — no hot-reload).
     ```bash
     # however the user starts the daemon — typically:
     pkill -f 'prep serve' && sleep 2 && prep serve &
     ```
   - **Trigger the relevant pipeline group** on PowerMate. Check the existing artifacts to figure out the exact endpoint. The daemon HTTP API is at `:8400`. The `finalize` group covers atlas/rules/concepts/audit/antibodies (~6 min). The `deep` group covers augment/epistemic (~30 min).
   - **Wait for completion** — `pipeline_run_metadata.json` will have a fresh `run_id` and `status: completed`.

6. **Re-capture** the affected artifacts into a NEW snapshot directory:
   ```
   snapshots/YYYY-MM-DD_<group-id>/outputs/<slug>/powermate-reborn.{json,md,jsonl}
   ```
   Don't overwrite the baseline. The naming convention is `YYYY-MM-DD_<group-id>-<verdict>` after the verdict is decided (e.g., `2026-05-19_A1-kept`).

7. **Diff** new outputs vs baseline. For JSON: use `jq` + `diff`. For markdown: `diff -u` or read side-by-side. For .jsonl: filter to the records affected by the change. Don't paste full outputs into the iteration block — quote 3-5 relevant lines and link to the snapshot file.

8. **Verdict each site** (`kept` / `reverted` / `partial` / `analysis`). Update the iteration block. If `kept`, re-baseline that site's snapshot.

9. **Commit per group.** Commit message format:
   ```
   docs(phase140): {A,B}<N> — <one-line summary>
   ```
   E.g., `docs(phase140): B2 — concept-generate worker scoping (kept), batch-edges substring-match (kept), batch-cluster name-length cap (reverted)`. Body should list verdicts per site.

10. **Move to next group.** Don't batch multiple groups before committing — the user wants the verdict cadence to be visible.

## Coordination protocol (avoiding stepping on each other)

### File-level conflict avoidance

Each AI ONLY writes to:
- `prompts/<their-15-sites>.md` — own iteration entries
- `findings/<new-finding>.md` — each new finding is its own file, unique name
- `snapshots/YYYY-MM-DD_<their-group-id>/` — own snapshot dirs
- Shared docs (`README.md`, `01_Inventory.md`, `04_Roadmap.md`) — see "Shared-doc updates" below

Each AI ONLY edits prompt source files they own (per the split table). If you find a structural issue affecting another AI's site, write a finding under `findings/` and reference it. Don't edit their prompts.

### Daemon serialization

There's one daemon and one PowerMate. Pipeline runs cannot overlap.

**Soft protocol:** announce in your commit message when you're about to start a pipeline run ("running A2 pipeline now"). Watch the other AI's recent commits before kicking off your own. If timing is tight, the user can act as orchestrator and ask one AI to pause.

**Hard protocol** (if soft protocol fails): use a lock file. `touch .phase140-pipeline-lock` before running; `rm` after capturing. Other AI must wait if the lock exists.

For now, default to soft protocol. Real conflicts are rare given groups take 1-2 hours of analysis between pipeline runs.

### Shared-doc updates

`README.md`, `01_Inventory.md`, `04_Roadmap.md` are touched by both AIs. To avoid merge conflicts:

- Pull / `git fetch && git rebase` before editing a shared doc.
- Keep edits to shared docs minimal — update only the status badges / status table / sprint status row for your own sites.
- Don't restructure shared docs — propose restructure as a separate discussion before editing.

If a merge conflict happens anyway, the resolution is usually: accept both AI's iteration counts and sum them (e.g., "Sites with at least one iteration entry: 3" + "Sites with at least one iteration entry: 4" → "Sites with at least one iteration entry: 7").

### Findings/ cross-references

If you write a finding in `findings/<your-finding>.md` and it affects sites the other AI owns, reference those sites in the finding's "Cross-references" section. The other AI is expected to read findings/ before each new group — they'll see your finding and incorporate it into their own analysis.

If a finding requires the other AI to revisit a site they already verdict'd, note it in the finding and let the user decide whether to reopen.

## What's already done (don't redo)

- **30 prompt sites inventoried** — see `01_Inventory.md`.
- **18 Slot B (PowerMate) captures** — atlas, all 5 audit pages, all 4 batched-aug pages, both epistemic, all 4 concept (via SQL extract from `prep_concepts.db`), audit-spaghetti, rules-agents-md (post-cleanup). Listed in `snapshots/2026-05-17_baseline/capture-notes.md`.
- **3 iteration entries:**
  - `rules-agents-md` Iteration #1 — double-block bug, manually cleaned PowerMate AGENTS.md, user declined to fix rules-generator in code.
  - `concept-validate` Iteration #1 — full analysis of 53% reject rate, diagnosed as upstream grounding-gap (Path A out-of-scope). No prompt edit.
  - `concept-generate` observation — cross-ref to concept-validate finding.
- **1 cross-cutting finding** — `findings/concept-pipeline-grounding-gap.md`.

Don't re-analyze these. If you have a different read, write a follow-up iteration in the same site page (Iteration #2) rather than overwriting.

## Open questions / handoff items

- **Slot A (SourcePrep self) not yet captured.** Whoever needs symmetric A/B comparison first should capture it. Process: query `~/.local/share/sourceprep/projects/f1636374-abc6-410d-99ee-822120379e79/` for the project's artifacts and `prep_concepts.db` for concepts (project_id `f1636374-abc6-410d-99ee-822120379e79`).
- **Slot C (third repo) not picked.** Slot B (PowerMate, Swift) gives non-Python diversity. Slot C should be a small Python lib OR a doc-heavy repo to stress doc-classification prompts. Pick when needed.
- **`atlas-root` / `atlas-segment` have no Slot B baseline** because PowerMate is single-segment. AI A's Group A1 will need a multi-segment repo (slot D) to capture these. Defer or pick a quick multi-segment fixture.
- **Agent prompt sites (`hr-*`, `custodian-*`, `researcher-*`) have no PowerMate baselines** because those agents have never been run against PowerMate. Whoever owns those groups (AI A's A5, AI B's B4-B5) needs to either (a) run the agent against PowerMate first, or (b) pick a different repo for those sites.

## Estimates

Per group (3 sites, 1 pipeline run):
- **Analysis-only group** (no edits, no rerun): 1-1.5 hours.
- **Single-edit group** (1 of 3 sites edited, finalize-group rerun): 2-3 hours.
- **Multi-edit group with deep rerun** (augment/epistemic touched, 30-min pipeline): 3-5 hours.

Total per AI (5 groups, mixed mode): roughly 12-20 hours of focused work, plus pipeline wait time. Splittable across multiple sessions.

## When you're done with a group

End-of-group checklist:
- [ ] All 3 site pages have an Iteration block with a verdict
- [ ] If any site verdict is `kept`, snapshot is re-baselined under a new dated dir
- [ ] Any cross-cutting findings written to `findings/`
- [ ] `01_Inventory.md` status badges updated for the 3 sites
- [ ] `README.md` status table iteration count bumped
- [ ] One commit with `docs(phase140): {A,B}<N> — <summary>` format
- [ ] No prompt source files left in a partially-edited state (e.g., didn't revert a `reverted` verdict)

When all 5 of your groups are done, write a summary in this doc's "Status" section below.

## Status (update as work progresses)

| AI | Group | Status | Verdicts | Notes |
|---|---|---|---|---|
| B | B1 | ✅ complete (2026-05-19) | all 3 sites: `analysis` — no prompt edits made | Both pre-existing findings (grounding-gap) reverified; new finding: concept-t3-refine is unwired in production pipeline ([`findings/concept-t3-refine-unwired.md`](./findings/concept-t3-refine-unwired.md)) |
| B | B2 | ✅ complete (2026-05-19) | all 3 sites: `analysis` — concrete EVIDENCE RULES edit proposed for batch-edges (deferred to follow-up rerun); concept-generate scope-tighten observation; batch-cluster snapshot gap | concept-generate Iteration #2 documents the `SYNTH_SYSTEM_PROMPT` reuse pattern (Generate ↔ Synthesize prompt edits couple); batch-edges proposes a 72%-noise-suppression EVIDENCE RULES clause |
| B | B3 | ✅ complete (2026-05-19) | all 3 sites: `analysis` — cross-cutting finding written | Single-file `EPISTEMIC_CODE_PROMPT`'s `tech_debt` instruction completely ignored (26/26 items in 5-file sample are design critiques, not TODO/FIXME). Schema-drift: model emits richer structured objects than schema spec (cross_references / decision_chains / tech_debt) — recovering quality from too-thin schema. Batched epistemic prompts dropped the field-level guidance the single-file siblings carry — BYOK users get under-steered output. See [`findings/epistemic-batched-vs-single-guidance-gap.md`](./findings/epistemic-batched-vs-single-guidance-gap.md). |
| B | B4 | pending | — | — |
| B | B5 | partial — rules-agents-md cleanup done; hr-auto-roles/custodian-safety pending | rules-agents-md: cleanup verdict | — |
| A | A1 | pending | — | needs multi-segment repo for atlas-root/atlas-segment |
| A | A2 | pending | — | — |
| A | A3 | pending | — | — |
| A | A4 | pending | — | — |
| A | A5 | pending | — | needs Researcher agent runs on PowerMate first |

## Handoff message to AI A (paste this into a new session if launching one)

> You are AI A in a parallel Phase 140 Prompt-Dogfood execution. Your scope is 15 prompt sites split into 5 groups (atlas, most of audit, doc-focused batched, researcher).
>
> Read `docs/Phase140_Prompt-Dogfood/05_ParallelExecution.md` first. It tells you which 15 sites you own, the cycle to follow per group of 3, and where to find the methodology + grounding + inventory + baseline captures.
>
> Start with Group A1 (`atlas-single-doc`, `atlas-root`, `atlas-segment`). Note that PowerMate is single-segment so atlas-root and atlas-segment need a different test repo — either pick a multi-segment repo or document the deferral and move atlas-single-doc only, then jump to A2.
>
> The other AI (B) is continuing the concept family and rules-agents-md. Don't touch B's sites or their prompt source files. If you find a structural issue affecting B's sites, write a finding under `findings/` and cross-reference.
>
> Commit per group with `docs(phase140): A<N> — <one-line summary>`.
