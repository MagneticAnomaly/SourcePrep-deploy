# Organic/Personal Post Draft for r/neovim

## Title Options
1. **I offloaded my "AI Context" to a local daemon so Neovim stays fast**
2. **Building a standalone MCP server for Neovim (Rust + Tree-sitter)**
3. **Avante.nvim + CoDRAG: Using a local graph engine for context**

## Body Structure

### The Performance Itch
I love Neovim because it's blazing fast. But as I started adding AI plugins (Copilot, Avante, etc.), I noticed they often choke when scanning large repos for context.

### The Philosophy
I realized the "heavy lifting" (parsing ASTs, finding references) shouldn't happen in the main editor thread (or even in Lua). It should be a separate process.

### The Tool
So I built **CoDRAG**. It's a standalone daemon written in Rust.
*   It watches files.
*   It builds a dependency graph.
*   It exposes an MCP (Model Context Protocol) server.

### The Workflow
Now, my editor just sends a lightweight query ("Get context for symbol X") to the daemon, and CoDRAG returns the pruned code. My Neovim UI stays snappy.

**Repo:** [Link]

## Tone
Performance-obsessed. "Keep the editor lightweight."
