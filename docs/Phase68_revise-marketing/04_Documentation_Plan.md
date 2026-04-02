# Public Documentation Revisions & Plan

## Overview
Updating the public-facing documentation to properly onboard users into the new Agent orchestration ecosystem. The docs must split into two distinct paths: **Human Users** (classic Codrag features) and **Agent Integrations** (new features).

## 1. Restructuring the Docs Sidebar
*   **Getting Started**
    *   Installation
    *   Configuring Projects
*   **Core Concepts (Human-in-the-loop)**
    *   Global Graph Search
    *   Trace Coverage
*   **[NEW] Agentic Integration System**
    *   What are Agent Scopes?
    *   Auto-Populating Agent Knowledge
    *   Orchestration Adapters Hub
*   **[NEW] Adapter Guides**
    *   Using CoDRAG with CrewAI
    *   Using CoDRAG with LangGraph
    *   Using CoDRAG with Paperclip (Native)
*   **Advanced Configuration**
    *   The `.codrag` folder structure
    *   Using the Rust Projection Engine locally

## 2. Drafting the "What are Agent Scopes?" Guide
*   **Core Message:** Explain the difference between global knowledge (what CoDRAG computes) and Agent Scopes (what an agent is allowed to retrieve). 
*   **Code Example:** Show a side-by-side of an MCP Tool call with and without the `role="<role>"` argument.
*   **Performance Note:** Explicitly call out that CoDRAG only embeds the files once on the backend, ensuring users know that 50 agents won't accidentally incur 50x the embedding compute cost.

## 3. Drafting the "Auto-Populating Agent Knowledge" Guide
*   **UI Walkthrough:** Step-by-step instructions on navigating to the Agent Scope Panel, selecting the Agent Role, and clicking the ✨ Auto-Populate feature.
*   **How it Works (Under the Hood):** Explain how we combine generic topological netting with a prompt-vetted Thinking LLM pass to perfectly map files to the role's instructions (e.g. from `AGENTS.md`).

## 4. Drafting the "Adapters Hub" Guides
Each adapter guide needs:
1.  Installation command (`pip install codrag-crewai`, etc.).
2.  A 10-line minimal "Hello World" Python script demonstrating how to inject the CoDRAG read-only search/impact tools into the respective framework's agent object.
3.  Best practices on setting the proper `role` string on the agent so context passes through properly.

## Next Steps for Technical Writers
*   Verify the CrewAI / LangGraph adapter code snippets against the `Phase 67/68` codebase implementations.
*   Record screen-capture GIFs of the Auto-Populate ✨ UI behavior for embedding in the markdown docs.
