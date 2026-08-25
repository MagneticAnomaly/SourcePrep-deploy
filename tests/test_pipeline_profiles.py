"""Tests: pipeline profile matrices + ProfileGate resolution (T-S1.2).

Covers the acceptance criteria from
IMPLEMENTATION-PLAN-SOURCEPREP-TEMPLATE-2026-08-24.md → T-S1.2:

* A ``prose_docs`` scope covering ``knowledge/linux/`` rejects ENRICHMENT for
  in-scope files and allows CATALOGUE for the same path.
* Unscoped paths are always allowed, every stage.
* Most-specific-prefix overlap resolution; tie → lowest scope id.
* The opt-in ``auto_profile_files`` markdown rule is dormant by default.
* No scopes ⇒ byte-identical "everything allowed" behavior.

Prompt-selection and end-to-end worker-gating tests live in
``test_augmenter_profiles.py`` (T-S2.6) and the pipeline-worker suite.
"""
from __future__ import annotations

import pytest

from prep.core.pipeline_profiles import (
    NEVER_GATED_STAGES,
    PER_FILE_STAGES,
    PIPELINE_PROFILES,
    ProfileGate,
    profile_allows_stage,
    profile_for_path,
)
from prep.core.scope_store import scope_store
from prep.services.pipeline.stages import StageId


# ── matrix truth table ────────────────────────────────────────────────


def test_code_profile_is_empty_allows_everything():
    assert PIPELINE_PROFILES["code"] == {}
    for stage in StageId:
        assert profile_allows_stage("code", stage) is True


@pytest.mark.parametrize(
    "profile,stage,expected",
    [
        ("prose_docs", StageId.INFERRED_EDGES, False),
        ("prose_docs", StageId.CATALOGUE, True),
        ("prose_docs", StageId.ENRICHMENT, False),
        ("prose_docs", StageId.GROUP_REASONING, False),
        ("prose_docs", StageId.CLUSTERING, True),
        ("prose_docs", StageId.DEEPENING, False),
        ("prose_docs", StageId.ATLAS, True),
        ("prose_docs", StageId.RULES, False),
        ("prose_docs", StageId.CONCEPTS, False),
        ("prose_docs", StageId.AUDIT, False),
        ("prose_docs", StageId.ANTIBODIES, False),
        ("system_config", StageId.INFERRED_EDGES, False),
        ("system_config", StageId.CATALOGUE, True),
        ("system_config", StageId.ENRICHMENT, True),
        ("system_config", StageId.GROUP_REASONING, True),
        ("system_config", StageId.CLUSTERING, True),
        ("system_config", StageId.DEEPENING, False),
        ("system_config", StageId.ATLAS, True),
    ],
)
def test_profile_matrix(profile, stage, expected):
    assert profile_allows_stage(profile, stage) is expected


def test_rust_embed_stages_never_gated():
    assert NEVER_GATED_STAGES == {"structural", "validation", "knowledge"}
    for profile in ("code", "prose_docs", "system_config"):
        for stage in (StageId.STRUCTURAL, StageId.VALIDATION, StageId.KNOWLEDGE):
            assert profile_allows_stage(profile, stage) is True


def test_deep_knowledge_per_file_stage_but_matrix_allows():
    # deep_knowledge carries a gate consult point (T-S1.3) yet built-in
    # matrices never disable it → runs for both profiles.
    assert "deep_knowledge" in PER_FILE_STAGES
    assert "deep_knowledge" not in NEVER_GATED_STAGES
    assert profile_allows_stage("prose_docs", StageId.DEEP_KNOWLEDGE) is True
    assert profile_allows_stage("system_config", StageId.DEEP_KNOWLEDGE) is True


# ── gate resolution with real scopes ─────────────────────────────────


def test_no_scopes_allows_everything(dummy_project_in_registry):
    pid = dummy_project_in_registry.id
    for stage in StageId:
        gate = ProfileGate(pid, stage)
        for fp in ("src/a.py", "knowledge/linux/man.1", "host/etc/ssh/sshd_config"):
            assert gate.allows(fp) is True, (stage, fp)


def test_prose_docs_scope_rejects_enrichment_allows_catalogue(
    tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    in_scope = "knowledge/linux/man.1"
    out_scope = "src/app.py"

    enr = ProfileGate(pid, StageId.ENRICHMENT)
    assert enr.allows(in_scope) is False
    assert enr.allows(out_scope) is True

    cat = ProfileGate(pid, StageId.CATALOGUE)
    assert cat.allows(in_scope) is True
    assert cat.allows(out_scope) is True


def test_system_config_scope_enables_group_reasoning_for_host(
    tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    gate = ProfileGate(pid, StageId.GROUP_REASONING)
    assert gate.allows("host/etc/ssh/sshd_config") is True
    # unscoped file -> code default -> group_reasoning absent from code matrix -> allowed
    assert gate.allows("src/app.py") is True


def test_profile_for_path_resolves_scope_membership(
    tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    gate = ProfileGate(pid, StageId.CATALOGUE)
    assert gate.profile_for_path("knowledge/linux/man.1") == "prose_docs"
    assert gate.profile_for_path("host/etc/ssh/sshd_config") == "system_config"
    # unscoped -> code default
    assert gate.profile_for_path("src/app.py") == "code"
    # module-level helper agrees
    assert profile_for_path(pid, "knowledge/linux/man.1", gate=gate) == "prose_docs"


def test_overlap_most_specific_prefix_wins(tmp_settings, dummy_project_in_registry):
    pid = dummy_project_in_registry.id
    # broad prose_docs scope, narrow code scope nested under it
    scope_store.create(pid, display_name="docs", paths=["knowledge/"], pipeline_profile="prose_docs")
    scope_store.create(
        pid, display_name="linux", paths=["knowledge/linux/"], pipeline_profile="code"
    )
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    # prose_docs disables enrichment; code enables it. Narrow code scope wins.
    assert gate.profile_for_path("knowledge/linux/man.1") == "code"
    assert gate.allows("knowledge/linux/man.1") is True
    # sibling under the broad scope only -> prose_docs -> enrichment disabled
    assert gate.profile_for_path("knowledge/bsd/man.1") == "prose_docs"
    assert gate.allows("knowledge/bsd/man.1") is False


def test_overlap_tie_breaks_to_lowest_scope_id(tmp_settings, dummy_project_in_registry):
    pid = dummy_project_in_registry.id
    # Two scopes of equal specificity (same path) but different profiles.
    # _allocate_unique_id would dedupe identical slugs; use distinct names
    # whose slugs differ but whose paths overlap at the same depth.
    scope_store.create(pid, display_name="alpha", paths=["shared/"], pipeline_profile="prose_docs")
    scope_store.create(pid, display_name="beta", paths=["shared/"], pipeline_profile="code")
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    # both cover shared/x at specificity len("shared/")=7; tie → lowest id
    # "alpha" < "beta" → prose_docs → enrichment disabled
    assert gate.profile_for_path("shared/x") == "prose_docs"
    assert gate.allows("shared/x") is False


def test_auto_profile_files_dormant_by_default(tmp_settings, dummy_project_in_registry):
    pid = dummy_project_in_registry.id
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    # No scopes; auto rule off → markdown resolves to code → enrichment allowed
    assert gate.profile_for_path("docs/guide.md") == "code"
    assert gate.allows("docs/guide.md") is True


def test_auto_profile_files_opt_in_marks_markdown_prose(
    tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    # opt in via project config
    dummy_project_in_registry.config["auto_profile_files"] = True
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    assert gate.profile_for_path("docs/guide.md") == "prose_docs"
    assert gate.allows("docs/guide.md") is False  # prose_docs disables enrichment
    # explicit scope still wins over auto rule
    scope_store.create(pid, display_name="docs", paths=["docs/"], pipeline_profile="code")
    gate2 = ProfileGate(pid, StageId.ENRICHMENT)
    assert gate2.profile_for_path("docs/guide.md") == "code"


# ── per-file gate consult points (T-S1.3) ────────────────────────────


def _make_enricher(tmp_path, monkeypatch):
    """Construct an EpistemicEnricher with a fake LLM + a pinned changeset
    so _needs_enrichment's profile-gate branch can be exercised directly."""
    from prep.core.epistemic_enrichment import EpistemicEnricher

    class _FakeLLM:
        model = "fake"

    class _FakeChangeset:
        def __init__(self, modified):
            self.modified = set(modified)
            self.deleted = set()

    enricher = EpistemicEnricher(_FakeLLM(), tmp_path, tmp_path / "idx", project_id="p")
    enricher.index_dir = tmp_path / "idx"
    enricher.index_dir.mkdir(exist_ok=True)
    # A file in changeset.modified → would_process is True absent the gate.
    enricher.changeset = _FakeChangeset(modified={"knowledge/linux/man.1", "src/app.py"})
    return enricher


def test_enrichment_needs_check_respects_prose_docs_gate(
    tmp_path, tmp_settings, dummy_project_in_registry, monkeypatch
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    enricher = _make_enricher(tmp_path, monkeypatch)
    enricher.profile_gate = ProfileGate(pid, StageId.ENRICHMENT)

    # Both files are in changeset.modified (would_process True) and already
    # have an existing entry (so we reach the gate/changeset branch).
    existing = {
        "file:knowledge/linux/man.1": object(),
        "file:src/app.py": object(),
    }
    augmentations = dict(existing)  # node_id present → past the augmentations guard

    doc_node = {"id": "file:knowledge/linux/man.1", "file_path": "knowledge/linux/man.1"}
    code_node = {"id": "file:src/app.py", "file_path": "src/app.py"}

    # prose_docs disables enrichment → the doc file never needs enrichment,
    # even though it's in changeset.modified.
    assert enricher._needs_enrichment(doc_node, existing, augmentations) is False
    # code file → enrichment enabled → modified → needs re-enrichment.
    assert enricher._needs_enrichment(code_node, existing, augmentations) is True


def test_enrichment_needs_check_no_gate_is_unchanged(tmp_path, monkeypatch):
    """Without a profile_gate, _needs_enrichment matches pre-profile behavior
    (modified files need re-enrichment regardless of path)."""
    enricher = _make_enricher(tmp_path, monkeypatch)
    assert enricher.profile_gate is None  # class default
    existing = {"file:knowledge/linux/man.1": object()}
    augmentations = dict(existing)
    doc_node = {"id": "file:knowledge/linux/man.1", "file_path": "knowledge/linux/man.1"}
    assert enricher._needs_enrichment(doc_node, existing, augmentations) is True


def test_worker_base_profile_gate_default_is_none():
    """Directly-constructed workers carry profile_gate=None (no AttributeError),
    matching the changeset contract — so non-worker callers are unaffected."""
    from prep.services.pipeline.workers.base import Worker

    class _W(Worker):
        pass

    w = _W()
    assert w.profile_gate is None
    assert w.changeset is None


def test_deepening_override_keys_subtract_gate_rejected(
    tmp_path, tmp_settings, dummy_project_in_registry, monkeypatch
):
    """_compute_deepening_override_keys' denominator must be profile-aware:
    gate-rejected files don't count toward _expected_total (T-S1.0 touchpoint 1)."""
    from prep.services.pipeline.workers import _compute_deepening_override_keys

    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )

    # Build a fake enricher exposing the three attrs the helper reads:
    # load_trace_nodes, _get_file_excerpt, load_existing, profile_gate.
    file_nodes = [
        {"id": "file:knowledge/linux/man.1", "kind": "file", "file_path": "knowledge/linux/man.1"},
        {"id": "file:src/app.py", "kind": "file", "file_path": "src/app.py"},
    ]

    class _Entry:
        pass

    class _FakeEnricher:
        profile_gate = None

        def __init__(self):
            self._idx = tmp_path / "idx"
            self._idx.mkdir(exist_ok=True)

        def load_trace_nodes(self):
            return file_nodes

        def _get_file_excerpt(self, fp, max_lines=1):
            return "nonempty"  # passes the empty-file filter

        def load_existing(self):
            return {}  # no prior deepening entries

    fe = _FakeEnricher()
    fe.profile_gate = ProfileGate(pid, StageId.DEEPENING)

    expected, processed = _compute_deepening_override_keys(
        fe, idx_dir=fe._idx, project_id=pid
    )
    # deepening disabled for prose_docs → only the code file counts (1).
    assert expected == 1
    assert processed == 0


# ── group_reasoning input-set filter (T-S1.6) ────────────────────────


def test_group_reasoning_matrix():
    assert profile_allows_stage("prose_docs", StageId.GROUP_REASONING) is False
    assert profile_allows_stage("system_config", StageId.GROUP_REASONING) is True
    assert profile_allows_stage("code", StageId.GROUP_REASONING) is True


def test_group_reasoning_filter_drops_docs_keeps_host(
    tmp_settings, dummy_project_in_registry
):
    """Docs-scope files never appear in any group, even if markdown edges
    link two docs; host config files group normally (T-S1.6 acceptance)."""
    from prep.core.group_reasoning import build_dependency_groups

    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    gate = ProfileGate(pid, StageId.GROUP_REASONING)

    docs = ["file:knowledge/linux/a.md", "file:knowledge/linux/b.md"]
    host = ["file:host/sshd_config", "file:host/sshd_dropin"]
    all_ids = docs + host
    epistemic = {nid: object() for nid in all_ids}
    # edges: a-b (docs), sshd_config-sshd_dropin (host)
    edges = [
        {"source": docs[0], "target": docs[1], "kind": "links_to"},
        {"source": host[0], "target": host[1], "kind": "import"},
    ]

    # Without the filter: two groups (docs + host).
    full_groups = build_dependency_groups(epistemic, edges)
    assert len(full_groups) == 2

    # Apply the T-S1.6 filter (what GroupReasoningEngine.run does).
    filtered = {
        nid: e for nid, e in epistemic.items()
        if not (nid.startswith("file:") and not gate.allows(nid[len("file:"):]))
    }
    # docs dropped, host kept
    assert set(filtered) == set(host)

    filtered_groups = build_dependency_groups(filtered, edges)
    # Only the host group survives; docs never appear in any group.
    assert len(filtered_groups) == 1
    members = set(filtered_groups[0])
    assert members == set(host)
    assert not (members & set(docs))