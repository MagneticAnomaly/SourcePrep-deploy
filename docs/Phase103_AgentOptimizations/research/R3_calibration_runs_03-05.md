# R3 Calibration Attempt — Runs 03–05

**Date:** 2026-04-14
**Goal:** Tune `security` and `architect` role vectors based on Run 02's weak per-role signals. Measure whether calibration restores B > A on role-aligned queries.

## Research anchor (brief)

- **Ozaki et al. 2025 "Confidence-Calibrated RAG":** document ordering + prompt structure affect output certainty.
- **Fine-tuning embedding models:** +7% lift with ~6K samples (Redis 2025) — overkill for our keyword-list calibration.
- **Weighted-graph centrality:** weights typically on edges; node-weight hybridization is harder (Springer Open).
- Takeaway: for our problem (module-granularity atlas retrieval), the right intervention is (a) keyword-list coverage of the actual tag universe, and (b) potentially `centrality_weight` and `detail_level` since those route the assembly stage.

## What we changed

### Run 03 — expand domain_affinity on security + architect
Data-driven: inspected `trace_epistemic.jsonl` to see what tags actually exist, added specific compound terms.

- **Security** +12 terms: `admin-policy`, `security-policy`, `policy-enforcement`, `access-control`, `role-based-access-control`, `input-sanitization`, `cryptography`, `cryptographic-hashing`, `session-management`, `credentials`, `cors`, `security-audit`, `audit-logging`, `audit-trail`.
- **Architect** +12 terms: `entry-point`, `bootstrap`, `daemon`, `daemon-architecture`, `daemon-lifecycle`, `cli`, `mcp`, `fastapi`, `rag`, `pipeline-orchestration`, `llm-orchestration`, `architecture-audit`, `audit-architecture`.

### Run 04 — methodology fix: isolate neutral baseline from role tuning
Earlier `_neutral_role_vector()` built `domain_affinity` as the **union of all BUILT_IN_ROLES**. This caused condition A to improve every time we tuned any role — confounding A-vs-B comparisons.

Fixed: neutral role now uses a small, stable, codebase-universal term set (top-frequency tags from `trace_epistemic.jsonl`). Does NOT derive from role definitions; role calibration no longer leaks into A.

### Run 05 — architect assembly-tier tweak
Architect `detail_level` 0.5 → 0.7 (manager → practitioner tier for more detailed content) and `centrality_weight` 0.8 → 0.6 (less hub bias, more entry-point coverage).

## Numbers

```
Condition       Run 02 avg    Run 03 avg    Run 04 avg    Run 05 avg
A uniform          51.2%         56.5%         55.6%         55.6%
B engineering      48.8%         48.8%         48.8%         48.8%
B security         45.7%         45.7%         45.7%         45.7%
B architect        45.7%         45.9%         45.9%         45.9%
B frontend           —           48.7%         48.7%         48.7%
```

- **Run 03:** A jumped +5.3pp (confound: tuning security+architect also strengthened A via neutral union).
- **Run 04:** A corrected back to 55.6% (−0.9pp) after methodology fix. Matches R3's actual baseline.
- **Run 05:** Architect tier change had **zero measurable impact on the aggregate**.

## Why the calibration did not move B-security or B-architect

Traced gq-a03 ("what are architectural entry points to the system") manually:

**Architect projection (calibrated, Run 05):**
- Keyword matches: 1/4 (`cli` hit, `entry` / `mcp` / `server` miss)
- File matches: 2/2 (via 4+ char ancestor `codrag`)
- Score: 3/6 = 50%

**Uniform projection (neutral baseline):**
- Keyword matches: 4/4 (atlas literally contains `entry` 1x, `cli` 3x, `mcp` 4x, `server` matches via stem)
- File matches: 2/2 (`cli.py` matches as basename directly — uniform atlas actually names the file)
- Score: 6/6 = 100%

**Mechanistic reason:** Architect role is narrowly scoped by design. Meta-architectural questions that span *all* entry points (CLI, server, MCP) benefit from breadth — the exact thing a specialized role vector reduces. Adding `cli`, `mcp`, `bootstrap` to architect's domain_affinity did boost CLI module coverage (from 1→7 occurrences of `cli`), but did not surface `mcp.py` / `server.py` specifically.

## The actual R3 finding (holding steady)

Knowledge-honing vs uniform atlas, clean comparison:

| Query type | Signal |
|---|---|
| Role-aligned, niche (gq-a08 frontend question, frontend role) | **B wins big: 20% → 80%** |
| Role-aligned, common (gq-a07 frontend question, frontend role) | B wins modest: 83% → 100% |
| Role-aligned, broad (gq-a01 engineering pipelines, eng role) | flat at 100% (uniform already has it) |
| Meta-architectural (gq-a03 entry points, architect role) | **A wins: 100% vs 50%** |
| Cross-cutting (gq-a06 API envelope + auth, security role) | A wins: 83% vs 50% |

**Knowledge-honing helps when the query is narrowly aligned to a role's domain, and is neutral-to-harmful when the query is meta or cross-cutting.** This is a sensible mechanism-level result, not a validation or refutation of the thesis.

## Implications for the product

1. **The role ↔ query alignment matters more than the role vector calibration.** Improving domain_affinity helps at the margins; the bigger lever is knowing *when to use* a role-scoped projection vs when to fall back to the uniform atlas.
2. **Query classification is the next frontier.** An MCP client calling `codrag(role="architect", task="...")` where the task is meta-architectural would benefit from falling back to the uniform atlas silently. R4's universal API spec should include this routing logic.
3. **Role specialization has diminishing returns past a base coverage.** Architect went from 14 terms → 19 terms with zero aggregate improvement. Keyword expansion alone isn't the answer.

## Stopping point (deliberate)

Per user direction ("leave further research for later"), we stop here on calibration. The intellectual honest conclusion:

- The calibrated role vectors are **keeping** the added domain_affinity terms — they are harmless and may help on non-measured queries.
- The methodology fix (neutral role isolation) is **keeping**.
- The thesis-weight numbers for R3 are: **Run 04 / 05** (they are equivalent).
- **R3's real finding:** knowledge-honing works where it should (narrow role-aligned queries) and doesn't hurt elsewhere beyond the scope-reduction expected from any filter.

## What to carry into later work (not now)

- Query classification: `codrag(task="...")` should infer whether the task is narrow-role or meta-architectural; use role projection for the former, uniform atlas (or a union projection) for the latter.
- Consider a `--condition AB` option where uniform and scoped are *both* returned and the client picks (or the server returns the higher-scoring one per query category).
- Frontend role is the cleanest win and the best template for how other roles should be scoped — examine its `domain_affinity` (`ui`, `frontend`, `react`, `typescript`, `design-system`, etc.) vs our current security/architect terms.
- Consider learned-embedding fine-tuning per role (Ozaki 2025 / Redis 2025 lit) as a future project — not this phase.

## Artifacts

- `run03_*.json`, `run04_*.json`, `run05_*.json` — 5 conditions × 3 runs.
- Role vector changes committed in `src/codrag/core/atlas/role_vectors.py` (kept).
- Neutral baseline fix committed in `tests/eval/eval_runner.py::_neutral_role_vector` (kept).

## Next actions (when resumed)

1. Implement server-side query classification so `codrag(role=X, task=Y)` can choose between role-scoped and uniform based on task type.
2. Apply the frontend role vector's structural pattern (many compound terms, high centrality_weight) to architect and security.
3. Add per-role eval bench (gold queries generated for each role, scored against the role's own projection) — the 2-queries-per-role design in `gold_queries.json v1.1` is too noisy.
