"""
Role Overrides Store — Phase 104 (Sub-Atlas & Role Lens)
=========================================================

Per-project, per-role overrides applied on top of built-in ``RoleVector``
defaults when an agent calls ``codrag(role=...)``.

**What is overridable in v1:**
  - ``max_chars``: override the char budget for the projected sub-atlas.
  - ``pinned_concept_ids``: concept IDs pinned to the role, prepended
    to the projection output as an additive context block.

**Design choice (optimization over the original plan):**
  The original Phase 104 plan called for two dedicated SQLite tables
  (``role_overrides`` and ``concept_role_pins``). That would require a
  schema migration. Instead we reuse the existing ``settings_store``'s
  per-project key/value namespace, which is already WAL-safe, tested, and
  lives in the same ``codrag_settings.db`` file. Two namespaced keys:

    ``project/<pid>/role_overrides/<role_id>``  → override dict
    ``project/<pid>/role_pins/<role_id>``       → {concept_id: pinned_at}

  This keeps the store at zero new tables and trivial to reason about.
  Listing overrides for a project is a namespace scan with a prefix filter.

**Usage:**
  ``from prep.services.role_overrides_store import role_overrides_store``
  ``role_overrides_store.upsert(pid, "engineering", max_chars=3500)``
  ``role_overrides_store.get(pid, "engineering")``
  ``role_overrides_store.pin_concept(pid, "engineering", concept_id)``
  ``role_overrides_store.list_pinned_concepts(pid, "engineering")``
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

# Key prefixes inside the per-project namespace of settings_store.
_OVERRIDE_KEY_PREFIX = "role_overrides/"
_PINS_KEY_PREFIX = "role_pins/"


@dataclass
class RoleOverride:
    """A per-role override layered on top of the built-in RoleVector.

    All fields except ``role_id`` are optional — an override is additive:
    unset fields fall through to the built-in RoleVector defaults.
    """
    role_id: str
    max_chars: int | None = None
    pinned_concept_ids: list[str] = field(default_factory=list)
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, role_id: str, d: dict) -> RoleOverride:
        return cls(
            role_id=role_id,
            max_chars=d.get("max_chars"),
            pinned_concept_ids=list(d.get("pinned_concept_ids", [])),
            updated_at=float(d.get("updated_at", 0.0)),
        )

    def is_empty(self) -> bool:
        """True when the override has no meaningful content (everything None/empty)."""
        return self.max_chars is None and not self.pinned_concept_ids


class RoleOverridesStore:
    """Thin wrapper over settings_store for role overrides + concept pins."""

    def __init__(self, settings=None):
        # Lazy import so test harnesses can inject a fake settings store
        # without importing the real one's sqlite init chain.
        self._settings = settings

    def _store(self):
        if self._settings is not None:
            return self._settings
        from prep.services.settings_store import settings
        return settings

    # ── Role override CRUD ───────────────────────────────────────────

    def get(self, project_id: str, role_id: str) -> RoleOverride | None:
        """Return the override for a role, or None if none is set."""
        raw = self._store().project_get(
            project_id, f"{_OVERRIDE_KEY_PREFIX}{role_id}"
        )
        if raw is None:
            return None
        if not isinstance(raw, dict):
            logger.warning(
                "Role override for %s/%s is not a dict; ignoring", project_id, role_id
            )
            return None
        ov = RoleOverride.from_dict(role_id, raw)
        # Pinned concepts live in a separate key so the override write path
        # doesn't have to re-read them. Merge them in for read callers.
        ov.pinned_concept_ids = self.list_pinned_concepts(project_id, role_id)
        return ov

    def list(self, project_id: str) -> list[RoleOverride]:
        """Return all overrides + pins merged into RoleOverride objects."""
        all_settings = self._store().project_get_all(project_id) or {}
        out: dict[str, RoleOverride] = {}
        for key, value in all_settings.items():
            if key.startswith(_OVERRIDE_KEY_PREFIX) and isinstance(value, dict):
                role_id = key[len(_OVERRIDE_KEY_PREFIX):]
                out[role_id] = RoleOverride.from_dict(role_id, value)
        # Now merge in pins. A role with only pins (no max_chars) still
        # deserves an entry so the UI can display it.
        for key, value in all_settings.items():
            if key.startswith(_PINS_KEY_PREFIX) and isinstance(value, dict):
                role_id = key[len(_PINS_KEY_PREFIX):]
                pinned_ids = list(value.keys())
                if role_id in out:
                    out[role_id].pinned_concept_ids = pinned_ids
                elif pinned_ids:
                    out[role_id] = RoleOverride(
                        role_id=role_id,
                        pinned_concept_ids=pinned_ids,
                    )
        return list(out.values())

    def upsert(
        self,
        project_id: str,
        role_id: str,
        *,
        max_chars: int | None = None,
    ) -> RoleOverride:
        """Upsert override fields. Returns the resulting override.

        Only the fields passed in are written; others are preserved. To clear
        a field, pass ``None`` explicitly (which is the default, so callers
        must pass the value to set it).

        ``pinned_concept_ids`` is NOT set via this method — use
        ``pin_concept`` / ``unpin_concept``.
        """
        existing = self._store().project_get(
            project_id, f"{_OVERRIDE_KEY_PREFIX}{role_id}"
        ) or {}
        now = time.time()
        merged = dict(existing)
        if max_chars is not None:
            merged["max_chars"] = int(max_chars)
        merged["updated_at"] = now
        self._store().project_set(
            project_id, f"{_OVERRIDE_KEY_PREFIX}{role_id}", merged
        )
        # Re-read through get() so the returned object has merged pins.
        result = self.get(project_id, role_id)
        assert result is not None
        return result

    def delete(self, project_id: str, role_id: str) -> bool:
        """Delete the override AND any pinned concepts for the role.

        Returns True if anything was deleted.
        """
        override_deleted = self._store().project_delete(
            project_id, f"{_OVERRIDE_KEY_PREFIX}{role_id}"
        )
        pins_deleted = self._store().project_delete(
            project_id, f"{_PINS_KEY_PREFIX}{role_id}"
        )
        return bool(override_deleted or pins_deleted)

    # ── Concept pinning ──────────────────────────────────────────────

    def pin_concept(
        self, project_id: str, role_id: str, concept_id: str
    ) -> list[str]:
        """Pin a concept to a role. Returns the resulting pinned-id list.

        Pins are stored as a map {concept_id: pinned_at} for O(1) lookup
        on unpin and stable iteration order on projection.
        """
        existing = self._store().project_get(
            project_id, f"{_PINS_KEY_PREFIX}{role_id}"
        ) or {}
        if not isinstance(existing, dict):
            existing = {}
        existing[concept_id] = time.time()
        self._store().project_set(
            project_id, f"{_PINS_KEY_PREFIX}{role_id}", existing
        )
        return list(existing.keys())

    def unpin_concept(
        self, project_id: str, role_id: str, concept_id: str
    ) -> list[str]:
        """Unpin a concept. Returns the resulting pinned-id list."""
        existing = self._store().project_get(
            project_id, f"{_PINS_KEY_PREFIX}{role_id}"
        ) or {}
        if not isinstance(existing, dict):
            existing = {}
        existing.pop(concept_id, None)
        if existing:
            self._store().project_set(
                project_id, f"{_PINS_KEY_PREFIX}{role_id}", existing
            )
        else:
            # Keep the store tidy when the last pin goes away.
            self._store().project_delete(
                project_id, f"{_PINS_KEY_PREFIX}{role_id}"
            )
        return list(existing.keys())

    def list_pinned_concepts(self, project_id: str, role_id: str) -> list[str]:
        """Return pinned concept IDs for a role in insertion-time order."""
        raw = self._store().project_get(
            project_id, f"{_PINS_KEY_PREFIX}{role_id}"
        )
        if not isinstance(raw, dict):
            return []
        # Sort by pinned_at timestamp ascending for deterministic projection
        # output when budgets force truncation.
        items = sorted(raw.items(), key=lambda kv: float(kv[1] or 0.0))
        return [cid for cid, _ in items]

    def list_roles_pinning_concept(
        self, project_id: str, concept_id: str
    ) -> list[str]:
        """Return role_ids that currently pin ``concept_id``.

        Reverse of ``list_pinned_concepts``. Used by the concepts panel
        to show which roles use a given concept (Phase 104 — concept
        badges on the concepts list).
        """
        all_settings = self._store().project_get_all(project_id) or {}
        out: list[str] = []
        for key, value in all_settings.items():
            if not key.startswith(_PINS_KEY_PREFIX):
                continue
            if not isinstance(value, dict):
                continue
            if concept_id in value:
                out.append(key[len(_PINS_KEY_PREFIX):])
        return sorted(out)

    def unpin_concept_from_all_roles(
        self, project_id: str, concept_id: str
    ) -> int:
        """Remove ``concept_id`` from every role's pin map.

        Used when a concept is deleted so stale IDs don't linger. Returns
        the number of roles that were mutated.
        """
        all_settings = self._store().project_get_all(project_id) or {}
        mutated = 0
        for key, value in list(all_settings.items()):
            if not key.startswith(_PINS_KEY_PREFIX):
                continue
            if not isinstance(value, dict) or concept_id not in value:
                continue
            value = dict(value)  # copy before mutating
            del value[concept_id]
            if value:
                self._store().project_set(project_id, key, value)
            else:
                self._store().project_delete(project_id, key)
            mutated += 1
        return mutated


# Module-level singleton — tests inject a fake via constructor arg.
role_overrides_store = RoleOverridesStore()
