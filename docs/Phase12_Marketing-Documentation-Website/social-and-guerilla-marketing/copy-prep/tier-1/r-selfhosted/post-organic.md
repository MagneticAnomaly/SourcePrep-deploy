# Organic/Personal Post Draft for r/selfhosted

## Title Options
1. **I built a self-hosted "Context Engine" because I refuse to upload my code to the cloud**
2. **Prep: A local-first, offline-capable code indexer (Rust/Tauri)**

## Body Structure

### The Problem
I love tools like Sourcegraph or Cursor, but I work on projects where I simply *cannot* upload the source code to a third-party server.

I looked for a self-hosted alternative that didn't require spinning up a 16GB Docker container or managing an Elasticsearch cluster. I just wanted a desktop app.

### The Solution
I built **Prep**. It's a single binary (well, an .app/.exe) that runs on my laptop.
*   **Index:** Stored in a local SQLite file.
*   **Search:** Runs on CPU (Rust).
*   **LLM:** Connects to my local Ollama instance (or an API if I choose).

### Why I'm sharing
I figured this community would appreciate the "sovereign" aspect. You own the index. You own the keys. The code never leaves `localhost`.

### Tech Stack
*   Tauri (frontend)
*   Rust (graph engine)
*   Python (optional sidecar for advanced ML)

**Repo:** [Link]

## Tone
Privacy-focused, DIY, "sovereign computing" vibe.
