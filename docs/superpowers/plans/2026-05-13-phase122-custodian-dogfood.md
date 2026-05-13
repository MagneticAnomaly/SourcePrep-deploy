# Phase 122 — Custodian Dogfood Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triage the 11 pending modules in `docs/INTENTIONALLY_DORMANT.md` to a decision by dogfooding the existing Custodian engine; record decisions back into the registry and into `docs/MASTER_TODO.md` as follow-up lines.

**Architecture:** A small driver script (`tools/phase122_custodian_run.py`, ~60 LoC) imports the production helpers from `prep.api.routers.agents` (`_get_engine_context`, `_make_core`, `_get_llm_fn`), constructs synthetic `dead_code` findings for the 11 candidates, calls `CustodianEngine.run(..., dry_run=True)`, and persists the verdicts to `docs/Phase122_FeatureUtilizationAudit/custodian_run.json`. A human then runs a confirmation pass (grep, git log, marketing check) on each verdict, applies a 5-bucket rubric, and writes one entry per module into `docs/INTENTIONALLY_DORMANT.md` plus a tracker line in `docs/MASTER_TODO.md` when the decision is DEPRECATE / DELETE / NEEDS-OWNER. No production code is touched; the LLM's `dependent_count` will always be 0 because of the `prep_impact` bug filed as P122-D1/D2/D3, so the human grep is the safety net.

**Tech Stack:** Python 3.11, pytest, existing `prep.agents.custodian.engine.CustodianEngine`, existing daemon LLM factory. Project venv at `.venv/`.

**Spec:** `docs/superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md`

---

## File Structure

| Path | Action | Purpose |
|---|---|---|
| `tools/phase122_custodian_run.py` | Create (~60 LoC) | Driver script. Builds synthetic findings, runs engine, dumps JSON. Stdlib + project imports only. |
| `tests/test_phase122_custodian_run.py` | Create (~40 LoC) | Unit tests for the findings-list builder. Engine call is exercised once manually, not asserted. |
| `docs/Phase122_FeatureUtilizationAudit/custodian_run.json` | Create | Captured run log from the engine. Machine-readable. |
| `docs/Phase122_FeatureUtilizationAudit/RESULTS.md` | Create | Summary doc — what the Custodian said, what human confirmation changed, bucket distribution. |
| `docs/INTENTIONALLY_DORMANT.md` | Edit | 11 entries promoted from "pending" → full triage block. 3 already-WIRED entries removed (`antibody_derivation`, `rules_generator`, `concept_seeder`). |
| `docs/MASTER_TODO.md` | Edit | Append a Phase 122 follow-up section with one tracker line per DEPRECATE / DELETE / NEEDS-OWNER decision. |

The 11 candidate modules (in plan-task order):

1. `roadmap_miner.py`
2. `treatment_registry.py`
3. `swarm_optimizer.py`
4. `lod_extractor.py`
5. `github_sync.py`
6. `budget_enforcement.py`
7. `chunking.py`
8. `inferred_edges.py`
9. `batch_profiles.py`
10. `swarm_registry.py`
11. `context_config.py`

---

## Task 1: Pre-flight verification

**Files:** none (verification only).

- [ ] **Step 1: Confirm daemon is running and the project resolves**

Run:
```bash
curl -s http://localhost:8400/projects/f1636374-abc6-410d-99ee-822120379e79 | head -c 300
```

Expected: JSON beginning `{"id": "f1636374-abc6-410d-99ee-822120379e79", ...}`. If the curl fails or returns 404, start the daemon with `.venv/bin/prep serve` and retry. Do NOT skip this — the driver imports daemon-side helpers; a missing daemon won't crash the script but a missing project will.

- [ ] **Step 2: Confirm the production helpers are importable in isolation**

Run:
```bash
.venv/bin/python -c "from prep.api.routers.agents import _get_engine_context, _make_core, _get_llm_fn; print('ok')"
```

Expected output: `ok`

If any import fails, stop and investigate — Task 3 assumes these are usable. (As of spec date 2026-05-13 they were pure Python functions at module level; this verifies they still are.)

- [ ] **Step 3: Confirm the 11 candidate files exist**

Run:
```bash
for f in roadmap_miner treatment_registry swarm_optimizer lod_extractor github_sync budget_enforcement chunking inferred_edges batch_profiles swarm_registry context_config; do
  test -f "/Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/$f.py" && echo "OK $f" || echo "MISSING $f"
done
```

Expected: 11 lines, all starting `OK`. If any line says `MISSING`, the candidate list in this plan is stale — stop and reconcile against the current `INTENTIONALLY_DORMANT.md` before continuing.

---

## Task 2: Driver script — findings-list builder (TDD)

**Files:**
- Create: `tools/phase122_custodian_run.py`
- Create: `tests/test_phase122_custodian_run.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase122_custodian_run.py`:

```python
"""Unit tests for the Phase 122 Custodian driver."""
from tools.phase122_custodian_run import build_findings, CANDIDATES


def test_build_findings_one_per_candidate():
    findings = build_findings()
    assert len(findings) == len(CANDIDATES) == 11


def test_build_findings_use_dead_code_category():
    # The Custodian engine filters on category in
    # {dead_code, orphan, deprecated, unused_export}. Anything else is
    # silently dropped, so we hard-code "dead_code".
    findings = build_findings()
    assert all(f["category"] == "dead_code" for f in findings)


def test_build_findings_have_required_fields():
    findings = build_findings()
    for f in findings:
        assert f["id"].startswith("P122-")
        assert f["affected_files"], f
        assert f["affected_files"][0].startswith("src/prep/core/")
        assert f["affected_files"][0].endswith(".py")
        assert f["description"]


def test_candidates_list_matches_spec():
    # If this fails, the candidate list drifted from the spec/plan.
    expected = {
        "roadmap_miner", "treatment_registry", "swarm_optimizer",
        "lod_extractor", "github_sync", "budget_enforcement",
        "chunking", "inferred_edges", "batch_profiles",
        "swarm_registry", "context_config",
    }
    assert set(CANDIDATES) == expected
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_phase122_custodian_run.py -v
```

Expected: ImportError or "no module named tools.phase122_custodian_run" — the file doesn't exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `tools/phase122_custodian_run.py`:

```python
"""Phase 122 — Custodian dogfood driver.

Feeds 11 pending Phase 122 candidates into the existing
CustodianEngine for LLM safety verification, captures the verdicts
to disk for human triage downstream.

Usage:
    .venv/bin/python tools/phase122_custodian_run.py [--out PATH]

Always dry-run. Never executes archive/branch/delete operations.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CANDIDATES: list[str] = [
    "roadmap_miner",
    "treatment_registry",
    "swarm_optimizer",
    "lod_extractor",
    "github_sync",
    "budget_enforcement",
    "chunking",
    "inferred_edges",
    "batch_profiles",
    "swarm_registry",
    "context_config",
]


def build_findings() -> list[dict[str, Any]]:
    """Construct synthetic dead_code findings for the candidate modules.

    The Custodian's discover() filters on `category in {dead_code,
    orphan, deprecated, unused_export}`. We pick `dead_code` since the
    actual classification (KEEP / DELETE / etc.) is the LLM verifier's
    job downstream.
    """
    findings: list[dict[str, Any]] = []
    for name in CANDIDATES:
        findings.append({
            "id": f"P122-{name}",
            "category": "dead_code",
            "affected_files": [f"src/prep/core/{name}.py"],
            "description": (
                f"Phase 119 recon: {name}.py has no external imports "
                "detected by naive grep. Phase 122 dogfood is asking "
                "the Custodian's safety verifier to confirm whether "
                "this is truly orphaned or is consumed via "
                "re-export / dynamic import / API surface."
            ),
        })
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/Phase122_FeatureUtilizationAudit/custodian_run.json",
        help="Path to write the JSON run log.",
    )
    parser.add_argument(
        "--project-id",
        default="f1636374-abc6-410d-99ee-822120379e79",
        help="SourcePrep project id for this repo.",
    )
    args = parser.parse_args(argv)

    findings = build_findings()
    # Engine wiring lands in Task 3 — until then, just dump findings.
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps({"findings": findings, "plan": None}, indent=2)
    )
    print(f"[phase122] wrote {len(findings)} findings to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/pytest tests/test_phase122_custodian_run.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/phase122_custodian_run.py tests/test_phase122_custodian_run.py
git commit -m "feat(phase122): Custodian driver skeleton + findings builder"
```

---

## Task 3: Driver script — engine wiring

**Files:**
- Modify: `tools/phase122_custodian_run.py:main()` (add engine call after findings build)

- [ ] **Step 1: Replace `main()` to invoke the engine**

Edit `tools/phase122_custodian_run.py`. Replace the body of `main()` (everything inside `def main(...)`, the `parser` setup stays) with:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/Phase122_FeatureUtilizationAudit/custodian_run.json",
        help="Path to write the JSON run log.",
    )
    parser.add_argument(
        "--project-id",
        default="f1636374-abc6-410d-99ee-822120379e79",
        help="SourcePrep project id for this repo.",
    )
    args = parser.parse_args(argv)

    # Import production helpers — they are pure Python in agents.py and
    # safe to call outside FastAPI request context.
    from prep.api.routers.agents import (
        _get_engine_context, _make_core, _get_llm_fn,
    )
    from prep.agents.custodian.engine import CustodianEngine

    idx_dir, project_root, pid = _get_engine_context(args.project_id)
    core = _make_core(pid, idx_dir, project_root)
    engine = CustodianEngine(core=core)
    llm_fn = _get_llm_fn(pid)

    findings = build_findings()
    print(f"[phase122] running Custodian on {len(findings)} candidates "
          f"(dry_run=True)...")
    plan = engine.run(findings, llm_fn, dry_run=True, max_files=20)

    # Serialize plan + verified candidates. We capture per-candidate
    # classification + reason from engine.verify_candidates output by
    # re-running it here (engine.run discards intermediate state).
    verified = engine.verify_candidates(
        engine.discover(findings, max_candidates=50), llm_fn,
    )
    payload = {
        "findings": findings,
        "plan": {
            "branch_name": plan.branch_name,
            "dry_run": plan.dry_run,
            "candidates_in_plan": [
                {
                    "file_path": c.file_path,
                    "finding_id": c.finding_id,
                    "classification": c.classification,
                    "dependent_count": c.dependent_count,
                    "reason": c.reason,
                }
                for c in plan.candidates
            ],
        },
        "verified_candidates": [
            {
                "file_path": c.file_path,
                "finding_id": c.finding_id,
                "classification": c.classification,
                "dependent_count": c.dependent_count,
                "reason": c.reason,
            }
            for c in verified
        ],
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(f"[phase122] wrote run log to {args.out}")
    print(f"[phase122] classifications: " + ", ".join(
        f"{c['file_path'].split('/')[-1]}={c['classification']}"
        for c in payload["verified_candidates"]
    ))
    return 0
```

- [ ] **Step 2: Re-run the unit tests to confirm `build_findings` still works**

```bash
.venv/bin/pytest tests/test_phase122_custodian_run.py -v
```

Expected: 4 passed. (The engine call isn't unit-tested — it requires the daemon LLM. Smoke-tested in Task 4.)

- [ ] **Step 3: Commit**

```bash
git add tools/phase122_custodian_run.py
git commit -m "feat(phase122): wire driver to CustodianEngine + capture verified candidates"
```

---

## Task 4: Smoke-run the driver

**Files:**
- Create (via script): `docs/Phase122_FeatureUtilizationAudit/custodian_run.json`

- [ ] **Step 1: Run the driver**

```bash
.venv/bin/python tools/phase122_custodian_run.py
```

Expected: stdout shows `[phase122] running Custodian on 11 candidates (dry_run=True)...` then a `classifications:` line listing all 11 modules with one of `safe_to_delete` / `needs_review` / `keep`. This will take 11 LLM calls, so wait — should complete within a few minutes.

If you see `Failed to parse safety verification response`, the LLM returned malformed JSON for one candidate. Re-run; if it persists, drop that candidate from the `CANDIDATES` list with a `# FIXME: LLM JSON parse failure 2026-05-13` comment, re-run, and triage that one entirely by hand in Task 5.x.

- [ ] **Step 2: Verify the run log was written and is structurally sound**

```bash
.venv/bin/python -c "
import json, sys
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
assert len(d['verified_candidates']) >= 9, f'too few verified: {len(d[\"verified_candidates\"])}'
assert all(c['classification'] for c in d['verified_candidates']), 'empty classification'
print('verified_candidates:', len(d['verified_candidates']))
for c in d['verified_candidates']:
    print(' ', c['file_path'], '->', c['classification'])
"
```

Expected: prints `verified_candidates: 11` (or ≥9 if some failed) and lists each file → classification. If <9 verified, stop and investigate.

- [ ] **Step 3: Commit the run log**

```bash
git add docs/Phase122_FeatureUtilizationAudit/custodian_run.json
git commit -m "feat(phase122): capture Custodian dogfood run log for 11 candidates"
```

---

## Task 5: Triage `roadmap_miner.py`

**Files:**
- Modify: `docs/INTENTIONALLY_DORMANT.md` (one entry edit)
- Modify: `docs/MASTER_TODO.md` (one tracker line, if applicable)

- [ ] **Step 1: Read the Custodian verdict for this module**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'roadmap_miner' in c['file_path']:
        print('classification:', c['classification'])
        print('reason:', c['reason'])
        break
"
```

Note the classification + reason — you'll quote it verbatim in the registry entry.

- [ ] **Step 2: Run the human confirmation pass**

```bash
grep -rn "from prep.core.roadmap_miner\|import prep.core.roadmap_miner\|\"prep.core.roadmap_miner\"\|roadmap_miner" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/roadmap_miner.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/roadmap_miner.py
echo "---"
grep -ril "roadmap.miner\|roadmap_miner\|roadmap miner" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/roadmap_miner.py
```

Capture: real callers found (count + paths), date of last meaningful commit, any marketing references, line count.

- [ ] **Step 3: Apply the rubric and pick a bucket**

| Custodian | Confirmation | Bucket |
|---|---|---|
| `keep` | real callers (graph wrong) | **WIRED** — remove module from `INTENTIONALLY_DORMANT.md` |
| `keep` | no callers, planned path | **KEEP-DORMANT** |
| `needs_review` | no callers, no plan | **NEEDS-OWNER** |
| `safe_to_delete` | orphaned > 6 months | **DELETE** |
| `safe_to_delete` | recent, no plan | **DEPRECATE** |
| any | marketing claims this feature | **NEEDS-OWNER** (escalate) |

Write down: chosen bucket, one-line "why" for the registry entry.

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`**

Find the bullet `` - `roadmap_miner.py` — pending `` and replace it with a full block placed alphabetically among the existing detailed sections (above "## Other modules under audit"):

```markdown
## roadmap_miner.py
- **Path:** `src/prep/core/roadmap_miner.py` (<LoC from Step 2> LoC)
- **Public API:** <module-level def/class names>
- **Production callers:** <N> (verified 2026-05-13 via Phase 122 Custodian run)
- **Custodian classification:** <safe_to_delete | needs_review | keep>
- **Custodian reason:** "<LLM reason, verbatim, ≤300 chars>"
- **Triage decision:** <WIRED | KEEP-DORMANT | NEEDS-OWNER | DEPRECATE | DELETE>
- **Why:** <one or two sentences explaining the bucket decision, citing what your grep pass found>
- **State (2026-05-13):** <observable facts: caller count, last touched, etc.>
- **Trigger to wire / removal target:** <when would this be revisited or removed>
- **Owner:** unassigned.
```

If the bucket is **WIRED**, do not add a block. Instead delete the bullet `` - `roadmap_miner.py` — pending `` and note the removal in the RESULTS doc (Task 16).

- [ ] **Step 5: If bucket is DEPRECATE / DELETE / NEEDS-OWNER, append a line to `docs/MASTER_TODO.md`**

In `docs/MASTER_TODO.md`, locate the 2026-05-13 Phase 122 dogfooding section (added by the spec commit) and append below its `**Recommended follow-up:**` block — under a new `**Phase 122 triage follow-ups:**` subheading if it doesn't already exist — a line of the form:

```
- [ ] **P122-T-roadmap_miner [DEPRECATE]:** `src/prep/core/roadmap_miner.py` (<NNN> LoC) — <one-line rationale>. Owner: unassigned.
```

If the bucket is **WIRED** or **KEEP-DORMANT**, skip this step.

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage roadmap_miner.py -> <BUCKET>"
```

---

## Task 6: Triage `treatment_registry.py`

**Files:**
- Modify: `docs/INTENTIONALLY_DORMANT.md`
- Modify: `docs/MASTER_TODO.md` (if applicable)

- [ ] **Step 1: Read the Custodian verdict**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'treatment_registry' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.treatment_registry\|import prep.core.treatment_registry\|\"prep.core.treatment_registry\"\|treatment_registry" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/treatment_registry.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/treatment_registry.py
echo "---"
grep -ril "treatment.registry\|treatment_registry" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/treatment_registry.py
```

Note: the existing `INTENTIONALLY_DORMANT.md` comment flags this as "likely re-exported via `__init__`" — pay special attention to `src/prep/core/__init__.py` and `src/prep/core/audit/__init__.py` re-exports.

- [ ] **Step 3: Apply the rubric** (same rubric as Task 5 Step 3).

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the bullet `` - `treatment_registry.py` — likely re-exported via `__init__` (Phase 122 §0 false-positive note); verify `` with a full block matching the template in Task 5 Step 4 (or remove the bullet if bucket is WIRED).

- [ ] **Step 5: Add MASTER_TODO line if bucket is DEPRECATE / DELETE / NEEDS-OWNER** (template in Task 5 Step 5).

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage treatment_registry.py -> <BUCKET>"
```

---

## Task 7: Triage `swarm_optimizer.py`

**Files:**
- Modify: `docs/INTENTIONALLY_DORMANT.md`
- Modify: `docs/MASTER_TODO.md` (if applicable)

- [ ] **Step 1: Read the Custodian verdict**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'swarm_optimizer' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.swarm_optimizer\|import prep.core.swarm_optimizer\|\"prep.core.swarm_optimizer\"\|swarm_optimizer" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/swarm_optimizer.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/swarm_optimizer.py
echo "---"
grep -ril "swarm.optimizer\|swarm_optimizer" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/swarm_optimizer.py
```

Note: the registry flag says "distinct from `swarm_orchestrator`" — make sure your grep is matching `swarm_optimizer` specifically and not catching the orchestrator.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `swarm_optimizer.py` bullet with a full block (template in Task 5 Step 4) or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage swarm_optimizer.py -> <BUCKET>"
```

---

## Task 8: Triage `lod_extractor.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `lod_extractor`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'lod_extractor' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.lod_extractor\|import prep.core.lod_extractor\|\"prep.core.lod_extractor\"\|lod_extractor" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/lod_extractor.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/lod_extractor.py
echo "---"
grep -ril "lod.extractor\|lod_extractor\|level of detail" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/lod_extractor.py
```

Note: registry says "Phase 95 LOD work; was it finished?" — check Phase 95 docs at `docs/Phase95*/README.md` for explicit "deferred" or "shipped" status.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `lod_extractor.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage lod_extractor.py -> <BUCKET>"
```

---

## Task 9: Triage `github_sync.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `github_sync`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'github_sync' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.github_sync\|import prep.core.github_sync\|\"prep.core.github_sync\"\|github_sync" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/github_sync.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/github_sync.py
echo "---"
grep -ril "github.sync\|github_sync\|github integration" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/github_sync.py
```

Note: roadmap atlas mentions "GitHub bi-directional sync" — high chance of marketing claim → NEEDS-OWNER even if no callers.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `github_sync.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage github_sync.py -> <BUCKET>"
```

---

## Task 10: Triage `budget_enforcement.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `budget_enforcement`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'budget_enforcement' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.budget_enforcement\|import prep.core.budget_enforcement\|\"prep.core.budget_enforcement\"\|budget_enforcement" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/budget_enforcement.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/budget_enforcement.py
echo "---"
grep -ril "budget.enforcement\|budget_enforcement\|cost budget" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/budget_enforcement.py
```

Note: registry says "budgets exist in UI; how are they enforced" — also grep `packages/ui/src/` (added above).

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `budget_enforcement.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage budget_enforcement.py -> <BUCKET>"
```

---

## Task 11: Triage `chunking.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `chunking`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if c['file_path'].endswith('/chunking.py'):
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.chunking\|import prep.core.chunking\|\"prep.core.chunking\"" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/chunking.py
echo "---"
grep -ril "semantic chunking\|chunking strategy" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/chunking.py
```

Note: registry says "Phase 110 semantic chunking shipped; verify wiring" — there is also a Rust `prep-chunking` crate. If the Python module's job moved to Rust, this is a DELETE candidate; otherwise it's likely WIRED through `prep-chunking` Python bindings.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `chunking.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage chunking.py -> <BUCKET>"
```

---

## Task 12: Triage `inferred_edges.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `inferred_edges`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'inferred_edges' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.inferred_edges\|import prep.core.inferred_edges\|\"prep.core.inferred_edges\"\|inferred_edges" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/inferred_edges.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/inferred_edges.py
echo "---"
grep -ril "inferred edges\|inferred_edges\|edge inference" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/inferred_edges.py
```

Note: registry says "pipeline stage exists; ensure edge inference runs" — check `src/prep/services/pipeline/stages.py` for an inferred-edges stage definition. Existence of a stage definition is not the same as it being scheduled — also grep `src/prep/services/pipeline/orchestrator.py` for the stage id.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `inferred_edges.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage inferred_edges.py -> <BUCKET>"
```

---

## Task 13: Triage `batch_profiles.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `batch_profiles`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'batch_profiles' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.batch_profiles\|from prep.core import.*batch_profiles\|import prep.core.batch_profiles\|\"prep.core.batch_profiles\"\|batch_profiles\|BatchProfile" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/batch_profiles.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/batch_profiles.py
echo "---"
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/batch_profiles.py
```

Note: registry flag was "likely wired via `prep.core` re-export" — pay attention to `src/prep/core/__init__.py` lines.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `batch_profiles.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage batch_profiles.py -> <BUCKET>"
```

---

## Task 14: Triage `swarm_registry.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `swarm_registry`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'swarm_registry' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.swarm_registry\|import prep.core.swarm_registry\|\"prep.core.swarm_registry\"\|swarm_registry" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/swarm_registry.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/swarm_registry.py
echo "---"
grep -ril "swarm.registry\|swarm_registry" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/swarm_registry.py
```

Note: there's existing memory ([swarm_enabled toggle design](swarm_enabled)) — the swarm subsystem has both `swarm_orchestrator` (active) and other swarm files. Verify which role `swarm_registry` plays before deciding.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `swarm_registry.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage swarm_registry.py -> <BUCKET>"
```

---

## Task 15: Triage `context_config.py`

**Files:** as Task 5.

- [ ] **Step 1: Read the Custodian verdict** for `context_config`.

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
for c in d['verified_candidates']:
    if 'context_config' in c['file_path']:
        print('classification:', c['classification']); print('reason:', c['reason']); break
"
```

- [ ] **Step 2: Human confirmation pass**

```bash
grep -rn "from prep.core.context_config\|import prep.core.context_config\|\"prep.core.context_config\"\|context_config\|ContextConfig" \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/src \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tests \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/scripts \
  /Volumes/4TB-BAD/HumanAI/CoDRAG/tools \
  2>/dev/null | grep -v ".pyc" | grep -v "/context_config.py:"
echo "---"
git -C /Volumes/4TB-BAD/HumanAI/CoDRAG log --oneline -3 -- src/prep/core/context_config.py
echo "---"
grep -ril "context config\|context_config" /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing/ /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs/ 2>/dev/null | head
wc -l /Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/core/context_config.py
```

Note: registry calls this "pending" with no extra hint. Also pay attention to whether `tool_context` in `mcp/server.py` consumes context config — there is a per-client context budget system that may live here.

- [ ] **Step 3: Apply the rubric.**

- [ ] **Step 4: Edit `docs/INTENTIONALLY_DORMANT.md`** — replace the `context_config.py` bullet with a full block or remove if WIRED.

- [ ] **Step 5: Add MASTER_TODO line if applicable.**

- [ ] **Step 6: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md
git commit -m "docs(phase122): triage context_config.py -> <BUCKET>"
```

---

## Task 16: Verify registry coverage + clean up already-WIRED entries

**Files:**
- Modify: `docs/INTENTIONALLY_DORMANT.md`

- [ ] **Step 1: Verify every Phase 122 candidate has a triage decision**

```bash
grep -c "^## " /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md
echo "---"
grep "— pending" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md
echo "---"
grep "— likely" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md
```

Expected:
- `^## ` count is `(original section count) - 3 already-WIRED entries to remove + (11 - WIRED-bucket count) new full entries`. Eyeball that the total looks right — a 2x increase from 1 to ~10–12 sections is the expected shape.
- `— pending` returns no matches.
- `— likely` returns no matches.

If `pending` or `likely` matches anything, that candidate was missed — return to its task and finish it.

- [ ] **Step 2: Remove the three already-WIRED candidates from the "Other modules under audit" list**

In `docs/INTENTIONALLY_DORMANT.md`, delete these three bullets (they were already classified as WIRED before Phase 122 dogfood, no entry needed):
```
- `antibody_derivation.py` — H3 confirmed via Phase 124 harness: derivation IS running ... Remove from Phase 122 audit list.
- `rules_generator.py` — wired (writes AGENTS.md every pipeline run)
- `concept_seeder.py` — wired (Phase 124 T4 integration verified)
```

- [ ] **Step 3: Commit**

```bash
git add docs/INTENTIONALLY_DORMANT.md
git commit -m "docs(phase122): drop already-WIRED candidates from pending list"
```

---

## Task 17: Write `RESULTS.md`

**Files:**
- Create: `docs/Phase122_FeatureUtilizationAudit/RESULTS.md`

- [ ] **Step 1: Tally the buckets**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('docs/Phase122_FeatureUtilizationAudit/custodian_run.json').read())
print('Custodian classifications:')
for c in d['verified_candidates']:
    print(f\"  {c['file_path']:55} {c['classification']}\")"
echo "---"
echo "Final-decision buckets (read from INTENTIONALLY_DORMANT.md headings + MASTER_TODO P122-T-* lines):"
grep -A1 "^## " /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md | grep -i "triage decision\|^## "
```

Capture the two distributions: Custodian classification count, and final human-decided bucket count.

- [ ] **Step 2: Write `docs/Phase122_FeatureUtilizationAudit/RESULTS.md`**

```markdown
# Phase 122 — Feature Utilization Audit — RESULTS

**Date:** 2026-05-13
**Spec:** `docs/superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md`
**Plan:** `docs/superpowers/plans/2026-05-13-phase122-custodian-dogfood.md`

## What we did

Dogfooded the existing Custodian engine (`src/prep/agents/custodian/engine.py`)
against the 11 modules under "Other modules under audit" in
`docs/INTENTIONALLY_DORMANT.md`. Built a thin driver
(`tools/phase122_custodian_run.py`) that synthesized `dead_code`
findings for each candidate and called `CustodianEngine.run(..., dry_run=True)`
through the daemon's LLM factory. Captured the verdicts to
`custodian_run.json` and did a human confirmation pass on each before
recording final decisions.

## Bucket distribution (final, human-decided)

| Bucket | Count | Modules |
|---|---|---|
| WIRED (graph was wrong, no dormant entry needed) | <N> | <list> |
| KEEP-DORMANT | <N> | <list> |
| NEEDS-OWNER | <N> | <list> |
| DEPRECATE | <N> | <list> |
| DELETE | <N> | <list> |
| INVESTIGATION_FAILED (LLM JSON parse error, hand-triaged) | <N> | <list> |

## Disagreement between Custodian and human

<For each module where the human confirmation pass changed the bucket
the Custodian's classification implied, write one bullet:>

- `<module.py>`: Custodian said `<safe_to_delete | needs_review | keep>`,
  final bucket is `<BUCKET>`. Why: <one line — usually "grep found callers
  the graph missed" or "marketing claims this feature">.

## prep_impact dogfooding bug confirmed

The driver consumed `dependent_count=0` from `core.get_impact_radius` for
every candidate — including modules that the human grep pass proved
have real callers. This confirms the `prep_impact` bimodal-node bug
filed as P122-D1/D2/D3 in `MASTER_TODO.md` and as `prep_observe`
observation `bd79badde4d2`. The Custodian's LLM verifier compensated
in <N> of <N> cases by reading file contents, missed <N> cases that
the human grep pass caught.

## Follow-up work tracked in MASTER_TODO

- P122-D1 / D2 / D3: fix `prep_impact` to aggregate edges across file ↔
  external_module twins (separate from this phase).
- P122-T-*: one follow-up per DEPRECATE / DELETE / NEEDS-OWNER module
  (see the 2026-05-13 Phase 122 section in `MASTER_TODO.md`).

## Phase 122 status

This pass closes the original Phase 122 §0 "Recommended first session"
tasks for the 11 candidates. T4 (spaghetti wire-up) was already shipped
by Phase 124 T5. Original T8 (FastAPI route audit, 279 routes) and T9
(Storybook story audit, 79 stories) remain out of scope and deferred.
```

Fill in every `<...>` placeholder before committing.

- [ ] **Step 3: Verify `RESULTS.md` has no placeholders left**

```bash
grep -nE "<[^>]+>|TBD|TODO" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/Phase122_FeatureUtilizationAudit/RESULTS.md
```

Expected: no output. If anything matches, fix it.

- [ ] **Step 4: Commit**

```bash
git add docs/Phase122_FeatureUtilizationAudit/RESULTS.md
git commit -m "docs(phase122): RESULTS summary — Custodian dogfood + bucket distribution"
```

---

## Task 18: Phase close-out

**Files:** none (verification + final commit).

- [ ] **Step 1: Confirm test suite still passes**

```bash
.venv/bin/pytest tests/test_phase122_custodian_run.py -v
```

Expected: 4 passed.

- [ ] **Step 2: Confirm no `pending` / `likely` markers remain in `INTENTIONALLY_DORMANT.md`**

```bash
grep -nE "— pending|— likely" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md
```

Expected: no output.

- [ ] **Step 3: Confirm `RESULTS.md` matches the bucket counts in `INTENTIONALLY_DORMANT.md`**

```bash
echo "Final-decision lines in INTENTIONALLY_DORMANT.md:"
grep "Triage decision" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/INTENTIONALLY_DORMANT.md | sort | uniq -c
echo "---"
echo "Buckets named in RESULTS.md:"
grep -E "^\| (WIRED|KEEP-DORMANT|NEEDS-OWNER|DEPRECATE|DELETE|INVESTIGATION_FAILED)" /Volumes/4TB-BAD/HumanAI/CoDRAG/docs/Phase122_FeatureUtilizationAudit/RESULTS.md
```

Eyeball that the counts agree. If they disagree, one of the two files is stale — fix it.

- [ ] **Step 4: Final phase close-out commit**

There should be no uncommitted state at this point. Verify:

```bash
git status --short
```

Expected: empty (or only files unrelated to Phase 122). If anything Phase-122-related is dirty, commit it:

```bash
git add docs/INTENTIONALLY_DORMANT.md docs/MASTER_TODO.md docs/Phase122_FeatureUtilizationAudit/
git commit -m "docs(phase122): final state — registry, master-todo, results aligned"
```

Phase 122 (decisions-only triage) is complete. Open items remain in `MASTER_TODO.md`:
- P122-D1/D2/D3 — fix the `prep_impact` bimodal-node bug.
- P122-T-* — one follow-up per non-KEEP-DORMANT triage decision.
- Original T8 (FastAPI route audit) and T9 (Storybook story audit) — deferred.
