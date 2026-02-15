# Post Draft for dev.to Series

## Series Title: "Building a Local-First Code Context Engine"

## Part 1: "Why I stopped trusting vector search for my code"
*   **Hook:** RAG is great for text, bad for strict code logic.
*   **Content:** Examples of vector search failures. Introduction to the "Graph" concept.
*   **CTA:** Follow along as I build the graph engine in Rust.

## Part 2: "Parsing the world with Tree-sitter and Rust"
*   **Hook:** How to turn a mess of text into a structured tree instantly.
*   **Content:** Rust + Tree-sitter basics. Handling incremental updates (the hard part).
*   **CTA:** Check out the open-source parser crate.

## Part 3: "Connecting to Cursor via MCP (Model Context Protocol)"
*   **Hook:** Building your own "Copilot" features without building an IDE.
*   **Content:** Tutorial on implementing an MCP server. How CoDRAG talks to Cursor.
*   **CTA:** Download CoDRAG to try the MCP server yourself.

## Part 4: "The 'Context Budget': How to stuff an LLM without choking it"
*   **Hook:** 128k tokens isn't infinite.
*   **Content:** Algorithms for pruning the graph. Selecting the "best" context.
*   **CTA:** Try the context visualizer in the CoDRAG dashboard.

## Tone
Educational, "Build in Public," transparent. Code snippets are mandatory. Use plenty of emojis and screenshots.

## Tags
`#rust`, `#python`, `#ai`, `#productivity`, `#mcp`

## Timing
Publish one part per week. Cross-post to Medium/Hashnode a few days later.
