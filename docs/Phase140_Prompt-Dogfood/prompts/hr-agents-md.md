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

### 2026-05-19: B4 — structural review (no PowerMate output; corrects page hypothesis #1)

**Type:** analysis-only (structural review of prompt + caller; output capture deferred — PowerMate has not been HR-staffed)

**Read materials:**
- `render_agents_md_prompt` + `AGENTS_MD_SYSTEM` (`agents/hr/prompts.py:11-77`).
- Caller `engine.py:322-330` (`agents_prompt = render_agents_md_prompt(...); agents_md, agents_tokens = llm_fn(agents_prompt, system=AGENTS_MD_SYSTEM)`).
- Wiring check: `grep -rn 'prep-managed-start\|hr-managed-start\|managed-start' src/prep/agents/hr/` returns ZERO hits.

**Correction to existing hypothesis (page line 23) — there is NO managed-block marker logic in HR.** The page lists "Managed-block fragility" as a known issue, citing `<!-- prep-managed-start -->` marker syntax. That marker pattern exists in `src/prep/core/rules_generator.py` (the `rules-agents-md` site that writes the project-root AGENTS.md), but it does **not** exist in `src/prep/agents/hr/`. HR-generated per-role AGENTS.md files are written as standalone artifacts (one per role) into a role-specific directory; there is no splicing into a pre-existing document.

What HR *does* have is an "edit-preservation" mechanism: when `previous_content` is non-empty, the prompt prepends an "IMPORTANT — PRESERVE EDITS" block (lines 30-42) instructing the model to "preserve and incorporate ALL existing content. Treat any human-authored additions as authoritative. Expand and refine them with updated codebase context, but NEVER remove or ignore user additions." This is the actual feature the page meant to describe.

Recommend updating the page's known-issues section to replace "Managed-block fragility" with **"Edit-preservation fidelity — does the model actually preserve user content verbatim, or does it reword it 'to integrate with updated context'?"** The latter is the real risk.

**Finding #1 — edit-preservation instruction is strong but inherently fragile.** The instruction (line 33-37) says "NEVER remove or ignore user additions" — but does not say "NEVER reword user additions." A model that "integrates with updated context" by rephrasing a user-authored guardrail (e.g., user wrote "do not modify auth_*.py without security review", model rewrites as "be cautious with authentication files") is technically preserving the spirit but losing the literal text. The user wrote those exact words for a reason.

Stricter framing:

```diff
-**You MUST preserve and incorporate ALL existing content.** Treat any
-human-authored additions as authoritative. Expand and refine them with
-updated codebase context, but NEVER remove or ignore user additions.
+**You MUST preserve ALL existing content VERBATIM.** Treat any
+human-authored additions as authoritative and LITERAL — quote them
+exactly, do not reword. You may APPEND new sections to extend the
+document, but you may NOT modify existing text. If a user-authored
+statement and your generated content would conflict, prefer the
+user's text and omit the conflict from your additions.
```

**Finding #2 — tool list is hardcoded into the prompt template.** Lines 64-66:

```
- `prep(role="{role_slug}")` for scoped structural overview
- `prep_search(query, role="{role_slug}")` for code search
- `prep_impact(file)` before modifying files
```

This is the *teaching* the model is asked to deliver. If we add a tool (e.g., `prep_concepts`, `prep_observe`, `prep_audit`), it doesn't appear in HR-generated AGENTS.md until this template is updated. The other site (`rules-agents-md`) recently centralized the MCP tool list (per commit `42767327 refactor(ui): single source of truth for MCP tool list + IDE snippets`); HR didn't get that treatment.

Worth porting: define the MCP tool list once (preferably in `mcp_tools.py` where the tool schemas live), have both `rules_generator.py` and `agents/hr/prompts.py` import it. Out of scope for prompt-copy iteration (this is module refactor), but flag it.

**Finding #3 — `~1500 tokens` target is set in the prompt, not the LLM call.** Prompt instruction: "Write a markdown document (~1500 tokens) that includes...". This is asking the *model* to estimate token count, which it cannot accurately do. Grounding §1 (Claude 4.7 calibrates response length to task complexity) suggests the prompt should specify length in **sections** or **paragraphs** rather than tokens, OR the `llm_fn` call should pass `max_tokens=1500` (the actual budget). Check `engine.py:330` — `llm_fn(agents_prompt, system=AGENTS_MD_SYSTEM)` — no `max_tokens` override, so the model uses its default. Either tighten the prompt-side or wire the LLM-side cap.

**Finding #4 — `Boundaries — What this role should NOT do` is a negatively-scoped requirement.** Per grounding §11 (negative instructions are harder for LLMs to follow than positive instructions), "should NOT" requirements tend to produce reactive lists ("don't modify X, don't access Y, don't merge Z") that read as paranoid. A positively-framed alternative: "**Lane integrity — explicit out-of-scope examples with referrals** (e.g., 'Security middleware changes go to the security role; cross-link here')." More actionable, less defensive.

**Verdict:** `analysis (no edit shipped this iteration).` Five deferred actions, none blocking:
1. **Update page hypothesis** to replace incorrect "managed-block" with "edit-preservation fidelity."
2. **Tighten edit-preservation** to "VERBATIM" with append-only extension semantics.
3. **Centralize MCP tool list** (cross-cutting code refactor — out of Phase 140 scope, flag for follow-up).
4. **Wire `max_tokens=1500`** at the call site OR replace token-count with paragraph-count in the prompt.
5. **Reframe `Boundaries`** as positive lane-integrity with referrals.

**Capture follow-up:** for output-driven verdicts on findings #1, #3, #4, need to actually run HR on at least one repo and capture 2-3 role outputs. PowerMate is single-segment — likely only generates 1-2 roles (developer + maintainer). SourcePrep itself would give a richer test (5-7 roles plausibly).

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (Claude length calibration — token-count instructions in prompts are weak vs API-level `max_tokens`).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §11 (tone / aggressive instruction: published evidence is mixed; negatively-scoped requirements like "must NOT" are a known weak spot worth measuring rather than asserting).

**Cross-references:** [`hr-soul-md.md`](./hr-soul-md.md), [`hr-auto-roles.md`](./hr-auto-roles.md), [`rules-agents-md.md`](./rules-agents-md.md) (different AGENTS.md — the project-root one with managed markers; HR ones are per-role and have no markers).

## Open questions
- Should the prompt accept the prior AGENTS.md content verbatim and produce a *diff* instead of a full document?
- Are the do/don't rules supposed to be role-specific or project-wide?

## Cross-references
- Sibling: [hr-soul-md](./hr-soul-md.md), [hr-auto-roles](./hr-auto-roles.md), [rules-agents-md](./rules-agents-md.md)
- AGENTS.md content shipped to client projects ≠ this prompt — see [rules-agents-md](./rules-agents-md.md) for that
