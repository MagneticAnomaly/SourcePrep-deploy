# Organic/Personal Post Draft for r/vscode

## Title Options
1. **I built a local tool to give VS Code "X-Ray Vision" for imports**
2. **Fixing the "missing context" problem in VS Code Copilot/Cline**

## Body Structure

### The Frustration
I use VS Code with Cline (the AI agent extension). It's great, but it often gets confused about where types are defined in my monorepo. It hallucinates method signatures because it can't see the file 3 folders up.

### The Fix
I built a local helper app called **CoDRAG**.
It's a "Context Engine" that runs in the background.

When I ask Cline a question, CoDRAG intercepts the query, walks the dependency graph (using Tree-sitter), and hands Cline the *exact* definitions it needs.

### Result
My "Apply Fix" success rate went up massively because the AI actually sees the code it's calling.

**Link:** [Link]

## Tone
Helpful tip. "I fixed a workflow bottleneck."
