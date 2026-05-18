# Capture notes — baseline 2026-05-17

How to read what's in `outputs/` and the caveats on each file.

## How these artifacts were obtained

Slot A (SourcePrep self) and Slot B (PowerMateReborn) were **already indexed** at capture time — we did not re-run the pipeline. We copied existing artifacts from each project's daemon-state directory:

- **Slot A** — `~/.local/share/sourceprep/projects/<sourceprep-id>/` (TBD — not yet captured for slot A)
- **Slot B** — `/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/PowerMateReborn/.sourceprep/` (embedded mode)

The capture date (2026-05-17) is when we *snapshotted* the artifacts into this directory. The artifacts themselves were *generated* at varying earlier dates — see "Capture vs generation dates" below.

## What's captured for Slot B (PowerMateReborn)

| Prompt site | File | Source | Generated | Notes |
|---|---|---|---|---|
| `atlas-single-doc` | `powermate-reborn.json` | `.sourceprep/atlas.json` | 2026-04-30 | Single-segment Swift project; one unified atlas |
| `atlas-single-doc` | `powermate-reborn-role-architect.txt` | `.sourceprep/atlas_roles/architect.txt` | 2026-04-30 | Phase 103 per-role projection sample |
| `atlas-single-doc` | `powermate-reborn-role-intern.txt` | `.sourceprep/atlas_roles/intern.txt` | 2026-04-30 | Phase 103 per-role projection sample |
| `audit-summary` | `powermate-reborn.md` | `.sourceprep/audit/AUDIT_SUMMARY.md` | 2026-05-01 | Health score + key findings |
| `audit-architecture` | `powermate-reborn.md` | `.sourceprep/audit/ARCHITECTURE_ANALYSIS.md` | 2026-05-01 | |
| `audit-gaps` | `powermate-reborn.md` | `.sourceprep/audit/GAP_ANALYSIS.md` | 2026-05-01 | |
| `audit-inventory` | `powermate-reborn.md` | `.sourceprep/audit/COMPONENT_INVENTORY.md` | 2026-05-01 | Only 9 lines — very small component count |
| `audit-tech-debt` | `powermate-reborn.md` | `.sourceprep/audit/TECH_DEBT_REPORT.md` | 2026-05-01 | |
| `batch-cluster` | `powermate-reborn.json` | `.sourceprep/trace_cluster_swarm_synthesis.json` | 2026-04-30 | 24 clusters analyzed by kimi-k2.6:cloud, 187.3s wall |
| `batch-edges` | `powermate-reborn.jsonl` | `.sourceprep/trace_inferred_edges.jsonl` | 2026-04-29 | 36 inferred edges |
| `batch-symbol` | `powermate-reborn.jsonl` | `.sourceprep/trace_augmented.jsonl` | 2026-04-29 | **Mixed-source file** — filter records by `node_id` starting `symbol:` |
| `batch-file` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Filter records where `node_id` starts `file:` and `role` is set |
| `batch-doc` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Filter records where `doc_type` and `doc_status` are present |
| `batch-narrative` | `powermate-reborn.jsonl` | same as above | 2026-04-29 | Subset of doc records — narrative-only summaries |
| `epistemic-code` | `powermate-reborn.jsonl` | `.sourceprep/trace_epistemic.jsonl` | 2026-04-30 | 24 records, filter by file extension `.swift` for code-only |
| `epistemic-doc` | `powermate-reborn.jsonl` | same as above | 2026-04-30 | Filter for `.md` / docs |
| `rules-agents-md` | `powermate-reborn.md` | `PowerMateReborn/AGENTS.md` (repo root) | 2026-04-20 | **STALE BRANDING** — see finding below |

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

## First finding (free of charge)

**Site:** `rules-agents-md`
**Finding:** PowerMate's `AGENTS.md` at the repo root still uses the **old "codrag" / "CoDRAG" branding** instead of the current "prep" / "SourcePrep" naming. The file was last regenerated 2026-04-20, before the project rename completed.

Sample (`outputs/rules-agents-md/powermate-reborn.md` line 3-8):
```
<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-20T22:30:44Z

codrag_project_id: 2e356d01-beaa-4559-8b5f-ceadb14b7203

**ROUTING: When calling ANY CoDRAG tool, ALWAYS include ...**
```

Implication: any client project that was indexed before the rename and has not had `prep rules` re-run still has stale managed-block content. The rules-generator is correctly written (it produces "prep" today) — but the *regeneration cadence* for previously-indexed projects is the open question.

This is recorded as the first iteration entry in [`../../prompts/rules-agents-md.md`](../../prompts/rules-agents-md.md).

## What's NOT captured

These prompt sites have no Slot B baseline:

- **`concept-*` (4 sites)** — `concepts_manifest.json` exists but only as a metadata pointer; the actual concept records are stored elsewhere (concept store SQLite or similar). Did not chase the actual records since they're pre-Phase125c anyway. Will re-capture after the next concept pipeline run.
- **`atlas-root` / `atlas-segment`** — PowerMate is single-segment, so these are N/A. Need a multi-segment slot D for these.
- **`hr-*` / `custodian-*` / `researcher-*` (7 sites)** — these are agent prompts that only fire when the corresponding agent is invoked. PowerMate has never been used as input to the HR/Custodian/Researcher agents. Capture deferred until an agent run is done.
