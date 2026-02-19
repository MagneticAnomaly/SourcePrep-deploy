# Organic/Personal Post Draft for r/windsurf

## Title Options
1. **Cascade was struggling with my huge repo, so I built it a "brain" (Local MCP)**
2. **I built a local graph indexer to stop Cascade from guessing imports**

## Body Structure

### The Story
I switched to Windsurf recently and love the flow, but I noticed Cascade sometimes struggles to "see" deep into the codebase structure without me manually opening tabs.

I realized it needed a **structural map**, not just text search.

### What I built
I built **CoDRAG**, a local desktop app that indexes your code using Tree-sitter. It knows that `class B` inherits from `class A`, even if they're in different folders.

### The MCP Connection
Since Windsurf supports MCP, I hooked CoDRAG up to it. Now I can just say "Refactor the Auth logic," and CoDRAG feeds Cascade the exact dependency tree.

It feels like giving the AI X-Ray vision.

### Try it out
It runs locally (no cloud upload). Let me know if it helps your workflow!

**Link:** [Link]

## Tone
Enthusiastic user. "I made Windsurf better."
