# Phase 84: Concepts Formalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve `prep_concepts` from free-text notes into structured assertions with doc links, conflict detection, and observation-promotion — making concepts load-bearing for Phase 83's audit violations and Phase 87's immune system.

**Architecture:** Extend the existing `Concept` dataclass and SQLite schema with three new fields (`assertion`, `doc_links`, `superseded_by`). Add conflict detection logic that flags contradictory active concepts. Add an observation-promotion flow that suggests converting durable observations into structured concepts. Keep all changes backward-compatible — existing concepts continue to work, new fields are optional for migration.

**Tech Stack:** Python 3.11, SQLite (concept_store), existing MCP tool infrastructure.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/prep/services/concept_store.py` | **Modify** | Add `assertion`, `doc_links`, `superseded_by` fields to Concept model + SQLite schema migration |
| `src/prep/core/concept_conflicts.py` | **Create** | Conflict detection: find contradictory active concepts by shared anchors |
| `src/prep/core/concept_promotion.py` | **Create** | Observation → concept promotion: suggest, preview, confirm |
| `src/prep/mcp_tools.py` | **Modify** | Add assertion, doc_links, superseded_by params to prep_concepts schema |
| `src/prep/mcp/server.py` | **Modify** | Wire new params through to concept_store, add conflict detection to audit |
| `tests/test_concept_store_v2.py` | **Create** | Tests for new concept fields and migration |
| `tests/test_concept_conflicts.py` | **Create** | Tests for conflict detection |
| `tests/test_concept_promotion.py` | **Create** | Tests for observation promotion |

---

### Task 1: Schema Migration — Add New Fields to Concept Model

**Files:**
- Modify: `src/prep/services/concept_store.py`
- Create: `tests/test_concept_store_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concept_store_v2.py
import pytest
from prep.services.concept_store import ConceptStore, Concept
from pathlib import Path
import tempfile


@pytest.fixture
def store(tmp_path):
    s = ConceptStore()
    s.init(tmp_path / "test_concepts.db")
    yield s
    s.close()


def test_concept_has_assertion_field():
    c = Concept(
        id="test-1", project_id="proj-1", title="Zero-LLM Pi Agent",
        content="Pi Agent must never import LLM libraries",
        assertion="pi_agent.py does not import llm_client, openai, or anthropic",
        category="constraint", status="active",
    )
    assert c.assertion == "pi_agent.py does not import llm_client, openai, or anthropic"


def test_concept_has_doc_links_field():
    c = Concept(
        id="test-2", project_id="proj-1", title="Design System",
        content="Component library architecture",
        doc_links=[
            {"path": "packages/ui/src/components/", "label": "Component root", "type": "source"},
            {"path": "docs/design-system.md", "label": "Design docs", "type": "doc"},
        ],
        category="architecture", status="active",
    )
    assert len(c.doc_links) == 2
    assert c.doc_links[0]["path"] == "packages/ui/src/components/"


def test_concept_has_superseded_by_field():
    c = Concept(
        id="test-3", project_id="proj-1", title="Old auth approach",
        content="Use JWT tokens",
        status="superseded", superseded_by="test-4",
        category="architecture",
    )
    assert c.superseded_by == "test-4"
    assert c.status == "superseded"


def test_concept_defaults_new_fields_to_empty():
    c = Concept(
        id="test-5", project_id="proj-1", title="Basic concept",
        content="Just a note", category="technical", status="seed",
    )
    assert c.assertion == ""
    assert c.doc_links == []
    assert c.superseded_by is None


def test_save_and_retrieve_with_new_fields(store):
    concept_id = store.save(
        project_id="proj-1",
        title="Zero-LLM Pi Agent",
        content="Pi Agent must never import LLM libraries",
        assertion="pi_agent.py does not import llm_client",
        doc_links=[{"path": "src/pi_agent.py", "label": "Pi Agent", "type": "source"}],
        category="constraint",
        status="active",
    )
    assert concept_id is not None

    retrieved = store.get(concept_id)
    assert retrieved is not None
    assert retrieved.assertion == "pi_agent.py does not import llm_client"
    assert len(retrieved.doc_links) == 1
    assert retrieved.doc_links[0]["path"] == "src/pi_agent.py"


def test_supersede_concept(store):
    old_id = store.save(
        project_id="proj-1", title="Old approach",
        content="Use JWT", category="architecture",
    )
    new_id = store.save(
        project_id="proj-1", title="New approach",
        content="Use session tokens", category="architecture",
    )
    store.supersede(old_id, new_id)

    old = store.get(old_id)
    assert old.status == "superseded"
    assert old.superseded_by == new_id


def test_backward_compat_concepts_without_new_fields(store):
    """Old concepts saved without assertion/doc_links should still load."""
    concept_id = store.save(
        project_id="proj-1", title="Legacy concept",
        content="Just a note", category="technical",
    )
    retrieved = store.get(concept_id)
    assert retrieved.assertion == ""
    assert retrieved.doc_links == []
    assert retrieved.superseded_by is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_concept_store_v2.py -v`
Expected: FAIL — `Concept` doesn't have `assertion`, `doc_links`, `superseded_by` fields

- [ ] **Step 3: Add new fields to the Concept dataclass**

In `src/prep/services/concept_store.py`, find the `Concept` class (around line 70) and add these fields after the existing ones:

```python
    assertion: str = ""                    # Testable statement (Phase 84)
    doc_links: List[Dict[str, str]] = field(default_factory=list)  # [{path, label, type}] (Phase 84)
    superseded_by: Optional[str] = None    # Concept ID that replaces this one (Phase 84)
```

Add `field` to the dataclass import if not already present. Add `Dict` to typing imports if needed.

- [ ] **Step 4: Update the SQLite schema**

In the `_create_tables` method of `ConceptStore`, add migration logic:

```python
# Phase 84 schema migration: add assertion, doc_links, superseded_by columns
try:
    self._conn.execute("ALTER TABLE concepts ADD COLUMN assertion TEXT DEFAULT ''")
except Exception:
    pass  # Column already exists
try:
    self._conn.execute("ALTER TABLE concepts ADD COLUMN doc_links TEXT DEFAULT '[]'")
except Exception:
    pass
try:
    self._conn.execute("ALTER TABLE concepts ADD COLUMN superseded_by TEXT DEFAULT NULL")
except Exception:
    pass
```

- [ ] **Step 5: Update save() to persist new fields**

In the `save()` method, add `assertion`, `doc_links`, `superseded_by` parameters (with defaults) and include them in the INSERT statement. `doc_links` should be JSON-serialized before storage.

- [ ] **Step 6: Update get/list/search to read new fields**

In the methods that construct `Concept` objects from database rows, add reading of the new columns. Use `json.loads()` for `doc_links`. Handle missing columns gracefully (backward compat with old DBs).

- [ ] **Step 7: Add supersede() method**

```python
def supersede(self, old_id: str, new_id: str) -> None:
    """Mark a concept as superseded by another concept."""
    self._conn.execute(
        "UPDATE concepts SET status = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?",
        (new_id, time.time(), old_id),
    )
    self._conn.commit()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_concept_store_v2.py -v`
Expected: All 7 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/prep/services/concept_store.py tests/test_concept_store_v2.py
git commit -m "feat(concepts): add assertion, doc_links, superseded_by fields with schema migration"
```

---

### Task 2: Conflict Detection

**Files:**
- Create: `src/prep/core/concept_conflicts.py`
- Create: `tests/test_concept_conflicts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concept_conflicts.py
import pytest
from prep.core.concept_conflicts import detect_conflicts, ConceptConflict


def _make_concept(id, title, anchors, category="architecture", status="active", created_at=1000.0):
    return {
        "id": id, "title": title, "anchors": anchors,
        "category": category, "status": status, "created_at": created_at,
    }


def test_no_conflicts_when_no_overlap():
    concepts = [
        _make_concept("c1", "Auth uses JWT", ["src/auth.py"]),
        _make_concept("c2", "DB uses SQLite", ["src/db.py"]),
    ]
    assert detect_conflicts(concepts) == []


def test_detects_conflict_on_shared_anchors():
    concepts = [
        _make_concept("c1", "Server uses dispatch pattern", ["src/server.py"], created_at=1000),
        _make_concept("c2", "Server uses inline handlers", ["src/server.py"], created_at=2000),
    ]
    conflicts = detect_conflicts(concepts)
    assert len(conflicts) == 1
    assert conflicts[0].concept_a_id == "c1"
    assert conflicts[0].concept_b_id == "c2"


def test_oldest_wins():
    concepts = [
        _make_concept("c1", "Old approach", ["src/server.py"], created_at=1000),
        _make_concept("c2", "New approach", ["src/server.py"], created_at=2000),
    ]
    conflicts = detect_conflicts(concepts)
    assert conflicts[0].winner_id == "c1"  # Oldest wins for code enforcement


def test_ignores_non_active_concepts():
    concepts = [
        _make_concept("c1", "Active", ["src/server.py"], status="active"),
        _make_concept("c2", "Archived", ["src/server.py"], status="archived"),
    ]
    assert detect_conflicts(concepts) == []


def test_only_constraint_and_architecture_conflict():
    concepts = [
        _make_concept("c1", "Convention A", ["src/server.py"], category="convention"),
        _make_concept("c2", "Convention B", ["src/server.py"], category="convention"),
    ]
    # Conventions don't conflict — only constraint and architecture do
    assert detect_conflicts(concepts) == []


def test_constraint_vs_architecture_conflicts():
    concepts = [
        _make_concept("c1", "Constraint", ["src/server.py"], category="constraint"),
        _make_concept("c2", "Architecture", ["src/server.py"], category="architecture"),
    ]
    conflicts = detect_conflicts(concepts)
    assert len(conflicts) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_concept_conflicts.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement conflict detection**

```python
# src/prep/core/concept_conflicts.py
"""Concept conflict detection for Prep.

Detects contradictory active concepts that share anchors.
Only constraint and architecture concepts can conflict.
Oldest concept wins for code enforcement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set


# Only these categories can produce conflicts
_CONFLICTING_CATEGORIES = frozenset({"constraint", "architecture"})


@dataclass
class ConceptConflict:
    """A pair of active concepts that may contradict each other."""
    concept_a_id: str
    concept_a_title: str
    concept_b_id: str
    concept_b_title: str
    shared_anchors: List[str]
    winner_id: str  # Oldest concept wins for code enforcement


def detect_conflicts(concepts: List[Dict[str, Any]]) -> List[ConceptConflict]:
    """Find pairs of active constraint/architecture concepts sharing anchors.

    Args:
        concepts: List of concept dicts with: id, title, anchors, category, status, created_at

    Returns:
        List of ConceptConflict pairs. Oldest concept is marked as winner.
    """
    # Filter to active constraint/architecture concepts only
    active = [
        c for c in concepts
        if c.get("status") == "active"
        and c.get("category", "") in _CONFLICTING_CATEGORIES
    ]

    conflicts: List[ConceptConflict] = []
    seen_pairs: Set[frozenset] = set()

    for i, a in enumerate(active):
        anchors_a = set(a.get("anchors", []))
        if not anchors_a:
            continue

        for b in active[i + 1:]:
            anchors_b = set(b.get("anchors", []))
            shared = anchors_a & anchors_b
            if not shared:
                continue

            pair_key = frozenset({a["id"], b["id"]})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Oldest wins
            a_time = a.get("created_at", 0)
            b_time = b.get("created_at", 0)
            if a_time <= b_time:
                winner_id = a["id"]
            else:
                winner_id = b["id"]

            conflicts.append(ConceptConflict(
                concept_a_id=a["id"],
                concept_a_title=a.get("title", ""),
                concept_b_id=b["id"],
                concept_b_title=b.get("title", ""),
                shared_anchors=sorted(shared),
                winner_id=winner_id,
            ))

    return conflicts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_concept_conflicts.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/concept_conflicts.py tests/test_concept_conflicts.py
git commit -m "feat(concepts): add conflict detection for contradictory concepts"
```

---

### Task 3: Observation → Concept Promotion

**Files:**
- Create: `src/prep/core/concept_promotion.py`
- Create: `tests/test_concept_promotion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concept_promotion.py
import pytest
from prep.core.concept_promotion import (
    suggest_promotion,
    PromotionSuggestion,
    build_concept_from_observation,
)


def _make_observation(content, category="decision", file_path="src/server.py"):
    return {
        "id": "obs-1",
        "content": content,
        "category": category,
        "file_path": file_path,
    }


def test_decision_observation_suggests_promotion():
    obs = _make_observation("We decided to use SQLite for portability", category="decision")
    suggestion = suggest_promotion(obs)
    assert suggestion is not None
    assert suggestion.reason is not None


def test_note_observation_does_not_suggest():
    obs = _make_observation("Looked at the code today", category="note")
    suggestion = suggest_promotion(obs)
    assert suggestion is None


def test_pattern_observation_suggests_promotion():
    obs = _make_observation("All MCP handlers follow dispatch pattern", category="pattern")
    suggestion = suggest_promotion(obs)
    assert suggestion is not None


def test_build_concept_from_observation():
    obs = _make_observation(
        "We decided to use SQLite for portability",
        category="decision",
        file_path="src/prep/core/project_registry.py",
    )
    concept = build_concept_from_observation(obs)
    assert concept["title"] != ""
    assert concept["content"] == obs["content"]
    assert "src/prep/core/project_registry.py" in concept["anchors"]
    assert concept["category"] in ("architecture", "domain", "constraint", "pattern", "convention")
    assert concept["status"] == "proposed"
    assert concept["assertion"] == ""  # Human fills this in


def test_build_concept_preserves_observation_ref():
    obs = _make_observation("Pattern: all handlers validate before dispatch", category="pattern")
    concept = build_concept_from_observation(obs)
    assert concept["source"] == "obs-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_concept_promotion.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement promotion logic**

```python
# src/prep/core/concept_promotion.py
"""Observation → Concept promotion for Prep.

Suggests promoting durable observations (decisions, patterns, assumptions)
into structured concepts. The human confirms and fills in the assertion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Observation categories eligible for promotion
_PROMOTABLE_CATEGORIES = frozenset({"decision", "pattern", "assumption"})

# Map observation categories to likely concept categories
_CATEGORY_MAP = {
    "decision": "architecture",
    "pattern": "pattern",
    "assumption": "domain",
}


@dataclass
class PromotionSuggestion:
    """Suggestion to promote an observation into a concept."""
    observation_id: str
    reason: str
    suggested_category: str


def suggest_promotion(observation: Dict[str, Any]) -> Optional[PromotionSuggestion]:
    """Check if an observation should be promoted to a concept.

    Only decision, pattern, and assumption observations are candidates.
    Notes and bugs are temporal and not suitable for promotion.

    Args:
        observation: Dict with keys: id, content, category, file_path

    Returns:
        PromotionSuggestion if eligible, None otherwise.
    """
    category = observation.get("category", "note")
    if category not in _PROMOTABLE_CATEGORIES:
        return None

    obs_id = observation.get("id", "")
    suggested = _CATEGORY_MAP.get(category, "technical")

    reasons = {
        "decision": "This decision may encode a durable architectural choice worth enforcing.",
        "pattern": "This observed pattern may be an established convention worth documenting.",
        "assumption": "This assumption may encode domain knowledge worth making explicit.",
    }

    return PromotionSuggestion(
        observation_id=obs_id,
        reason=reasons.get(category, "This observation may be worth promoting to a concept."),
        suggested_category=suggested,
    )


def build_concept_from_observation(observation: Dict[str, Any]) -> Dict[str, Any]:
    """Build a concept draft from an observation.

    The assertion field is left empty — the human fills it in.
    The concept is created with status="proposed" for review.

    Args:
        observation: Dict with keys: id, content, category, file_path

    Returns:
        Dict ready to pass to concept_store.save() (minus project_id).
    """
    content = observation.get("content", "")
    category = observation.get("category", "note")
    file_path = observation.get("file_path", "")

    # Generate a title from the first sentence or first 80 chars
    title = content.split(".")[0].strip()
    if len(title) > 80:
        title = title[:77] + "..."
    if not title:
        title = content[:80]

    concept_category = _CATEGORY_MAP.get(category, "technical")

    anchors = [file_path] if file_path else []

    return {
        "title": title,
        "content": content,
        "assertion": "",  # Human fills this in
        "category": concept_category,
        "status": "proposed",
        "anchors": anchors,
        "doc_links": [],
        "source": observation.get("id", ""),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_concept_promotion.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/concept_promotion.py tests/test_concept_promotion.py
git commit -m "feat(concepts): add observation-to-concept promotion logic"
```

---

### Task 4: Update MCP Tool Schema for prep_concepts

**Files:**
- Modify: `src/prep/mcp_tools.py` (prep_concepts tool definition)

- [ ] **Step 1: Read the current schema**

The prep_concepts tool is at lines ~323-382 in mcp_tools.py. Read it to understand current params.

- [ ] **Step 2: Add new parameters**

Add these to the `prep_concepts` inputSchema properties:

```python
"assertion": {
    "type": "string",
    "description": "(save) A testable statement about what should be true. Used for violation detection.",
},
"doc_links": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory path"},
            "label": {"type": "string", "description": "Display label"},
            "type": {"type": "string", "enum": ["source", "doc", "config", "external"]},
        },
        "required": ["path"],
    },
    "description": "(save) Linked documentation, source files, or folders.",
},
"supersede": {
    "type": "string",
    "description": "(save) ID of an existing concept that this new concept supersedes.",
},
```

Also add `"proposed"` to the status enum (currently only seed|active|archived).

- [ ] **Step 3: Verify schema loads**

Run: `.venv/bin/python -c "from prep.mcp_tools import TOOLS; t = [t for t in TOOLS if t['name'] == 'prep_concepts'][0]; print('assertion' in t['inputSchema']['properties'])"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add src/prep/mcp_tools.py
git commit -m "feat(concepts): add assertion, doc_links, supersede to MCP schema"
```

---

### Task 5: Wire MCP Server for New Concept Fields

**Files:**
- Modify: `src/prep/mcp/server.py`

- [ ] **Step 1: Find the concepts handler**

Look for the `tool_concepts` method or the prep_concepts dispatch block.

- [ ] **Step 2: Update the save path**

When `action == "save"`, pass the new fields through:
- `assertion=args.get("assertion", "")`
- `doc_links=args.get("doc_links", [])`
- After save, if `args.get("supersede")` is set, call `concept_store.supersede(supersede_id, new_concept_id)`

- [ ] **Step 3: Update the get/list response**

Ensure `assertion`, `doc_links`, and `superseded_by` fields are included in the response dict and markdown output.

- [ ] **Step 4: Verify module loads**

Run: `.venv/bin/python -c "from prep.mcp.server import MCPServer; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/server.py
git commit -m "feat(concepts): wire assertion, doc_links, supersede through MCP handlers"
```

---

### Task 6: Integrate Conflict Detection with Audit

**Files:**
- Modify: `src/prep/core/audit/structural.py`
- Modify: `src/prep/mcp/server.py` (tool_audit_structural)

- [ ] **Step 1: Add concept_violation finding type to structural scanner**

In `structural.py`, add a `_detect_concept_conflicts` function:

```python
def _detect_concept_conflicts(
    concepts: List[Dict[str, Any]],
) -> List[StructuralFinding]:
    """Detect conflicting active concepts and surface as audit findings."""
    from prep.core.concept_conflicts import detect_conflicts

    conflicts = detect_conflicts(concepts)
    findings = []
    for conflict in conflicts:
        findings.append(StructuralFinding(
            finding_type="concept_conflict",
            file_path=conflict.shared_anchors[0] if conflict.shared_anchors else "",
            severity="warning",
            title=f"Conflicting concepts: '{conflict.concept_a_title}' vs '{conflict.concept_b_title}'",
            description=(
                f"Two active concepts share anchors ({', '.join(conflict.shared_anchors)}) "
                f"and may contradict each other. Oldest concept ('{conflict.concept_a_title}') "
                f"wins for code enforcement until resolved."
            ),
            risk_score=0.65,
            recommendation="Review and resolve: archive, supersede, or update one of the conflicting concepts.",
            evidence={
                "concept_a": conflict.concept_a_id,
                "concept_b": conflict.concept_b_id,
                "shared_anchors": conflict.shared_anchors,
                "winner": conflict.winner_id,
            },
        ))
    return findings
```

Call this from `run_structural_audit` alongside the existing detectors.

- [ ] **Step 2: Update `_CATEGORY_TO_FINDING_TYPE` mapping**

```python
"concept_violation": {"concept_conflict"},
```

- [ ] **Step 3: Add test**

```python
def test_structural_detects_concept_conflicts():
    ctx = _make_mock_context()
    ctx["concepts"] = [
        {"id": "c1", "title": "Use dispatch", "anchors": ["src/server.py"],
         "category": "architecture", "status": "active", "created_at": 1000},
        {"id": "c2", "title": "Use inline", "anchors": ["src/server.py"],
         "category": "architecture", "status": "active", "created_at": 2000},
    ]
    findings = run_structural_audit(ctx)
    conflict_findings = [f for f in findings if f.finding_type == "concept_conflict"]
    assert len(conflict_findings) >= 1
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/pytest tests/test_structural_audit.py tests/test_concept_conflicts.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/audit/structural.py tests/test_structural_audit.py
git commit -m "feat(audit): surface concept conflicts as structural audit findings"
```

---

### Task 7: Integration Verification

- [ ] **Step 1: Run ALL Phase 84 tests together**

```bash
.venv/bin/pytest tests/test_concept_store_v2.py tests/test_concept_conflicts.py tests/test_concept_promotion.py tests/test_structural_audit.py tests/test_enrichment.py tests/test_recommendations.py -v
```

All should pass.

- [ ] **Step 2: Verify all imports chain correctly**

```bash
.venv/bin/python -c "
from prep.services.concept_store import ConceptStore, Concept
from prep.core.concept_conflicts import detect_conflicts, ConceptConflict
from prep.core.concept_promotion import suggest_promotion, build_concept_from_observation
from prep.core.audit.structural import run_structural_audit
from prep.mcp.server import MCPServer
print('All Phase 84 imports OK')
"
```

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix(concepts): integration test fixes for Phase 84"
```
