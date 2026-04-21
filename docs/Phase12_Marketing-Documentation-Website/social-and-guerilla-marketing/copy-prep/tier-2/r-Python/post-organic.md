# Organic/Personal Post Draft for r/Python

## Title Options
1. **I built a desktop app using Python (FastAPI) + Rust (PyO3) + Tauri**
2. **Using Python for the "Brain" (MCP) and Rust for the "Brawn" (Graph)**

## Body Structure

### The Architecture
I wanted to share the stack for my new desktop app, **Prep**.
It's a local code search engine.

*   **Frontend:** Tauri (JS/React) - Keeps the bundle small.
*   **Backend Core:** Rust — file watching and Tree-sitter parsing, exposed to Python via `PyO3` + `maturin`.
*   **Backend Logic:** Python - Handles the MCP server, API endpoints, and Pydantic models.

### Why Python?
Everyone says "Rewrite it all in Rust," but Python's ecosystem for AI/LLM integration (and the MCP SDK) is just too good to ignore. Using PyO3 gave me the performance-critical path in Rust while keeping the business logic flexible in Python. `maturin` makes building the wheel genuinely pleasant.

**Repo:** [Link]

## Tone
Architecture sharing. "Here's how I glued these things together."
