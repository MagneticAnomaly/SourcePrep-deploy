# Phase 67 Technical Specification: Pipeline Resiliency & Agent Context Auto-Population

## Overview
Phase 67 addresses two critical system integrity problems and introduces one landmark UX feature:
1. **Pipeline Stabilization (Phantom Loops):** Correcting a severe divergence between `compute_trace_coverage` and `TraceBuilder` where `.gitignore`-excluded files trigger infinite rebuilding loops.
2. **Sub-Atlas Continuity:** Ensuring role-specific knowledge generation (`Sub-Atlas` / `Phase 64`) correctly resumes if the CoDRAG server crashes or is restarted.
3. **Agent Scope Auto-Population:** A one-click intelligent action that leverages semantic deep search and our highest-tier Thinking LLM to perfectly map out the necessary file scope for any Paperclip/MCP agent role.

---

## 1. Pipeline Stabilization: Phantom Files Loop

### 1.1 The Problem
When the background system goes idle, `codrag.core.trace.watcher` fires a health check via `compute_trace_coverage()`. This function parses the filesystem using basic string globs. However, `codrag.core.trace.builder.TraceBuilder` parses the filesystem using robust `pathspec` logic on `.gitignore`. 
Because the coverage engine ignores `.gitignore`, it counts standard cache folders (`.venv`, `node_modules`, `build/`) as valid, "untraced" Python/JS files. It demands an immediate orchestrator rebuild. The orchestrator triggers the builder, the builder correctly ignores the files, finishes, and the cycle repeats infinitely.

### 1.2 Implementation: Synchronize `pathspec` Engine
**File to Modify:** `src/codrag/core/trace/coverage.py`
**Method:** `compute_trace_coverage(...)`

**Code Steps:**
1. **Load Gitignore Configuration:**
   Inject `gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)` exactly as the trace builder does.
2. **Evaluate at `os.walk` iteration:**
   Inside the main loop, before checking `base` strings against default patterns, stringify the path to relative POSIX.
3. **Short-circuit Skip:**
   Execute `gitignore_spec.match_file(rel_path)`. If it matches, immediately `continue` loop execution.
   
*Verification:* Starting CoDRAG with `codrag-daemon` inside a NextJS or deeply-virtual-enved Python project must result in `coverage_gap.untraced = 0`. Graph Scope UI must show "All files traced."

---

## 2. Pipeline Resume State: Sub-Atlas Constraints

### 2.1 The Problem
When `run_deep_enrichment` fails mid-flight, the orchestrator tries to pick up where it left off.
`_detect_resume_point` iterates the 11 pipeline stages. When it checks `StageId.ATLAS`, it checks if `atlas_manifest.json` exists. If it does, it assumes the entire stage finished perfectly.
However, Phase 64 introduced synchronous processing inside the Atlas Worker that generates `.prep/atlas_role_*.md` files and `atlas_segments_manifest.json`. If the pipeline halts *between* the main atlas and the segment/role atlases, the resume logic completely abandons the Sub-Atlases.

### 2.2 Implementation: Enforce Dependent Manifests
**File to Modify:** `src/codrag/services/pipeline/orchestrator.py`
**Method:** `_detect_resume_point(...)`

**Code Steps:**
1. Override the generic loop checking `if manifest_file: mpath.exists()`.
2. Add a sub-branch specifically tracking `StageId.ATLAS`:
   ```python
   elif stage == StageId.ATLAS:
       segments_path = idx_dir / "atlas_segments_manifest.json"
       if not segments_path.exists() or segments_path.stat().st_size == 0:
           stage_decisions.append({
               "stage": stage.value,
               "decision": "INCOMPLETE",
               "reason": "Main atlas exists but sub-atlas segments are missing."
           })
           return i
   ```
3. Update `src/codrag/services/pipeline/workers.py` inside `_atlas_worker()` to emit `pfl.log("atlas", f"Role atlases cached...")` for transparent telemetric confirmation of rebuilds.

---

## 3. Capstone Feature: Agent Scope Auto-Population (Deep Search Vetting)

The Agent UI allows you to scope context, preventing Agent Hallucination. Manually picking hundreds of files for a "Lead Security Auditor" agent is slow. We will automate this using our multi-stage LLM context pipeline.

### 3.1 Backend API Contract
**Target Router:** `src/codrag/api/routers/scope.py`
**New Endpoint:** `POST /projects/{project_id}/scope/agents/{agent_role}/auto-populate`

**Workflow Steps:**
1. **Determine Role Profile:** Read `AGENTS.md` or `.prep/project.json` to get the defined instructions and overarching goal of the `{agent_role}` (e.g. `Backend Architect`).
2. **Broad Topological Net:** 
   * Option A (Semantic Index): Vector query `embedding_store` using the Role's directives string to pull the Top ~100 structural files.
   * Option B (Structural Filter): Alternatively, apply logic to read all Python/Rust files if the role dictates Backend.
3. **The 'Thinking' Bottleneck (Vetting LLM):**
   * Instantiate the user's selected standard or Thinking model wrapper.
   * Pass the 100 candidate files as `(filepath, description / docstring summary)` pairs.
   * **Prompt Structure:**
     * *System:* "You are an orchestration AI configuring a minimal, highest-density context workspace for an AI coworker."
     * *Directives:* Provide the Target Agent's Role instructions.
     * *Goal:* Output a JSON list (`{ "selected_files": [...] }`) containing STRICTLY the filepaths critical to that persona's success. Explicitly ignore tangental assets.
4. **Resolution:** Extract the JSON list. Respond immediately to the frontend:
   ```json
   {
      "auto_populated": true,
      "recommended_paths": ["src/server/auth.py", "scripts/deploy.py"],
      "model_latency_ms": 4200
   }
   ```

### 3.2 Frontend UI Automation
**Target File:** `packages/ui/src/components/agent/AgentKnowledgeTree.tsx`

**UI Modalities:**
1. **The Call-to-Action:** Introduce a clear "Auto-Populate ✨" button above the `FolderTree` search bar.
2. **Transition State:** When clicked, replace the Tree view with an animated "Thinking" state. Present a text readout describing the backend process:
   > "Extracting role vectors... Vetting candidates with Thinking LLM... Finalizing scope..."
3. **Payload Merging:**
   * Received `recommended_paths`.
   * Clear the previous `includedPaths` array state (or present a modal asking "Merge or Overwrite?").
   * Inject the `recommended_paths` tightly into the component state. The `FolderTree` component natively reacts by turning the checkboxes "blue".
4. **Persistence (Save on Vetted):** 
   Since the graph explicitly determined these, immediately call `CodragApi.updateScope(...)` to persist the tree so the user doesn't have to manually click "Save" after an auto-populate action (unless user-override conventions prefer manual saving).
