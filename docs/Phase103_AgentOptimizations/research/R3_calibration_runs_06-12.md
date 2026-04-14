# R3 Calibration — Runs 06–12

**Date:** 2026-04-14
**Goal:** Push `B` (role-weighted sub-atlas) past `A` (uniform) on role-aligned
queries for engineering, architect, security; then **broaden** beyond dev roles
by adding personal-assistant, project-manager, and researcher personas
(Phase 103 motivated by OpenClaw and other non-dev agent use cases).

---

## Headline result

1. **Knowledge-honing now beats uniform on at least one role-aligned query for
   every tuned role**, including the three new non-dev roles.
2. **Three roles beat A on the full 24-query aggregate**: engineering (49.8% vs
   A 48.1%), architect (50.8%), researcher (50.5%). Frontend and assistant
   are within 3pp.
3. **The single load-bearing change** turned out to be a one-character
   `detail_level` boundary fix (0.7 → 0.8) that re-enabled role scoring for
   architect and security. Every prior calibration attempt for those roles was
   silently inert.

### Per-role role-aligned wins

| Role | Best win on role-aligned query | Recovered from regression |
|---|---|---|
| engineering | gq-a02 +25pp | — |
| architect | gq-a04 +20pp | gq-a03 −50pp → 0pp |
| security | gq-a05 +17pp | gq-a06 −33pp → 0pp |
| frontend (`full_stack`) | gq-a08 +60pp (already winning) | — |
| **assistant (OpenClaw)** | **gq-a09 +60pp** | new role |
| **pm (project manager)** | **gq-a11 +50pp, gq-a12 +50pp** | new role |
| **researcher** | **gq-a13 +50pp, gq-a14 +17pp** | new role |

---

## The unlock: detail_level boundary at the manager → practitioner tier

Run 05's bump of architect `detail_level` from 0.5 → 0.7 produced zero movement
on the aggregate. The reason was a one-line dispatch in `role_projection.py`:

```python
elif role.detail_level <= 0.7:
    return _assemble_manager(...)        # iterates modules in JSONL order, NOT role-scored
else:
    return _assemble_practitioner(...)   # iterates files sorted by role affinity
```

`detail_level=0.7` lands in **manager** tier, which walks
`trace_modules.jsonl` in storage order and only role-scores files *within*
each module. The role vector's `domain_affinity` therefore couldn't promote
an off-module file. Bumping to **0.8** routes architect/security into the
**practitioner** tier where `scored_files` are sorted by relevance score
before assembly — finally letting role weighting actually pick which files
appear.

Frontend was already winning Run 05 because it resolves to `full_stack`
(`detail_level=0.8`, practitioner). It was the only role in the practitioner
tier — making it look like calibration was hopeless when really the dispatch
boundary was disabling it for two of three calibrated roles.

All new roles (`assistant`, `pm`, `researcher`) are defined at
`detail_level=0.8` to avoid this trap.

---

## Per-run change log (one knob per run)

### Run 06 — baseline reproduction
No source changes. Confirmed Run 05 numbers reproduce; the `gq-a05` /
`gq-a06` security projections contained Agent Orchestration / HR / Marketing
modules instead of envelope or admin-policy content. This kicked off the
boundary investigation. Artifacts not retained — Run 05 JSON is the
authoritative baseline.

### Run 07 — architect + security `detail_level` 0.7 → 0.8

Just the boundary cross. Architect recovered gq-a03 (50% → 100%, matches A);
security gained gq-a05 (33% → 67%, beats A by 17pp). Cost: gq-a06 regressed
50% → 33% because the manager tier had been carrying the FastAPI envelope
module by accident.

### Run 08 — security recovers gq-a06

Two coupled changes:
1. Added `api-design`, `response-envelope`, `error-handling`,
   `exception-handling`, `middleware`, `fastapi` to security
   `domain_affinity`.
2. Bumped security `layer_weights["presentation"]` from 0.2 → 0.5.

The layer bump was load-bearing. `envelope.py` (layer=presentation,
tags=`[api, error-handling, fastapi]`) scored 0.488 under Run 07 vs 0.663 for
`audit_log.py`, getting cut at the budget line. Lifting presentation to 0.5
added ~0.075 to the layer component, putting envelope.py into the top-9 cut.
gq-a06 returned to 83% (matches A).

### Run 09 — architect wins gq-a04 via hub/graph vocabulary

Added 19 graph-centrality terms to architect `domain_affinity`:
`dependency-graph`, `dependency-analysis`, `dependency-management`,
`dependency-extraction`, `dependency-injection`, `dependency-inference`,
`graph-analysis`, `code-graph`, `trace-graph`, `graph-construction`,
`graph-algorithms`, `graph-traversal`, `graph-engine`, `knowledge-graph`,
`cross-platform`, `cross-cutting`, `import-cycle`, `centrality`, `hub-file`.

These names appear as actual `domain_tags` in `trace_epistemic.jsonl` —
verified by frequency-counting before adding. `gq-a04`: 20% → 40% (+20pp,
beats A=20%).

### Run 10 — engineering domain_affinity expansion (no movement)

Added embedder/augmenter vocabulary to engineering. Engineering projection
contained `embedder` 3× and `embedding` 4× — but `augmenter`/`service` still
missed because `augmenter.py` got cut at the 3500-char budget line. `gq-a02`
stayed at 50% (B/eng matched A but didn't beat it).

### Run 11 — engineering `max_chars` 3500 → 4000

Lifted engineering budget to match A's 4000-char neutral budget.
`augmenter.py` now surfaced, contributing the missing keyword hits. `gq-a02`:
50% → 75% (+25pp, beats A=50%).

### Run 12 — scrutiny pass + new non-dev roles

Three categories of change:

**(a) Bisect-driven cleanup of engineering vector.** The bisect (max_chars
3500 → 3500 only) showed engineering reverted to 50% on gq-a02; the win was
predominantly bought with budget. Sharpened the vector by removing the broad
`api` term (which was pulling API routers into top results), adding compound
terms (`service-layer`, `factory-pattern`, `embedder`, `augmenter`,
`pipeline-orchestration`, `incremental-builds`), and lowering
`centrality_weight` 0.5 → 0.4 to favor niche service files. Restored
max_chars=4000 for budget parity with A's neutral. Honest finding: the
ranking didn't change much (`augmenter.py` is still rank 39 of 200+ files);
the 4000 budget remains the load-bearing knob.

**(b) Three new non-dev roles** (in `BUILT_IN_ROLES`):

```python
"assistant": RoleVector(    # OpenClaw, secretarial agents
    layer_weights = doc-heavy (documentation 0.95, business_logic 0.4),
    domain_affinity = [planning, implementation-plan, roadmap, milestone,
                       specification, mvp, requirements, decision-log, todo,
                       task, action-item, status, blocker,
                       agent-architecture, agent-orchestration,
                       context-engineering, knowledge-management,
                       tacit-knowledge, memory, user-facing, onboarding,
                       feature, phase, deliverable, scope],
    centrality_weight = 0.3,
    detail_level = 0.8,
    max_chars = 4000,
)

"pm": RoleVector(    # operational project management (distinct from product/strategy)
    domain_affinity = [project-management, roadmap, milestone, deliverable,
                       phase, deadline, tracking, status, scheduling, scope,
                       blocker, dependency-management, release-management,
                       rollout, implementation-plan, team-coordination,
                       agile, sprint, kanban, retrospective,
                       tech-debt, technical-debt],
    detail_level = 0.8, max_chars = 3500,
)

"researcher": RoleVector(    # comparative analysis / evaluation
    domain_affinity = [research, research-engine, research-strategy,
                       evaluation, benchmark, comparison, ablation,
                       hypothesis, finding, experiment, metrics,
                       measurement, analysis, literature, survey,
                       methodology, calibration, ai-agent,
                       agent-architecture, knowledge-graph,
                       epistemic-analysis, context-engineering,
                       code-intelligence, graph-rag],
    detail_level = 0.8, max_chars = 4000,
)
```

Resolver mappings updated (`role_resolver.py`):
- `assistant`, `secretary`, `pa`, `ea`, `coordinator`, `openclaw`, `todo`,
  `planner` → `assistant`
- `pm`, `program`, `project`, `scrum`, `tpm`, `delivery`, `agile` → `pm`
  (was → `product`)
- `researcher`, `research`, `analyst`, `evaluator` → `researcher` (was
  → `design`)

**(c) Six new gold queries** (`gq-a09..a14`) for the new roles. Each role
gets two queries — one narrow-niche, one moderate cross-cutting — keeping
the existing queries gq-a01..a08 untouched per scope.

---

## Final aggregate (Run 12, 24-query corpus)

```
Condition         pass    avg
A uniform        13/24  48.1%
B engineering    15/24  49.8%   ← beats A
B architect      13/24  50.8%   ← beats A
B research       15/24  50.5%   ← beats A
B frontend       10/24  46.5%
B assistant      14/24  45.2%
B security       11/24  39.4%
B pm              9/24  39.2%
```

Engineering, architect, and researcher beat A on aggregate. The other roles
trail because their off-role queries (12+ of 24) cost more breadth than
their 2 role-aligned wins gain. **This is the routing problem the parallel
workstream owns** — `codrag(role=X, task=Y)` should classify Y and silently
fall back to uniform when Y is off-role.

### Per-query, role-aligned only

| QID | Role(s) | A | B (matched role) | Δ |
|---|---|---|---|---|
| gq-a01 | eng | 100% | 100% | tied (ceiling) |
| **gq-a02** | eng | 50% | **75% (B/eng)** | **+25pp** |
| gq-a03 | arch | 100% | 100% (B/arch) | tied (was −50pp) |
| **gq-a04** | arch | 20% | **40% (B/arch)** | **+20pp** |
| **gq-a05** | sec | 50% | **67% (B/sec)** | **+17pp** |
| gq-a06 | sec | 83% | 83% (B/sec) | tied (was −33pp) |
| **gq-a07** | fe, design_eng | 83% | **100% (B/fe)** | **+17pp** |
| **gq-a08** | fe, eng | 20% | **80% (B/fe)** | **+60pp** |
| **gq-a09** | assistant | 20% | **80% (B/asst)** | **+60pp** |
| gq-a10 | assistant | 50% | 50% (B/asst) | tied |
| **gq-a11** | pm | 0% | **50% (B/pm)** | **+50pp** |
| **gq-a12** | pm | 17% | **67% (B/pm)** | **+50pp** |
| **gq-a13** | researcher | 0% | **50% (B/res)** | **+50pp** |
| **gq-a14** | researcher | 67% | **83% (B/res)** | **+17pp** |

Of 14 role-aligned queries: 9 clean B wins, 3 tied (one a recovered
regression, one a ceiling), 0 B losses. Run 05's two losses (gq-a03, gq-a06)
are recovered. Across the original 8 atlas queries we now beat A on 5
(vs 1 in Run 05).

---

## Honest scrutiny — what we know vs what we're claiming

### Things that are *real* wins (mechanism + measurement aligned)

- **detail_level boundary fix** (0.7 → 0.8 for architect, security; 0.8 from
  the start for new roles). Mechanism: switches from `_assemble_manager`
  (module-order, role-blind) to `_assemble_practitioner` (file-scored). This
  is the largest single contributor to every architect/security/new-role
  improvement.
- **Layer weight bump** for security (presentation 0.2 → 0.5). Mechanism:
  the practitioner tier sorts by score; layer_match is a meaningful
  tiebreaker for files with already-high tag affinity. Verified by computing
  `envelope.py`'s relevance score before/after.
- **Data-driven domain_affinity** (Runs 08, 09; new roles). Adding tags that
  exist in `trace_epistemic.jsonl` (verified by frequency-counting) elevated
  the right files. Adding *intent* terms without checking the tag universe
  (Run 03 style) was inert.
- **Three new non-dev roles wins**. With practitioner-tier dispatch and
  domain_affinity targeted at planning/spec/research vocabulary, the new
  roles produce measurable lift on queries where A scored 0–20%.

### Things that are *budget-normalization*, not specialization

- **Engineering gq-a02 win**. The bisect (max_chars=3500 with all other
  changes intact) showed engineering reverted to 50% on gq-a02 — same as A.
  At max_chars=4000, eng wins 75%. The +25pp delta is largely budget parity
  with A (which already runs at 4000). Recommendation: standardize all role
  budgets at 4000 to remove this confound entirely, OR accept this is
  budget-normalized comparison and stop calling it "specialization".

### Things that did *not* move the needle

- Run 03 `domain_affinity` expansion alone (without practitioner-tier).
- Run 05 `centrality_weight` reduction in isolation.
- Run 12 engineering vector "sharpening" (removing `api`, adding compound
  terms, lowering centrality). `augmenter.py` rank stayed at 39; the 4000
  budget is what lets it surface.

### Things deferred (worth naming explicitly)

- **Manager-tier role scoring fix**. `_assemble_manager` walks
  `trace_modules.jsonl` in storage order and ignores `domain_affinity`. Any
  role with `detail_level <= 0.7` (currently: cto, design, qa, devops,
  devsecops, product, writer, data_engineer) cannot have its module
  selection influenced by calibration. A one-line `modules.sort(key=...)`
  call in that function would close the gap; it's the single most impactful
  improvement available without restructuring anything else. Out of
  calibration scope; left to the parallel workstream or a future sub-task.
- **`atlas_content=""` in eval.** `eval_runner.assemble_atlas_context`
  passes empty atlas, so neither A nor B includes
  identity/stack/cross-cutting sections. gq-a04 keywords (`hub`, `edges`,
  `cross-cutting`) live in the atlas's CROSS-CUTTING block and would lift
  *both* conditions if wired. Worth re-running once that's plumbed; relative
  deltas may shift.
- **Audience-bonus expansion**. `_compute_audience_bonus` uses a
  `TAG_TO_AUDIENCE` map in `role_projection.py` that doesn't include many
  engineering-relevant tags (`llm-orchestration`, `trace-augmentation`,
  `semantic-analysis`, `pipeline-stage`). Adding these would let
  `augmenter.py` rank higher under engineering without budget tricks. Not
  attempted to keep the changes confined to `role_vectors.py`.
- **Synonym-cluster audit**. The `_TAG_TO_CLUSTER` 0.5 synonym match is
  dominated by the 0.7 substring match in practice. Almost certainly dead
  weight; left alone.

---

## Files touched

```
src/codrag/core/atlas/role_vectors.py
   engineering: domain_affinity sharpened (-1 broad term, +6 compound),
                centrality_weight 0.5→0.4, max_chars 3500→4000
   architect:   domain_affinity +19 graph terms, detail_level 0.7→0.8
   security:    layer_weights[presentation] 0.2→0.5,
                domain_affinity +6 API terms, detail_level 0.7→0.8
   assistant:   NEW role (Personal Assistant, OpenClaw)
   pm:          NEW role (Project Manager, operational)
   researcher:  NEW role (Research Analyst)

src/codrag/core/atlas/role_resolver.py
   KEYWORD_TO_BASE: 12 new mappings for assistant/pm/researcher slugs;
                    moved 'pm', 'project', 'scrum', 'agile' from product→pm;
                    moved 'researcher' from design→researcher.

tests/eval/gold_queries.json (v1.1 → v1.2)
   +6 atlas-level queries gq-a09..a14 for new roles. Existing queries
   unmodified.

docs/Phase103_AgentOptimizations/research/
   R3_calibration_runs_06-12.md      (this file)
   HANDOFF_CALIBRATION.md            (§15 handoff-back appended)
   run{07..12}_cond*.json            (5×6 + 8×1 = 38 artifacts)
```

No source changes outside `role_vectors.py` and `role_resolver.py` and
`gold_queries.json`. Per scope: `role_projection.py`, `eval_runner.py`, the
MCP layer, and the original `gq-001..010` queries are untouched.
