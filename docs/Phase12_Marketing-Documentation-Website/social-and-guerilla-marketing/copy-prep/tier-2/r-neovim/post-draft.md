# Post Draft for r/neovim

## Title Options
1. **I built an MCP Server for structural code context (works with avante.nvim / LLM plugins)**
2. **Prep: A local rust-based graph indexer to feed context to your AI plugins**
3. **Offloading "code understanding" to an external daemon so my editor stays fast**

## Body Structure

### Hook
We all love that Neovim is fast. But as soon as you start adding "AI Context" plugins that grep 1000 files, things can get heavy (or the context quality sucks).

### The Solution
I built **Prep**, a standalone local daemon (written in Rust) that indexes your codebase into a dependency graph. It exposes this via **MCP (Model Context Protocol)**.

### Why this fits Neovim
*   **Unix Philosophy:** Let the editor edit. Let the context engine index.
*   **Standard Protocol:** If you use an MCP client (like `avante.nvim` or others adding support), you can query Prep for "all implementations of `Auth`" and get a precise, pruned context back.
*   **Performance:** The heavy lifting (Tree-sitter parsing, graph analysis) happens in a separate process.

### Features
*   Tree-sitter based graph analysis.
*   Local-first (no cloud).
*   Trace-Assisted Grasping (TAG) for retrieving connected code.

### Links
*   **Repo:** [Link]
*   **Docs:** [Link]

## Tone
Technical, respectful of the "editor speed" ethos. Focus on modularity.

## Timing
Weekday.
