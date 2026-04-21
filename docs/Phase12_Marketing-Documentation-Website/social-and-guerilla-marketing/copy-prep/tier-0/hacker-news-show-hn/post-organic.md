# Organic/Personal Post Draft for Hacker News

## Title Options
1. **Show HN: We built a local code indexer because we didn't want to upload our repo**
2. **Show HN: Prep – Fixing the "context window" problem with structural graph analysis**

## Body Structure

### The Story
Hi HN,

My co-founder and I have been working on complex codebases, and we kept running into a problem with AI coding tools: **Context.**

The "naive RAG" approach (chunking text + vector search) works great for documentation, but it's terrible for code. It misses the strict dependencies. If you change a function signature in `utils.py`, the AI looking at `main.py` has no idea unless you manually paste the file.

We didn't want to upload our intellectual property to a cloud service just to get better indexing.

### So we built Prep.

It's a local-first desktop application (Rust + Tauri + Python) that indexes your code *structurally*.

Instead of just embedding text, it builds a graph of definitions and references. When you ask a question, it traverses the graph to pull in the exact interfaces and types required to answer it.

### Why strictly local?
1.  **Privacy:** We work on some sensitive projects. We assume you do too.
2.  **Speed:** Local file watching means the index is updated ms after you save.
3.  **Ownership:** You pay for the license once (or use the free tier), and it's yours. No SaaS subscription for a tool that runs on your CPU.

We're using the **Model Context Protocol (MCP)** to pipe this data directly into Cursor and Windsurf.

We'd love to hear your thoughts on the local-first architecture.

**Repo:** [Link]
**Docs:** [Link]

## Tone
Builder-to-builder. Rational. "We solved a problem you probably have."
