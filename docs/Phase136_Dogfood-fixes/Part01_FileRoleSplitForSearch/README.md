#  File-role split for search

> **Status:** Spec / Ready for implementation
> **Date:** 2026-05-13
> **Trigger:** 2026-05-12 dogfood — agent called `prep_search` 3× for UI behavior, got planning docs back every time, gave up and ran `grep` directly. See `project_search_docs_bias` memory.

---

## TL;DR

`classify_rel_path` collapses every `.md` file into a single `"docs"` role. That's why a planning doc named `ROADMAP_DASHBOARD_PANEL.md` outranks `RoadmapPanel.tsx` for UI queries: the docs-role multiplier (`0.82` under `intent=code`) is too weak to overcome the additive basename-token boost (`+0.25`) on the MD file, and the multiplier is the same whether the MD is a roadmap or a README.

**The fix is to split `"docs"` into three sub-roles** (`planning_doc`, `reference_doc`, `generated_artifact`) and apply tighter multipliers per intent. The wiring is already in place — chunks already carry a `role` field, the ranker already applies role multipliers, the intent classifier already returns `"code"` for UI tokens. We refine one classifier and one multiplier table.

**Not in scope:** legacy/deprecated detection at file level (requires concept anchors that don't exist yet), concept→file lifecycle propagation, new pipeline stages, new metadata files.

---
## What's already built (don't rebuild)

| Surface | Where | What it does today |
|---|---|---|
| Per-chunk `role` field | `src/prep/core/index.py:466, 557, 598, 618` | Every chunk gets `role = classify_rel_path(rel_path)` at index time |
| Role-aware ranking | `src/prep/core/index.py:1231-1247` | Reads `d.get("role")`, applies `role_weight × intent_multiplier` |
| Intent classifier | `src/prep/core/index.py:_classify_query_intent` | Returns `tests | docs | code | default`. Already has `code_tokens` bucket including `component, hook, controller, router, route, schema, model` |
| Intent multipliers | `src/prep/core/index.py:_intent_role_multipliers` | `code` intent: `{code: 1.10, docs: 0.82, tests: 1.0, other: 0.85}` — already penalizes docs |
| Planning-doc constants | `src/prep/core/docs_grounding.py:PLANNING_FILENAMES`, `PLANNING_FOLDERS`, `EXCLUDED_DIRS` | Curated lists (Phase 125c T1). Currently consumed only by the concept-generation swarm |
| Roadmap keywords | `src/prep/core/roadmap_miner.py:ROADMAP_KEYWORDS`, `PLANNING_FILE_PATTERNS` | Used by roadmap visualization only |

**Observation:** the three planning-doc classifiers (`docs_grounding`, `roadmap_miner`, `repo_profile.classify_rel_path`) disagree on what counts as planning. This phase consolidates them. The downstream consumers (concept gen, roadmap miner, search ranker) all become callers of one function.

---

## The 3-task plan

### T1 — Split `classify_rel_path` to expose doc sub-roles

**File:** `src/prep/core/repo_profile.py`

Replace the single `"docs"` return with three sub-roles. Reuse `docs_grounding.PLANNING_FILENAMES` and `PLANNING_FOLDERS` — do **not** redefine them.

```python
# Pseudocode — actual implementation reads from docs_grounding module-level constants
def classify_rel_path(rel_path: str) -> str:
    p = rel_path.replace("\\", "/").lower()
    parts = [x for x in p.split("/") if x]
    stem = Path(p).stem.upper()
    ext = Path(p).suffix

    if any(part in TEST_DIR_NAMES for part in parts):
        return "tests"

    if ext in DOC_EXTS or any(part in DOC_DIR_NAMES for part in parts):
        # New: split docs into three sub-roles
        if _is_generated_artifact(rel_path):       # AGENTS.md, CLAUDE.md, GEMINI.md, .cursor/rules/*
            return "generated_artifact"
        if _is_planning_doc(rel_path, stem):       # ROADMAP, RFC, ADR, PROPOSAL, SPEC, PLAN, BACKLOG, MASTER_TODO, docs/phases/, docs/rfcs/...
            return "planning_doc"
        return "reference_doc"                     # README, ARCHITECTURE, CHANGELOG, docs/api/, docs/guides/

    if ext in CODE_EXTS or any(part in CODE_DIR_NAMES for part in parts):
        return "code"

    return "other"
```

**Helpers** (inline, ~15 LOC total):

```python
def _is_generated_artifact(rel_path: str) -> bool:
    stem = Path(rel_path).stem.upper()
    return stem in {"AGENTS", "CLAUDE", "GEMINI", "CURSOR", "WINDSURF"} or \
           rel_path.startswith((".cursor/rules/", ".windsurf/rules/", ".github/instructions/"))

def _is_planning_doc(rel_path: str, stem: str) -> bool:
    from prep.core.docs_grounding import PLANNING_FILENAMES, PLANNING_FOLDERS
    if stem in PLANNING_FILENAMES:
        return True
    rel = rel_path.replace("\\", "/")
    return any(rel.startswith(f + "/") for f in PLANNING_FOLDERS)
```

Why reuse the `docs_grounding` constants: they're already vetted, already exported, and the concept-generation swarm depends on them. One source of truth, three consumers.

### T2 — Extend `_intent_role_multipliers` for the new roles

**File:** `src/prep/core/index.py` (lines ~1100–1110)

Add multipliers for the three new doc sub-roles. Tighten the penalty on `planning_doc` and `generated_artifact` under code intent; promote `planning_doc` under a new (small) `planning` intent.

```python
def _intent_role_multipliers(self, intent: str) -> Dict[str, float]:
    if intent == "docs":
        return {
            "code": 0.95, "tests": 0.95,
            "reference_doc": 1.25,   # README/ARCHITECTURE — primary docs answer
            "planning_doc": 1.05,    # roadmaps surface but don't dominate
            "generated_artifact": 0.70,  # AGENTS.md is auto-generated noise
            "other": 0.90,
        }
    if intent == "planning":
        return {
            "code": 0.90, "tests": 0.85,
            "planning_doc": 1.35,    # primary answer for "plan for X"
            "reference_doc": 1.05,
            "generated_artifact": 0.60,
            "other": 0.85,
        }
    if intent == "tests":
        return {
            "tests": 1.15, "code": 1.0,
            "reference_doc": 0.90, "planning_doc": 0.85,
            "generated_artifact": 0.60, "other": 0.90,
        }
    if intent == "code":
        return {
            "code": 1.10, "tests": 1.0,
            "reference_doc": 0.85,   # was docs: 0.82
            "planning_doc": 0.65,    # ← the fix: stronger penalty
            "generated_artifact": 0.55,  # ← AGENTS.md must not win UI queries
            "other": 0.85,
        }
    # default: mild code bias — Prep primarily serves AI coding tools
    return {
        "code": 1.05,
        "reference_doc": 0.92, "planning_doc": 0.82,
        "generated_artifact": 0.65,
        "tests": 1.0, "other": 0.95,
    }
```

Backward-compat note: callers that look up `role="docs"` (e.g. some tests, possibly `repo_policy.json` configs) need a shim. Two options:
- **a)** Keep `"docs"` as a synonym in the multiplier dict (sum of the three sub-roles, weighted), so legacy `role_weights` configs still work.
- **b)** Migrate `repo_policy.json` at load time: split a single `docs` entry into the three sub-roles.

Pick **(a)** for simplicity. Add `"docs"` back to each dict with a sensible average. Document in code comment.

### T3 — Add `planning` intent to `_classify_query_intent`

**File:** `src/prep/core/index.py` (lines ~990–1080)

Add a `planning_tokens` set and route to `"planning"` intent before `"docs"`. Order matters: `planning` should beat the broader `docs` bucket when present.

```python
planning_tokens = {
    "plan", "plans", "planning", "roadmap", "roadmaps",
    "milestone", "milestones", "sprint", "backlog",
    "phase", "rfc", "rfcs", "adr", "proposal", "spec",
    "design-doc", "future", "upcoming", "next-steps",
    "todo", "wip",
}

# ... earlier checks: tests_tokens, debug_tokens

if tokens & planning_tokens:
    return "planning"
if tokens & docs_tokens:
    return "docs"
if tokens & code_tokens:
    return "code"
return "default"
```

Evaluate `planning_tokens` **before** `docs_tokens` because `"design"` already lives in `docs_tokens` and we want `"design-doc"` / `"rfc"` queries to prefer planning.

---

## Acceptance tests

Create `tests/test_search_role_priors.py`:

1. **The dogfood regression** — corpus with `RoadmapPanel.tsx` and `ROADMAP_DASHBOARD_PANEL.md`. Query `"where is the dashboard panel"`. Expect: `.tsx` ranks above `.md`. Currently fails.

2. **Inverse (planning intent)** — same corpus. Query `"plan for dashboard panel"`. Expect: `.md` ranks above `.tsx`.

3. **Generated artifact suppression** — corpus includes an `AGENTS.md` with topical content. Query `"component implementation"`. Expect: `AGENTS.md` does not appear in top-3.

4. **Reference doc preserved under docs intent** — query `"architecture overview"`. Expect: `docs/ARCHITECTURE.md` wins over both `.tsx` and `ROADMAP*.md`.

5. **`classify_rel_path` table** — direct unit test of the new classifier covering every sub-role.

6. **Backward-compat shim** — `repo_policy.json` with `"docs": 0.9` still works; effective weight is applied to all three sub-roles.

---

## Effort & scope

- **2 files modified**: `src/prep/core/repo_profile.py`, `src/prep/core/index.py`
- **1 file imported from**: `src/prep/core/docs_grounding.py` (no changes there)
- **1 test file added**: `tests/test_search_role_priors.py`
- **No new modules, no schema migration, no pipeline stage**
- **Estimated LOC**: ~80 production, ~150 test

## Non-goals (explicit)

- **Legacy/deprecated detection at file level** — needs concept anchors. Project currently has 0 active concepts; deferred to Phase 136+ when concepts populate via Phase 125c.
- **Concept→file lifecycle propagation** — same blocker as above.
- **Git-age / staleness signal** — could feed into a `legacy_doc` sub-role later; out of scope here.
- **Consolidating `roadmap_miner` and `docs_grounding`** — both still call their own classifiers internally. We add a *third* consumer (the ranker) but keep their internals untouched. A future cleanup phase can hoist the shared logic into one helper.
- **MMR / reranker changes** — the existing MMR diversity pass is untouched.

## Risks

1. **Tightening the planning_doc penalty may break "where is X documented" if that query has UI tokens.** Mitigation: `docs_tokens` triggers `intent="docs"` which gives `reference_doc: 1.25`, and `planning_doc` is only 1.05 there — still surfaces, doesn't dominate.

2. **Test mode pollution: tests subfolder under `docs/`** (e.g. `docs/examples/test-fixtures/`) might trip the `tests` classifier. Mitigation: `tests` is keyed on `TEST_DIR_NAMES` which is `__tests__`, `tests/`, `test/`, `__test__`, `spec/`, `specs/` — `docs/` is checked first via extension. Verify with table test.

3. **`AGENTS.md` legitimately has tool guidance an agent might want.** Mitigation: it still appears in results, just heavily penalized for code intent. Primer-boost in `_primer_boosts` (`index.py:2091`) still gives it a +0.25 baseline for matching primer queries, which is unchanged by this phase.

4. **`repo_policy.json` files in customer projects with `role_weights: {docs: ...}`** — handled by the backward-compat shim. Verified by acceptance test #6.

## Out of scope but worth flagging

- The three planning classifiers (`docs_grounding`, `roadmap_miner`, `repo_profile`) duplicate intent and will drift. A Phase 136 cleanup could fold them into a single `prep.core.file_role` module. Out of scope here because the immediate fix doesn't need it.
- `_classify_query_intent` is rule-based with hand-curated token sets. For long queries with mixed intent ("show me the code that implements the roadmap for X"), classification is brittle. A small LLM rerank could replace this but adds latency and complexity — not now.
- The atlas's `LAYERS` field (`presentation: 533, business_logic: 178, documentation: 836`) is currently unused by search. Could be a future axis for finer-grained code roles (`presentation_code` vs `business_logic_code` vs `infrastructure_code`). Defer.
