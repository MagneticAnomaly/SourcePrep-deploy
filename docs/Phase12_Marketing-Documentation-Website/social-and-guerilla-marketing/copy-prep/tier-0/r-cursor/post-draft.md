# Post Draft for r/cursor

## Title Options
1. **I built a local MCP server to give Cursor better context (using code graphs, not just embeddings)**
2. **Improving Cursor's @codebase with a local structural indexer**
3. **Free local tool to fix "context window" issues in Cursor (via MCP)**

## Body Structure

### Hook
I love Cursor, but sometimes the `@codebase` indexing misses the mark on complex dependency chains, or I hit context limits when working in a massive monorepo.

### The Solution
I built **CoDRAG**, a local desktop app that acts as an **MCP (Model Context Protocol) server** for Cursor.

Instead of relying solely on Cursor's cloud embeddings, CoDRAG builds a local dependency graph of your code. When you ask it for context, it "traces" the imports and definitions to give you exactly the code you need—and nothing you don't.

### How to use it with Cursor
1.  Run the CoDRAG app (indexes your repo locally).
2.  Add the MCP server command to your Cursor config.
3.  Type `@codrag search "auth flow"` in Chat or Composer.

It injects the relevant files *plus* the structural context (interfaces, types) directly into the chat context.

### Why do this?
*   **Privacy:** The index stays on your machine.
*   **Precision:** It grabs *connected* code, not just *similar* text.
*   **Freshness:** Updates instantly when you save a file.

### Links
*   **Setup Guide:** [Link to Docs]
*   **Download:** [Link]

Let me know if this helps your workflow!

## Tone
Helpful, community-focused. "I built this to scratch my own itch." NOT "Switch to my tool." Frame it as a **plugin/enhancement** for Cursor.

## Timing
Any weekday.

## Links to Include
- **Primary:** Docs page specifically for "Cursor Integration"
- **Secondary:** GitHub Repo
