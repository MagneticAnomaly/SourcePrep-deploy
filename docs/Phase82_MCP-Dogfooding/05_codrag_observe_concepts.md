# 05 — `codrag_observe` and `codrag_concepts` Tools (Memory)

**Grades:** observe A-, concepts N/A (empty)
**Calls tested:** observe get (1), concepts get (1)

## codrag_observe — What Works Well

### Decision history is genuinely valuable
The 10 observations paint a clear architectural narrative:
- Phase 62: Strategic pivot from PM features to knowledge provider
- Phase 62: Dual-agent architecture validated (Claude Code + Pi)
- Phase 62: A2A protocol adoption decided
- Phase 65: PM Push Adapter implemented
- Phase 66: Pi Agent built with 7 scenarios
- Phase 67: Unified implementation plan for 3 agents

This decision log is information that **cannot** be derived from code or git history. Git tells you *what* changed; observations tell you *why* and *what was considered and rejected*. For an agent joining mid-project, this is the difference between understanding the codebase and merely reading it.

### File anchoring enables staleness detection
Each observation is anchored to a file path (e.g., `src/codrag/services/pi_agent.py`). If that file changes significantly, the observation can be flagged as potentially stale. This is a good design choice that prevents memory rot.

### Decision format is well-structured
Each observation leads with the key facts, then provides numbered decision points. Example from the Phase 66 entry:
```
Pi Agent has 7 scenarios: Watchdog, Doctor, Geologist, Dispatcher, 
Librarian, Architect, Scholar. All scenarios are pure Python analysis 
— zero LLM required.
```
This is scannable and actionable.

---

## codrag_observe — Issues Found

### ISSUE 1: All observations are "decision" type — no variety (LOW)

All 10 observations are categorized as `[decision]`. The schema supports `note`, `decision`, `bug`, `pattern`, `assumption` — but none of those other types are used.

**Impact:** Decisions are the most valuable type, so this isn't terrible. But the absence of `bug` observations means known issues aren't tracked in cross-session memory. And the absence of `pattern` observations means recurring code patterns (e.g., "we always use Pydantic models for API schemas") aren't captured.

**Suggested fix:**
1. This is likely a usage/adoption issue, not a tool bug. The tool accepts all types correctly.
2. Consider auto-generating `pattern` observations from the audit (e.g., "consistent use of barrel exports in UI components") 
3. Consider auto-generating `bug` observations when the audit finds recurring issues
4. Add prompting in the MCP tool description: "Use category='bug' for known issues, 'pattern' for recurring code patterns, 'assumption' for things you're not sure about"

---

### ISSUE 2: No filtering or pagination in `get` (LOW)

`codrag_observe(action="get")` returned all 10 observations. In a mature project with 50+ observations, this would blow up the token budget. The tool accepts `query` and `file_path` filters, but there's no `limit` parameter visible in the MCP schema (though the backend may support it).

**Suggested fix:**
1. Default to returning the 10 most recent/relevant observations
2. Add a summary mode: "15 observations stored. 8 decisions, 3 patterns, 2 bugs, 2 notes. Use query='...' to filter."
3. Sort by recency by default — the oldest Phase 62 decisions are less likely to be actionable than Phase 66+ observations

---

### ISSUE 3: Observations are long — token-heavy for cross-tool injection (LOW)

When `codrag_search` injects observations via `working_dir`, it adds full observation text to the search results. Some observations are 500+ characters. In a token-constrained environment, injecting 3-4 observations could consume 2K+ tokens from the search budget.

**Suggested fix:**
1. When injecting observations into search results, use a 200-char truncated version
2. Include a pointer: "Full observation available via codrag_observe(query='Pi Agent')"

---

## codrag_concepts — Assessment

### Current state: Empty
`codrag_concepts(action="get")` returned "No concepts found."

This is the least adopted of the 6 tools. The tool is designed to store business rationale, design decisions, and domain knowledge — overlapping significantly with `codrag_observe` (which stores decisions).

### The observe/concepts boundary is unclear

| Feature | observe | concepts |
|---------|---------|----------|
| Stores decisions | Yes | Yes |
| Anchored to files | Yes | Yes (anchors) |
| Categories | note/decision/bug/pattern/assumption | architecture/domain/product/epistemic/process/brand/security/technical/pattern/constraint/decision |
| Staleness tracking | Yes (via file anchors) | Yes (via file anchors) |
| Cross-session | Yes | Yes |

The overlap is significant. An agent deciding whether to use `observe(category="decision")` or `concepts(category="decision")` has no clear guidance.

**Suggested fix:**
1. Differentiate clearly: observations = what happened (ephemeral facts, bugs, notes); concepts = why things are the way they are (durable knowledge, design rationale)
2. Or: merge them. The conceptual distinction is elegant but if users consistently use `observe` for everything, the two-tool split adds confusion without value
3. Add a migration path: auto-promote long-lived, high-value observations to concepts

---

## Opportunities

### OPPORTUNITY 1: Auto-observation on significant events
When the audit detects a new circular dependency that didn't exist before, auto-save an observation: "New circular dep between X and Y introduced in this session." This builds the memory without requiring manual save calls.

### OPPORTUNITY 2: Observation-informed search boosting
If an observation says "Pi Agent is the most important recent work," then `codrag_search` queries about "agent" should boost Pi-related files. The `working_dir` injection is a step in this direction, but it could be more aggressive — observations should influence the semantic search ranking globally, not just when `working_dir` happens to match.

### OPPORTUNITY 3: "What do I need to know?" summary
A `codrag_observe(action="summary")` that returns a 3-sentence brief: "Key active decisions: X, Y, Z. Known bugs: A. Active assumptions: B." This would be the ideal cross-session orientation tool — more actionable than reading all 10+ observations.
