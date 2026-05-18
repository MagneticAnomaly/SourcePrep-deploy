# Capture notes — baseline 2026-05-17 (re-captured 2026-05-18)

> **Update 2026-05-18:** A fresh `finalize` pipeline group run completed on PowerMate at 2026-05-18T06:10-06:17 (run-id `run-402c4bc15857`, 385s total). The stale Apr 29-30 artifacts originally captured here have been replaced with the May 18 outputs. Concept records were extracted from `prep_concepts.db` directly. AGENTS.md was cleaned (legacy `codrag-managed-*` block removed — see `prompts/rules-agents-md.md` Iteration #1).


How to read what's in `outputs/` and the caveats on each file.

## How these artifacts were obtained

Slot A (SourcePrep self) and Slot B (PowerMateReborn) were **already indexed** at capture time — we did not re-run the pipeline. We copied existing artifacts from each project's daemon-state directory:

- **Slot A** — `~/.local/share/sourceprep/projects/<sourceprep-id>/` (TBD — not yet captured for slot A)
- **Slot B** — `/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/PowerMateReborn/.sourceprep/` (embedded mode)

The capture date (2026-05-17) is when we *snapshotted* the artifacts into this directory. The artifacts themselves were *generated* at varying earlier dates — see "Capture vs generation dates" below.

## What's captured for Slot B (PowerMateReborn) — current state

| Prompt site | File | Source | Generated | Notes |
|---|---|---|---|---|
| `atlas-single-doc` | `powermate-reborn.json` | `.sourceprep/atlas.json` | 2026-05-18 | **Fresh** — model `kimi-k2.6:cloud`, 1551 chars, single-segment |
| `atlas-single-doc` | `powermate-reborn-role-architect.txt` | `.sourceprep/atlas_roles/architect.txt` | 2026-04-30 | Per-role projection — not re-captured (no role-projection stage in May 18 run) |
| `atlas-single-doc` | `powermate-reborn-role-intern.txt` | `.sourceprep/atlas_roles/intern.txt` | 2026-04-30 | Same |
| `audit-summary` | `powermate-reborn.md` | `.sourceprep/audit/AUDIT_SUMMARY.md` | 2026-05-18 | **Fresh** — 50 findings, tier2 parallel, model `kimi-k2.6:cloud`, 208s |
| `audit-architecture` | `powermate-reborn.md` | `.sourceprep/audit/ARCHITECTURE_ANALYSIS.md` | 2026-05-18 | **Fresh** |
| `audit-gaps` | `powermate-reborn.md` | `.sourceprep/audit/GAP_ANALYSIS.md` | 2026-05-18 | **Fresh** |
| `audit-inventory` | `powermate-reborn.md` | `.sourceprep/audit/COMPONENT_INVENTORY.md` | 2026-05-18 | **Fresh** |
| `audit-tech-debt` | `powermate-reborn.md` | `.sourceprep/audit/TECH_DEBT_REPORT.md` | 2026-05-18 | **Fresh** |
| `audit-spaghetti` | `powermate-reborn.json` | `.sourceprep/audit/spaghetti.json` | 2026-05-18 | **New capture** — not a separate prompt site but useful audit grounding signal (memory: `project_audit_runner_schema.md`) |
| `batch-cluster` | `powermate-reborn.json` | `.sourceprep/trace_cluster_swarm_synthesis.json` | 2026-04-30 | Not re-run on 2026-05-18 (finalize group only ran atlas/rules/concepts/audit/antibodies) |
| `batch-edges` | `powermate-reborn.jsonl` | `.sourceprep/trace_inferred_edges.jsonl` | 2026-04-29 | Not re-captured |
| `batch-symbol` | `powermate-reborn.jsonl` | `.sourceprep/trace_augmented.jsonl` | 2026-04-29 | **Mixed-source file** — filter by `node_id` starting `symbol:` |
| `batch-file` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Filter by `node_id` starting `file:` with `role` set |
| `batch-doc` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Filter where `doc_type` and `doc_status` are present |
| `batch-narrative` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Narrative-only summary records |
| `epistemic-code` | `powermate-reborn.jsonl` | `.sourceprep/trace_epistemic.jsonl` | 2026-04-30 | 24 records, filter by `.swift` |
| `epistemic-doc` | `powermate-reborn.jsonl` | same as above | 2026-04-30 | Filter for `.md` |
| `concept-synthesize` | `powermate-reborn-concepts.json` | `prep_concepts.db` (66 records) | 2026-05-18 | **New capture via SQL** — Phase 125c current prompts. 6 active / 10 archived / 47 seed / 3 triage_pending |
| `concept-synthesize` | `powermate-reborn-questions.json` | `prep_concepts.db` (36 questions) | 2026-05-18 | **New capture via SQL** |
| `concept-validate` | `powermate-reborn-concepts.json` | (same file, mirrored) | 2026-05-18 | Same 66 records — `status` field reflects validate verdicts |
| `concept-t3-refine` | `powermate-reborn-concepts.json` | (same file, mirrored) | 2026-05-18 | Same 66 records — refine verdicts in `status` |
| `concept-generate` | `powermate-reborn-concepts.json` | (same file, mirrored) | 2026-05-18 | Same 66 records — seed status (47) shows pre-validate state |
| `rules-agents-md` | `powermate-reborn.md` | `PowerMateReborn/AGENTS.md` (repo root) | 2026-05-18 cleanup | **Fresh + manually cleaned** — codrag legacy block removed (see Iteration #1) |
| `_run-metadata` | `powermate-reborn-pipeline-2026-05-18.json` | `.sourceprep/pipeline_run_metadata.json` | 2026-05-18 | **New** — provenance for the fresh run |
| `_run-metadata` | `powermate-reborn-concept-generate-2026-05-18.json` | `.sourceprep/concept_generate_manifest.json` | 2026-05-18 | **New** — Generate stage stats: swarm_size=3, prompt_revision=2 |

## Capture vs generation dates

This baseline is a **rolling capture** — different artifacts were generated at different points in time, all before the 2026-05-17 snapshot date.

Why this matters: the prompt-file SHAs recorded in [`README.md`](./README.md) are *current* (as of 2026-05-17). The artifacts may have been produced by *earlier* versions of those prompts. Specifically:

### Known prompt-source drift since artifacts were generated

Between 2026-04-25 and 2026-05-17, the following prompts changed substantially (per `git log`):

- **Phase 125c work (`fd5356e7`, `fd657f9e`, `b2106223`)** — concept prompts (`concept_synthesizer.py`, `concept_validate_prompt.py`, `concept_generate_prompt.py`, `concept_t3_refine.py`) were rewritten for the quality-checked swarm. **Concept-site captures should be considered "pre-Phase125c historical reference" and re-captured before any iteration verdict.**
- **Phase 134 (`a0ec7242`, `d1f5719b`, `bd832755`)** — changeset-driven pipeline. May have changed `epistemic_enrichment.py` plumbing but probably not the prompt strings themselves. Worth verifying with `git diff <old-sha>..HEAD src/prep/core/epistemic_enrichment.py`.

### Sites whose captures are likely still valid as baselines

- `atlas-*` — `atlas/prompts.py` not touched since ~2026-04
- `audit-*` — `audit/prompts.py` not touched since ~2026-04
- `batch-*` — `batch_prompts.py` not touched since ~2026-04
- `rules-agents-md` — see below (template, not LLM; but content was generated pre-rename)

Treat the "validity" line as a best-effort estimate. If in doubt for a specific site, run `git log -- <prompt-file>` and compare against the artifact generation date.

## First finding (revised after 2026-05-18 deeper inspection)

**Site:** `rules-agents-md`
**Finding:** The rules-generator stage DID successfully run on 2026-05-18T06:11:01Z — but it **appended** a fresh `prep-managed-*` block instead of **replacing** the legacy `codrag-managed-*` block. PowerMate's AGENTS.md ended up 196 lines with two managed blocks side-by-side, two atlases, two tool tables, two project IDs.

**Verdict (user 2026-05-18):** Don't fix the rules-generator's legacy-marker handling. Manually clean up the affected files when encountered.

**Action:** Deleted the codrag block from PowerMate's AGENTS.md. File now 103 lines. Snapshot re-captured.

**Audit:** Our own repo's AGENTS.md is clean — `grep -c codrag-managed AGENTS.md` returned 0. PowerMate was the only file affected in Phase 140 scope.

Full iteration record: [`../../prompts/rules-agents-md.md`](../../prompts/rules-agents-md.md) Iteration #1.

## What's NOT captured for Slot B

- **`atlas-root` / `atlas-segment`** — PowerMate is single-segment, so these are N/A. Need a multi-segment slot D for these.
- **`hr-*` / `custodian-*` / `researcher-*` (7 sites)** — agent prompts that only fire when the corresponding agent is invoked. PowerMate has never been used as input to the HR/Custodian/Researcher agents. Capture deferred until an agent run is done.
- **`batch-*` and `epistemic-*` were NOT re-captured on 2026-05-18** — the finalize-group pipeline run only re-ran atlas/rules/concepts/audit/antibodies, not the augment/epistemic stages. The Apr 29-30 captures still represent the current state of those artifacts. If those prompt sources change, a deep-pipeline rerun is needed before re-capture.

## Updated capture counts (2026-05-18)

| Bucket | Captured | of total |
|---|---|---|
| LLM-driven prompt sites | 18 | 30 |
| Plus structural artifacts (audit-spaghetti, run-metadata) | 2 | — |
| Concept records (via SQL) | 66 concepts + 36 questions | — |
