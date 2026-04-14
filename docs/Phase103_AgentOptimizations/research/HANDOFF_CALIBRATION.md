# HANDOFF — Role Vector Calibration & Fine-Tuning

**To:** whichever AI picks this up next.
**From:** prior session that scoped, built, and first-pass calibrated the Phase 103 R3 harness.
**Scope:** calibrating CoDRAG's role vectors and the atlas-scoring loop so that condition B (role-weighted sub-atlas) measurably outperforms condition A (uniform baseline) on role-aligned queries. **Nothing else.** See "Out of scope" below.

Read this once top to bottom, then start at §8. The links point to already-committed artifacts you can inspect directly.

---

## 1. TL;DR — your mission in one paragraph

The CoDRAG product serves role-scoped codebase context via `codrag(role=X)` over MCP. Phase 103 asks: **does role-weighted sub-atlas delivery outperform uniform-atlas delivery for code tasks?** A harness exists (`tests/eval/eval_runner.py` atlas mode) that runs 18 gold queries across 5 conditions and produces scored results. Prior work established the plumbing, ran baselines, and made one calibration pass that **did not move the needle** on aggregate. Your job is to keep tuning — role vectors, scorer, gold queries, assembly tiers — until role-aligned queries show a clean knowledge-honing win on matched-role B conditions. Leave query classification, routing, MCP API, emission, and everything else to the parallel workstream.

---

## 2. The thesis in plain terms

We do **knowledge-honing**, not persona-prompting. We don't tell the agent "you are a security engineer." We change what the agent *sees* — serve a sub-atlas weighted by the role's domain tags, layer affinities, hub centrality, and detail level. Same agent, same instructions, different corpus.

Persona-prompting research (arxiv 2603.18507) shows mixed-to-negative effects — does not apply to us. Our mechanism is untested in the literature; R3 is the first rigorous test.

**Distinct R3 patterns (decision framework):**
- **Pattern 1/2/5:** knowledge-honing produces measurable lift on role-aligned queries → ship.
- **Pattern 3:** specialization hurts across the board → contrarian finding, strip role scoping.
- **Pattern 4:** nothing moves at our budgets → tune (your job) before declaring null.

We are currently in **calibrated Pattern 4-ish territory**: one strong per-query win (gq-a08 frontend: 20% → 80%), flat aggregates. Your goal is to push the aggregate B > A on role-aligned queries.

---

## 3. Environment — you are working in this isolated worktree

```
/Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/phase103-poc/
```

**Branch:** `phase103-poc` (3 commits ahead of `main`).

**Isolation model:**
- `.venv/` → symlink to main-tree `/Volumes/4TB-BAD/HumanAI/CoDRAG/.venv`.
- `codrag_data_poc/` → isolated runtime data dir (use `CODRAG_DATA_DIR=$(pwd)/codrag_data_poc` when invoking anything that writes).
- Index source: the **main tree's** live `.codrag/` at `/Volumes/4TB-BAD/HumanAI/CoDRAG/.codrag/` (read-only from our side). The daemon keeps it fresh. 26,435 nodes / 39,476 edges, embedded mode.
- `eval_runner` is read-only against the index. No runs mutate main-tree data.

**All commands assume CWD = the worktree path above.**

### Venv / import discipline

```bash
# Python invocation template (always)
PYTHONPATH=src .venv/bin/python -m tests.eval.eval_runner [args]
```

Don't `pip install codrag` — it's the project itself.
Don't use system `python` — always `.venv/bin/python`.

---

## 4. The mechanism you are calibrating

### 4.1 Role vector definition (the knob)

**File:** `src/codrag/core/atlas/role_vectors.py`

A `RoleVector` has four tunables that affect projection output:

```python
@dataclass
class RoleVector:
    layer_weights: Dict[str, float]   # per-architecture-layer weight (0..1)
    domain_affinity: List[str]        # keywords fuzzy-matched vs file tags
    centrality_weight: float          # 0=niche/leaves, 1=hubs
    detail_level: float               # 0=exec summary, 1=practitioner code detail
    max_chars: int                    # budget of projected text
```

All built-in roles live in `BUILT_IN_ROLES` dict. Current targets of active tuning: `"security"` and `"architect"`.

### 4.2 Scoring (how a file gets picked)

**File:** `src/codrag/core/atlas/role_vectors.py::max_tag_affinity`

For each file, compute affinity vs role keywords:
- Exact match: 1.0
- Substring (`"auth"` in `"authentication"`): 0.7
- Synonym cluster: 0.5

Max over all (tag, keyword) pairs. **Implication:** adding unambiguous compound terms (`admin-policy`) helps. Adding short broad terms (`auth`) invites false positives via substring (matches `authoring_experience`).

### 4.3 Projection pipeline

**File:** `src/codrag/core/atlas/role_projection.py::project_atlas_for_role`

Flow: load modules/epistemic → score files → route to `_assemble_executive/_manager/_practitioner` based on `detail_level` → trim to `max_chars`. Rust fast-path tried first; Python fallback if unavailable.

Reads from `index_dir/trace_modules.jsonl`, `trace_epistemic.jsonl`, `atlas.json`. **No caching** — changes to role_vectors.py flow through immediately on next call. (Verified: Runs 04 and 05 reflected tier changes.)

### 4.4 Neutral baseline (condition A)

**File:** `tests/eval/eval_runner.py::_neutral_role_vector`

IMPORTANT methodology note: the neutral role used to derive its `domain_affinity` as **union of all BUILT_IN_ROLES**. That meant tuning any role also boosted A — a confound. **Fixed in current HEAD:** neutral uses a fixed, codebase-universal term set (top-frequency tags) that does NOT depend on role definitions. **Keep this invariant.** If you find yourself reaching for `BUILT_IN_ROLES.values()` in the neutral function, stop and think.

---

## 5. What's already been measured

All results live in `docs/Phase103_AgentOptimizations/research/`. Read them if you want full detail; this section is a cheat sheet.

| Run | What changed | Key numbers |
|---|---|---|
| 01 (`R3_baseline_run_01.md`) | original strict scorer, 10 search-level gold queries | A=24.8%, B=15–18%. Scorer too strict. |
| 02 (`R3_baseline_run_02.md`) | loose scorer (stem matching + parent-dir file match) + 8 new atlas-tagged queries (`gq-a01..gq-a08`, tagged with owning roles) | A=51.2%, B=45–48%. A leads; role-aligned signal: **gq-a08 frontend 20% → 80%**, gq-a02 engineering 25% → 50%. |
| 03 | +12 `domain_affinity` terms each to security + architect | A=56.5% (confound — old neutral derived from union-of-roles), B flat. |
| 04 | neutral baseline isolated (methodology fix) | A=55.6%, B flat. **Run 04 is the honest current baseline.** |
| 05 | architect `detail_level` 0.5→0.7, `centrality_weight` 0.8→0.6 | **Identical to Run 04.** Aggregate did not move. |

### Per-query deltas worth memorizing

Where knowledge-honing **wins**:
- **gq-a08** (frontend + frontend role): A=20%, B/fe=80%. +60pp. Proof of mechanism.
- **gq-a07** (frontend + frontend role): A=83%, B/fe=100%. +17pp.
- **gq-a02** (engineering + eng role): A=50%, B/eng=50%. tied (was +25pp in Run 02).
- **gq-a04** (architect + arch role): A=20%, B/arch=40%. +20pp.

Where it **loses**:
- **gq-a03** (architect + arch role, entry-point question): A=100%, B/arch=50%. −50pp.
- **gq-a06** (security + sec role, API envelope + auth): A=83%, B/sec=50%. −33pp.

**Interpreted:** role specialization helps on narrow role-aligned queries (frontend components, engineering pipeline details) and hurts on **meta / cross-cutting** queries (entry points span everything; API+auth combined spans multiple concerns). This is mechanistically sensible — narrowing a filter removes breadth.

Your lever is to (a) boost performance on the winning cases further, and (b) close the gap on losing cases without killing the neutral.

---

## 6. Out of scope — do NOT touch these

The parallel workstream owns:
- **Query classification / routing** (choosing between role projection and uniform atlas per task). This is an R4 universal-API item; DO NOT start building it in this handoff's scope.
- **The MCP tool signature** (`codrag()` parameters). Out of bounds.
- **Emission targets** (`.claude/agents/*.md`, OpenClaw SOUL.md, Cursor rules).
- **Hooks** (PostToolUse, PreToolUse, antibodies).
- **Concept promotion, temporal validity, auto-observation** — Phase 103 b/c/d.
- **Rewriting `project_atlas_for_role`** or the Rust fast-path engine. You can inspect; don't refactor.
- **`gold_queries.json` v1.0 entries (`gq-001..gq-010`)**. Those measure the legacy search path. You may **add** new atlas-level queries (use the `gq-a*` prefix); do not edit or remove existing ones.

If you find yourself needing changes in those areas to make calibration work, **write a note at the bottom of this file** and stop. Don't branch into their scope.

---

## 7. Levers available — ranked by current plausibility

### Tier 1 — most likely to move the needle

1. **Examine the frontend role vector as a template** (`src/codrag/core/atlas/role_vectors.py::"frontend"`). Frontend is the cleanest win (`gq-a08` 20% → 80%). Compare its `domain_affinity` length, term specificity, layer_weights distribution, and centrality to architect/security. Apply that pattern structurally. Success signal: security gq-a06 closes the 33pp gap without cannibalizing A on unrelated queries.

2. **Expand role-aligned gold queries from 2 per role to 5–6 per role.** N=2 makes single-query noise dominate. Add 3–4 per role such that they span:
   - One narrow niche query (where B should win cleanly).
   - One moderate cross-role query (mixed signal expected).
   - One deliberately-meta query (where A is *supposed* to win; confirms specialization isn't breaking too much).
   - One query for a file you know is in the role's scope but not already named in the other queries.

   Each query goes in `tests/eval/gold_queries.json` with the format of `gq-a01..gq-a08`. Include `"roles": [...]` field. Keep v1.0 `gq-001..gq-010` untouched.

3. **Tune the scoring functions** in `tests/eval/eval_runner.py`. Current scorer uses substring-or-stem for keywords, and full/basename/parent/module-ancestor for files. Consider:
   - File-match minimum segment length is 4 chars. "cli" (3 chars) currently fails module-ancestor matching. Lowering to 3 may help but risks false positives on `src/`, `py`. Measure.
   - Keyword stemming strips common suffixes. Add a prefix strip too? Add a short-token (`mcp`, `cli`) whitelist that bypasses the stem-length floor?
   - Penalty for content-length difference: currently long answers are rewarded (more text = more substring hits). Consider dividing by `sqrt(atlas_chars)` or something. Empirically test.

### Tier 2 — worth exploring if Tier 1 doesn't move the needle

4. **Explore `layer_weights` more aggressively.** We've kept these stable. `security`'s `data=0.7`, `infrastructure=0.6` may undercount what admin_policy / api_envelope are tagged as. Dump the architecture_layer distribution for security-relevant files and compare.

5. **Try harder on `detail_level`.** Run 05 bumped architect to 0.7 with no effect. That's suspicious. Verify by manually printing the 3 tier outputs (`_assemble_executive/manager/practitioner`) for the same role — if they're very similar, detail_level is a weak lever and we should document that.

6. **Synonym-cluster audit** (`_TAG_TO_CLUSTER` in role_vectors.py). The 0.5 synonym-match fires when terms share a cluster. We don't know what our clusters are. Run a diagnostic that prints, for security's `domain_affinity`, which actual file tags fire on synonym match vs substring match. If substring is dominating, clusters are dead weight.

### Tier 3 — deeper changes; flag before doing

7. **Alter `max_chars` per role** — frontend is at practitioner budget (3500); security at 2500. Run a `max_chars=4000` pass for security. If it rises on role-aligned queries without moving A, specialization needs more budget to express itself.

8. **Inspect the Rust scoring fast-path** (`_try_rust_scoring`). If it's producing different scores than Python fallback, that's a confound. Force Python path (flip a flag) and compare. Don't modify the Rust engine.

---

## 8. How to run the harness (copy-paste ready)

### 8.1 Full 5-condition sweep (the standard measurement)

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/phase103-poc

RUN=06   # increment per run
RESULTS_DIR=docs/Phase103_AgentOptimizations/research

for cfg in "A::run${RUN}_condA" \
           "B:engineering:run${RUN}_condB_eng" \
           "B:security:run${RUN}_condB_sec" \
           "B:architect:run${RUN}_condB_arch" \
           "B:frontend:run${RUN}_condB_fe"; do
  cond=$(echo "$cfg" | cut -d: -f1)
  role=$(echo "$cfg" | cut -d: -f2)
  label=$(echo "$cfg" | cut -d: -f3)
  out_json="$RESULTS_DIR/${label}.json"
  if [ -n "$role" ]; then
    PYTHONPATH=src .venv/bin/python -m tests.eval.eval_runner \
      --repo /Volumes/4TB-BAD/HumanAI/CoDRAG \
      --mode atlas --condition $cond --role $role \
      --output-json "$out_json" > /dev/null 2>&1
  else
    PYTHONPATH=src .venv/bin/python -m tests.eval.eval_runner \
      --repo /Volumes/4TB-BAD/HumanAI/CoDRAG \
      --mode atlas --condition $cond \
      --output-json "$out_json" > /dev/null 2>&1
  fi
done
```

### 8.2 Aggregate results table

```bash
PYTHONPATH=src .venv/bin/python -c "
import json
from pathlib import Path
R = Path('docs/Phase103_AgentOptimizations/research')
RUN = '06'  # match above
configs = [('A uniform', f'run{RUN}_condA.json'),
           ('B eng', f'run{RUN}_condB_eng.json'),
           ('B sec', f'run{RUN}_condB_sec.json'),
           ('B arch', f'run{RUN}_condB_arch.json'),
           ('B fe',  f'run{RUN}_condB_fe.json')]
data = {l: json.loads((R/f).read_text()) for l,f in configs}
gold = json.load(open('tests/eval/gold_queries.json'))
meta = {q['id']: q.get('roles',[]) for q in gold['queries']}
queries = [r['query_id'] for r in data['A uniform']['results']]
print(f\"{'QID':<8} {'Roles':<24}\", end='')
for l,_ in configs: print(f'  {l:>10}', end='')
print()
for qid in queries:
    rs = ','.join(meta.get(qid,[])) or '-'
    print(f'{qid:<8} {rs:<24}', end='')
    for l,_ in configs:
        r = next(rr for rr in data[l]['results'] if rr['query_id']==qid)
        m='P' if r['passed'] else ' '
        print(f\"  {r['score']*100:5.1f}%{m}\", end='')
    print()
print()
for l,_ in configs:
    s = data[l]['summary']
    print(f\"  {l:<10} pass={s['passed']}/{s['total']} avg={s['avg_score']*100:.1f}%\")
"
```

### 8.3 Single-query diagnostic (use this a lot)

```bash
PYTHONPATH=src .venv/bin/python -m tests.eval.eval_runner \
  --repo /Volumes/4TB-BAD/HumanAI/CoDRAG \
  --mode atlas --condition B --role security \
  --query gq-a06 --verbose
```

### 8.4 Inspect projection for any role

```bash
PYTHONPATH=src .venv/bin/python -c "
from pathlib import Path
from codrag.core.atlas.role_resolver import resolve_role
from codrag.core.atlas.role_projection import project_atlas_for_role
rv = resolve_role('security')
text = project_atlas_for_role(rv, Path('/Volumes/4TB-BAD/HumanAI/CoDRAG/.codrag'))
print(f'len={len(text)}'); print(text)
"
```

### 8.5 Discover what tags exist in the data

```bash
PYTHONPATH=src .venv/bin/python -c "
import json
from collections import Counter
c = Counter()
with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/.codrag/trace_epistemic.jsonl') as f:
    for line in f:
        try:
            for t in json.loads(line).get('domain_tags',[]): c[t]+=1
        except Exception: pass
for tag, n in c.most_common(80):
    print(f'{n:5d}  {tag}')
"
```

---

## 9. Data pointers

### Where things live

```
src/codrag/core/atlas/
  role_vectors.py       BUILT_IN_ROLES dict + RoleVector class + synonym clusters
  role_projection.py    project_atlas_for_role() + scoring + assembly tiers
  role_resolver.py      slug → RoleVector (fuzzy matching, keyword decomposition)

tests/eval/
  eval_runner.py        harness — atlas mode, conditions, loose scorer, JSON output
  gold_queries.json     v1.1 — 10 search queries + 8 atlas queries with roles

/Volumes/4TB-BAD/HumanAI/CoDRAG/.codrag/          (live CoDRAG self-index, read-only)
  atlas.json             identity + stack + module map
  trace_modules.jsonl    module summaries (what project_atlas_for_role consumes)
  trace_epistemic.jsonl  per-file tags, layers, epistemic confidence
  trace_edges.jsonl      dependency edges (for centrality)
  trace_nodes.jsonl      file-level metadata
  atlas_roles/*.txt      precomputed role projections (we don't use; verify if suspicious)

docs/Phase103_AgentOptimizations/research/       (all your results go here)
  R3_baseline_run_01.md, _run_02.md               deep prior writeups
  R3_calibration_runs_03-05.md                    most recent prior writeup
  run{01..05}_cond*.json                          artifacts per condition per run
  HANDOFF_CALIBRATION.md                          ← this file
```

### The 8 atlas queries you're optimizing against

```
gq-a01 engineering              pipeline orchestration modules
gq-a02 engineering              embedding generation service layer
gq-a03 architect                architectural entry points
gq-a04 architect                hub files in dependency graph
gq-a05 security                 admin policy + permissions
gq-a06 security                 API envelope + auth
gq-a07 frontend, design_engineer  UI packages for dashboard
gq-a08 frontend, engineering    VS Code extension integration
```

---

## 10. Research anchors (read if pattern 4 persists)

The prior session already surveyed these. Cited for your convenience:

- **Confidence-Calibrated RAG (Ozaki et al., 2025)** — document ordering + prompt structure affect output certainty. Could inform how we *order* content within the assembled sub-atlas.
- **Fine-Tune Embedding Models for RAG (Redis, 2025)** — +7% lift with 6K samples. Overkill for now; flag if we're stuck after all Tier 1+2 levers.
- **Latent Query Alignment (ICIC 2025)** — contrastive alignment between query and document embeddings. Heavy machinery.
- **Codebase-Memory (arxiv 2603.27277)** — tree-sitter KG via MCP; direct benchmark template for external comparison.
- **Node-weighted centrality hybridization (Springer Open)** — node weights vs edge weights; could inform whether our centrality_weight application is sound.
- **Graph centrality in Neo4j docs** — PageRank vs Betweenness vs Closeness are semantically different; we currently use in-degree. Worth auditing.

Don't lose a day on research. If Tier 1 levers aren't working, one of the above may unblock; otherwise focus on measurement.

---

## 11. Success criteria

In priority order, any of these constitutes a success you can hand back:

1. **Primary:** on the 8 atlas-level queries, matched-role B condition beats A uniform by ≥5pp on **role-aligned** queries (a01/a02 for eng, a03/a04 for arch, a05/a06 for sec, a07/a08 for fe). In Run 05, only frontend achieved this cleanly. Your target: engineering + architect + security also achieve it on at least one of their two queries.

2. **Secondary:** the weakest per-query gap (currently gq-a03 at A=100% vs B/arch=50%) closes to within ≤15pp without any other regression.

3. **Tertiary:** N per role rises to ≥5 queries via new gold entries, and the variance of per-query scores within a role drops (i.e., the role's mean score is a more stable indicator).

4. **Fallback:** if after serious effort you cannot push aggregate B > A, **document why** (with data) and identify the mechanism-level reason. A clear "specialization can't beat uniform without routing" paper is valuable — it hands the parallel workstream the right framing for query classification.

---

## 12. Working discipline (please follow)

- **One change per run.** Don't tune `domain_affinity` + `centrality_weight` + `max_chars` simultaneously. Bisect.
- **Commit every run.** Fresh JSON artifacts belong with the run that produced them. Use the `run{N}_*` naming convention.
- **Write a run writeup** (`R3_runs_06-NN.md` or similar) each time you advance — describe the hypothesis tested, changes, numbers, interpretation. Prior writeups are templates.
- **Never commit `.venv`**. It's a symlink.
- **Never add new files to `tests/eval/`** — that directory is gitignored but individual tracked files can still be committed. Use `git add <specific-path>`. New eval files go elsewhere.
- **Commit message format:** `phase103-poc: <what> <Run N outcome>` — see `git log --oneline phase103-poc ^main`.
- **No Co-Authored-By trailer** per repo convention.
- **Stay in the worktree.** Don't edit main-tree files.

---

## 13. Known quirks

- `.codrag/atlas_roles/*.txt` exists as precomputed projections — **NOT currently read** by role_projection.py. Ignored. Don't worry about invalidating them.
- The `_stem` function strips many suffixes but is intentionally lightweight. Don't swap in Porter without measuring first.
- `codrag()` MCP tool has a `role` parameter already. Don't change its schema; the atlas harness exists to measure what the tool's scoped path returns.
- Main-tree `tests/eval/` is gitignored at the directory level, but `eval_runner.py` is a tracked file — so `git add tests/eval/eval_runner.py` works, `git add tests/eval/new_helper.py` does not. If you need new test helpers, put them in `tests/` directly.

---

## 14. When you think you're done

1. Update your writeup (`R3_runs_06-NN.md`) with final numbers.
2. Make sure all run JSON artifacts are committed.
3. Leave the role_vectors.py in a state where the `"security"` and `"architect"` vectors are your best-tuned version (keep intermediate explorations in commits, not in working tree).
4. Append a **"calibration handoff back"** section to the bottom of *this* file (section 15 below), briefly noting what works, what didn't, and what the parallel workstream should know before integrating.
5. Don't merge to main without the lead's sign-off.

---

## 15. Calibration handoff back (Runs 06–11)

Full writeup: `R3_calibration_runs_06-11.md`. TL;DR below.

### (a) Final numbers (Run 11)

```
QID      Roles                        A         B eng     B sec     B arch    B fe
gq-a01   engineering               100.0%P  100.0%P    60.0%P  100.0%P    20.0%
gq-a02   engineering                50.0%P   75.0%P  ← +25    50.0%P    75.0%P    25.0%
gq-a03   architect                 100.0%P   83.3%P    83.3%P  100.0%P    83.3%P
gq-a04   architect                  20.0%    20.0%     20.0%    40.0%  ← +20  40.0%
gq-a05   security                   50.0%P   33.3%     66.7%P ← +17  33.3%    33.3%
gq-a06   security                   83.3%P   50.0%P    83.3%P   50.0%P    83.3%P
gq-a07   frontend, design_engineer  83.3%P   50.0%P    50.0%P   83.3%P   100.0%P ← +17
gq-a08   frontend, engineering      20.0%     0.0%      0.0%    20.0%    80.0%P ← +60

Aggregate:  A=55.6%   eng=53.8%   sec=45.9%   arch=54.6%   fe=48.7%
```

**Success criterion #1 met:** every tuned role beats A by ≥5pp on at least one
of its role-aligned queries. Recovered Run 05's two losing queries (gq-a03
−50pp → 0pp, gq-a06 −33pp → 0pp).

### (b) Levers that moved the needle

1. **`detail_level` boundary 0.7 → 0.8 for architect + security.** This was
   the load-bearing change. `role_projection.py:578` dispatches `<=0.7` to
   `_assemble_manager`, which iterates modules in JSONL order and ignores
   `domain_affinity` for module selection. `>0.7` routes to
   `_assemble_practitioner`, where files are sorted by role relevance score
   before assembly. Engineering and frontend (full_stack) were already at
   0.8. Architect and security were quietly disabled at 0.7. **All Run 03–05
   `domain_affinity` work was inert for these two roles** because of this
   single dispatch.
2. **`layer_weights["presentation"]` 0.2 → 0.5 for security.** Necessary
   complement to (1). Once practitioner tier is sorting by score,
   `layer_match` becomes a meaningful tiebreaker. Security was scoring
   `envelope.py` at 0.488 vs `audit_log.py` at 0.663 — the layer bump moved
   API-layer security files into the top cut.
3. **Data-driven `domain_affinity` expansion.** Adding tags that genuinely
   exist in `trace_epistemic.jsonl` (`dependency-graph`, `trace-augmentation`,
   `response-envelope`, etc.) elevated the right files. Adding *intent*
   keywords without checking the tag universe (Run 03 style) doesn't help.
4. **`max_chars` 3500 → 4000 for engineering.** Closed the budget gap with A.
   Let `augmenter.py` surface alongside `embedder.py`.

### (c) Levers that did NOT move the needle (and why)

- Run 03 keyword expansion alone — bypassed the practitioner tier dispatch.
- Run 05 `centrality_weight` reduction — manager tier doesn't sort modules by
  anything, so module-side knobs were inert.
- Run 10 engineering keyword expansion alone — surfaced the right files
  semantically but they got cut at the budget line. Needed the budget bump.

### (d) Open questions for the query-classification workstream

1. **Manager-tier roles can't be calibrated.** `_assemble_manager` walks
   `trace_modules.jsonl` in storage order. Any role with `detail_level <= 0.7`
   (currently: cto, design, qa, devops, devsecops, product, writer,
   data_engineer) cannot have its module selection influenced by
   `domain_affinity`. A one-line sort in that function would close the gap;
   it's the single most impactful improvement available without changing
   anything else. Suggest the parallel workstream owns this since it's a
   structural fix to projection, not calibration.
2. **B/sec aggregate still trails A by 10pp** despite per-query wins. Of
   security's 18 evaluated queries, only 2 are security-aligned. The other 16
   pay a specialization tax for narrowing the filter. **This is the routing
   problem you're scoping** — `codrag(role=X, task=Y)` should classify Y and
   fall back to uniform when Y isn't role-aligned.
3. **Asymmetric budgets distort comparisons.** A neutral runs at
   `max_chars=4000`; tuned roles ranged from 2500 (security, qa, design) to
   3500 (engineering, full_stack). Smaller budgets structurally disadvantage
   B even when role scoring is correct. Either standardize at 4000 or accept
   that aggregate comparisons need budget-normalization.
4. **`atlas_content=""` in eval.** `eval_runner.assemble_atlas_context` passes
   empty atlas, so neither A nor B includes identity/stack/cross-cutting
   sections. gq-a04 keywords (`hub`, `edges`, `cross-cutting`) live in the
   atlas's CROSS-CUTTING block and would benefit *both* conditions. Wiring
   real atlas content through eval would lift both A and B; relative deltas
   may shift.

### (e) Files touched

- `src/codrag/core/atlas/role_vectors.py` — engineering / architect / security
  vector tuning. Three roles modified; all others untouched.
- `docs/Phase103_AgentOptimizations/research/R3_calibration_runs_06-11.md` —
  full per-run writeup.
- `docs/Phase103_AgentOptimizations/research/run{06..11}_cond*.json` — 30 run
  artifacts (5 conditions × 6 runs).
- `docs/Phase103_AgentOptimizations/research/HANDOFF_CALIBRATION.md` — this
  section.

No source changes outside `role_vectors.py`. Per scope, nothing was modified
in `role_projection.py`, `eval_runner.py`, gold queries, or the MCP layer.

---

**End of handoff. Start at §7 Tier 1 and iterate. Good luck.**
