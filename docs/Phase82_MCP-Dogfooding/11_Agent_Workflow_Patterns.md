# 11 — Agent Workflow Patterns

How agents actually use (and should use) CoDRAG tools in practice. Based on observed patterns during dogfooding and extrapolated from common coding workflows.

---

## Observed Patterns

### Pattern 1: "Orient Then Dive" (Most Common)

```
Agent receives task → codrag() for orientation → codrag_search() for specifics → Read file → Edit file
```

This is the expected happy path and it works. The `codrag` ambient call gives module context, then targeted search finds the right files. The gap is between search and edit — there's no "impact check before edit" step, and most agents skip it.

**Improvement:** The `codrag_search` response should include a micro-impact note for returned files: "This file has 23 dependents — consider running codrag_impact before modifying."

### Pattern 2: "Grep Fallback" (Too Common)

```
Agent receives task → codrag_search() → results not useful → grep/Glob instead → Read file → Edit file
```

Agents fall back to grep when:
- The semantic query doesn't match (intent mismatch, wrong terms)
- Symbol search returns only paths (no code context to evaluate)
- Results are from docs when the agent wanted code

**Improvement:** When search confidence is low, proactively suggest grep patterns: "For exact matches, try: `grep -r 'handle_tools' src/`". Better yet, do it automatically as a fallback layer within `codrag_search`.

### Pattern 3: "Audit Then Ignore" (Wasteful)

```
Agent calls codrag_audit() → gets 100 findings → overwhelmed → ignores audit → does the task without health context
```

The audit returns too much. An agent working on MCP tools doesn't care about UI bottlenecks. Without scoping or prioritization, the audit is noise.

**Improvement:** Default audit should return top 5 findings relevant to the agent's working area. "You're working in src/codrag/mcp/ — here are the 3 audit findings that affect you."

### Pattern 4: "Impact After The Fact" (Risky)

```
Agent edits file → realizes it's a hub → calls codrag_impact() → discovers 23 dependents → too late, already committed
```

Impact analysis is most valuable *before* editing, but agents only think to call it *after* encountering a problem.

**Improvement:** The `codrag` ambient response should flag hub files in the working area: "hub files near you: server.py (23 deps), orchestrator.py (45 deps) — run codrag_impact before modifying."

### Pattern 5: "Single-Tool Session" (Missed Opportunity)

```
Agent calls codrag() once → never calls another CoDRAG tool → uses grep/Read for everything
```

Many agents call `codrag` at task start (as AGENTS.md instructs) but never return. They don't know about `codrag_search`, `codrag_impact`, or `codrag_audit`, or don't see when they'd be useful.

**Improvement:** The `codrag` response should include a "What else I can do" section: "Available: codrag_search (find code by meaning), codrag_impact (check blast radius), codrag_audit (health check)."

---

## Anti-Patterns

### Anti-Pattern 1: "Blind Trust"
Agent uses CoDRAG search result as authoritative without verifying. Especially dangerous when index is stale or search confidence is moderate.

**Mitigation:** Freshness and confidence signals in responses. "This result is from an index built 4 hours ago — 12 files have changed since then."

### Anti-Pattern 2: "Tool Cascade"
Agent calls `codrag()` → `codrag_search()` → `codrag_impact()` → `codrag_audit()` → `codrag_observe()` for every task, burning 15K+ tokens on context before writing a single line of code.

**Mitigation:** Progressive disclosure. The ambient `codrag()` call should provide enough context for simple tasks. Only drill down when the task is complex or touches hub files.

### Anti-Pattern 3: "Observation Spam"
Agent saves an observation for every minor finding: "File X uses snake_case", "File Y has 3 functions." This pollutes the observation store with noise.

**Mitigation:** Observation quality guidelines in the tool description. "Save observations that a future agent would need — decisions, surprises, non-obvious constraints. Don't save things derivable from code."

### Anti-Pattern 4: "Concept Paralysis"
Agent reads concepts and becomes afraid to make changes that might conflict with stated design principles. "The concept says 'agents/ → services/ → core/, never reverse' but my fix requires a backward import."

**Mitigation:** Concepts should note their flexibility: "Hard constraint (architectural invariant)" vs "Soft guidance (preferred pattern, acceptable exceptions exist)."

---

## Recommended Workflow Templates

### Template 1: Bug Fix

```
1. codrag() — orient (if not already in session)
2. codrag_search("the bug symptom or error message") — find relevant code
3. Read the found file(s)
4. codrag_impact(file_path) — check blast radius IF file has many dependents
5. Fix the bug
6. codrag_observe(action="save", category="bug", content="...") — IF the bug was non-obvious
```

### Template 2: New Feature

```
1. codrag() — orient
2. codrag_concepts(query="relevant domain") — understand design rationale
3. codrag_search("similar existing feature") — find patterns to follow
4. codrag_impact(file_path) — for each file you'll modify
5. Implement
6. codrag_audit(scope="changed files") — check for introduced issues
7. codrag_observe(action="save", category="decision") — record non-obvious choices
```

### Template 3: Refactoring

```
1. codrag_audit(category="architecture") — find what needs refactoring
2. codrag_impact(file_path) — blast radius for each target
3. codrag_concepts(query="architecture") — understand constraints
4. Plan the refactoring (ordering by dependency depth)
5. Implement in dependency order
6. codrag_audit(action="verify") — confirm findings are resolved
```

### Template 4: Code Review

```
1. codrag_impact(file_path) — for each changed file in the PR
2. codrag_audit(scope="changed files") — health check on changes
3. codrag_concepts(query="relevant patterns") — check concept alignment
4. codrag_observe(action="get", file_path="changed file") — check for known issues
5. Review with full context
```

### Template 5: Onboarding (New to Project)

```
1. codrag() — structural overview
2. codrag_concepts() — all active concepts
3. codrag_observe() — recent decisions and known issues
4. codrag_audit(action="scan") — current health
5. codrag_search("the specific area you'll be working in")
```

---

## The "Ambient Intelligence" Vision

The ultimate workflow isn't a sequence of tool calls — it's the tools working invisibly. Imagine:

1. Agent opens a file → CoDRAG automatically injects:
   - Module context for this file's module
   - Impact score ("this is a hub file, be careful")
   - Relevant concepts ("this module follows the adapter pattern")
   - Recent observations ("known bug: race condition under high load")

2. Agent starts typing → CoDRAG flags potential issues:
   - "You're importing from agents/ in a core/ file — this violates the dependency direction concept"
   - "This function name conflicts with an existing function in another module"

3. Agent finishes editing → CoDRAG summarizes impact:
   - "Your changes affect 3 direct dependents and 12 transitive dependents"
   - "New circular dependency introduced between X and Y"
   - "No test coverage for the new function"

This is the IDE integration dream. The MCP tools are the building blocks, but the real value is when they compose into seamless ambient intelligence.

---

## Measuring Success

How do we know if CoDRAG tools are actually helping agents? Proposed metrics:

| Metric | What it measures | How to collect |
|--------|-----------------|----------------|
| **Tool adoption rate** | % of sessions that use CoDRAG tools beyond initial `codrag()` | Log tool calls per session |
| **Grep fallback rate** | How often agents fall back to grep after a CoDRAG search | Detect grep calls following search calls |
| **Impact-before-edit rate** | How often agents check impact before modifying hub files | Correlate impact calls with subsequent edits |
| **Observation persistence** | How often saved observations are retrieved in future sessions | Track observation read/write ratios |
| **Task completion time** | Do CoDRAG-using agents finish tasks faster? | Compare task duration with and without CoDRAG calls |
| **Rework rate** | Do CoDRAG-using agents need fewer revision cycles? | Track commits/reverts after CoDRAG-informed vs uninformed changes |

None of these require external analytics — they could all be tracked in the daemon's own logs and surfaced through the audit or dashboard.
