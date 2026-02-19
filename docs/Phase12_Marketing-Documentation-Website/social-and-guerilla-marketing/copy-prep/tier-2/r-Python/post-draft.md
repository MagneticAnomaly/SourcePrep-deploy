# Post Draft for r/Python

## Title Options
1. **I built a local AI context engine using Python + Rust (PyO3) + Tauri**
2. **Using Python for the "Brains" and Rust for the "Brawn" in a local desktop app**
3. **Showcase: CoDRAG - A Python-powered MCP server for local code search**

## Body Structure

### Hook
I wanted to build a desktop app that does complex code analysis (graph-based RAG) but also runs local ML models.

### The Architecture
*   **Python:** Handles the MCP server logic, API endpoints, and optional local LLM integration (because the ML ecosystem is here).
*   **Rust:** Handles the file watching and Tree-sitter parsing, exposed to Python via `PyO3` bindings (compiled with `maturin`).
*   **Tauri:** The UI.

### Why Python still matters for local tools
Even with Rust being fast, Python is unbeatable for the "glue" logic and ML interoperability. We use `pydantic` heavily for schema validation and `FastAPI` for the local API layer — the Python side stays clean while the Rust extension handles the raw parsing.

### The Tool
CoDRAG is the result—a local context engine you can plug into Cursor/Windsurf.

### Links
*   **GitHub:** [Link]
*   **Tech Stack Details:** [Link]

## Tone
"Pythonista building cool stuff." Highlight libraries used (Pydantic, FastAPI, etc.).

## Timing
Check r/Python rules—might need to be in "Showcase Sunday" or similar threads.
