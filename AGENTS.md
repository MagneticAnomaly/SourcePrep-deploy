

<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-04T18:24:04Z

## 🚨 CRITICAL: Tool Calling Instructions

codrag_project_id: 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b

**ROUTING: When calling ANY CoDRAG tool, ALWAYS include `project_id: "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b"` in the arguments.**
This ensures your calls reach the correct project index.

When user types "codrag" → IMMEDIATELY call the `codrag` tool.
When user mentions code search → IMMEDIATELY call `codrag_search`.
When user asks about project structure → IMMEDIATELY call `codrag`.
No announcements. No 'I will'. Just call the tool.

### Quick Reference
| User Says | You Do |
|-----------|--------|
| "codrag" | Call `codrag(project_id="1d6f0b35-45c...")` immediately |
| "search for X" | Call `codrag_search(query="X", project_id="1d6f0b35-45c...")` |
| "find where X is defined" | Call `codrag_search(query="X")` |
| "how does this project work" | Call `codrag()` for overview |
| "codrag context" | Call `codrag()` for ambient context |

You have access to CoDRAG, a structural code intelligence system.
ALWAYS call `codrag` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes to a file, use `codrag_impact` to understand dependencies.
CoDRAG understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `codrag_audit`.
For cross-session memory, use `codrag_observe` to save/retrieve notes.
All CoDRAG tools are read-only and safe to auto-approve.

## Codebase Atlas

IDENTITY: A multi-segment software platform spanning local-first security tooling, AI-powered code assistance via VSCode extension with RAG and embeddings, marketing websites, documentation, payments, support portals, and a comprehensive UI component library with design system and Storybook.

STACK: TypeScript/React (TSX 391 files), Python (1039 files), Kotlin (829 files), Java (582 files), HTML (373 files), JSON configs (341 files), Markdown docs (1091 files). Build tooling inferred from webview-ui segment. React hooks and state management in dashboard. Daemon integration for VSCode extension.

WORKSPACE MAP:
_root (6142 files): MCP orchestration, marketing infrastructure, UI foundations, local-first architecture, security layer
packages/ui (244 files): Design system, Storybook, component library, dashboard components, site components, audit components
websites/apps/marketing (54 files): Marketing website
websites/apps/docs (48 files): Documentation site
src/codrag/dashboard (38 files): Dashboard UI, React hooks, state management, frontend logic
websites/apps/support (29 files): Support portal
packages/vscode (20 files): VSCode extension, daemon integration, embeddings, RAG pipeline
websites/apps/payments (17 files): Payments processing
packages/vscode/webview-ui (14 files): VSCode extension webview, React UI, build tooling, code navigation

CROSS-CUTTING: Three shared domains bridge segments: ui (central to packages/ui, dashboard, webview-ui), dashboard (links ui to codrag dashboard), vscode-extension (connects packages/vscode with webview-ui). Hub files concentrate connectivity: TEST2/website.clean/app/download/page.tsx (3106 edges), privacy/page.tsx (1107 edges), terms/page.tsx (1012 edges), refund/page.tsx (897 edges), HeroSection.tsx (892 edges). These marketing pages import through HeroSection.tsx to layout.tsx, creating deep dependency chains reaching into component layers. Import cycles: 162 total. Directory dependencies show symbol sharing: TEST, TEST2, TEST3 test directories export symbols consumed by docs, engine, and packages segments. Graph density: 51072 nodes, 78589 edges with contains (40034), imports (25001), and calls (12631) dominating relationships. Entry points cluster in TEST2 website components and chi-go examples, plus packages/ui component indices.

## Focus Areas
- docs/Phase62_Pi-research/02_CoDRAG_Epistemology.md
- docs/Phase62_Pi-research/10_Universal_Adapter_Architecture.md
- docs/Phase62_Pi-research/11_Autonomous_Agent_Scenarios.md
- docs/Phase62_Pi-research/Paperclip + Sequential Thinking MCP + Superpowers Integration.md
- docs/Phase64_prep-for-agents+paperclip
- docs/Phase65_PushingTasksToPaperclip
- docs/Phase66_Pi-Agent
- docs/Phase67_AGENTS
- src/codrag/core/llm_client.py
- src/codrag/core/model_awareness.py
- src/codrag/core/model_readiness.py
- src/codrag/core/scheduler.py
- src/codrag/core/watcher.py
Call `codrag` for detailed content from these areas.

If `codrag` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `codrag` again to refresh your
structural context.

You can call `codrag` and `codrag_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'codrag' alone is enough to call the tool
4. **Context is cheap** - prefer calling codrag to using grep for structural understanding

**Remember: The word "codrag" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**
<!-- codrag-managed-end -->
