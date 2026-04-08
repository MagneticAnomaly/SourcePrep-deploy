"""Staffing Agent Engine — generates AI agent role definitions from codebase analysis.

Orchestrates readiness scoring, role generation (list/auto/hybrid modes),
and roster persistence. Uses AgentCore for CoDRAG data access when available.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from codrag.agents.hr.prompts import (
    AGENTS_MD_SYSTEM,
    AUTO_ROLES_SYSTEM,
    SOUL_MD_SYSTEM,
    render_agents_md_prompt,
    render_auto_roles_prompt,
    render_knowledge_md,
    render_soul_md_prompt,
)
from codrag.agents.hr.readiness import ReadinessReport, compute_readiness
from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec, _normalize_slug

logger = logging.getLogger(__name__)

# Type alias for injectable LLM function
LLMFn = Callable[..., Tuple[str, int]]


@dataclass
class RoleFitness:
    """Fitness assessment for a single role."""

    slug: str
    display_name: str
    fitness_score: float  # 0.0-1.0
    recommendation: str  # healthy | minor_drift | significant_drift | critical
    details: str = ""

    @staticmethod
    def classify(score: float) -> str:
        if score > 0.8:
            return "healthy"
        if score > 0.6:
            return "minor_drift"
        if score > 0.4:
            return "significant_drift"
        return "critical"


@dataclass
class DriftReport:
    """Result of roster drift analysis."""

    role_fitness: List[RoleFitness] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    overlap_warnings: List[str] = field(default_factory=list)


class StaffingEngine:
    """Generates and manages AI agent role definitions.

    Accepts either an ``AgentCore`` instance (preferred — provides data access
    through the Phase 0 facade) or raw ``index_dir`` + ``project_id`` for
    lightweight / test usage.

    Args:
        core: AgentCore instance. When provided, ``index_dir`` and ``project_id``
            are derived from it.
        index_dir: Path to the CoDRAG index directory. Used when ``core`` is None.
        project_id: CoDRAG project identifier. Used when ``core`` is None.
    """

    def __init__(
        self,
        core: Optional[Any] = None,
        *,
        index_dir: Optional[Path] = None,
        project_id: str = "",
    ) -> None:
        if core is not None:
            self._core = core
            self._index_dir = core._data._index_dir
            self._project_id = core.project_id
        elif index_dir is not None:
            self._core = None
            self._index_dir = Path(index_dir)
            self._project_id = project_id
        else:
            raise ValueError("Provide either 'core' (AgentCore) or 'index_dir'")

        self._roster = Roster(self._index_dir)

    # -- Data Access (delegates to AgentCore when available) --

    def _load_modules(self) -> List[Dict[str, Any]]:
        if self._core is not None:
            return self._core.get_module_structure()
        # Fallback for lightweight / test usage
        modules_path = self._index_dir / "trace_modules.jsonl"
        if not modules_path.exists():
            return []
        modules: List[Dict[str, Any]] = []
        for line in modules_path.read_text().strip().splitlines():
            if line.strip():
                try:
                    modules.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return modules

    def _load_atlas(self) -> str:
        if self._core is not None:
            return self._core.get_atlas()
        # Fallback for lightweight / test usage
        atlas_path = self._index_dir / "codebase_atlas.md"
        if atlas_path.exists():
            return atlas_path.read_text(encoding="utf-8")
        return ""

    def _modules_summary(self, modules: List[Dict[str, Any]]) -> str:
        parts = []
        for m in modules:
            name = m.get("name", "unknown")
            count = len(m.get("member_files", []))
            summary = m.get("summary", "")
            tags = ", ".join(m.get("domain_tags", []))
            parts.append(f"- **{name}** ({count} files): {summary} [{tags}]")
        return "\n".join(parts) if parts else "(no modules)"

    def _build_role_knowledge(
        self,
        role_slug: str,
        full_atlas: str,
    ) -> Tuple[str, List[Tuple[str, float]]]:
        """Build role-filtered sub-atlas and scored file list for KNOWLEDGE.md.

        Uses RoleVector projection to generate a focused sub-atlas containing
        only modules, hub files, and graph centralities within the role's scope.
        This solves the 28K boilerplate problem — each role gets 2-5K tokens
        of focused, actionable context instead of the global atlas dump.

        Returns:
            Tuple of (role_filtered_atlas, scored_files) where scored_files
            is a list of (file_path, relevance_score) tuples for the top files.
        """
        try:
            from codrag.core.atlas.role_resolver import resolve_role
            from codrag.core.atlas.role_projection import (
                project_atlas_for_role,
                _python_scoring,
            )

            role_vector = resolve_role(role_slug)

            # Generate role-filtered sub-atlas
            role_atlas = project_atlas_for_role(
                role_vector, self._index_dir, atlas_content=full_atlas
            )

            # Score files and extract top recommendations
            scored = _python_scoring(role_vector, self._index_dir)
            scored_files: List[Tuple[str, float]] = []
            if scored:
                for file_path, _entry, score in scored[:25]:
                    if score >= 0.2:
                        scored_files.append((file_path, score))

            logger.info(
                "[HR/%s] Role-filtered atlas: %d chars (vs %d full), %d scored files",
                role_slug, len(role_atlas), len(full_atlas), len(scored_files),
            )
            return role_atlas, scored_files

        except Exception as exc:
            logger.warning(
                "[HR/%s] Role projection failed, using truncated atlas: %s",
                role_slug, exc,
            )
            # Graceful fallback to truncated global atlas
            return full_atlas[:2000] if full_atlas else "(no atlas available)", []

    # -- Readiness --

    def check_readiness(self) -> ReadinessReport:
        """Evaluate codebase readiness for role generation."""
        modules = self._load_modules()
        atlas = self._load_atlas()
        file_count = sum(len(m.get("member_files", [])) for m in modules)

        has_hub_files = any(
            m.get("hub_score", 0) > 0 or "hub" in str(m.get("domain_tags", []))
            for m in modules
        )
        has_docs = bool(atlas and len(atlas) > 50)

        return compute_readiness(
            modules=modules,
            atlas_content=atlas,
            file_count=file_count,
            has_hub_files=has_hub_files,
            has_docs=has_docs,
        )

    # -- List Mode Generation --

    def generate_roles(
        self,
        role_names: List[str],
        llm_fn: LLMFn,
        min_readiness: float = 0.3,
    ) -> List[RoleSpec]:
        """Generate role definitions for user-specified role names (list mode).

        Args:
            role_names: Display names for roles to generate.
            llm_fn: Callable with signature (prompt, system=, **kwargs) -> (text, tokens).
            min_readiness: Minimum readiness score required.

        Returns:
            List of generated RoleSpec instances.

        Raises:
            ValueError: If readiness score is below threshold.
        """
        if not role_names:
            return []

        report = self.check_readiness()
        logger.info(
            "[HR] Readiness check: score=%.2f, list_ready=%s, auto_ready=%s",
            report.score, report.ready_for_list, report.ready_for_auto,
        )
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for generation "
                f"(score={report.score:.2f}, need>={min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()
        modules_summary = self._modules_summary(modules)

        all_tags: List[str] = []
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))

        logger.info(
            "[HR] Context loaded: %d modules, atlas=%d chars, %d domain tags",
            len(modules), len(atlas), len(set(all_tags)),
        )

        # Deduplicate by slug
        seen_slugs: set = set()
        unique_names: List[str] = []
        for name in role_names:
            slug = _normalize_slug(name)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                unique_names.append(name)

        roles: List[RoleSpec] = []
        for i, name in enumerate(unique_names, 1):
            slug = _normalize_slug(name)
            logger.info("[HR] Generating role %d/%d: %s (slug=%s)", i, len(unique_names), name, slug)
            role = self._generate_single_role(
                display_name=name,
                slug=slug,
                atlas=atlas,
                modules_summary=modules_summary,
                domain_tags=list(set(all_tags)),
                llm_fn=llm_fn,
            )
            self._roster.save_role(role)
            roles.append(role)
            logger.info("[HR] Role '%s' saved to roster and disk", slug)

        logger.info("[HR] Generation complete: %d role(s) created", len(roles))
        return roles

    def _generate_single_role(
        self,
        display_name: str,
        slug: str,
        atlas: str,
        modules_summary: str,
        domain_tags: List[str],
        llm_fn: LLMFn,
    ) -> RoleSpec:
        """Generate all three files for a single role.

        If existing files are found in ``.agents/<slug>/``, their content is
        passed to the LLM as ``previous_content`` so human edits (e.g. the user
        adding "manages the storybook") are preserved and expanded upon.
        """
        # ── Load previous content from disk (edit-aware regeneration) ──
        prev_agents, prev_soul = self._load_existing_files(slug)
        if prev_agents:
            logger.info(
                "[HR/%s] Found existing AGENTS.md (%d chars) — edits will be preserved",
                slug, len(prev_agents),
            )
        if prev_soul:
            logger.info(
                "[HR/%s] Found existing SOUL.md (%d chars) — edits will be preserved",
                slug, len(prev_soul),
            )

        # 0. Build role-filtered context (used by AGENTS.md and KNOWLEDGE.md)
        role_atlas, scored_files = self._build_role_knowledge(slug, atlas)
        top_file_paths = [fp for fp, _score in scored_files[:10]]
        # Use role-filtered atlas for LLM prompts; fall back to truncated global
        atlas_excerpt = role_atlas if role_atlas else (atlas[:2000] if atlas else "(no atlas available)")

        # 1. Generate AGENTS.md via LLM
        logger.info("[HR/%s] Generating AGENTS.md ...", slug)
        agents_prompt = render_agents_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
            modules_summary=modules_summary,
            recommended_files=top_file_paths,
            previous_content=prev_agents,
        )
        agents_md, agents_tokens = llm_fn(agents_prompt, system=AGENTS_MD_SYSTEM)
        logger.info("[HR/%s] AGENTS.md generated (%d chars, %d tokens)", slug, len(agents_md), agents_tokens)

        # 2. Generate SOUL.md via LLM
        logger.info("[HR/%s] Generating SOUL.md ...", slug)
        soul_prompt = render_soul_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
            previous_content=prev_soul,
        )
        soul_md, soul_tokens = llm_fn(soul_prompt, system=SOUL_MD_SYSTEM)
        logger.info("[HR/%s] SOUL.md generated (%d chars, %d tokens)", slug, len(soul_md), soul_tokens)

        # 3. Generate KNOWLEDGE.md via role-filtered sub-atlas (no LLM)
        logger.info("[HR/%s] Rendering role-filtered KNOWLEDGE.md ...", slug)
        knowledge_md = render_knowledge_md(
            role_name=display_name,
            role_slug=slug,
            atlas_snapshot=role_atlas,
            recommended_files=scored_files,
            domain_focus=domain_tags,
            project_id=self._project_id,
        )

        role = RoleSpec(
            slug=slug,
            display_name=display_name,
            agents_md=agents_md,
            soul_md=soul_md,
            knowledge_md=knowledge_md,
            recommended_files=top_file_paths,
        )

        # 4. Write files to disk
        written = self.write_role_files(role)
        for fp in written:
            logger.info("[HR/%s] Wrote: %s", slug, fp)

        return role

    # -- Disk I/O for role files -----------------------------------------

    def _agents_dir(self) -> Path:
        """Return the ``.agents/`` directory in the project root (or index dir)."""
        if self._core is not None and self._core._data._project_root:
            return self._core._data._project_root / ".agents"
        return self._index_dir / ".agents"

    def _load_existing_files(self, slug: str) -> Tuple[str, str]:
        """Load existing AGENTS.md and SOUL.md from disk for edit-aware regeneration.

        Returns (agents_md_content, soul_md_content). Empty strings if missing.
        """
        role_dir = self._agents_dir() / slug
        agents_md = ""
        soul_md = ""
        if role_dir.exists():
            agents_path = role_dir / "AGENTS.md"
            soul_path = role_dir / "SOUL.md"
            if agents_path.exists():
                try:
                    agents_md = agents_path.read_text(encoding="utf-8")
                except Exception as exc:
                    logger.warning("[HR/%s] Failed to read existing AGENTS.md: %s", slug, exc)
            if soul_path.exists():
                try:
                    soul_md = soul_path.read_text(encoding="utf-8")
                except Exception as exc:
                    logger.warning("[HR/%s] Failed to read existing SOUL.md: %s", slug, exc)
        return agents_md, soul_md

    def write_role_files(self, role: RoleSpec) -> List[Path]:
        """Write AGENTS.md, SOUL.md, and KNOWLEDGE.md to ``.agents/<slug>/``.

        Creates the directory if it doesn't exist. Returns list of written paths.
        """
        role_dir = self._agents_dir() / role.slug
        role_dir.mkdir(parents=True, exist_ok=True)

        written: List[Path] = []
        for filename, content in [
            ("AGENTS.md", role.agents_md),
            ("SOUL.md", role.soul_md),
            ("KNOWLEDGE.md", role.knowledge_md),
        ]:
            if content:
                path = role_dir / filename
                try:
                    path.write_text(content, encoding="utf-8")
                    written.append(path)
                except Exception as exc:
                    logger.error("[HR/%s] Failed to write %s: %s", role.slug, filename, exc)

        return written

    # -- Auto / Hybrid Mode Generation --

    def auto_generate_roles(
        self,
        llm_fn: LLMFn,
        min_readiness: float = 0.5,
    ) -> List[RoleSpec]:
        """Auto-infer roles from codebase analysis, then generate files (auto mode).

        Args:
            llm_fn: Callable with signature (prompt, system=, **kwargs) -> (text, tokens).
            min_readiness: Minimum readiness score. Default 0.5 for auto mode.

        Returns:
            List of generated RoleSpec instances.

        Raises:
            ValueError: If readiness score is below threshold or LLM inference fails.
        """
        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for auto generation "
                f"(score={report.score:.2f}, need>={min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()

        inferred = self._infer_roles(modules, atlas, llm_fn)

        return self.generate_roles(
            role_names=[r["display_name"] for r in inferred],
            llm_fn=llm_fn,
            min_readiness=0.0,  # already checked above
        )

    def hybrid_generate_roles(
        self,
        required_names: List[str],
        llm_fn: LLMFn,
        min_readiness: float = 0.5,
    ) -> List[RoleSpec]:
        """Auto-infer roles but guarantee required_names are included (auto+list mode).

        Args:
            required_names: Role names that must be included.
            llm_fn: Callable LLM function.
            min_readiness: Minimum readiness score.

        Returns:
            List of generated RoleSpec instances.
        """
        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for hybrid generation "
                f"(score={report.score:.2f}, need>={min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()

        inferred = self._infer_roles(modules, atlas, llm_fn)
        inferred_names = [r["display_name"] for r in inferred]

        required_slugs = {_normalize_slug(n) for n in required_names}
        merged = list(required_names)
        for name in inferred_names:
            if _normalize_slug(name) not in required_slugs:
                merged.append(name)

        return self.generate_roles(
            role_names=merged,
            llm_fn=llm_fn,
            min_readiness=0.0,
        )

    def _load_audit_findings(self) -> List[Dict[str, str]]:
        """Load structural audit findings for role inference.

        Returns a simplified list of findings suitable for LLM prompt injection.
        Prioritizes coupling hotspots, hub concentration, concept violations,
        and architectural drift — the signals most useful for role justification.
        """
        if self._core is None:
            return []
        try:
            items = self._core.get_audit_findings(
                min_priority="P2",
                categories=["architecture", "coupling", "complexity", "quality"],
            )
            findings: List[Dict[str, str]] = []
            for item in items[:30]:  # Cap to avoid prompt bloat
                findings.append({
                    "title": getattr(item, "title", ""),
                    "category": getattr(item, "category", ""),
                    "severity": getattr(item, "severity", "info"),
                    "description": getattr(item, "description", ""),
                    "affected_files": ", ".join(getattr(item, "affected_files", [])[:5]),
                })
            return findings
        except Exception as exc:
            logger.debug("Audit findings unavailable for role inference: %s", exc)
            return []

    def _infer_roles(
        self,
        modules: List[Dict[str, Any]],
        atlas: str,
        llm_fn: LLMFn,
    ) -> List[Dict[str, Any]]:
        """Use LLM to infer optimal roles from codebase analysis.

        Incorporates structural audit findings (coupling hotspots, hub
        concentration, concept violations) when available via AgentCore.

        Raises:
            ValueError: If the LLM response cannot be parsed as valid JSON.
        """
        all_tags: List[str] = []
        layer_dist: Dict[str, int] = {}
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))
            layer = m.get("architecture_layer", "unknown")
            layer_dist[layer] = layer_dist.get(layer, 0) + len(m.get("member_files", []))

        audit_findings = self._load_audit_findings()
        if audit_findings:
            logger.info("[HR] Loaded %d audit findings for role inference", len(audit_findings))

        file_count = sum(len(m.get("member_files", [])) for m in modules)
        prompt = render_auto_roles_prompt(
            file_count=file_count,
            module_count=len(modules),
            modules_summary=self._modules_summary(modules),
            atlas_excerpt=atlas[:2000] if atlas else "",
            domain_tags=sorted(set(all_tags)),
            layer_distribution=layer_dist,
            audit_findings=audit_findings if audit_findings else None,
        )

        response, _ = llm_fn(prompt, system=AUTO_ROLES_SYSTEM, json_mode=True)

        try:
            from codrag.agents.shared.json_utils import extract_json

            roles = extract_json(response)
            if not isinstance(roles, list):
                roles = [roles]
            # Validate each role has required fields
            for r in roles:
                if "display_name" not in r:
                    raise ValueError(f"Role missing 'display_name': {r}")
            return roles
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Auto role inference failed: LLM returned unparseable response. "
                f"Parse error: {exc}"
            ) from exc

    # -- Drift Detection --

    def audit_roles(self) -> DriftReport:
        """Analyze drift between existing roles and current codebase state.

        Uses RoleVector-based fitness scoring: resolves each role to a
        RoleVector, scores all indexed files against it, and measures how
        well the role's declared scope matches the files that actually
        score highly for it. Also detects cross-role overlaps and coverage gaps.

        Returns:
            DriftReport with per-role fitness, coverage gaps, and overlap warnings.
        """
        roles = self._roster.list_roles()
        if not roles:
            return DriftReport()

        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}

        fitness_list: List[RoleFitness] = []
        role_top_files: Dict[str, set] = {}  # slug -> set of top-scoring files
        covered_modules: set = set()

        for slug in roles:
            role = self._roster.get_role(slug)
            if role is None:
                continue

            score, top_files, details = self._compute_role_fitness_vector(role)
            fitness_list.append(RoleFitness(
                slug=role.slug,
                display_name=role.display_name,
                fitness_score=score,
                recommendation=RoleFitness.classify(score),
                details=details,
            ))
            role_top_files[slug] = top_files

            # Track module coverage: from scored files first, text match fallback
            for mn in module_names:
                if top_files and any(mn in fp.lower() for fp in top_files):
                    covered_modules.add(mn)
                elif mn in role.agents_md.lower():
                    covered_modules.add(mn)

        # Coverage gaps: modules with no role scoring highly for them
        gaps = [mn for mn in module_names if mn not in covered_modules and mn]

        # Cross-role overlap detection
        overlap_warnings = self._detect_role_overlaps(role_top_files)

        return DriftReport(
            role_fitness=fitness_list,
            coverage_gaps=gaps,
            overlap_warnings=overlap_warnings,
        )

    def _compute_role_fitness_vector(
        self,
        role: RoleSpec,
    ) -> Tuple[float, set, str]:
        """Score role fitness using RoleVector projection against the index.

        Resolves the role slug to a RoleVector, scores all indexed files,
        and measures alignment between the role's declared scope (recommended_files)
        and files that actually score highly.

        Returns:
            Tuple of (fitness_score, top_file_paths, details_string).
        """
        try:
            from codrag.core.atlas.role_resolver import resolve_role
            from codrag.core.atlas.role_projection import _python_scoring

            role_vector = resolve_role(role.slug)
            scored = _python_scoring(role_vector, self._index_dir)

            if not scored:
                # No index data — fall back to content-based heuristic
                return self._compute_role_fitness_fallback(role), set(), "no index data"

            # Top files: those scoring above threshold
            top_files = {fp for fp, _entry, score in scored[:30] if score >= 0.25}

            # Alignment: how many of the role's recommended files score highly?
            declared = set(role.recommended_files) if role.recommended_files else set()
            if declared:
                overlap = declared & top_files
                alignment = len(overlap) / len(declared)
            else:
                # No declared files — measure by average score of top-k
                top_scores = [score for _, _, score in scored[:20]]
                alignment = sum(top_scores) / len(top_scores) if top_scores else 0.0

            # Content quality score
            content_ok = 1.0 if len(role.agents_md) > 50 and len(role.soul_md) > 20 else 0.5

            # Composite: 60% vector alignment, 20% content quality, 20% top-file strength
            top_k = scored[:10]
            top_strength = sum(s for _, _, s in top_k) / len(top_k) if top_k else 0.3
            fitness = round(alignment * 0.6 + content_ok * 0.2 + top_strength * 0.2, 3)

            details = (
                f"vector alignment={alignment:.2f}, "
                f"top_strength={top_strength:.2f}, "
                f"declared_files={len(declared)}, "
                f"top_scored={len(top_files)}"
            )
            return fitness, top_files, details

        except Exception as exc:
            logger.debug("Vector fitness failed for %s: %s", role.slug, exc)
            return self._compute_role_fitness_fallback(role), set(), f"fallback: {exc}"

    def _compute_role_fitness_fallback(self, role: RoleSpec) -> float:
        """Fallback text-match fitness when index data is unavailable."""
        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}
        all_tags: set = set()
        for m in modules:
            all_tags.update(t.lower() for t in m.get("domain_tags", []))

        content = (role.agents_md + " " + role.knowledge_md).lower()
        referenced = sum(1 for mn in module_names if mn and mn in content)
        module_score = min(1.0, referenced / max(1, len(module_names) * 0.3))
        tag_hits = sum(1 for t in all_tags if t and t in content)
        tag_score = min(1.0, tag_hits / max(1, len(all_tags) * 0.3))
        content_score = 1.0 if len(role.agents_md) > 50 and len(role.soul_md) > 20 else 0.5
        return round(module_score * 0.5 + tag_score * 0.3 + content_score * 0.2, 3)

    def _detect_role_overlaps(
        self,
        role_top_files: Dict[str, set],
    ) -> List[str]:
        """Detect significant file overlap between roles.

        Two roles sharing >50% of their top-scoring files indicates
        either redundancy (merge candidates) or unclear boundaries.
        """
        warnings: List[str] = []
        slugs = list(role_top_files.keys())
        for i, slug_a in enumerate(slugs):
            files_a = role_top_files[slug_a]
            if not files_a:
                continue
            for slug_b in slugs[i + 1:]:
                files_b = role_top_files[slug_b]
                if not files_b:
                    continue
                overlap = files_a & files_b
                union = files_a | files_b
                jaccard = len(overlap) / len(union) if union else 0.0
                if jaccard > 0.4:
                    warnings.append(
                        f"'{slug_a}' and '{slug_b}' share {len(overlap)} "
                        f"top files (Jaccard={jaccard:.0%}) — "
                        f"consider merging or clarifying boundaries"
                    )
        return warnings

    # -- Org Chart --

    def generate_org_chart(self) -> Dict[str, Any]:
        """Generate an org chart from the current roster.

        Returns a dict with structure:
        {
            "roles": [
                {"slug": "...", "display_name": "...", "collaborates_with": [...], "modules": [...]},
            ]
        }

        Collaboration relationships are inferred from shared module/domain references.
        """
        slugs = self._roster.list_roles()
        if not slugs:
            return {"roles": []}

        roles_data: List[Dict[str, Any]] = []
        role_modules: Dict[str, set] = {}

        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}

        for slug in slugs:
            role = self._roster.get_role(slug)
            if role is None:
                continue
            content = (role.agents_md + " " + role.knowledge_md).lower()
            referenced = {mn for mn in module_names if mn and mn in content}
            role_modules[slug] = referenced

        for slug in slugs:
            role = self._roster.get_role(slug)
            if role is None:
                continue
            collaborators = []
            my_modules = role_modules.get(slug, set())
            for other_slug in slugs:
                if other_slug == slug:
                    continue
                other_modules = role_modules.get(other_slug, set())
                if my_modules & other_modules:
                    collaborators.append(other_slug)

            roles_data.append({
                "slug": slug,
                "display_name": role.display_name,
                "collaborates_with": collaborators,
                "modules": sorted(my_modules),
            })

        return {"roles": roles_data}

    def generate_org_chart_md(self) -> str:
        """Generate a markdown representation of the org chart."""
        chart = self.generate_org_chart()
        if not chart["roles"]:
            return "# Org Chart\n\n(No roles defined yet.)\n"

        lines = ["# Org Chart\n"]
        for r in chart["roles"]:
            lines.append(f"## {r['display_name']} (`{r['slug']}`)")
            if r["modules"]:
                lines.append(f"- **Modules:** {', '.join(r['modules'])}")
            if r["collaborates_with"]:
                lines.append(f"- **Collaborates with:** {', '.join(r['collaborates_with'])}")
            lines.append("")

        return "\n".join(lines)

    # -- Paperclip Sync --

    def push_to_paperclip(
        self,
        roles: Optional[List[RoleSpec]] = None,
    ) -> Dict[str, str]:
        """Push roles to Paperclip as managed agents.

        For each role, creates or updates the corresponding Paperclip agent.
        Stores the Paperclip agent ID back in the roster for future syncs.

        Args:
            roles: Specific roles to push. If None, pushes all roles in roster.

        Returns:
            Dict mapping role slug → Paperclip agent ID.

        Raises:
            RuntimeError: If AgentCore has no Paperclip client configured.
        """
        if self._core is None:
            raise RuntimeError(
                "push_to_paperclip requires an AgentCore instance with Paperclip configured."
            )

        if roles is None:
            roles = [
                self._roster.get_role(slug)
                for slug in self._roster.list_roles()
                if self._roster.get_role(slug) is not None
            ]

        result: Dict[str, str] = {}
        for role in roles:
            # Check if agent already exists in Paperclip
            if role.paperclip_agent_id:
                # Update existing
                self._core.update_agent(role.paperclip_agent_id, role)
                result[role.slug] = role.paperclip_agent_id
                logger.info("Updated Paperclip agent %s for role %s",
                           role.paperclip_agent_id, role.slug)
            else:
                # Try to find by role slug
                existing = self._core.find_agent_by_role(role.slug)
                if existing:
                    agent_id = existing.get("id", "")
                    self._core.update_agent(agent_id, role)
                    role.paperclip_agent_id = agent_id
                    self._roster.save_role(role)
                    result[role.slug] = agent_id
                    logger.info("Found and updated existing agent %s for role %s",
                               agent_id, role.slug)
                else:
                    # Create new
                    agent_id = self._core.create_agent(role)
                    role.paperclip_agent_id = agent_id
                    self._roster.save_role(role)
                    result[role.slug] = agent_id
                    logger.info("Created Paperclip agent %s for role %s",
                               agent_id, role.slug)

        return result

    # -- Dry Run --

    def dry_run(
        self,
        llm_fn: LLMFn,
        mode: str = "auto",
        role_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Preview what generation would produce without writing files or syncing.

        Returns a report dict with proposed roster, drift analysis (if existing
        roles), and estimated knowledge sizes — but no side effects.

        Args:
            llm_fn: LLM callable for role inference.
            mode: "auto", "list", or "hybrid".
            role_names: Required for "list" and "hybrid" modes.

        Returns:
            Dict with keys: proposed_roles, readiness, drift (if applicable),
            estimated_knowledge_sizes.
        """
        report: Dict[str, Any] = {}

        # Readiness
        readiness = self.check_readiness()
        report["readiness"] = {
            "score": readiness.score,
            "ready_for_auto": readiness.ready_for_auto,
            "ready_for_list": readiness.ready_for_list,
            "missing": readiness.missing,
        }

        modules = self._load_modules()
        atlas = self._load_atlas()

        # Infer roles
        if mode == "auto" or mode == "hybrid":
            inferred = self._infer_roles(modules, atlas, llm_fn)
            proposed = [r["display_name"] for r in inferred]
            if mode == "hybrid" and role_names:
                required_slugs = {_normalize_slug(n) for n in role_names}
                merged = list(role_names)  # copy to avoid mutating caller
                for name in proposed:
                    if _normalize_slug(name) not in required_slugs:
                        merged.append(name)
                proposed = merged
        elif role_names:
            proposed = role_names
            inferred = [{"display_name": n, "slug": _normalize_slug(n)} for n in role_names]
        else:
            proposed = []
            inferred = []

        report["proposed_roles"] = inferred

        # Estimate knowledge sizes for each proposed role
        sizes: Dict[str, int] = {}
        for name in proposed:
            slug = _normalize_slug(name)
            role_atlas, scored_files = self._build_role_knowledge(slug, atlas)
            sizes[slug] = len(role_atlas)
        report["estimated_knowledge_sizes"] = sizes

        # Drift against existing roster
        existing = self._roster.list_roles()
        if existing:
            drift = self.audit_roles()
            report["drift"] = {
                "role_fitness": [
                    {
                        "slug": rf.slug,
                        "display_name": rf.display_name,
                        "fitness_score": rf.fitness_score,
                        "recommendation": rf.recommendation,
                        "details": rf.details,
                    }
                    for rf in drift.role_fitness
                ],
                "coverage_gaps": drift.coverage_gaps,
                "overlap_warnings": drift.overlap_warnings,
            }

        return report

    # -- Adoption Mode --

    def adopt_existing_agents(
        self,
        agents_dir: Path,
        llm_fn: LLMFn,
    ) -> List[RoleSpec]:
        """Import existing agent files and enrich them with CoDRAG intelligence.

        Reads AGENTS.md (and optionally SOUL.md, KNOWLEDGE.md) from each
        subdirectory of agents_dir, then regenerates KNOWLEDGE.md with
        role-filtered sub-atlas and populates recommended_files via scoring.

        Args:
            agents_dir: Path containing agent subdirectories (e.g., `.agents/`).
            llm_fn: LLM callable for regenerating SOUL.md if missing.

        Returns:
            List of enriched RoleSpec instances.
        """
        if not agents_dir.exists():
            raise ValueError(f"Agents directory does not exist: {agents_dir}")

        # Load shared data once (not per-role)
        atlas = self._load_atlas()
        modules = self._load_modules()
        all_tags: List[str] = []
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))
        unique_tags = list(set(all_tags))

        adopted: List[RoleSpec] = []
        for role_dir in sorted(agents_dir.iterdir()):
            if not role_dir.is_dir():
                continue

            slug = role_dir.name
            agents_path = role_dir / "AGENTS.md"
            if not agents_path.exists():
                logger.debug("[HR/adopt] Skipping %s — no AGENTS.md", slug)
                continue

            logger.info("[HR/adopt] Adopting role: %s", slug)

            agents_md = agents_path.read_text(encoding="utf-8")
            soul_md = ""
            soul_path = role_dir / "SOUL.md"
            if soul_path.exists():
                soul_md = soul_path.read_text(encoding="utf-8")

            # Derive display name from slug or first line of AGENTS.md
            display_name = slug.replace("_", " ").title()
            for line in agents_md.split("\n"):
                stripped = line.strip().lstrip("#").strip()
                if stripped:
                    display_name = stripped
                    break

            # Build role-filtered knowledge
            role_atlas, scored_files = self._build_role_knowledge(slug, atlas)
            top_file_paths = [fp for fp, _score in scored_files[:10]]

            knowledge_md = render_knowledge_md(
                role_name=display_name,
                role_slug=slug,
                atlas_snapshot=role_atlas,
                recommended_files=scored_files,
                domain_focus=unique_tags,
                project_id=self._project_id,
            )

            # Generate SOUL.md if missing
            if not soul_md:
                logger.info("[HR/adopt/%s] No SOUL.md found, generating ...", slug)
                atlas_excerpt = atlas[:2000] if atlas else ""
                soul_prompt = render_soul_md_prompt(
                    role_name=display_name,
                    role_slug=slug,
                    atlas_excerpt=atlas_excerpt,
                )
                soul_md, _ = llm_fn(soul_prompt, system=SOUL_MD_SYSTEM)

            role = RoleSpec(
                slug=slug,
                display_name=display_name,
                agents_md=agents_md,
                soul_md=soul_md,
                knowledge_md=knowledge_md,
                recommended_files=top_file_paths,
            )

            self._roster.save_role(role)
            written = self.write_role_files(role)
            for fp in written:
                logger.info("[HR/adopt/%s] Wrote: %s", slug, fp)

            adopted.append(role)

        logger.info("[HR/adopt] Adopted %d role(s)", len(adopted))
        return adopted

    # -- Roster Access --

    @property
    def roster(self) -> Roster:
        """Access the underlying roster."""
        return self._roster
