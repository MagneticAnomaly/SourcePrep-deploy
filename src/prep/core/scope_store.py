from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

GLOBAL_SCOPE_ID = "global"
_SCOPE_KEY_PREFIX = "scope"
_MAX_SLUG_SUFFIX = 99
_UNSET: object = object()

# Built-in pipeline profile names selectable per scope. The stage matrices
# themselves live in ``core/pipeline_profiles``; this set is the validation
# surface so the store rejects unknown names at write time.
KNOWN_PIPELINE_PROFILES = frozenset({"code", "prose_docs", "system_config"})


@dataclass
class ScopeRecord:
    id: str
    display_name: str
    paths: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)  # reserved for v1.1
    assigned_to_role: str | None = None
    # Named pipeline stage matrix (see ``core/pipeline_profiles``). ``code``
    # is the default and matches today's behavior, so existing serialized
    # records without the field keep all stages enabled.
    pipeline_profile: str = "code"
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
            pipeline_profile=str(d.get("pipeline_profile") or "code"),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )


class ScopeStore:
    """CRUD for named scope records, persisted in the per-project
    settings_store under the ``scope.<scope_id>`` namespace.

    **Concurrency caveat (v1):** ``create()`` and ``update()`` perform
    a non-atomic read-modify-write — they call ``list()`` to enforce
    slug-uniqueness and ``assigned_to_role``-uniqueness, then ``_write()``
    the new record. Two concurrent calls from independent FastAPI
    workers can race past these checks. The dashboard is a single
    human writer in practice, so the impact is bounded; if scope
    mutations ever come from automated/parallel callers, replace the
    relevant helpers with a registry-style ``mutate_config`` RMW
    (see Phase 24's ``mutate_global_scope`` for the pattern).
    """

    def get(self, project_id: str, scope_id: str) -> ScopeRecord | None:
        from prep.services.settings_store import settings

        raw = settings.project_get(project_id, f"{_SCOPE_KEY_PREFIX}.{scope_id}")
        if not isinstance(raw, dict):
            return None
        return ScopeRecord.from_dict(raw)

    def list(self, project_id: str) -> list[ScopeRecord]:
        from prep.services.settings_store import settings

        all_settings = settings.project_get_all(project_id)
        prefix = f"{_SCOPE_KEY_PREFIX}."
        out: list[ScopeRecord] = []
        for key, value in all_settings.items():
            if key.startswith(prefix) and isinstance(value, dict):
                out.append(ScopeRecord.from_dict(value))
        return sorted(out, key=lambda r: r.id)

    def create(
        self,
        project_id: str,
        display_name: str,
        paths: list[str] | None = None,  # type: ignore[valid-type]  # mypy: ScopeStore.list shadows builtin
        assigned_to_role: str | None = None,
        pipeline_profile: str = "code",
    ) -> ScopeRecord:
        slug = _slugify(display_name)
        if slug == GLOBAL_SCOPE_ID:
            raise ValueError(f"scope id '{GLOBAL_SCOPE_ID}' is reserved")
        _validate_pipeline_profile(pipeline_profile)
        scope_id = self._allocate_unique_id(project_id, slug)
        if assigned_to_role:
            self._check_role_unique(project_id, assigned_to_role, exclude_id=None)
        now = _iso_now()
        rec = ScopeRecord(
            id=scope_id,
            display_name=display_name,
            paths=sorted(set(paths or [])),
            assigned_to_role=assigned_to_role,
            pipeline_profile=pipeline_profile,
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
        assigned_to_role: Any = _UNSET,
        pipeline_profile: Any = _UNSET,
    ) -> ScopeRecord:
        """Update a scope's metadata.

        Pass ``assigned_to_role=None`` to clear an existing assignment.
        Omit (default) to leave it unchanged. Pass a string to set/replace.

        ``pipeline_profile`` follows the same convention: omit to leave
        unchanged, pass a known profile name to set it. Unknown names raise
        ``ValueError`` (surfaced as 409 SCOPE_INVALID by the API).
        """
        rec = self.get(project_id, scope_id)
        if rec is None:
            raise KeyError(scope_id)
        if assigned_to_role is not _UNSET and assigned_to_role != rec.assigned_to_role:
            if assigned_to_role:
                self._check_role_unique(project_id, assigned_to_role, exclude_id=scope_id)
            rec.assigned_to_role = assigned_to_role or None
        if pipeline_profile is not _UNSET and pipeline_profile != rec.pipeline_profile:
            _validate_pipeline_profile(pipeline_profile)
            rec.pipeline_profile = pipeline_profile
        if display_name is not None:
            rec.display_name = display_name
        rec.updated_at = _iso_now()
        self._write(project_id, rec)
        return rec

    def set_paths(self, project_id: str, scope_id: str, paths: list[str]) -> ScopeRecord:  # type: ignore[valid-type]  # mypy: ScopeStore.list shadows builtin
        rec = self.get(project_id, scope_id)
        if rec is None:
            raise KeyError(scope_id)
        rec.paths = sorted({p for p in paths if p})  # type: ignore[attr-defined]
        rec.updated_at = _iso_now()
        self._write(project_id, rec)
        return rec

    def delete(self, project_id: str, scope_id: str) -> bool:
        """Delete a scope. Returns True if it existed, False otherwise."""
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


def _validate_pipeline_profile(profile: Any) -> None:
    """Raise ``ValueError`` for an unknown pipeline profile name.

    ``None`` falls back to the ``code`` default rather than raising — callers
    that treat the field as optional pass ``None`` from the API layer.
    """
    if profile is None:
        return
    if not isinstance(profile, str) or profile not in KNOWN_PIPELINE_PROFILES:
        raise ValueError(
            f"unknown pipeline_profile {profile!r}; "
            f"expected one of {sorted(KNOWN_PIPELINE_PROFILES)}"
        )


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_") or "scope"


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Module-level singleton
scope_store = ScopeStore()
