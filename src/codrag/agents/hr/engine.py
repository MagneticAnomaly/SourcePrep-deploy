"""Staffing Agent Engine — generates AI agent role definitions from codebase analysis.

Orchestrates readiness scoring, role generation (list/auto/hybrid modes),
and roster persistence. Uses AgentCore for CoDRAG data access and LLM calls.
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

    Args:
        index_dir: Path to the CoDRAG index directory.
        project_id: CoDRAG project identifier.
        project_root: Optional path to the project source root.
    """

    def __init__(
        self,
        index_dir: Path,
        project_id: str,
        project_root: Optional[Path] = None,
    ) -> None:
        self._index_dir = Path(index_dir)
        self._project_id = project_id
        self._project_root = project_root
        self._roster = Roster(self._index_dir)

    # -- Data Access Helpers --

    def _load_modules(self) -> List[Dict[str, Any]]:
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
        atlas_path = self._index_dir / "codebase_atlas.md"
        if atlas_path.exists():
            return atlas_path.read_text(encoding="utf-8")
        return ""

    def _count_indexed_files(self) -> int:
        modules = self._load_modules()
        return sum(len(m.get("member_files", [])) for m in modules)

    def _modules_summary(self, modules: List[Dict[str, Any]]) -> str:
        parts = []
        for m in modules:
            name = m.get("name", "unknown")
            count = len(m.get("member_files", []))
            summary = m.get("summary", "")
            tags = ", ".join(m.get("domain_tags", []))
            parts.append(f"- **{name}** ({count} files): {summary} [{tags}]")
        return "\n".join(parts) if parts else "(no modules)"

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

        # Deduplicate by slug
        seen_slugs: set = set()
        unique_names: List[str] = []
        for name in role_names:
            slug = _normalize_slug(name)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                unique_names.append(name)

        roles: List[RoleSpec] = []
        for name in unique_names:
            slug = _normalize_slug(name)
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
        """Generate all three files for a single role."""
        atlas_excerpt = atlas[:2000] if atlas else "(no atlas available)"

        # 1. Generate AGENTS.md via LLM
        agents_prompt = render_agents_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
            modules_summary=modules_summary,
            recommended_files=[],
        )
        agents_md, _ = llm_fn(agents_prompt, system=AGENTS_MD_SYSTEM)

        # 2. Generate SOUL.md via LLM
        soul_prompt = render_soul_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
        )
        soul_md, _ = llm_fn(soul_prompt, system=SOUL_MD_SYSTEM)

        # 3. Generate KNOWLEDGE.md via template (no LLM)
        knowledge_md = render_knowledge_md(
            role_name=display_name,
            role_slug=slug,
            atlas_snapshot=atlas_excerpt,
            recommended_files=[],
            domain_focus=domain_tags,
            project_id=self._project_id,
        )

        return RoleSpec(
            slug=slug,
            display_name=display_name,
            agents_md=agents_md,
            soul_md=soul_md,
            knowledge_md=knowledge_md,
        )

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
            ValueError: If readiness score is below threshold.
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

    def _infer_roles(
        self,
        modules: List[Dict[str, Any]],
        atlas: str,
        llm_fn: LLMFn,
    ) -> List[Dict[str, Any]]:
        """Use LLM to infer optimal roles from codebase analysis."""
        all_tags: List[str] = []
        layer_dist: Dict[str, int] = {}
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))
            layer = m.get("architecture_layer", "unknown")
            layer_dist[layer] = layer_dist.get(layer, 0) + len(m.get("member_files", []))

        file_count = sum(len(m.get("member_files", [])) for m in modules)
        prompt = render_auto_roles_prompt(
            file_count=file_count,
            module_count=len(modules),
            modules_summary=self._modules_summary(modules),
            atlas_excerpt=atlas[:2000] if atlas else "",
            domain_tags=sorted(set(all_tags)),
            layer_distribution=layer_dist,
        )

        response, _ = llm_fn(prompt, system=AUTO_ROLES_SYSTEM, json_mode=True)

        try:
            roles = json.loads(response)
            if not isinstance(roles, list):
                roles = [roles]
            return roles
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse auto-roles LLM response: %s", exc)
            return [{"slug": "engineer", "display_name": "Engineer"}]

    # -- Drift Detection --

    def audit_roles(self) -> DriftReport:
        """Analyze drift between existing roles and current codebase state.

        Computes a fitness score per role by checking whether the modules
        and domain tags referenced in the role's AGENTS.md still exist.

        Returns:
            DriftReport with per-role fitness and cross-role analysis.
        """
        roles = self._roster.list_roles()
        if not roles:
            return DriftReport()

        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}
        all_tags = set()
        for m in modules:
            all_tags.update(t.lower() for t in m.get("domain_tags", []))

        fitness_list: List[RoleFitness] = []
        covered_modules: set = set()

        for slug in roles:
            role = self._roster.get_role(slug)
            if role is None:
                continue

            score = self._compute_role_fitness(role, module_names, all_tags)
            fitness_list.append(RoleFitness(
                slug=role.slug,
                display_name=role.display_name,
                fitness_score=score,
                recommendation=RoleFitness.classify(score),
            ))

            for mn in module_names:
                if mn in role.agents_md.lower():
                    covered_modules.add(mn)

        gaps = [mn for mn in module_names if mn not in covered_modules and mn]

        return DriftReport(
            role_fitness=fitness_list,
            coverage_gaps=gaps,
        )

    def _compute_role_fitness(
        self,
        role: "RoleSpec",
        module_names: set,
        domain_tags: set,
    ) -> float:
        """Score how well a role's definition matches current codebase.

        Checks:
        - Do modules referenced in AGENTS.md still exist? (weight: 0.5)
        - Do domain tags in KNOWLEDGE.md still exist? (weight: 0.3)
        - Is the role's content non-empty? (weight: 0.2)
        """
        content = (role.agents_md + " " + role.knowledge_md).lower()

        referenced = sum(1 for mn in module_names if mn and mn in content)
        module_score = min(1.0, referenced / max(1, len(module_names) * 0.3))

        tag_hits = sum(1 for t in domain_tags if t and t in content)
        tag_score = min(1.0, tag_hits / max(1, len(domain_tags) * 0.3))

        content_score = 1.0 if len(role.agents_md) > 50 and len(role.soul_md) > 20 else 0.5

        return round(module_score * 0.5 + tag_score * 0.3 + content_score * 0.2, 3)

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

    # -- Roster Access --

    @property
    def roster(self) -> Roster:
        """Access the underlying roster."""
        return self._roster
