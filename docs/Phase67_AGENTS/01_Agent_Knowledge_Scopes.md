# Phase 67: Agent Knowledge Scopes

## Objective
Replace static file hardcoding (`KNOWLEDGE.md`) with an interactive, per-agent **Knowledge Scope** UI in the CoDRAG Dashboard, backed by a robust filtering engine on the backend vector store.

## The Problem
Currently, the CoDRAG dashboard supports a single, global **Knowledge Sources** selection tree. This builds the semantic RAG index used by MCP agents and search tools. 
If a project includes backend specs, frontend stylesheets, and marketing docs into the global knowledge pool, an agent tasked strictly with UI design will be overwhelmed by irrelevant semantic search hits from the backend docs.

The natural instinct is to give every agent a completely isolated vector index, but this creates significant compute redundancy. If 5 agents need `README.md`, embedding it 5 separate times is slow and expensive.

## The Solution: UI-Siloed, Backend-Pooled Scopes
We will give the user the *experience* of having completely siloed index trees per agent, while sharing compute efficiently on the backend.

### 1. The Per-Agent UI
The Dashboard receives a new interactive panel: `<AgentScopePanel />`.
- It behaves identically to the current Global Knowledge Sources panel.
- It includes a Role Selector dropdown (e.g. `CEO`, `CTO`, `UX Designer`).
- When a user changes the role, the checkboxes reflect that specific agent's scope. 

### 2. Backend Pooling
When users select files across different agents, the Python backend merges all selected paths into a single `set()`. 
The `KnowledgeIndex` only embeds the deduplicated union of these files into a **unified global embedding matrix**. We only pay to embed a file once.

### 3. Execution Masking (The Magic)
When a Paperclip agent executes an MCP tool to gather context:
- The tool receives the `role` argument natively (e.g. `codrag_search("button styles", role="ux-designer")`).
- The Python API fetches the explicitly checked file paths for the `ux-designer` role.
- CoDRAG securely **filters out** any semantic search hits that fall outside of that specific agent's tree, guaranteeing the agent never hallucinates off irrelevant context.

## Default Behavior
If an agent executes a tool and they *do not* have a distinct Knowledge Scope configured in the dashboard, the system safely falls back to the legacy behavior: searching across the Global Knowledge tree.
