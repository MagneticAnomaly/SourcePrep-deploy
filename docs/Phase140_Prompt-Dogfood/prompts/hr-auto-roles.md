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

_(none yet)_

## Open questions
- What's the right role-count distribution by project size? (1 role for tiny, 3-5 for medium, ~8 for large?)
- Should role responsibilities be derived from `prep_audit` action items rather than free-form inference?

## Cross-references
- Sibling: [hr-agents-md](./hr-agents-md.md), [hr-soul-md](./hr-soul-md.md)
