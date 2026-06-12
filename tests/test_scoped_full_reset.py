"""Tests for scoped Danger-Zone resets:
    DELETE /projects/{id}/enrichment/full-reset  (stages 6-15)
    DELETE /projects/{id}/finalize/full-reset    (stages 11-15)

Both must wipe their scoped files + dirs, leave fast-sync (stages 1-5)
intact, and write the reset barrier so selfheal cannot resurrect.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "test", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _idx_dir(client: TestClient, pid: str) -> Path:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    return Path(project_index_dir(require_project(pid)))


def _seed_checkpoint(idx_dir: Path) -> None:
    """Populate .checkpoints/_golden/ with snapshot files that a scoped
    reset must clear so selfheal can't resurrect them after the barrier
    clears on the next finalize completion."""
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / "_meta.json").write_text("{}")
    (golden / "atlas.json").write_text("{}")
    (golden / "atlas_manifest.json").write_text("{}")
    (golden / "trace_nodes.jsonl").write_text('{}\n')


def _seed_full_project(idx_dir: Path) -> None:
    """Populate idx_dir with every artifact from every stage group."""
    # Fast sync (stages 1-5): must survive scoped resets
    (idx_dir / "trace_manifest.json").write_text("{}")
    (idx_dir / "trace_nodes.jsonl").write_text('{"id":"n1"}\n')
    (idx_dir / "trace_edges.jsonl").write_text('{"src":"a","dst":"b"}\n')
    (idx_dir / "trace_augmented.jsonl").write_text('{"id":"n1"}\n')
    (idx_dir / "trace_augment_manifest.json").write_text("{}")
    (idx_dir / "trace_inferred_edges.jsonl").write_text('{}\n')
    (idx_dir / "trace_inferred_manifest.json").write_text("{}")

    # Deep enrichment (stages 6-10)
    (idx_dir / "trace_epistemic.jsonl").write_text('{}\n')
    (idx_dir / "trace_epistemic_manifest.json").write_text("{}")
    (idx_dir / "trace_group_reasoning.jsonl").write_text('{}\n')
    (idx_dir / "group_reasoning_manifest.json").write_text("{}")
    (idx_dir / "trace_modules.jsonl").write_text('{}\n')
    (idx_dir / "trace_modules_manifest.json").write_text("{}")
    (idx_dir / "deepening_manifest.json").write_text("{}")
    (idx_dir / "deep_knowledge_manifest.json").write_text("{}")

    # Finalize (stages 11-15)
    (idx_dir / "atlas.json").write_text("{}")
    (idx_dir / "atlas_manifest.json").write_text("{}")
    (idx_dir / "atlas_routing.json").write_text("{}")
    (idx_dir / "rules_manifest.json").write_text("{}")
    (idx_dir / "concepts_manifest.json").write_text("{}")
    (idx_dir / "audit_manifest.json").write_text("{}")
    (idx_dir / "antibodies_manifest.json").write_text("{}")

    (idx_dir / "atlas_roles").mkdir()
    (idx_dir / "atlas_roles" / "role.json").write_text("{}")
    (idx_dir / "audit").mkdir()
    (idx_dir / "audit" / "findings.json").write_text("[]")


def test_finalize_full_reset_wipes_finalize_only(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    _seed_full_project(idx_dir)
    _seed_checkpoint(idx_dir)

    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code == 200

    # .checkpoints/ is blown away so _golden can't hold stale
    # finalize-era data that selfheal could resurrect once the barrier
    # clears on the next finalize completion.
    assert not (idx_dir / ".checkpoints").exists()

    # Fast sync survives
    assert (idx_dir / "trace_nodes.jsonl").is_file()
    assert (idx_dir / "trace_augmented.jsonl").is_file()
    assert (idx_dir / "trace_inferred_edges.jsonl").is_file()

    # Deep enrichment survives
    assert (idx_dir / "trace_epistemic.jsonl").is_file()
    assert (idx_dir / "trace_group_reasoning.jsonl").is_file()
    assert (idx_dir / "trace_modules.jsonl").is_file()
    assert (idx_dir / "deepening_manifest.json").is_file()
    assert (idx_dir / "deep_knowledge_manifest.json").is_file()

    # Finalize wiped
    assert not (idx_dir / "atlas.json").exists()
    assert not (idx_dir / "atlas_manifest.json").exists()
    assert not (idx_dir / "rules_manifest.json").exists()
    assert not (idx_dir / "concepts_manifest.json").exists()
    assert not (idx_dir / "audit_manifest.json").exists()
    assert not (idx_dir / "antibodies_manifest.json").exists()
    assert not (idx_dir / "atlas_roles").exists()
    assert not (idx_dir / "audit").exists()

    # Reset barrier written
    assert (idx_dir / ".reset_barrier").is_file()


def test_enrichment_full_reset_wipes_deep_and_finalize(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    _seed_full_project(idx_dir)
    _seed_checkpoint(idx_dir)

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code == 200
    assert not (idx_dir / ".checkpoints").exists()

    # Fast sync survives
    assert (idx_dir / "trace_nodes.jsonl").is_file()
    assert (idx_dir / "trace_augmented.jsonl").is_file()
    assert (idx_dir / "trace_inferred_edges.jsonl").is_file()
    assert (idx_dir / "trace_manifest.json").is_file()

    # Deep enrichment wiped
    assert not (idx_dir / "trace_epistemic.jsonl").exists()
    assert not (idx_dir / "trace_group_reasoning.jsonl").exists()
    assert not (idx_dir / "trace_modules.jsonl").exists()
    assert not (idx_dir / "deepening_manifest.json").exists()
    assert not (idx_dir / "deep_knowledge_manifest.json").exists()

    # Finalize wiped
    assert not (idx_dir / "atlas.json").exists()
    assert not (idx_dir / "rules_manifest.json").exists()
    assert not (idx_dir / "concepts_manifest.json").exists()
    assert not (idx_dir / "audit_manifest.json").exists()
    assert not (idx_dir / "antibodies_manifest.json").exists()
    assert not (idx_dir / "atlas_roles").exists()
    assert not (idx_dir / "audit").exists()

    # Reset barrier written
    assert (idx_dir / ".reset_barrier").is_file()


def test_scoped_reset_barrier_records_reason(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    _seed_full_project(idx_dir)

    client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert "enrichment_reset" in (idx_dir / ".reset_barrier").read_text()

    # Clear and try the other scope
    (idx_dir / ".reset_barrier").unlink()
    _seed_full_project(idx_dir)
    client.delete(f"/projects/{pid}/finalize/full-reset")
    assert "finalize_reset" in (idx_dir / ".reset_barrier").read_text()


def test_scoped_reset_clears_antibody_and_concept_stores(client, tmp_path, monkeypatch):
    """Both scoped resets must clear antibody_store and concept_store or
    the UI shows stale 'N antibodies' / 'N concepts' after the manifests
    are gone. User-authored concepts are not distinguishable from
    auto-generated ones — Reset means clean slate."""
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    _seed_full_project(idx_dir)

    # Spy on the store methods — we don't need real data, just proof the
    # scoped reset invokes clear_project with the right project_id.
    from prep.services import antibody_store as ab_mod
    from prep.services import concept_store as cc_mod

    ab_calls: list[str] = []
    cc_calls: list[str] = []
    monkeypatch.setattr(
        ab_mod.antibody_store, "clear_project",
        lambda pid_: ab_calls.append(pid_) or 0,
    )
    monkeypatch.setattr(
        cc_mod.concept_store, "clear_project",
        lambda pid_: cc_calls.append(pid_) or 0,
    )

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code == 200
    assert ab_calls == [pid]
    assert cc_calls == [pid]

    # Re-arm and try the finalize scope
    ab_calls.clear()
    cc_calls.clear()
    _seed_full_project(idx_dir)
    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code == 200
    assert ab_calls == [pid]
    assert cc_calls == [pid]


def test_antibody_store_clear_project_deletes_rows(tmp_path):
    """Direct unit test for antibody_store.clear_project — regression
    guard against the hasattr() silent no-op we just fixed. Inserts
    rows via raw SQL to sidestep the Antibody dataclass so this test
    stays stable across antibody schema changes."""
    from prep.services.antibody_store import AntibodyStore

    store = AntibodyStore()
    store.init(tmp_path / "ab.db")

    conn = store._conn
    assert conn is not None
    conn.execute(
        "INSERT INTO antibodies (id, project_id, name, source_concept_id, "
        "trigger_json, response_json, severity, status, created_at, "
        "last_triggered, trigger_count, dismiss_count) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ab-1", "p1", "n", "c1", "{}", "{}", "warn", "active", 0.0, None, 0, 0),
    )
    conn.execute(
        "INSERT INTO antibodies (id, project_id, name, source_concept_id, "
        "trigger_json, response_json, severity, status, created_at, "
        "last_triggered, trigger_count, dismiss_count) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ab-2", "p2", "n", "c2", "{}", "{}", "warn", "active", 0.0, None, 0, 0),
    )
    conn.commit()

    # Sanity: both rows present
    assert conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", ("p1",)
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", ("p2",)
    ).fetchone()[0] == 1

    rows = store.clear_project("p1")
    assert rows == 1
    # p1 wiped, p2 untouched
    assert conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", ("p1",)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", ("p2",)
    ).fetchone()[0] == 1
    store.close()


def test_branch_snapshot_restore_blocked_by_barrier(tmp_path):
    """restore_project must refuse while the reset barrier is active.

    After a scoped reset, branch snapshots contain stale pre-reset data.
    Without the barrier check, switching branches could silently restore
    that stale data over the clean post-reset state.
    """
    from prep.services.branch_backup_manager import (
        SNAPSHOT_PATTERNS,
        restore_project,
        snapshot_project,
    )

    idx = tmp_path / "idx"
    idx.mkdir()

    # Seed enough data that snapshot_project saves something
    for pat in SNAPSHOT_PATTERNS[:3]:
        (idx / pat).write_text("{}")

    # Create a snapshot for branch 'main'
    snapshot_project(idx, "main")
    snap_dir = idx / ".branch_snapshots" / "main"
    assert snap_dir.is_dir()

    # No barrier → restore succeeds
    result = restore_project(idx, "main")
    assert result is not None
    assert result["files_restored"] > 0

    # With barrier → restore blocked
    (idx / ".reset_barrier").write_text("1234\ntest\n")
    result = restore_project(idx, "main")
    assert result is None

    # Clear barrier → restore works again
    (idx / ".reset_barrier").unlink()
    result = restore_project(idx, "main")
    assert result is not None


# ─────────────────────────────────────────────────────────────────────
# Code-Index-only reset (Knowledge Scope embeddings)
# ─────────────────────────────────────────────────────────────────────


def _seed_code_index(idx_dir: Path) -> None:
    """Write the four files (and remote/local-deltas dirs) that
    code_index_destroy is responsible for clearing."""
    (idx_dir / "documents.json").write_text('[{"id":"x"}]')
    (idx_dir / "embeddings.npy").write_bytes(b"\x00" * 16)
    (idx_dir / "manifest.json").write_text('{"count":1}')
    (idx_dir / "fts.sqlite3").write_bytes(b"SQLite format 3\x00")
    # WAL/SHM siblings (only present when fts is in WAL mode)
    (idx_dir / "fts.sqlite3-wal").write_bytes(b"\x00")
    (idx_dir / "fts.sqlite3-shm").write_bytes(b"\x00")
    # Team-sync directories
    remote = idx_dir / "remote"
    remote.mkdir()
    (remote / "documents.json").write_text("[]")
    deltas = idx_dir / "local_deltas"
    deltas.mkdir()
    (deltas / "documents.json").write_text("[]")


def test_code_index_destroy_wipes_only_code_index_artifacts(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    _seed_full_project(idx_dir)  # trace + atlas + concepts + audit
    _seed_checkpoint(idx_dir)
    _seed_code_index(idx_dir)

    # Seed a fake .index_backup_<uuid> in idx_dir.parent to verify our
    # endpoint does NOT sweep the parent (P2 race-prevention).
    parent_backup = idx_dir.parent / ".index_backup_NOTOURS"
    parent_backup.mkdir()
    (parent_backup / "important.txt").write_text("not for us to delete")

    res = client.delete(f"/projects/{pid}/code-index/destroy")
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    deleted = set(body["deleted"])

    # CodeIndex artifacts gone
    for f in ("documents.json", "embeddings.npy", "manifest.json",
              "fts.sqlite3", "fts.sqlite3-wal", "fts.sqlite3-shm"):
        assert not (idx_dir / f).exists(), f"{f} should be deleted"
        assert f in deleted

    # Team-sync subdirs gone
    assert not (idx_dir / "remote").exists()
    assert not (idx_dir / "local_deltas").exists()
    assert "remote/" in deleted and "local_deltas/" in deleted

    # P2: parent-dir .index_backup_* SURVIVES (we don't sweep that anymore)
    assert parent_backup.exists(), (
        "code_index_destroy must not sweep idx_dir.parent — that races with "
        "in-flight atomic swaps"
    )
    assert (parent_backup / "important.txt").read_text() == "not for us to delete"

    # Trace, atlas, concepts, audit, antibodies all PRESERVED
    assert (idx_dir / "trace_nodes.jsonl").is_file()
    assert (idx_dir / "trace_epistemic.jsonl").is_file()
    assert (idx_dir / "atlas.json").is_file()
    assert (idx_dir / "atlas_manifest.json").is_file()
    assert (idx_dir / "concepts_manifest.json").is_file()
    assert (idx_dir / "audit_manifest.json").is_file()
    assert (idx_dir / "antibodies_manifest.json").is_file()
    assert (idx_dir / "atlas_roles").is_dir()
    assert (idx_dir / "audit").is_dir()

    # No reset barrier — code-index reset must not gate trace pipeline
    assert not (idx_dir / ".reset_barrier").exists()

    # Checkpoints preserved (they belong to trace pipeline, not CodeIndex)
    assert (idx_dir / ".checkpoints").is_dir()


def test_code_index_destroy_preserves_project_config(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    res = client.put(
        f"/projects/{pid}",
        json={"config": {
            "include_globs": ["**/*.py"],
            "exclude_globs": ["**/.mypy_cache/**"],
            "included_paths": ["src/foo.py", "docs/api.md"],
            "use_gitignore": True,
        }},
    )
    assert res.status_code == 200

    idx_dir = _idx_dir(client, pid)
    _seed_code_index(idx_dir)

    assert client.delete(f"/projects/{pid}/code-index/destroy").status_code == 200

    # Project config — particularly included_paths (FolderTree selection) —
    # must survive the reset.
    cfg = client.get(f"/projects/{pid}").json()["data"]["project"]["config"]
    assert cfg["include_globs"] == ["**/*.py"]
    assert cfg["exclude_globs"] == ["**/.mypy_cache/**"]
    assert cfg["included_paths"] == ["src/foo.py", "docs/api.md"]
    assert cfg["use_gitignore"] is True


def test_enrichment_reset_wipes_unknown_files_via_allowlist(client, tmp_path):
    """Files not in any stage's output spec also get wiped.

    Regression: previous denylist-based reset left atlas_swarm_synthesis.json,
    trace_cluster_swarm_synthesis.json, and any future-added stage outputs
    behind. Allowlist behavior wipes them by default.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Seed a fast-sync output (must SURVIVE)
    (idx_dir / "trace_nodes.jsonl").write_text("{}\n")
    # Seed a known enrichment output (must be wiped)
    (idx_dir / "trace_modules.jsonl").write_text("{}\n")
    # Seed UNKNOWN files (regression — must also be wiped)
    (idx_dir / "atlas_swarm_synthesis_v99.json").write_text("{}")
    (idx_dir / "future_stage_output.jsonl").write_text("{}")

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert (idx_dir / "trace_nodes.jsonl").is_file()  # fast-sync survived
    assert not (idx_dir / "trace_modules.jsonl").exists()
    assert not (idx_dir / "atlas_swarm_synthesis_v99.json").exists()
    assert not (idx_dir / "future_stage_output.jsonl").exists()


def test_finalize_reset_preserves_enrichment_outputs(client, tmp_path):
    """Reset 11-15 keeps deep_enrichment outputs (stages 6-10)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Fast-sync + enrichment outputs (must SURVIVE)
    (idx_dir / "trace_nodes.jsonl").write_text("{}\n")
    (idx_dir / "trace_epistemic.jsonl").write_text("{}\n")
    (idx_dir / "trace_modules.jsonl").write_text("{}\n")
    # Finalize outputs (must be wiped)
    (idx_dir / "atlas.json").write_text("{}")
    (idx_dir / "rules_manifest.json").write_text("{}")

    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    assert (idx_dir / "trace_nodes.jsonl").is_file()
    assert (idx_dir / "trace_epistemic.jsonl").is_file()
    assert (idx_dir / "trace_modules.jsonl").is_file()
    assert not (idx_dir / "atlas.json").exists()
    assert not (idx_dir / "rules_manifest.json").exists()


def test_all_data_files_covers_every_stage_output():
    """Parity test (2026-05-17). The full-reset wipe iterates
    ALL_DATA_FILES (TRACE_FILES + INDEX_FILES + RECOVERY_MARKERS); if a
    new stage output is added to STAGE_OUTPUTS but not to ALL_DATA_FILES,
    that file silently survives /index/destroy and confuses coverage /
    selfheal / next-run resume on the freshly-"reset" project.

    Phase 134 (changeset.json) + Phase 124 T2 (atlas_markdown_links) +
    the catalogue + swarm-synthesis artifacts all leaked through this
    exact gap. This test pins parity so the next leak fails CI here
    instead of in dogfooding."""
    from prep.api.routers.trace_routes.shared import ALL_DATA_FILES
    from prep.services.pipeline.stages import STAGE_OUTPUTS

    all_stage_files: set[str] = set()
    for spec in STAGE_OUTPUTS.values():
        all_stage_files |= spec.files

    # KnowledgeIndex outputs live in INDEX_FILES already (the
    # double-listing is intentional: same files used in two contexts).
    # Both lists feed into ALL_DATA_FILES so the union below covers them.
    missing = all_stage_files - set(ALL_DATA_FILES)
    assert not missing, (
        "STAGE_OUTPUTS contains file(s) not listed in ALL_DATA_FILES — "
        "these would survive /index/destroy and confuse the next run. "
        "Add them to TRACE_FILES (or INDEX_FILES for embedding outputs) "
        f"in src/prep/api/routers/trace_routes/shared.py. Missing: {sorted(missing)}"
    )


def test_index_destroy_wipes_f67_pending_backups(client, tmp_path):
    """2026-05-17 regression. F-67 (orchestrator.py:2399) renames stale
    manifests to <name>.f67_pending at stage start so resume detection
    sees absence after a mid-stage crash. On a full reset the rebuild
    these came from is discarded — but the backups previously survived
    /index/destroy, letting a future selfheal pass restore them and
    making the next run resume from the wrong stage."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Seed F-67 backups (simulating an interrupted rebuild).
    (idx_dir / "trace_manifest.json.f67_pending").write_text("{}")
    (idx_dir / "trace_epistemic_manifest.json.f67_pending").write_text("{}")
    (idx_dir / "knowledge_manifest.json.f67_pending").write_text("{}")

    res = client.delete(f"/projects/{pid}/index/destroy")
    assert res.status_code in (200, 207), res.text

    leftover = list(idx_dir.glob("*.f67_pending")) if idx_dir.is_dir() else []
    assert not leftover, (
        f"/index/destroy must wipe F-67 pending-rename backups so a "
        f"future selfheal cannot resurrect them. Leftover: "
        f"{[p.name for p in leftover]}"
    )


def test_index_destroy_wipes_changeset(client, tmp_path):
    """2026-05-17 regression. Phase 134 introduced changeset.json (the
    inter-stage truth signal) but never added it to ALL_DATA_FILES,
    so /index/destroy left it behind. Coverage at coverage.py:101 then
    re-read the stale changeset and classified every file as `stale`
    (because the last rebuild had filled cs.modified) instead of
    `untraced` — the Graph Scope panel showed "74 stale" on a
    freshly-wiped project. After this fix, full reset wipes the
    changeset so coverage falls into the cs-is-None branch and files
    appear as untraced, matching the user's mental model: stale = was
    indexed AND changed; untraced = was never indexed (or wiped)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    _seed_full_project(idx_dir)
    (idx_dir / "changeset.json").write_text(
        '{"added":[],"modified":["main.py"],"deleted":[],"unchanged":[],'
        '"run_id":"r1","base_run_id":null}'
    )

    res = client.delete(f"/projects/{pid}/index/destroy")
    assert res.status_code in (200, 207), res.text

    assert not (idx_dir / "changeset.json").exists(), (
        "/index/destroy must wipe changeset.json so coverage re-classifies "
        "files as untraced. Otherwise post-reset Graph Scope falsely shows "
        "every file as stale."
    )


def test_enrichment_reset_wipes_audit_dir(client, tmp_path):
    """Regression: audit/spaghetti.json was surviving despite audit/ being
    in the denylist. Allowlist with explicit audit/ exclusion fixes."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = idx_dir / "audit"
    audit_dir.mkdir()
    (audit_dir / "spaghetti.json").write_text("{}")

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert not audit_dir.exists()
