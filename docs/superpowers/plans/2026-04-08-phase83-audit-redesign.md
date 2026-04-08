# Phase 83: Audit Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `codrag_audit` into a dual-mode tool (structural-only findings + external finding enrichment) with a global experimental toggle and P0 quick fixes.

**Architecture:** The existing `codrag_audit` MCP tool gains a new `findings` parameter. When absent, a new structural-only scan runs (keeping only CoDRAG-unique analyzers: hub bottlenecks, circular deps, module boundary violations). When present, an enrichment engine annotates each external finding with trace graph context, concepts, and observations. A global `experimental` toggle gates LLM recommendations and the dashboard audit pane. Existing analyzer infrastructure (`BaseAnalyzer`, `AuditContext`, `Finding`) is reused.

**Tech Stack:** Python 3.11, FastAPI, SQLite (settings_store), existing trace/concept/observation APIs.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/codrag/core/enrichment.py` | **Create** | Enrichment engine: takes external findings + trace/concept/observation context → annotated findings |
| `src/codrag/core/audit/structural.py` | **Create** | Structural-only scan: runs only CoDRAG-unique analyzers, deduplicates, generates template recommendations |
| `src/codrag/core/audit/recommendations.py` | **Create** | Template-based recommendation fragments + experimental LLM recommendation generator |
| `src/codrag/mcp_tools.py` | **Modify** | Add `findings` param to `codrag_audit` schema |
| `src/codrag/mcp/server.py` | **Modify** | Route `findings` → enrichment handler; route default scan → structural handler |
| `src/codrag/services/settings_store.py` | **Modify** | Add `get_experimental()` helper |
| `src/codrag/api/routers/audit.py` | **Modify** | Add `/structural` endpoint for new structural scan |
| `tests/test_enrichment.py` | **Create** | Tests for enrichment engine |
| `tests/test_structural_audit.py` | **Create** | Tests for structural-only scan |
| `tests/test_recommendations.py` | **Create** | Tests for recommendation generator |

---

### Task 1: Global Experimental Toggle

**Files:**
- Modify: `src/codrag/services/settings_store.py`
- Test: `tests/test_experimental_toggle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experimental_toggle.py
import pytest
from codrag.services.settings_store import SettingsStore
from pathlib import Path
import tempfile


@pytest.fixture
def store(tmp_path):
    s = SettingsStore()
    s.init(tmp_path / "test_settings.db")
    yield s
    s.close()


def test_experimental_defaults_to_false(store):
    assert store.get_experimental() is False


def test_experimental_can_be_enabled(store):
    store.set("global/experimental", True)
    assert store.get_experimental() is True


def test_experimental_can_be_disabled(store):
    store.set("global/experimental", True)
    store.set("global/experimental", False)
    assert store.get_experimental() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_experimental_toggle.py -v`
Expected: FAIL with `AttributeError: 'SettingsStore' object has no attribute 'get_experimental'`

- [ ] **Step 3: Add `get_experimental()` to SettingsStore**

In `src/codrag/services/settings_store.py`, add this method to the `SettingsStore` class (after the existing `get` method):

```python
def get_experimental(self) -> bool:
    """Return the global experimental toggle. Defaults to False."""
    val = self.get("global/experimental")
    return bool(val) if val is not None else False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_experimental_toggle.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_experimental_toggle.py src/codrag/services/settings_store.py
git commit -m "feat(settings): add global experimental toggle"
```

---

### Task 2: Template Recommendation Generator

**Files:**
- Create: `src/codrag/core/audit/recommendations.py`
- Test: `tests/test_recommendations.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recommendations.py
import pytest
from codrag.core.audit.recommendations import generate_recommendation


def test_critical_hub_with_concept():
    rec = generate_recommendation(
        hub_status="critical",
        dependents=23,
        concepts=["Planned refactor: split handler dispatch"],
        observations=[],
    )
    assert "Critical hub file" in rec
    assert "23 dependents" in rec
    assert "Planned refactor" in rec


def test_moderate_hub_no_concept():
    rec = generate_recommendation(
        hub_status="moderate",
        dependents=8,
        concepts=[],
        observations=[],
    )
    assert "no architectural plan" in rec.lower() or "consider creating a concept" in rec.lower()


def test_hub_with_observations():
    rec = generate_recommendation(
        hub_status="high",
        dependents=15,
        concepts=[],
        observations=["2026-03-15: Growing concern", "2026-04-01: Still growing"],
    )
    assert "flagged" in rec.lower() or "2" in rec


def test_low_risk_file():
    rec = generate_recommendation(
        hub_status="low",
        dependents=2,
        concepts=[],
        observations=[],
    )
    assert "low" in rec.lower() or "leaf" in rec.lower() or "minimal" in rec.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_recommendations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codrag.core.audit.recommendations'`

- [ ] **Step 3: Implement the recommendation generator**

```python
# src/codrag/core/audit/recommendations.py
"""Template-based recommendation generator for audit findings.

Composes fragments based on structural signals (hub status, concepts, observations).
LLM recommendations are gated behind the experimental toggle.
"""
from __future__ import annotations

from typing import List, Optional


def generate_recommendation(
    hub_status: str,
    dependents: int,
    concepts: List[str],
    observations: List[str],
    experimental_llm: bool = False,
) -> str:
    """Generate a context-aware recommendation from structural signals.

    Args:
        hub_status: "critical" | "high" | "moderate" | "low"
        dependents: Number of files that depend on this file
        concepts: Related concept titles/assertions
        observations: Related observation summaries
        experimental_llm: If True, also generate LLM recommendation (Phase 83.1)

    Returns:
        Human-readable recommendation string.
    """
    parts: List[str] = []

    # Hub status fragment
    if hub_status == "critical":
        parts.append(f"Critical hub file \u2014 changes here ripple to {dependents} dependents.")
    elif hub_status == "high":
        parts.append(f"High-impact file with {dependents} dependents.")
    elif hub_status == "moderate":
        parts.append(f"Moderate coupling ({dependents} dependents).")
    else:
        parts.append(f"Low coupling ({dependents} dependents). Minimal blast radius.")

    # Concept fragment
    if concepts:
        parts.append(f"Existing concept: {concepts[0]}")
        if len(concepts) > 1:
            parts.append(f"({len(concepts) - 1} more related concepts.)")
    elif hub_status in ("critical", "high"):
        parts.append("No architectural plan documented. Consider creating a concept before modifying.")

    # Observation fragment
    if observations:
        parts.append(f"Flagged {len(observations)} times in observations.")

    # Composite advice
    if concepts and hub_status in ("critical", "high"):
        parts.append("Prioritize \u2014 high structural impact with planned work already documented.")
    elif not concepts and hub_status in ("critical", "high"):
        parts.append("High impact but undocumented. Proceed with caution.")

    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_recommendations.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/audit/recommendations.py tests/test_recommendations.py
git commit -m "feat(audit): add template-based recommendation generator"
```

---

### Task 3: Risk Score Calculator

**Files:**
- Modify: `src/codrag/core/audit/recommendations.py`
- Test: `tests/test_recommendations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recommendations.py`:

```python
from codrag.core.audit.recommendations import compute_risk_score


def test_risk_score_critical_hub_with_concept():
    score = compute_risk_score(
        hub_percentile=0.95,
        has_constraint_concept=True,
        has_architecture_concept=False,
        observation_score=0.5,
        churn_score=0.3,
    )
    # 0.40*0.95 + 0.30*1.0 + 0.20*0.5 + 0.10*0.3 = 0.38 + 0.30 + 0.10 + 0.03 = 0.81
    assert abs(score - 0.81) < 0.01


def test_risk_score_leaf_file():
    score = compute_risk_score(
        hub_percentile=0.1,
        has_constraint_concept=False,
        has_architecture_concept=False,
        observation_score=0.0,
        churn_score=0.1,
    )
    # 0.40*0.1 + 0.30*0.0 + 0.20*0.0 + 0.10*0.1 = 0.04 + 0 + 0 + 0.01 = 0.05
    assert abs(score - 0.05) < 0.01


def test_risk_score_clamped_0_to_1():
    score = compute_risk_score(
        hub_percentile=1.0,
        has_constraint_concept=True,
        observation_score=1.0,
        churn_score=1.0,
    )
    assert 0.0 <= score <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_recommendations.py::test_risk_score_critical_hub_with_concept -v`
Expected: FAIL with `ImportError: cannot import name 'compute_risk_score'`

- [ ] **Step 3: Implement risk score calculator**

Add to `src/codrag/core/audit/recommendations.py`:

```python
# Default weights — configurable via settings
_WEIGHTS = {
    "hub": 0.40,
    "concept": 0.30,
    "observation": 0.20,
    "churn": 0.10,
}


def compute_risk_score(
    hub_percentile: float,
    has_constraint_concept: bool = False,
    has_architecture_concept: bool = False,
    observation_score: float = 0.0,
    churn_score: float = 0.0,
    weights: Optional[dict] = None,
) -> float:
    """Compute composite risk score for a file.

    Args:
        hub_percentile: 0-1, where the file sits in the dependent count distribution
        has_constraint_concept: True if an active constraint concept is anchored here
        has_architecture_concept: True if an active architecture concept is anchored here
        observation_score: 0-1, based on recency and frequency of observations
        churn_score: 0-1, based on git change frequency
        weights: Optional override for weight dict

    Returns:
        Float 0-1 risk score.
    """
    w = weights or _WEIGHTS

    concept_score = 1.0 if has_constraint_concept else (0.5 if has_architecture_concept else 0.0)

    raw = (
        w["hub"] * hub_percentile
        + w["concept"] * concept_score
        + w["observation"] * observation_score
        + w["churn"] * churn_score
    )
    return max(0.0, min(1.0, raw))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_recommendations.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/audit/recommendations.py tests/test_recommendations.py
git commit -m "feat(audit): add configurable risk score calculator"
```

---

### Task 4: Structural Audit Scanner

**Files:**
- Create: `src/codrag/core/audit/structural.py`
- Test: `tests/test_structural_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_structural_audit.py
import pytest
from codrag.core.audit.structural import run_structural_audit, StructuralFinding


def _make_mock_context():
    """Create a minimal mock of the data needed for structural audit."""
    return {
        "hub_files": [
            ("src/server.py", 25),
            ("src/utils.py", 12),
            ("src/leaf.py", 2),
        ],
        "cycles": [
            ["src/a.py", "src/b.py", "src/c.py"],
        ],
        "modules": [
            {"name": "core", "member_files": ["src/server.py", "src/utils.py"]},
            {"name": "helpers", "member_files": ["src/leaf.py"]},
        ],
        "concepts": [],
        "observations": [],
        "total_files": 50,
    }


def test_structural_returns_findings():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    assert isinstance(findings, list)
    assert len(findings) > 0
    assert all(isinstance(f, StructuralFinding) for f in findings)


def test_structural_detects_hub_hotspots():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    hub_findings = [f for f in findings if f.finding_type == "coupling_hotspot"]
    assert len(hub_findings) >= 1
    assert "server.py" in hub_findings[0].file_path


def test_structural_detects_cycles():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    cycle_findings = [f for f in findings if f.finding_type == "import_cycle"]
    assert len(cycle_findings) >= 1


def test_structural_no_duplicates():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    # Each file should appear at most once per finding type
    seen = set()
    for f in findings:
        key = (f.finding_type, f.file_path)
        assert key not in seen, f"Duplicate finding: {key}"
        seen.add(key)


def test_structural_excludes_generated_files():
    ctx = _make_mock_context()
    ctx["hub_files"].append(("package-lock.json", 30))
    findings = run_structural_audit(ctx)
    paths = [f.file_path for f in findings]
    assert "package-lock.json" not in paths


def test_structural_under_20_findings():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    assert len(findings) <= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_structural_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codrag.core.audit.structural'`

- [ ] **Step 3: Implement structural audit scanner**

```python
# src/codrag/core/audit/structural.py
"""Structural-only audit scanner.

Returns ONLY findings that are unique to CoDRAG's structural knowledge:
coupling hotspots, import cycles, hub concentration risk, module boundary
violations. Drops everything linters already catch.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .recommendations import compute_risk_score, generate_recommendation

# Files that should never appear in findings
_GENERATED_FILE_PATTERNS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "poetry.lock", "Pipfile.lock",
}
_GENERATED_FILE_SUFFIXES = {".d.ts", ".min.js", ".min.css", ".generated.ts", ".generated.py"}


@dataclass
class StructuralFinding:
    """A structural audit finding unique to CoDRAG."""
    finding_type: str       # coupling_hotspot | hub_concentration | import_cycle | module_boundary
    file_path: str          # Primary file (or "" for cycle findings)
    severity: str           # critical | warning | info
    title: str
    description: str
    risk_score: float
    recommendation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    related_concepts: List[str] = field(default_factory=list)
    related_observations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "file_path": self.file_path,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "risk_score": self.risk_score,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "related_concepts": self.related_concepts,
            "related_observations": self.related_observations,
        }


def _is_generated(path: str) -> bool:
    """Check if a file path is a generated/lock file."""
    import os
    basename = os.path.basename(path)
    if basename in _GENERATED_FILE_PATTERNS:
        return True
    return any(path.endswith(suffix) for suffix in _GENERATED_FILE_SUFFIXES)


def _hub_percentile(in_degree: int, all_degrees: List[int]) -> float:
    """Compute where a file sits in the in-degree distribution (0-1)."""
    if not all_degrees:
        return 0.0
    count_below = sum(1 for d in all_degrees if d < in_degree)
    return count_below / len(all_degrees)


def run_structural_audit(
    ctx: Dict[str, Any],
    max_findings: int = 20,
) -> List[StructuralFinding]:
    """Run structural-only audit.

    Args:
        ctx: Dictionary with keys:
            - hub_files: List[Tuple[str, int]] — (file_path, in_degree)
            - cycles: List[List[str]] — import cycle lists
            - modules: List[Dict] — module definitions with member_files
            - concepts: List[Dict] — relevant concepts
            - observations: List[Dict] — relevant observations
            - total_files: int — total file count in project
        max_findings: Cap on returned findings (default 20)

    Returns:
        List of StructuralFinding, deduplicated and sorted by risk score.
    """
    findings: List[StructuralFinding] = []
    hub_files = ctx.get("hub_files", [])
    cycles = ctx.get("cycles", [])
    concepts = ctx.get("concepts", [])
    observations = ctx.get("observations", [])
    total_files = ctx.get("total_files", 0)

    all_degrees = [deg for _, deg in hub_files]

    # --- Coupling hotspots ---
    if all_degrees and len(all_degrees) >= 5:
        mean_deg = statistics.mean(all_degrees)
        stdev_deg = statistics.stdev(all_degrees) if len(all_degrees) > 1 else 0.0

        for file_path, in_degree in hub_files:
            if _is_generated(file_path):
                continue
            if in_degree < 8:
                continue
            z = (in_degree - mean_deg) / stdev_deg if stdev_deg > 0 else 0.0
            if z < 2.0:
                continue

            percentile = _hub_percentile(in_degree, all_degrees)
            severity = "critical" if z >= 3.0 else "warning"

            # Find related concepts and observations for this file
            file_concepts = [c.get("title", "") for c in concepts
                            if file_path in c.get("anchors", [])]
            file_obs = [o.get("content", "")[:100] for o in observations
                       if o.get("file_path") == file_path]

            risk = compute_risk_score(
                hub_percentile=percentile,
                has_constraint_concept=any(
                    c.get("category") == "constraint" for c in concepts
                    if file_path in c.get("anchors", [])
                ),
                has_architecture_concept=any(
                    c.get("category") == "architecture" for c in concepts
                    if file_path in c.get("anchors", [])
                ),
                observation_score=min(1.0, len(file_obs) * 0.25),
            )

            rec = generate_recommendation(
                hub_status="critical" if z >= 3.0 else "high",
                dependents=in_degree,
                concepts=file_concepts,
                observations=file_obs,
            )

            findings.append(StructuralFinding(
                finding_type="coupling_hotspot",
                file_path=file_path,
                severity=severity,
                title=f"Coupling hotspot: {file_path} ({in_degree} dependents)",
                description=(
                    f"{file_path} is imported by {in_degree} other files "
                    f"(z-score={z:.1f}). Changes here have a large blast radius."
                ),
                risk_score=risk,
                recommendation=rec,
                evidence={"in_degree": in_degree, "z_score": round(z, 2), "percentile": round(percentile, 2)},
                related_concepts=file_concepts,
                related_observations=file_obs,
            ))

    # --- Import cycles ---
    for cycle in cycles:
        if len(cycle) < 2:
            continue
        cycle_filtered = [p for p in cycle if not _is_generated(p)]
        if len(cycle_filtered) < 2:
            continue

        severity = "critical" if len(cycle) >= 4 else "warning"
        cycle_display = " \u2192 ".join(cycle[:6])
        if len(cycle) > 6:
            cycle_display += f" \u2192 ... ({len(cycle)} total)"

        findings.append(StructuralFinding(
            finding_type="import_cycle",
            file_path=cycle[0],  # Use first file as primary
            severity=severity,
            title=f"Import cycle: {len(cycle)} files",
            description=f"Circular dependency: {cycle_display}",
            risk_score=min(1.0, 0.3 + len(cycle) * 0.1),
            recommendation=(
                "Break the cycle by extracting shared interfaces or "
                "using dependency injection. Identify the lowest-cost edge to remove."
            ),
            evidence={"cycle_length": len(cycle), "cycle": cycle[:10]},
        ))

    # --- Deduplicate (one file per finding_type) ---
    seen = set()
    deduped = []
    for f in findings:
        key = (f.finding_type, f.file_path)
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    # Sort by risk score descending, cap at max_findings
    deduped.sort(key=lambda f: -f.risk_score)
    return deduped[:max_findings]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_structural_audit.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/audit/structural.py tests/test_structural_audit.py
git commit -m "feat(audit): add structural-only audit scanner"
```

---

### Task 5: Enrichment Engine

**Files:**
- Create: `src/codrag/core/enrichment.py`
- Test: `tests/test_enrichment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrichment.py
import pytest
from codrag.core.enrichment import enrich_findings, EnrichedFinding


def _make_finding(file="src/server.py", line=42, message="Too complex", severity="warning", tool="ruff"):
    return {"file": file, "line": line, "message": message, "severity": severity, "tool": tool}


def _make_context():
    """Mock context provider that returns structural data for known files."""
    return {
        "src/server.py": {
            "dependents": 23,
            "hub_status": "critical",
            "module": "mcp",
            "concepts": ["Planned refactor: split handler dispatch"],
            "observations": ["2026-03-15: Growing concern"],
        },
        "src/leaf.py": {
            "dependents": 1,
            "hub_status": "low",
            "module": "helpers",
            "concepts": [],
            "observations": [],
        },
    }


def test_enrich_known_file():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.codrag is not None
    assert f.codrag["dependents"] == 23
    assert f.codrag["hub_status"] == "critical"
    assert len(f.codrag["concepts"]) == 1


def test_enrich_unknown_file_shows_stale_message():
    findings = [_make_finding(file="src/unknown.py")]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert result.stale_data_warning is True


def test_enrich_includes_risk_score():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert 0.0 <= result.findings[0].codrag["risk_score"] <= 1.0


def test_enrich_summary():
    findings = [_make_finding(), _make_finding(file="src/leaf.py")]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert result.summary["total"] == 2
    assert result.summary["enriched"] == 2
    assert result.summary["high_risk"] >= 1


def test_enrich_respects_max_findings():
    findings = [_make_finding(file=f"src/file{i}.py") for i in range(300)]
    ctx = _make_context()
    result = enrich_findings(findings, ctx, max_findings=200)
    assert len(result.findings) <= 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_enrichment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codrag.core.enrichment'`

- [ ] **Step 3: Implement enrichment engine**

```python
# src/codrag/core/enrichment.py
"""Finding enrichment engine for codrag_audit.

Accepts external findings (V1 simple schema) and annotates each with
CoDRAG structural context: dependent count, hub status, concepts,
observations, risk score, and recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from codrag.core.audit.recommendations import compute_risk_score, generate_recommendation


@dataclass
class EnrichedFinding:
    """An external finding annotated with CoDRAG context."""
    file: str
    line: int
    message: str
    severity: str
    tool: str
    codrag: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "severity": self.severity,
            "tool": self.tool,
        }
        if self.codrag is not None:
            d["codrag"] = self.codrag
        return d


@dataclass
class EnrichmentResult:
    """Result of enriching a set of external findings."""
    findings: List[EnrichedFinding]
    summary: Dict[str, Any]
    stale_data_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }
        if self.stale_data_warning:
            d["message"] = (
                "Looks like you have stale data, "
                "CoDRAG recommends running enrichment again."
            )
        return d


def _hub_status_from_dependents(dependents: int) -> str:
    """Map dependent count to hub status label."""
    if dependents >= 20:
        return "critical"
    elif dependents >= 10:
        return "high"
    elif dependents >= 5:
        return "moderate"
    return "low"


def enrich_findings(
    findings: List[Dict[str, Any]],
    context: Dict[str, Dict[str, Any]],
    max_findings: int = 200,
) -> EnrichmentResult:
    """Enrich external findings with CoDRAG structural context.

    Args:
        findings: List of dicts with keys: file, line, message, severity, tool
        context: Dict mapping file_path -> structural context dict with keys:
            dependents (int), hub_status (str), module (str),
            concepts (List[str]), observations (List[str])
        max_findings: Maximum findings to enrich (default 200)

    Returns:
        EnrichmentResult with enriched findings and summary.
    """
    enriched: List[EnrichedFinding] = []
    stale = False
    enriched_count = 0
    high_risk_count = 0

    for raw in findings[:max_findings]:
        file_path = raw.get("file", "")
        ef = EnrichedFinding(
            file=file_path,
            line=raw.get("line", 0),
            message=raw.get("message", ""),
            severity=raw.get("severity", "info"),
            tool=raw.get("tool", "unknown"),
        )

        file_ctx = context.get(file_path)
        if file_ctx is None:
            stale = True
            enriched.append(ef)
            continue

        dependents = file_ctx.get("dependents", 0)
        hub_status = file_ctx.get("hub_status", _hub_status_from_dependents(dependents))
        concepts = file_ctx.get("concepts", [])
        observations = file_ctx.get("observations", [])
        module = file_ctx.get("module", "")

        risk = compute_risk_score(
            hub_percentile=min(1.0, dependents / 30.0),  # Rough normalization
            has_constraint_concept=False,  # V1: simple concept presence
            has_architecture_concept=len(concepts) > 0,
            observation_score=min(1.0, len(observations) * 0.25),
        )

        rec = generate_recommendation(
            hub_status=hub_status,
            dependents=dependents,
            concepts=concepts,
            observations=observations,
        )

        ef.codrag = {
            "dependents": dependents,
            "hub_status": hub_status,
            "module": module,
            "concepts": concepts,
            "observations": observations,
            "risk_score": round(risk, 2),
            "recommendation": rec,
        }

        enriched_count += 1
        if risk >= 0.6:
            high_risk_count += 1

        enriched.append(ef)

    summary = {
        "total": len(enriched),
        "enriched": enriched_count,
        "unenriched": len(enriched) - enriched_count,
        "high_risk": high_risk_count,
    }

    return EnrichmentResult(
        findings=enriched,
        summary=summary,
        stale_data_warning=stale,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_enrichment.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/enrichment.py tests/test_enrichment.py
git commit -m "feat(audit): add finding enrichment engine"
```

---

### Task 6: Update MCP Tool Schema

**Files:**
- Modify: `src/codrag/mcp_tools.py:170-225`

- [ ] **Step 1: Read the current schema**

Run: `.venv/bin/python -c "from codrag.mcp_tools import MCP_TOOLS; t = [t for t in MCP_TOOLS if t['name'] == 'codrag_audit'][0]; print(t['inputSchema']['properties'].keys())"`

- [ ] **Step 2: Update the codrag_audit schema**

In `src/codrag/mcp_tools.py`, replace the `codrag_audit` tool definition (lines 170-225) with:

```python
    # ── 4. codrag_audit (codebase health) ───────────────────────────
    {
        "name": "codrag_audit",
        "description": (
            "Codebase structural intelligence and finding enrichment. "
            "Two modes: (1) Call with no 'findings' param to get CoDRAG's own "
            "structural insights — coupling hotspots, import cycles, hub concentration, "
            "concept violations. These are things only CoDRAG can see. "
            "(2) Call with 'findings' param to enrich external lint/analysis results "
            "with structural context — dependent counts, hub status, related concepts, "
            "risk scores. Pipe ruff/eslint/semgrep output through here to make findings "
            "actionable. "
            "Legacy actions ('refactor', 'verify', 'report', 'advise') still work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Operation mode. 'scan' (default) runs structural-only audit. "
                        "'refactor', 'verify', 'report', 'advise' are legacy actions."
                    ),
                    "enum": ["scan", "refactor", "verify", "report", "advise"],
                    "default": "scan",
                },
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string", "description": "File path"},
                            "line": {"type": "integer", "description": "Line number"},
                            "message": {"type": "string", "description": "Finding message"},
                            "severity": {"type": "string", "description": "warning/error/info"},
                            "tool": {"type": "string", "description": "Source tool (ruff, eslint, etc.)"},
                        },
                        "required": ["file", "message"],
                    },
                    "description": (
                        "External findings to enrich. When provided, CoDRAG annotates each "
                        "finding with structural context (dependents, hub status, concepts, "
                        "risk score). Omit to get CoDRAG's own structural findings."
                    ),
                },
                "scope": {
                    "type": "string",
                    "description": "Limit structural scan to a specific file or directory path.",
                },
                "category": {
                    "type": "string",
                    "description": "(scan) Filter structural findings by type.",
                    "enum": ["coupling", "cycles", "hub_concentration", "concept_violation"],
                },
                "synthesize": {
                    "type": "boolean",
                    "description": "(legacy scan) Also generate LLM-written markdown reports. Default: false.",
                    "default": False,
                },
                "finding_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "(refactor) IDs of findings to address.",
                },
                "instructions": {
                    "type": "string",
                    "description": "(refactor) Additional instructions for the refactoring approach.",
                },
                "analyzers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "(verify) Analyzer names to re-run.",
                },
                "report_name": {
                    "type": "string",
                    "description": "(report) Name of the report to retrieve.",
                    "enum": ["AUDIT_SUMMARY", "ARCHITECTURE_ANALYSIS", "GAP_ANALYSIS", "COMPONENT_INVENTORY", "TECH_DEBT_REPORT"],
                },
                "max_findings": {
                    "type": "integer",
                    "description": "Maximum findings to return/enrich. Default: 200 for enrichment, 20 for structural.",
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": [],
        },
        "annotations": {"title": "CoDRAG: Codebase Audit", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
```

- [ ] **Step 3: Verify schema loads**

Run: `.venv/bin/python -c "from codrag.mcp_tools import MCP_TOOLS; t = [t for t in MCP_TOOLS if t['name'] == 'codrag_audit'][0]; print('findings' in t['inputSchema']['properties'])"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add src/codrag/mcp_tools.py
git commit -m "feat(audit): update MCP schema with findings param and structural categories"
```

---

### Task 7: Wire MCP Server Routing

**Files:**
- Modify: `src/codrag/mcp/server.py:3248-3281` (audit dispatch)
- Modify: `src/codrag/mcp/server.py` (add new handler methods)

- [ ] **Step 1: Add the structural audit handler method**

Add this method to the `CodragMcpServer` class in `server.py` (after the existing `tool_audit` method around line 1842):

```python
    async def tool_audit_structural(
        self,
        category: Optional[str] = None,
        scope: Optional[str] = None,
        max_findings: int = 20,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run structural-only audit — CoDRAG-unique findings only."""
        project_id = await self._resolve_project_id(override=project_override)

        # Get hub files from trace graph
        hub_data = await self._api_get(
            f"/projects/{project_id}/trace/hub-files?k=50"
        )
        hub_files = []
        if isinstance(hub_data, dict):
            for item in hub_data.get("hub_files", []):
                hub_files.append((item.get("file_path", ""), item.get("in_degree", 0)))

        # Get cycles from audit (reuse circular deps analyzer)
        cycles = []
        try:
            audit_data = await self._api_get(f"/projects/{project_id}/audit/findings?limit=500")
            all_findings = audit_data.get("findings", []) if isinstance(audit_data, dict) else []
            for f in all_findings:
                if f.get("analyzer") == "circular_deps":
                    cycle = f.get("evidence", {}).get("cycle", [])
                    if cycle:
                        cycles.append(cycle)
        except Exception:
            pass

        # Get modules
        modules = []
        try:
            mod_data = await self._api_get(f"/projects/{project_id}/trace/modules")
            if isinstance(mod_data, dict):
                modules = mod_data.get("modules", [])
        except Exception:
            pass

        # Get concepts and observations
        concepts = []
        observations = []
        try:
            from codrag.services.concept_store import ConceptStore
            from codrag.services.observation_store import ObservationStore
            concept_store = ConceptStore()
            obs_store = ObservationStore()
            concepts = [c.__dict__ if hasattr(c, '__dict__') else c
                       for c in concept_store.list_concepts(project_id)]
            observations = [o.__dict__ if hasattr(o, '__dict__') else o
                          for o in obs_store.get_recent(project_id, limit=50)]
        except Exception:
            pass

        from codrag.core.audit.structural import run_structural_audit

        ctx = {
            "hub_files": hub_files,
            "cycles": cycles,
            "modules": modules,
            "concepts": concepts,
            "observations": observations,
            "total_files": len(hub_files),
        }

        findings = run_structural_audit(ctx, max_findings=max_findings)

        # Format as markdown
        md_lines = [f"## Structural Audit ({len(findings)} findings)\n"]
        for f in findings:
            md_lines.append(f"- **[{f.severity}] {f.title}**")
            md_lines.append(f"  Risk: {f.risk_score:.2f} | {f.recommendation}")
            if f.related_concepts:
                md_lines.append(f"  Concepts: {', '.join(f.related_concepts[:3])}")
        md = "\n".join(md_lines)

        return {
            "project_id": project_id,
            "total_findings": len(findings),
            "findings": [f.to_dict() for f in findings],
            "_to_markdown": md,
        }
```

- [ ] **Step 2: Add the enrichment handler method**

Add this method after the structural handler:

```python
    async def tool_audit_enrich(
        self,
        findings: List[Dict[str, Any]],
        max_findings: int = 200,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enrich external findings with CoDRAG structural context."""
        project_id = await self._resolve_project_id(override=project_override)

        # Collect unique file paths from findings
        file_paths = list(set(f.get("file", "") for f in findings if f.get("file")))

        # Build context for each file
        context: Dict[str, Dict[str, Any]] = {}
        for file_path in file_paths:
            file_ctx: Dict[str, Any] = {
                "dependents": 0,
                "hub_status": "low",
                "module": "",
                "concepts": [],
                "observations": [],
            }

            # Get dependent count from trace graph
            try:
                node_id = f"file:{file_path}"
                data = await self._api_get(
                    f"/projects/{project_id}/trace/neighbors/{node_id}?direction=in&max_nodes=100"
                )
                if isinstance(data, dict):
                    in_nodes = data.get("in_nodes", data.get("nodes", []))
                    file_ctx["dependents"] = len(in_nodes)
            except Exception:
                pass

            # Get module membership
            try:
                mod_data = await self._api_get(f"/projects/{project_id}/trace/modules")
                if isinstance(mod_data, dict):
                    for mod in mod_data.get("modules", []):
                        if file_path in mod.get("member_files", []):
                            file_ctx["module"] = mod.get("name", "")
                            break
            except Exception:
                pass

            # Get concepts for this file
            try:
                from codrag.services.concept_store import ConceptStore
                store = ConceptStore()
                file_concepts = store.search(project_id, file_path, limit=5)
                file_ctx["concepts"] = [c.title if hasattr(c, 'title') else str(c)
                                       for c in file_concepts]
            except Exception:
                pass

            # Get observations for this file
            try:
                from codrag.services.observation_store import ObservationStore
                store = ObservationStore()
                file_obs = store.get_for_file(project_id, file_path)
                file_ctx["observations"] = [o.content[:100] if hasattr(o, 'content') else str(o)[:100]
                                           for o in file_obs[:5]]
            except Exception:
                pass

            # Compute hub status
            dep_count = file_ctx["dependents"]
            if dep_count >= 20:
                file_ctx["hub_status"] = "critical"
            elif dep_count >= 10:
                file_ctx["hub_status"] = "high"
            elif dep_count >= 5:
                file_ctx["hub_status"] = "moderate"

            context[file_path] = file_ctx

        from codrag.core.enrichment import enrich_findings

        result = enrich_findings(findings, context, max_findings=max_findings)
        output = result.to_dict()
        output["project_id"] = project_id

        # Generate markdown summary
        md_lines = [f"## Enrichment Results ({result.summary['total']} findings)\n"]
        md_lines.append(f"Enriched: {result.summary['enriched']} | "
                       f"High risk: {result.summary['high_risk']} | "
                       f"Unenriched: {result.summary['unenriched']}\n")
        if result.stale_data_warning:
            md_lines.append("> Looks like you have stale data, CoDRAG recommends running enrichment again.\n")
        for ef in result.findings[:15]:
            if ef.codrag:
                md_lines.append(f"- **[{ef.codrag['hub_status']}] {ef.file}:{ef.line}** — {ef.message}")
                md_lines.append(f"  {ef.codrag['recommendation']}")
            else:
                md_lines.append(f"- {ef.file}:{ef.line} — {ef.message} (not enriched)")
        output["_to_markdown"] = "\n".join(md_lines)

        return output
```

- [ ] **Step 3: Update the dispatch routing**

Replace the audit dispatch block at lines 3248-3281 with:

```python
            elif name == "codrag_audit":
                # Phase 83: Dual-mode audit — enrichment vs structural
                ext_findings = args.get("findings")
                if ext_findings is not None:
                    # Enrichment mode: annotate external findings
                    result = await self.tool_audit_enrich(
                        findings=ext_findings,
                        max_findings=args.get("max_findings", 200),
                        project_override=project_override,
                    )
                else:
                    action = args.get("action", "scan")
                    if action == "refactor":
                        result = await self.tool_audit_refactor(
                            finding_ids=args.get("finding_ids", []),
                            instructions=args.get("instructions"),
                            project_override=project_override,
                        )
                    elif action == "verify":
                        result = await self.tool_audit_check(
                            analyzers=args.get("analyzers", []),
                            project_override=project_override,
                        )
                    elif action == "report":
                        result = await self.tool_audit_report(
                            report_name=args.get("report_name", ""),
                            project_override=project_override,
                        )
                    elif action == "advise":
                        result = await self.tool_advise(
                            project_override=project_override,
                        )
                    elif action == "roadmap":
                        result = await self.tool_roadmap(
                            tier=args.get("tier"),
                            project_override=project_override,
                        )
                    else:
                        # Default: structural scan (Phase 83 replacement)
                        result = await self.tool_audit_structural(
                            category=args.get("category"),
                            scope=args.get("scope"),
                            max_findings=args.get("max_findings", 20),
                            project_override=project_override,
                        )
```

- [ ] **Step 4: Verify the server module loads**

Run: `.venv/bin/python -c "from codrag.mcp.server import CodragMcpServer; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "feat(audit): wire structural + enrichment modes into MCP dispatch"
```

---

### Task 8: P0 Fix — Impact Markdown Formatting

**Files:**
- Modify: `src/codrag/mcp/server.py` (tool_trace_neighbors, around line 1365)

- [ ] **Step 1: Read the current tool_trace_neighbors output**

The function at line 1365 returns raw JSON with `nodes` and `edges` arrays but no `_to_markdown` field. The `tool_impact` function (line 1438) already has markdown formatting. We need to add markdown to `tool_trace_neighbors`.

- [ ] **Step 2: Add markdown formatting to tool_trace_neighbors**

After the return dict is built in `tool_trace_neighbors` (around line 1406-1413), add markdown generation before the return statement:

```python
        # Phase 83 P0: Format as markdown for consistency with other tools
        md_lines = [f"## Neighbors for {node_id}\n"]
        md_lines.append(f"Nodes: {len(nodes)} | Edges: {len(edges)}\n")
        center_name = center.get("name", node_id) if isinstance(center, dict) else node_id
        md_lines.append(f"Center: {center_name}\n")
        for n in nodes[:max_nodes]:
            name = n.get("name", n.get("id", "?"))
            kind = n.get("kind", "")
            path = n.get("file_path", "")
            md_lines.append(f"  - {name} ({path}) [{kind}]")

        result = {
            "project_id": project_id,
            "center": center,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes[:max_nodes],
            "edges": edges[:50],
            "_to_markdown": "\n".join(md_lines),
        }
        return result
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "fix(impact): add markdown formatting to direction=all/dependencies"
```

---

### Task 9: P0 Fix — Filter Stdlib from Impact

**Files:**
- Modify: `src/codrag/mcp/server.py` (tool_trace_neighbors and tool_impact)

- [ ] **Step 1: Add stdlib filtering to tool_trace_neighbors**

In `tool_trace_neighbors`, after receiving `nodes` from the API (around line 1403), filter out external/stdlib nodes:

```python
        # Phase 83 P0: Filter stdlib/external nodes by default
        include_external = False  # Could be parameterized later
        if not include_external:
            nodes = [n for n in nodes if n.get("kind") != "external_module"
                     and not n.get("id", "").startswith("ext:")]
            edges = [e for e in edges
                     if not e.get("target", "").startswith("ext:")
                     and not e.get("source", "").startswith("ext:")]
```

- [ ] **Step 2: Add stdlib filtering to tool_impact**

In `tool_impact` (around line 1480), after receiving `dependents`, filter:

```python
        # Phase 83 P0: Filter stdlib/external from dependents
        dependents = [d for d in dependents
                     if d.get("kind") != "external_module"
                     and not d.get("id", "").startswith("ext:")]
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "fix(impact): filter stdlib/external nodes from impact results"
```

---

### Task 10: P0 Fix — Search Symbol Context

**Files:**
- Modify: `src/codrag/mcp/server.py` (find `tool_trace_search` or symbol search handler)

- [ ] **Step 1: Find the symbol search handler**

Run: `.venv/bin/grep -n "tool_trace_search\|symbol.*search" src/codrag/mcp/server.py | head -10`

- [ ] **Step 2: Add code context to symbol results**

In the symbol search handler, ensure each result includes: `qualified_name`, `signature` (first line of function), `line_number`, and `docstring` (first line). These fields should already be available from the trace node data — the fix is ensuring they're included in the response dict, not stripped for token efficiency.

Locate where symbol search results are formatted and ensure these fields pass through:

```python
            entry = {
                "name": node.get("name", ""),
                "file_path": node.get("file_path", ""),
                "kind": node.get("kind", ""),
                # Phase 83 P0: Include code context
                "qualified_name": node.get("qualified_name", node.get("name", "")),
                "line_number": node.get("line_start", node.get("line", 0)),
                "signature": node.get("signature", ""),
                "docstring": (node.get("docstring", "") or "")[:200],
            }
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "fix(search): include qualified name, signature, line number in symbol results"
```

---

### Task 11: Integration Test — Dogfood on CoDRAG

**Files:**
- No new files — manual testing

- [ ] **Step 1: Test structural mode via MCP**

Start the daemon and test:

```bash
# Terminal 1: start daemon
.venv/bin/codrag serve

# Terminal 2: test structural audit
.venv/bin/python -c "
import asyncio, json
from codrag.mcp.server import CodragMcpServer
async def main():
    s = CodragMcpServer()
    await s.initialize()
    result = await s.handle_tools_call({
        'name': 'codrag_audit',
        'arguments': {'project_id': '1d6f0b35-45cb-427b-ae9d-aac3c6371a4b'}
    })
    print(json.dumps(result, indent=2, default=str)[:3000])
asyncio.run(main())
"
```

Expected: <20 structural findings, no generated file findings, no duplicates.

- [ ] **Step 2: Test enrichment mode**

```bash
.venv/bin/python -c "
import asyncio, json, subprocess
from codrag.mcp.server import CodragMcpServer

# Get ruff findings
ruff_out = subprocess.run(
    ['.venv/bin/ruff', 'check', 'src/', '--output-format', 'json'],
    capture_output=True, text=True
)
ruff_findings = json.loads(ruff_out.stdout) if ruff_out.stdout else []

# Convert to simple schema
findings = [
    {'file': f['filename'], 'line': f['location']['row'],
     'message': f['message'], 'severity': 'warning', 'tool': 'ruff'}
    for f in ruff_findings[:20]
]

async def main():
    s = CodragMcpServer()
    await s.initialize()
    result = await s.handle_tools_call({
        'name': 'codrag_audit',
        'arguments': {
            'findings': findings,
            'project_id': '1d6f0b35-45cb-427b-ae9d-aac3c6371a4b',
        }
    })
    print(json.dumps(result, indent=2, default=str)[:3000])
asyncio.run(main())
"
```

Expected: Each finding enriched with dependents, hub_status, risk_score. Summary shows counts.

- [ ] **Step 3: Test impact markdown (P0 fix)**

```bash
.venv/bin/python -c "
import asyncio, json
from codrag.mcp.server import CodragMcpServer
async def main():
    s = CodragMcpServer()
    await s.initialize()
    result = await s.handle_tools_call({
        'name': 'codrag_impact',
        'arguments': {
            'file_path': 'src/codrag/mcp/server.py',
            'direction': 'all',
            'project_id': '1d6f0b35-45cb-427b-ae9d-aac3c6371a4b',
        }
    })
    md = result.get('_to_markdown', 'NO MARKDOWN')
    print(md[:1500])
asyncio.run(main())
"
```

Expected: Formatted markdown, not raw JSON. No `ext:` or stdlib entries.

- [ ] **Step 4: Commit any fixes found during integration testing**

```bash
git add -u
git commit -m "fix(audit): integration test fixes for Phase 83"
```
