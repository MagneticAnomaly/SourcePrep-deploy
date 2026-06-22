"""Shared vocabulary between ``tools/playwright_smoke.py`` and the Phase 145
invariant library (``tools/phase145_uat/invariants.py``).

These constants encode the 15-stage pipeline order, the per-stage group
membership, and the canonical mapping from raw DOM state attributes to a
small comparison vocabulary. They live in their own module so both the
harness and the invariant library can import them without one taking a
dependency on the other (which would otherwise be a circular import once
``playwright_smoke`` imports ``run_all`` from ``invariants``).

Any change to this module is a public-contract change for the harness and
the UAT scorecard format. Keep the lists/dicts in lockstep with the
dashboard's stage_id vocabulary and the canon table documented in
``.claude/skills/playwright-smoke/references/desync-rules.md``.
"""
from __future__ import annotations

# Fast Sync → Deep Enrichment → Finalize, in the 15-stage order published
# by /pipeline/status. Kept as a list of (stage_id, group) pairs because
# the UI groups stages identically.
STAGE_ORDER: list[tuple[str, str]] = [
    ("structural", "fast_sync"),
    ("inferred_edges", "fast_sync"),
    ("catalogue", "fast_sync"),
    ("validation", "fast_sync"),
    ("knowledge", "fast_sync"),
    ("enrichment", "deep_enrichment"),
    ("group_reasoning", "deep_enrichment"),
    ("clustering", "deep_enrichment"),
    ("deepening", "deep_enrichment"),
    ("deep_knowledge", "deep_enrichment"),
    ("atlas", "finalize"),
    ("rules", "finalize"),
    ("concepts", "finalize"),
    ("audit", "finalize"),
    ("antibodies", "finalize"),
]

STAGE_TO_GROUP: dict[str, str] = dict(STAGE_ORDER)

# Canonical state vocabulary for desync comparison. Both API and DOM states
# are normalized into this set before diffing.
CANON_STATES: set[str] = {"pending", "running", "complete", "failed"}

DOM_STATE_TO_CANON: dict[str, str] = {
    "running": "running",
    "rerunning": "running",
    "rebuilding": "running",  # promoteForRebuild outputs this during Danger Zone rebuilds
    "queued": "pending",
    "waiting": "pending",
    "idle": "pending",
    "not_built": "pending",
    "disabled": "pending",
    "paused": "pending",
    "complete": "complete",
    "stale": "complete",
    "warning": "complete",
    "error": "failed",
}
