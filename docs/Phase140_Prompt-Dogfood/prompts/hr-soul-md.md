# HR — SOUL.md per role

**File:** `src/prep/agents/hr/prompts.py:79-126` (render at 79, SYSTEM at 120)
**Symbols:** `SOUL_MD_SYSTEM`, `render_soul_md_prompt`
**Invoked by:** HR Staffing Agent — once per role
**Pipeline stage:** agent (HR)
**Output schema:** markdown for per-role SOUL.md (identity / values / collaboration style)
**Status:** baseline

## Purpose
Generates a per-role SOUL.md — the "identity" file that complements AGENTS.md. AGENTS.md tells the agent *what to do*; SOUL.md tells it *how to be*.

## Grounding (inputs)
- Role definition (from `role.yaml`)
- Optional team / org context
- Codebase identity (from atlas)

## Output schema
Markdown. Sections typically: identity, values, collaboration patterns, voice/tone.

## Known issues / hypotheses
- **Overlap with AGENTS.md**: where does identity end and instruction begin? Outputs may duplicate content between the two files. Diff AGENTS.md vs SOUL.md from the same role to see.
- **Personality-vs-personality-template**: SOUL.md prompts that ask for "personality" tend to drift toward corporate self-help language ("strives for excellence"). Hypothesis: more constrained framings ("3 specific working patterns this role exhibits") yield better outputs.
- **Audience confusion**: SOUL.md is read by the agent, not the human. Writing style should be second-person addressed to the agent, not third-person describing it. Verify.

## Snapshot 2026-05-17
- Prompt source SHA: `bb3512c0976a`
- Outputs captured: TBD (capture for at least 3 roles)

## Iterations

_(none yet)_

## Open questions
- Should SOUL.md be merged into AGENTS.md, or kept distinct for a clear "instruction vs identity" split?
- How does an agent actually use SOUL.md content at inference time?

## Cross-references
- Sibling: [hr-agents-md](./hr-agents-md.md), [hr-auto-roles](./hr-auto-roles.md)
