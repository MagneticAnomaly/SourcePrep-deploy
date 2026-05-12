"""Phase 134 — guard against os.walk re-introduction in pipeline-
relevant code paths."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_os_walk_in_pipeline_code():
    """grep across the pipeline-relevant code paths for os.walk.
    Expected: zero hits. Phase 134 converges all walkers onto
    prep_engine.walk_repo."""
    result = subprocess.run(
        ["grep", "-rn", "os.walk",
         "src/prep/core/augmenter.py",
         "src/prep/core/deepening.py",
         "src/prep/core/epistemic_enrichment.py",
         "src/prep/core/epistemic_score.py",
         "src/prep/core/audit/analyzers/",
         "src/prep/core/trace/",
         "src/prep/core/repo_profile.py",
         "src/prep/core/atlas/markdown_links.py",
         "src/prep/services/pipeline/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # grep returns 1 when no matches found — that's the success case.
    if result.returncode == 0:
        # Found something — Phase 134 contract violated.
        hits = result.stdout.strip().split("\n")
        # Filter out comment-only mentions (the Phase 134 spec/comments
        # may legitimately reference os.walk by name).
        code_hits = [h for h in hits if "os.walk(" in h]
        assert not code_hits, (
            f"Phase 134 contract violation: os.walk re-appeared in "
            f"pipeline code. Use prep_engine.walk_repo instead.\n"
            f"Hits:\n  " + "\n  ".join(code_hits)
        )
