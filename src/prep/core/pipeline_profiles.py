"""Per-scope pipeline profiles + the profile gate.

A *pipeline profile* is a named stage matrix: a map of stage-id → enabled
flag for the LLM/embed stages that can be selectively skipped per content
type. Rust/embed stages (structural, validation, knowledge, deep_knowledge)
are never gated and therefore never appear in any matrix — an absent key
means "enabled", which is also the rule for the ``code`` profile (empty
matrix = everything on, i.e. today's behavior).

Profiles are a built-in SourcePrep concept (not a Halbert template detail)
so any app can reuse them. A scope carries its profile name on
``ScopeRecord.pipeline_profile`` (``core/scope_store``); the matrix lookup
happens here.

Three enforcement points consult this module:

* **Per-file gate** — the 5 per-file stages (inferred_edges, catalogue,
  enrichment, deepening, deep_knowledge) call ``ProfileGate.allows(fp)``
  inside their worker skip checks (T-S1.3).
* **Per-stage skip** — orchestrator-level ``disabled_stages`` config turns a
  stage off project-wide (T-S1.5); orthogonal to profiles.
* **Input-set filter** — group_reasoning drops profile-rejected files from
  its epistemic input set (T-S1.6).

Resolution is layered (scrutiny Risk 4):

1. Explicit scope membership → that scope's ``pipeline_profile``.
   Overlapping scopes resolve by most-specific path prefix; ties break to
   the lowest scope id (deterministic). A file matching scopes with
   differing profiles logs a warning.
2. Per-file content-type detection — ONLY when the project opts in via
   ``auto_profile_files: true`` (off by default, preserving back-compat for
   existing repos where markdown is project docs). The sole v1 rule is
   ``*.md`` → ``prose_docs``. This layer ships dormant.
3. ``code`` default — files matching no scope and no auto rule get ``code``.

Files that resolve to a profile whose matrix disables the queried stage are
rejected by ``allows()``. Everything else (including all unscoped files and
the never-gated Rust/embed stages) is allowed, so projects without any
profiled scopes are byte-identical to today.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable

from prep.core.scope_resolver import path_matches_any_scope
from prep.core.scope_store import scope_store

if TYPE_CHECKING:
    from prep.services.pipeline.stages import StageId

logger = logging.getLogger(__name__)

# Stage matrices. Keys are StageId *values* (the lowercase string). An empty
# matrix means "all stages enabled" (the ``code`` profile). Rust/embed stages
# (structural, validation, knowledge, deep_knowledge) are intentionally
# absent from every matrix — they always run.
PIPELINE_PROFILES: dict[str, dict[str, bool]] = {
    "code": {},  # today's behavior: every stage enabled
    "prose_docs": {
        "inferred_edges": False,
        "catalogue": True,
        "enrichment": False,
        "group_reasoning": False,
        "clustering": True,
        "deepening": False,
        "atlas": True,
        "rules": False,
        "concepts": False,
        "audit": False,
        "antibodies": False,
    },
    "system_config": {
        "inferred_edges": False,
        "catalogue": True,
        "enrichment": True,
        "group_reasoning": True,
        "clustering": True,
        "deepening": False,
        "atlas": True,
        "rules": False,
        "concepts": False,
        "audit": False,
        "antibodies": False,
    },
}

# Stages that gate per-file (the five that consult ProfileGate.allows). The
# other LLM stages operate per-group / per-graph / per-module and are gated
# by the orchestrator skip (T-S1.5) or input-set filter (T-S1.6), not here.
PER_FILE_STAGES: frozenset[str] = frozenset(
    {
        "inferred_edges",
        "catalogue",
        "enrichment",
        "deepening",
        "deep_knowledge",
    }
)

# Rust/embed stages that are never gated by profiles. Note: ``deep_knowledge``
# (stage 10) is a per-file-gated stage — it re-embeds with enriched data and
# carries a ProfileGate consult point (T-S1.3) — so it is NOT here; the built-in
# matrices simply never disable it (absent key → enabled), so it runs for both
# profiles, matching design-doc §2.3.
NEVER_GATED_STAGES: frozenset[str] = frozenset({"structural", "validation", "knowledge"})

_DEFAULT_PROFILE = "code"
_MARKDOWN_SUFFIXES = (".md", ".markdown")


def _stage_value(stage: "StageId | str") -> str:
    """Normalize a StageId (or raw stage-id string) to its lowercase value."""
    return stage.value if hasattr(stage, "value") else str(stage)


def profile_allows_stage(profile: str, stage: "StageId | str") -> bool:
    """True if *profile* enables *stage*.

    An absent stage key (every Rust/embed stage, and every stage under the
    ``code`` profile's empty matrix) means enabled. Only an explicit
    ``False`` entry disables the stage.
    """
    matrix = PIPELINE_PROFILES.get(profile)
    if not matrix:
        return True  # unknown profile or empty ``code`` matrix → enabled
    return bool(matrix.get(_stage_value(stage), True))


def _covering_scope_paths(scope_paths: Iterable[str], file_path: str) -> list[str]:
    """Return the scope paths that cover *file_path*, longest-first."""
    hits = [sp for sp in scope_paths if path_matches_any_scope(file_path, {sp})]
    # Longest path = most-specific prefix. Sort stable by length descending.
    hits.sort(key=lambda sp: len(sp), reverse=True)
    return hits


def _is_markdown(file_path: str) -> bool:
    return file_path.lower().endswith(_MARKDOWN_SUFFIXES)


class ProfileGate:
    """Per-stage gate answering "should *stage* run on *file_path*?".

    One gate is constructed per worker (T-S1.3 injects it parallel to the
    changeset). The scope list is loaded once per instance and cached, so a
    worker iterating thousands of files pays the settings-store read once.
    """

    def __init__(self, project_id: str, stage: "StageId | str") -> None:
        self.project_id = project_id
        self.stage_value = _stage_value(stage)
        # Loaded lazily so a gate constructed but never consulted (the
        # non-per-file stages carry one harmlessly per T-S1.3) pays nothing.
        self._scopes: list | None = None
        self._auto_profile_files: bool | None = None

    # ── scope / config loading ────────────────────────────────────
    def _load_scopes(self) -> list:
        if self._scopes is None:
            try:
                self._scopes = scope_store.list(self.project_id)
            except Exception:  # pragma: no cover - never let the gate raise
                logger.debug(
                    "ProfileGate: scope load failed for %s", self.project_id, exc_info=True
                )
                self._scopes = []
        return self._scopes

    def _auto_profile_enabled(self) -> bool:
        if self._auto_profile_files is None:
            self._auto_profile_files = False
            try:
                from prep.services.project_helpers import require_project

                proj = require_project(self.project_id)
                cfg = proj.config if isinstance(proj.config, dict) else {}
                self._auto_profile_files = bool(cfg.get("auto_profile_files", False))
            except Exception:  # pragma: no cover - keep the gate non-fatal
                logger.debug(
                    "ProfileGate: project config load failed for %s",
                    self.project_id,
                    exc_info=True,
                )
        return self._auto_profile_files

    # ── resolution ────────────────────────────────────────────────
    def profile_for_path(self, file_path: str) -> str:
        """Resolve the effective profile name for *file_path*.

        Layered: explicit scope membership (most-specific-prefix-wins,
        tie→lowest scope id) → opt-in markdown auto-rule → ``code`` default.
        """
        scopes = self._load_scopes()
        if scopes:
            best = self._resolve_overlapping_scope(file_path, scopes)
            if best is not None:
                return best.pipeline_profile

        # Layer 2: per-file content-type detection, opt-in only.
        if self._auto_profile_enabled() and _is_markdown(file_path):
            return "prose_docs"

        return _DEFAULT_PROFILE

    @staticmethod
    def _resolve_overlapping_scope(file_path: str, scopes: list):
        """Pick the single scope whose profile governs *file_path*.

        Most-specific path prefix wins (deepest covering path); ties break
        to the lowest scope id (deterministic). Logs a warning when a file
        matches several scopes carrying different profiles.
        """
        candidates = []
        for scope in scopes:
            hits = _covering_scope_paths(scope.paths, file_path)
            if hits:
                # specificity = length of the longest covering path for this scope
                candidates.append((len(hits[0]), scope.id, scope))

        if not candidates:
            return None

        # Distinct profiles across candidates → overlap with divergence.
        profiles = {c[2].pipeline_profile for c in candidates}
        if len(profiles) > 1:
            logger.warning(
                "ProfileGate: %s matches scopes with differing profiles %s; "
                "most-specific-prefix (tie→lowest id) resolves to %s",
                file_path,
                sorted(profiles),
                sorted(candidates, key=lambda c: (-c[0], c[1]))[0][2].pipeline_profile,
            )

        # most-specific first, then lowest scope id
        candidates.sort(key=lambda c: (-c[0], c[1]))
        return candidates[0][2]

    # ── the gate answer ────────────────────────────────────────────
    def allows(self, file_path: str) -> bool:
        """True if this gate's stage should process *file_path*."""
        # Never-gated stages always run (defensive; the per-file stages are
        # the only ones that construct a consulting gate, but a gate built
        # for a Rust/embed stage must answer True regardless).
        if self.stage_value in NEVER_GATED_STAGES:
            return True
        profile = self.profile_for_path(file_path)
        return profile_allows_stage(profile, self.stage_value)


def profile_for_path(project_id: str, file_path: str, *, gate: ProfileGate | None = None) -> str:
    """Module-level convenience: resolve the profile for *file_path*.

    Callers in a hot loop should hold a ``ProfileGate`` and call its
    ``profile_for_path`` to avoid re-reading the scope list per file; this
    helper builds a throwaway ``code``-stage gate when one is not supplied
    (the stage is irrelevant — only scope/auto resolution matters here, and
    those are stage-independent).
    """
    if gate is None:
        gate = ProfileGate(project_id, "code")
    return gate.profile_for_path(file_path)