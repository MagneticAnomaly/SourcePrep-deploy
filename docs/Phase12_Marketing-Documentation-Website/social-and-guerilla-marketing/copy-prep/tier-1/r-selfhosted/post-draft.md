# Post Draft for r/selfhosted

## Title Options
1. **I built a self-hosted "code context engine" so I don't have to upload my repo to the cloud**
2. **CoDRAG: A local-first alternative to cloud-based AI code indexing**
3. **Run your own MCP server locally for code search (No telemetry, no cloud)**

## Body Structure

### Hook
I wanted the "magic" of AI code search (like Cursor or Sourcegraph) but I **didn't** want to upload my proprietary code to a SaaS or pay a subscription just to search my own files.

### The Project: CoDRAG
It's a desktop app (Mac/Windows) that runs entirely on your machine.
*   **No Cloud:** The index is stored as a SQLite DB and some flat files on your SSD.
*   **No Telemetry:** It doesn't phone home with your code.
*   **Bring Your Own Key:** If you use the optional re-ranking or AI features, you use your own local LLM (Ollama) or your own API key directly. No middleman.

### How it fits in a Self-Hosted Lab
It runs as a daemon. You can point it at your `~/projects` folder, let it index, and then connect it to any editor that supports MCP (Model Context Protocol). It's basically "`grep` on steroids" that understands code structure.

### Tech Stack
*   **Backend:** Python + Rust (for the heavy graph analysis)
*   **Frontend:** Tauri (lightweight, not a full Electron hog)
*   **Storage:** Local filesystem + SQLite

### Links
*   **GitHub/Source:** [Link]
*   **Docs:** [Link]

Let me know if you have questions about the local indexing performance!

## Tone
Privacy-first, DIY, technical. Emphasize "ownership" and "control."

## Timing
Weekend or Weekday evening.

## Links to Include
- **Primary:** GitHub Repo (this audience loves checking the code).
- **Secondary:** Docs.
