# Goalposts: Architecture & Pipeline Design

## 1. The Planning Pipeline (`GoalpostsPlanner`)

The existing CoDRAG pipeline builds an epistemology of the codebase through `EpistemicEnrichment` (building up layer by layer from file leaves) and clustering. The **Goalposts Pipeline** will sit on top of this established knowledge base.

### 1.1 Trigger Mechanisms
- **Post-Enrichment Auto-Run:** Automatically queued after a full codebase enrichment finishes (if the Goalposts feature is enabled in project settings).
- **Idle Background Task:** The `MultiProjectCoordinator` (`scheduler.py`) runs this low-priority task in the background when no active enrichments are pending.
- **On-Demand (Queued First):** Triggered manually by the user via the Dashboard if they want a refreshed plan immediately.

### 1.2 Input Context Assembly
Because a codebase's epistemic context is massive, the `GoalpostsPlanner` needs a compressed representation:
1. **Product Vision / User Intent:** Ingests any custom instructions or "product goals" the user has set for the project.
2. **Epistemic Overview:** Uses the existing deep analysis artifacts (e.g., aggregated domain tags, top-level architecture layer summaries, and tech debt from `trace_epistemic.jsonl`).
3. **Current State:** Reads the current list of resolved and pending tasks to understand "what is done."

### 1.3 The LLM Forward-Looking Pass
A hyper-specific LLM routine designed to act as a *Staff Engineer & Product Manager*. 
- **Prompt Focus:** "Given this codebase's architecture and completeness, and the user's product goals, what are the next logical sprints to achieve the vision?"
- **Output Schema:** Expects a structured JSON response containing:
  - `sprints`: List of proposed sprints (e.g., "Refactor Auth Interface", "Implement Webhook Receivers").
  - `tasks`: Specific, actionable steps within each sprint.
  - `research_phases`: Questions or unknowns the user needs to answer before a sprint can begin.
  - `audits`: Suggested architecture or security reviews.

## 2. Data Storage
Sprints and planning data will be stored persistently, distinct from the transient trace cache.
- **`goalposts.json` / Database Table:** Stores proposed, approved, rejected, and completed sprints for a specific Project ID.
- **State Machine:** Sprints transition between states (`PROPOSED` -> `APPROVED` -> `ACTIVE` -> `COMPLETED`, or `PROPOSED` -> `REJECTED`).

## 3. Worker Integration
- Will be registered as a new stage in the `PipelineOrchestrator` (e.g., `StageId.GOALPOSTS`).
- Handled via `headless_runner.py` to ensure it can run concurrently or in the background without blocking the main UI loops.
