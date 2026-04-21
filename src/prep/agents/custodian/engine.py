"""Digital Custodian Engine — detects dead code, verifies safety, plans cleanup.

Pipeline: discover -> verify -> plan -> (optionally execute) -> report.
Dry-run by default. Uses AgentCore when available.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from prep.agents.custodian.manifest import ArchiveManifest, ManifestEntry
from prep.agents.custodian.prompts import (
    SAFETY_VERIFICATION_SYSTEM,
    render_archive_readme,
    render_safety_verification_prompt,
)
from prep.agents.shared.models import CleanupCandidate, CleanupPlan

logger = logging.getLogger(__name__)

LLMFn = Callable[..., Tuple[str, int]]

_DEAD_CODE_CATEGORIES = {"dead_code", "orphan", "deprecated", "unused_export"}


class CustodianEngine:
    """Detects dead code, verifies safety, and plans cleanup operations."""

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

        self._manifest = ArchiveManifest(self._index_dir)

    def _get_impact(self, file_path: str) -> int:
        if self._core is not None:
            result = self._core.get_impact_radius(file_path)
            return len(result.get("dependents", []))
        return 0

    def _is_claimed_by_other(self, file_path: str) -> bool:
        """Check if another agent has claimed this file."""
        if self._core and self._core.collab:
            try:
                return self._core.collab.claims.is_claimed(
                    self._project_id, file_path,
                    exclude_agent="custodian",
                )
            except Exception:
                pass
        return False

    def _read_file_contents(self, file_path: str) -> str:
        if self._core is not None and hasattr(self._core, '_data'):
            project_root = self._core._data._project_root
            if project_root:
                full_path = project_root / file_path
                if full_path.exists():
                    return full_path.read_text(encoding="utf-8", errors="replace")
        return ""

    # -- Stage 1: Discovery --

    def discover(
        self,
        findings: List[Dict[str, Any]],
        max_candidates: int = 50,
    ) -> List[CleanupCandidate]:
        if not findings:
            return []

        candidates: List[CleanupCandidate] = []
        for f in findings:
            category = f.get("category", "").lower()
            if category not in _DEAD_CODE_CATEGORIES:
                continue
            for file_path in f.get("affected_files", []):
                # Phase 73.5: Skip files claimed by another agent
                if self._is_claimed_by_other(file_path):
                    logger.info(
                        "Custodian: skipping %s — claimed by "
                        "another agent", file_path,
                    )
                    continue
                dep_count = self._get_impact(file_path)
                candidates.append(CleanupCandidate(
                    file_path=file_path,
                    finding_id=f.get("id", ""),
                    dependent_count=dep_count,
                    classification="needs_review",
                    reason=f.get("description", ""),
                ))

        return candidates[:max_candidates]

    # -- Stage 2: Safety Verification --

    def verify_candidate(
        self,
        candidate: CleanupCandidate,
        llm_fn: LLMFn,
    ) -> CleanupCandidate:
        file_contents = self._read_file_contents(candidate.file_path)

        prompt = render_safety_verification_prompt(
            file_path=candidate.file_path,
            file_contents=file_contents,
            dependent_count=candidate.dependent_count,
            import_list=[],
            module_name="",
            domain_tags=[],
        )

        response, _ = llm_fn(prompt, system=SAFETY_VERIFICATION_SYSTEM, json_mode=True)

        try:
            from prep.agents.shared.json_utils import extract_json
            result = extract_json(response)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Failed to parse safety verification response: {exc}"
            ) from exc

        classification = result.get("classification", "NEEDS_REVIEW").lower()
        reason = result.get("reason", "")

        return CleanupCandidate(
            file_path=candidate.file_path,
            finding_id=candidate.finding_id,
            dependent_count=candidate.dependent_count,
            classification=classification,
            reason=reason,
        )

    def verify_candidates(
        self,
        candidates: List[CleanupCandidate],
        llm_fn: LLMFn,
    ) -> List[CleanupCandidate]:
        return [self.verify_candidate(c, llm_fn) for c in candidates]

    # -- Stage 3: Plan --

    def plan_cleanup(
        self,
        candidates: List[CleanupCandidate],
        dry_run: bool = True,
        max_files: int = 20,
    ) -> CleanupPlan:
        from datetime import date
        branch_name = f"custodian/cleanup-{date.today().isoformat()}"

        safe = [c for c in candidates if c.classification == "safe_to_delete"]
        capped = safe[:max_files]

        return CleanupPlan(
            branch_name=branch_name,
            candidates=capped,
            archive_branch="custodian/archive",
            dry_run=dry_run,
        )

    # -- Full Pipeline --

    def run(
        self,
        findings: List[Dict[str, Any]],
        llm_fn: LLMFn,
        dry_run: bool = True,
        max_candidates: int = 50,
        max_files: int = 20,
    ) -> CleanupPlan:
        candidates = self.discover(findings, max_candidates=max_candidates)
        if not candidates:
            return CleanupPlan(dry_run=dry_run)

        verified = self.verify_candidates(candidates, llm_fn)
        plan = self.plan_cleanup(verified, dry_run=dry_run, max_files=max_files)

        return plan

    # -- Push Packaging --

    def package_for_push(
        self,
        plan: CleanupPlan,
    ) -> Tuple[Any, List[Any], List[Any]]:
        from prep.adapters.pm_models import PMGoal, PMIssue, PMProject

        project = PMProject(
            name=f"Code Cleanup — {self._project_id}",
            description=(
                f"Custodian cleanup plan: {len(plan.candidates)} files identified "
                f"for deletion. Dry run: {plan.dry_run}."
            ),
        )

        goals: List[PMGoal] = []
        issues: List[PMIssue] = []

        for candidate in plan.candidates:
            issue = PMIssue(
                title=f"Remove: {candidate.file_path}",
                description=(
                    f"**Classification:** {candidate.classification}\n"
                    f"**Reason:** {candidate.reason}\n"
                    f"**Dependents at scan:** {candidate.dependent_count}\n"
                    f"**Finding:** {candidate.finding_id}"
                ),
                priority="P3",
                category="cleanup",
                effort="small",
                prep_address=f"prep://{self._project_id}/custodian/{candidate.finding_id}",
            )
            issues.append(issue)

        return project, goals, issues

    @property
    def manifest(self) -> ArchiveManifest:
        return self._manifest
