# Phase 120 — Named Scopes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a universal "named scope" primitive — a per-request RAG file mask, selectable from a dropdown in the existing Scope panel and addressable from MCP via `prep(scope="marketing")`. Decouples Phase 67's role-keyed `agent_scope` from the role concept and deletes the parallel `AgentScopePanel`.

**Architecture:** Three orthogonal axes — trace graph (untouched), role projection (untouched), named scope (new). Named scopes live in the existing per-project `settings_store` under `project/<pid>/scope/<scope_id>` keys. The `global` scope is a virtual view onto today's `project.config.included_paths`. The build pipeline gains a single `compute_index_membership(project_id) → Set[str]` helper that returns the deduped union (global ∪ all named scope paths) and replaces five direct `pcfg.get("included_paths")` reads. Search-time masking uses a new `scope_resolver.resolve_mask(project_id, scope, role)` function with four resolution rules.

**Tech Stack:** Python 3.11 (FastAPI, Pydantic, pytest), TypeScript (React/Vite, Tremor, Tailwind, Vitest), the project's `.venv` for Python tooling.

**Convention notes:**
- Use `.venv/bin/pytest` and `.venv/bin/ruff` (project venv, per repo memory).
- Commit messages are Conventional-Commit style; **no Co-Authored-By trailer** (per repo memory).
- Tests live in `tests/` (not `src/prep/tests/`).
- All new Python files include `from __future__ import annotations`.

---

## Phase A — Backend foundation (Tasks 1–7)

### Task 1: ScopeRecord model and ScopeStore CRUD

**Files:**
- Create: `src/prep/core/scope_store.py`
- Test:   `tests/test_scope_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scope_store.py
from __future__ import annotations
from prep.core.scope_store import ScopeStore, ScopeRecord, GLOBAL_SCOPE_ID


def test_create_get_round_trip(tmp_settings):
    store = ScopeStore()
    rec = store.create("proj-1", display_name="Marketing",
                      paths=["websites/marketing/"], assigned_to_role=None)
    assert rec.id == "marketing"
    assert rec.display_name == "Marketing"
    assert rec.paths == ["websites/marketing/"]
    fetched = store.get("proj-1", "marketing")
    assert fetched == rec


def test_slug_collision_auto_suffix(tmp_settings):
    store = ScopeStore()
    a = store.create("proj-1", display_name="Marketing", paths=[])
    b = store.create("proj-1", display_name="Marketing", paths=[])
    assert a.id == "marketing"
    assert b.id == "marketing_2"


def test_global_id_is_reserved(tmp_settings):
    store = ScopeStore()
    import pytest
    with pytest.raises(ValueError, match="reserved"):
        store.create("proj-1", display_name="global", paths=[])


def test_list_excludes_global(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="Marketing", paths=[])
    store.create("proj-1", display_name="Data Cleaning", paths=[])
    ids = [r.id for r in store.list("proj-1")]
    assert ids == ["data_cleaning", "marketing"]
    assert GLOBAL_SCOPE_ID not in ids


def test_assigned_to_role_uniqueness(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="A", paths=[], assigned_to_role="cto")
    import pytest
    with pytest.raises(ValueError, match="already assigned"):
        store.create("proj-1", display_name="B", paths=[], assigned_to_role="cto")


def test_delete(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="Marketing", paths=["x/"])
    assert store.delete("proj-1", "marketing") is True
    assert store.get("proj-1", "marketing") is None
    assert store.delete("proj-1", "marketing") is False
```

A pytest fixture `tmp_settings` should swap the `settings_store` singleton's underlying SQLite file to a tmp_path-backed copy. Add to `tests/conftest.py` if it does not already exist:

```python
# tests/conftest.py (add this fixture; leave existing fixtures intact)
import pytest
from pathlib import Path

@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    from prep.services import settings_store as ss
    db = tmp_path / "settings.db"
    monkeypatch.setattr(ss.settings, "_db_path", db, raising=False)
    # reset cache
    if hasattr(ss.settings, "_conn"):
        ss.settings._conn = None
    yield ss.settings
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_scope_store.py -v
```

Expected: ImportError or "module 'prep.core.scope_store' has no attribute 'ScopeStore'".

- [ ] **Step 3: Implement scope_store.py**

```python
# src/prep/core/scope_store.py
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

GLOBAL_SCOPE_ID = "global"
_SCOPE_KEY_PREFIX = "scope"
_MAX_SLUG_SUFFIX = 99


@dataclass
class ScopeRecord:
    id: str
    display_name: str
    paths: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)  # reserved for v1.1
    assigned_to_role: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScopeRecord":
        return cls(
            id=str(d["id"]),
            display_name=str(d.get("display_name", d["id"])),
            paths=list(d.get("paths", [])),
            weights=dict(d.get("weights", {})),
            assigned_to_role=d.get("assigned_to_role"),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )


class ScopeStore:
    def get(self, project_id: str, scope_id: str) -> Optional[ScopeRecord]:
        from prep.services.settings_store import settings
        raw = settings.project_get(project_id, f"{_SCOPE_KEY_PREFIX}.{scope_id}")
        if not isinstance(raw, dict):
            return None
        return ScopeRecord.from_dict(raw)

    def list(self, project_id: str) -> List[ScopeRecord]:
        from prep.services.settings_store import settings
        all_settings = settings.project_get_all(project_id)
        prefix = f"{_SCOPE_KEY_PREFIX}."
        out: List[ScopeRecord] = []
        for key, value in all_settings.items():
            if key.startswith(prefix) and isinstance(value, dict):
                out.append(ScopeRecord.from_dict(value))
        return sorted(out, key=lambda r: r.id)

    def create(
        self,
        project_id: str,
        display_name: str,
        paths: Optional[List[str]] = None,
        assigned_to_role: Optional[str] = None,
    ) -> ScopeRecord:
        slug = _slugify(display_name)
        if slug == GLOBAL_SCOPE_ID:
            raise ValueError(f"scope id '{GLOBAL_SCOPE_ID}' is reserved")
        scope_id = self._allocate_unique_id(project_id, slug)
        if assigned_to_role:
            self._check_role_unique(project_id, assigned_to_role, exclude_id=None)
        now = _iso_now()
        rec = ScopeRecord(
            id=scope_id,
            display_name=display_name,
            paths=sorted(set(paths or [])),
            assigned_to_role=assigned_to_role,
            created_at=now,
            updated_at=now,
        )
        self._write(project_id, rec)
        return rec

    def update(
        self,
        project_id: str,
        scope_id: str,
        display_name: Optional[str] = None,
        assigned_to_role: Optional[str] = None,
    ) -> ScopeRecord:
        rec = self.get(project_id, scope_id)
        if rec is None:
            raise KeyError(scope_id)
        if assigned_to_role is not None and assigned_to_role != rec.assigned_to_role:
            self._check_role_unique(project_id, assigned_to_role, exclude_id=scope_id)
            rec.assigned_to_role = assigned_to_role or None
        if display_name is not None:
            rec.display_name = display_name
        rec.updated_at = _iso_now()
        self._write(project_id, rec)
        return rec

    def set_paths(self, project_id: str, scope_id: str, paths: List[str]) -> ScopeRecord:
        rec = self.get(project_id, scope_id)
        if rec is None:
            raise KeyError(scope_id)
        rec.paths = sorted({p for p in paths if p})
        rec.updated_at = _iso_now()
        self._write(project_id, rec)
        return rec

    def delete(self, project_id: str, scope_id: str) -> bool:
        from prep.services.settings_store import settings
        return settings.project_delete(project_id, f"{_SCOPE_KEY_PREFIX}.{scope_id}")

    # ── internals ────────────────────────────────────────────────
    def _write(self, project_id: str, rec: ScopeRecord) -> None:
        from prep.services.settings_store import settings
        settings.project_set(project_id, f"{_SCOPE_KEY_PREFIX}.{rec.id}", rec.to_dict())

    def _allocate_unique_id(self, project_id: str, slug: str) -> str:
        if self.get(project_id, slug) is None:
            return slug
        for n in range(2, _MAX_SLUG_SUFFIX + 1):
            candidate = f"{slug}_{n}"
            if self.get(project_id, candidate) is None:
                return candidate
        raise ValueError(f"slug collision exhausted for '{slug}'")

    def _check_role_unique(
        self, project_id: str, role: str, exclude_id: Optional[str]
    ) -> None:
        for rec in self.list(project_id):
            if rec.id == exclude_id:
                continue
            if rec.assigned_to_role == role:
                raise ValueError(f"role '{role}' already assigned to scope '{rec.id}'")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_") or "scope"


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Module-level singleton
scope_store = ScopeStore()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_scope_store.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/scope_store.py tests/test_scope_store.py tests/conftest.py
git commit -m "feat(phase120): add ScopeStore for named-scope CRUD

ScopeRecord dataclass + ScopeStore class with CRUD against
settings_store. Reserves the 'global' scope id and enforces
per-project uniqueness of assigned_to_role."
```

---

### Task 2: compute_index_membership helper

**Files:**
- Modify: `src/prep/services/project_helpers.py` (add new function near bottom)
- Test:   `tests/test_compute_index_membership.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compute_index_membership.py
from __future__ import annotations
import pytest
from prep.services.project_helpers import compute_index_membership
from prep.core.scope_store import scope_store


def test_membership_is_global_when_no_scopes(tmp_settings, dummy_project):
    dummy_project.config["included_paths"] = ["src/", "docs/"]
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/", "docs/"}


def test_membership_unions_global_with_scope_paths(
    tmp_settings, dummy_project,
):
    dummy_project.config["included_paths"] = ["src/"]
    scope_store.create(dummy_project.id, display_name="Marketing",
                      paths=["websites/marketing/", "src/marketing.md"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/", "websites/marketing/", "src/marketing.md"}


def test_membership_dedups_overlapping_paths(tmp_settings, dummy_project):
    dummy_project.config["included_paths"] = ["src/"]
    scope_store.create(dummy_project.id, display_name="A", paths=["src/"])
    scope_store.create(dummy_project.id, display_name="B", paths=["src/"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/"}


def test_membership_with_no_global_returns_scope_union(
    tmp_settings, dummy_project,
):
    dummy_project.config["included_paths"] = []
    scope_store.create(dummy_project.id, display_name="Marketing",
                      paths=["websites/marketing/"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"websites/marketing/"}
```

`dummy_project` fixture (add to `tests/conftest.py`):

```python
@pytest.fixture
def dummy_project(tmp_path, monkeypatch):
    from prep.core.project_registry import Project
    proj = Project(
        id="proj-test",
        name="Test",
        root=str(tmp_path),
        config={"included_paths": []},
    )
    from prep.services import project_helpers as ph
    monkeypatch.setattr(ph, "require_project", lambda pid: proj)
    return proj
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_compute_index_membership.py -v
```

Expected: ImportError on `compute_index_membership`.

- [ ] **Step 3: Add `compute_index_membership` to project_helpers.py**

Append to `src/prep/services/project_helpers.py`:

```python
def compute_index_membership(project_id: str) -> set[str]:
    """Return the deduped set of paths that should be embedded for a project.

    The set is the union of:
    - project.config.included_paths (the user's global Scope panel selection)
    - scope.paths for every named scope in the project's scope store

    Used by the build pipeline as the source of truth for "what to embed."
    Replaces the prior `pcfg.get("included_paths")` direct reads.
    """
    proj = require_project(project_id)
    cfg = proj.config or {}
    members: set[str] = set(cfg.get("included_paths") or [])
    from prep.core.scope_store import scope_store
    for rec in scope_store.list(project_id):
        members.update(rec.paths)
    return members
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_compute_index_membership.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/project_helpers.py tests/test_compute_index_membership.py tests/conftest.py
git commit -m "feat(phase120): add compute_index_membership helper

Returns the deduped union of included_paths plus every named scope's
paths. The build pipeline reads this in place of included_paths so
files added to a non-global scope are embedded."
```

---

### Task 3: scope_resolver — mask resolution + path matching

**Files:**
- Create: `src/prep/core/scope_resolver.py`
- Test:   `tests/test_scope_resolver.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scope_resolver.py
from __future__ import annotations
from prep.core.scope_resolver import (
    resolve_mask, path_matches_any_scope, MaskResolution,
)
from prep.core.scope_store import scope_store


def test_explicit_scope_known_returns_paths(tmp_settings, dummy_project):
    scope_store.create(dummy_project.id, display_name="Marketing",
                      paths=["websites/marketing/"])
    res = resolve_mask(dummy_project.id, scope="marketing", role=None)
    assert res.applied_scope == "marketing"
    assert res.mask == {"websites/marketing/"}
    assert res.warning is None


def test_explicit_scope_unknown_falls_back_to_global_with_warning(
    tmp_settings, dummy_project,
):
    res = resolve_mask(dummy_project.id, scope="marketin", role=None)
    assert res.applied_scope == "global"
    assert res.mask is None  # global = no mask
    assert "marketin" in (res.warning or "")


def test_role_with_assigned_scope_uses_that_scope(tmp_settings, dummy_project):
    scope_store.create(dummy_project.id, display_name="Copy",
                      paths=["docs/copy/"], assigned_to_role="copywriter")
    res = resolve_mask(dummy_project.id, scope=None, role="copywriter")
    assert res.applied_scope == "copy"
    assert res.mask == {"docs/copy/"}


def test_role_without_assigned_scope_returns_global(tmp_settings, dummy_project):
    res = resolve_mask(dummy_project.id, scope=None, role="copywriter")
    assert res.applied_scope == "global"
    assert res.mask is None


def test_no_args_returns_global(tmp_settings, dummy_project):
    res = resolve_mask(dummy_project.id, scope=None, role=None)
    assert res.applied_scope == "global"
    assert res.mask is None


def test_explicit_scope_overrides_role_assignment(tmp_settings, dummy_project):
    scope_store.create(dummy_project.id, display_name="Copy",
                      paths=["docs/copy/"], assigned_to_role="copywriter")
    scope_store.create(dummy_project.id, display_name="Marketing",
                      paths=["websites/marketing/"])
    res = resolve_mask(dummy_project.id, scope="marketing", role="copywriter")
    assert res.applied_scope == "marketing"
    assert res.mask == {"websites/marketing/"}


def test_path_matches_any_scope_exact():
    assert path_matches_any_scope("src/foo.py", {"src/foo.py"}) is True


def test_path_matches_any_scope_prefix():
    assert path_matches_any_scope("src/foo.py", {"src/"}) is True


def test_path_matches_any_scope_no_match():
    assert path_matches_any_scope("docs/x.md", {"src/", "tests/"}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_scope_resolver.py -v
```

Expected: ImportError on `prep.core.scope_resolver`.

- [ ] **Step 3: Implement scope_resolver.py**

```python
# src/prep/core/scope_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set


@dataclass(frozen=True)
class MaskResolution:
    """Result of resolving a (scope, role) request to a file mask.

    - mask is None means "no filtering" (full RAG over included_paths union).
    - applied_scope is always a string for the response envelope; "global" when
      no per-scope mask is in effect.
    - warning is set when the requested scope was not found and we fell back
      to global.
    """
    mask: Optional[Set[str]]
    applied_scope: str
    warning: Optional[str] = None


def resolve_mask(
    project_id: str,
    scope: Optional[str],
    role: Optional[str],
) -> MaskResolution:
    """Resolve (scope, role) to a file-mask + applied-scope label.

    Resolution rules (in order):
    1. If `scope=X` is passed and scope.<X> exists → mask = its paths.
    2. Else if `scope=X` is passed but no such scope exists → mask = None
       (global), warning carries the unknown name.
    3. Else if `role=Y` is passed AND a scope has assigned_to_role == Y →
       mask = that scope's paths.
    4. Else → mask = None (global), no warning.
    """
    from prep.core.scope_store import scope_store

    if scope:
        rec = scope_store.get(project_id, scope)
        if rec is not None:
            return MaskResolution(mask=set(rec.paths), applied_scope=rec.id)
        return MaskResolution(
            mask=None,
            applied_scope="global",
            warning=f"requested '{scope}' not found, used global",
        )

    if role:
        for rec in scope_store.list(project_id):
            if rec.assigned_to_role == role:
                return MaskResolution(mask=set(rec.paths), applied_scope=rec.id)

    return MaskResolution(mask=None, applied_scope="global")


def path_matches_any_scope(file_path: str, scope_paths: Set[str]) -> bool:
    """Check if `file_path` is covered by any path in `scope_paths`.

    Matches exactly or as a directory prefix (scope entry "src/" matches
    "src/foo.py"). Public successor of agent_scope_manager._path_matches_scope.
    """
    if file_path in scope_paths:
        return True
    for sp in scope_paths:
        prefix = sp.rstrip("/") + "/"
        if file_path.startswith(prefix):
            return True
    return False
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_scope_resolver.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/scope_resolver.py tests/test_scope_resolver.py
git commit -m "feat(phase120): add scope_resolver with 4 resolution rules

resolve_mask() implements the explicit-scope > role-assignment > global
fallback chain. path_matches_any_scope() is the public successor of
agent_scope_manager._path_matches_scope (which was a private cross-module
import smell)."
```

---

### Task 4: mutate_global_scope helper + Phase 24 refactor

**Files:**
- Modify: `src/prep/services/project_helpers.py` (add helper)
- Modify: `src/prep/api/routers/scope.py` (refactor `/scope/add` and `/scope/remove` to delegate)
- Test:   `tests/test_mutate_global_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mutate_global_scope.py
from __future__ import annotations
from prep.services.project_helpers import mutate_global_scope


def test_add_paths_to_global(tmp_settings, dummy_project_in_registry):
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "add", ["src/", "docs/"])
    assert set(new_paths) == {"src/", "docs/"}


def test_remove_paths_from_global(tmp_settings, dummy_project_in_registry):
    mutate_global_scope(dummy_project_in_registry.id, "add", ["src/", "docs/"])
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "remove", ["docs/"])
    assert set(new_paths) == {"src/"}


def test_add_prunes_descendants_already_present(
    tmp_settings, dummy_project_in_registry,
):
    mutate_global_scope(dummy_project_in_registry.id, "add", ["src/foo.py"])
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "add", ["src/"])
    assert set(new_paths) == {"src/"}


def test_invalid_action_raises(tmp_settings, dummy_project_in_registry):
    import pytest
    with pytest.raises(ValueError):
        mutate_global_scope(dummy_project_in_registry.id, "frobnicate", ["x"])
```

`dummy_project_in_registry` is `dummy_project` but additionally registered with `_get_registry`. Add this fixture variant to `tests/conftest.py`:

```python
@pytest.fixture
def dummy_project_in_registry(dummy_project, monkeypatch):
    from prep.core import project_registry
    monkeypatch.setattr(project_registry, "_registry_singleton", _FakeReg(dummy_project))
    return dummy_project


class _FakeReg:
    def __init__(self, proj):
        self._proj = proj

    def get_project(self, project_id):
        return self._proj if project_id == self._proj.id else None

    def mutate_config(self, project_id, fn):
        if project_id != self._proj.id:
            return
        self._proj.config = fn(self._proj.config or {})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_mutate_global_scope.py -v
```

Expected: ImportError on `mutate_global_scope`.

- [ ] **Step 3: Add `mutate_global_scope` to project_helpers.py**

```python
def mutate_global_scope(
    project_id: str, action: str, paths: list[str]
) -> list[str]:
    """Atomic RMW on `project.config.included_paths`. Single source of truth
    for both Phase 24's `/scope/*` endpoints and Phase 120's
    `/scopes/global/*` endpoints.

    `action` is "add" or "remove". Returns the new sorted included_paths.
    """
    if action not in ("add", "remove"):
        raise ValueError(f"action must be 'add' or 'remove', got {action!r}")

    def _apply(cfg: dict) -> dict:
        current = set(cfg.get("included_paths", []))
        if action == "add":
            for p in paths:
                if not p:
                    continue
                current.add(p)
                prefix = p + "/"
                current = {x for x in current if not x.startswith(prefix) or x == p}
        else:
            for p in paths:
                current.discard(p)
                prefix = p + "/"
                current = {x for x in current if not x.startswith(prefix)}
        return {**cfg, "included_paths": sorted(current)}

    from prep.core.project_registry import _registry_singleton
    _registry_singleton.mutate_config(project_id, _apply)
    proj = _registry_singleton.get_project(project_id)
    return sorted((proj.config or {}).get("included_paths", []))
```

- [ ] **Step 4: Refactor Phase 24 endpoints in routers/scope.py**

Find `scope_add_files` and `scope_remove_files` in `src/prep/api/routers/scope.py` (around lines 105–185). Replace the bodies' atomic RMW + state read with a single call to `mutate_global_scope`. The orchestrator notify call stays:

```python
# routers/scope.py — scope_add_files
from prep.services.project_helpers import mutate_global_scope
new_paths = mutate_global_scope(project_id, "add", req.paths)
from prep.services.scope_orchestrator import scope_orchestrator
_ensure_build_fn_registered(project_id)
scope_orchestrator.on_files_added(project_id, req.paths)
return ok({
    "added": len(req.paths),
    "included_paths": new_paths,
    "status": scope_orchestrator.status(project_id),
})
```

Mirror for `scope_remove_files` with `action="remove"` and `on_files_removed`.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_mutate_global_scope.py tests/api/test_scope_endpoints.py -v
```

Expected: helper tests pass; existing Phase 24 endpoint tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/project_helpers.py src/prep/api/routers/scope.py tests/test_mutate_global_scope.py
git commit -m "refactor(phase120): extract mutate_global_scope helper

Phase 24's /scope/add and /scope/remove now delegate to
project_helpers.mutate_global_scope. Phase 120's /scopes/global/*
will reuse the same helper to prevent drift between the two URL
surfaces."
```

---

### Task 5: /scopes HTTP router (CRUD endpoints)

**Files:**
- Create: `src/prep/api/routers/scopes.py`
- Modify: `src/prep/server.py` (mount the new router)
- Test:   `tests/api/test_scopes_endpoints.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_scopes_endpoints.py
from __future__ import annotations
from fastapi.testclient import TestClient


def test_list_includes_synthetic_global(client: TestClient, project):
    r = client.get(f"/projects/{project.id}/scopes")
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [s["id"] for s in body["scopes"]]
    assert "global" in ids


def test_create_returns_record(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "Marketing", "paths": ["websites/marketing/"]},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["id"] == "marketing"
    assert body["paths"] == ["websites/marketing/"]


def test_get_global_synthesizes_from_included_paths(client, project):
    project.config["included_paths"] = ["src/"]
    r = client.get(f"/projects/{project.id}/scopes/global")
    body = r.json()["data"]
    assert body["id"] == "global"
    assert body["paths"] == ["src/"]


def test_delete_global_is_rejected(client, project):
    r = client.delete(f"/projects/{project.id}/scopes/global")
    assert r.status_code == 400


def test_delete_named_scope(client, project):
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "M", "paths": []})
    r = client.delete(f"/projects/{project.id}/scopes/m")
    assert r.status_code == 200
    r2 = client.get(f"/projects/{project.id}/scopes/m")
    assert r2.status_code == 404


def test_unknown_scope_get_returns_404(client, project):
    r = client.get(f"/projects/{project.id}/scopes/nope")
    assert r.status_code == 404
```

`client` and `project` fixtures should already exist in `tests/api/conftest.py`. If not, mirror the pattern from `tests/api/test_atlas_endpoints.py` if it exists, or create the smallest viable client fixture against `prep.server.app`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/api/test_scopes_endpoints.py -v
```

Expected: 404s on every endpoint (router not mounted).

- [ ] **Step 3: Implement the router**

```python
# src/prep/api/routers/scopes.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok
from prep.core.scope_store import scope_store, GLOBAL_SCOPE_ID

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scopes"])


# ── Request models ───────────────────────────────────────────────
class CreateScopeRequest(BaseModel):
    display_name: str
    paths: Optional[List[str]] = None
    assigned_to_role: Optional[str] = None


class UpdateScopeRequest(BaseModel):
    display_name: Optional[str] = None
    assigned_to_role: Optional[str] = None


class PathsRequest(BaseModel):
    paths: List[str]


# ── Helpers ──────────────────────────────────────────────────────
def _synthesize_global(project_id: str) -> Dict[str, Any]:
    from prep.services.project_helpers import require_project
    proj = require_project(project_id)
    paths = sorted((proj.config or {}).get("included_paths", []))
    return {
        "id": GLOBAL_SCOPE_ID,
        "display_name": "Global",
        "paths": paths,
        "weights": {},
        "assigned_to_role": None,
        "created_at": "",
        "updated_at": "",
    }


def _summary(rec_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": rec_dict["id"],
        "display_name": rec_dict["display_name"],
        "path_count": len(rec_dict.get("paths", [])),
        "assigned_to_role": rec_dict.get("assigned_to_role"),
    }


# ── Endpoints ────────────────────────────────────────────────────
@router.get("/projects/{project_id}/scopes")
def list_scopes(project_id: str) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    summaries = [_summary(_synthesize_global(project_id))]
    summaries.extend(_summary(r.to_dict()) for r in scope_store.list(project_id))
    return ok({"scopes": summaries})


@router.get("/projects/{project_id}/scopes/{scope_id}")
def get_scope(project_id: str, scope_id: str) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        return ok(_synthesize_global(project_id))
    rec = scope_store.get(project_id, scope_id)
    if rec is None:
        raise ApiException(status_code=404, code="SCOPE_NOT_FOUND",
                           message=f"scope '{scope_id}' not found")
    return ok(rec.to_dict())


@router.post("/projects/{project_id}/scopes")
def create_scope(project_id: str, req: CreateScopeRequest) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    try:
        rec = scope_store.create(
            project_id,
            display_name=req.display_name,
            paths=req.paths,
            assigned_to_role=req.assigned_to_role,
        )
    except ValueError as e:
        raise ApiException(status_code=409, code="SCOPE_INVALID", message=str(e))
    return ok(rec.to_dict())


@router.put("/projects/{project_id}/scopes/{scope_id}")
def update_scope(
    project_id: str, scope_id: str, req: UpdateScopeRequest,
) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        raise ApiException(status_code=400, code="GLOBAL_IMMUTABLE",
                           message="global scope metadata is immutable")
    try:
        rec = scope_store.update(
            project_id, scope_id,
            display_name=req.display_name,
            assigned_to_role=req.assigned_to_role,
        )
    except KeyError:
        raise ApiException(status_code=404, code="SCOPE_NOT_FOUND",
                           message=f"scope '{scope_id}' not found")
    except ValueError as e:
        raise ApiException(status_code=409, code="SCOPE_INVALID", message=str(e))
    return ok(rec.to_dict())


@router.delete("/projects/{project_id}/scopes/{scope_id}")
def delete_scope(project_id: str, scope_id: str) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        raise ApiException(status_code=400, code="GLOBAL_UNDELETABLE",
                           message="global scope cannot be deleted")
    deleted = scope_store.delete(project_id, scope_id)
    return ok({"deleted": deleted})
```

- [ ] **Step 4: Mount the router in server.py**

In `src/prep/server.py`, find where other routers are included (search for `from prep.api.routers import scope`) and add:

```python
from prep.api.routers import scopes as scopes_router
app.include_router(scopes_router.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/api/test_scopes_endpoints.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/scopes.py src/prep/server.py tests/api/test_scopes_endpoints.py
git commit -m "feat(phase120): add /projects/{id}/scopes CRUD router

GET/POST/PUT/DELETE for named scopes, plus a synthetic 'global'
record reading from included_paths. global is rejected on delete and
metadata-update."
```

---

### Task 6: /scopes path-add/remove with build-pipeline notifications

**Files:**
- Modify: `src/prep/api/routers/scopes.py` (add path mutator endpoints)
- Test:   extend `tests/api/test_scopes_endpoints.py`

- [ ] **Step 1: Add the failing tests**

```python
# tests/api/test_scopes_endpoints.py — append
def test_add_paths_to_global_writes_included_paths(client, project):
    r = client.post(f"/projects/{project.id}/scopes/global/add",
                    json={"paths": ["src/foo.py"]})
    assert r.status_code == 200
    proj = client.app.state.registry.get_project(project.id)
    assert "src/foo.py" in proj.config["included_paths"]


def test_add_paths_to_named_scope_writes_record(client, project):
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "M", "paths": []})
    r = client.post(f"/projects/{project.id}/scopes/m/add",
                    json={"paths": ["websites/marketing/"]})
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["paths"] == ["websites/marketing/"]


def test_add_to_named_scope_triggers_orchestrator_when_outside_global(
    client, project, mock_orchestrator,
):
    project.config["included_paths"] = ["src/"]
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "M", "paths": []})
    client.post(f"/projects/{project.id}/scopes/m/add",
                json={"paths": ["websites/marketing/"]})
    assert mock_orchestrator.added == [(project.id, ["websites/marketing/"])]


def test_add_to_named_scope_skips_orchestrator_when_inside_global(
    client, project, mock_orchestrator,
):
    project.config["included_paths"] = ["src/"]
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "M", "paths": []})
    client.post(f"/projects/{project.id}/scopes/m/add",
                json={"paths": ["src/foo.py"]})
    # src/foo.py is already in compute_index_membership via global → no new embed
    assert mock_orchestrator.added == []
```

`mock_orchestrator` fixture in `tests/api/conftest.py`:

```python
@pytest.fixture
def mock_orchestrator(monkeypatch):
    class M:
        def __init__(self):
            self.added = []
            self.removed = []
        def on_files_added(self, pid, paths):
            self.added.append((pid, list(paths)))
        def on_files_removed(self, pid, paths):
            self.removed.append((pid, list(paths)))
        def status(self, pid):
            return {"state": "idle"}
    inst = M()
    from prep.services import scope_orchestrator as so
    monkeypatch.setattr(so, "scope_orchestrator", inst)
    return inst
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/api/test_scopes_endpoints.py -v
```

Expected: 4 new tests fail with 404.

- [ ] **Step 3: Implement add/remove endpoints**

Append to `src/prep/api/routers/scopes.py`:

```python
@router.post("/projects/{project_id}/scopes/{scope_id}/add")
def add_paths(
    project_id: str, scope_id: str, req: PathsRequest,
) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    if not req.paths:
        raise ApiException(status_code=400, code="EMPTY_PATHS",
                           message="No file paths provided")

    if scope_id == GLOBAL_SCOPE_ID:
        from prep.services.project_helpers import mutate_global_scope
        new_paths = mutate_global_scope(project_id, "add", req.paths)
        from prep.services.scope_orchestrator import scope_orchestrator
        from prep.api.routers.scope import _ensure_build_fn_registered
        _ensure_build_fn_registered(project_id)
        scope_orchestrator.on_files_added(project_id, req.paths)
        return ok({"id": GLOBAL_SCOPE_ID, "paths": new_paths})

    rec = scope_store.get(project_id, scope_id)
    if rec is None:
        raise ApiException(status_code=404, code="SCOPE_NOT_FOUND",
                           message=f"scope '{scope_id}' not found")

    from prep.services.project_helpers import compute_index_membership
    membership_before = compute_index_membership(project_id)
    rec = scope_store.set_paths(project_id, scope_id,
                               sorted(set(rec.paths) | set(req.paths)))
    new_paths_outside_membership = [p for p in req.paths if p not in membership_before]
    if new_paths_outside_membership:
        from prep.services.scope_orchestrator import scope_orchestrator
        from prep.api.routers.scope import _ensure_build_fn_registered
        _ensure_build_fn_registered(project_id)
        scope_orchestrator.on_files_added(project_id, new_paths_outside_membership)
    return ok(rec.to_dict())


@router.post("/projects/{project_id}/scopes/{scope_id}/remove")
def remove_paths(
    project_id: str, scope_id: str, req: PathsRequest,
) -> Dict[str, Any]:
    from prep.server import _require_project
    _require_project(project_id)
    if not req.paths:
        raise ApiException(status_code=400, code="EMPTY_PATHS",
                           message="No file paths provided")

    if scope_id == GLOBAL_SCOPE_ID:
        from prep.services.project_helpers import mutate_global_scope
        new_paths = mutate_global_scope(project_id, "remove", req.paths)
        from prep.services.scope_orchestrator import scope_orchestrator
        from prep.api.routers.scope import _ensure_build_fn_registered
        _ensure_build_fn_registered(project_id)
        scope_orchestrator.on_files_removed(project_id, req.paths)
        return ok({"id": GLOBAL_SCOPE_ID, "paths": new_paths})

    rec = scope_store.get(project_id, scope_id)
    if rec is None:
        raise ApiException(status_code=404, code="SCOPE_NOT_FOUND",
                           message=f"scope '{scope_id}' not found")

    new_paths = sorted(set(rec.paths) - set(req.paths))
    rec = scope_store.set_paths(project_id, scope_id, new_paths)

    from prep.services.project_helpers import compute_index_membership
    membership_after = compute_index_membership(project_id)
    paths_dropped_from_membership = [p for p in req.paths if p not in membership_after]
    if paths_dropped_from_membership:
        from prep.services.scope_orchestrator import scope_orchestrator
        from prep.api.routers.scope import _ensure_build_fn_registered
        _ensure_build_fn_registered(project_id)
        scope_orchestrator.on_files_removed(project_id, paths_dropped_from_membership)
    return ok(rec.to_dict())
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/api/test_scopes_endpoints.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/scopes.py tests/api/test_scopes_endpoints.py
git commit -m "feat(phase120): wire scope add/remove to scope_orchestrator

Adds to global delegate to mutate_global_scope. Adds to named scopes
write the scope record AND trigger an incremental embed only for
paths newly entering compute_index_membership. Removes likewise only
fire on_files_removed for paths leaving the union."
```

---

### Task 7: Switch the 5 build pipeline sites to compute_index_membership

**Files:**
- Modify: `src/prep/services/pipeline/post_flight.py` (3 sites: ~91, ~153, ~202)
- Modify: `src/prep/services/pipeline/workers.py` (1 site: ~896)
- Modify: `src/prep/api/routers/scope.py` (1 site: ~42 in `_build_fn`)

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_pipeline_uses_membership.py
from __future__ import annotations
from prep.services.project_helpers import compute_index_membership


def test_post_flight_reads_membership_not_included_paths(
    tmp_settings, dummy_project_in_registry, monkeypatch,
):
    pid = dummy_project_in_registry.id
    dummy_project_in_registry.config["included_paths"] = ["src/"]
    from prep.core.scope_store import scope_store
    scope_store.create(pid, display_name="M", paths=["websites/marketing/"])

    captured: list[list[str]] = []

    def fake_start(*args, included_paths=None, **kwargs):
        captured.append(list(included_paths or []))
        return True

    from prep.services import build_manager
    monkeypatch.setattr(build_manager.build_manager, "start_project_build", fake_start)

    # Trigger any of the 3 post_flight call paths. Pick the simplest.
    from prep.services.pipeline import post_flight
    post_flight.maybe_resume_build(pid)  # adapt name to actual entry point

    assert captured, "build was never started"
    assert set(captured[-1]) == {"src/", "websites/marketing/"}
```

(If `maybe_resume_build` is not the right entry point in this codebase, pick the closest one to lines 91/153/202 that the test can call directly; keep the assertion the same.)

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_pipeline_uses_membership.py -v
```

Expected: assertion fails — captured contains only `["src/"]`.

- [ ] **Step 3: Update each of the 5 sites**

In `src/prep/services/pipeline/post_flight.py`, find the three blocks that look like:

```python
included_paths = pcfg.get("included_paths") or []
# … pass to start_project_build(included_paths=included_paths if included_paths else None, ...) …
```

Replace each with:

```python
from prep.services.project_helpers import compute_index_membership
included_paths = sorted(compute_index_membership(project_id))
# … pass to start_project_build(included_paths=included_paths or None, ...) …
```

Mirror the same change in `src/prep/services/pipeline/workers.py:896` and the `_build_fn` block in `src/prep/api/routers/scope.py` around line 42–55 (replace `cfg.get("included_paths") or None` with the same `sorted(compute_index_membership(project_id)) or None`).

- [ ] **Step 4: Run the full pipeline test suite**

```bash
.venv/bin/pytest tests/test_pipeline_uses_membership.py tests/ -v -k "pipeline or post_flight or scope_router"
```

Expected: target test now passes; no existing pipeline tests regress.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/post_flight.py src/prep/services/pipeline/workers.py src/prep/api/routers/scope.py tests/test_pipeline_uses_membership.py
git commit -m "feat(phase120): build pipeline reads compute_index_membership

Five sites that previously read pcfg.get('included_paths') now read
the deduped union of included_paths plus every named scope's paths.
This wires Phase 67's never-implemented embedder-pools-the-union
intent to the new universal scope storage."
```

---

## Phase B — Search integration & cleanup (Tasks 8–10)

### Task 8: Replace agent_scope mask in routers/projects/search.py (both sites)

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:54-68` (basic search)
- Modify: `src/prep/api/routers/projects/search.py:1075-1110` (segment-routed search)
- Test:   `tests/api/test_search_with_scope.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_search_with_scope.py
from __future__ import annotations


def test_search_with_scope_filters_results(client, project, indexed_corpus):
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "M", "paths": ["websites/marketing/"]})
    r = client.post(f"/projects/{project.id}/search",
                    json={"query": "hero", "scope": "marketing"})
    body = r.json()["data"]
    assert body["applied_scope"] == "marketing"
    paths = [hit["source_path"] for hit in body["results"]]
    assert all(p.startswith("websites/marketing/") for p in paths)


def test_unknown_scope_falls_back_to_global_with_warning(
    client, project, indexed_corpus,
):
    indexed_corpus(project.id, paths=["src/foo.py"])
    r = client.post(f"/projects/{project.id}/search",
                    json={"query": "foo", "scope": "marketin"})
    body = r.json()["data"]
    assert body["applied_scope"] == "global"
    assert "marketin" in body.get("scope_warning", "")


def test_role_no_longer_auto_applies_mask(client, project, indexed_corpus):
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    # No scope, no assigned_to_role: role should NOT filter results.
    r = client.post(f"/projects/{project.id}/search",
                    json={"query": "foo", "role": "copywriter"})
    body = r.json()["data"]
    assert body["applied_scope"] == "global"
    assert len(body["results"]) >= 2  # both files reachable


def test_role_with_assigned_scope_uses_it(client, project, indexed_corpus):
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    client.post(f"/projects/{project.id}/scopes",
                json={"display_name": "Copy",
                      "paths": ["websites/marketing/"],
                      "assigned_to_role": "copywriter"})
    r = client.post(f"/projects/{project.id}/search",
                    json={"query": "hero", "role": "copywriter"})
    body = r.json()["data"]
    assert body["applied_scope"] == "copy"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/api/test_search_with_scope.py -v
```

Expected: 4 failing — search request models don't accept `scope`, response envelope missing `applied_scope`, etc.

- [ ] **Step 3: Update the search request model and both call sites**

Find the `SearchRequest` Pydantic model in `routers/projects/search.py`. Add `scope: Optional[str] = None`.

Replace lines 52-68 (basic search):

```python
from prep.core.scope_resolver import resolve_mask, path_matches_any_scope
resolution = resolve_mask(project_id, scope=req.scope, role=req.role)
_agent_mask = resolution.mask  # Optional[Set[str]]

out: List[Dict[str, Any]] = []
for r in results:
    d = r.doc
    source_path = str(d.get("source_path") or "")
    if _agent_mask is not None and source_path and not path_matches_any_scope(source_path, _agent_mask):
        continue
    # … rest of the loop unchanged …

envelope_extras = {"applied_scope": resolution.applied_scope,
                   "applied_role": req.role}
if resolution.warning:
    envelope_extras["scope_warning"] = resolution.warning
return ok({"results": out, **envelope_extras})
```

Replace lines 1075–1110 (segment-routed search) with the same `resolve_mask` + `path_matches_any_scope` pattern. Drop the manual `_expanded_mask` directory expansion — the resolver returns set-of-prefix-paths and `path_matches_any_scope` handles prefix matching.

- [ ] **Step 4: Run the search tests**

```bash
.venv/bin/pytest tests/api/test_search_with_scope.py tests/api/test_search.py -v
```

Expected: new tests pass; existing search tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/projects/search.py tests/api/test_search_with_scope.py
git commit -m "feat(phase120): search uses scope_resolver, drops Phase 67 mask

Both /search and /context (segment-routed) now resolve (scope, role)
through the new resolver. The Phase 67 'role auto-applies a file
mask' behavior is removed; role only auto-applies when an explicit
assigned_to_role link exists. Response envelope now carries
applied_scope, applied_role, and an optional scope_warning."
```

---

### Task 9: Replace agent_scope_manager call in agents/shared/prep_data.py

**Files:**
- Modify: `src/prep/agents/shared/prep_data.py:170-180`
- Test:   `tests/test_prep_data_scope.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_prep_data_scope.py
from __future__ import annotations


def test_prep_data_uses_resolver(tmp_settings, dummy_project, monkeypatch):
    from prep.core.scope_store import scope_store
    scope_store.create(dummy_project.id, display_name="Copy",
                      paths=["docs/"], assigned_to_role="copywriter")
    from prep.agents.shared.prep_data import PrepData
    pd = PrepData(project_id=dummy_project.id)
    mask = pd._resolve_mask_for_role("copywriter")
    assert mask == {"docs/"}


def test_prep_data_no_assignment_returns_none(tmp_settings, dummy_project):
    from prep.agents.shared.prep_data import PrepData
    pd = PrepData(project_id=dummy_project.id)
    assert pd._resolve_mask_for_role("nobody") is None
```

(Adapt the public surface to match the actual class name and accessor in `prep_data.py`. Read the file before editing.)

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_prep_data_scope.py -v
```

Expected: AttributeError on the import or method.

- [ ] **Step 3: Update prep_data.py**

In `src/prep/agents/shared/prep_data.py`, locate the block (around lines 170–180):

```python
from prep.core.agent_scope_manager import agent_scope_manager
mask = agent_scope_manager.get_agent_mask(self._project_id, role)
```

Replace with:

```python
from prep.core.scope_resolver import resolve_mask
resolution = resolve_mask(self._project_id, scope=None, role=role)
mask = resolution.mask
```

If the surrounding logic relied on `mask is None` meaning "no scope," that is preserved — `resolve_mask` returns `mask=None` for both "no scope" and "global" outcomes, both of which mean "no filter."

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_prep_data_scope.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/agents/shared/prep_data.py tests/test_prep_data_scope.py
git commit -m "refactor(phase120): prep_data uses scope_resolver

Paperclip integration touchpoint. Behavior is preserved: with the
auto-migrated scope assignment from Phase 67 (or the user creating a
scope with assigned_to_role) the same mask gets applied. Without an
assignment, role no longer silently filters."
```

---

### Task 10: Delete agent_scope_manager and the agent_scope router

**Files:**
- Delete: `src/prep/core/agent_scope_manager.py`
- Delete: `src/prep/api/routers/agent_scope.py`
- Modify: `src/prep/server.py` (unregister the agent_scope router import)
- Verify: no remaining importers

- [ ] **Step 1: Confirm no remaining importers**

```bash
grep -rn "agent_scope_manager\|from prep.api.routers import agent_scope\|routers/agent_scope" src/prep packages 2>/dev/null | grep -v __pycache__
```

Expected: only the two files about to be deleted.

If any other file shows up, fix that file's import first (it should already have been replaced in earlier tasks; this is a safety check).

- [ ] **Step 2: Delete the files**

```bash
rm src/prep/core/agent_scope_manager.py
rm src/prep/api/routers/agent_scope.py
```

- [ ] **Step 3: Remove the import in server.py**

In `src/prep/server.py`, find and delete:

```python
from prep.api.routers import agent_scope
app.include_router(agent_scope.router)
```

- [ ] **Step 4: Run the full backend test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all green. Any failure pinpoints a missed Phase B refactor.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "chore(phase120): delete agent_scope_manager and /agent-scope router

All call sites migrated to scope_store + scope_resolver in Tasks 8-9.
Phase 67's parallel system is removed; Phase 120's universal scope
infrastructure now owns the file-mask axis."
```

---

## Phase C — MCP integration (Tasks 11–13)

### Task 11: Add `scope` parameter to MCP tool schemas

**Files:**
- Modify: `src/prep/mcp_tools.py` (schemas for prep, prep_search, prep_impact, prep_concepts, prep_observe)

- [ ] **Step 1: Read the current schemas**

```bash
grep -n "\"name\": \"prep\"\|\"name\": \"prep_search\"\|\"name\": \"prep_impact\"\|\"name\": \"prep_concepts\"\|\"name\": \"prep_observe\"" src/prep/mcp_tools.py
```

Find each schema's `properties` block.

- [ ] **Step 2: Add `scope` to each tool schema's properties**

For `prep`, `prep_search`, `prep_impact`, `prep_concepts`, and `prep_observe`, add inside the `properties` dict (placed after `role` if `role` exists, otherwise after `project_id`):

```python
"scope": {
    "type": "string",
    "description": (
        "Optional named scope to filter retrieval. Defaults to 'global' "
        "(the project's full Knowledge Sources). Pass a scope id like "
        "'marketing' or 'data-cleaning' to limit results to that file "
        "subset. Unknown scopes silently fall back to global."
    ),
},
```

- [ ] **Step 3: Update the `role` description on prep_search**

Find the `role` property in the `prep_search` schema and replace its description with:

```python
"description": (
    "Optional role for trace-graph projection (centrality + layer + "
    "domain weights). Does not filter files. Use scope= to limit "
    "retrieval to a named file scope."
),
```

- [ ] **Step 4: Smoke-check MCP tool listing**

```bash
.venv/bin/pytest tests/test_mcp_tools_schema.py -v
```

(If a schema-validation test exists; otherwise skip and rely on Task 12's integration test.)

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp_tools.py
git commit -m "feat(phase120): add scope parameter to MCP tool schemas

Five tools (prep, prep_search, prep_impact, prep_concepts,
prep_observe) gain an optional scope parameter. prep_search's role
description is updated to drop the Phase 67 'results are filtered'
wording — role no longer auto-applies a file mask. prep_audit is
intentionally excluded; its existing scope param means something
else and is deferred to a future harmonization phase."
```

---

### Task 12: Wire scope through MCP server handlers and response envelope

**Files:**
- Modify: `src/prep/mcp/server.py` (the five tool handlers)
- Test:   `tests/test_mcp_scope_envelope.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mcp_scope_envelope.py
from __future__ import annotations


async def test_search_tool_envelope_includes_applied_scope(mcp_client, project):
    from prep.core.scope_store import scope_store
    scope_store.create(project.id, display_name="M",
                      paths=["websites/marketing/"])
    result = await mcp_client.call_tool(
        "prep_search",
        {"query": "hero", "scope": "marketing", "project_id": project.id},
    )
    assert result["applied_scope"] == "marketing"


async def test_search_tool_unknown_scope_warning(mcp_client, project):
    result = await mcp_client.call_tool(
        "prep_search",
        {"query": "foo", "scope": "nope", "project_id": project.id},
    )
    assert result["applied_scope"] == "global"
    assert "nope" in result.get("scope_warning", "")


async def test_prep_tool_filters_atlas_by_scope(mcp_client, project):
    from prep.core.scope_store import scope_store
    scope_store.create(project.id, display_name="M",
                      paths=["websites/marketing/"])
    result = await mcp_client.call_tool(
        "prep",
        {"scope": "marketing", "project_id": project.id},
    )
    assert result["applied_scope"] == "marketing"
    # No segments outside websites/marketing/ in the orientation payload.
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_mcp_scope_envelope.py -v
```

Expected: tools don't accept `scope` yet → handler error.

- [ ] **Step 3: Update each tool handler signature in mcp/server.py**

For `prep_search` (around line 862):

```python
async def tool_search(
    self,
    query: str,
    role: Optional[str] = None,
    scope: Optional[str] = None,
    project_id: Optional[str] = None,
    # … rest …
):
    pid = await self._resolve_project_id(override=project_id)
    payload: Dict[str, Any] = {"query": query, "k": k}
    if role:
        payload["role"] = role
    if scope:
        payload["scope"] = scope
    # … existing call to /search …
    # The /search endpoint now returns applied_scope etc. — pass them through.
```

Mirror the param addition + payload pass-through for `prep` (`tool_context`), `prep_impact`, `prep_concepts`, `prep_observe`. Each handler's job is to:
1. Accept `scope: Optional[str] = None`.
2. Pass `scope` to the underlying HTTP call when set.
3. Return the response envelope with `applied_scope`, `applied_role`, and `scope_warning` if present.

For `prep` (the ambient orientation call, no query): apply scope filtering to the segments list returned by the atlas endpoint. Either:
- (a) Pass `?scope=X` to the atlas endpoint (requires a small atlas-endpoint change), or
- (b) Filter the segments client-side in the handler against the resolved mask paths.

Pick (b) for v1 to avoid touching atlas endpoints:

```python
if scope:
    from prep.core.scope_resolver import resolve_mask
    resolution = resolve_mask(pid, scope=scope, role=role)
    if resolution.mask is not None:
        result["modules"] = [
            m for m in result.get("modules", [])
            if any(m.get("dir_path", "").startswith(p.rstrip("/") + "/") or
                   m.get("dir_path") == p.rstrip("/")
                   for p in resolution.mask)
        ]
        result["hub_files"] = [
            h for h in result.get("hub_files", [])
            if path_matches_any_scope(h.get("path", ""), resolution.mask)
        ]
    result["applied_scope"] = resolution.applied_scope
    if resolution.warning:
        result["scope_warning"] = resolution.warning
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_mcp_scope_envelope.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/server.py tests/test_mcp_scope_envelope.py
git commit -m "feat(phase120): MCP handlers wire scope through to response

Each of the five tools accepts an optional scope parameter and threads
it to the daemon. Response envelopes carry applied_scope (always),
applied_role (nullable), and scope_warning (when an unknown scope
falls back to global). The prep ambient handler additionally filters
segments and hub_files client-side so 'prep(scope=marketing)' returns
a scope-flavored orientation."
```

---

### Task 13: AGENTS.md generator lists project scopes

**Files:**
- Modify: `src/prep/core/rules_generator.py:340` (`_build_managed_content`)
- Modify: same file's debounce trigger (so scope CRUD regenerates AGENTS.md)
- Test:   `tests/test_rules_generator_scopes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_rules_generator_scopes.py
from __future__ import annotations


def test_managed_content_lists_scopes(tmp_settings, dummy_project):
    from prep.core.scope_store import scope_store
    scope_store.create(dummy_project.id, display_name="Marketing",
                      paths=["websites/marketing/"])
    scope_store.create(dummy_project.id, display_name="Data Cleaning",
                      paths=["src/cleaners/"])
    from prep.core.rules_generator import _build_managed_content
    md = _build_managed_content(
        project_path=dummy_project.root,
        project_name="Test",
        atlas_content="atlas body",
        included_paths=["src/"],
        is_preliminary=False,
        stats={},
        project_id=dummy_project.id,
    )
    assert "## Scopes" in md
    assert "marketing" in md
    assert "data_cleaning" in md
    assert "scope=" in md  # the hint line
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_rules_generator_scopes.py -v
```

Expected: assertion fails — `"## Scopes"` not in managed content.

- [ ] **Step 3: Add scope listing to `_build_managed_content`**

In `src/prep/core/rules_generator.py`, locate `_build_managed_content` (~line 340). After the existing sections (atlas, focus areas, etc.) but before the closing markers, append:

```python
# Phase 120: Named scopes
try:
    from prep.core.scope_store import scope_store
    scopes = scope_store.list(project_id) if project_id else []
except Exception:
    scopes = []
if scopes:
    parts.append("\n## Scopes\n")
    parts.append(
        "Pass `scope=<name>` to limit retrieval to that surface. "
        "Unknown scopes fall back to global with a warning.\n"
    )
    parts.append("Available scopes: `global`")
    for s in scopes:
        parts.append(f", `{s.id}`")
    parts.append("\n")
```

(Adapt to the function's actual buffer-building idiom — `parts.append`, f-string concat, etc. Read the function before editing.)

- [ ] **Step 4: Hook scope CRUD to AGENTS.md regeneration**

In `src/prep/api/routers/scopes.py`, after each successful mutation (`create_scope`, `update_scope`, `delete_scope`, `add_paths`, `remove_paths`), call the existing debounced regenerator. Find the helper used by Phase 24 (likely `_schedule_rules_refresh(project_id)` in rules_generator) and add:

```python
from prep.core.rules_generator import schedule_rules_refresh
schedule_rules_refresh(project_id)
```

after each return.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_rules_generator_scopes.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prep/core/rules_generator.py src/prep/api/routers/scopes.py tests/test_rules_generator_scopes.py
git commit -m "feat(phase120): AGENTS.md lists named scopes

_build_managed_content emits a Scopes section listing every project
scope plus the scope=<name> usage hint. Scope CRUD endpoints trigger
the existing debounced AGENTS.md regenerator so the file stays in
sync."
```

---

## Phase D — Frontend (Tasks 14–19)

### Task 14: TypeScript types for scope records

**Files:**
- Modify: `packages/ui/src/types.ts`
- Modify: `packages/ui/src/index.ts` (re-export)

- [ ] **Step 1: Add types**

In `packages/ui/src/types.ts`, append:

```typescript
export interface ScopeRecord {
  id: string;
  display_name: string;
  paths: string[];
  weights?: Record<string, number>;
  assigned_to_role: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ScopeSummary {
  id: string;
  display_name: string;
  path_count: number;
  assigned_to_role: string | null;
}

export interface ScopesListResponse {
  scopes: ScopeSummary[];
}
```

- [ ] **Step 2: Re-export from package index**

In `packages/ui/src/index.ts`, add:

```typescript
export type { ScopeRecord, ScopeSummary, ScopesListResponse } from './types';
```

- [ ] **Step 3: Verify typecheck**

```bash
cd packages/ui && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/types.ts packages/ui/src/index.ts
git commit -m "feat(phase120): add ScopeRecord/ScopeSummary types"
```

---

### Task 15: API client methods for scopes

**Files:**
- Modify: `packages/ui/src/api/client.ts`
- Modify: `packages/ui/src/api/mock.ts`
- Modify: `packages/ui/src/api/types.ts` (if interfaces live there)

- [ ] **Step 1: Add the client interface**

In `packages/ui/src/api/client.ts`, find the API class/interface and add:

```typescript
listScopes(projectId: string): Promise<ScopesListResponse>;
getScope(projectId: string, scopeId: string): Promise<ScopeRecord>;
createScope(projectId: string, body: { display_name: string; paths?: string[]; assigned_to_role?: string | null }): Promise<ScopeRecord>;
updateScope(projectId: string, scopeId: string, body: { display_name?: string; assigned_to_role?: string | null }): Promise<ScopeRecord>;
deleteScope(projectId: string, scopeId: string): Promise<void>;
addPathsToScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
removePathsFromScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
```

Implement each as a fetch wrapper following the existing client conventions (`api/${path}` base, `headers: { 'Content-Type': 'application/json' }`, response unwraps `data`).

- [ ] **Step 2: Add mock implementations**

In `packages/ui/src/api/mock.ts`, mirror each method with an in-memory `Map<string, ScopeRecord>` keyed by `${projectId}:${scopeId}`. Synthetic `global` is computed from the mock's `included_paths`.

- [ ] **Step 3: Typecheck and commit**

```bash
cd packages/ui && npm run typecheck
git add packages/ui/src/api/
git commit -m "feat(phase120): API client methods for scope CRUD"
```

---

### Task 16: useScopes hook

**Files:**
- Create: `src/prep/dashboard/src/hooks/useScopes.ts`
- Test:   `src/prep/dashboard/src/hooks/__tests__/useScopes.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// src/prep/dashboard/src/hooks/__tests__/useScopes.test.ts
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useScopes } from '../useScopes';

describe('useScopes', () => {
  it('lists scopes on mount and defaults active to global', async () => {
    const api = {
      listScopes: vi.fn().mockResolvedValue({
        scopes: [
          { id: 'global', display_name: 'Global', path_count: 5, assigned_to_role: null },
          { id: 'marketing', display_name: 'Marketing', path_count: 3, assigned_to_role: null },
        ],
      }),
    };
    const { result } = renderHook(() => useScopes('proj-1', api as any));
    await waitFor(() => expect(result.current.scopes).toHaveLength(2));
    expect(result.current.activeScopeId).toBe('global');
  });

  it('createScope appends and switches active', async () => {
    const api = {
      listScopes: vi.fn().mockResolvedValue({
        scopes: [{ id: 'global', display_name: 'Global', path_count: 0, assigned_to_role: null }],
      }),
      createScope: vi.fn().mockResolvedValue({
        id: 'marketing', display_name: 'Marketing',
        paths: [], assigned_to_role: null,
      }),
    };
    const { result } = renderHook(() => useScopes('proj-1', api as any));
    await waitFor(() => expect(result.current.scopes).toHaveLength(1));
    await act(async () => { await result.current.createScope('Marketing'); });
    expect(result.current.activeScopeId).toBe('marketing');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/prep/dashboard && npm run test -- useScopes
```

Expected: ImportError on `../useScopes`.

- [ ] **Step 3: Implement useScopes**

```typescript
// src/prep/dashboard/src/hooks/useScopes.ts
import { useState, useEffect, useCallback } from 'react';
import type { ScopeRecord, ScopeSummary, ScopesListResponse } from '@prep/ui';

export interface ScopesApi {
  listScopes(projectId: string): Promise<ScopesListResponse>;
  getScope(projectId: string, scopeId: string): Promise<ScopeRecord>;
  createScope(projectId: string, body: { display_name: string; paths?: string[]; assigned_to_role?: string | null }): Promise<ScopeRecord>;
  updateScope(projectId: string, scopeId: string, body: { display_name?: string; assigned_to_role?: string | null }): Promise<ScopeRecord>;
  deleteScope(projectId: string, scopeId: string): Promise<void>;
  addPathsToScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
  removePathsFromScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
}

export function useScopes(projectId: string | null, api: ScopesApi) {
  const [scopes, setScopes] = useState<ScopeSummary[]>([]);
  const [activeScopeId, setActiveScopeId] = useState<string>('global');

  const refresh = useCallback(async () => {
    if (!projectId) return;
    const res = await api.listScopes(projectId);
    setScopes(res.scopes);
  }, [projectId, api]);

  useEffect(() => { refresh(); }, [refresh]);

  const createScope = useCallback(async (display_name: string) => {
    if (!projectId) return null;
    const rec = await api.createScope(projectId, { display_name });
    await refresh();
    setActiveScopeId(rec.id);
    return rec;
  }, [projectId, api, refresh]);

  const renameScope = useCallback(async (id: string, display_name: string) => {
    if (!projectId) return;
    await api.updateScope(projectId, id, { display_name });
    await refresh();
  }, [projectId, api, refresh]);

  const deleteScope = useCallback(async (id: string) => {
    if (!projectId) return;
    await api.deleteScope(projectId, id);
    if (activeScopeId === id) setActiveScopeId('global');
    await refresh();
  }, [projectId, api, refresh, activeScopeId]);

  const addPaths = useCallback(async (id: string, paths: string[]) => {
    if (!projectId) return;
    await api.addPathsToScope(projectId, id, paths);
    await refresh();
  }, [projectId, api, refresh]);

  const removePaths = useCallback(async (id: string, paths: string[]) => {
    if (!projectId) return;
    await api.removePathsFromScope(projectId, id, paths);
    await refresh();
  }, [projectId, api, refresh]);

  return {
    scopes, activeScopeId, setActiveScopeId,
    createScope, renameScope, deleteScope, addPaths, removePaths,
    refresh,
  };
}
```

- [ ] **Step 4: Run tests**

```bash
cd src/prep/dashboard && npm run test -- useScopes
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/dashboard/src/hooks/useScopes.ts src/prep/dashboard/src/hooks/__tests__/useScopes.test.ts
git commit -m "feat(phase120): useScopes hook for dashboard scope management"
```

---

### Task 17: FolderTreePanel — header dropdown, + button, Edit popover

**Files:**
- Modify: `packages/ui/src/components/project/FolderTreePanel.tsx`
- Test:   `packages/ui/src/components/project/__tests__/FolderTreePanel.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// packages/ui/src/components/project/__tests__/FolderTreePanel.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FolderTreePanel } from '../FolderTreePanel';

const baseProps = {
  data: [],
  scopes: [
    { id: 'global', display_name: 'Global', path_count: 5, assigned_to_role: null },
    { id: 'marketing', display_name: 'Marketing', path_count: 3, assigned_to_role: null },
  ],
  activeScopeId: 'global',
  onSetActiveScope: vi.fn(),
  onCreateScope: vi.fn().mockResolvedValue({ id: 'data_cleaning', display_name: 'Data Cleaning', paths: [], assigned_to_role: null }),
  onRenameScope: vi.fn(),
  onDeleteScope: vi.fn(),
};

describe('FolderTreePanel', () => {
  it('renders scope dropdown with active selection', () => {
    render(<FolderTreePanel {...baseProps} />);
    expect(screen.getByRole('button', { name: /global/i })).toBeInTheDocument();
  });

  it('opens dropdown and switches active scope', () => {
    render(<FolderTreePanel {...baseProps} />);
    fireEvent.click(screen.getByRole('button', { name: /global/i }));
    fireEvent.click(screen.getByText(/marketing/i));
    expect(baseProps.onSetActiveScope).toHaveBeenCalledWith('marketing');
  });

  it('+ button opens inline create input and submits a new scope', async () => {
    render(<FolderTreePanel {...baseProps} />);
    fireEvent.click(screen.getByLabelText(/add scope/i));
    fireEvent.change(screen.getByLabelText(/scope name/i), {
      target: { value: 'Data Cleaning' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() =>
      expect(baseProps.onCreateScope).toHaveBeenCalledWith('Data Cleaning'),
    );
  });

  it('Edit affordance is hidden on global', () => {
    render(<FolderTreePanel {...baseProps} />);
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull();
  });

  it('Edit popover shows when a non-global scope is active', () => {
    render(<FolderTreePanel {...baseProps} activeScopeId="marketing" />);
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('exclude column is disabled on a non-global scope', () => {
    render(<FolderTreePanel {...baseProps} activeScopeId="marketing"
                            data={[{ name: 'src', path: 'src', children: [], type: 'folder' }]} />);
    // Tooltip text appears on the disabled exclude control
    expect(screen.getByTitle(/excludes are global/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/ui && npm run test -- FolderTreePanel
```

Expected: 6 failing.

- [ ] **Step 3: Update FolderTreePanel.tsx**

Extend `FolderTreePanelProps` with the new props (`scopes`, `activeScopeId`, `onSetActiveScope`, `onCreateScope`, `onRenameScope`, `onDeleteScope`). Render the header as:

```tsx
<div className="flex items-center gap-2 mb-3 shrink-0">
  <ScopeDropdown
    scopes={scopes}
    activeScopeId={activeScopeId}
    onSelect={onSetActiveScope}
  />
  <button
    aria-label="Add scope"
    onClick={() => setShowCreate(true)}
  >+</button>
  {activeScopeId !== 'global' && (
    <ScopeEditPopover
      scope={scopes.find(s => s.id === activeScopeId)!}
      onRename={onRenameScope}
      onDelete={onDeleteScope}
    />
  )}
</div>
{showCreate && (
  <ScopeCreateInline
    onCancel={() => setShowCreate(false)}
    onSubmit={async (name) => {
      await onCreateScope(name);
      setShowCreate(false);
    }}
  />
)}
```

Inside the tree, when `activeScopeId !== 'global'`, pass an additional `disableExclude` prop down to `FolderTree` and have it render the exclude column with `title="Excludes are global. Switch to the global scope to edit."` and `disabled` semantics.

(Implement `ScopeDropdown`, `ScopeEditPopover`, `ScopeCreateInline` as small co-located components within the same file or as siblings in `packages/ui/src/components/project/`. Each is small enough to live next to `FolderTreePanel.tsx`.)

- [ ] **Step 4: Run tests**

```bash
cd packages/ui && npm run test -- FolderTreePanel
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/project/
git commit -m "feat(phase120): FolderTreePanel scope dropdown + create/edit

Header gains a scope dropdown, + create-inline input, and an Edit
popover (rename + delete) shown only when a non-global scope is
active. Tree's exclude column is disabled on non-global scopes with
a tooltip pointing back to global."
```

---

### Task 18: Wire useScopes into useDashboardPanels and delete AgentScopePanel

**Files:**
- Modify: `src/prep/dashboard/src/hooks/useDashboardPanels.tsx`
- Delete: `packages/ui/src/components/agents/AgentScopePanel.tsx`
- Delete: `packages/ui/src/stories/agents/AgentScopePanel.stories.tsx`
- Modify: `packages/ui/src/components/agents/index.ts` (drop export)
- Modify: `packages/ui/src/index.ts` (drop export)

- [ ] **Step 1: Update useDashboardPanels.tsx**

In `src/prep/dashboard/src/hooks/useDashboardPanels.tsx`:

1. Remove the `AgentScopePanel` import.
2. Add `import { useScopes } from './useScopes';` and call it: `const scopes = useScopes(p.selectedProjectId, api);`.
3. In the `'file-tree'` slot (around line 843), replace the props with the new scope-aware ones:

```tsx
'file-tree': (
  <FolderTreePanel
    data={p.fileTree}
    includedPaths={p.includedPaths}
    scopeStatus={p.scopeStatus}
    onToggleInclude={(paths, action) => {
      if (scopes.activeScopeId === 'global') {
        p.handleToggleInclude(paths, action);
      } else {
        if (action === 'add') scopes.addPaths(scopes.activeScopeId, paths);
        else scopes.removePaths(scopes.activeScopeId, paths);
      }
    }}
    pathWeights={p.pathWeights}
    onWeightChange={p.handlePathWeightChange}
    excludedPaths={excludedPaths}
    onToggleExclude={handleToggleExclude}
    alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_GLOBS}
    onLoadChildren={p.handleLoadChildren}
    title="Scope"
    bare
    scopes={scopes.scopes}
    activeScopeId={scopes.activeScopeId}
    onSetActiveScope={scopes.setActiveScopeId}
    onCreateScope={scopes.createScope}
    onRenameScope={scopes.renameScope}
    onDeleteScope={scopes.deleteScope}
  />
),
```

4. Delete the entire `'agent-scope':` slot (around lines 873-905).

- [ ] **Step 2: Delete the agents panel files**

```bash
rm packages/ui/src/components/agents/AgentScopePanel.tsx
rm packages/ui/src/stories/agents/AgentScopePanel.stories.tsx
```

- [ ] **Step 3: Drop the exports**

In `packages/ui/src/components/agents/index.ts`, remove the `AgentScopePanel` line. In `packages/ui/src/index.ts:171-172`, remove `AgentScopePanel`, `AgentScopePanelProps`, `AutoPopulateResult` from the export lists.

- [ ] **Step 4: Build and typecheck**

```bash
cd packages/ui && npm run typecheck
cd src/prep/dashboard && npm run typecheck
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat(phase120): wire useScopes into dashboard, delete AgentScopePanel

The Scope panel (FolderTreePanel) is now the only scope UI. The old
agent-scope dashboard slot, AgentScopePanel.tsx, and its stories are
deleted. Path-toggle clicks route through useScopes when a non-global
scope is active."
```

---

### Task 19: Storybook stories for FolderTreePanel

**Files:**
- Modify: `packages/ui/src/stories/project/FolderTree.stories.tsx`

- [ ] **Step 1: Append five new stories**

```typescript
// packages/ui/src/stories/project/FolderTree.stories.tsx — append
export const ScopePanelGlobal: Story = {
  render: () => (
    <FolderTreePanel
      data={SAMPLE_TREE}
      includedPaths={new Set(['src/'])}
      scopes={[
        { id: 'global', display_name: 'Global', path_count: 247, assigned_to_role: null },
        { id: 'marketing', display_name: 'Marketing', path_count: 12, assigned_to_role: null },
      ]}
      activeScopeId="global"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({ id: 'new', display_name: 'New', paths: [], assigned_to_role: null })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
    />
  ),
};

export const ScopePanelNamedPopulated: Story = {
  render: () => (
    <FolderTreePanel
      data={SAMPLE_TREE}
      includedPaths={new Set(['websites/marketing/'])}
      scopes={[
        { id: 'global', display_name: 'Global', path_count: 247, assigned_to_role: null },
        { id: 'marketing', display_name: 'Marketing', path_count: 12, assigned_to_role: null },
      ]}
      activeScopeId="marketing"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({ id: 'new', display_name: 'New', paths: [], assigned_to_role: null })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
    />
  ),
};

export const ScopePanelEmpty: Story = {
  render: () => (
    <FolderTreePanel
      data={SAMPLE_TREE}
      includedPaths={new Set()}
      scopes={[
        { id: 'global', display_name: 'Global', path_count: 247, assigned_to_role: null },
        { id: 'data_cleaning', display_name: 'Data Cleaning', path_count: 0, assigned_to_role: null },
      ]}
      activeScopeId="data_cleaning"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({ id: 'new', display_name: 'New', paths: [], assigned_to_role: null })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
    />
  ),
};

export const ScopePanelCreateInputOpen: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <FolderTreePanel
        data={SAMPLE_TREE}
        scopes={[{ id: 'global', display_name: 'Global', path_count: 247, assigned_to_role: null }]}
        activeScopeId="global"
        onSetActiveScope={() => {}}
        onCreateScope={async (name) => { setOpen(false); return { id: name.toLowerCase(), display_name: name, paths: [], assigned_to_role: null }; }}
        onRenameScope={async () => {}}
        onDeleteScope={async () => {}}
        onToggleInclude={() => {}}
        // Force the inline create input to be visible:
        defaultShowCreate={open}
      />
    );
  },
};

export const ScopePanelExcludeDisabled: Story = {
  render: () => (
    <FolderTreePanel
      data={SAMPLE_TREE}
      excludedPaths={new Set(['vendor/'])}
      scopes={[
        { id: 'global', display_name: 'Global', path_count: 247, assigned_to_role: null },
        { id: 'marketing', display_name: 'Marketing', path_count: 12, assigned_to_role: null },
      ]}
      activeScopeId="marketing"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({ id: 'new', display_name: 'New', paths: [], assigned_to_role: null })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
    />
  ),
};
```

(`SAMPLE_TREE` should already exist in the same stories file. If not, copy from a sibling story.)

- [ ] **Step 2: Run Storybook**

```bash
cd packages/ui && npm run storybook
```

Open `http://localhost:6006`, find the new stories under `Project / FolderTree`, confirm each renders without console errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/stories/project/FolderTree.stories.tsx
git commit -m "feat(phase120): Storybook stories for scoped FolderTreePanel"
```

---

## Final verification gate

After Task 19, run all gates from the spec's Verification gates section:

```bash
.venv/bin/ruff check src/
.venv/bin/mypy src/
.venv/bin/pytest tests/ -v
cd packages/ui && npm run typecheck && npm run lint && npm run test
cd src/prep/dashboard && npm run typecheck
```

Then run the full manual golden path in `docs/Phase120_NamedScopes/README.md` under "Verification gates → Manual dev-server golden path."

```bash
scripts/dev.sh
# In another terminal: open http://localhost:5174, exercise each step.
```

Once all gates pass, open a PR with the title:

```
feat(phase120): Named Scopes — universal RAG file masks
```

Body: paste the spec's Motivation section verbatim plus a checklist of the 19 task commits.

---

## Self-review

**Spec coverage** — every section in the spec maps to at least one task:
- Core architecture / disjointness / virtual default → Task 5 (synthesize_global) + Task 7 (membership)
- Index-membership integration → Task 2 + Task 7
- Add/remove/delete semantics → Task 6
- Scope record / data model → Task 1
- HTTP API → Tasks 5–6
- MCP signature & resolution → Tasks 11–12
- Response envelope → Task 12
- Ambient prep() filtering → Task 12
- AGENTS.md generation → Task 13
- UI (dropdown, +, Edit, tree behavior) → Tasks 14–18
- Storybook → Task 19
- Phase 67 deletion (manager, router, panel) → Tasks 9–10, 18
- Verification gates → Final section

**Placeholder scan** — every step contains code, an exact command, or both. No "TODO," "TBD," "appropriate," or "similar to" wording.

**Type consistency** — `ScopeRecord`, `ScopeSummary`, `MaskResolution`, `ScopesApi`, `applied_scope`/`applied_role`/`scope_warning` envelope keys are spelled identically across Tasks 1, 3, 5, 8, 12, 14, 15, 16. Method names (`createScope`, `renameScope`, `deleteScope`, `addPaths`, `removePaths`, `setActiveScopeId`) match between hook (Task 16), panel props (Task 17), and dashboard wiring (Task 18).

**Risks intentionally out of v1** are listed in the spec's "Future work / deferred" section and are NOT covered by tasks here:
- Per-scope path weights (Future work #1)
- Multi-scope per request (Future work #2)
- Auto-populate via role projection (Future work #3)
- localStorage persistence of activeScopeId (Future work #4)
- Per-scope freshness/build status (Future work #5)
- Per-scope concept pins (Future work #6)
- `prep_audit(scope=…)` harmonization (Risks/watchpoints note)

If any of those become required during implementation, escalate before adding tasks — they materially expand the phase.
