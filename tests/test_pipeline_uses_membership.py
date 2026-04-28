"""
Phase 120 Task 7 — Build pipeline sites read compute_index_membership.

Five sites previously read pcfg.get("included_paths") directly.
After Task 7 they all read compute_index_membership(project_id) so that
named scopes' paths flow into the embedder and into generated AGENTS.md files.

Test strategy
-------------
- Sites 1 & 2 (post_flight.generate_preliminary_atlas_and_rules,
               post_flight.regenerate_rules_with_full_atlas) — patch
  write_rules_file and verify the included_paths arg contains scope paths.
- Site 3 (post_flight.trigger_code_index_build) — patch
  build_manager.start_project_build and verify included_paths contains scope paths.
- Site 4 (workers._rules_worker) — patch write_rules_file in the worker and
  verify included_paths contains scope paths.
- Site 5 (routers/scope._build_fn) — patch build_manager.start_project_build
  and verify included_paths contains scope paths.

All tests share the same shape:
  global included_paths = ["src/"]
  named scope adds       = ["websites/marketing/"]
  expected union         = {"src/", "websites/marketing/"}
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from prep.core.scope_store import scope_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_project_with_scope(project, project_id: str) -> None:
    """Set included_paths on the project and create a named scope."""
    object.__setattr__(
        project,
        "config",
        {**(project.config or {}), "included_paths": ["src/"]},
    )
    scope_store.create(project_id, display_name="Marketing", paths=["websites/marketing/"])


# ---------------------------------------------------------------------------
# Site 3: PostFlightActions.trigger_code_index_build
# ---------------------------------------------------------------------------

def test_trigger_code_index_build_reads_membership(
    tmp_settings, dummy_project_in_registry, monkeypatch
):
    """trigger_code_index_build must pass the membership union to start_project_build."""
    pid = dummy_project_in_registry.id
    _setup_project_with_scope(dummy_project_in_registry, pid)

    captured: list[list[str]] = []

    def fake_start(project, roots, include_globs, exclude_globs,
                   max_file_bytes, hard_limit_bytes, *,
                   use_gitignore=False, included_paths=None):
        captured.append(list(included_paths or []))
        return True

    from prep.services import build_manager as bm_mod
    monkeypatch.setattr(bm_mod.build_manager, "start_project_build", fake_start)

    # Also stub activity check so it doesn't bail early.
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    from prep.services.pipeline.post_flight import PostFlightActions
    PostFlightActions.trigger_code_index_build(pid)

    assert captured, "start_project_build was never called"
    assert set(captured[-1]) == {"src/", "websites/marketing/"}


# ---------------------------------------------------------------------------
# Site 5: routers/scope._build_fn (via _ensure_build_fn_registered)
# ---------------------------------------------------------------------------

def test_scope_build_fn_reads_membership(
    tmp_settings, dummy_project_in_registry, monkeypatch
):
    """The _build_fn registered by scope router must pass membership union to start_project_build."""
    pid = dummy_project_in_registry.id
    _setup_project_with_scope(dummy_project_in_registry, pid)

    captured: list[list[str]] = []

    def fake_start(project, roots, include_globs, exclude_globs,
                   max_file_bytes, hard_limit_bytes, *,
                   use_gitignore=False, included_paths=None):
        captured.append(list(included_paths or []))
        return True

    from prep.services import build_manager as bm_mod
    # Stub is_project_building so the wait-loop exits immediately.
    monkeypatch.setattr(bm_mod.build_manager, "is_project_building", lambda pid: False)
    monkeypatch.setattr(bm_mod.build_manager, "start_project_build", fake_start)

    # Stub last_build_error so the post-build check passes.
    bm_mod.build_manager.last_build_error = {}

    # Also stub scope_orchestrator.register_build_fn to capture the _build_fn
    # without needing the full orchestrator.
    registered_fn = {}
    from prep.services import scope_orchestrator as so_mod

    def fake_register(project_id, fn):
        registered_fn[project_id] = fn

    monkeypatch.setattr(so_mod.scope_orchestrator, "register_build_fn", fake_register)

    # Reset the _registered_projects cache so _ensure_build_fn_registered runs.
    import prep.api.routers.scope as scope_router_mod
    scope_router_mod._registered_projects.discard(pid)

    scope_router_mod._ensure_build_fn_registered(pid)

    assert pid in registered_fn, "_build_fn was never registered"
    fn = registered_fn[pid]

    # Invoke _build_fn — it calls start_project_build internally.
    fn(added=[], removed=[], changed=[])

    assert captured, "start_project_build was never called from _build_fn"
    assert set(captured[-1]) == {"src/", "websites/marketing/"}


# ---------------------------------------------------------------------------
# Site 1: PostFlightActions.generate_preliminary_atlas_and_rules
# ---------------------------------------------------------------------------

def test_generate_preliminary_atlas_passes_membership_to_rules_file(
    tmp_settings, dummy_project_in_registry, monkeypatch, tmp_path
):
    """generate_preliminary_atlas_and_rules must pass membership union to write_rules_file."""
    pid = dummy_project_in_registry.id
    _setup_project_with_scope(dummy_project_in_registry, pid)

    # Point the project path to tmp_path so project_index_dir doesn't fail.
    object.__setattr__(dummy_project_in_registry, "path", str(tmp_path))

    # Stub project_index_dir to return a valid directory.
    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()

    # Write a minimal trace_nodes.jsonl so the early-return check passes.
    (idx_dir / "trace_nodes.jsonl").write_text('{"id":"n1"}\n')

    captured_kwargs: list[dict] = []

    def fake_write_rules_file(**kwargs):
        captured_kwargs.append(kwargs)

    # Patch project_index_dir so it returns our tmp idx_dir.
    monkeypatch.setattr(
        "prep.core.project_registry.project_index_dir",
        lambda proj: idx_dir,
    )

    # Patch write_rules_file in the module where post_flight imports it.
    monkeypatch.setattr(
        "prep.core.rules_generator.write_rules_file",
        fake_write_rules_file,
    )

    # Patch CodebaseAtlas.generate_structural and load so we don't need real data.
    fake_doc = MagicMock()
    fake_doc.mode = "structural"
    fake_doc.content = "atlas content"
    fake_doc.char_count = 12
    fake_doc.file_count = 1

    with patch("prep.core.atlas.CodebaseAtlas") as MockAtlas:
        mock_atlas_inst = MockAtlas.return_value
        mock_atlas_inst.load.return_value = None  # no existing LLM atlas
        mock_atlas_inst.generate_structural.return_value = fake_doc
        mock_atlas_inst.cache_role_atlases.return_value = {}

        from prep.services.pipeline.post_flight import PostFlightActions
        PostFlightActions.generate_preliminary_atlas_and_rules(pid)

    assert captured_kwargs, "write_rules_file was never called"
    paths_arg = captured_kwargs[-1].get("included_paths") or []
    assert set(paths_arg) == {"src/", "websites/marketing/"}


# ---------------------------------------------------------------------------
# Site 2: PostFlightActions.regenerate_rules_with_full_atlas
# ---------------------------------------------------------------------------

def test_regenerate_rules_with_full_atlas_passes_membership(
    tmp_settings, dummy_project_in_registry, monkeypatch, tmp_path
):
    """regenerate_rules_with_full_atlas must pass membership union to write_rules_file."""
    pid = dummy_project_in_registry.id
    _setup_project_with_scope(dummy_project_in_registry, pid)

    object.__setattr__(dummy_project_in_registry, "path", str(tmp_path))
    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()

    fake_doc = MagicMock()
    fake_doc.mode = "llm"
    fake_doc.content = "full atlas"
    fake_doc.char_count = 10
    fake_doc.file_count = 1

    captured_kwargs: list[dict] = []

    def fake_write_rules_file(**kwargs):
        captured_kwargs.append(kwargs)

    monkeypatch.setattr(
        "prep.core.project_registry.project_index_dir",
        lambda proj: idx_dir,
    )
    monkeypatch.setattr(
        "prep.core.rules_generator.write_rules_file",
        fake_write_rules_file,
    )

    with patch("prep.core.atlas.CodebaseAtlas") as MockAtlas:
        mock_atlas_inst = MockAtlas.return_value
        mock_atlas_inst.load.return_value = fake_doc

        from prep.services.pipeline.post_flight import PostFlightActions
        PostFlightActions.regenerate_rules_with_full_atlas(pid)

    assert captured_kwargs, "write_rules_file was never called"
    paths_arg = captured_kwargs[-1].get("included_paths") or []
    assert set(paths_arg) == {"src/", "websites/marketing/"}


# ---------------------------------------------------------------------------
# Site 4: WorkerFactory._rules_worker (workers.py:896)
# ---------------------------------------------------------------------------

def test_rules_worker_passes_membership_to_rules_file(
    tmp_settings, dummy_project_in_registry, monkeypatch, tmp_path
):
    """_rules_worker must pass membership union to write_rules_file."""
    pid = dummy_project_in_registry.id
    _setup_project_with_scope(dummy_project_in_registry, pid)

    object.__setattr__(dummy_project_in_registry, "path", str(tmp_path))
    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()

    fake_doc = MagicMock()
    fake_doc.mode = "llm"
    fake_doc.content = "full atlas"
    fake_doc.char_count = 20
    fake_doc.file_count = 3

    captured_kwargs: list[dict] = []

    def fake_write_rules_file(**kwargs):
        captured_kwargs.append(kwargs)

    monkeypatch.setattr(
        "prep.core.project_registry.project_index_dir",
        lambda proj: idx_dir,
    )
    monkeypatch.setattr(
        "prep.core.rules_generator.write_rules_file",
        fake_write_rules_file,
    )

    # Stub ManifestStore to avoid needing real SQLite graph stats.
    fake_store = MagicMock()
    fake_store.read_graph_stats.return_value = {}

    with patch("prep.core.atlas.CodebaseAtlas") as MockAtlas, \
         patch("prep.services.pipeline.manifest_store.ManifestStore", return_value=fake_store):
        mock_atlas_inst = MockAtlas.return_value
        mock_atlas_inst.load.return_value = fake_doc

        from prep.services.pipeline.workers import WorkerFactory

        worker_fn = WorkerFactory._rules_worker(pid)

        fake_slot = MagicMock()
        worker_fn(fake_slot, lambda label, cur, total, baseline=0: None)

    assert captured_kwargs, "write_rules_file was never called by _rules_worker"
    paths_arg = captured_kwargs[-1].get("included_paths") or []
    assert set(paths_arg) == {"src/", "websites/marketing/"}
