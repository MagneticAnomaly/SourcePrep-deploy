# HR — Auto-roles

**File:** `src/prep/agents/hr/prompts.py:185-268` (render at 185, SYSTEM at 267)
**Symbols:** `AUTO_ROLES_SYSTEM`, `render_auto_roles_prompt`
**Invoked by:** HR Staffing Agent — bootstrap when no `role.yaml` exists
**Pipeline stage:** agent (HR)
**Output schema:** structured JSON list of inferred AI-agent roles (with name, responsibility, scope, MCP tools)
**Status:** baseline

## Purpose
Auto-infers a starter set of AI-agent roles from codebase stats + audit findings. The bootstrap that produces the initial `role.yaml` so HR Staffing has something to work from.

## Grounding (inputs)
- Codebase atlas (segments, hub files)
- Audit findings (cross-cutting concerns)
- Module / cluster summaries
- Language and framework distribution

## Output schema
JSON list. Each role: `{name, responsibility, scope (file globs / segments), mcp_tools[]}`.

## Known issues / hypotheses
- **Role inflation**: the easy failure mode is "produce 12 roles for a 50-file project." Outputs should be parsimonious. Hypothesis: add an explicit "maximum N roles" cap derived from project size.
- **Role-name vocabulary**: roles like "Backend Engineer" / "Frontend Engineer" are generic and don't add signal. Domain-specific names ("Concept-Pipeline Maintainer", "MCP Tool Owner") are more useful. Verify outputs use codebase-specific names.
- **Tool assignment**: which MCP tools does each role get? Default-everyone-gets-all is wasteful in role-scoped context. Hypothesis: outputs frequently assign all tools to every role.

## Snapshot 2026-05-17
- Prompt source SHA: `bb3512c0976a`
- Outputs captured: TBD (3 repos minimum)

## Iterations

### 2026-05-19: B5 — structural review + corrects page schema description

**Type:** analysis-only (no PowerMate output captured; structural review of prompt + audit_findings integration)

**Read materials:**
- `render_auto_roles_prompt` + `AUTO_ROLES_SYSTEM` (`agents/hr/prompts.py:185-268`).

**Correction to existing page (line 20) — output schema is incorrect in the stub.** Page says output is `{name, responsibility, scope (file globs / segments), mcp_tools[]}` — 4 fields. Actual prompt (line 248-256) asks for 5 different fields:

```
1. slug — lowercase_underscore identifier
2. display_name — Human-readable role title
3. justification — Why this role is needed (cite specific modules/domains and any audit findings that this role would address)
4. primary_modules — Which modules this role owns
5. domain_focus — Which domain tags this role covers
```

The page hypothesis #3 ("Tool assignment: which MCP tools does each role get? Default-everyone-gets-all is wasteful") is **moot** — auto-roles does not assign MCP tools at all. Tool assignment lives elsewhere in the HR pipeline (likely a deterministic post-process in `engine.py`, or in `hr-agents-md` which inlines the tool table).

Recommend updating the page's `## Output schema` and `## Known issues` sections to match reality.

**Finding #1 — size-derived role-count heuristic is in the prompt (addresses page hypothesis #1).** Lines 259-262:

```
- Small codebases (<30 files): 2-3 generalist roles
- Medium codebases (30-100 files): 3-4 roles
- Large codebases (>100 files): 4-6 specialized roles
- Monorepos: Consider domain-owner roles per workspace
```

This is the role-inflation guard the page's hypothesis #1 calls for. Good design. Caveat: the bands are unrelated to the prompt's actual `file_count` input — the model has to look at the count and decide which band applies. A more enforceable version would phrase the band as a hard constraint:

```diff
+CONSTRAINT — emit role count based on file_count above:
+  if file_count < 30:   emit 2-3 roles
+  if file_count < 100:  emit 3-4 roles
+  else:                 emit 4-6 roles
+Emitting outside this range is a failure mode.
```

The hard-constraint phrasing makes the rule a check the model can apply, not a vibe to honor.

**Finding #2 — audit_findings integration is the strongest grounding hook in the prompt.** Lines 206-227 (`audit_section`) inject up to 20 structural audit findings into the prompt, each with `[SEVERITY] title (category): description — files: ...`. The prompt then instructs (line 252):

> 3. **justification** — Why this role is needed (cite specific modules/domains and any audit findings that this role would address)

And (lines 263-264):

> - If audit findings show coupling hotspots or hub concentration in a module, that module needs a dedicated steward role
> - If audit findings show concept violations or architectural drift, propose a role responsible for maintaining architectural intent

This is excellent — roles are not just inferred from "what files exist" but from "what structural problems exist." A role exists because it resolves a real failure, not just because a domain exists. Per grounding §9 (adversarial framing), this is the right shape: the prompt asks the model to anchor recommendations in concrete observed problems, not in vibes.

**Finding #3 — `display_name` vocabulary unconstrained.** Page hypothesis #2 ("Role-name vocabulary: roles like 'Backend Engineer' / 'Frontend Engineer' are generic and don't add signal. Domain-specific names like 'Concept-Pipeline Maintainer', 'MCP Tool Owner' are more useful.") is valid — the prompt does not constrain `display_name`. Worth adding a NAMING RULES clause similar to `batch-cluster`'s:

```diff
+display_name NAMING RULES:
+  - Good: "Concept Pipeline Maintainer", "MCP Tool Owner", "Brightness Subsystem Steward"
+  - Bad: "Backend Engineer", "Senior Architect", "Module Owner"
+  - Use codebase-specific vocabulary; reference actual subsystems/modules.
+  - Never use generic role titles that could apply to any project.
```

**Finding #4 — `AUTO_ROLES_SYSTEM` is minimal.** Single sentence: "You are an expert at analyzing codebases and designing optimal AI agent team structures. You output ONLY valid JSON — a JSON array of role objects. No markdown, no explanations outside the JSON." Per grounding §6, persona-only system prompts are weak signal. The substantive guidance lives in the user prompt (which is fine). No iteration needed on the system.

**Finding #5 — no anti-padding clause.** The prompt has an upper bound (2-6 roles) but no "fewer is better" or "empty is acceptable" stance. Compare `SYNTH_SYSTEM_PROMPT`'s "EMPTY OUTPUT IS ACCEPTABLE — PADDING IS A FAILURE MODE" — a single role would be a perfectly reasonable output for a 5-file codebase. The current prompt would push the model to emit 2-3 regardless.

**Verdict:** `analysis (no edit shipped this iteration).` Four deferred actions:
1. **Update page stub** to reflect actual schema (5 fields, no mcp_tools).
2. **Tighten role-count heuristic** to hard-constraint phrasing.
3. **Add display_name NAMING RULES** to prevent generic-vocabulary drift.
4. **Add anti-padding clause** to allow single-role outputs for tiny projects.

**Capture follow-up:** PowerMate (single-segment) would produce 2-3 auto-roles. SourcePrep self (29 modules in scope per atlas) would produce 4-6. Both should be captured before any of the above edits ship — diff would show whether the role-count distribution actually matches the heuristic.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (adversarial: roles-from-audit-findings is a strong anti-vibe pattern).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §11 (instruction tone: "If audit findings show..." conditional guidance is more enforceable than "consider audit findings").

**Cross-references:** [`hr-agents-md.md`](./hr-agents-md.md) (downstream consumer of auto-roles output), [`hr-soul-md.md`](./hr-soul-md.md) (also downstream).

## Open questions
- What's the right role-count distribution by project size? (1 role for tiny, 3-5 for medium, ~8 for large?)
- Should role responsibilities be derived from `prep_audit` action items rather than free-form inference?

## Cross-references
- Sibling: [hr-agents-md](./hr-agents-md.md), [hr-soul-md](./hr-soul-md.md)
