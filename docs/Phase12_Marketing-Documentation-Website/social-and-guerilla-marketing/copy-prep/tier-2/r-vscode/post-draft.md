# Post Draft for r/vscode

## Title Options
1. **I built a local tool to give VS Code AI extensions better context (via MCP)**
2. **Don't switch editors: CoDRAG adds structural code search to VS Code**
3. **Fixing Copilot's "hallucinated imports" with a local graph indexer**

## Body Structure

### Hook
I see a lot of people switching to Cursor/Windsurf for better AI context. I wanted to keep using my VS Code setup (and my keybindings!) but get that same level of "codebase awareness."

### The Solution: CoDRAG
I built a desktop app that runs alongside VS Code.
*   It watches your folder.
*   It builds a dependency graph (who calls what).
*   It serves this context via **MCP (Model Context Protocol)**.

### How to use it
If you use an AI extension that supports MCP (like Cline or others coming soon), you just plug CoDRAG in. When you ask a question, it doesn't just guess files—it traces the graph to find exactly the relevant code.

### Why not just "Open File"?
Because CoDRAG prunes the file to just the relevant signatures and implementations, saving your context window for the actual reasoning.

### Links
*   **Repo:** [Link]
*   **Docs:** [Link]

## Tone
Helpful, "power-user" tip.

## Timing
Weekday.
