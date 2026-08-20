# Research Questions: Global LLM Pause

This document contains open questions and research directives for the AI agent assigned to implement the Global LLM Pause feature.

## 1. State Machine Integration
- **Current Behavior:** How does the existing "pause" feature work at the pipeline orchestrator level? (See `Phase145_Pipeline-UI-Reliability/README.md`)
- **Impact of Halting:** If we halt all LLM compute mid-pipeline, what happens to the `.reset_barrier` and in-flight jobs? Do they timeout, or can they be cleanly suspended?
- **Resumption:** When the user unpauses (e.g., after their Ollama limits reset), what is the exact transition path for jobs that were suspended? Do they restart from scratch, or resume from the last known state?

## 2. Component Isolation
- **Scheduler vs. Worker:** Should the pause be implemented at the scheduler level (preventing jobs from being dispatched to workers) or at the LLM client level (rejecting outbound requests)? Rejecting at the client level might cause stages to register as "failed" rather than "paused". 
- **Queue Behavior:** If the global pause is active, should the file watcher still detect changes and enqueue jobs, just leaving them in a `Pending` state until unpaused?

## 3. Daemon and MCP Continuity
- **MCP Availability:** Ensure that read-only MCP queries (`prep`, `prep_search`, `prep_audit`, etc.) do not route through the LLM execution pathways that will be paused.
- **Heartbeat:** Does the daemon require periodic LLM health checks that would fail if we globally pause LLM calls? 

## 4. UI/UX
- **User Feedback:** Where should the "Global Pause" indicator live on the dashboard? 
- **Actionability:** How do we communicate to the user *why* the pipeline is paused (e.g., "Paused due to LLM limits exhausted" vs "User initiated pause")?
