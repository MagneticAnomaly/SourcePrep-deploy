# Phase 80: MemPalace Integration — Research Strategy

> Date: 2026-04-07
> Status: Planning / Exploratory
> Goal: Define a rigorous methodology for evaluating MemPalace's architectural concepts (AAAK dialect, Agent Diaries, Temporal Graph) to determine where and if they should be integrated into the CoDRAG ecosystem.

## 1. Background & Hypothesis

Our initial investigation of the [MemPalace](https://github.com/milla-jovovich/mempalace) repository revealed that while its core engine (a conversation-centric ChromaDB knowledge base) shouldn't replace CoDRAG's codebase-anchored architecture, several of its data models and memory abstractions are highly compelling.

The hypothesis is that we can adapt specific MemPalace patterns to solve CoDRAG's emerging challenges:
1. **Token Constraint in Swarms:** The "AAAK" dialect offers a symbolic shorthand that could drastically reduce token costs when passing state between workers and coordinators during Phase 79 Swarm execution.
2. **Global Context Pollution:** Agent-specific "Diaries" could silo knowledge to specialized roles (e.g., HR, Architect) without cluttering the global `observation_store`.
3. **Temporal Drift:** A temporal Knowledge Graph (valid_from/valid_to) could manage concept staleness better than binary Boolean flags.

**Before implementation, we must deeply examine the codebase to identify integration points and explicitly weigh the pros and cons.**

---

## 2. Research Focus Areas

This research will be divided into three core evaluation tracks. For each track, we will analyze specific files, list potential pros/cons, and determine the technical feasibility.

### Track A: The AAAK Compression Dialect

**Objective:** Evaluate modifying CoDRAG's context assembly pipelines to encode variables, files, and module relationships into AAAK-like symbolic abbreviations.

**Codebase Areas to Examine:**
- `src/codrag/core/compression/lod_extractor.py` and `compressor.py`: Can we inject an AAAK conversion pass?
- `src/codrag/core/swarm_orchestrator.py` & `src/codrag/services/pipeline/stages.py`: How does state move between workers and the coordinator? Do we compress outputs?
- `src/codrag/api/routers/projects/search.py`: How are context payloads assembled, and can the prompt adapt to read AAAK dialect?

**Evaluation Mapping:**
- **Pros:** Potential 40-60% token reduction in cross-agent communication. Faster processing times.
- **Cons:** Added latency from compression/decompression. Potential for critical logic loss if an abbreviation is misunderstood by the LLM. Loss of human-readability in debugging trails.

### Track B: Specialist Agent Diaries & The 4-Layer Memory Stack

**Objective:** Evaluate separating global structural observations from role-scoped "diaries" (MemPalace layers 1 & 2) for our Paperclip-managed agents.

**Codebase Areas to Examine:**
- `src/codrag/services/observation_store.py`: Examining the current `visibility` and `created_by` access patterns. Are they rigorous enough for true isolation?
- `src/codrag/agents/core.py`: Reviewing `AgentCore` facade to see how `save_observation` is currently utilized by role logic.
- `src/codrag/mcp/server.py`: Can we safely expose `codrag_diary_read` and `codrag_diary_write` MCP tools without breaking existing patterns?

**Evaluation Mapping:**
- **Pros:** Prevents overarching atlas and graph inflation. Agents maintain continuity ("I remember trying this refactoring pattern yesterday"). 
- **Cons:** Risk of dual sources of truth (diary vs observation). Schema bloat. Complexity in cross-agent knowledge sharing.

### Track C: Temporal Knowledge Graph & Staleness

**Objective:** Evaluate upgrading our `ConceptStore` and `ObservationStore` to track temporal validity (`valid_from`, `valid_to`) rather than simply using a `stale = 1` boolean triggered by file edits.

**Codebase Areas to Examine:**
- `src/codrag/services/concept_store.py`: How is the `status` (seed, active, archived) and `stale` flag managed today?
- `src/codrag/core/watcher.py` & `src/codrag/services/scope_orchestrator.py`: How do code changes currently invalidate stored knowledge?

**Evaluation Mapping:**
- **Pros:** Perfect historical recall (e.g., "Why did we make this change in 2024?"). Better handling of architectural drift.
- **Cons:** Database migration risks. Increased storage volume. Complex invalidation logic (when does a concept truly "end"?).

---

## 3. Methodology & Next Steps

We will proceed with the following steps. **Do not modify source code during this phase.**

1. **Deep Code Tracing:** Step through the targeted files defined in the Tracks above. For each track, create an explicit impact map assessing the current code vs. integration.
2. **LLM Validation Tests (AAAK):** Formulate rapid test prompts with AAAK compression against target swarm models (e.g. Haiku) to verify they can reliably parse the compressed symbols without explicit pre-training.
3. **Database Schema Review:** Draw out the exact SQLite changes needed for Diaries and Temporal graphs.
4. **Final Decision Matrix:** Compile the findings into a report (`02_MemPalace_Integration_Findings.md`) that ranks each feature by ROI (Token/Quality Gain vs Implementation Complexity).
