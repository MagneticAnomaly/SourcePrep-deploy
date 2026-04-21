# Post Draft for Hacker News (Show HN)

## Title Options
1. **Show HN: Prep – Local-first structural code context for AI assistants**
2. **Show HN: Prep – A desktop app for indexing codebases without the cloud**
3. **Show HN: Search and cite your local repo using Model Context Protocol**

*Chosen Strategy: Option 1 is the strongest balance of "what it is" and "why it's interesting."*

## Body Structure
(Note: HN posts can be a link or text. For a tool like this, a **text post** with links is often better to explain the nuance, OR a **link post** to a very strong technical blog post/GitHub repo. Let's assume a text post for maximum control, or a link to the "Architecture Overview" blog post with a strong first comment.)

**Option A: Text Post Body**

Hello HN,

I built **Prep**, a local-first context engine for large codebases.

Most AI coding tools rely on uploading your code to the cloud or using naive chunk-based embeddings. I wanted something that ran locally, respected privacy, and understood code structure (definitions, references) rather than just text similarity.

Prep is a desktop app (macOS/Windows) that:
1.  **Indexes locally:** Uses Tree-sitter and a Rust-based graph engine to map your repo's structure.
2.  **Stays fresh:** A file watcher updates the index instantly when you save.
3.  **Connects via MCP:** It acts as a Model Context Protocol server, so you can pull this context into Cursor, Windsurf, or Claude Desktop.
4.  **No GPU needed:** The core graph retrieval runs on CPU.

It uses a "Trace-Assisted Grasping" approach: if you ask about a function, it traverses the dependency graph to pull in the interface and relevant types, rather than guessing with vector search.

It's free for individual use (local-only).

**Repo/Docs:** [Link]
**Architecture Deep Dive:** [Link]

I’d love feedback on the graph traversal approach vs. standard RAG.

## Tone
Concise, humble, factual. No marketing adjectives ("revolutionary", "amazing"). Focus on the *problem* (naive embeddings, privacy) and the *solution* (structural graph, local execution).

## Timing
Post around 8 AM - 10 AM PT on a weekday.
**CRITICAL:** Stay in the comments for 3 hours. Answer every technical question with detail.

## Links to Include
- **Primary:** Landing Page / GitHub (clean, no-nonsense)
- **Secondary:** Architecture Blog Post (for the curious)
