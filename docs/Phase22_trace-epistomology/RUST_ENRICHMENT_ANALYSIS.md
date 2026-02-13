# Rust Pass Enrichment — Analysis of Two Theories

**Parent**: `Phase22_trace-epistomology/README.md`  
**Status**: Analysis Complete

---

## Theory 1: The Rust Pass is Underutilized

### Finding: Confirmed. Massively underutilized for docs.

The current Rust trace build (`codrag-graph::build_trace`) handles files in two paths:

**Code files** (`.py`, `.ts`, `.swift`, etc.):
- `detect_language()` returns a language tag
- Rust reads the **full file content** (`std::fs::read_to_string`)
- tree-sitter parses it → extracts symbol nodes + import/contains edges
- Content is then **discarded** (not stored in the trace output)
- Result: Rich graph with symbols, relationships, spans

**Everything else** (`.md`, `.json`, `.yaml`, etc.):
- `detect_language()` returns `None`
- **No content is read. No parsing. No edges. Nothing.**
- A bare `file` node is created with `metadata: Default::default()` (all fields None)
- Result: An empty node floating in the graph with zero connections

This means in the HomeColab trace (989 nodes), every `.md` file — all 200+ of them containing the project's entire institutional memory — is a **dead node** with no edges, no metadata, no structure. The augmenter then reads 30 lines and asks the 3b to classify it. That's the entirety of what we know about these files.

### Why "just read more lines in the augmenter" isn't the fix

The augmenter reading 30 vs 100 vs 500 lines doesn't solve the fundamental problem: **docs have no graph connections**. A code file has import edges connecting it to other files. A doc file has nothing. The 14b enrichment pass (Pass 2) was designed to use neighbor summaries — but docs have no neighbors.

The fix needs to happen at the structural layer: **Rust should extract document structure.**

### What Rust can extract from `.md` files (zero LLM, pure regex/parsing)

All of these are **cheap** operations that Rust can do in microseconds per file:

#### 1. Section Headers → "section" nodes
```markdown
# Ad Framework Status          → section node, depth 1
## Quick Status Overview        → section node, depth 2
### 1. AdManager.swift          → section node, depth 3
```

Each `##` header becomes a node:
```json
{
  "id": "sec:Docs/ADS_FRAMEWORK_STATUS.md:8",
  "kind": "section",
  "name": "Quick Status Overview",
  "file_path": "Docs/ADS_FRAMEWORK_STATUS.md",
  "span": {"start_line": 8, "end_line": 20},
  "metadata": {"depth": 2}
}
```

With `contains` edges from the file node to each section node. This gives the augmenter **structural context** — it can augment individual sections, not just whole files.

#### 2. Backtick References → `references` edges
```markdown
`Managers/AdManager.swift`
`FirestoreManager`
`InterstitialAdController.swift`
```

Regex: `` `([A-Za-z0-9_/.]+\.(swift|py|ts|tsx|js|json|md))` ``

If the referenced path matches a known file node in the graph → create a `references` edge:
```json
{
  "kind": "references",
  "source": "file:Docs/ADS_FRAMEWORK_STATUS.md",
  "target": "file:Managers/AdManager.swift",
  "metadata": {"confidence": 1.0, "line": 12}
}
```

If it matches a known symbol name → create a `mentions` edge to the symbol node.

**This is the biggest win.** Suddenly docs are connected to the code they describe. The graph becomes cross-referenced. Pass 2 enrichment has neighbor context for docs.

#### 3. Markdown Links → `links_to` edges
```markdown
See [Link Unfurling Findings](1_Link_unfurrling_findings.md)
Related: [MONETIZATION_STRATEGY](../Monetization/MONETIZATION_STRATEGY.md)
```

Regex: `\[([^\]]+)\]\(([^)]+)\)`

Resolve relative paths → create `links_to` edges between docs.

#### 4. Status Markers → metadata on file node
```markdown
**Status**: ✅ Framework Complete, ⏳ Backend Required
**Status**: Research Complete
**Verdict**: We can unlock "Verified" data
```

Regex patterns for common status lines. Store as metadata:
```json
{
  "metadata": {
    "doc_status_markers": ["✅ Framework Complete", "⏳ Backend Required"],
    "has_status_line": true,
    "has_verdict": true
  }
}
```

This is heuristic, not perfect — but it gives the LLM a strong starting signal.

#### 5. Table Extraction → metadata
```markdown
| Component | Status | File |
|-----------|--------|------|
| AdManager | ✅ Complete | `Managers/AdManager.swift` |
```

Detect markdown tables, extract row count and header names. Don't parse content (that's the LLM's job) but flag: "this doc has a status table with 7 rows."

#### 6. Front-matter (YAML) → metadata
```yaml
---
title: Ad Framework Status
status: complete
last_updated: 2025-10-21
---
```

Some docs have YAML front-matter. Rust can extract this trivially.

#### 7. Document Metrics → metadata
- Line count
- Section count (number of `#` headers)
- Reference density (backtick references per 100 lines)
- Link count (markdown links to other files)
- Has code blocks (fenced ``` blocks)
- Estimated reading time

These are all free and give the LLM immediate triage signals.

### Performance Impact

For 200 `.md` files averaging 150 lines each:
- Reading: ~30K lines total → ~1.5MB → **< 5ms** in Rust (memory-mapped I/O)
- Regex extraction: ~1000 backtick refs + ~200 links → **< 10ms**
- Section parsing: ~800 headers → **< 5ms**
- Node/edge creation: ~800 section nodes + ~1200 edges → **< 2ms**

**Total: < 25ms.** The user's "20 sec instead of 4" is way conservative — this adds essentially nothing to build time. The entire Rust trace build is 72ms; markdown extraction would add maybe 25ms. Call it 100ms total.

### Implementation: New `codrag-parser` module

```
engine/crates/codrag-parser/src/
  markdown.rs       ← NEW: markdown structure extraction
  python.rs
  typescript.rs
  ...
```

`markdown.rs` wouldn't use tree-sitter (overkill for markdown). It would be a simple line-by-line regex scanner:

```rust
pub fn analyze_markdown(file_path: &str, content: &str) -> ParseResult {
    let mut result = ParseResult::empty();
    let file_id = stable_file_node_id(file_path);
    
    for (line_num, line) in content.lines().enumerate() {
        let line_1 = line_num + 1;
        
        // Section headers
        if let Some(caps) = HEADER_RE.captures(line) { ... }
        
        // Backtick references to files
        for caps in BACKTICK_FILE_RE.captures_iter(line) { ... }
        
        // Markdown links
        for caps in MD_LINK_RE.captures_iter(line) { ... }
        
        // Status markers
        if STATUS_RE.is_match(line) { ... }
    }
    
    result
}
```

Then in `build_trace()`, change the `else` branch:

```rust
} else if entry.path.ends_with(".md") || entry.path.ends_with(".markdown") {
    let content = std::fs::read_to_string(&entry.abs_path)?;
    let md_result = codrag_parser::markdown::analyze_markdown(&entry.path, &content);
    for node in md_result.nodes { graph.add_node(node); }
    for edge in md_result.edges { graph.add_edge(edge); }
    files_parsed += 1;
} else {
    files_parsed += 1;
}
```

### Why read full files?

The user asked "why not read the full files?" The answer depends on which files:

**Code files**: Rust already reads them fully for tree-sitter. The content isn't stored because the trace is a graph, not a content store. The augmenter re-reads from disk when it needs source snippets. Storing full content in the trace would bloat `trace_nodes.jsonl` by ~3MB for minimal benefit (files are already on disk).

**Doc files**: Rust currently reads NOTHING. This is the real gap. Rust should read the full content — not to store it, but to **extract structure from it**. Headers, references, links, status markers. The extracted structure becomes nodes and edges in the graph, which is exactly what the graph is for.

**The augmenter can then read more lines too.** Currently `_get_file_head()` reads 30 lines for file classification. For `.md` files, this should be 100+ lines (docs front-load their value in headers and introductions). This is a one-line change in `augmenter.py`:

```python
max_lines = 100 if file_path.endswith('.md') else 30
head = self._get_file_head(file_path, max_lines=max_lines)
```

But the real win is the Rust-extracted edges — those give the LLM contextual awareness that more lines alone can't provide.

---

## Theory 2: LLM-Guided Rust Re-Trace

### The Idea

```
Pass 0  (Rust)  → Structural trace: nodes + edges (imports, contains)
Pass 1  (LLM)   → Fast catalogue: summaries + roles + RELATIONSHIP HYPOTHESES
Pass 0.5 (Rust) → Re-trace with LLM-identified relationships
Pass 2  (LLM)   → Epistemic enrichment with the richer graph
```

The LLM identifies relationships that static parsing can't see. Rust validates and traces them. Each node is marked as having had the combined pass, preventing redundant work.

### Analysis: This is genuinely brilliant, with caveats.

#### What the LLM can identify that Rust can't

| Relationship type | Example | Why Rust can't see it |
|---|---|---|
| **Semantic grouping** | "These 6 files form the ad framework" | No import edges between AdConfig and BannerView — they communicate through a coordinator |
| **Convention-based patterns** | "*Manager.swift manages *View.swift" | Naming conventions aren't edges |
| **Indirect dependencies** | "VoteButton uses the voting state machine from VOTING_STATE_MACHINE.md" | Doc ↔ code link with no import |
| **Architectural layers** | "This is a presentation-layer file that should never import data-access directly" | Architectural constraints aren't in the AST |
| **Functional equivalence** | "OldListingCard and NewListingCard do the same thing — migration in progress" | Requires understanding intent, not structure |

#### What Rust can do with these hypotheses

1. **Validate file existence**: LLM says "relates to AdConfig.swift" — Rust checks if that node exists in the graph. If not, discard the hypothesis.

2. **Add typed edges**: New edge kinds that are structurally distinct from parser-derived edges:
   ```json
   {
     "kind": "semantic_group",
     "source": "file:Components/Ads/InterstitialAdManager.swift",
     "target": "file:Components/Ads/AdConfiguration.swift",
     "metadata": {
       "confidence": 0.85,
       "inferred_by": "llm_pass1",
       "relationship": "coordinates_with",
       "group": "ad-framework"
     }
   }
   ```

3. **Compute transitive closure**: Once semantic edges are added, Rust can compute "reachability" through the expanded graph. If A→B (semantic) and B→C (import), then A can reach C — useful for Pass 2 neighbor gathering.

4. **Validate bidirectional references**: If the LLM says "Doc X documents Code Y", and the Rust markdown parser (from Theory 1) also found a backtick reference from Doc X to Code Y — **mutual confirmation**. Boost confidence to 1.0.

5. **Cluster analysis**: With semantic edges, Rust can run connected-component analysis to identify subsystems. This is a graph algorithm that's trivial for Rust but impossible for an LLM (which can't hold the whole graph in context).

#### The Risk: LLM Hallucination Contaminating the Graph

This is the real concern. If the LLM hallucinates "FileA relates to FileB" and we add that edge, it becomes structural "truth" that future passes build on. Bad edges propagate through the enrichment loop.

**Mitigations** (all implementable):

1. **Strict typing**: LLM-inferred edges use `kind: "inferred"`, never `kind: "imports"` or `kind: "contains"`. The graph cleanly separates factual edges from hypothetical ones.

2. **Confidence gating**: Only add edges where the LLM reports confidence >= 0.7. Below that, discard.

3. **Rust validation**: The second Rust pass doesn't blindly add edges. It validates:
   - Both endpoints exist as nodes in the graph
   - The source and target are of compatible kinds (file→file, file→symbol, not symbol→symbol for "documents" edges)
   - No duplicate edges already exist

4. **Decay and pruning**: Inferred edges that are NOT confirmed by Pass 2 (the 14b doesn't mention this relationship when enriching either endpoint) get their confidence decayed. After 2 passes without confirmation, they're pruned.

5. **Never override factual edges**: If the LLM says "A doesn't import B" but Rust's tree-sitter found an import edge, the import edge is authoritative. LLM-inferred edges are additive only.

#### Is this overkill?

**No, if done right.** The cost analysis:

| Step | Cost | Time |
|---|---|---|
| Pass 0 (Rust structural) | Free (already happening) | 72ms |
| Pass 1 (3b LLM) | Already happening | ~10 min |
| **New: extract relationship hints from Pass 1 output** | ~0 extra cost (parse existing JSON output for a "related_files" field) | ~1ms |
| **New: Pass 0.5 (Rust re-trace)** | Validate + add edges | ~5ms |
| Pass 2 (14b enrichment) | Already planned | ~60 min |

The only new cost is adding a `"related_files"` field to the Pass 1 prompt and having Rust validate the LLM's answers. **The second Rust pass is essentially free** — it's just adding pre-validated edges to an in-memory graph, not re-parsing files.

#### Practical Implementation

**Modify the Pass 1 prompt** to ask for relationships:

Current Pass 1 output:
```json
{"summary": "...", "role": "core", "confidence": 0.95}
```

Enhanced Pass 1 output:
```json
{
  "summary": "...",
  "role": "core",
  "confidence": 0.95,
  "related_files": [
    {"path": "Components/Ads/AdConfiguration.swift", "relationship": "reads_config_from"},
    {"path": "Docs/ADS_FRAMEWORK_STATUS.md", "relationship": "documented_by"}
  ]
}
```

The 3b model already sees the file path and imports. Asking it "what other files might this relate to?" is a very light addition. It won't always be right, but it doesn't need to be — Rust validates.

**New function in `codrag-graph`**:

```rust
/// Incorporate LLM-inferred relationships into the graph.
/// Validates all endpoints exist and adds typed edges.
pub fn incorporate_inferred_edges(
    &mut self,
    inferences: Vec<InferredRelationship>,
) -> IncorporateResult {
    let mut added = 0;
    let mut rejected = 0;
    
    for inf in inferences {
        // Validate both endpoints exist
        let source_exists = self.nodes.contains_key(&inf.source_id);
        let target_id = stable_file_node_id(&inf.target_path);
        let target_exists = self.nodes.contains_key(&target_id);
        
        if !source_exists || !target_exists {
            rejected += 1;
            continue;
        }
        
        if inf.confidence < 0.7 {
            rejected += 1;
            continue;
        }
        
        // Add as inferred edge (distinct from structural)
        self.add_edge(ParsedEdge {
            id: stable_edge_id("inferred", &inf.source_id, &target_id, &inf.relationship),
            kind: "inferred".to_string(),
            source: inf.source_id,
            target: target_id,
            metadata: EdgeMetadata {
                confidence: inf.confidence,
                ..Default::default()
            },
        });
        added += 1;
    }
    
    IncorporateResult { added, rejected }
}
```

**Marking nodes as having had the combined pass**: Add a field to the augmentation entry:

```json
{
  "node_id": "file:AdManager.swift",
  "pass_history": ["rust_v1", "llm_3b_v1", "rust_v1.5", "llm_14b_v1"],
  "last_structural_pass": "rust_v1.5"
}
```

This prevents re-running Rust re-trace unless the source file changes.

---

## How Theories 1 and 2 Combine

These aren't competing ideas — they're **complementary layers**:

```
┌────────────────────────────────────────────────────────┐
│ Pass 0: Rust Structural + Markdown Extraction          │
│   Code files: tree-sitter → symbols + imports          │
│   Doc files:  regex → sections + references + links    │  ← Theory 1
│   Output: rich graph with doc↔code edges               │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Pass 1: 3b Fast Catalogue (enhanced prompt)            │
│   Now includes: "related_files" field                  │
│   Output: summaries + roles + relationship hypotheses  │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Pass 0.5: Rust Re-Trace (validate + incorporate)       │  ← Theory 2
│   Validates LLM relationship hypotheses                │
│   Adds inferred edges to graph                         │
│   Runs graph algorithms (connected components, etc.)   │
│   Output: enriched graph with semantic edges           │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Pass 2+: 14b Epistemic Enrichment                      │
│   Now has: structural edges + doc refs + inferred edges│
│   Much richer neighbor context for every node          │
│   Output: deep epistemic understanding                 │
└────────────────────────────────────────────────────────┘
```

Theory 1 gives docs **structural connections** (backtick refs, markdown links).
Theory 2 gives the whole graph **semantic connections** (LLM-hypothesized relationships, Rust-validated).

Together, by the time Pass 2 runs, every node — code and doc alike — has a rich neighborhood of both factual and semantic edges. The 14b model sees a complete picture.

---

## The Feedback Loop Formalized

With both theories implemented, the full loop becomes:

```
Rust (facts) → LLM (hypotheses) → Rust (validation) → LLM (deepening) → ...
```

This is a **hypothesis-and-test loop** where:
- **Rust is the tester**: fast, deterministic, can validate file existence, compute graph properties, check for contradictions
- **LLM is the hypothesizer**: can understand intent, group by concept, identify patterns Rust can't see

Each cycle produces a strictly richer graph. Convergence happens when the LLM stops generating new hypotheses that Rust can validate.

### Why this isn't infinite

1. **Rust validation prunes bad hypotheses** — the graph only grows with validated edges
2. **Diminishing returns** — after 2-3 cycles, most relationships are discovered
3. **Budget control** — the LLM passes have token budgets; when budget is exhausted, the loop stops
4. **Epistemic score convergence** — when all nodes reach 0.95+, the loop self-terminates

### Why this isn't risky (with proper safeguards)

1. **Edge typing** — inferred edges are always distinguishable from structural edges
2. **Confidence gating** — low-confidence hypotheses are discarded
3. **Rust validation** — hallucinated file references are caught immediately
4. **Decay and pruning** — unconfirmed inferences are removed after 2 passes
5. **Additive only** — LLM can never override or delete structural edges

---

## Recommendation

### Ship order:

1. **Theory 1 first** (Rust markdown extraction) — biggest bang for buck, no LLM changes needed, purely additive. Gives docs structural connections immediately.

2. **Theory 2 second** (LLM-guided re-trace) — builds on Theory 1. Requires Pass 1 prompt changes + new `incorporate_inferred_edges` function. More architectural but the value is multiplicative.

### Estimated effort:

| Item | Effort | Impact |
|---|---|---|
| `markdown.rs` in codrag-parser | Medium (2-3 days) | **Critical** — unlocks doc intelligence |
| `build_trace` markdown branch | Small (1 day) | Wiring |
| Pass 1 prompt: `related_files` field | Small (1 day) | Captures relationships cheaply |
| `incorporate_inferred_edges` | Medium (2 days) | Validates LLM hypotheses |
| Pass 0.5 orchestration in Python | Small (1 day) | Wiring between Rust and LLM |
| Augmenter: read 100 lines for `.md` | Trivial (1 line) | Immediate quality boost |

---

## Open Questions

1. **Should the second Rust pass also re-parse code files that the LLM flagged as misidentified?** (e.g., LLM says "this .js file is actually a config, not a script" — could trigger re-parse with different heuristics.) Probably not for v1.

2. **Should we add a tree-sitter markdown grammar?** There is one (`tree-sitter-markdown`). It's more robust than regex for nested structures. But regex is simpler and sufficient for our needs (headers, links, code refs). Start with regex, upgrade to tree-sitter if we need to handle complex markdown.

3. **How do we handle `.json` files?** They're also `detect_language → None` currently. Could extract key names and structure cheaply. Lower priority than markdown but same principle applies.

4. **Should inferred edges be stored in a separate file?** (e.g., `trace_inferred_edges.jsonl`) This would keep the structural trace clean and make it easy to rebuild inferred edges independently. Recommended.
