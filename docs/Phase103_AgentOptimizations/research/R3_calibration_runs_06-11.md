# R3 Calibration — Runs 06–11

**Date:** 2026-04-14
**Goal:** Push `B` (role-weighted sub-atlas) past `A` (uniform) on role-aligned queries
for engineering, architect, and security. Continue from Run 05's flat plateau.

## Headline result

Knowledge-honing now beats uniform on at least one role-aligned query for every tuned
role. Frontend was already winning; engineering, architect, and security all join.

| Query | A | B (matched role) | Δ vs A |
|---|---|---|---|
| gq-a01 (eng pipelines) | 100% | 100% | tied (ceiling) |
| **gq-a02 (eng embedding service)** | 50% | **75%** | **+25pp** |
| gq-a03 (arch entry points) | 100% | 100% | tied (was −50pp Run 05) |
| **gq-a04 (arch hub files)** | 20% | **40%** | **+20pp** |
| **gq-a05 (sec admin policy)** | 50% | **67%** | **+17pp** |
| gq-a06 (sec API + auth) | 83% | 83% | tied (was −33pp Run 05) |
| **gq-a07 (frontend dashboard)** | 83% | **100%** | **+17pp** |
| **gq-a08 (frontend VS Code)** | 20% | **80%** | **+60pp** |

Aggregate (Run 11):

```
A uniform   pass=11/18  avg=55.6%
B eng       pass=11/18  avg=53.8%
B arch      pass=10/18  avg=54.6%
B sec       pass=10/18  avg=45.9%
B fe        pass= 7/18  avg=48.7%
```

Per-role aggregate B is now within 1–2pp of A for engineering and architect (was
6–10pp behind in Run 05). Security still trails on aggregate because most non-role
queries don't benefit from specialization — that's the expected cost of narrowing
a filter, and it's the routing problem the parallel workstream owns.

Success criterion #1 (matched-role B beats A by ≥5pp on a role-aligned query
for engineering + architect + security) is **met**.

---

## The unlock: detail_level boundary at the manager → practitioner tier

Run 05's calibration of architect `detail_level` from 0.5 → 0.7 produced zero
movement. The reason was a one-line dispatch in `role_projection.py:578`:

```python
elif role.detail_level <= 0.7:
    return _assemble_manager(...)   # iterates modules in JSONL order, NOT role-scored
else:
    return _assemble_practitioner(...)   # iterates files sorted by role affinity
```

`detail_level=0.7` lands in **manager** tier, which walks modules in the order
they appear in `trace_modules.jsonl` and only role-scores files *within* each
module's section. The role vector's `domain_affinity` therefore couldn't promote
an off-module file. Bumping to **0.8** routes architect/security to the
**practitioner** tier, where `scored_files` are sorted by relevance score before
assembly — finally letting role weighting actually pick which files appear.

This explains why frontend (resolves to `full_stack`, `detail_level=0.8`) was
the only role producing a clean win in Run 05 — it was the only role in the
practitioner tier.

Engineering was already at 0.8 (practitioner). Architect and security were both
at 0.7 (manager) — a one-character difference that effectively disabled role
scoring for two of the three roles we'd been trying to tune.

---

## Per-run changes (one knob per run)

### Run 06 — baseline reproduction
No changes. Confirmed Run 05 numbers reproduce exactly. Took the opportunity to
inspect the projection for `gq-a05`/`gq-a06` and discovered file matches were
passing trivially (via module-ancestor) while keyword matches were failing
because the security projection contained Agent Orchestration / HR / Marketing
modules instead of envelope or admin-policy content. Triggered the boundary
investigation above.

### Run 07 — architect + security `detail_level` 0.7 → 0.8

```diff
- detail_level=0.7,   # was 0.5; "practitioner tier"  (NOT — 0.7 is still manager)
+ detail_level=0.8,   # crosses <=0.7 manager boundary → real practitioner
```

| Query | A | B Run 06 | B Run 07 | Δ |
|---|---|---|---|---|
| gq-a03 (arch) | 100% | 50% | **100%** | +50pp recovered |
| gq-a05 (sec) | 50% | 33% | **67%** | +34pp |
| gq-a06 (sec) | 83% | 50% | 33% | −17pp regression |

Practitioner tier surfaced legitimate security files (audit_log.py,
feature_gate.py, security_health.py, generate_license.py, lib.rs) but dropped
the FastAPI-envelope module that manager tier had carried by accident. gq-a06
expects keywords `envelope, error, exception, api` — none present in the new
projection. Need a follow-up.

### Run 08 — security recovers gq-a06 via API surface tags

Two changes (both targeting the same regression):

1. Added `api-design`, `response-envelope`, `error-handling`,
   `exception-handling`, `middleware`, `fastapi` to security `domain_affinity`.
2. Bumped security `layer_weights["presentation"]` from 0.2 → 0.5 to let
   API-layer files clear the score floor.

The layer bump was the load-bearing change. `envelope.py` (layer=presentation,
tags=`[api, error-handling, fastapi]`) scored 0.488 under Run 07 vs 0.663 for
audit_log.py, getting cut at the budget line. Lifting presentation to 0.5
added ~0.075 to the layer component, putting envelope.py into the top-9 cut.

| Query | A | B Run 07 | B Run 08 | Δ |
|---|---|---|---|---|
| gq-a06 (sec) | 83% | 33% | **83%** | +50pp recovered |
| gq-a05 (sec) | 50% | 67% | 67% | held |

### Run 09 — architect wins gq-a04 via hub/graph vocabulary

Added 18 graph-centrality terms to architect `domain_affinity`:
`dependency-graph`, `dependency-analysis`, `dependency-management`,
`dependency-extraction`, `dependency-injection`, `dependency-inference`,
`graph-analysis`, `code-graph`, `trace-graph`, `graph-construction`,
`graph-algorithms`, `graph-traversal`, `graph-engine`, `knowledge-graph`,
`cross-platform`, `cross-cutting`, `import-cycle`, `centrality`, `hub-file`.

These names appear as actual `domain_tags` in `trace_epistemic.jsonl` — verified
by frequency-counting before adding. Files tagged with them surface
graph-related modules whose summaries naturally contain `dependency`/`graph`
keywords.

| Query | A | B Run 08 | B Run 09 | Δ |
|---|---|---|---|---|
| gq-a04 (arch) | 20% | 20% | **40%** | +20pp (now beats A) |
| gq-a07 (off-role) | 83% | 50% | 83% | +33pp side benefit |

### Run 10 — engineering domain_affinity expansion (no movement)

Added embedder/augmenter vocabulary to engineering: `embeddings`, `vector-search`,
`llm-integration`, `retrieval`, `trace-augmentation`, `semantic-analysis`,
`pipeline-stage`, `llm-orchestration`, `epistemic-analysis`,
`knowledge-representation`.

Engineering projection now contained `embedder` 3×, `embedding` 4× — but
`augmenter`/`service` still missed because `augmenter.py` got cut at the 3500-char
budget line. `gq-a02` stayed at 50% (B/eng matched A but didn't beat).

### Run 11 — engineering `max_chars` 3500 → 4000

Single-knob change: lifted engineering budget to match A's 4000-char neutral
budget. `augmenter.py` now surfaces, contributing the missing `augment`/`service`
keyword hits.

| Query | A | B Run 10 | B Run 11 | Δ |
|---|---|---|---|---|
| gq-a02 (eng) | 50% | 50% | **75%** | +25pp (now beats A) |

---

## Final role vector deltas (vs Run 05)

```python
"engineering": {
    domain_affinity += [embeddings, vector-search, llm-integration, retrieval,
                        trace-augmentation, semantic-analysis, pipeline-stage,
                        llm-orchestration, epistemic-analysis,
                        knowledge-representation],
    max_chars: 3500 → 4000,
}

"architect": {
    domain_affinity += [dependency-graph, dependency-analysis,
                        dependency-management, dependency-extraction,
                        dependency-injection, dependency-inference,
                        graph-analysis, code-graph, trace-graph,
                        graph-construction, graph-algorithms, graph-traversal,
                        graph-engine, knowledge-graph, cross-platform,
                        cross-cutting, import-cycle, centrality, hub-file],
    detail_level: 0.7 → 0.8,   # manager → practitioner tier
}

"security": {
    domain_affinity += [api-design, response-envelope, error-handling,
                        exception-handling, middleware, fastapi],
    layer_weights["presentation"]: 0.2 → 0.5,
    detail_level: 0.7 → 0.8,
}
```

Frontend (`full_stack`) and other roles unchanged.

---

## What did and didn't work

**Worked (load-bearing):**
- `detail_level` boundary fix (0.7 → 0.8) for architect + security. This was the
  hidden constraint blocking ~all earlier calibration. Without crossing the
  0.7 threshold, role scoring on files was disabled for those two roles.
- `layer_weights["presentation"]` bump for security (0.2 → 0.5). Necessary
  *complement* to detail_level: practitioner tier sorts by score, and score
  is dominated by layer_match for files whose tag set already covers the role.
- Data-driven `domain_affinity` expansion based on the actual tag universe
  (e.g., `dependency-graph`, `trace-augmentation`). Pulled in modules whose
  summaries naturally contained the gold-query keywords.
- `max_chars` lift for engineering (3500 → 4000) to let a second target file
  (augmenter.py) clear the budget line alongside embedder.py.

**Didn't work:**
- Run 03's `domain_affinity` expansion in isolation. Without the practitioner
  tier, the new keywords couldn't influence module selection.
- Run 05's `centrality_weight` reduction. Architect manager tier doesn't sort
  modules by centrality (or anything else); just walks the JSONL.

**Not tried (deferred):**
- Manager-tier module sorting by role affinity. This would let manager-tier
  roles also benefit from `domain_affinity`. Out of scope for calibration; it's
  a `role_projection.py` change. Worth flagging to the parallel workstream.
- Synonym cluster audit. The `_TAG_TO_CLUSTER` matches at 0.5, but our 0.7
  substring matches dominate in practice. Probably dead weight; left alone.
- Audience bonus expansion. Adding `error-handling`, `api-design` to
  `TAG_TO_AUDIENCE[security]` would let security claim API files via the
  audience component (worth +0.10 max). Decided not to touch this since the
  layer/affinity adjustments were sufficient.

---

## Mechanism-level interpretation

Knowledge-honing produces measurable lift on role-aligned queries when:
1. The role's tier dispatches to practitioner-level assembly (file-scored).
2. The role's `layer_weights` and `domain_affinity` collectively elevate the
   *correct* files past the budget cutoff.
3. The query's expected-keyword set has reasonable lexical overlap with the
   tags or summaries of those elevated files.

Run 07–11 demonstrate all three are independently necessary. Earlier calibration
runs missed (1) entirely for architect/security, so (2) and (3) were inert.

The Run 05 conclusion ("knowledge-honing helps on narrow role-aligned queries
and is neutral-to-harmful on meta queries") still holds, but the strength of
the helpful regime was undercounted because two of three calibrated roles were
silently in the wrong assembly tier.

---

## Open questions for the parallel workstream

1. **Manager-tier role scoring.** `_assemble_manager` walks `trace_modules.jsonl`
   in storage order and ignores `domain_affinity`. Adding a one-line sort by
   `max_tag_affinity(mod['domain_tags'], role.domain_affinity)` would let
   `detail_level <= 0.7` roles also benefit from calibration. Cheap, low-risk,
   and would close the manager/practitioner capability gap.
2. **Aggregate B/sec still 10pp behind A.** This is a routing problem, not a
   calibration problem. Of security's 18 queries, only 2 are role-aligned. The
   other 16 (including 10 legacy v1.0 queries) are general codebase questions
   where specialization purely costs breadth. The query-classification work
   should detect "this isn't a security question" and silently fall back to
   uniform.
3. **Asymmetric budgets.** A's neutral uses `max_chars=4000`; tuned roles use
   2500–4000. We bumped engineering to 4000 to match. Worth deciding whether
   role budgets should ever be smaller than neutral, since smaller budgets
   structurally disadvantage B even when role scoring is correct.
4. **`atlas_content` is empty in eval.** `eval_runner.assemble_atlas_context`
   passes `atlas_content=""`, so neither A nor B includes the CROSS-CUTTING
   identity/stack section. gq-a04 ("hub files anchor the dependency graph")
   would benefit from that section in *both* conditions; a future eval could
   wire real atlas content through and re-measure relative deltas.

---

## Files touched

- `src/codrag/core/atlas/role_vectors.py` — engineering, architect, security
  vector tuning. Frontend / others unchanged.
- `docs/Phase103_AgentOptimizations/research/R3_calibration_runs_06-11.md`
  (this file).
- `docs/Phase103_AgentOptimizations/research/run{06..11}_cond*.json` — 30
  artifacts.
- `docs/Phase103_AgentOptimizations/research/HANDOFF_CALIBRATION.md` —
  handoff-back section appended.

No source changes outside `role_vectors.py`. Per scope, nothing was modified
in `role_projection.py`, `eval_runner.py`, gold queries, or the MCP layer.
