# Baseline snapshot — 2026-05-17

**Captured:** 2026-05-18T00:40:05Z (local: 2026-05-17)
**Git SHA:** `01ba32520b30e03e26f9be251a0079b84d82563a`
**Branch:** `main`
**Status:** Immutable. New iterations must produce new dated snapshot directories.

## Why this exists

Baseline for Phase 140. Every prompt iteration is compared against the captured outputs in `outputs/`. The prompt-file SHAs below let future iterations see at a glance which prompts changed.

## Prompt-file SHA-256 (first 12 chars) and line counts

| SHA (12) | Lines | File |
|---|---|---|
| `6252f4eca4b2` | 117 | `src/prep/core/atlas/prompts.py` |
| `b35e784e3abd` | 901 | `src/prep/core/concept_synthesizer.py` |
| `f257c13839aa` | 310 | `src/prep/core/concept_validate_prompt.py` |
| `45f6da3f0f1a` | 606 | `src/prep/core/concept_t3_refine.py` |
| `a474170fc6bd` | 237 | `src/prep/core/concept_generate_prompt.py` |
| `3ec1255d5b0f` | 546 | `src/prep/core/batch_prompts.py` |
| `d129188714f2` | 165 | `src/prep/core/audit/prompts.py` |
| `7c6239a6f300` | 1368 | `src/prep/core/epistemic_enrichment.py` |
| `bb3512c0976a` | 268 | `src/prep/agents/hr/prompts.py` |
| `1062afc416cd` | 63 | `src/prep/agents/custodian/prompts.py` |
| `3b0ba9b80202` | 134 | `src/prep/agents/researcher/prompts.py` |
| `c880edc924cd` | 1296 | `src/prep/core/rules_generator.py` |

Recompute on any prompt change: `shasum -a 256 <file> | cut -c1-12`.

## Environment

To be recorded on first output capture. Suggested fields:

- Python version: TBD
- Daemon mode: server (default) | direct
- Embedder: `nomic-embed-text-v1.5` ONNX (Phase 139 hardened)
- Cloud LLM: TBD (model, version, provider)
- Concurrency: auto-discovered (Phase 82)

## Test repos captured

See [`../../02_TestRepos.md`](../../02_TestRepos.md) for slot definitions. As outputs are captured, fill in the table below.

| Slot | Repo | Commit | File count | Captured? |
|---|---|---|---|---|
| A | SourcePrep self-host (`/Volumes/4TB-BAD/HumanAI/CoDRAG/`) | `01ba3252` | ~2,000 | ⏳ |
| B | TBD | — | — | ⏳ |
| C | TBD | — | — | ⏳ |
| D | (deferred) | — | — | — |
| E | (deferred) | — | — | — |

## Outputs index

Outputs are organized as `outputs/<site-slug>/<repo-label>.{json,md}`. The slugs match `prompts/<slug>.md` page names. Empty so far — will populate as captures land.

```
outputs/
├── atlas-single-doc/
├── atlas-root/
├── atlas-segment/
├── concept-synthesize/
├── concept-validate/
├── concept-t3-refine/
├── concept-generate/
├── batch-symbol/
├── batch-file/
├── batch-doc/
├── batch-narrative/
├── batch-edges/
├── batch-epi-code/
├── batch-epi-doc/
├── batch-cluster/
├── audit-summary/
├── audit-architecture/
├── audit-gaps/
├── audit-inventory/
├── audit-tech-debt/
├── epistemic-code/
├── epistemic-doc/
├── hr-agents-md/
├── hr-soul-md/
├── hr-auto-roles/
├── custodian-safety/
├── researcher-topic/
├── researcher-research/
├── researcher-plan/
└── rules-agents-md/
```
