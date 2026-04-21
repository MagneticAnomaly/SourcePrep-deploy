# Additional Marketing Article Drafts (March 2026)

This document contains a fresh set of casual and technical marketing drafts. The casual drafts are designed for social channels (Reddit, X, LinkedIn, IndieHackers) and include hooks to link back to the technical drafts (Medium, Dev.to, Hacker News). 

**Core Rule Applied:** Every draft explicitly states what Prep does in the first 1-2 sentences.

---

## 📱 CASUAL DRAFTS (For Social Media & Forums)

### Casual Draft 1: Reddit (r/LocalLLaMA, r/coding, r/Cursor)
**Title:** We built an epistemic context engine to help AI coding assistants actually understand large codebases. 

**Body:**
Prep is a privacy-first context engine that gives your AI coding assistants (like Cursor, Windsurf, or Claude) a deep, structural understanding of your codebase before they write any code. It runs locally by default but is versatile enough to support BYOK (Bring Your Own Key) for cloud models if you prefer. 

If you've ever pasted a bunch of files into an LLM and watched it hallucinate a function that doesn't exist, you know the pain. The problem isn't the AI; it's that it doesn't understand your architecture. Most tools just use simple text search or dump raw files. We built Prep to actually map the codebase. It uses a high-performance Rust engine to build a "Trace Graph" of your code's structure (imports, calls, dependencies) and combines it with semantic vector search.

When your AI asks for context via MCP, Prep doesn't just hand it 50 files. It routes the query, traverses the graph, and delivers a compressed "capsule" of exactly what it needs, complete with validation scores. 

If you want to see the nerdy details on how we built a continuous graph enrichment pipeline to maintain epistemic state, we wrote a technical deep dive here: **[Link to Technical Article 1]**.

Would love for you guys to try it out and let us know what you think! 

---

### Casual Draft 2: X / Twitter Thread
**1/** Prep is a versatile context engine that plugs into your AI coding assistants (like Cursor or Windsurf) and feeds them the exact architectural context they need. It can run 100% locally or via your preferred cloud APIs.

**2/** The problem with AI coding right now isn't the models—it's that they lack an epistemic understanding of your codebase. If you just dump code into an LLM, it gets confused by distractors.

**3/** We built Prep to fix this. It sits on your machine, parses your entire repository using a native Rust engine, and builds an intelligent "Trace Graph" of how every file, function, and class connects. 

**4/** When Claude or Cursor needs context (via MCP), Prep doesn't just do a keyword search. It understands the architecture. It finds the relevant node and traverses the graph to pull in the exact dependencies needed.

**5/** Best part? You control the privacy. You can use local ONNX embeddings that run fast on your hardware, or securely hook up your own cloud API keys for heavier lifting. 

**6/** We wrote a full breakdown on how we use continuous "Graph Enrichment" to maintain an AI's understanding of your code. Check out the architecture here: **[Link to Technical Article 2]**. Try Prep today at runprep.io!

---

### Casual Draft 3: LinkedIn / IndieHackers
**Headline:** How we gave AI coding assistants a real understanding of architecture.

**Body:**
Prep is a privacy-first context engine that connects to your favorite AI tools (Cursor, Claude, Windsurf) and gives them a deep, structural understanding of your entire codebase. 

As developers, we don't just search for keywords when fixing a bug; we trace execution flows, look at imports, and understand the architecture. Why do we expect our AI to do it differently? 

We built Prep to give AI that same architectural awareness. It builds an "epistemic" Trace Graph of your project using a fast Rust engine. When your AI needs context, Prep provides highly compressed, structurally accurate snippets—saving massive amounts of tokens and reducing hallucinations. 

It's highly versatile: you can run the entire pipeline 100% locally for total privacy, or use your own cloud API keys for specific reasoning tasks. 

Read our latest post on the engineering behind our continuous graph enrichment pipeline: **[Link to Technical Article 1]**.

---
---

## 💻 TECHNICAL DRAFTS (For Blogs, Dev.to, Medium, Hacker News)

### Technical Draft 1: Dev.to / Medium / Personal Blog
**Title:** Beyond Vector Search: Building an Epistemic Context Engine for AI Assistants
**Subtitle:** How Prep uses Trace Graphs and continuous enrichment to give AI a structural understanding of codebases.

**Introduction**
Prep is a privacy-first context engine that connects to AI coding assistants (like Cursor, Windsurf, or Claude via MCP) and delivers structurally accurate, highly compressed codebase knowledge. While it can run entirely offline, it offers BYOK versatility for cloud models.

**The Problem: Lack of Epistemic State**
Most coding assistants treat a repository as a bag of text. They use naive chunking and basic vector search to retrieve snippets. This works for simple questions but fails on complex architectural tasks because the AI has no "epistemic state"—no real understanding of how components interlock, inherit, or depend on each other.

**The Solution: A Continuous Graph Enrichment Pipeline**
We built Prep to mimic human architectural understanding. It doesn't just index; it continuously learns.

**How Prep Works:**
1. **The Rust Engine:** Prep uses a native Rust engine with Tree-sitter to parse your entire repository in milliseconds, building a baseline "Trace Graph" of all structural relationships.
2. **Epistemic Enrichment:** The pipeline continuously validates this graph. It evaluates nodes, computes confidence scores, and synthesizes "Module Clusters." This creates an epistemic map of the codebase.
3. **Dual-Layer Retrieval:** When an AI asks a question, Prep uses semantic routing (to find the right module) and then expands through the Trace Graph to gather the exact callers and dependencies needed.
4. **Level of Detail (LOD) Compression:** We don't send raw files. Prep compresses peripheral files dynamically to just their structural skeletons (signatures/docstrings). This reduces token usage by up to 80% while retaining the architectural signal.

**The Result**
Your AI assistant gets a curated, structurally sound "capsule" of context. It knows exactly what dependencies exist and where state is updated. Whether you run it locally or via BYOK, the result is smarter, context-aware coding.

Try out the MCP server today and watch your AI get dramatically smarter.

---

### Technical Draft 2: Show HN (Hacker News)
**Title:** Show HN: Prep – An epistemic context engine for AI coding assistants

**Body:**
Prep is a privacy-first context engine that gives AI coding assistants (Cursor, Windsurf, Claude via MCP) a deep structural map of your codebase. It runs locally by default but supports BYOK APIs for versatility.

Hey HN,

We found that most AI coding tools fail on complex tasks because they rely on simple vector search. They treat code like prose, ignoring the structural relationships (inheritance, call graphs, module boundaries) that define software. We wanted to give the AI actual "epistemic" understanding.

We built Prep to fix this. 

**Under the hood:**
- **Rust/Tree-sitter Parser:** It rapidly parses your repo into an in-memory Trace Graph (capturing imports, calls, classes, etc.).
- **Continuous Enrichment:** We run a background pipeline that synthesizes "Module Clusters" and computes confidence scores for different parts of the graph, maintaining an active epistemic state.
- **Trace Expansion:** When the AI asks a question, it finds the semantic pivot point, then traverses the graph to pull in actual dependencies and callers.
- **LOD (Level of Detail) Compression:** Instead of sending full files, it compresses neighbors down to their structural skeletons. This yields an 80% token reduction while keeping the exact architectural signal the AI needs.

The result is a highly sophisticated retrieval system: it routes via high-level module themes and expands via low-level trace edges. You can run the whole pipeline offline using ONNX and local LLMs, or plug in your own API keys.

We'd love for you to try it out. The MCP server integrates in seconds. Happy to answer any questions about the graph traversal, our enrichment pipeline, or the LOD compression heuristics.
