# CoDRAG
**The Context Engine for AI-Assisted Software Engineering**

## What is CoDRAG?
CoDRAG is an advanced context engine and semantic search platform designed specifically for the era of AI-assisted development. It bridges the gap between massive, complex codebases and Large Language Models (LLMs) by providing precise, graph-augmented context rather than simply overwhelming the model with raw text. 

Our mission is to give your AI tools the *right* code, not just *more* code—ensuring high-quality, accurate, and hallucination-free code generation.

## The Problem We're Solving
The traditional approach to AI coding context is broken. Dumping thousands of lines of code into an LLM prompt leads to degraded reasoning (the "Lost in the Middle" syndrome) and skyrocketing token costs. This creates several massive pain points for developers:
- **Context Bloat:** Even the most advanced models struggle to find the needle in the haystack when flooded with irrelevant files and distractor code.
- **Structural Blindness:** Standard semantic search (RAG) finds text matches but misses critical structural dependencies, like how a specific function connects to a broader interface or database schema.
- **Stale Information:** Codebases change rapidly. Outdated context fed to an AI leads to broken logic, hallucinated APIs, and frustrating debugging loops.

## How It Works
CoDRAG acts as the intelligent bridge between your codebase and your AI agent, providing a full-cycle context pipeline:

1. **Native Semantic Search:** Fast, locally-run embedding models (ONNX) search your codebase to find the most semantically relevant snippets without ever sending your raw code to external third-party APIs.
2. **Code Graph & Trace Expansion:** Using advanced AST parsing (Tree-sitter), CoDRAG builds an in-memory graph of your code's structure. When it finds a relevant snippet, it intelligently follows dependencies (imports, calls, interfaces) to gather the full structural picture.
3. **Smart Compression:** CoDRAG applies structural compression (Level-of-Detail extraction), stripping out bulky implementations while preserving critical signatures, types, and docstrings. This achieves up to 20:1 token compression without sacrificing reasoning quality.
4. **Model Context Protocol (MCP):** CoDRAG integrates seamlessly with modern AI IDEs via the open MCP standard, allowing your AI agent to natively query the codebase, resolve imports, and navigate the project autonomously.

## Built for the Future of Development
CoDRAG is delivered as a secure, local desktop application complete with a powerful visual dashboard for managing your knowledge bases, exploring trace graphs, and tuning your AI pipeline settings. Available in tiers ranging from Indie Hackers to Enterprise, it is the definitive intelligence layer for modern engineering.
