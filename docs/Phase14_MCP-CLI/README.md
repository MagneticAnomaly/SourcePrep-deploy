# Phase 14: MCP-CLI (Pure CLI Mode)

## Overview
This phase focuses on shipping a lightweight, standalone version of Prep that functions purely as a **CLI tool** and **MCP Server**, without requiring a persistent background daemon or GUI.

## Goal
To provide the "best plumbing" for IDEs (Windsurf, Cursor) by allowing developers to simply run `npx prep` (or `pip install prep`) and instantly get:
1.  **Semantic Search** over their codebase.
2.  **Context Assembly** for their LLM.
3.  **Trace Analysis** (GraphRAG) for deep dependencies.

## What Ships (Phase 14)
- **Direct MCP mode (no daemon):** `prep mcp --mode direct`
- **MCP config generator:** `prep mcp-config --mode direct --ide cursor`
- **Default repo root:** current working directory (CWD)
- **Default index dir:** `<repo_root>/.runprep/index`
- **Repo policy persistence:** `<index_dir>/repo_policy.json` (auto-generated via `ensure_repo_policy`)

## Dashboard Integration
The dashboard includes an **IDE Integration (MCP)** panel that:
- Calls `GET /api/code-index/mcp-config`
- Lets the user select IDE + MCP mode (`direct | auto | project`)
- Provides a **copy-to-clipboard** JSON config block for IDE setup

## Requirements
- **Ollama** is still required for embeddings (default `http://localhost:11434`, model `nomic-embed-text`).
- Direct MCP does **not** require the Prep daemon (`prep serve`).

## Key Constraints
- **Single Repo Focus**: Optimized for "I am working on *this* project right now."
- **No repo-count gating**: Direct mode operates on the current working directory; "Free = 1 repo" applies to the multi-project daemon registry.
- **License enforcement (Direct mode)**: Direct mode can remain a "Community/Local" path with no mandatory license checks; recommended gating is feature-based (e.g., trace) rather than repo-count.
- **Zero Friction**: No "Start the server", "Open the dashboard", "Create a project". It should just work in the current directory.
- **Direct Integration**: The MCP server should run the logic *in-process* (or manage its own subprocess) rather than relying on a separate user-managed daemon.

## Analytics / measurement posture

- Prep MUST work without analytics.
- If analytics are enabled (opt-in), Direct mode should emit only aggregated counters (no file contents, no raw queries, no absolute paths).
- Distribution signals (pip/homebrew downloads) are directional only and should not be treated as user counts.

## The "Heavy GUI" Solution
By stripping away the Tauri app and the multi-project daemon requirement, we solve the "Heavy GUI" friction. The app becomes invisible infrastructure—true "plumbing."
