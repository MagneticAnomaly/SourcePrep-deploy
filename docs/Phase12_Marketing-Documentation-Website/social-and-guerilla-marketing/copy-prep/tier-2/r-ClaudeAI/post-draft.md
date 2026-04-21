# Post Draft for r/ClaudeAI

## Title Options
1. **Giving Claude "structural awareness" of my repo via a local MCP server**
2. **I built a local code indexer for Claude Desktop (works via MCP)**
3. **Better than `grep`: Using Prep to feed Claude precise code context**

## Body Structure

### Hook
Claude 3.5 Sonnet is amazing at coding, but the "Add Folder" context in Claude Desktop can be a bit dumb (it's just text).

### The Solution
I built **Prep**, a local MCP server designed specifically for this. It builds a graph of your code.

### Workflow
1.  Connect Prep to Claude Desktop (`claude_desktop_config.json`).
2.  Ask Claude: "How is the `User` class used in `auth.py`?"
3.  Claude calls the Prep tool, traces the graph, and sees *only* the relevant lines.

### Result
Less "I can't see that file" errors, and less wasted context tokens.

### Links
*   **Repo/Docs:** [Link]

## Tone
Helpful, "here's a tool to make Claude better."

## Timing
Weekday.
