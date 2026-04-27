from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, List  # noqa: UP035

GLOBAL_SCOPE_ID = "global"
_SCOPE_KEY_PREFIX = "scope"
_MAX_SLUG_SUFFIX = 99


@dataclass
class ScopeRecord:
    id: str
    display_name: str
    paths: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)  # reserved for v1.1
    assigned_to_role: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScopeRecord:
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
    def get(self, project_id: str, scope_id: str) -> ScopeRecord | None:
        from prep.services.settings_store import settings

        raw = settings.project_get(project_id, f"{_SCOPE_KEY_PREFIX}.{scope_id}")
        if not isinstance(raw, dict):
            return None
        return ScopeRecord.from_dict(raw)

    def list(self, project_id: str) -> List[ScopeRecord]:  # noqa: UP006
        from prep.services.settings_store import settings

        all_settings = settings.project_get_all(project_id)
        prefix = f"{_SCOPE_KEY_PREFIX}."
        out: List[ScopeRecord] = []  # noqa: UP006
        for key, value in all_settings.items():
            if key.startswith(prefix) and isinstance(value, dict):
                out.append(ScopeRecord.from_dict(value))
        return sorted(out, key=lambda r: r.id)

    def create(
        self,
        project_id: str,
        display_name: str,
        paths: List[str] | None = None,  # noqa: UP006
        assigned_to_role: str | None = None,
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
        display_name: str | None = None,
        assigned_to_role: str | None = None,
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

    def set_paths(self, project_id: str, scope_id: str, paths: List[str]) -> ScopeRecord:  # noqa: UP006
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
        self, project_id: str, role: str, exclude_id: str | None
    ) -> None:
        for rec in self.list(project_id):
            if rec.id == exclude_id:
                continue
            if rec.assigned_to_role == role:
                raise ValueError(f"role '{role}' already assigned to scope '{rec.id}'")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_") or "scope"


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Module-level singleton
scope_store = ScopeStore()
