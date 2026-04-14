# R4 — Universal Client API Design

**Goal:** Generalize `codrag(role="rolename")` from Paperclip-specific to client-agnostic.
**Time budget:** 1 week
**Decision at end:** v2 MCP spec for the primary `codrag()` tool.

## Core question

Our `codrag(role="rolename")` call works because Paperclip passes a known role slug. **What is the minimum, elegant API signature that works for every MCP client — Claude Code, Cursor, Windsurf, OpenClaw, Paperclip, and clients we haven't seen yet?**

Clients don't all know their role. Some just have a user task. Some have a file. Some have both. The universal API must handle all entry points without becoming a swiss-army knife.

## Hypothesis

**H1:** Three parameters are sufficient: `task` (what the user is doing), `role` (optional; inferred if absent), `budget` (optional; defaulted from R2).

**H2:** Role inference from task text is accurate enough (≥80%) that most clients don't need to pass role explicitly. Paperclip still can; others don't have to.

**H3:** Everything beyond those three parameters is either (a) encodable in `task` as natural language, or (b) belongs to a separate tool (e.g., `codrag_impact` for specific file analysis).

## Literature check

- **MCP spec** — tool signatures stay simple; the MCP ecosystem rewards clear, minimal APIs.
- **Anthropic Claude Agent SDK** — tool-use patterns favor few parameters with rich return values.
- **Agentic RAG survey** — single-entry-point retrieval with internal routing is a common pattern.
- **Our own `codrag_search`** — auto-classifies intent from natural language. Proves clients *can* pass free text.

## Current state (baseline)

```
codrag(project_id: str) -> AtlasContext
codrag(project_id: str, working_dir: str) -> ScopedAtlasContext
```

Paperclip uses a slightly different path (sets `role` internally). No universal `role` or `task` parameter exposed.

## Proposed v2

```
codrag(
  task: Optional[str] = None,     # natural language task description
  role: Optional[str] = None,     # explicit role hint (optional)
  file: Optional[str] = None,     # current working file (optional)
  budget: Optional[str] = "moderate",  # minimal|moderate|rich; default from R2
  project_id: str = ...,          # routing, already required
) -> ScopedContext
```

**Server-side behavior:**
1. If `role` provided → use directly.
2. Else if `task` provided → infer role from task text (via existing intent classifier + role vectors).
3. Else if `file` provided → infer role from file's owning modules (via role_resolver).
4. Else → return the generic atlas (legacy behavior, preserves back-compat).

**Return shape:** a flat `ScopedContext` object with sections aligned to the R1 layout standard:
```
ScopedContext {
  critical_start: { antibodies, forbidden_tools, task_framing },
  knowledge:      { atlas_slice, concepts, code_chunks },
  critical_end:   { repeat_key_constraints, next_action_hints },
  metadata:       { inferred_role, budget_used, concepts_version, ... }
}
```

The host client concatenates the three sections in order (or formats as preferred). Metadata is for debugging and client-side caching.

## Experiment

Unlike R1–R3, this is primarily a **design** sub-phase, but validated with measurement.

**Design phase (2 days):**
- Draft the v2 spec.
- Map each existing `codrag` call site (Paperclip, Claude Code server mode, direct mode, CLI) to v2.
- Identify backward-compatibility shims needed.

**Validation phase (3 days):**
- Role inference test: 50 natural-language task strings with human-labeled expected role. Measure inference accuracy.
- Round-trip test: for each existing call pattern, confirm v2 gives equivalent or better results.
- Client integration test: dry-run the API from a Claude Code session, a Cursor session, an OpenClaw agent. Note friction.

**Measure:**
- Inference accuracy (target ≥80%).
- API surface size (lines of schema).
- Client-side integration effort (questions that come up, confusion points).

## Decisions

**Path 1 — H1 holds:** 3 parameters sufficient. Ship v2. Deprecate role-specific paths gradually.

**Path 2 — inference too weak:** role must be explicitly passed. Make `role` effectively required for role-scoped responses; fall back to generic atlas when absent. Still simpler than current API.

**Path 3 — more parameters needed:** if clients can't work with 3 parameters, identify the missing one(s). Watch for over-scoping — most of the time the answer is "put it in `task`."

## Simplicity audit — continuous

Every added parameter to `codrag()` should pass this bar:
- Can this be inferred from `task` text?
- Can this be a separate tool instead?
- Does every client need this, or just one?

If any answer is "no, yes, or one," the parameter doesn't belong in the core `codrag()` signature.

**Counterexamples (things that would bloat the API):**
- `layout=sandwich|flat|sorted` → internal detail from R1, don't expose.
- `concept_filter=["security", "auth"]` → encode in `task` ("auth-related security review").
- `include_observations=true` → always include relevant ones; agent filters.
- `format=markdown|json` → host preference; handle at transport layer, not tool signature.

## Backward compatibility

- Existing `codrag(project_id, working_dir)` still works. `working_dir` maps to `file`.
- Paperclip's role-slug path still works. `role` is accepted explicitly.
- The return type stays a superset of today's — clients reading the old structure see nothing new.

## Dependencies

- R1 layout standard (to define the `ScopedContext` structure).
- R2 budget defaults (for the `budget` parameter).
- R3 role-projection outcome — **if Pattern 4 (kill role projection)**, then `role` parameter becomes a thin hint for clients that still want it, but server-side treatment changes. v2 spec should anticipate this branch.

## Success criteria

- ✅ v2 spec is 3–5 parameters, fully backward-compatible.
- ✅ Role inference validated at ≥80% accuracy.
- ✅ At least 2 non-Paperclip clients (Claude Code, one other) use v2 in testing.
- ✅ Documentation migration path from legacy calls to v2.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R4_results.md`:
- v2 MCP spec.
- Role inference accuracy data.
- Migration guide from v1 to v2.
- Deprecation schedule.
- Explicit list of parameters we chose NOT to add, with rationale.

## Connection to "simplicity" principle

R4 is the sub-phase most at risk of scope creep. It's the API. Everyone wants to add their favorite parameter to the API.

**The discipline:** every v2 spec draft is followed by a 1-hour simplification pass where we ask *"what can we remove?"* We should ship the simplest spec that the measurements allow, not the richest one that the measurements tolerate.

The best outcome is a v2 spec smaller than v1.
