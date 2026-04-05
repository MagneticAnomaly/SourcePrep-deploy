# Raw Evidence — MCP Tool Output Analysis

> Supporting data for Phase 73 Quality Assessment
> Date: 2026-04-04

---

## 1. `codrag` Overview — Output Statistics

**Total output:** 745 lines, ~52KB

### Content Breakdown

| Section | Lines | % of Total | Usefulness |
|---------|-------|-----------|------------|
| Module summaries (top 3 detailed)         | 3 lines       
| 0.4% | 🟢 Excellent |
| Architecture table + pipeline stages      | ~44 lines | 5.9%      | 🟢 Excellent |
| MCP tool list                             | ~6 lines  | 0.8%      | 🟢 Excellent |
| Hub content (epistemology doc)            | ~128 lines| 17.2%     | 🟡 Good (but 3× duplicated) |
| Hub content (unique only)                 | ~43 lines | 5.8%      | 🟢 Excellent |
| Hub content (duplicate waste)             | ~85 lines | 11.4%     | 🔴 Pure waste |
| Module list (602 entries)                 | ~604 lines| 81.1%     | 🔴 Overwhelming |
| **Genuinely useful content**              **~96 lines** **~13%** | — |

### Duplication Evidence

The following identical block appeared 3 times (lines 12–51, 55–95, 98–137):

```
CoDRAG is a **local-first, AI-powered codebase intelligence system**...
| Layer | Technology | Purpose |
...
Stage 1:  File Discovery (scan repo)
...
CoDRAG exposes **5 MCP tools**:
```

Each repetition was identical, word for word. The hub system appears to be emitting the same source chunk multiple times because it's accessed through different structural paths.

### Module List Analysis

Of the 602 modules listed:
- **7 modules** have >20 files (architecturally significant)
- **23 modules** have 5-20 files (meaningful subsystems)
- **83 modules** have 2-4 files (small components)
- **489 modules** have exactly 1 file (effectively just a file listing)

The 489 single-file "modules" include entries like:
- "Storybook CSS Injection Utilities" (1 file)
- "PropTypes Runtime Validation" (1 file)
- "ES Compatibility Polyfills" (1 file)
- "JSX Transformation Runtime" (1 file)
- "..." (1 file) — yes, literally "..." as a module name

These provide no architectural insight. An agent cannot reason about 602 modules. Human working memory is 7±2 items; AI context windows have different constraints, but signal dilution still applies.

---

## 2. `codrag_search` — Query/Response Analysis

### Query 1: "how does the pipeline orchestrator process files"

**Expected:** Content from `src/codrag/services/pipeline/orchestrator.py` (2,643 lines, the actual orchestrator)

**Actually received:**
- `src/codrag/core/scheduler.py` — a 51-line stub that delegates to `pipeline_scheduler`
- `src/codrag/core/watcher.py` — the filesystem watcher (380 lines)

**Analysis:** Neither file answers the question. `scheduler.py` is a thin delegation layer. `watcher.py` is about filesystem events, not file processing. The core orchestrator logic (state machine, stage execution, worker dispatch) was completely missed.

**Possible causes:**
1. `orchestrator.py` is 2,643 lines — it may be chunked in a way that dilutes its embedding signal
2. The words "process files" may match better against watcher.py's file event handling than orchestrator.py's stage-based processing
3. The scheduler stub mentions "pipeline" prominently in its module docstring

### Query 2: "MCP tool handler request response"

**Expected:** Content from `src/codrag/mcp/server.py` (2,427 lines, the MCP server)

**Actually received:**
- `src/codrag/core/model_readiness.py` — Ollama model readiness detection (~440 lines)

**Analysis:** This is a near-total miss. model_readiness.py handles HTTP requests to Ollama, which may explain why "request response" matched. But no part of this file relates to MCP protocol handling. The MCP server file at `src/codrag/mcp/server.py` was indexed (it appears in the audit as a 2,427-line file) but was not retrieved.

### Query 3: "how does the context assembly work for MCP tool responses"

**Expected:** The context assembly logic — likely in the MCP server or a dedicated context module

**Actually received:**
- `src/codrag/core/llm_client.py` — LLM client with response parsing (~280 lines)

**Analysis:** Partial relevance. The LLM client handles output parsing, but "context assembly" in the MCP sense (how CoDRAG assembles the chunks, modules, and hubs returned by `codrag` and `codrag_search`) is a different subsystem. The file was well-documented and the code quality was high — so when retrieval works, the content quality is good.

### Pattern Observed

All three queries share a pattern: **large, important files are systematically missed in favor of smaller peripheral files.** This suggests an inverse-size bias in the retrieval pipeline — chunking large files fragments their semantic identity, while small focused files maintain coherent embeddings.

---

## 3. `codrag_impact` — Output Analysis

### Query: `llm_client.py` dependents

**Output:** 30 total dependents (19 direct, 11 transitive)

**Quality indicators:**
- ✅ Every file path is useful and accurate
- ✅ Relationship types (`[imports]` vs `[calls]`) add real information
- ✅ Direct vs transitive separation is clear
- ✅ No noise — every line contributes
- ✅ The output is compact (~30 lines for 30 relationships)

**Bytes per useful datum:** ~20 bytes per relationship (file + type)
**Compare to `codrag` overview:** ~70 bytes per module entry, 80% of which are noise

This is what good MCP tool output looks like: dense, typed, hierarchical, and actionable.

---

## 4. `codrag_audit` — Output Analysis

### Findings Breakdown

| Severity | Count | Actionable | Noise |
|----------|-------|------------|-------|
| Critical | 11 | 3 (code files) | 8 (lockfiles, logs, docs) |
| Warning | 26 | ~15 | ~11 |
| Info | 63 | ~40 | ~23 |
| **Total** | **100** | **~58** | **~42** |

### Critical Findings — Noise Analysis

Of 11 critical findings:
- `package-lock.json` × 3 — auto-generated, not actionable
- `MASTER_TODO.md` — a planning document, length is expected
- `ENTERPRISE_ADMIN_DESIGN.md` — a design doc, length is expected  
- `overnight_2026-02-21.json` — a log file, length is expected
- `PLAN.md` — a planning document, length is expected
- **Actually critical:** `orchestrator.py` (2,643), `server.py` (2,427), `augmenter.py` (2,136)

Only **3 of 11 "critical" findings** represent genuine code quality issues. The other 8 are lockfiles, logs, markdown docs, and planning documents being flagged for "large file" the same way as a god-class Python module.

### What's Missing from Audit

The audit currently only surfaces file-size findings. CoDRAG has the graph data to surface much more interesting architectural findings:
- Circular dependency cycles (the overview mentions 162 import cycles)
- High fan-in/fan-out modules (hub concentration)
- Orphan modules (no incoming edges)
- API surface sprawl
- Cross-layer violations

None of these appeared in the default scan despite being more architecturally significant than "your lockfile is big."

---

## 5. Overall Token Efficiency Analysis

Across all tool calls in this session:

| Tool Call | Tokens Received (est.) | Tokens Useful (est.) | Efficiency |
|-----------|----------------------|---------------------|------------|
| `codrag` overview | ~15,000 | ~2,500 | 17% |
| `codrag_search` #1 | ~4,500 | ~500 | 11% |
| `codrag_search` #2 | ~5,000 | ~200 | 4% |
| `codrag_search` #3 | ~3,500 | ~2,000 | 57% |
| `codrag_impact` | ~500 | ~450 | 90% |
| `codrag_audit` | ~1,500 | ~600 | 40% |
| **Total** | **~30,000** | **~6,250** | **~21%** |

**~79% of the context budget consumed by CoDRAG tools was noise or duplication.**

The standout is `codrag_impact` at 90% efficiency. The worst is `codrag_search` #2 at 4% (wrong file entirely for the query).
