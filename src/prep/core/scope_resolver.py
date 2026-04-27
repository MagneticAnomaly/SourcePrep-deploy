from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaskResolution:
    """Result of resolving a (scope, role) request to a file mask.

    - mask is None means "no filtering" (full RAG over included_paths union).
    - applied_scope is always a string for the response envelope; "global" when
      no per-scope mask is in effect.
    - warning is set when the requested scope was not found and we fell back
      to global.
    """

    mask: set[str] | None
    applied_scope: str
    warning: str | None = None


def resolve_mask(
    project_id: str,
    scope: str | None,
    role: str | None,
) -> MaskResolution:
    """Resolve (scope, role) to a file-mask + applied-scope label.

    Resolution rules (in order):
    1. If ``scope=X`` is passed and scope.<X> exists → mask = its paths.
    2. Else if ``scope=X`` is passed but no such scope exists → mask = None
       (global), warning carries the unknown name.
    3. Else if ``role=Y`` is passed AND a scope has assigned_to_role == Y →
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


def path_matches_any_scope(file_path: str, scope_paths: set[str]) -> bool:
    """Check if ``file_path`` is covered by any path in ``scope_paths``.

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
