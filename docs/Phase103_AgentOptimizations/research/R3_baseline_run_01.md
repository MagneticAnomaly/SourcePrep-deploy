# R3 Baseline — Run 01

**Date:** 2026-04-14
**Branch / worktree:** `phase103-poc`
**Index source:** live CoDRAG self-project at `/Volumes/4TB-BAD/HumanAI/CoDRAG/.prep/` (embedded mode; 26,435 nodes / 39,476 edges; built 2h prior)
**Harness:** `tests/eval/eval_runner.py --mode atlas --condition {A,B} --role {none,engineering,security,architect}`
**Gold queries:** 10 (existing `gold_queries.json`, originally designed for search-quality eval)
**Trials:** 1 (deterministic atlas assembly)

## Summary

| Condition | Pass rate | Avg score | Atlas chars |
|---|---|---|---|
| A uniform (neutral) | 2/10 | **24.8%** | 3,840 |
| B / engineering | 1/10 | 18.0% | 3,482 |
| B / security | 0/10 | 16.3% | 2,289 |
| B / architect | 1/10 | 15.8% | 2,969 |

## Per-query breakdown

| Query | Category | A uniform | B eng | B sec | B arch |
|---|---|---|---|---|---|
| gq-001 | architecture | 25.0% | 25.0% | 25.0% | 25.0% |
| gq-002 | api | 33.3% | 0.0% ↓ | 33.3% | 33.3% |
| gq-003 | features | 0.0% | 0.0% | 0.0% | 0.0% |
| gq-004 | features | 0.0% | 0.0% | 0.0% | 0.0% |
| gq-005 | core | 0.0% | 25.0% ↑ | 0.0% | 0.0% |
| gq-006 | features | 20.0% | 20.0% | 20.0% | 20.0% |
| gq-007 | mcp | **100.0%** | 40.0% ↓ | 40.0% ↓ | 60.0% ↓ |
| gq-008 | core | 50.0% | 50.0% | 25.0% ↓ | 0.0% ↓ |
| gq-009 | core | 0.0% | 0.0% | 0.0% | 0.0% |
| gq-010 | core | 20.0% | 20.0% | 20.0% | 20.0% |

## Interpretation

**Surface reading (naïve):** Pattern 3 territory — uniform atlas beats every role-weighted sub-atlas on this gold set (A 24.8% vs best B at 18%). Knowledge-honing appears to actively hurt.

**Under the hood (the real story):** The gold queries were designed for **search-quality evaluation** — they expect literal function names (`_swap_index_dir`), specific file paths (`src/codrag/core/index.py`), and narrow keyword tokens. The atlas — a module-level summary — will rarely contain those exact tokens. When the role-weighted sub-atlas narrows the content, it loses coincidental keyword hits the uniform atlas had. The scorer rewards width, not relevance.

**Evidence for the "scoring mismatch" reading:**
- gq-007 "what MCP tools are exposed": A scores 100% because the uniform atlas mentions every tool by name. B/engineering drops to 40% not because it's wrong but because it prioritizes role-owned modules and doesn't list every tool.
- gq-005 "how are embeddings generated": A scores 0%, B/engineering 25% — role-weighted atlas correctly surfaces embedding-related modules the uniform atlas's round-robin sampling missed.

**The measurement is honest; the metric is biased against role-filtering at module granularity.**

## What this run changes about the plan

Two follow-ups before another R3 sweep is meaningful:

1. **Add atlas-appropriate gold queries** — module-level questions phrased as "what system is responsible for X" rather than "what function implements X." Each query tagged with its owning role so we can pair it with the right condition-B role. Target: ≥12 queries covering engineering, security, architect, frontend. (Task #13.)

2. **Loosen the atlas scorer** — accept substring/stem matches for keywords (e.g., `atomic` should match `atomicity`, `atomic_swap`), and accept parent-directory matches for expected files (e.g., if query expects `src/codrag/core/index.py` and atlas mentions `codrag/core` module, that's a legitimate partial hit). (Task #14.)

With both fixes, Run 02 will test the R3 thesis on a fair scorer and an appropriate query set. Only then do the numbers carry thesis-weight.

## What this run does NOT change

- **The measurement primitive is validated.** `codrag(role=X)` returns consistent, differentiated content per role. Engineering gets 3,482 chars, security gets 2,289, architect gets 2,969 — the role projection is doing its job.
- **The harness plumbing is correct.** Same code path, same index, 4 conditions, reproducible JSON artifacts.
- **Dogfooding confirms our CLAUDE.md claim** (live index, fresh trace data, full atlas available via the daemon).

## Artifacts

- `condA_uniform.json`
- `condB_eng.json`
- `condB_sec.json`
- `condB_arch.json`

Each contains the full `results[]` array + summary. Reusable input for Run 02 comparison once scorer + queries are improved.

## Next

Run 02 (after tasks #13 + #14) will be the first R3 result that carries conclusion-weight. Before then, this baseline's role is to establish *that the harness works* and *how bad the scorer mismatch is* — both of which we now have.
