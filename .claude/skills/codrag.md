---
description: Get structural codebase context from CoDRAG
tools:
  - mcp__codrag__codrag
  - mcp__codrag__codrag_search
  - mcp__codrag__codrag_impact
---

Call `codrag` to get the structural overview of this codebase -- modules,
hub files, and knowledge base content. Use the structural context to
inform your approach before reading or editing files.

If the user asked a specific question, also call `codrag_search` with
their question to find relevant code with structural trace expansion.

Before making changes, call `codrag_impact` on the target file to
understand what depends on it.
