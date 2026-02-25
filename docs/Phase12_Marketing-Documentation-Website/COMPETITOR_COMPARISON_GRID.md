# CoDRAG Competitor Comparison Grid (Draft)

This document is a direct feature-by-feature comparison grid for use on the marketing website and in sales materials. It compares CoDRAG against the major categories of competing tools a prospective user is likely to evaluate.

**Competitor categories** (we avoid naming specific small/indie tools to prevent free advertising — instead we group by architecture):

| Column | Represents |
|--------|-----------|
| **CoDRAG** | Us |
| **IDE Built-in** | Cursor, Windsurf, Claude Code — the indexing built into AI IDEs |
| **Cloud Indexers** | Augment Code, Sourcegraph Cody — cloud-first code search + context |
| **AST Context Engines** | Local-first tools using tree-sitter + SQLite/FTS, distributed as IDE extensions |
| **LSP-Backed MCP Tools** | Tools wrapping Language Server Protocol for semantic retrieval |
| **CLI Semantic Search** | Privacy-first grep-for-AI tools (vector search from the terminal) |

---

## Feature Comparison Grid

### Core Retrieval

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| Vector semantic search | ✅ ONNX local | ✅ Cloud | ✅ Cloud | ❌ FTS/TF-IDF only | ❌ | ✅ Local |
| Full-text keyword search (FTS5) | ✅ | Partial | ✅ | ✅ | ❌ | ❌ |
| Deterministic dependency graph | ✅ Rust parser | ❌ | Partial | ✅ | ✅ (via LSP) | ❌ |
| Graph-navigated context expansion | ✅ | ❌ | ❌ | Partial | Partial | ❌ |
| Cross-file structural queries | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |

### Context Quality

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| Multi-level structural compression (LOD) | ✅ Full→Sig→Name | ❌ | ❌ | Partial (sig+doc only) | ❌ | ❌ |
| Language-aware doc compression | ✅ LLMLingua-2 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Intent detection (debug/arch/impl) | ✅ Auto per-query | ❌ | ❌ | ❌ | ❌ | ❌ |
| Role weights (code vs docs vs tests) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Path weights (per-directory boost) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Token budget enforcement | ✅ Hard ceiling | ❌ Varies | ✅ | Partial | ❌ | ❌ |

### Session Continuity & Freshness

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| Persistent Agent Memory (cross-session observations) | ✅ File-linked | ❌ | ❌ | Partial (basic notes) | ❌ | ❌ |
| Automatic staleness detection on observations | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Incremental re-indexing | ✅ Symbol-level | Varies | ✅ | ✅ File-level | N/A (live) | ❌ Full rebuild |
| Real-time file watcher | ✅ | ✅ | ✅ | Partial | N/A (live) | ❌ |
| Visible freshness health indicator | ✅ Dashboard | ❌ | ❌ | ❌ | ❌ | ❌ |

### Transparency & Control

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| See relevance scores per chunk | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| See exactly what was sent to the LLM | ✅ | ❌ | ❌ | ❌ | ❌ | Partial |
| Dashboard UI for health + inspection | ✅ | ❌ | ✅ (web app) | ❌ | ❌ | ❌ |
| Per-query control (k, max_chars, compression) | ✅ | ❌ | Partial | Partial | ❌ | Partial |
| Configurable include/exclude scoping | ✅ | Partial | ✅ | Partial | ❌ | ✅ |

### Architecture & Deployment

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| 100% local (no cloud required) | ✅ | ❌ (cloud index) | ❌ | ✅ | ✅ | ✅ |
| Ships own embedding model (ONNX) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Works offline / air-gapped | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| No runtime dependency per language | ✅ tree-sitter | N/A | N/A | ✅ tree-sitter | ❌ Needs LSP | ✅ |
| MCP-native (editor-agnostic) | ✅ | ❌ (locked) | ❌ (locked) | ❌ (IDE ext) | ✅ | Partial |
| Multi-project registry | ✅ | ❌ | ✅ | Partial | ❌ | ❌ |
| Desktop companion app | ✅ Tauri | N/A | Web app | ❌ | ❌ | ❌ |

### Language & Parser Support

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| Languages supported | 15+ via tree-sitter | Varies | Most | 5–15 via tree-sitter | Per-LSP | Any (text) |
| AST-level parsing | ✅ | ❌ | ✅ | ✅ | ✅ (via LSP) | ❌ |
| LLM-inferred edges (dynamic refs) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Handles circular imports | ✅ | N/A | ✅ | ✅ | ✅ | N/A |

### Pricing & Licensing

| Feature | CoDRAG | IDE Built-in | Cloud Indexers | AST Engines | LSP MCP Tools | CLI Search |
|---------|--------|-------------|----------------|-------------|---------------|------------|
| Free tier | ✅ (2 projects) | ✅ (limited) | ❌ or limited | ✅ (varies) | ✅ (open source) | ✅ (open source) |
| One-time perpetual license | ✅ $79 | ❌ | ❌ | ❌ | N/A | N/A |
| No subscription required | ✅ | ❌ ($20/mo) | ❌ ($19–49/mo) | Varies | N/A | N/A |
| No telemetry / data collection | ✅ | ❌ | ❌ | Varies | ✅ | ✅ |
| BYOK (bring your own LLM key) | ✅ | ❌ (vendor LLM) | ❌ (vendor LLM) | Partial | N/A | N/A |

---

## CoDRAG's Unique Differentiators (Summary)

These are capabilities where CoDRAG has **no direct equivalent** in any competitor category:

1. **Persistent Agent Memory with Staleness Detection** — File-linked observations that persist across sessions and automatically flag `[STALE]` when source files change. No other tool tracks the AI's own learned knowledge against code changes.

2. **Dual-Channel Adaptive Compression** — Structural LOD compression for code (full source → signatures → names) and language-aware compression for documentation, chosen automatically per chunk. Other tools either dump raw text or skip compression entirely.

3. **Intent Detection** — Automatic per-query classification (debug / architecture / implementation) that adjusts file-type weights without user configuration. No competitor offers this.

4. **Full Retrieval Transparency** — Relevance scores, token counts, chunk boundaries, and exact content sent to the LLM — all visible in the Dashboard. IDE built-ins and cloud indexers are black boxes.

5. **Editor-Agnostic Portability** — MCP-first design means your index, weights, observations, and configuration survive editor switches. IDE built-in indexing is locked to that IDE.

6. **Perpetual License + No Telemetry** — $79 one-time, works offline forever, no data collection. Every cloud indexer and most IDE tools require a recurring subscription and send data to their servers.

---

## Messaging Guidelines for the Grid

- **Don't name specific indie competitors.** Use category labels (AST Engine, CLI Search). This avoids giving them free visibility and keeps the grid timeless.
- **Be honest about parity.** Where competitors match us (e.g., incremental indexing, offline mode), mark them ✅. Credibility matters more than column-stuffing.
- **Lead with our unique rows.** In any visual presentation, place Persistent Agent Memory, Compression, and Intent Detection near the top — these have the most ❌s in competitor columns.
- **Cloud Indexers are the biggest threat.** Augment Code and Sourcegraph Cody have strong context modeling. Our advantages are: local-first, perpetual license, transparency, and no vendor lock-in. Don't try to out-feature them on retrieval quality — compete on trust, cost, and control.
- **AST Engines are the closest competitors.** They share our architecture (tree-sitter, SQLite, local-first). Our advantages: true semantic search (ONNX embeddings vs. TF-IDF), persistent staleness-aware memory, dual-channel compression, a real dashboard, and MCP-native editor portability.
