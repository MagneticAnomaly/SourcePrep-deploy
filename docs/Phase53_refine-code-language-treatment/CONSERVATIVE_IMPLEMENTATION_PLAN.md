# Phase 53: Conservative Implementation Plan
## Clear Sprints with Stability Checks & Architectural Research

**Version:** 1.0 - Conservative Path  
**Approach:** Rust-first, 3-class start, 7-class finish  
**Backward Compatibility:** Not required (active development phase)

---

## Research: Content Class Drift

### What Is Content Class Drift?

**Content class drift** occurs when a file's nature changes over time, causing its classification to shift. This happens because:

1. **Evolution:** Files grow from simple to complex (or vice versa)
2. **Refactoring:** Code extracted into separate files
3. **Deprecation:** Documentation becomes outdated
4. **Merging:** Multiple files combined

### Real Examples (From Your HomeColab Codebase)

| File | Initial State | Current State | Drift |
|------|---------------|---------------|-------|
| `README.md` | 50 lines (Unstructured) | 500 lines with API docs (Structured) | ↑ Upgrade |
| `TWO_PHASE_ENRICHMENT.md` | Design spec (Structured) | Implementation complete (Unstructured narrative) | ↓ Degrade |
| `Marketing_Copy_and_Plan.md` | Outline (SemiStructured) | Full copy (Unstructured) | ↓ Degrade |
| `api/routes.py` | Monolith (StructuredCode) | Refactored to handlers (Mixed) | → Complexify |

### Why It Matters

**Scenario: Stale Classification**
```
Week 1: README.md classified as UnstructuredNarrative
Week 10: README.md has grown into full API documentation
Problem: Still treated as UnstructuredNarrative (50 lines context)
Result: Incomplete understanding by LLM, poor augmentation
```

### Detection Strategy

We detect drift by monitoring **structural metrics** between builds:

```rust
// In Rust classification engine
struct ClassificationFingerprint {
    section_count: u32,
    ref_count: u32,
    code_block_count: u32,
    total_lines: u32,
    hash_of_structure: String,  // Hash of heading hierarchy
}

// Drift detection
if current_fingerprint.section_count > last_fingerprint.section_count * 2 {
    // File has grown significantly - reclassify
    DriftEvent::PossibleUpgrade
}

if current_fingerprint.ref_count == 0 && last_fingerprint.ref_count > 5 {
    // References removed - document simplified
    DriftEvent::PossibleDegrade
}
```

### Handling Strategies

**Strategy A: Rebuild Reclassification (Conservative)**
- Reclassify on every full build
- Cost: ~1ms per file (negligible)
- Accuracy: High
- **Recommendation:** Use this for Phase 53

**Strategy B: Incremental Drift Detection (Future)**
- Track fingerprints separately
- Only reclassify when drift detected
- Cost: Lower CPU, higher complexity
- **Status:** Future optimization, not Phase 53

**Strategy C: Manual Override Persistence (Edge Case)**
- User manually sets class → store override
- Even if file drifts, keep override
- **Implementation:** Skip, add if users request

### Phase 53 Decision

**Use Strategy A (Rebuild Reclassification).** Since we're rebuilding indexes anyway:
- Every build computes fresh classification
- No drift accumulation
- Simple to implement
- Revisit Strategy B if performance becomes issue

---

## Architecture Decision: Mixed Content

### The Question
Should files like complex READMEs (with heavy code blocks) be:
- **Option A:** Single node with `Mixed` treatment
- **Option B:** Split into virtual nodes (prose node + code block nodes)

### Analysis

**Current State (augmenter.py:1108-1115):**
```python
# Single node per file
file_node = TraceNode(...)
if is_md:
    doc_files.append(node)  # Gets doc treatment
```

**Option B Would Require:**
```
README.md → 
  ├─ Node 1: README.md (prose sections) → doc treatment
  ├─ Node 2: README.md:codeblock1 (Swift example) → code treatment  
  ├─ Node 3: README.md:codeblock2 (Config example) → config treatment
```

### Complexity Comparison

| Aspect | Option A: Single Mixed | Option B: Virtual Split |
|--------|----------------------|------------------------|
| **Node Count** | 1 per file | 1 + N code blocks |
| **Trace Graph Size** | Manageable | Could explode (×10 for code-heavy docs) |
| **Augmentation Logic** | Simple (one call) | Complex (multiple calls, ordering) |
| **Edge Management** | Simple | Need `contains` edges to virtual nodes |
| **UI Display** | One file = one node | User sees file fragments |
| **Search Results** | Return whole file | Return specific code block? |

### Strategic Assessment

**Don't Split (Option A) - Here's Why:**

1. **Your Codebase Variance**: You mentioned "a lot of variance" - this is true, but most variance is **between files**, not **within files**. A marketing doc doesn't become code; a README with code is still primarily documentation.

2. **Graph Complexity**: HomeColab has 801 files. If 10% are Mixed with average 3 code blocks each:
   - Current: 801 nodes
   - Split: 801 + 240 = 1,041 nodes (+30%)
   - UI becomes cluttered, trace graph harder to navigate

3. **Treatment Reality**: Mixed content needs **Mixed treatment** (some doc, some code), not **split processing**. The current plan handles this with `Mixed` class using strategic excerpt selection.

4. **Future-Proofing**: We can add virtual splitting later if needed. Harder to remove if we add it now.

### Decision: Conservative Treatment for Mixed

**Keep single nodes, implement sophisticated Mixed treatment:**

```python
# For Mixed files: Weighted excerpt selection
def get_mixed_excerpt(file_path, sections):
    # 60% prose sections (for narrative flow)
    prose = select_prose_sections(sections, weight=0.6, max_lines=300)
    
    # 30% code blocks (for technical accuracy)
    code = select_code_blocks(sections, weight=0.3, max_lines=150)
    
    # 10% structure (headings for navigation)
    structure = get_heading_outline(sections, weight=0.1)
    
    return combine_weighted(prose, code, structure)
```

**Revisit Condition:** If we find files where code blocks are the PRIMARY content (not supporting material), we can add `CodePrimary` subclass later.

---

## Sprint Plan with Stability Checks

### Sprint 0: Rust Foundation (Week 1)
**Goal:** Build Rust content classifier with 3 classes

#### Technical Implementation
```rust
// New: codrag-engine/src/classifier.rs
pub enum ContentClass {
    StructuredCode,        // All source code files
    StructuredDocs,        // API docs, technical specs
    UnstructuredNarrative, // Marketing, plans, simple READMEs
}

pub struct ContentClassifier;

impl ContentClassifier {
    pub fn classify(
        file_path: &Path,
        sections: &[Section],
        refs: &[Reference],
        ast: Option<&AST>,
    ) -> ContentClass {
        // Priority 1: Code detection
        if ast.is_some() {
            return ContentClass::StructuredCode;
        }
        
        // Priority 2: Markdown classification
        if file_path.extension() == "md" {
            let metrics = calculate_doc_metrics(sections, refs);
            
            if metrics.ref_count > 3 && metrics.section_count > 5 {
                ContentClass::StructuredDocs
            } else {
                ContentClass::UnstructuredNarrative
            }
        } else {
            // Config, Data, etc. → StructuredDocs (conservative)
            ContentClass::StructuredDocs
        }
    }
}
```

#### Integration Points
- [ ] Hook classifier into Rust trace builder
- [ ] Store `content_class` in trace_nodes.jsonl.metadata
- [ ] Add classification metrics to trace_manifest.json

#### Stability Check Criteria
| Check | Test | Pass Criteria |
|-------|------|---------------|
| **Classification Accuracy** | Run on 50 known files | >90% match expected class |
| **Performance** | Time classification for 1000 files | <2ms per file |
| **Schema Valid** | Load trace_nodes.jsonl in Python | No JSON parse errors |
| **Deterministic** | Re-run on same files | Same classification results |

#### Go/No-Go Gate
**Proceed if:** Classification >90% accurate, <2ms overhead, schema valid  
**Rollback if:** >5% files misclassified, >10ms overhead, schema errors

---

### Sprint 1: Python Integration (Week 2)
**Goal:** Python can read classification, TreatmentRegistry exists

#### Technical Implementation

**Step 1: Python Bindings**
```python
# src/codrag/core/content_class.py
from enum import Enum

class ContentClass(str, Enum):
    STRUCTURED_CODE = "structured_code"
    STRUCTURED_DOCS = "structured_docs"  
    UNSTRUCTURED_NARRATIVE = "unstructured_narrative"

@dataclass
class ClassifiedNode:
    trace_node: Dict[str, Any]
    content_class: ContentClass
    confidence: float  # 0.0-1.0
    
    @classmethod
    def from_trace_node(cls, node: Dict) -> "ClassifiedNode":
        class_str = node.get("metadata", {}).get("content_class", "unknown")
        return cls(
            trace_node=node,
            content_class=ContentClass(class_str),
            confidence=calculate_confidence(node),  # From section metrics
        )
```

**Step 2: Treatment Registry**
```python
# src/codrag/core/treatment_registry.py
@dataclass(frozen=True)
class TreatmentConfig:
    context_lines: int
    batch_size: int
    use_strategic_excerpt: bool
    system_prompt: str

class TreatmentRegistry:
    _TREATMENTS = {
        ContentClass.STRUCTURED_CODE: TreatmentConfig(
            context_lines=50,
            batch_size=8,
            use_strategic_excerpt=False,
            system_prompt=BATCHED_FILE_SYSTEM,
        ),
        ContentClass.STRUCTURED_DOCS: TreatmentConfig(
            context_lines=200,
            batch_size=4,
            use_strategic_excerpt=True,
            system_prompt=BATCHED_DOC_SYSTEM,
        ),
        ContentClass.UNSTRUCTURED_NARRATIVE: TreatmentConfig(
            context_lines=50,
            batch_size=1,  # No batching
            use_strategic_excerpt=False,
            system_prompt=BATCHED_NARRATIVE_SYSTEM,  # New simpler prompt
        ),
    }
    
    @classmethod
    def get_treatment(cls, content_class: ContentClass) -> TreatmentConfig:
        return cls._TREATMENTS[content_class]
```

#### Frontend Test Criteria
| Component | Test | Expected Result |
|-----------|------|----------------|
| **Dashboard API** | GET /projects/{id}/trace/status | Returns `content_class` in node metadata |
| **Graph Explorer** | Load trace nodes | Nodes show class badge (Code/Docs/Narrative) |
| **File Tree** | Expand markdown folder | Files have icons by class (📄 📋 📝) |

#### Stability Check Criteria
| Check | Test | Pass Criteria |
|-------|------|---------------|
| **API Response** | Query trace endpoint | All nodes have `content_class` field |
| **Registry Lookup** | Treatment for each class | Returns valid TreatmentConfig |
| **Prompt Existence** | Load narrative prompt | No ImportError |
| **UI Rendering** | Open Graph Explorer | No console errors, icons render |

#### Go/No-Go Gate
**Proceed if:** API returns classes, registry works, UI renders  
**Rollback if:** API errors, missing classes, UI crashes

---

### Sprint 2: Treatment Differentiation (Week 3)
**Goal:** Different treatments per class, fix your failing files

#### Technical Implementation

**Step 1: Augmenter Integration**
```python
# src/codrag/core/augmenter.py: Refactor _augment_files_batched

def _augment_files_batched(self, file_nodes: List[Dict], ...):
    # REPLACE binary split with classified grouping
    classified = defaultdict(list)
    for node in file_nodes:
        class_node = ClassifiedNode.from_trace_node(node)
        classified[class_node.content_class].append(class_node)
    
    # Process each class with its treatment
    for content_class, nodes in classified.items():
        treatment = TreatmentRegistry.get_treatment(content_class)
        self._process_class_batch(nodes, treatment, ...)
```

**Step 2: New Narrative Prompt**
```python
# src/codrag/core/batch_prompts.py

BATCHED_NARRATIVE_SYSTEM = """You are a document summarizer.
Analyze the content and return a brief summary.
Respond ONLY with JSON: {"summary": "...", "topics": ["..."]}
No markdown, no explanation."""

def build_batched_narrative_prompt(items: List[Dict]) -> str:
    """Simplified prompt for unstructured content."""
    parts = [f"Summarize these {len(items)} documents:\n"]
    for i, item in enumerate(items, 1):
        # Limit content aggressively for narrative
        content = item['content'][:500]  # Hard limit
        parts.append(f"\n{i}. {item['file_path']}:\n{content[:300]}...")
    parts.append("\nJSON response:")
    return "\n".join(parts)
```

**Step 3: Template Literal Fix**
```python
# src/codrag/core/batch_strategy.py

@staticmethod
def _try_template_literal_fix(text: str) -> Optional[List[Dict]]:
    """Fix responses where LLM preserved template placeholders."""
    import re
    
    # Detect <placeholder> patterns
    if not re.search(r'<[a-z_]+>', text):
        return None
    
    # Replace with sequential numbers
    fixed = text
    for i, match in enumerate(re.finditer(r'<[a-z_]+>', text), 1):
        fixed = fixed.replace(match.group(), str(i), 1)
    
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
```

#### Test Your Failing Files
| File | Previous Class | New Class | Expected Result |
|------|---------------|-----------|-----------------|
| `Marketing_Copy_and_Plan.md` | StructuredDocs | UnstructuredNarrative | 50 lines, simple prompt, success |
| `TWO_PHASE_ENRICHMENT.md` | StructuredDocs | StructuredDocs | 200 lines, works as before |
| `RANKING_IMPLEMENTATION_SUMMARY.md` | StructuredDocs | StructuredDocs | 200 lines, works as before |

#### Stability Check Criteria
| Check | Test | Pass Criteria |
|-------|------|---------------|
| **Parser Success** | Build HomeColab project | >95% batch parse success |
| **No Regressions** | Build codrag itself | Same success rate as before |
| **Content Limits** | Verify narrative files | Max 50 lines sent to LLM |
| **Template Fixes** | Parse responses with `<doc_number>` | Successfully extracts items |

#### Go/No-Go Gate
**Proceed if:** Parser success >95%, HomeColab builds without errors  
**Rollback if:** <90% success rate, new parser failures introduced

---

### Sprint 3: Expansion to 7 Classes (Week 4)
**Goal:** Add Configuration, Data, Mixed, SemiStructuredDocs

#### Technical Implementation
Add 4 new classes with conservative defaults:

```rust
pub enum ContentClass {
    StructuredCode,
    SemiStructuredDocs,    // NEW: Simple docs with few sections
    StructuredDocs,
    Mixed,                 // NEW: READMEs with code blocks
    Configuration,           // NEW: .json, .yaml, .toml
    Data,                  // NEW: .csv, .jsonl
    UnstructuredNarrative,
}
```

**Treatment Mapping:**
| Class | Inherits From | Modification |
|-------|--------------|--------------|
| SemiStructuredDocs | StructuredDocs | context_lines: 150 (not 200) |
| Mixed | StructuredDocs | Use Mixed treatment (see below) |
| Configuration | StructuredDocs | Use config-aware prompt |
| Data | StructuredDocs | Skip LLM, metadata only |

**Mixed Treatment Implementation:**
```python
def get_mixed_excerpt(file_path, sections):
    # 60% prose, 30% code, 10% structure
    prose = select_sections(sections, exclude_code=True, max_lines=180)
    code = select_code_blocks(sections, max_lines=90)
    structure = get_heading_outline(sections)
    return combine(prose, code, structure)
```

#### Frontend Updates
- [ ] Add 4 new icons to File Tree
- [ ] Dashboard shows class distribution pie chart
- [ ] Filter by class in Graph Explorer

#### Stability Check Criteria
| Check | Test | Pass Criteria |
|-------|------|---------------|
| **7-Class Coverage** | Classify 100 diverse files | All files get a class |
| **No Unknowns** | Check for ContentClass.UNKNOWN | 0 files unclassified |
| **Treatment Exists** | Lookup treatment for each class | All 7 return valid config |

#### Go/No-Go Gate
**Proceed if:** All 7 classes work, no "unknown" classifications  
**Delay if:** Classification ambiguous, treatments incomplete

---

### Sprint 4: Polish & Validation (Week 5)
**Goal:** Performance optimization, documentation, edge case handling

#### Technical Implementation
- [ ] Performance benchmark: Build time vs old system
- [ ] Edge case: Empty files, binary files, huge files
- [ ] Confidence scoring implementation
- [ ] Manual override UI (low priority)
- [ ] Documentation: Content Class Guide

#### Final Stability Check
| Metric | Baseline | Target | Result |
|--------|----------|--------|--------|
| Parser Success Rate | 94% | >97% | Measure |
| Build Time (HomeColab) | ~15 min | <16 min | Measure |
| Classification Accuracy | N/A | >95% | Validation set |
| Memory Usage | Baseline | <110% | Monitor |

---

## Timeline Summary

| Sprint | Week | Focus | Deliverable | Stability Check |
|--------|------|-------|-------------|-----------------|
| 0 | 1 | Rust Foundation | 3-class classifier in Rust | >90% accuracy, <2ms |
| 1 | 2 | Python Integration | TreatmentRegistry, API updates | API returns classes |
| 2 | 3 | Treatment Diff | Fix your failing files | >95% parser success |
| 3 | 4 | 7-Class Expansion | Full classification taxonomy | All files classified |
| 4 | 5 | Polish | Performance, docs, edge cases | >95% accuracy validated |

**Total Timeline:** 5 weeks  
**Buffer:** +1 week if Sprint 2 hits issues  
**Ship Date:** Week 5 (or Week 6 with buffer)

---

## Embedding Strategy Decision

**Decision:** Keep single embedding model (nomic-embed-v2-moe)

**Rationale:**
- Current model works well for all content types
- Separate models = complexity without clear benefit
- Can revisit when newer multimodal embedding models emerge

**Future Door:** 
- Add `embedding_strategy` to TreatmentConfig (optional field)
- Default: current model
- Future: point to specific model per class
- No implementation now, architecture supports it

---

## Success Criteria Summary

**Must Have (Ship Blockers):**
- [ ] 3-class classification working (>95% accuracy)
- [ ] Parser success rate >95% (HomeColab builds clean)
- [ ] No performance regression >10%
- [ ] API returns classes, UI renders

**Nice to Have (Post-MVP):**
- [ ] 7-class taxonomy complete
- [ ] Confidence scoring
- [ ] Manual override UI
- [ ] Content class drift visualization

**Explicitly Out of Scope:**
- [ ] Virtual node splitting (Mixed content)
- [ ] Multiple embedding models
- [ ] Incremental drift detection (rebuild on every build)
- [ ] Backward compatibility (rebuilding is fine)

---

## Next Action

**Create Sprint 0 GitHub Issues:**
1. [#P53-S0-1] Create Rust content classifier module
2. [#P53-S0-2] Implement 3-class classification logic
3. [#P53-S0-3] Store classification in trace_nodes metadata
4. [#P53-S0-4] Create validation dataset (50 labeled files)
5. [#P53-S0-5] Write classification accuracy tests

**Ready to start Sprint 0?**
```bash
# Create branch
git checkout -b phase53/content-classification

# First commit: Rust classifier scaffold
# Target: End of week 1 with working 3-class classification
```

---