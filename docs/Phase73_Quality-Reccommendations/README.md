# Phase 73 — MCP Tool Quality Assessment

> **Research Phase**: Epistemic Quality Audit of CoDRAG MCP Tool Outputs
> **Date**: 2026-04-04
> **Method**: Real-world tool invocations with critical analysis of what an AI agent actually receives and can use

---

## Purpose

CoDRAG is an MCP server that provides epistemic knowledge and structural understanding of a codebase. This research phase asks a simple question: **when an AI agent calls these tools, does it actually get useful context?**

This document is the result of calling every CoDRAG MCP tool in a real session and honestly evaluating what came back — what was genuinely helpful, what was mediocre, and what actively hurt.

---

## Tools Tested

| Tool | What It Claims | Tested? |
|------|---------------|---------|
| `codrag` | Structural overview (modules, hubs, focus areas) | ✅ |
| `codrag_search` | Semantic search with structural trace expansion | ✅ (3 queries) |
| `codrag_impact` | Dependency/dependent analysis (blast radius) | ✅ |
| `codrag_audit` | Codebase health findings | ✅ |
| `codrag_observe` | Cross-session memory | ❌ (not tested this session) |

---

## Detailed Findings

### 1. `codrag` — Structural Overview

**Verdict: 🟡 Mixed — Great concept, bad signal-to-noise ratio**

#### What's Great
- The **module summaries at the top** (lines 6–8) are genuinely excellent. The Pipeline Orchestration Engine, LLM Orchestration Engine, and Filesystem Monitoring summaries give me real understanding of what those subsystems do, what they depend on, and what their concerns are. This is the kind of context that saves an agent from making blind assumptions.
- The **architecture table** from the epistemology doc (layers, technology, purpose) is exactly the right density of information.
- The **11-stage pipeline diagram** is immediately useful for understanding the system's execution model.

#### What's Meh
- The **hub file listing** could be more useful. I get told `02_CoDRAG_Epistemology.md` is a hub with `in-degree:0`, but the *same block of content from that file is included 3 times identically* (lines 12–95, 55–95, 98–137). This is pure waste — 3× duplication of the exact same table and pipeline diagram. This alone consumed ~40% of the "useful" context budget.

#### What's Not Working
- **The module list is overwhelming and noisy.** I received a list of **602 modules**, most of which are 1-2 file modules with names like "Ui Subsystem (Docs) #23" or "Storybook CSS Injection Utilities". An AI agent reading this list of 600+ modules gets *less* understanding of the architecture, not more. It's the equivalent of dumping `find . -type d` and calling it architecture.
- **The ratio problem**: Out of 745 lines returned, roughly:
  - ~130 lines were genuinely useful (module summaries, pipeline stages, architecture table)
  - ~120 lines were duplicated content (same epistemology section 3×)  
  - ~500 lines were the exhaustive module list that no agent can meaningfully use
  
  That's an **~17% useful signal rate**. An agent is spending context window on 600 module names it will never reference.

**Recommendations:**
1. **Deduplicate hub content.** If the same chunk appears multiple times as a hub, include it once with a note about its connectivity.
2. **Tier the module list.** Show the top 10-15 modules with real dependency information. Collapse the 500+ single-file modules into a count: "... and 487 smaller modules (1-2 files each)". An agent can `codrag_search` if it needs one of those.
3. **Budget-aware assembly.** The tool knows how much context it's returning. It should prioritize novel, high-connectivity information over exhaustive listings.

---

### 2. `codrag_search` — Semantic Search

**Verdict: 🟡 Mixed — Retrieval quality varies wildly by query type**

#### Test 1: "how does the pipeline orchestrator process files"
**Result:** Got `scheduler.py` (51 lines) and `watcher.py` (full file, ~380 lines)

- **The problem:** Neither of these files is the orchestrator. The query asked about the pipeline orchestrator processing files, and I got the scheduler stub and the filesystem watcher. The actual `orchestrator.py` (which is 2,643 lines and is *the* file for this query) was not returned at all.
- **Why this might happen:** The embeddings may be matching on "pipeline" + "process" and landing on adjacent infrastructure rather than the core file. Or the orchestrator is too large to chunk well.
- **Impact:** An agent asking "how does the orchestrator work?" would get a confident-looking but wrong answer based on peripheral code.

#### Test 2: "MCP tool handler request response"
**Result:** Got `model_readiness.py` (full file, ~440 lines)

- **The problem:** I asked about MCP tool handlers and got the Ollama model readiness module. This is not even in the MCP package. The actual MCP server (`src/codrag/mcp/server.py`) was not returned despite being a 2,427-line file explicitly about MCP tool handling.
- **This is the most concerning finding.** A user asking about MCP tools should get MCP code. Period.

#### Test 3: "how does the context assembly work for MCP tool responses"
**Result:** Got `llm_client.py` (~280 lines)

- **Partial hit.** The LLM client is related to context assembly in the pipeline sense, but the query was specifically about MCP tool response context assembly (i.e., how CoDRAG assembles the context chunks into a response for the AI). The actual context assembly logic (likely in the MCP server or a context module) was missed.
- The code returned was high quality and well-documented — if it had been the right file, this would've been an A+.

#### What's Great About Search
- When it retrieves the right file, the **code quality and documentation** in the returned chunks is excellent. The `llm_client.py` result had clear docstrings, good comments, and logical structure.
- The **session-memory note** appended at the bottom of search results is a nice touch — it provides lightweight cross-session context ("Phase 66: Pi Agent Foundation built...").

#### What's Not Working
- **Semantic relevance is weak for architectural queries.** All three queries asked about specific subsystems, and all three returned tangentially related but incorrect files. The search seems to be doing keyword-ish matching rather than true structural understanding.
- **No indication of confidence or alternatives.** When the tool returns `model_readiness.py` for a query about "MCP tool handlers", there's no signal that this might not be the best match. An agent trusts the result.

**Recommendations:**
1. **File-path awareness in retrieval.** If a query mentions "MCP", boost results from `src/codrag/mcp/`. If it mentions "orchestrator", boost `orchestrator.py`. This is a simple heuristic that would fix 2/3 of the test failures.
2. **Return multiple candidates with relevance scores.** Instead of one authoritative result, return 3-5 with scores. Let the agent decide.
3. **Include a "did you mean?" signal** when the best match is weak. "No high-confidence matches found for MCP tool handlers. Closest results:..."
4. **Test with architectural/navigational queries specifically.** The current retrieval may be optimized for "find code that does X" but fails at "explain how subsystem Y works".

---

### 3. `codrag_impact` — Dependency Analysis

**Verdict: 🟢 Genuinely Useful — Best tool in the suite**

#### What's Great
- This is the tool that delivers the most actionable value. For `llm_client.py`, it returned:
  - **19 direct dependents** with relationship types (`[imports]`, `[calls]`)
  - **11 transitive dependents** 
  - Clear file paths and parent directories
- The relationship type annotations (`[imports]` vs `[calls]`) are exactly what an agent needs to understand the blast radius of a change.
- The output is **dense and noise-free**. Every line is useful. No padding, no filler.
- The distinction between direct and transitive dependents is exactly the right level of detail.

#### What's Meh
- Transitive dependents don't include relationship types. Knowing *how* `events.py` depends on `llm_client.py` transitively (through which intermediate?) would help prioritize impact assessment.
- No reverse direction shown unless you call with `direction='dependencies'` separately. A single "show me the full neighborhood" call would save a round-trip.

**Recommendations:**
1. **Add intermediate paths for transitive deps.** E.g., "events.py → (via augmenter.py) → llm_client.py"
2. **Consider a compact bidirectional mode** that shows both directions in one response for common use cases.
3. **This tool is the model for what the others should aspire to.** Dense, actionable, zero waste.

---

### 4. `codrag_audit` — Codebase Health

**Verdict: 🟡 Mixed — Good findings, generic advice**

#### What's Great
- It found real issues: `orchestrator.py` at 2,643 lines, `server.py` at 2,427 lines, `augmenter.py` at 2,136 lines. These are legitimate architectural concerns.
- Severity classification (critical/warning/info) is useful for prioritization.
- The mention of available deeper reports (ARCHITECTURE_ANALYSIS, TECH_DEBT_REPORT, etc.) is a good progressive disclosure pattern.

#### What's Meh
- The **advice is generic and sometimes wrong in context.** Every large file gets the same action: "Consider splitting into a subpackage with focused modules." This is reasonable for `orchestrator.py` but absurd for `package-lock.json` — you can't "split a lockfile into subpackages." The tool should know that auto-generated files are not actionable findings.
- 11 critical findings, and 4 of them are `package-lock.json` files. That's noise.
- No architectural findings (circular deps, coupling metrics, etc.) in the default scan. The structural analysis that CoDRAG is supposedly great at doesn't surface here.

**Recommendations:**
1. **Filter auto-generated files** (`package-lock.json`, `*.lock`, `dist/`, `build/`) from audit results by default. These inflate severity counts and waste attention.
2. **Make advice file-type-aware.** A Python god-class needs different advice than a markdown doc that's long. "Consider splitting" is only relevant for code files.
3. **Surface structural findings by default.** Circular dependencies, high coupling modules, and hub file concentration are more interesting architectural insights than "your lockfile is big."

---

## Cross-Cutting Issues

### Issue 1: Context Budget Misallocation
The biggest systemic problem is that CoDRAG spends tokens on low-value content while missing high-value content. The `codrag` overview spends 500 lines on an exhaustive module list but doesn't include the actual hub file code. The search tool returns full files (~400 lines each) even when only a few functions are relevant.

**Fix:** Implement aggressive LOD (Level of Detail) compression. Return signatures + docstrings for large files, full code only for small/focused files.

### Issue 2: Duplicate Content
The same epistemology section was returned 3 times in a single `codrag` call. This is a 3× waste of tokens for zero additional information.

**Fix:** Deduplicate at the chunk level before assembly. Hash chunks and skip duplicates.

### Issue 3: Retrieval Misses on "Home Base" Queries
When someone asks about the MCP server, they should get MCP server code. When someone asks about the orchestrator, they should get orchestrator code. The search tool failed on both of these obvious cases. This suggests the embedding space doesn't weight file names and paths strongly enough.

**Fix:** Blend semantic search with structural priors. Boost files whose path/name matches query keywords. This is a well-known technique in code search (hybrid search).

### Issue 4: No Self-Awareness of Quality
When search returns a weakly-related result, there's no indication. The tool presents everything with equal confidence. An agent can't distinguish "this is exactly what you asked for" from "this was the closest thing I could find."

**Fix:** Include a simple relevance score or confidence indicator with search results.

---

## Summary Scorecard

| Tool | Signal Quality | Noise Level | Actionability | Overall |
|------|---------------|-------------|---------------|---------|
| `codrag` | 🟢 High (top modules) | 🔴 Very High (600 modules) | 🟡 Medium | **C+** |
| `codrag_search` | 🔴 Low (wrong files) | 🟡 Medium (full files) | 🔴 Low | **D+** |
| `codrag_impact` | 🟢 High | 🟢 Low | 🟢 High | **A-** |
| `codrag_audit` | 🟡 Medium | 🟡 Medium (lockfiles) | 🟡 Medium | **B-** |

### Priority Actions (Highest Impact → Lowest)

1. **Fix search retrieval quality** — this is the core value proposition and it's currently unreliable
2. **Deduplicate and tier the `codrag` overview** — the 600-module dump is counterproductive
3. **Filter noise from audit** — lockfiles, generated files shouldn't be "critical" findings
4. **Add confidence/relevance scores to search results**
5. **Preserve and protect `codrag_impact`** — it's already excellent, don't break it

---

## Methodology Notes

All evaluations were done in a single session on 2026-04-04 against the CoDRAG codebase itself (self-referential analysis). The test queries were chosen to represent common AI agent usage patterns:
- "How does X work?" (architectural understanding)
- "What calls Y?" (impact analysis)
- "What's wrong?" (health assessment)
- "Find code related to Z" (code navigation)

Results may vary with different codebases, embedding models, or pipeline stages completed. This assessment should be repeated after improvements are made.
