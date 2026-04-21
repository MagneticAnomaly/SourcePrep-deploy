# Post Draft for r/devops

## Title Options
1. **Local-first "Context Engine" for air-gapped dev environments (No cloud dependency)**
2. **I built a self-hosted alternative to GitHub Copilot's indexing layer**
3. **Tool sharing: Prep - A structural code indexer that runs locally (Rust + Tauri)**

## Body Structure

### Hook
We're seeing more demand for "AI coding tools" in our org, but the security team shuts down anything that uploads code to a SaaS vector DB.

### The Project
I built **Prep**, a desktop daemon that indexes code locally. It's designed to run on the developer's laptop, building a dependency graph of the codebase without touching the network.

### Why for DevOps/Platform?
*   **Security:** Index stays on localhost.
*   **Compliance:** No third-party data processing of your IP.
*   **Integration:** It exposes an MCP (Model Context Protocol) server, so you can point secure/local LLM clients at it.

### Tech Stack
*   Rust (Tree-sitter) for parsing.
*   Python/FastAPI for the API layer.
*   Tauri for the UI.

### Links
*   **Repo:** [Link]

## Tone
Professional, security-conscious. "Here is a tool that solves a compliance headache."

## Timing
Weekday.
