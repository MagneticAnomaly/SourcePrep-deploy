# Phase 148 — Global LLM Pause

**Status:** Open (Research Phase)
**Goal:** Design a mechanism to universally pause all LLM calls while keeping the daemon and MCP session alive. 

## The Problem
Currently, users can toggle individual repositories on or off. However, this action shuts down the active MCP for that repository entirely and stops the pipeline. 

There is a critical missing feature: the ability to keep the active session (and MCP) alive, but globally pause all new pipeline runs or LLM invocations. 

**Use Case Example:** 
If a user exhausts their cloud LLM limits (e.g., Ollama cloud node), the SourcePrep app continues to attempt LLM calls, resulting in repeated failures and error logs. The user needs a clean "pause" button that halts all LLM activity globally, preventing further errors, but keeps the daemon and MCP up so they can continue working with read-only tools and existing structural context.

## Architectural Considerations
Implementing a global LLM pause is conceptually simple ("stop making network requests to LLMs"), but architecturally complex due to the existing state machine:
1. **Existing Pause Semantics:** There is existing pause functionality in the pipeline that is already problematic (as documented in Phase 145 pipeline UI reliability issues). 
2. **State Machine Drift:** The state machine orchestrating pipeline runs and the UI rendering state often drift (e.g., failed finalize steps leaving barriers stuck). A hard global pause might leave in-flight jobs in a zombie state or fail to cleanly resume when unpaused.
3. **Queue vs Execution:** We must decide whether a "paused" state prevents jobs from entering the queue, or allows them to queue but halts execution at the scheduler level.
4. **Daemon Lifecyle:** The daemon must continue serving MCP requests for read-only lookups (`prep`, `prep_search`, etc.) while blocking mutation/enrichment requests that rely on LLM compute.

## Next Steps for Future AI Agent
This folder serves as the starting point for researching and designing the Global LLM Pause feature. The next agent should:
1. Review the state machine architecture (referencing `docs/Phase145_Pipeline-UI-Reliability/README.md` and related state stores).
2. Propose a clean way to intercept and block LLM invocations at the orchestrator/scheduler level without corrupting the pipeline state.
3. Design the UI mechanism to display the global paused state.
4. Author a `PROPOSAL_global-llm-pause.md` detailing the required state machine updates and code changes.
