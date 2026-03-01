# Phase 42: SEO and AI Search Optimization (AIO) Plan

## 1. Objective & Target Audience
To build organic visibility for CoDRAG across traditional search engines (Google, Bing) and AI-driven search engines (Perplexity, ChatGPT Search, Claude). 
**Target Audience**: Senior/Staff Engineers, IT Admins, Enterprise Architects, and AI developers who are frustrated with the privacy, cost, or context-window limitations of cloud-based AI coding tools.

## 2. Keyword & Positioning Strategy (SEO)

### Primary Core Themes
- "Local-first codebase indexing"
- "MCP server for multi-repo search"
- "Structural code graph for AI"
- "BYOK AI coding assistant"
- "Air-gapped AI code generation"

### Competitor "Vs / Alternative" Keywords
Engineers often search for alternatives when hitting limits (cost, privacy, or multi-repo support) with existing tools.
- *Cloud Indexers*: "Greptile alternative", "Sourcegraph Cody vs", "Bloop.ai alternative"
- *IDE Built-ins*: "Cursor codebase indexing alternative", "Windsurf multi-repo context"
- *Concepts*: "GraphRAG for codebases", "Local alternative to GitHub Copilot Enterprise"

### High-Intent Long-Tail Keywords
- "How to index local codebase for Cursor"
- "Provide multi-repo context to Claude Desktop"
- "Zero-cloud codebase RAG"
- "Prevent AI context window bloat for code"

## 3. AI Search Optimization (AIO) Strategy
AI search engines (Perplexity, ChatGPT, Gemini) prioritize high-signal, well-structured, authoritative technical content over standard marketing fluff. 

### AIO Tactics:
1. **High-Density Technical Content**: AI models heavily weight technical depth. We must publish deep-dives on *how* CoDRAG works (e.g., AST parsing, LOD context compression, local Rust daemon).
2. **Structured Comparison Tables**: AI bots parse HTML `<table>` and Markdown tables excellently. We need a dedicated `/compare` page with a matrix showing CoDRAG vs. Cursor vs. Greptile vs. Sourcegraph across dimensions like (Local-first, BYOK, Multi-repo, Trace Graph).
3. **Use of Exact Terminology**: Frequently use standard AI terms (RAG, GraphRAG, Context Window, Token Compression, Embeddings, ONNX, MCP) so AI models conceptually cluster CoDRAG with cutting-edge AI infrastructure.
4. **Third-Party Validation Markers**: AI models look for Reddit, HackerNews, and GitHub discussions. (Plan to seed technical discussions in these channels post-launch).
5. **"What is CoDRAG?" Section**: Have a clear, single-paragraph definition on the homepage and docs that LLMs can easily extract as a featured snippet.

## 4. Content Execution Plan (What to Build)

### A. Comparison Pages (`/compare/*`)
Create dedicated, honest comparison pages. 
- `/compare/codrag-vs-greptile` (Focus on Local vs Cloud)
- `/compare/codrag-vs-cursor-indexing` (Focus on structural trace graph vs simple BM25 vector search)

### B. Technical "Deep Dive" Blog Posts
- *“Why Vector Search Fails for Codebases (And Why We Built the Trace Index)”*
- *“Implementing Local-First RAG for Claude Desktop using MCP”*
- *“How to Compress Code Context by 80% using LOD (Level of Detail)”*

### C. Use-Case Pages (`/use-cases/*`)
- `/use-cases/enterprise-security` (Air-gapped, zero cloud, local-first)
- `/use-cases/multi-repo-architectures` (Microservices, monorepos)
- `/use-cases/mcp-integration` (Cursor, Windsurf, Claude Desktop)

## 5. Technical SEO & Schema Checklist
- [ ] **JSON-LD Schema**: Add `SoftwareApplication` and `Product` schema to the Next.js layouts.
- [ ] **Semantic HTML**: Ensure `<header>`, `<article>`, `<nav>`, and logical `H1`->`H3` structures.
- [ ] **Meta Tags & OpenGraph**: Dynamic meta descriptions and Twitter/OG images for every docs and marketing page.
- [ ] **Sitemap & Robots.txt**: Generate `sitemap.xml` combining `/marketing`, `/docs`, and `/blog` routes to ensure instant indexing.
- [ ] **Canonical URLs**: Prevent duplicate content penalties between similar docs/marketing pages.

## 6. Next Steps for Implementation
1. Add JSON-LD schema generation to the Marketing site's `layout.tsx`.
2. Draft the content for the first 2 competitor comparison pages.
3. Update the homepage with a highly extractable "What is CoDRAG?" H2/paragraph for AI bot ingestion.
