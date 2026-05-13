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
from typing import Any, Dict, List


CANDIDATES: List[str] = [
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


def build_findings() -> List[Dict[str, Any]]:
    """Construct synthetic dead_code findings for the candidate modules.

    The Custodian's discover() filters on `category in {dead_code,
    orphan, deprecated, unused_export}`. We pick `dead_code` since the
    actual classification (KEEP / DELETE / etc.) is the LLM verifier's
    job downstream.
    """
    findings: List[Dict[str, Any]] = []
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


def main(argv: List[str] | None = None) -> int:
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
