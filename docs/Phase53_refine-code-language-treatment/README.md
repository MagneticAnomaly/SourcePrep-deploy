# Phase 53: Refine Code/Language Treatment
## Unified Content Ingestion & Treatment Architecture

**Status:** Planning  
**Priority:** High (blocking optimal Fast Catalogue performance)  
**Estimated Effort:** 2-3 sprints  
**Dependencies:** Phase 22 (Trace Epistemology - complete), Phase 35 (BYOK - stable)

---

## Executive Summary

Current CoDRAG treats content as binary: code files (.py, .js) vs documentation (.md). This creates systematic failures where:

- **Marketing copy** (unstructured narrative) receives "strategic excerpt" treatment meant for API docs
- **Technical specifications** (highly structured) get processed with insufficient context
- **Configuration files** (.json, .yaml) fall through cracks with minimal treatment
- **Mixed-content files** (README with embedded code) get truncated at arbitrary boundaries

**Phase 53 introduces a unified `ContentGraph` abstraction** where all files flow through the same extraction → classification → treatment pipeline, with treatment decisions based on *extractable structure density* rather than file extension.

---

## Current State Analysis

### Code Path (augmenter.py:1115-1118)

```python
is_md = lang == "markdown" or fp.endswith((".md", ".markdown"))
if is_md:
    doc_files.append(node)  # → strategic_excerpt(1000 lines max)
else:
    code_files.append(node)  # → file_head(30 lines)
```

### Current Treatment Matrix

| File Extension | Classification | Extraction Strategy | LLM Treatment | Batch Size |
|----------------|---------------|---------------------|---------------|------------|
| .py, .js, .ts | `code` | First 30 lines | `BATCHED_FILE_SYSTEM` | `CATALOGUE_FILE` (5) |
| .md | `doc` | Strategic excerpt (1000 lines) | `BATCHED_DOC_SYSTEM` | `CATALOGUE_FILE // 5` (1) |
| .json, .yaml | `code` (falls through) | First 30 lines | `BATCHED_FILE_SYSTEM` | 5 |
| .swift, .rs | `code` | First 30 lines | `BATCHED_FILE_SYSTEM` | 5 |

### Failure Patterns (From Production Logs)

```
BatchedResponseParser: all strategies failed (len=5271)
  → Marketing_Copy_and_Plan.md (unstructured, 400 lines)
  
BatchedResponseParser: all strategies failed (len=7081)  
  → TWO_PHASE_ENRICHMENT.md (structured but oversized)
  
Template literal output: {"id": <doc_number>}
  → 3b model confused by complex doc structure
```

**Root Cause:** Binary classification fails to distinguish between:
- Structured API documentation (should get rich treatment)
- Unstructured marketing copy (should get minimal treatment)
- Semi-structured planning docs (need custom treatment)

---

## Proposed Architecture: ContentGraph

### Core Abstraction

```rust
// Rust extraction layer (extends current markdown.rs)
pub enum ContentClass {
    StructuredCode,        // AST-extractable, import/call graphs
    StructuredDocs,        // Section-extractable, rich cross-references
    SemiStructuredDocs,    // Loose sections, moderate references
    UnstructuredNarrative, // Minimal structure, narrative flow
    Configuration,         // Key-value, schema-validated
    Data,                  // Tabular, CSV/JSONL
    Mixed,                 // Complex: README with heavy code blocks
}

pub struct ContentNode {
    pub file_path: PathBuf,
    pub class: ContentClass,
    pub structure: ExtractedStructure,  // AST | SectionGraph | KeyValueTree | None
    pub metrics: ContentMetrics,        // ref_count, complexity, token_estimate
    pub treatment: TreatmentAssignment, // Derived from class + metrics
}

pub struct TreatmentAssignment {
    pub compression_strategy: CompressionStrategy,
    pub llm_treatment: LLMTreatment,
    pub batch_size: u8,
    pub context_lines: u16,
    pub use_structured_output: bool,
}
```

### Treatment Decision Matrix (New)

| ContentClass | Detection Criteria | Extraction | Context Lines | LLM Model | Batch Size |
|--------------|-------------------|------------|---------------|-----------|------------|
| `StructuredCode` | AST nodes > 10, imports > 3 | AST symbols + imports | 30-50 | Fast (3b) | 5-10 |
| `StructuredDocs` | Sections > 5, ref_count > 3 | Section tree + hot sections | 100-200 | Fast (3b) | 3-5 |
| `SemiStructuredDocs` | Sections > 3, ref_count 1-3 | Section headers + first para | 50-100 | Fast (3b) | 2-3 |
| `UnstructuredNarrative` | Sections ≤ 3, refs ≤ 1 | First 30 lines + summary | 30 | Fast (3b) | 1 (skip batch) |
| `Configuration` | Key-value pairs | Schema outline | 50 | Fast (3b) | 5 |
| `Data` | Tabular structure | Schema + sample rows | 20 | Embeddings only | N/A |
| `Mixed` | Code blocks > 3 in .md | Split: code blocks + prose | 50 each | Fast (3b) | 2 |

---

## Implementation Roadmap

### Sprint 1: Content Classification Layer (Week 1)

**Goal:** Replace binary is_markdown check with ContentClass detection

#### Task 1.1: Rust Content Classifier Extension
**File:** `src/codrag/engine/markdown.rs` (extend) + `src/codrag/engine/content_classifier.rs` (new)

```rust
// New module: content_classifier.rs
pub fn classify_content(
    file_path: &Path,
    ast: Option<AST>,
    sections: Vec<Section>,
    refs: Vec<Reference>,
) -> ContentClass {
    if ast.is_some() {
        return ContentClass::StructuredCode;
    }
    
    let ref_count = refs.len();
    let section_count = sections.len();
    let has_code_blocks = sections.iter()
        .any(|s| s.contains_code_blocks);
    
    // Markdown classification logic
    if has_code_blocks && section_count > 5 {
        ContentClass::Mixed
    } else if ref_count > 3 && section_count > 5 {
        ContentClass::StructuredDocs
    } else if section_count > 3 {
        ContentClass::SemiStructuredDocs
    } else if ref_count == 0 && section_count <= 2 {
        ContentClass::UnstructuredNarrative
    } else {
        ContentClass::SemiStructuredDocs  // Default
    }
}
```

**Acceptance Criteria:**
- [ ] Classifier correctly identifies:
  - [ ] API documentation → `StructuredDocs`
  - [ ] Marketing copy → `UnstructuredNarrative`  
  - [ ] Mixed README → `Mixed`
  - [ ] Config files → `Configuration`
- [ ] Classification stored in trace_nodes.jsonl as `content_class` field

#### Task 1.2: Python Binding Updates
**File:** `src/codrag/core/trace_loader.py`

```python
@dataclass
class TraceNode:
    # ... existing fields ...
    content_class: Optional[ContentClass] = None
    structure_metrics: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_rust_json(cls, data: Dict) -> "TraceNode":
        return cls(
            # ... existing ...
            content_class=ContentClass(data.get("content_class")),
            structure_metrics=data.get("structure_metrics"),
        )
```

#### Task 1.3: Classification Integration
**File:** `src/codrag/core/augmenter.py` (refactor `_augment_files_batched`)

```python
# REPLACE:
is_md = lang == "markdown" or fp.endswith((".md", ".markdown"))
if is_md:
    doc_files.append(node)
else:
    code_files.append(node)

# WITH:
classified = defaultdict(list)
for node in file_nodes:
    content_class = node.get("content_class", ContentClass.UNKNOWN)
    classified[content_class].append(node)
```

**Deliverable:** Classification working end-to-end, visible in logs

---

### Sprint 2: Treatment Assignment Engine (Week 2)

**Goal:** Map ContentClass to treatment parameters

#### Task 2.1: Treatment Configuration Schema
**File:** `src/codrag/core/content_treatment.py` (new)

```python
@dataclass(frozen=True)
class TreatmentConfig:
    """Treatment parameters for a content class."""
    context_lines: int
    batch_size: int
    use_strategic_excerpt: bool
    use_structured_output: bool
    system_prompt: str
    max_section_depth: Optional[int] = None
    
class TreatmentRegistry:
    """Maps content classes to treatment configurations."""
    
    _DEFAULTS = {
        ContentClass.StructuredCode: TreatmentConfig(
            context_lines=50,
            batch_size=8,
            use_strategic_excerpt=False,
            use_structured_output=False,
            system_prompt=BATCHED_FILE_SYSTEM,
        ),
        ContentClass.StructuredDocs: TreatmentConfig(
            context_lines=200,
            batch_size=4,
            use_strategic_excerpt=True,
            use_strategic_sections=True,
            max_section_depth=2,
            system_prompt=BATCHED_DOC_SYSTEM,
        ),
        ContentClass.UnstructuredNarrative: TreatmentConfig(
            context_lines=50,
            batch_size=1,  # No batching - unpredictable
            use_strategic_excerpt=False,
            use_structured_output=False,
            system_prompt=BATCHED_NARRATIVE_SYSTEM,  # New: simpler prompt
        ),
        # ... etc
    }
    
    @classmethod
    def get_treatment(cls, content_class: ContentClass) -> TreatmentConfig:
        return cls._DEFAULTS.get(content_class, cls._DEFAULTS[ContentClass.SemiStructuredDocs])
```

#### Task 2.2: Strategic Excerpt Refinement
**File:** `src/codrag/core/augmenter.py` (refactor `_get_strategic_excerpt`)

```python
def _get_strategic_excerpt(
    self,
    file_path: str,
    section_nodes: List[Dict[str, Any]],
    treatment: TreatmentConfig,
) -> str:
    """Get excerpt based on treatment config, not hardcoded values."""
    if not treatment.use_strategic_excerpt:
        return self._get_file_head(file_path, max_lines=treatment.context_lines)
    
    # Use treatment-configured limits
    head_lines = min(300, treatment.context_lines // 2)
    section_lines = 30 if treatment.max_section_depth else 50
    max_total = treatment.context_lines
    
    # ... existing logic with parameterization ...
```

#### Task 2.3: Class-Specific System Prompts
**File:** `src/codrag/core/batch_prompts.py` (add new prompts)

```python
# New prompt for unstructured narrative (simpler, no complex JSON)
BATCHED_NARRATIVE_SYSTEM = """You are a document summarizer. Summarize the content briefly.
Return ONLY a JSON object: {"summary": "1-2 sentence description", "topics": ["topic1"]}
No markdown, no explanation."""

def build_batched_narrative_prompt(items: List[Dict]) -> str:
    """Simplified prompt for unstructured content."""
    parts = [f"Summarize these {len(items)} documents briefly.\n"]
    for i, item in enumerate(items, 1):
        parts.append(f"\n{i}. {item['file_path']}:")
        parts.append(item['content'][:500])  # Limit content
    parts.append("\nJSON response:")
    return "\n".join(parts)
```

**Deliverable:** Treatment selection working, different classes get different context sizes

---

### Sprint 3: Batch Strategy Refinement (Week 2-3)

**Goal:** Fix the batch parsing failures

#### Task 3.1: Template Literal Detection
**File:** `src/codrag/core/batch_strategy.py` (add to BatchedResponseParser)

```python
@staticmethod
def _try_template_literal_fix(text: str) -> Optional[List[Dict]]:
    """Fix responses where LLM preserved template placeholders."""
    import re
    
    # Detect template patterns like <doc_number>, <file_path>
    placeholder_pattern = r'<[a-z_]+>'
    if not re.search(placeholder_pattern, text):
        return None
    
    # Strategy: Replace placeholders with sequential values
    items = []
    for match in re.finditer(r'\{[^{}]*<[^>]+>[^{}]*\}', text):
        item_text = match.group(0)
        # Replace placeholders
        item_text = re.sub(r'<doc_number>', lambda m, c=[0]: str(c[0]+1), item_text)
        item_text = re.sub(r'<file_path>', '"path/to/file"', item_text)
        # ... etc for other placeholders
        
        try:
            items.append(json.loads(item_text))
        except json.JSONDecodeError:
            continue
    
    return items if items else None
```

#### Task 3.2: CoT Stripping Enhancement
**File:** `src/codrag/core/batch_strategy.py` (enhance parse method)

```python
@staticmethod
def parse(response_text: str, expected_count: int = 0, content_class: Optional[ContentClass] = None) -> List[Dict]:
    """Enhanced parse with content-class aware stripping."""
    text = _strip_think_tags(response_text)
    
    # NEW: Content-class aware preamble stripping
    if content_class in (ContentClass.UnstructuredNarrative, ContentClass.Mixed):
        # These types trigger more CoT - strip more aggressively
        text = BatchedResponseParser._strip_cot_preamble(text)
    
    # ... existing strategies ...
    
    # NEW: Try template literal fix for small-model failures
    results = BatchedResponseParser._try_template_literal_fix(text)
    if results:
        return results

def _strip_cot_preamble(text: str) -> str:
    """Strip natural language thinking before JSON."""
    # Find first JSON-like structure
    brace_pos = text.find('{')
    bracket_pos = text.find('[')
    
    start_pos = min(p for p in [brace_pos, bracket_pos] if p >= 0)
    
    # Check if there's a clear delimiter (newline before JSON)
    if start_pos > 0 and '\n\n' in text[:start_pos]:
        return text[text.rfind('\n\n', 0, start_pos)+2:]
    return text
```

#### Task 3.3: Fallback to Individual Processing
**File:** `src/codrag/core/augmenter.py` (augmentation retry logic)

```python
def _call_batch_with_fallback(self, items: List[Dict], treatment: TreatmentConfig):
    """Try batch, fall back to individual if batch fails."""
    try:
        return self._call_batch(items, treatment)
    except BatchParseError as e:
        if len(items) == 1:
            raise  # Already individual, propagate
        
        logger.warning("Batch failed for %d items, falling back to individual", len(items))
        results = []
        for item in items:
            try:
                result = self._call_batch([item], treatment)
                results.extend(result)
            except Exception as inner_e:
                logger.error("Individual processing failed for %s: %s", item['file_path'], inner_e)
                results.append(self._create_fallback_entry(item))
        return results
```

**Deliverable:** Batch parsing more robust, fallback mechanisms in place

---

### Sprint 4: Configuration & UI (Week 3)

**Goal:** Expose treatment settings to users

#### Task 4.1: Settings Schema Update
**File:** `src/codrag/services/settings_store.py`

```python
@dataclass
class ContentTreatmentSettings:
    """User-configurable treatment overrides."""
    structured_code_context: int = 50
    structured_docs_context: int = 200
    unstructured_narrative_context: int = 50
    
    enable_smart_batching: bool = True
    fallback_to_individual: bool = True
    
    # Per-class model overrides (for Phase 44 LLM Mapping integration)
    class_model_overrides: Dict[ContentClass, str] = field(default_factory=dict)
```

#### Task 4.2: Dashboard UI Updates
**File:** `dashboard/src/components/ContentTreatmentSettings.tsx` (new)

- Content class breakdown pie chart
- Treatment parameter sliders per class
- Preview: "Show me how Marketing_Copy.md will be treated"
- Toggle: "Enable experimental treatment engine"

#### Task 4.3: Observability
**File:** `src/codrag/core/content_treatment_metrics.py` (new)

```python
@dataclass
class TreatmentMetrics:
    """Track treatment effectiveness."""
    content_class: ContentClass
    total_files: int
    batch_success_rate: float
    avg_parse_time_ms: float
    fallback_rate: float
    llm_token_efficiency: float  # tokens_in / useful_tokens_out
```

**Deliverable:** Treatment settings visible and configurable in UI

---

### Sprint 5: Validation & Migration (Week 4)

**Goal:** Ensure backward compatibility, measure improvement

#### Task 5.1: Backward Compatibility Mode
**File:** `src/codrag/core/augmenter.py` (compatibility layer)

```python
def _augment_files_batched_legacy(self, file_nodes, ...):
    """Legacy mode: binary code/doc split."""
    # Keep old code path for safety
    
def _augment_files_batched_new(self, file_nodes, ...):
    """New mode: ContentClass-based treatment."""
    # New implementation
    
# Config flag
USE_NEW_TREATMENT = os.getenv("CODRAG_NEW_TREATMENT", "false").lower() == "true"
```

#### Task 5.2: A/B Testing Framework
**File:** `src/codrag/core/treatment_experiment.py` (new)

```python
class TreatmentExperiment:
    """Compare old vs new treatment on same files."""
    
    def compare_batch_strategies(self, file_nodes: List[Dict]) -> ComparisonResult:
        """Run both treatments, compare success rates."""
        old_results = self._run_legacy(file_nodes)
        new_results = self._run_new(file_nodes)
        
        return ComparisonResult(
            old_success_rate=old_results.success_rate,
            new_success_rate=new_results.success_rate,
            token_efficiency_delta=new_results.efficiency - old_results.efficiency,
            recommendation="adopt_new" if new_results.success_rate > old_results.success_rate * 1.1 else "keep_legacy"
        )
```

#### Task 5.3: Validation Dataset
**File:** `tests/fixtures/content_classification/validation_set.jsonl`

Create validation set with known-tricky files:
- Marketing_Copy_and_Plan.md → should be UnstructuredNarrative
- TWO_PHASE_ENRICHMENT.md → should be StructuredDocs
- API.md → should be StructuredDocs
- README.md (simple) → should be SemiStructuredDocs

**Acceptance Criteria:**
- [ ] New treatment succeeds on >95% of validation files
- [ ] Old treatment comparison shows improvement
- [ ] No regressions on existing test suite

---

## Integration with Other Phases

### Phase 44: LLM Mapping Integration
The treatment system provides `content_class` as an input to LLM Mapping:

```python
# In Phase 44 LLM Mapping
task_assignments = {
    "catalogue_structured_code": "fast_model",
    "catalogue_structured_docs": "fast_model",  
    "catalogue_unstructured_narrative": "fast_model_single",  # No batch
    "catalogue_mixed": "code_model",  # Use code model for mixed content
}
```

### Phase 22: Trace Epistemology Integration
Content class feeds into epistemic scoring:

```python
# Unstructured narrative gets lower base confidence
base_confidence = {
    ContentClass.StructuredCode: 0.85,
    ContentClass.StructuredDocs: 0.80,
    ContentClass.UnstructuredNarrative: 0.65,  # Lower confidence
}
```

### Phase 35: BYOK Batching Integration
Treatment config provides batch profiles:

```python
# Map treatment batch_size to BYOK profile
if treatment.batch_size == 1:
    profile = PROFILE_OFF  # No batching
elif treatment.batch_size <= 5:
    profile = PROFILE_CLOUD_SMALL
# etc
```

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Fast Catalogue success rate | ~94% | >98% | Failed parses / total |
| Marketing doc failure rate | ~15% | <2% | Narrative class failures |
| Token efficiency | ~60% | >75% | Useful output / total LLM tokens |
| Batch fallback rate | N/A | <5% | Individual retries / total batches |
| User-reported "weird summaries" | Baseline | -50% | Support ticket categorization |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Classification errors | Fallback to SemiStructuredDocs, manual override in settings |
| Performance regression | Legacy mode flag, A/B testing before full rollout |
| User confusion | Dashboard visualization of content classes |
| Model compatibility | Keep structured output optional per provider |

---

## Open Questions

1. **Should we split Mixed content?** (README with heavy code blocks)
   - Option A: Process as single node with mixed treatment
   - Option B: Split into virtual nodes (prose node + code nodes)
   
2. **How to handle content class drift?** (File changes from structured → unstructured)
   - Reclassify on every build? Only when structure changes significantly?

3. **Integration with embeddings?** (Should narrative docs get different embedding strategy?)
   - Current: All use same nomic-embed model
   - Possible: Narrative docs benefit from passage-level embeddings vs semantic

---

## Appendix A: Content Classification Algorithm

```python
def classify_content(file_path: str, ast: Optional[AST], sections: List[Section], refs: List[Ref]) -> ContentClass:
    """
    Algorithm for content classification.
    
    Priority: Code > Config > Data > Docs (by specificity)
    """
    
    # 1. Code detection (highest priority)
    if ast is not None and ast.nodes > 0:
        return ContentClass.StructuredCode
    
    # 2. Config/Data detection
    ext = Path(file_path).suffix.lower()
    if ext in ('.json', '.yaml', '.yml', '.toml', '.ini'):
        return ContentClass.Configuration
    if ext in ('.csv', '.tsv', '.jsonl'):
        return ContentClass.Data
    
    # 3. Markdown classification (requires Rust extraction)
    if ext == '.md':
        metrics = calculate_doc_metrics(sections, refs)
        
        # Heavily referenced + structured = API docs
        if metrics.ref_count > 5 and metrics.section_count > 5:
            return ContentClass.StructuredDocs
            
        # Lots of code blocks = technical spec
        if metrics.code_block_count > 3:
            return ContentClass.Mixed
            
        # Few sections, no refs = narrative
        if metrics.section_count <= 3 and metrics.ref_count == 0:
            return ContentClass.UnstructuredNarrative
            
        # Default
        return ContentClass.SemiStructuredDocs
    
    # 4. Fallback
    return ContentClass.SemiStructuredDocs

def calculate_doc_metrics(sections: List[Section], refs: List[Ref]) -> DocMetrics:
    return DocMetrics(
        section_count=len(sections),
        ref_count=len(refs),
        avg_section_depth=mean(s.depth for s in sections),
        code_block_count=sum(1 for s in sections if s.has_code_blocks),
        total_lines=sum(s.line_count for s in sections),
    )
```

---

## Appendix B: Migration Checklist

- [ ] Rust content classifier implemented
- [ ] Python bindings updated
- [ ] Treatment registry configured
- [ ] Batch parser enhancements deployed
- [ ] Settings UI updated
- [ ] Validation dataset created
- [ ] A/B test completed
- [ ] Documentation updated
- [ ] Migration guide for users
- [ ] Legacy mode deprecation timeline set

---

**Next Step:** Review this plan, prioritize sprints, and create GitHub issues for Task 1.1 (Rust content classifier).