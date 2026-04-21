# Organic/Personal Post Draft for r/LocalLLaMA

## Title Options
1. **We got tired of RAG failing on our monorepo, so we built a local graph engine instead**
2. **Standard RAG was too "dumb" for our code, so we replaced vectors with a dependency graph (Rust + Tree-sitter)**
3. **Sharing our frustration-driven project: A local context engine that actually understands imports**

## Body Structure

### The Frustration (Hook)
Hey everyone,

We've been building heavy Python/Rust systems for a while, and we kept hitting a wall with local LLMs. We love running Llama 3 locally, but the RAG part always felt... bad.

You know the drill: you ask "how does Auth work?", and the vector search gives you 5 chunks of comments or unit tests, but misses the *actual* base class definition because it didn't use the word "Auth" in the file name.

It felt like "vibe-based coding," not engineering.

### The "Aha" Moment
We realized that code isn't just text. It has strict structure. If I'm looking at `login()`, I *need* to see `UserSession` (which is imported), not just a file that also has the word "login" in it.

So we paused our main work and built **Prep**.

### What we built
It's a desktop app (Mac/Windows) that acts as a "structural" context engine.
*   It watches your folder.
*   It uses **Tree-sitter** to parse every file into an AST.
*   It builds a dependency graph using a custom Rust graph engine (`prep-graph`).
*   When you query it, it "walks" the graph to find connected code, not just similar text.

### The Result
We hooked it up to our local IDEs (via MCP), and honestly, it's a relief. The models stop hallucinating methods that don't exist because the *actual* method signature is right there in the context window.

It runs locally. It doesn't send code to the cloud. We built it because we needed it to exist.

### Links
*   **Repo:** [Link]
*   **How the graph algo works:** [Link]

Would love to hear if anyone else has tried graph-based retrieval for code. It was a pain to build, but worth it.

## Tone
Honest, exhausted-but-happy, "we fixed it," technical camaraderie.
