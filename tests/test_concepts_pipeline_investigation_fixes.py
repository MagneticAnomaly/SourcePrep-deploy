"""Tests for fixes identified in docs/CONCEPTS_PIPELINE_INVESTIGATION_2026-08-22.md.

Each test is tagged with the issue ID from the investigation report so the
work stays traceable. Tests are written FIRST (failing), then the fix is
applied, then the test passes — per the project workflow.

Issues covered (in implementation order):
  4.1   — tradeoff category silent coercion
  B-sub — rationale leakage in search() / get_for_anchors_directory()
  C4    — sticky stale Generate manifest on empty/failed runs
  B-main— concepts not injected into /projects/{id}/context retrieval
  4.4   — pipeline overwrites human/AI curation in save_many
  C1    — silent synthesis fallback has no provenance flag
  4.3   — triage_pending is a one-way dead end in Pass 4
  C2/C3 — MCP prep_concepts lacks questions/answer/approve/archive + mcp_direct dispatch
  A     — workers never receive source code slices for anchor files
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.concept_store import ConceptStore, VALID_CATEGORIES


# ── Shared fixture ────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> ConceptStore:
    s = ConceptStore()
    s.init(tmp_path / "test_investigation.db")
    yield s
    s.close()


# ══════════════════════════════════════════════════════════════════
# Issue 4.1 — tradeoff category silent coercion
# ══════════════════════════════════════════════════════════════════


class TestTradeoffCategory:
    """The synthesizer prompt lists `tradeoff` as a valid category, but
    concept_store.VALID_CATEGORIES omits it, so save_many silently remaps
    every `tradeoff` concept to `technical`."""

    def test_tradeoff_is_a_valid_category(self):
        """VALID_CATEGORIES must include 'tradeoff' so the synthesizer's
        prompt-emit category round-trips through save without coercion."""
        assert "tradeoff" in VALID_CATEGORIES, (
            "VALID_CATEGORIES is missing 'tradeoff'; the synthesizer prompt "
            "(concept_synthesizer.py:436) instructs the LLM to emit it but "
            "save_many silently remaps it to 'technical'."
        )

    def test_save_preserves_tradeoff_category(self, store: ConceptStore):
        cid = store.save(
            project_id="proj-1",
            title="Tauri over Electron for binary size",
            content="8 MB vs 80 MB — size wins over ecosystem maturity.",
            category="tradeoff",
            kind="concept",
        )
        retrieved = store.get(cid)
        assert retrieved is not None
        assert retrieved.category == "tradeoff", (
            f"Expected 'tradeoff', got '{retrieved.category}' — save() "
            "coerced the category."
        )

    def test_save_many_preserves_tradeoff_category(self, store: ConceptStore):
        saved, _ = store.save_many("proj-1", [
            {
                "title": "Embedder singleton vs per-request",
                "content": "Process-wide singleton to avoid ONNX memory leaks.",
                "category": "tradeoff",
                "kind": "concept",
            },
        ])
        assert saved == 1
        items = store.list_concepts("proj-1", kind="concept")
        assert items[0].category == "tradeoff"


# ══════════════════════════════════════════════════════════════════
# Issue B-sub — rationale leakage in search() / get_for_anchors_directory()
# ══════════════════════════════════════════════════════════════════


class TestRationaleLeakage:
    """search() and get_for_anchors_directory() do not filter by kind, so
    thousands of module_rationale rows pollute concept retrieval alongside
    the curated concept layer."""

    def test_search_filters_to_concepts_by_default(self, store: ConceptStore):
        # Both rows contain "auth" so the query matches both — the kind
        # filter is what must separate them.
        store.save("proj-1", "Auth uses JWT", "JWT auth rationale",
                   anchors=["src/auth.py"], kind="module_rationale")
        store.save("proj-1", "Auth boundary decision",
                   "Cross-cutting auth design", anchors=["src/auth.py"],
                   kind="concept", status="active")

        results = store.search("proj-1", "auth")
        titles = {c.title for c in results}
        assert "Auth boundary decision" in titles
        assert "Auth uses JWT" not in titles, (
            "search() leaked a module_rationale row into concept results."
        )

    def test_search_can_opt_into_rationale(self, store: ConceptStore):
        store.save("proj-1", "Auth uses JWT", "JWT rationale",
                   anchors=["src/auth.py"], kind="module_rationale")
        results = store.search("proj-1", "auth", kind=None)
        assert any(c.title == "Auth uses JWT" for c in results)

    def test_get_for_anchors_directory_filters_to_concepts_by_default(
        self, store: ConceptStore,
    ):
        store.save("proj-1", "Per-module auth note", "JWT rationale",
                   anchors=["src/auth/login.py"], kind="module_rationale")
        store.save("proj-1", "Auth boundary decision",
                   "Cross-cutting auth design", anchors=["src/auth/login.py"],
                   kind="concept", status="active")

        results = store.get_for_anchors_directory("proj-1", "src/auth")
        titles = {c.title for c in results}
        assert "Auth boundary decision" in titles
        assert "Per-module auth note" not in titles, (
            "get_for_anchors_directory() leaked a module_rationale row."
        )


# ══════════════════════════════════════════════════════════════════
# Issue C4 — sticky stale Generate manifest on empty/failed runs
# ══════════════════════════════════════════════════════════════════


class TestGenerateManifestGate:
    """concept_generate_manifest.json is written unconditionally, even when
    0 candidates were generated or all workers failed. The freshness check
    then skips every subsequent run, permanently locking in the empty
    state."""

    def test_manifest_not_written_when_zero_candidates(self, tmp_path: Path):
        from prep.core.concept_generate_swarm import synthesize_concepts_swarm
        from prep.core.concept_synthesizer import Grounding
        from prep.core.docs_grounding import DocsGrounding

        llm = MagicMock()
        llm.generate = MagicMock(return_value=("[]", 10))

        with patch(
            "prep.core.concept_generate_swarm.load_grounding",
            return_value=Grounding(project_name="test"),
        ), patch(
            "prep.core.concept_generate_swarm.load_or_build_docs_grounding",
            return_value=DocsGrounding(version=1, generated_at=0, docs=[]),
        ), patch(
            "prep.core.concept_generate_swarm._rationale_fingerprint",
            return_value=(0, 0.0),
        ), patch("prep.services.concept_store.concept_store") as cs:
            cs.save_many.return_value = (0, 0)
            synthesize_concepts_swarm(
                "p1", llm=llm, swarm_size=1,
                idx_dir=tmp_path, project_root=tmp_path,
                project_name="test",
            )

        manifest_path = tmp_path / "concept_generate_manifest.json"
        assert not manifest_path.exists(), (
            "Manifest was written despite 0 candidates — subsequent runs "
            "will skip Generate forever (sticky stale state)."
        )

    def test_manifest_written_when_candidates_emitted(self, tmp_path: Path):
        from prep.core.concept_generate_swarm import synthesize_concepts_swarm
        from prep.core.concept_synthesizer import Grounding
        from prep.core.docs_grounding import DocsGrounding

        concept_json = json.dumps([{
            "title": "Real concept", "category": "architecture",
            "tier": "T2", "tier_pairwise": "closer_to_lower",
            "anchors": ["src/x.py"], "counter_evidence": "",
            "falsification": "grep x", "refined_content": "content",
        }])
        llm = MagicMock()
        llm.generate = MagicMock(return_value=(concept_json, 100))

        with patch(
            "prep.core.concept_generate_swarm.load_grounding",
            return_value=Grounding(project_name="test"),
        ), patch(
            "prep.core.concept_generate_swarm.load_or_build_docs_grounding",
            return_value=DocsGrounding(version=1, generated_at=0, docs=[]),
        ), patch(
            "prep.core.concept_generate_swarm._rationale_fingerprint",
            return_value=(0, 0.0),
        ), patch("prep.services.concept_store.concept_store") as cs:
            cs.save_many.return_value = (1, 0)
            synthesize_concepts_swarm(
                "p1", llm=llm, swarm_size=1,
                idx_dir=tmp_path, project_root=tmp_path,
                project_name="test",
            )

        manifest_path = tmp_path / "concept_generate_manifest.json"
        assert manifest_path.exists(), (
            "Manifest should be written when candidates are emitted so the "
            "next run can short-circuit on unchanged rationale."
        )
