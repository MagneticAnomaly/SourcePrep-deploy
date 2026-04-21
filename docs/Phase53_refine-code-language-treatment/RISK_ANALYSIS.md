# Phase 53: Risk Analysis & Refined Implementation Plan

**Document Version:** 1.0  
**Status:** Pre-Implementation Risk Assessment  
**Based On:** Deep code review of trace/builder.py, augmenter.py, batch_prompts.py, batch_strategy.py

---

## Executive Summary

After thorough analysis of the CoDRAG codebase, Phase 53's "Content Classification" architecture introduces **7 critical risk areas** that could derail implementation or cause production instability:

| Risk Area | Severity | Probability | Mitigation Complexity |
|-----------|----------|-------------|----------------------|
| Rust/Python Data Flow | **Critical** | High | Medium |
| Schema Migration | **High** | Certain | Low |
| Classification Accuracy | **High** | Medium | High |
| Performance Regression | **Medium** | Medium | Medium |
| Prompt Engineering Debt | **Medium** | High | High |
| Testing Matrix Explosion | **High** | Certain | Medium |
| Backward Compatibility | **Critical** | Certain | Low |

**Recommendation:** Proceed with Sprint 1 (Classification Layer) but implement **A/B testing framework first** to validate changes without risking production stability.

---

## 1. Deep Technical Risk Analysis

### 1.1 Risk: Rust/Python Data Flow Complexity

**Current State Analysis:**
```python
# From builder.py:243-251 - File node creation
file_node = TraceNode(
    id=stable_file_node_id(rel_path),
    kind="file",
    name=file_path.name,
    file_path=rel_path,
    span=None,
    language=_detect_language(rel_path),
    metadata={"truncated": is_large, "size": file_size},
)
```

**The Problem:**
- File nodes are created in Python (builder.py) OR Rust (builder.py:316 `_build_rust`)
- Content classification requires **section analysis** (for docs) or **AST analysis** (for code)
- Markdown sections are extracted in Rust (Phase 22: "Rust Markdown Extraction"), NOT in Python
- Classification algorithm needs access to:
  - For code: AST nodes, import count, symbol complexity
  - For docs: Section hierarchy, ref_count, code block presence

**Risk Manifestation:**
```
Scenario: Mixed build (some files Rust, some Python)
- Rust-built files: Have section data in trace_nodes.jsonl.metadata.sections
- Python-built files: Have only basic metadata
- Classification runs in Python augmenter.py
- Result: Inconsistent classification across build paths
```

**Mitigation Strategy:**
Option A: **Dual Implementation** (High cost)
- Implement classification in BOTH Rust and Python
- Ensure identical logic between languages
- High maintenance burden

Option B: **Lazy Classification** (Recommended)
- Python augmenter loads trace data
- Calculates classification on-the-fly during augmentation
- Stores in memory (not persisted)
- **Trade-off:** Re-classification on every build vs. build-time consistency

Option C: **Rust-Only Classification**
- Move classification to Rust (where markdown sections exist)
- Add `content_class` field to TraceNode in Rust
- Python reads pre-computed class
- **Trade-off:** Requires Rust development expertise

**Decision:** Use Option C (Rust-only) for consistency, but implement feature flag to fall back to binary split if issues arise.

---

### 1.2 Risk: Schema Migration & Index Invalidation

**Current State:**
- `trace_nodes.jsonl` format: `{"id": "...", "kind": "...", "metadata": {...}}`
- No versioning for metadata schema
- Existing indexes in production don't have `content_class`

**Risk Manifestation:**
```
Scenario: User upgrades CoDRAG
- Old index: trace_nodes.jsonl without content_class
- New code: Expects content_class in metadata
- Result: KeyError or misclassification for all existing projects
```

**Impact Assessment:**
- **All existing projects** will need index rebuilds
- **Team Sync** feature (Phase 06) shares indexes - version mismatch between team members
- **CI/CD pipelines** with cached indexes will break

**Mitigation Strategy:**
1. **Lazy Migration Path:**
   ```python
   content_class = node.get("metadata", {}).get("content_class")
   if content_class is None:
       # Compute on-the-fly using legacy heuristic
       content_class = _legacy_classify(node)
   ```

2. **Index Version Bump:**
   - Bump `TRACE_MANIFEST_VERSION` from "1.0" to "1.1"
   - Detect old version → trigger automatic rebuild
   - Show user notification: "Index format updated, rebuilding..."

3. **Staged Rollout:**
   - Phase 1: Add classification without consuming it (no treatment changes)
   - Phase 2: Validate classification accuracy
   - Phase 3: Enable treatment changes

---

### 1.3 Risk: Classification Accuracy & False Positives

**The Problem:**
The classification algorithm (from Phase 53 README) uses heuristics:

```python
def classify_content(sections, refs):
    if ref_count > 3 and section_count > 5:
        return ContentClass.StructuredDocs  # API docs
    elif section_count <= 3 and ref_count == 0:
        return ContentClass.UnstructuredNarrative  # Marketing
```

**Risk Scenarios:**

| File | True Nature | Algorithm Classification | Impact |
|------|-------------|------------------------|---------|
| `README.md` (complex) | Mixed (code + prose) | StructuredDocs | Wrong treatment: too much context |
| `CHANGELOG.md` | Semi-structured | UnstructuredNarrative | Loses version history context |
| `API_GUIDE.md` | StructuredDocs | SemiStructuredDocs (false negative) | Insufficient context for LLM |
| `LICENSE.md` | Unstructured | Configuration (if .txt) | Completely wrong treatment |

**Systematic Failure Mode:**
- Marketing copy with many headers → Misclassified as StructuredDocs → 1000 lines sent to 3b model → **OOM/parser failures**
- Technical spec with minimal headers → Misclassified as UnstructuredNarrative → Only 30 lines sent → **Incomplete understanding**

**Mitigation Strategy:**

1. **Confidence Scoring:**
   ```python
   @dataclass
   class ClassificationResult:
       content_class: ContentClass
       confidence: float  # 0.0 - 1.0
       reasoning: str  # Why this classification
       
   # Use confidence to adjust treatment
   if confidence < 0.7:
       treatment = CONSERVATIVE_TREATMENT  # Smaller batches, more context
   ```

2. **Manual Override UI:**
   - Dashboard shows classification for each file
   - User can override: "This is actually StructuredDocs"
   - Store override in `.prep/config.yaml`

3. **Validation Dataset:**
   - Create 100-file labeled dataset before implementation
   - Test classification algorithm against ground truth
   - Target: >90% accuracy before shipping

---

### 1.4 Risk: Performance Impact Analysis

**Current Pipeline Timing (from Phase 40 docs):**
```
Stage: Fast Catalogue (Pass 1)
- Current: ~10 minutes for 650 files
- Bottleneck: LLM calls (3b model)
```

**New Overhead from Classification:**

| Operation | Time Impact | Notes |
|-----------|-------------|-------|
| Section extraction (Rust) | **0ms** | Already happening in Phase 22 |
| Classification calculation | **~1ms per file** | Simple arithmetic on section counts |
| Metadata serialization | **~0.1ms per file** | Small JSON field addition |
| Treatment lookup | **~0.01ms per file** | Hash map lookup |

**Total Overhead: ~1%** (negligible)

**BUT: Treatment Changes Have Impact:**

| ContentClass | Context Lines | Batch Size | Time per File |
|--------------|---------------|------------|---------------|
| Code (current) | 30 | 5 | 200ms |
| StructuredDocs (new) | 200 | 4 | 800ms |
| UnstructuredNarrative (new) | 50 | 1 | 400ms |

**Risk Scenario:**
```
Project: 1000 files (500 code, 400 docs, 100 narrative)
Before: All treated as docs (1000 × 800ms) = 800s
After: 
  - Code: 500 × 200ms = 100s
  - Structured: 300 × 800ms = 240s
  - Narrative: 100 × 400ms = 40s
  - Mixed: 100 × (400s [split processing]) = 40s
Total: 420s (47% faster!)

BUT if classification is wrong:
- 400 docs misclassified as narrative: 400 × 400ms = 160s
- Plus overhead of individual processing: +50s
- Result: 610s (24% SLOWER)
```

**Mitigation:**
- A/B test on real projects before rollout
- Monitor p95 build times
- Rollback if >10% regression

---

### 1.5 Risk: Prompt Engineering Debt

**Current State (batch_prompts.py):**
- 3 main prompts: `BATCHED_FILE_SYSTEM`, `BATCHED_DOC_SYSTEM`, `BATCHED_SYMBOL_SYSTEM`
- Working reasonably well (94% success rate)

**Phase 53 Expansion:**
- 7 content classes × 2 stages (catalogue, epistemic) = **14 new prompts**
- Each prompt needs testing across multiple models (3b, 14b, cloud)
- Each prompt needs schema definition

**Maintenance Burden:**
```
Current: 3 prompts × 3 models = 9 test cases
Phase 53: 14 prompts × 3 models = 42 test cases
4.7x increase in prompt maintenance
```

**Risk Manifestation:**
```
Week 1: Implement UnstructuredNarrative prompt
Week 2: Test on 3b model - works
Week 3: Cloud model (Claude) - works
Week 4: User reports failure on qwen3:4b - CoT leakage
Week 5: Fix for qwen3 - breaks Claude
Week 6: Revert, create separate prompt variants...
```

**Mitigation Strategy:**

1. **Prompt Template System:**
   ```python
   class PromptTemplate:
       base_prompt: str
       model_adaptations: Dict[str, str]  # per-model overrides
       
       def render(self, model: str) -> str:
           base = self.base_prompt
           adaptations = self.model_adaptations.get(model, "")
           return f"{base}\n\n{adaptations}"
   ```

2. **Progressive Prompt Rollout:**
   - Start with 2 classes: StructuredCode, UnstructuredNarrative
   - Validate across all models
   - Add remaining 5 classes incrementally

3. **Shared Components:**
   ```python
   # Base schema instructions shared across prompts
   BASE_JSON_INSTRUCTIONS = """
   You MUST respond with valid JSON.
   Do not include markdown code fences.
   Do not explain your reasoning.
   """
   
   # Class-specific additions
   NARRATIVE_ADDITIONS = "Focus on key topics, not structure."
   CODE_ADDITIONS = "Extract symbol relationships."
   ```

---

### 1.6 Risk: Testing Matrix Explosion

**New Variables Introduced:**

| Variable | Options | Current |
|----------|---------|---------|
| Content Class | 7 | 2 (code/doc) |
| Treatment Config | 7 × parameters | 2 |
| Model | 3 (3b, 14b, cloud) | 3 |
| Provider | 5 (Ollama, OpenAI, etc.) | 5 |

**Test Matrix Size:**
```
Current: 2 × 2 × 3 × 5 = 60 scenarios
Phase 53: 7 × 7 × 3 × 5 = 735 scenarios
12x increase
```

**Critical Test Scenarios:**

1. **Classification × Treatment Mismatch:**
   - File classified as UnstructuredNarrative
   - But uses StructuredDocs treatment due to config error
   - Result: Parser failures

2. **Provider-Specific Structured Output:**
   - OpenAI supports `response_schema` → Reliable JSON
   - Ollama 3b doesn't → Template literal failures
   - Same treatment, different outcomes

3. **Fallback Cascade:**
   - Batch parse fails
   - Falls back to individual
   - Individual fails
   - Falls back to metadata-only
   - Verify graceful degradation

**Mitigation Strategy:**

1. **Risk-Based Testing:**
   - P0: Code + StructuredDocs (80% of files)
   - P1: Mixed + UnstructuredNarrative (15% of files)
   - P2: Configuration + Data (5% of files)

2. **Property-Based Testing:**
   ```python
   @given(st.sampled_from(ContentClass))
   def test_treatment_exists_for_all_classes(content_class):
       assert TreatmentRegistry.get_treatment(content_class) is not None
   ```

3. **Snapshot Testing:**
   - Capture successful responses per model/provider/class
   - Regression test against snapshots

---

### 1.7 Risk: Backward Compatibility

**Breaking Changes:**

| Area | Current | Phase 53 | Impact |
|------|---------|----------|--------|
| `augmenter.py` | Binary split | 7-way split | All augmentation tests break |
| `batch_prompts.py` | 3 prompts | 14 prompts | Import errors |
| `trace_nodes.jsonl` | 8 fields | 9 fields (content_class) | Schema validation failures |
| Settings API | `llm_concurrency_fast` | `llm_concurrency_structured_docs` | UI/API breakage |
| Dashboard | Graph shows file/symbol | Shows file class | UI component updates needed |

**Migration Path Complexity:**

```
User with existing project:
1. Upgrades CoDRAG binary
2. Opens dashboard
3. Dashboard queries API for trace status
4. API loads trace_nodes.jsonl
5. Missing content_class field → Error
6. User sees "Rebuild required"
7. Clicks rebuild
8. New format written
9. Dashboard works

BUT:
- Step 6 could be confusing: "Why rebuild?"
- Step 8 takes time (10 min for large project)
- Step 9 might still fail if classification has bugs
```

**Mitigation Strategy:**

1. **Graceful Degradation:**
   ```python
   # In API layer
   def get_trace_status(project_id):
       try:
           nodes = load_trace_nodes(project_id)
       except SchemaError:
           return {"status": "needs_rebuild", "reason": "Index format updated"}
   ```

2. **Feature Flags:**
   ```python
   USE_CONTENT_CLASSIFICATION = os.getenv(
       "CODRAG_CONTENT_CLASSIFICATION", 
       "false"
   ).lower() == "true"
   
   # If false, use legacy binary split
   ```

3. **Migration Assistant:**
   - CLI command: `codrag migrate --project <id>`
   - Shows progress: "Rebuilding with new classification..."
   - Validates after: "Classification complete. 850 files processed."

---

## 2. Revised Implementation Plan (Risk-Weighted)

### Pre-Sprint: A/B Testing Framework (Week 0)

**Goal:** Enable safe experimentation without production impact

**Tasks:**
- [ ] Create `TreatmentExperiment` class (compare old vs new)
- [ ] Add `CODRAG_TREATMENT_EXPERIMENT` feature flag
- [ ] Build validation dataset (100 labeled files)
- [ ] Create metrics dashboard (success rate, token efficiency)

**Risk Mitigation:** Allows rolling back any change instantly

---

### Sprint 1: Conservative Classification (Week 1)

**Scope Reduction:** Start with 3 classes, not 7

**Implementation:**
```python
class ContentClass:
    StructuredCode = "structured_code"      # All code files
    StructuredDocs = "structured_docs"    # API docs, specs
    UnstructuredNarrative = "unstructured_narrative"  # Everything else
```

**Tasks:**
- [ ] Rust: Add section analysis to file node metadata
- [ ] Python: `classify_content()` with 3-way split
- [ ] Treatment: Map 3 classes to existing batch profiles
- [ ] Tests: 90% accuracy on validation dataset

**Success Criteria:**
- Classification accuracy >90%
- No performance regression
- Backward compatibility maintained

---

### Sprint 2: Treatment Differentiation (Week 2)

**Scope:** Different treatments for the 3 classes

**Tasks:**
- [ ] Create `TreatmentRegistry` with 3 configs
- [ ] Refactor `augmenter.py` to use treatment registry
- [ ] Add new prompts for UnstructuredNarrative (simpler)
- [ ] Implement template literal fix in parser

**Risk Mitigation:**
- A/B test on 10% of files
- Monitor parser failure rates
- Rollback if >2% increase in failures

---

### Sprint 3: Full Classification (Week 3-4)

**Scope:** Expand to 7 classes, add confidence scoring

**Tasks:**
- [ ] Add Configuration, Data, Mixed, SemiStructuredDocs classes
- [ ] Implement confidence scoring
- [ ] Add manual override UI
- [ ] Full test suite (P0 scenarios)

**Risk Mitigation:**
- Feature flag for each new class
- Gradual rollout: Configuration first (low risk), Mixed last (high risk)

---

### Sprint 4: Polish & Migration (Week 5)

**Scope:** Production readiness

**Tasks:**
- [ ] Migration assistant CLI
- [ ] Documentation updates
- [ ] Performance benchmarking
- [ ] Remove feature flags (make default)

**Go/No-Go Criteria:**
- [ ] >95% classification accuracy
- [ ] <5% parser failure rate
- [ ] <10% build time regression
- [ ] Zero backward compatibility issues

---

## 3. Success Metrics & Monitoring

### Technical Metrics

| Metric | Baseline | Target | Alert Threshold |
|--------|----------|--------|-----------------|
| Classification Accuracy | N/A | >95% | <90% |
| Parser Success Rate | 94% | >97% | <92% |
| Build Time (p50) | 10 min | <11 min | >12 min |
| Build Time (p95) | 25 min | <27 min | >30 min |
| Token Efficiency | 60% | >75% | <65% |
| Fallback Rate | N/A | <5% | >10% |

### Business Metrics

| Metric | Measurement |
|--------|-------------|
| User-reported "weird summaries" | Support tickets categorized |
| Treatment override usage | Dashboard analytics |
| Index rebuild requests | Server logs |
| Rollback rate | Feature flag toggles |

---

## 4. Contingency Plans

### If Classification Accuracy <90%

**Option A:** Simplify to 2 classes
- Structured (code + structured docs)
- Unstructured (everything else)
- Still better than current binary split

**Option B:** Disable for specific file types
- Skip classification for .md files >10KB
- Treat as "unknown" → conservative treatment

### If Parser Failures Increase

**Option A:** Rollback to legacy batch prompts
- Keep classification for analytics only
- Don't change treatment yet

**Option B:** Increase fallback aggressiveness
- Batch fails → individual
- Individual fails → metadata-only
- Never fail the entire build

### If Performance Regresses >20%

**Option A:** Async classification
- Classify in background while building
- Use last-known class if not ready

**Option B:** Caching
- Cache classification results in `.prep/content_cache.json`
- Reuse across builds

---

## 5. Open Questions for Discussion

1. **Should we ship classification without treatment changes first?**
   - Pros: Validates accuracy without risk
   - Cons: No immediate user value, extra computation

2. **Should UnstructuredNarrative skip LLM entirely?**
   - Option: Derive summary from file path + metadata only
   - Saves tokens, but loses nuance

3. **How do we handle content class drift?**
   - File changes from unstructured → structured over time
   - Reclassify on every build? Only on significant changes?

4. **What's the migration story for Team Sync?**
   - Shared indexes between users with different CoDRAG versions
   - Force upgrade? Backward compatibility mode?

---

## 6. Recommendations

### Immediate Actions (Before Sprint 1)

1. **Create validation dataset** - 100 files, hand-labeled
2. **Implement A/B testing framework** - Feature flags, metrics
3. **Add content_class field to schema** - No logic, just field
4. **Measure baseline** - Current parser success rates, build times

### Go/No-Go Decision Gates

| Gate | Criteria | Decision |
|------|----------|----------|
| **Sprint 0** | A/B framework working | Proceed |
| **Sprint 1** | >90% accuracy on 3 classes | Proceed / Simplify |
| **Sprint 2** | <5% parser regression | Proceed / Rollback |
| **Sprint 3** | >95% accuracy, <10% time regression | Proceed / Delay |
| **Sprint 4** | Zero critical bugs in staging | Ship / Fix |

### Final Recommendation

**Proceed with Phase 53** using the **risk-weighted implementation plan** above. The architectural benefits (unified treatment, better doc handling) outweigh the risks IF we:

1. Implement A/B testing first
2. Start with 3 classes, expand gradually
3. Maintain backward compatibility throughout
4. Have clear rollback procedures

**Estimated Timeline:** 5 weeks (with contingency)  
**Confidence Level:** Medium-High (with mitigation strategies)

---

**Next Step:** Review this risk analysis, decide on Pre-Sprint tasks, and create GitHub issues for A/B framework implementation.