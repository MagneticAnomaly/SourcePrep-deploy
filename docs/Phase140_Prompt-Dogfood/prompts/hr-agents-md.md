# HR — AGENTS.md per role

**File:** `src/prep/agents/hr/prompts.py:11-77` (render at 11, SYSTEM at 72)
**Symbols:** `AGENTS_MD_SYSTEM`, `render_agents_md_prompt`
**Invoked by:** HR Staffing Agent — once per role
**Pipeline stage:** agent (HR)
**Output schema:** markdown for a per-role AGENTS.md instruction file (with managed markers preserving user edits)
**Status:** baseline

## Purpose
Generates an AGENTS.md per role (e.g., backend, frontend, security) tailored to that role's responsibilities. Uses managed markers (`<!-- prep-managed-start -->`) so user additions outside the block survive regeneration.

## Grounding (inputs)
- Role definition (from `role.yaml`)
- Codebase atlas (relevant segments)
- MCP tool list
- Prior AGENTS.md content (so managed-block edits don't clobber user content)

## Output schema
Markdown with explicit managed block. Sections typically: role identity, MCP tool usage, do/don't rules.

## Known issues / hypotheses
- **Managed-block fragility**: the output must produce *exactly* the marker syntax for splicing. Hypothesis: model drifts on marker text (extra whitespace, swapped chars), breaking the splice. Verify outputs contain markers literally.
- **Role-specific tailoring**: how much does per-role output actually differ? If a frontend AGENTS.md reads ~95% like a backend one, the prompt isn't using the role differentiator. Diff outputs across roles to check.
- **Tool-list staleness**: MCP tool list is grounded in. If the prompt inlines tool descriptions, they go stale when tools change. Better: reference a canonical tool table.

## Snapshot 2026-05-17
- Prompt source SHA: `bb3512c0976a`
- Outputs captured: TBD (capture for at least 3 roles)

## Iterations

_(none yet)_

## Open questions
- Should the prompt accept the prior AGENTS.md content verbatim and produce a *diff* instead of a full document?
- Are the do/don't rules supposed to be role-specific or project-wide?

## Cross-references
- Sibling: [hr-soul-md](./hr-soul-md.md), [hr-auto-roles](./hr-auto-roles.md), [rules-agents-md](./rules-agents-md.md)
- AGENTS.md content shipped to client projects ≠ this prompt — see [rules-agents-md](./rules-agents-md.md) for that
