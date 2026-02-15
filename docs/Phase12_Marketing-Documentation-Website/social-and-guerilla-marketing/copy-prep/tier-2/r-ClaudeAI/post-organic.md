# Organic/Personal Post Draft for r/ClaudeAI

## Title Options
1. **I built a "Memory" for Claude Desktop that actually understands code**
2. **Feeding Claude my entire repo structure via MCP (Local tool)**

## Body Structure

### The Love/Hate
I love Claude 3.5 Sonnet. It's the best coding model.
But the "Add Folder" feature in Claude Desktop is basically just `cat *`. It doesn't understand connections.

### The Solution
I built **CoDRAG**, a local MCP server.
When I ask Claude about a bug, CoDRAG traces the function calls and feeds Claude *only* the relevant code paths.

It feels like Claude suddenly "gets" the architecture of my app.

**Repo:** [Link]

## Tone
"Claude is great, but let's make it better."
