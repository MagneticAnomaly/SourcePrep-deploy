# Phase 67: Agent Optimization & Knowledge Scopes

This phase is dedicated to upgrading CoDRAG to deeply natively orchestrate and manage Papersclip AI Agents by providing Agent-specific file scopes and reducing friction from static Markdown manual management.

## Architecture Guidelines
- **No duplicated embeddings:** Use a union of file paths for the global Vector DB to save compute and avoid race conditions.
- **Strict runtime filtering:** Agents retrieve information strictly constrained by their specialized file scope selection.
- **Seamless UI integration:** Combine the robustness of the existing `FolderTree` React component with per-agent state.
