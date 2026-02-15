# Post Draft for r/windsurf

## Title Options
1. **Giving Windsurf "X-Ray Vision" with a local structural context server (MCP)**
2. **I built a local graph indexer that plugs into Windsurf via MCP**
3. **Better context for Cascade: A local tool to trace code dependencies**

## Body Structure

### Hook
Windsurf's Cascade is great, but like all LLM tools, it's only as good as the context it gets. I wanted to feed it precise, structural data about my codebase without dumping everything into the context window.

### The Solution
I built **CoDRAG**, a local desktop app that works as an **MCP server**. It uses a rust-based graph engine to map out your code's structure (definitions, references, imports).

### Workflow
You connect it to Windsurf (since Windsurf has native MCP support now!), and then you can ask Cascade to "use codrag to trace the AuthController."

It returns the file content **plus** the relevant imported types and interfaces, so Cascade can write correct code on the first try without hallucinating method signatures.

### Key Features
*   **Local-first:** Index never leaves your machine.
*   **Structural:** Understands code, not just text.
*   **Zero-config:** Just point it at your folder.

### Links
*   **Quick Start for Windsurf:** [Link to Docs]
*   **Repo:** [Link]

## Tone
Enthusiastic about Windsurf/Cascade. Position CoDRAG as a "power-up" for the IDE.

## Timing
Any weekday.

## Links to Include
- **Primary:** Docs page for "Windsurf Integration"
- **Secondary:** GitHub Repo
