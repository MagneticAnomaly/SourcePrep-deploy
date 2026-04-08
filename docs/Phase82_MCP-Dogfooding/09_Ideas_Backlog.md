# 09 — Ideas Backlog (Unfiltered)

Raw ideas generated from dogfooding. Not prioritized, not filtered. Some are obvious, some are wild. The goal is breadth — filter later.

---

## A. Tool-Level Improvements

### A1. `codrag` — Ambient Context

- **Concept summaries in ambient response** (from doc 08): Top 3-5 concepts as 1-2 line summaries, with drill-down pointer to `codrag_concepts`
- **Working directory weighting**: If agent is in `src/codrag/mcp/`, emphasize the MCP module summary and its hub files, not the pipeline orchestrator
- **"What changed since last call" mode**: Track what the agent already received and return only deltas — new modules, changed hub files, new concepts
- **Configurable sections**: Let agents specify which sections they want: `sections=["modules", "hubs", "concepts"]` vs `sections=["modules"]`
- **Project health headline**: One line at the top: "Project: CoDRAG | 1,012 files | 2 circular deps | 124 import cycles | index 3m old"
- **Active branch context**: If the current git branch has recent commits, mention them: "On branch `fix/mcp-handler` — 3 commits ahead of main, touching mcp/server.py"
- **Role-based code hubs**: Different roles should see different hub files. A "qa" role should see test files and CI config; an "engineer" role should see core source files
- **Ephemeral focus**: Let agents set a session focus that `codrag` respects: "I'm working on the audit system today" → ambient context emphasizes audit-related modules
- **Dependency heatmap**: Instead of listing modules, show which modules have the most churn, the most recent changes, or the most open issues

### A2. `codrag_search` — Semantic Search

- **Intent classification**: Before searching, classify the query: "how does X work?" (explanation), "where is X?" (location), "what uses X?" (dependents), "why is X like this?" (rationale). Route to different retrieval strategies.
- **Search history**: Track what the agent searched for in this session. If they search for "auth middleware" and then "rate limiting", the second search could boost results that are near the first result's files.
- **Multi-hop search**: "Find the function that handles MCP tool dispatch AND the tests for it" — two queries combined with structural linking
- **Code-only / docs-only toggle**: Simple scope filter: `scope="code"` excludes `.md`, `.txt`, `.rst`. `scope="docs"` excludes source files
- **"Show me an example"**: A query type that returns usage examples of a function/pattern rather than definitions. "Show me how useEventStream is used" → returns call sites, not the hook definition
- **Fuzzy symbol search**: Searching for "handle_tool_list" (missing 's') should still find `handle_tools_list`. Levenshtein distance or n-gram matching on symbol names
- **Search within results**: After a broad search returns 5 files, let the agent narrow: "within those results, find error handling" — sub-search scoped to previously returned content
- **Temporal search**: "What code changed related to MCP in the last week?" — combine semantic search with git history
- **Natural language to grep**: If the semantic search misses, automatically fall back to literal string matching and tell the agent: "No semantic matches, but found 3 literal occurrences of 'build pipeline'"
- **Confidence-based truncation**: If confidence is high (>0.8), return full context. If low (<0.5), return just file paths with a note: "Low confidence — consider rephrasing"
- **Embedding model transparency**: Show which embedding model was used and its characteristics: "Searched with nomic-embed-text (768d). For code-heavy queries, consider switching to code-specific embeddings."

### A3. `codrag_impact` — Dependency Analysis

- **Risk scoring**: Not just "what depends on this" but "how risky is changing this" — weighted by test coverage, change frequency, and number of dependents
- **Change simulation**: "If I rename this function, what breaks?" — parse the function signature and find all call sites that would need updating
- **Diff-aware impact**: "I changed lines 50-75 of server.py — what's affected?" — only analyze the impact of specific changes, not the whole file
- **Visual output option**: Return a Mermaid diagram string that agents can render: `graph LR; server.py --> mcp_tools.py; server.py --> errors.py;`
- **Blast radius summary**: Instead of listing all dependents, give a score: "Blast radius: HIGH (23 dependents, 3 critical paths, no test coverage for 7 files)"
- **Circular dependency highlighting**: When analyzing a file that's part of a cycle, flag it prominently: "This file is in a circular dependency with events.py — changes may have unexpected cascading effects"
- **Historical impact**: "How often has changing this file broken other things?" — combine with git history to show files that historically cause problems when modified
- **Safe change zones**: Identify parts of the file that have low impact if changed — functions that are only used internally, private methods, etc.
- **Import depth analysis**: "This file is imported at depth 1 by 3 files, depth 2 by 12 files, depth 3 by 45 files" — exponential blast radius is a red flag

### A4. `codrag_audit` — Codebase Health

- **Audit diff**: Compare current audit to previous audit: "3 new warnings since last run, 2 resolved, severity trend: improving"
- **Module-scoped audit**: `codrag_audit(scope="src/codrag/mcp/")` — only scan the MCP module
- **Custom rules**: Let users define project-specific audit rules in a config: "files in api/ must not import from core/ directly"
- **Fix difficulty estimation**: Each finding gets a rough effort tag: "5min", "1hr", "1day", "refactor" — so agents can pick low-hanging fruit
- **Auto-fix suggestions**: For simple findings (unused imports, naming inconsistencies), generate a concrete fix, not just advice
- **Test coverage integration**: "This file has 0% test coverage AND is a dependency bottleneck" — compound risk flags
- **Trend graphs**: Track codebase health over time. Even as text: "Complexity trend (last 5 builds): 847 → 852 → 849 → 861 → 877 ⬆ increasing"
- **"What should I fix before shipping?"**: A release-readiness check that focuses on critical issues in recently changed files
- **Positive findings**: Not just problems — also highlight good patterns: "Clean module boundary between api/ and core/ — no leaky abstractions detected"
- **Tech debt budget**: "You have ~40 hours of estimated tech debt. Top 3 items account for 60% of it."
- **Audit-driven refactoring**: `codrag_audit(action="refactor", finding_ids=["ARCH-1"])` returns the finding with surrounding code context, suggested fix, and affected files. This already exists but could be more aggressive with concrete code patches.

### A5. `codrag_observe` / `codrag_concepts` — Memory

- **Auto-promote observations to concepts**: If an observation has been cited 3+ times and is 30+ days old, suggest promoting it to a concept
- **Conflict detection**: If a new observation contradicts an existing concept, flag it: "This observation conflicts with concept 'CoDRAG is a knowledge provider' — should the concept be updated?"
- **Observation templates**: Common patterns get templates: `codrag_observe(action="save", template="bug", file_path="...", symptom="...", root_cause="...")`
- **Team-visible concepts**: If CoDRAG is used in a team context, concepts become shared knowledge that any team member's agent can access
- **Concept dependencies**: "Concept A (knowledge provider pivot) depends on Concept B (ActionItem model is universal output)" — changing one may invalidate the other
- **Concept voting/confidence**: Track how many times a concept has been confirmed vs questioned. High-confidence concepts get more weight in ambient context.
- **"Why was this decision made?" query**: `codrag_concepts(query="why no PM features")` → returns the specific concept with full rationale
- **Time-travel**: "What were the active concepts as of March 15?" — the `as_of` parameter exists but isn't widely used. Promote it.
- **Observation-triggered actions**: "When a new bug observation is saved for file X, automatically run codrag_impact on X and attach the blast radius to the observation"

---

## B. New Tools / Capabilities

### B1. `codrag_explain` — Code Explanation Engine
A dedicated tool for "explain this code to me" that combines:
- The code itself (from file read)
- Structural context (from trace graph — what calls it, what it calls)
- Conceptual context (from concepts — why it's designed this way)
- Historical context (from git blame — who wrote it, when, why)

Different from `codrag_search` which finds code. This one explains code you already found.

### B2. `codrag_plan` — Change Planning Assistant
"I want to add a new MCP tool" → CoDRAG returns:
- Files that need modification (from structural analysis)
- Similar past changes (from git history pattern matching)
- Risks and dependencies (from impact analysis)
- Relevant concepts and constraints (from concepts store)
- Suggested file creation order (from dependency graph)

This is the "before you start coding" companion tool.

### B3. `codrag_test` — Test Intelligence
- "What tests cover this file?" — map code to test files via naming conventions and import analysis
- "What should I test after changing X?" — combine impact analysis with test mapping
- "What's untested?" — gaps in coverage mapped to risk (high-impact untested code = urgent)
- "Generate a test outline for this function" — not writing tests, but suggesting what to test based on the function's behavior and callers

### B4. `codrag_timeline` — Project History Intelligence
- "What happened in the last week?" — commit summary with semantic grouping (not just a commit list)
- "Who knows about the MCP module?" — git blame analysis to identify domain experts
- "When was this file most actively developed?" — activity timeline per file
- "What's the velocity trend?" — are we speeding up or slowing down?

### B5. `codrag_review` — Pre-Commit Review
Before committing, run `codrag_review` on staged changes:
- Impact analysis on changed files
- Audit findings introduced by the changes (new large file? new circular dep?)
- Concept alignment check: "This change moves auth logic into core/ — note that Concept 'dependency direction' says agents/ → services/ → core/, never reverse"
- Style consistency: does the change match existing patterns in that module?

### B6. `codrag_onboard` — New Agent/Developer Onboarding
A guided walkthrough for agents (or humans) joining the project:
1. "Here's what this project is" (from atlas)
2. "Here's why it's designed this way" (from concepts)
3. "Here's what's happening right now" (from observations)
4. "Here's what needs work" (from audit)
5. "Here's how to make your first contribution" (from test/review setup)

This already partially exists as an MCP resource but could be a proper tool with interactive depth.

---

## C. UX / Protocol Improvements

### C1. Streaming Responses
MCP supports streaming but CoDRAG tools return complete responses. For large audit reports or search results, streaming would let agents start processing before the full response arrives. Especially valuable for `codrag_audit report` which can be 10K+ tokens.

### C2. Response Caching with Invalidation
Cache tool responses keyed on (project_id, tool, params, index_timestamp). If the index hasn't changed, return the cached response instantly. Invalidate when the index is rebuilt. This would make repeated `codrag` calls nearly free.

### C3. Tool Composition Macros
Define compound operations:
```
codrag_macro("pre-change-check", file_path="server.py") →
  1. codrag_impact(file_path, direction="dependents")
  2. codrag_audit(category="architecture", scope=file_path)
  3. codrag_search(query=file_path + " tests")
  → Combined response with all three results
```

### C4. Contextual Defaults
Remember the last file the agent worked with. If they call `codrag_impact` without a `file_path`, use the most recently edited file. Reduces parameter boilerplate.

### C5. Agent Feedback Loop
After returning results, accept feedback: "Was this helpful? yes/no". Track feedback per query pattern to improve retrieval ranking over time. Even simple click-through rates (did the agent actually use the returned file?) would be valuable signal.

### C6. Multi-Project Awareness
When working in a monorepo or multi-project setup, let tools cross-reference: "This function in project A is also used by project B" — relevant for shared libraries.

### C7. MCP Resource Enrichment
CoDRAG exposes MCP resources (atlas, modules, audit) but they're static snapshots. Make resources dynamic — subscribing to a module resource gives live updates when the module changes. This aligns with the MCP spec's resource notification feature.

### C8. Error Message Quality
When a tool fails (project not found, index stale, query too vague), return actionable error messages:
```
❌ Project index not found. 
To build: codrag build --project /path/to/repo
To check status: codrag status
```
Not just "Error: no index."

---

## D. Integration Ideas

### D1. Git Hook Integration
- Pre-commit: Run `codrag_review` on staged changes
- Post-commit: Update observations with commit summary
- Pre-push: Run audit on all commits being pushed

### D2. CI/CD Pipeline Stage
CoDRAG as a CI step that:
- Runs audit and fails the build if critical findings increase
- Generates a health report comment on PRs
- Tracks health trends across commits

### D3. IDE Status Bar
Show real-time CoDRAG status in the IDE:
- Index freshness indicator
- Current file's blast radius score
- Number of active concepts relevant to the current file

### D4. Slack/Teams Bot
"@codrag what's the blast radius of changing auth.py?" — same MCP tools but exposed via chat interface for non-IDE contexts.

### D5. Documentation Generation
Use concepts, observations, and structural analysis to auto-generate:
- Architecture decision records (ADRs) from concepts
- Module documentation from atlas + trace graph
- Onboarding guides from onboard tool output

### D6. LLM Context Injection
When an agent opens a file in an IDE, CoDRAG automatically injects relevant context into the LLM's prompt:
- Module summary for the file's module
- Related concepts
- Recent observations about the file
- Impact score

This is the "ambient intelligence" vision — agents don't need to call tools because CoDRAG proactively provides context.

---

## E. Wild Ideas (Might Be Crazy)

### E1. Codebase Personality
Give the codebase a "personality" derived from its patterns: "This codebase is verbose and well-documented. It prefers explicit error handling over exceptions. It uses dependency injection heavily." Generated from pattern analysis, this could guide agents to write code that fits the project's style without reading every file.

### E2. Concept Evolution Timeline
Visualize how the project's strategic concepts have evolved: "March: monolithic pipeline → April: subpackage migration → May: microservice consideration." Shows intellectual trajectory, not just current state.

### E3. "What Would Break If We Deleted This?"
The inverse of impact analysis. Instead of "what depends on this," ask "if this didn't exist, what would we need to rebuild?" Useful for evaluating whether legacy code is still load-bearing.

### E4. Cross-Repository Concept Transfer
"Project A decided to use event sourcing for audit logs. Project B is implementing audit logs. Should we suggest the same pattern?" Concepts become transferable across projects.

### E5. Confidence-Weighted Code Navigation
When an agent navigates from file A to file B, CoDRAG annotates the connection: "A imports B (confidence: 0.95, 3 direct calls)" vs "A is semantically related to B (confidence: 0.6, inferred by LLM)." Agents can trust high-confidence links and be cautious with low-confidence ones.

### E6. "Explain This Bug"
Combine trace graph, git history, and observations: "The circular dependency between queue.py and events.py was introduced in commit abc123 on March 15. At that time, the observation log says the events system was being refactored. The relevant concept is 'event-driven architecture migration.' This is likely an incomplete refactor."

### E7. Architectural Drift Detection
Compare the codebase's actual structure to its declared architecture (from concepts): "Concept says 'agents/ → services/ → core/' but services/foo.py imports from agents/bar.py — architectural drift detected." Concepts become testable assertions.

### E8. Natural Language Refactoring
"Make the MCP module less coupled to the pipeline orchestrator" → CoDRAG identifies the coupling edges, suggests which imports to remove or redirect, generates a step-by-step refactoring plan, and estimates blast radius at each step.

### E9. "Teach Me This Codebase" Mode
A conversational mode where an agent (or human) asks progressively deeper questions and CoDRAG builds a personalized mental model:
1. "What does this project do?" → atlas summary
2. "How does search work?" → module deep dive
3. "Why does it use ONNX embeddings?" → concept lookup
4. "What would I need to change to switch to OpenAI embeddings?" → impact + plan

Each answer builds on previous context, creating a learning path rather than a reference lookup.

### E10. Codebase "Immune System"
Concepts and observations act as the codebase's institutional memory. When an agent proposes a change that contradicts a concept or repeats a known mistake (from a bug observation), CoDRAG proactively warns: "A similar change was tried in Phase 42 and reverted because of X. The relevant observation is: [...]"
