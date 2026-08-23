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


# ══════════════════════════════════════════════════════════════════
# Issue B-main — concepts not injected into /projects/{id}/context
# ══════════════════════════════════════════════════════════════════


class TestConceptsInContextRetrieval:
    """The primary AI search path (context_project) queries CodeIndex +
    KnowledgeIndex + observations + atlas but never queries concept_store.
    An agent asking about the codebase never receives the active concept
    layer in its search context."""

    def test_inject_concepts_helper_exists(self):
        """A _inject_concepts helper must exist in the search module,
        mirroring _inject_observations."""
        from prep.api.routers.projects import search as search_mod
        assert hasattr(search_mod, "_inject_concepts"), (
            "_inject_concepts helper not found in search.py — concepts are "
            "never injected into /projects/{id}/context retrieval."
        )

    def test_inject_concepts_prepends_active_concepts(self, store: ConceptStore):
        from prep.api.routers.projects.search import _inject_concepts

        store.save("proj-1", "License gate precedes cloud calls",
                   "All cloud LLM calls must pass through the license check.",
                   category="constraint", kind="concept", status="active",
                   anchors=["src/llm/gate.py"])
        store.save("proj-1", "Unfinished thought", "Maybe we do X",
                   kind="concept", status="seed")

        # _inject_concepts imports concept_store inside the function body,
        # so patch at the source module.
        with patch(
            "prep.services.concept_store.concept_store", store,
        ):
            new_ctx, meta = _inject_concepts(
                "BASE CONTEXT", "proj-1", "license cloud calls",
            )

        assert "[concepts]" in new_ctx.lower() or "[active concepts]" in new_ctx.lower()
        assert "License gate" in new_ctx
        assert meta is not None
        assert meta.get("concepts_injected", 0) >= 1

    def test_inject_concepts_no_active_concepts_returns_unchanged(
        self, store: ConceptStore,
    ):
        from prep.api.routers.projects.search import _inject_concepts

        with patch(
            "prep.services.concept_store.concept_store", store,
        ):
            new_ctx, meta = _inject_concepts(
                "BASE CONTEXT", "proj-1", "anything",
            )
        assert new_ctx == "BASE CONTEXT"
        assert meta is None

    def test_context_endpoint_calls_inject_concepts(self):
        """Source-level guard: context_project must call _inject_concepts
        so concepts reach the agent's search context."""
        import inspect
        from prep.api.routers.projects.search import context_project
        src = inspect.getsource(context_project)
        assert "_inject_concepts" in src, (
            "context_project does not call _inject_concepts — active concepts "
            "are never injected into the RAG retrieval path."
        )


# ══════════════════════════════════════════════════════════════════
# Issue 4.4 — pipeline overwrites human & AI curation in save_many
# ══════════════════════════════════════════════════════════════════


class TestUserEditedGuard:
    """save_many matches existing rows by (project_id, title, kind) and
    overwrites content/category/status without checking whether the row
    was manually created, edited, or approved. Re-runs demote active
    curated concepts back to seed/triage_pending."""

    def test_update_sets_user_edited_flag(self, store: ConceptStore):
        cid = store.save("proj-1", "Curated", "Original", kind="concept",
                         status="active")
        store.update(cid, content="Human-edited content")
        retrieved = store.get(cid)
        assert retrieved is not None
        assert getattr(retrieved, "user_edited", False) is True, (
            "update() must mark the row user_edited=True so save_many "
            "knows not to clobber it on pipeline re-runs."
        )

    def test_save_many_preserves_user_edited_row(self, store: ConceptStore):
        """A pipeline re-run must NOT overwrite a human-edited concept."""
        cid = store.save("proj-1", "Curated decision", "Original content",
                         kind="concept", status="active", category="decision")
        store.update(cid, content="Human-curated content", status="active")

        # Pipeline re-run emits the same title with different content/status
        store.save_many("proj-1", [{
            "title": "Curated decision",
            "content": "Pipeline regenerated content",
            "category": "technical",
            "status": "seed",
            "kind": "concept",
        }])

        retrieved = store.get(cid)
        assert retrieved is not None
        assert "Human-curated" in retrieved.content, (
            "save_many overwrote a user-edited concept — pipeline re-runs "
            "must not clobber human curation."
        )
        assert retrieved.status == "active"

    def test_save_many_overwrites_non_edited_row(self, store: ConceptStore):
        """A pipeline re-run SHOULD update a row that was never user-edited."""
        cid = store.save("proj-1", "Auto concept", "Original", kind="concept",
                         status="seed")
        store.save_many("proj-1", [{
            "title": "Auto concept",
            "content": "Regenerated content",
            "status": "active",
            "kind": "concept",
        }])
        retrieved = store.get(cid)
        assert retrieved is not None
        assert "Regenerated" in retrieved.content
        assert retrieved.status == "active"


# ══════════════════════════════════════════════════════════════════
# Issue C1 — silent synthesis fallback has no provenance flag
# ══════════════════════════════════════════════════════════════════


class TestSynthesisFallbackProvenance:
    """When synthesis times out or fails, the seeder merges raw per-module
    worker rationales, saves them without a provenance/fallback flag, and
    returns status='success'. Downstream passes ingest unvetted rationales
    with zero visibility."""

    def test_fallback_rationales_carry_provenance_tag(self, store: ConceptStore):
        """Rationales saved via the fallback path must be distinguishable
        from synthesized rationales so downstream passes and the dashboard
        can flag them."""
        # Simulate what the seeder fallback does: save with a provenance tag
        store.save_many("proj-1", [{
            "title": "Fallback rationale",
            "content": "Merged from raw worker output",
            "kind": "module_rationale",
            "tags": ["provenance:fallback_merge"],
        }])
        items = store.list_concepts("proj-1", kind="module_rationale")
        assert len(items) == 1
        assert "provenance:fallback_merge" in items[0].tags

    def test_concept_has_provenance_field(self):
        """The Concept dataclass should expose a provenance field so the
        flag is first-class, not just a tag convention."""
        from prep.services.concept_store import Concept
        c = Concept(
            id="x", project_id="p", title="t", content="c",
            category="technical", status="seed",
        )
        # provenance defaults to None/empty — the field must exist
        assert hasattr(c, "provenance")


# ══════════════════════════════════════════════════════════════════
# Issue 4.3 — triage_pending is a one-way dead end in Pass 4
# ══════════════════════════════════════════════════════════════════


class TestTriagePendingPass4:
    """Validate assigns T1 concepts to triage_pending. Pass 4 gate only
    checks status='seed', so triage_pending concepts are never re-gated
    and accumulate indefinitely."""

    def test_pass4_gate_includes_triage_pending_by_default(
        self, tmp_path: Path,
    ):
        from prep.core.concept_promotion_pipeline import run_pass4_gate

        # run_pass4_gate opens its own sqlite connection at
        # prep_data_dir()/prep_concepts.db — create the DB at that path.
        db_path = tmp_path / "prep_concepts.db"
        local_store = ConceptStore()
        local_store.init(db_path)
        try:
            local_store.save(
                "proj-1", "Triage candidate", "High quality but was T1",
                kind="concept", status="triage_pending",
                confidence=0.92, anchors=["src/x.py"],
            )

            with patch(
                "prep.core.project_registry.prep_data_dir",
                return_value=tmp_path,
            ):
                report = run_pass4_gate(
                    "proj-1", high=0.90, low=0.65, dry_run=True,
                )
        finally:
            local_store.close()

        # The triage_pending concept must be included in the gate input
        assert report.input_count >= 1, (
            "Pass 4 gate ignored triage_pending concepts — they are a "
            "one-way dead end with no path to active/archived."
        )
        assert report.activated >= 1, (
            "High-confidence triage_pending concept was not activated."
        )


# ══════════════════════════════════════════════════════════════════
# Issue C2/C3 — MCP prep_concepts lacks questions/answer/approve/archive
#               + mcp_direct.py has no prep_concepts dispatch at all
# ══════════════════════════════════════════════════════════════════


class TestMCPConceptsActions:
    """The REST API has endpoints for questions/answer/approve/archive,
    but the MCP tool only exposes 'get' and 'save'. mcp_direct.py doesn't
    dispatch prep_concepts at all."""

    def test_mcp_tools_schema_includes_new_actions(self):
        """The prep_concepts tool schema must list the new actions."""
        from prep.mcp_tools import TOOLS
        concepts_tool = next(
            (t for t in TOOLS if t["name"] == "prep_concepts"), None,
        )
        assert concepts_tool is not None
        actions = concepts_tool["inputSchema"]["properties"]["action"]
        enum = actions.get("enum", [])
        for required_action in ("get", "save", "questions", "answer",
                                "approve", "archive"):
            assert required_action in enum, (
                f"prep_concepts action enum missing '{required_action}'"
            )

    def test_mcp_tools_schema_includes_tradeoff_category(self):
        """The category enum in the schema must include 'tradeoff'."""
        from prep.mcp_tools import TOOLS
        concepts_tool = next(
            (t for t in TOOLS if t["name"] == "prep_concepts"), None,
        )
        cats = concepts_tool["inputSchema"]["properties"]["category"]["enum"]
        assert "tradeoff" in cats

    def test_mcp_direct_dispatches_prep_concepts(self):
        """mcp_direct.py must dispatch 'prep_concepts' tool calls."""
        from prep.mcp_direct import DirectMCPServer
        src = __import__("inspect").getsource(DirectMCPServer.handle_tools_call)
        assert "prep_concepts" in src, (
            "mcp_direct.py handle_tools_call does not dispatch 'prep_concepts' "
            "— direct-mode MCP clients can't access concepts at all."
        )


# ══════════════════════════════════════════════════════════════════
# Issue A — workers never receive source code slices for anchor files
# ══════════════════════════════════════════════════════════════════


class TestSourceGroundingSlices:
    """Generate and Validate workers demand grep-falsifiable assertions
    about source files, but the grounding payload never includes the
    actual source code. The LLM hallucinates assertions about files it
    has never seen."""

    def test_grounding_dataclass_has_source_slices_field(self):
        """The Grounding dataclass must carry source code slices for
        anchor files so workers can verify their assertions against
        real code."""
        from prep.core.concept_synthesizer import Grounding
        g = Grounding(project_name="test")
        assert hasattr(g, "source_slices"), (
            "Grounding has no source_slices field — workers can't see "
            "the source code they're asked to make assertions about."
        )

    def test_load_grounding_populates_source_slices(self, tmp_path: Path):
        """load_grounding must populate source_slices with actual file
        content for anchor files."""
        from prep.core.concept_synthesizer import Grounding, load_grounding

        # Create a fake project structure with a source file
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "auth.py").write_text(
            "def login(user, password):\n"
            "    return check_credentials(user, password)\n"
        )

        # Create a fake rationale row in concept_store so load_grounding
        # picks up the anchor, then verify the source slice is populated.
        from prep.services.concept_store import ConceptStore
        db_path = tmp_path / "prep_concepts.db"
        local_store = ConceptStore()
        local_store.init(db_path)
        try:
            local_store.save(
                "proj-1", "Auth rationale", "JWT auth pattern",
                anchors=["src/auth.py"], kind="module_rationale",
            )
        finally:
            local_store.close()

        with patch(
            "prep.services.concept_store.concept_store",
            local_store,
        ), patch(
            "prep.core.project_registry.prep_data_dir",
            return_value=tmp_path,
        ):
            local_store2 = ConceptStore()
            local_store2.init(db_path)
            try:
                with patch(
                    "prep.services.concept_store.concept_store",
                    local_store2,
                ):
                    g = load_grounding(
                        "proj-1", idx_dir=tmp_path,
                        project_name="test",
                        project_root=tmp_path,
                    )
            finally:
                local_store2.close()

        assert isinstance(g, Grounding)
        assert hasattr(g, "source_slices")
        slices = g.source_slices or {}
        # The key may be relative or absolute — check both
        auth_slice = slices.get("src/auth.py") or slices.get(
            str(tmp_path / "src" / "auth.py"),
        )
        assert auth_slice is not None, (
            "load_grounding did not populate a source slice for "
            "src/auth.py even though it's an anchor file."
        )
        assert "def login" in auth_slice, (
            "Source slice doesn't contain the actual file content."
        )
