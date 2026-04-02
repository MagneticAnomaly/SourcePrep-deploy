# Phase 3: Digital Custodian Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Digital Custodian Engine that detects dead code via CoDRAG's trace graph, uses LLM for safety verification, plans cleanup operations with archive-first strategy, and produces a manifest + Paperclip cleanup report — all in dry-run mode by default.

**Architecture:** The engine lives at `src/codrag/agents/custodian/`. It consumes AgentCore for audit findings and impact analysis, uses the existing `GitClient` from `agents/shared/git_client.py` for branch/archive operations, and an injectable LLM for safety verification. The pipeline is: discover → verify → plan → (optionally execute) → report. The `CleanupCandidate` and `CleanupPlan` models from Phase 0's `shared/models.py` are used as-is.

**Tech Stack:** Python 3.11+, AgentCore (Phase 0), GitClient (Phase 0), LLMClient, CoDRAG audit/impact APIs, JSON persistence.

**Build order:** Tasks 1-2 are independent (prompts + manifest). Tasks 3-5 build the engine sequentially. Task 6 adds push packaging. Tasks 7-8 finalize.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/codrag/agents/custodian/__init__.py` | Subpackage init, re-exports `CustodianEngine` |
| `src/codrag/agents/custodian/prompts.py` | LLM prompt for safety verification |
| `src/codrag/agents/custodian/manifest.py` | `ArchiveManifest` class: JSON persistence for archived items |
| `src/codrag/agents/custodian/engine.py` | `CustodianEngine` class: orchestrates cleanup pipeline |
| `tests/test_custodian_prompts.py` | Prompt template tests |
| `tests/test_custodian_manifest.py` | Manifest persistence tests |
| `tests/test_custodian_engine.py` | CustodianEngine tests |
| `tests/test_custodian_integration.py` | Full pipeline integration tests |

---

### Task 1: Create custodian subpackage and prompt templates

**Files:**
- Create: `src/codrag/agents/custodian/__init__.py`
- Create: `src/codrag/agents/custodian/prompts.py`
- Create: `tests/test_custodian_prompts.py`

- [ ] **Step 1: Create subpackage init**

```python
# src/codrag/agents/custodian/__init__.py
"""Digital Custodian Engine — detects dead code, archives safely, cleans up codebases."""
```

- [ ] **Step 2: Write tests for prompt templates**

```python
# tests/test_custodian_prompts.py
"""Tests for Custodian prompt template rendering."""
from codrag.agents.custodian.prompts import (
    render_safety_verification_prompt,
    render_archive_readme,
)


class TestSafetyVerificationPrompt:
    def test_includes_file_path(self) -> None:
        result = render_safety_verification_prompt(
            file_path="src/legacy/old_parser.py",
            file_contents="def parse(): pass",
            dependent_count=0,
            import_list=["os", "json"],
            module_name="legacy",
            domain_tags=["deprecated"],
        )
        assert "src/legacy/old_parser.py" in result

    def test_includes_file_contents(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py",
            file_contents="class OldHandler:\n    pass",
            dependent_count=0,
            import_list=[],
            module_name="core",
            domain_tags=[],
        )
        assert "class OldHandler" in result

    def test_includes_dependent_count(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py",
            file_contents="x = 1",
            dependent_count=3,
            import_list=[],
            module_name="",
            domain_tags=[],
        )
        assert "3" in result

    def test_asks_safety_questions(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py",
            file_contents="",
            dependent_count=0,
            import_list=[],
            module_name="",
            domain_tags=[],
        )
        assert "dynamic" in result.lower() or "importlib" in result.lower()
        assert "SAFE_TO_DELETE" in result
        assert "NEEDS_REVIEW" in result


class TestArchiveReadme:
    def test_includes_file_paths(self) -> None:
        result = render_archive_readme(
            original_paths=["src/old/a.py", "src/old/b.py"],
            reason="Dead code — 0 dependents",
            finding_id="ARCH-17",
            archived_at="2026-04-01T14:30:00Z",
        )
        assert "src/old/a.py" in result
        assert "src/old/b.py" in result

    def test_includes_reason(self) -> None:
        result = render_archive_readme(
            original_paths=["a.py"],
            reason="Module replaced by v2",
            finding_id="QUAL-5",
            archived_at="2026-04-01",
        )
        assert "Module replaced by v2" in result
        assert "QUAL-5" in result
```

- [ ] **Step 3: Implement prompt templates**

```python
# src/codrag/agents/custodian/prompts.py
"""LLM prompt templates for Digital Custodian safety verification."""
from __future__ import annotations

from typing import List


def render_safety_verification_prompt(
    file_path: str,
    file_contents: str,
    dependent_count: int,
    import_list: List[str],
    module_name: str,
    domain_tags: List[str],
) -> str:
    """Render the LLM prompt for verifying whether a file is safe to delete."""
    imports_str = ", ".join(import_list) if import_list else "(none)"
    tags_str = ", ".join(domain_tags) if domain_tags else "(none)"
    # Truncate file contents to first 200 lines
    lines = file_contents.splitlines()[:200]
    truncated = "\n".join(lines)

    return f"""You are reviewing a code file to determine if it is truly dead (safe to delete).

File: {file_path}
File contents (first 200 lines):
```
{truncated}
```

CoDRAG analysis:
- Dependents (static imports): {dependent_count} (should be 0)
- This file imports: {imports_str}
- Module membership: {module_name}
- Domain tags: {tags_str}

Answer these questions:
1. Could this file be imported dynamically (importlib, __import__, exec)?
2. Could this file be referenced via string-based paths (config files, env vars)?
3. Is this file a public API entry point (exposed via __init__.py, __all__)?
4. Is this file part of a plugin system or extension mechanism?
5. Could this file be a CLI entry point, test fixture, or script?
6. Is there any reason a human might want to keep this file?

If ANY answer is "yes" or "uncertain", classify as NEEDS_REVIEW.
If ALL answers are "no", classify as SAFE_TO_DELETE.
Never default to SAFE_TO_DELETE if uncertain.

Return JSON: {{"classification": "SAFE_TO_DELETE" | "NEEDS_REVIEW" | "KEEP", "reason": "..."}}"""


SAFETY_VERIFICATION_SYSTEM = """You are a conservative code safety reviewer.
You output ONLY valid JSON with "classification" and "reason" fields.
When in doubt, classify as NEEDS_REVIEW — false positives are acceptable, false negatives are not."""


def render_archive_readme(
    original_paths: List[str],
    reason: str,
    finding_id: str,
    archived_at: str,
) -> str:
    """Render an _ARCHIVE_README.md for an archived file group."""
    files_list = "\n".join(f"- `{p}`" for p in original_paths)

    return f"""# Archived by Digital Custodian

**Archived at:** {archived_at}
**CoDRAG Finding:** {finding_id}
**Reason:** {reason}

## Original Locations

{files_list}

## Restore Instructions

To restore these files, cherry-pick the archive commit or copy them
back from this directory to their original locations.
"""
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_custodian_prompts.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/custodian/__init__.py src/codrag/agents/custodian/prompts.py tests/test_custodian_prompts.py
git commit -m "feat(custodian): add subpackage and safety verification prompts"
```

---

### Task 2: Archive manifest persistence

**Files:**
- Create: `src/codrag/agents/custodian/manifest.py`
- Create: `tests/test_custodian_manifest.py`

- [ ] **Step 1: Write tests for manifest**

```python
# tests/test_custodian_manifest.py
"""Tests for Custodian archive manifest persistence."""
import json
from pathlib import Path

import pytest

from codrag.agents.custodian.manifest import ArchiveManifest, ManifestEntry


@pytest.fixture
def manifest(tmp_path: Path) -> ArchiveManifest:
    return ArchiveManifest(tmp_path)


def _sample_entry() -> ManifestEntry:
    return ManifestEntry(
        entry_id="archive-001",
        original_paths=["src/old/a.py", "src/old/b.py"],
        archive_path="archived/old_module/",
        reason="Dead code — 0 dependents",
        finding_id="ARCH-17",
        dependent_count=0,
    )


class TestArchiveManifest:
    def test_add_and_get_entry(self, manifest: ArchiveManifest) -> None:
        entry = _sample_entry()
        manifest.add_entry(entry)
        loaded = manifest.get_entry("archive-001")
        assert loaded is not None
        assert loaded.original_paths == ["src/old/a.py", "src/old/b.py"]
        assert loaded.reason == "Dead code — 0 dependents"

    def test_list_entries(self, manifest: ArchiveManifest) -> None:
        manifest.add_entry(_sample_entry())
        e2 = ManifestEntry(
            entry_id="archive-002",
            original_paths=["c.py"],
            archive_path="archived/c/",
            reason="Orphaned",
            finding_id="ARCH-22",
            dependent_count=0,
        )
        manifest.add_entry(e2)
        entries = manifest.list_entries()
        assert len(entries) == 2

    def test_empty_manifest(self, manifest: ArchiveManifest) -> None:
        assert manifest.list_entries() == []
        assert manifest.get_entry("x") is None

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        m1 = ArchiveManifest(tmp_path)
        m1.add_entry(_sample_entry())
        m2 = ArchiveManifest(tmp_path)
        assert m2.get_entry("archive-001") is not None

    def test_manifest_file_is_valid_json(
        self, manifest: ArchiveManifest, tmp_path: Path
    ) -> None:
        manifest.add_entry(_sample_entry())
        data = json.loads(
            (tmp_path / ".custodian_manifest.json").read_text()
        )
        assert "version" in data
        assert "entries" in data

    def test_entry_has_timestamp(self, manifest: ArchiveManifest) -> None:
        manifest.add_entry(_sample_entry())
        entry = manifest.get_entry("archive-001")
        assert entry is not None
        assert entry.archived_at  # non-empty string
```

- [ ] **Step 2: Implement ArchiveManifest**

```python
# src/codrag/agents/custodian/manifest.py
"""Archive manifest persistence for Digital Custodian.

Stores the master index of all archived items to
``<index_dir>/.custodian_manifest.json``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = ".custodian_manifest.json"


@dataclass
class ManifestEntry:
    """A single archived item in the manifest."""

    entry_id: str
    original_paths: List[str]
    archive_path: str
    reason: str
    finding_id: str
    dependent_count: int
    archived_at: str = ""
    cleanup_branch: str = ""
    cleanup_commit: str = ""

    def __post_init__(self) -> None:
        if not self.archived_at:
            self.archived_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ManifestEntry:
        return cls(
            entry_id=d["entry_id"],
            original_paths=list(d.get("original_paths", [])),
            archive_path=d.get("archive_path", ""),
            reason=d.get("reason", ""),
            finding_id=d.get("finding_id", ""),
            dependent_count=d.get("dependent_count", 0),
            archived_at=d.get("archived_at", ""),
            cleanup_branch=d.get("cleanup_branch", ""),
            cleanup_commit=d.get("cleanup_commit", ""),
        )


class ArchiveManifest:
    """Manages the persistent manifest of archived items.

    Args:
        index_dir: Directory where ``.custodian_manifest.json`` is stored.
    """

    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _MANIFEST_FILENAME
        self._entries: Dict[str, ManifestEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = {
                e["entry_id"]: ManifestEntry.from_dict(e)
                for e in data.get("entries", [])
            }
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load manifest: %s", exc)
            self._entries = {}

    def _save(self) -> None:
        data = {
            "version": 1,
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp", prefix=".manifest_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def add_entry(self, entry: ManifestEntry) -> None:
        """Add an entry to the manifest."""
        self._entries[entry.entry_id] = entry
        self._save()

    def get_entry(self, entry_id: str) -> Optional[ManifestEntry]:
        """Get an entry by ID, or None if not found."""
        return self._entries.get(entry_id)

    def list_entries(self) -> List[ManifestEntry]:
        """Return all entries."""
        return list(self._entries.values())
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_custodian_manifest.py -v`
Expected: All 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/codrag/agents/custodian/manifest.py tests/test_custodian_manifest.py
git commit -m "feat(custodian): add ArchiveManifest for archive tracking"
```

---

### Task 3: CustodianEngine — discovery and safety verification

**Files:**
- Create: `src/codrag/agents/custodian/engine.py`
- Create: `tests/test_custodian_engine.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_custodian_engine.py
"""Tests for CustodianEngine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from codrag.agents.custodian.engine import CustodianEngine
from codrag.agents.shared.models import CleanupCandidate, CleanupPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    """Fake LLM that classifies all candidates as safe to delete."""
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "SAFE_TO_DELETE",
            "reason": "No dynamic imports, no config refs, no public API usage",
        }), 40
    return "ok", 10


def _fake_llm_needs_review(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    """Fake LLM that classifies all candidates as needs_review."""
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "NEEDS_REVIEW",
            "reason": "Possible dynamic import via importlib",
        }), 40
    return "ok", 10


def _sample_findings() -> List[Dict[str, Any]]:
    return [
        {"id": "ARCH-17", "title": "Orphaned test fixture",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["tests/old_fixture.py"],
         "description": "Test fixture with 0 dependents"},
        {"id": "ARCH-22", "title": "Unused utility module",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["src/utils/old_helpers.py"],
         "description": "Helper functions never imported"},
        {"id": "SEC-1", "title": "Hardcoded secret",
         "category": "security", "priority": "P0",
         "affected_files": ["config.py"],
         "description": "Not dead code — should be ignored"},
    ]


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    (tmp_path / "codebase_atlas.md").write_text("# Test Project")
    modules = [
        {"name": "core", "member_files": ["core/a.py"] * 10,
         "domain_tags": ["backend"], "architecture_layer": "core"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> CustodianEngine:
    return CustodianEngine(index_dir=engine_dir, project_id="test_proj")


class TestDiscovery:
    def test_discover_filters_dead_code_findings(
        self, engine: CustodianEngine
    ) -> None:
        candidates = engine.discover(_sample_findings())
        # Should only include dead_code category, not security
        assert all(c.finding_id != "SEC-1" for c in candidates)
        assert len(candidates) == 2

    def test_discover_creates_cleanup_candidates(
        self, engine: CustodianEngine
    ) -> None:
        candidates = engine.discover(_sample_findings())
        assert all(isinstance(c, CleanupCandidate) for c in candidates)
        assert candidates[0].file_path == "tests/old_fixture.py"

    def test_discover_empty_findings(
        self, engine: CustodianEngine
    ) -> None:
        assert engine.discover([]) == []

    def test_discover_respects_max_candidates(
        self, engine: CustodianEngine
    ) -> None:
        candidates = engine.discover(_sample_findings(), max_candidates=1)
        assert len(candidates) <= 1


class TestSafetyVerification:
    def test_verify_classifies_safe(
        self, engine: CustodianEngine
    ) -> None:
        candidate = CleanupCandidate(
            file_path="old.py", finding_id="ARCH-1", dependent_count=0,
        )
        verified = engine.verify_candidate(candidate, llm_fn=_fake_llm)
        assert verified.classification == "safe_to_delete"

    def test_verify_classifies_needs_review(
        self, engine: CustodianEngine
    ) -> None:
        candidate = CleanupCandidate(
            file_path="old.py", finding_id="ARCH-1", dependent_count=0,
        )
        verified = engine.verify_candidate(
            candidate, llm_fn=_fake_llm_needs_review,
        )
        assert verified.classification == "needs_review"

    def test_verify_populates_reason(
        self, engine: CustodianEngine
    ) -> None:
        candidate = CleanupCandidate(
            file_path="old.py", finding_id="ARCH-1", dependent_count=0,
        )
        verified = engine.verify_candidate(candidate, llm_fn=_fake_llm)
        assert verified.reason  # non-empty

    def test_verify_raises_on_bad_json(
        self, engine: CustodianEngine
    ) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        candidate = CleanupCandidate(
            file_path="old.py", finding_id="ARCH-1", dependent_count=0,
        )
        with pytest.raises(ValueError, match="safety verification"):
            engine.verify_candidate(candidate, llm_fn=bad_llm)
```

- [ ] **Step 2: Implement CustodianEngine**

```python
# src/codrag/agents/custodian/engine.py
"""Digital Custodian Engine — detects dead code, verifies safety, plans cleanup.

Pipeline: discover → verify → plan → (optionally execute) → report.
Dry-run by default. Uses AgentCore when available.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from codrag.agents.custodian.manifest import ArchiveManifest, ManifestEntry
from codrag.agents.custodian.prompts import (
    SAFETY_VERIFICATION_SYSTEM,
    render_archive_readme,
    render_safety_verification_prompt,
)
from codrag.agents.shared.models import CleanupCandidate, CleanupPlan

logger = logging.getLogger(__name__)

LLMFn = Callable[..., Tuple[str, int]]

# Categories that indicate dead/orphaned code
_DEAD_CODE_CATEGORIES = {"dead_code", "orphan", "deprecated", "unused_export"}


class CustodianEngine:
    """Detects dead code, verifies safety, and plans cleanup operations.

    Accepts either an AgentCore instance (preferred) or raw index_dir
    + project_id for lightweight / test usage.
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

        self._manifest = ArchiveManifest(self._index_dir)

    # -- Data Access --

    def _get_impact(self, file_path: str) -> int:
        """Return dependent count for a file. 0 if unavailable."""
        if self._core is not None:
            result = self._core.get_impact_radius(file_path)
            return len(result.get("dependents", []))
        return 0

    def _read_file_contents(self, file_path: str) -> str:
        """Read file contents for LLM review. Returns '' if not found."""
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
        """Filter audit findings to dead code candidates.

        Args:
            findings: Raw audit findings (dicts with id, title, category,
                affected_files, etc.).
            max_candidates: Maximum candidates to return.

        Returns:
            List of CleanupCandidate instances with classification "needs_review".
        """
        if not findings:
            return []

        candidates: List[CleanupCandidate] = []
        for f in findings:
            category = f.get("category", "").lower()
            if category not in _DEAD_CODE_CATEGORIES:
                continue

            for file_path in f.get("affected_files", []):
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
        """Run LLM safety verification on a single candidate.

        Returns a new CleanupCandidate with updated classification and reason.

        Raises:
            ValueError: If LLM returns unparseable response.
        """
        file_contents = self._read_file_contents(candidate.file_path)

        prompt = render_safety_verification_prompt(
            file_path=candidate.file_path,
            file_contents=file_contents,
            dependent_count=candidate.dependent_count,
            import_list=[],  # Could be enriched from trace data
            module_name="",
            domain_tags=[],
        )

        response, _ = llm_fn(prompt, system=SAFETY_VERIFICATION_SYSTEM, json_mode=True)

        try:
            result = json.loads(response)
        except (json.JSONDecodeError, TypeError) as exc:
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
        """Run safety verification on all candidates."""
        return [self.verify_candidate(c, llm_fn) for c in candidates]

    # -- Stage 3: Plan --

    def plan_cleanup(
        self,
        candidates: List[CleanupCandidate],
        dry_run: bool = True,
        max_files: int = 20,
    ) -> CleanupPlan:
        """Create a cleanup plan from verified candidates.

        Only includes candidates classified as "safe_to_delete".
        Caps at max_files.

        Args:
            candidates: Verified candidates.
            dry_run: Whether this is a dry run (default True).
            max_files: Maximum files to include.

        Returns:
            CleanupPlan instance.
        """
        from datetime import date
        branch_name = f"custodian/cleanup-{date.today().isoformat()}"

        # Filter to safe candidates only, cap at max_files
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
        """Execute the full cleanup pipeline: discover → verify → plan.

        Args:
            findings: Raw audit findings.
            llm_fn: Injectable LLM function.
            dry_run: Whether to skip execution (default True).
            max_candidates: Max candidates to discover.
            max_files: Max files in cleanup plan.

        Returns:
            CleanupPlan instance.
        """
        # Stage 1: Discover
        candidates = self.discover(findings, max_candidates=max_candidates)
        if not candidates:
            return CleanupPlan(dry_run=dry_run)

        # Stage 2: Verify
        verified = self.verify_candidates(candidates, llm_fn)

        # Stage 3: Plan
        plan = self.plan_cleanup(verified, dry_run=dry_run, max_files=max_files)

        return plan

    # -- Push Packaging --

    def package_for_push(
        self,
        plan: CleanupPlan,
    ) -> Tuple[Any, List[Any], List[Any]]:
        """Convert cleanup plan into Paperclip-ready PM models.

        Returns:
            Tuple of (PMProject, goals, issues).
        """
        from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject

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
                codrag_address=f"codrag://{self._project_id}/custodian/{candidate.finding_id}",
            )
            issues.append(issue)

        return project, goals, issues

    # -- Manifest Access --

    @property
    def manifest(self) -> ArchiveManifest:
        """Access the underlying archive manifest."""
        return self._manifest
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_custodian_engine.py -v`
Expected: All 8 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/codrag/agents/custodian/engine.py tests/test_custodian_engine.py
git commit -m "feat(custodian): add CustodianEngine with discovery and safety verification"
```

---

### Task 4: Cleanup plan and push packaging tests

**Files:**
- Modify: `tests/test_custodian_engine.py`

- [ ] **Step 1: Add tests for plan + push + full pipeline**

Append to `tests/test_custodian_engine.py`:

```python
class TestCleanupPlan:
    def test_plan_includes_only_safe_candidates(
        self, engine: CustodianEngine
    ) -> None:
        candidates = [
            CleanupCandidate(file_path="a.py", finding_id="A1",
                           dependent_count=0, classification="safe_to_delete"),
            CleanupCandidate(file_path="b.py", finding_id="A2",
                           dependent_count=0, classification="needs_review"),
        ]
        plan = engine.plan_cleanup(candidates)
        assert len(plan.candidates) == 1
        assert plan.candidates[0].file_path == "a.py"

    def test_plan_caps_at_max_files(
        self, engine: CustodianEngine
    ) -> None:
        candidates = [
            CleanupCandidate(file_path=f"f{i}.py", finding_id=f"A{i}",
                           dependent_count=0, classification="safe_to_delete")
            for i in range(30)
        ]
        plan = engine.plan_cleanup(candidates, max_files=5)
        assert len(plan.candidates) == 5

    def test_plan_has_branch_name(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.plan_cleanup([])
        assert plan.branch_name.startswith("custodian/cleanup-")

    def test_plan_defaults_to_dry_run(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.plan_cleanup([])
        assert plan.dry_run is True


class TestPushPackaging:
    def test_package_returns_pm_models(
        self, engine: CustodianEngine
    ) -> None:
        plan = CleanupPlan(
            candidates=[CleanupCandidate(
                file_path="old.py", finding_id="A1",
                dependent_count=0, classification="safe_to_delete",
                reason="Dead code",
            )],
            dry_run=True,
        )
        project, goals, issues = engine.package_for_push(plan)
        assert "Cleanup" in project.name
        assert len(issues) == 1
        assert "old.py" in issues[0].title

    def test_empty_plan_returns_empty_issues(
        self, engine: CustodianEngine
    ) -> None:
        plan = CleanupPlan(candidates=[], dry_run=True)
        _, _, issues = engine.package_for_push(plan)
        assert issues == []


class TestFullPipeline:
    def test_run_produces_cleanup_plan(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
        )
        assert isinstance(plan, CleanupPlan)
        assert plan.dry_run is True

    def test_run_filters_and_verifies(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
        )
        # Only dead_code findings, all verified as safe
        for c in plan.candidates:
            assert c.classification == "safe_to_delete"

    def test_run_with_empty_findings(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.run(findings=[], llm_fn=_fake_llm)
        assert plan.candidates == []

    def test_run_with_needs_review_llm(
        self, engine: CustodianEngine
    ) -> None:
        plan = engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm_needs_review,
        )
        # All classified as needs_review, so none in plan (plan only includes safe)
        assert plan.candidates == []
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_custodian_engine.py -v`
Expected: All 18 tests PASS (8 existing + 10 new)

- [ ] **Step 3: Commit**

```bash
git add tests/test_custodian_engine.py
git commit -m "test(custodian): add cleanup plan, push packaging, and full pipeline tests"
```

---

### Task 5: Public API exports

**Files:**
- Modify: `src/codrag/agents/custodian/__init__.py`

- [ ] **Step 1: Update init with re-exports**

```python
# src/codrag/agents/custodian/__init__.py
"""Digital Custodian Engine — detects dead code, archives safely, cleans up codebases."""

from codrag.agents.custodian.engine import CustodianEngine
from codrag.agents.custodian.manifest import ArchiveManifest, ManifestEntry

__all__ = [
    "CustodianEngine",
    "ArchiveManifest",
    "ManifestEntry",
]
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py tests/test_researcher_*.py tests/test_custodian_*.py -q`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/codrag/agents/custodian/__init__.py
git commit -m "feat(custodian): export public API from custodian subpackage"
```

---

### Task 6: Integration test + strategy doc update

**Files:**
- Create: `tests/test_custodian_integration.py`
- Modify: `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

- [ ] **Step 1: Create integration test**

```python
# tests/test_custodian_integration.py
"""Integration tests for the full Digital Custodian pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from codrag.agents.custodian import CustodianEngine, ArchiveManifest
from codrag.agents.shared.models import CleanupPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "SAFE_TO_DELETE",
            "reason": "Confirmed dead — no dynamic imports or config refs",
        }), 40
    return "ok", 10


def _findings():
    return [
        {"id": "ARCH-17", "title": "Orphaned fixture",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["tests/old_fixture.py"],
         "description": "0 dependents"},
        {"id": "ARCH-22", "title": "Unused helpers",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["src/utils/old.py"],
         "description": "Never imported"},
        {"id": "QUAL-5", "title": "Deprecated module",
         "category": "deprecated", "priority": "P3",
         "affected_files": ["src/legacy/auth_v1.py"],
         "description": "Replaced by auth_v2"},
        {"id": "SEC-1", "title": "Secret leak",
         "category": "security", "priority": "P0",
         "affected_files": ["config.py"],
         "description": "Not dead code"},
    ]


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    (tmp_path / "codebase_atlas.md").write_text("# Test")
    (tmp_path / "trace_modules.jsonl").write_text("")
    return tmp_path


class TestCustodianEndToEnd:
    def test_full_dry_run_pipeline(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")

        plan = engine.run(findings=_findings(), llm_fn=_fake_llm)

        assert isinstance(plan, CleanupPlan)
        assert plan.dry_run is True
        # Should find 3 dead code files (not SEC-1)
        assert len(plan.candidates) == 3
        for c in plan.candidates:
            assert c.classification == "safe_to_delete"

    def test_push_packaging_end_to_end(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")
        plan = engine.run(findings=_findings(), llm_fn=_fake_llm)

        project, _, issues = engine.package_for_push(plan)
        assert "Cleanup" in project.name
        assert len(issues) == 3

    def test_stage_by_stage(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")

        # Stage 1: Discover
        candidates = engine.discover(_findings())
        assert len(candidates) == 3

        # Stage 2: Verify
        verified = engine.verify_candidates(candidates, _fake_llm)
        assert all(c.classification == "safe_to_delete" for c in verified)

        # Stage 3: Plan
        plan = engine.plan_cleanup(verified)
        assert len(plan.candidates) == 3
        assert plan.dry_run is True
```

- [ ] **Step 2: Run integration + full suite**

Run: `.venv/bin/pytest tests/test_custodian_integration.py -v`
Expected: All 3 tests PASS

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py tests/test_researcher_*.py tests/test_custodian_*.py -q`
Expected: All tests PASS

- [ ] **Step 3: Update IMPLEMENTATION_STRATEGY.md — mark Phase 3 tasks complete**

Mark 3.1-3.7 as ☑. Leave 3.8 (Paperclip adapter), 3.9 (Pi Agent wiring), 3.10 (AgentConcurrencyGate) as ☐.

- [ ] **Step 4: Commit**

```bash
git add tests/test_custodian_integration.py docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md
git commit -m "feat(custodian): complete Phase 3 — Digital Custodian Engine"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Subpackage + safety verification prompts | 6 |
| 2 | Archive manifest persistence | 6 |
| 3 | CustodianEngine — discovery + verification | 8 |
| 4 | Plan + push + pipeline tests | 10 |
| 5 | Public API exports | 0 (run existing) |
| 6 | Integration test + strategy update | 3 |
| **Total** | | **~33 tests** |
