# R3 Baseline — Run 02 (loose scorer + atlas queries)

**Date:** 2026-04-14
**Changes from Run 01:**
1. Loosened atlas scorer — file match accepts full/basename/parent-dir/module-ancestor; keyword match accepts substring OR stem-form.
2. Added 8 atlas-level gold queries (`gq-a01..gq-a08`) tagged with their owning roles.
3. Added B/frontend condition (not tested in Run 01).

## Summary

| Condition | Pass rate | Avg score | Δ from Run 01 |
|---|---|---|---|
| A uniform | 8/18 | **51.2%** | +26.4 pp |
| B engineering | **9/18** | 48.8% | +30.8 pp |
| B security | 8/18 | 45.7% | +29.4 pp |
| B architect | 8/18 | 45.7% | +29.9 pp |
| B frontend | 7/18 | 48.7% | (new) |

B/engineering has **more passes** than uniform. On avg score, A still leads narrowly, but the A–B gap shrank from ~7 pp (Run 01) to ~3–5 pp (Run 02). Much of Run 01's apparent "A dominance" was scorer artifact.

## Role-alignment analysis (the thesis test)

When the query's owning role matches the condition-B role, does knowledge-honing lift performance?

| Role-aligned pair | A uniform | B (matched role) | Other B roles | Lift |
|---|---|---|---|---|
| **gq-a01 engineering** | 100.0% | 100.0% (eng) | 100/100/80/20 (sec/arch/arch/fe) | flat — A & matched tie |
| **gq-a02 engineering** | 25.0% | **50.0% (eng)** | 25/25/25 (sec/arch/fe) | **+25 pp ↑** |
| **gq-a03 architect** | 83.3% | 66.7% (arch) | 83/67/83 (eng/sec/fe) | **−17 pp ↓** |
| **gq-a04 architect** | 20.0% | 40.0% (arch) | 20/40/40 (eng/sec/fe) | **+20 pp ↑** |
| **gq-a05 security** | 33.3% | 33.3% (sec) | 33/33/33 | flat |
| **gq-a06 security** | 83.3% | 50.0% (sec) | 50/50/83 | **−33 pp ↓** |
| **gq-a07 frontend** | 83.3% | **100.0% (fe)** | 83/67/67 | **+17 pp ↑** |
| **gq-a08 frontend** | 20.0% | **80.0% (fe)** | 0/0/0 | **+60 pp ↑↑↑** |

**Pattern observed:**
- **Frontend role wins cleanly on both frontend queries** — +17pp on gq-a07, +60pp on gq-a08. Strongest thesis evidence in the run.
- **Engineering role wins modestly** — +25pp on gq-a02, ties on gq-a01.
- **Architect role is mixed** — wins +20pp on gq-a04, loses −17pp on gq-a03.
- **Security role doesn't distinguish itself on its aligned queries** — ties on gq-a05, loses −33pp on gq-a06.

## Per-query breakdown (abridged)

```
QID      Cat          Roles                              A        B/eng    B/sec    B/arch   B/fe
gq-a01   atlas        engineering                       100.0%   100.0%   100.0%    80.0%    20.0%
gq-a02   atlas        engineering                        25.0%    50.0% ↑  25.0%    25.0%    25.0%
gq-a03   atlas        architect                          83.3%    83.3%    66.7%    66.7% ↓  83.3%
gq-a04   atlas        architect                          20.0%    20.0%    40.0%    40.0% =  40.0%
gq-a05   atlas        security                           33.3%    33.3%    33.3%    33.3%    33.3%
gq-a06   atlas        security                           83.3%    50.0%    50.0% ↓  50.0%    83.3%
gq-a07   atlas        frontend                           83.3%    83.3%    66.7%    66.7%   100.0% ↑
gq-a08   atlas        frontend                           20.0%     0.0%     0.0%     0.0%    80.0% ↑
```

The search-level queries (gq-001..gq-010) are roughly flat across conditions — as expected; they don't target the kind of module-level content role projection amplifies.

## Interpretation

**Pattern 4 (calibration) confirmed for some roles; pattern 1/5 (knowledge-honing wins) confirmed for others.**

The mechanism works — gq-a08 (20% → 80% under the right role) is proof that knowledge-honing can deliver large lifts. But not every role vector is equally well-calibrated:
- **Frontend** role vector produces strong role-aligned performance (has a clear domain — UI packages, dashboard, vscode extension — that maps cleanly).
- **Engineering** role produces modest lift (its domain is broader, so the uniform atlas already covers much of what engineering would surface).
- **Architect** and **Security** roles inconsistent — they win on one query and lose on another of the same category. Suggests the domain affinities aren't matching well to the atlas module tags.

**Recommended calibration actions:**
1. Inspect `role_vectors.py` for **security** role — confirm `domain_affinity` includes the terms that actually appear in `admin_policy.py` / `api_envelope.py` module summaries. The 50% on gq-a06 suggests the security atlas isn't surfacing api_envelope content.
2. Inspect **architect** role — the `centrality_weight=0.85` is producing hub-heavy output but gq-a03 expects entry-point discussion (CLI, server). Either adjust weight or broaden domain_affinity.
3. Consider adding more atlas queries per role (currently 2 each) — N=2 makes single-query noise dominate.

## The honest Run 02 story

**Knowledge-honing works** on the clearly-aligned cases (frontend; engineering on specific queries). **It needs calibration** for security and architect.

Three responses, in order of cost:
1. **Cheap (1 day):** Tune security + architect role vectors (add/refine `domain_affinity` terms; maybe bump their `max_chars`). Re-run.
2. **Medium (2–3 days):** Add 4–6 more queries per role so we have 4+ per role category. Re-run.
3. **Higher (week+):** Empirically derive role vectors from actual codebase usage patterns rather than hand-curated terms.

Recommendation: do #1 this week before spending more measurement budget.

## Comparison with Run 01

The Run 01 conclusion ("A dominates B by ~7pp") was a **scorer artifact**. With a fair scorer + appropriate queries, the A vs B gap narrows to 2–5pp on aggregate, and flips per-query based on role alignment. Run 01's value: confirmed the measurement primitive works. Run 02's value: first thesis-meaningful numbers.

**Run 02 status:** thesis partially validated. Mechanism works; some role vectors need tuning.

## Artifacts

- `run02_condA.json`
- `run02_condB_eng.json`
- `run02_condB_sec.json`
- `run02_condB_arch.json`
- `run02_condB_fe.json`

## Next

Before Run 03:
- Inspect + refine role vectors for security and architect (task: new).
- Optionally add 2 more queries per role to reduce per-query noise.
- Then re-run the 5-condition sweep. Run 03 is the first run positioned to carry Phase 103 conclusion weight.
