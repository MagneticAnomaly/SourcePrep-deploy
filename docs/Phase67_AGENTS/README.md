# Phase 67: Autonomous Agent Architecture & Paperclip Integration

This phase delivers CoDRAG's three autonomous agent personas (Staffing, Researcher, Custodian) and the **Hybrid MCP + Lightweight Plugin** integration with [Paperclip](https://paperclip.ing).

## Integration Architecture

CoDRAG integrates with Paperclip through two layers:

- **Pull (MCP Server)**: Paperclip agents connect to CoDRAG's MCP endpoint to access 5 core intelligence tools (`codrag`, `codrag_search`, `codrag_impact`, `codrag_audit`, `codrag_observe`). This is the primary integration — no plugin SDK required.
- **Push (Python REST)**: CoDRAG's agent engines proactively push health findings, research plans, and agent profiles to Paperclip via REST API. System agents appear in Paperclip as paused "dummy profiles" that author tickets without Paperclip executing them.

**Definitive architecture doc**: [Paperclip-Plugin/02_Hybrid_MCP_Architecture.md](./Paperclip-Plugin/02_Hybrid_MCP_Architecture.md)

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| [Paperclip-Plugin/](./Paperclip-Plugin/) | Integration architecture (02_Hybrid_MCP_Architecture.md is the source of truth) |
| [Researcher-concept-adapter/](./Researcher-concept-adapter/) | Researcher Agent design: engines, LangGraph/CrewAI adapters, implementation plans |
| [HR-concept-adapter/](./HR-concept-adapter/) | Staffing Agent design: landscape research, architecture, integration (Docs 01–07) |

## Architecture Guidelines

- **Headless intelligence**: CoDRAG provides answers via MCP and pushes data via REST. No UI injection into Paperclip.
- **Paused dummy profiles**: System agents appear in Paperclip org charts as paused employees authored by CoDRAG.
- **No duplicated embeddings**: Agents use a union of file paths against the global Vector DB.
- **Strict runtime filtering**: Agent queries are scoped by their `role` parameter via MCP.
