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

    # Import production helpers — they are pure Python in agents.py and
    # safe to call outside FastAPI request context.
    from prep.agents.custodian.engine import CustodianEngine  # type: ignore[import-untyped]
    from prep.api.routers.agents import (  # type: ignore[import-untyped]
        _get_engine_context,
        _get_llm_fn,
        _make_core,
    )

    idx_dir, project_root, pid = _get_engine_context(args.project_id)
    core = _make_core(pid, idx_dir, project_root)
    engine = CustodianEngine(core=core)
    llm_fn = _get_llm_fn(pid)

    findings = build_findings()
    print(f"[phase122] running Custodian on {len(findings)} candidates "
          f"(dry_run=True)...")
    # Inline the three stages engine.run() would call. Calling engine.run()
    # directly and then re-running verify_candidates() to harvest the
    # KEEP/NEEDS_REVIEW verdicts would double the LLM cost — engine.run()
    # discards everything except the safe_to_delete subset. Inlining
    # preserves the full verified list at zero behavioural cost.
    candidates = engine.discover(findings, max_candidates=50)
    if len(candidates) < len(findings):
        dropped = {f["affected_files"][0] for f in findings} - {
            c.file_path for c in candidates
        }
        print(f"[phase122] WARNING: discover() dropped {len(dropped)} "
              f"candidate(s) (likely claimed by another agent or filtered "
              f"by category): {sorted(dropped)}")
    verified = engine.verify_candidates(candidates, llm_fn)
    plan = engine.plan_cleanup(verified, dry_run=True, max_files=20)
    payload: dict[str, Any] = {
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
    print("[phase122] classifications: " + ", ".join(
        f"{c['file_path'].split('/')[-1]}={c['classification']}"
        for c in payload["verified_candidates"]
    ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
