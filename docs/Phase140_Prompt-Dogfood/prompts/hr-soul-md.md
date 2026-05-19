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

### 2026-05-19: B4 — structural review (no PowerMate output; corrects page hypothesis #3)

**Type:** analysis-only (structural review of prompt + caller; output capture deferred)

**Read materials:**
- `render_soul_md_prompt` + `SOUL_MD_SYSTEM` (`agents/hr/prompts.py:79-126`).
- Caller `engine.py:335-341` (same `llm_fn(..., system=SOUL_MD_SYSTEM)` pattern as `hr-agents-md`).

**Correction to existing hypothesis (page line 24) — the prompt DOES use first-person voice.** The page says: "Audience confusion: SOUL.md is read by the agent, not the human. Writing style should be second-person addressed to the agent, not third-person describing it." But line 111 of the prompt requires:

> 1. **Identity Statement** — "I am the {role_name}. My purpose is..." (one sentence)

That's first-person, voiced *from* the agent's perspective — exactly correct for an identity document the agent reads to internalize who it is. The page's hypothesis confuses first-person and second-person voice (second-person would be "You are the X. Your purpose is..." — like the API system prompt convention). The actual prompt uses the right voice (first-person from the agent's POV).

Update the page hypothesis to: **"Voice consistency across SOUL.md sections — identity statement is first-person ('I am'), but other sections (Communication Style, Guardrails, Collaboration) have no voice constraint and may drift to third-person ('the role values...', 'this role must not...') breaking the identity frame."** That's the real risk worth checking when output is captured.

**Finding #1 — `~600 tokens` target shares the `hr-agents-md` finding #3.** Same issue: token count is asked of the model, not enforced at the call site. See sibling iteration.

**Finding #2 — `Core Values — 3-5 values derived from what this role protects/optimizes in this codebase`** is the prompt's strongest grounding hook. Compare to the open-ended SOUL.md persona prompts that produce "strives for excellence" / "values teamwork" output the page worries about. This prompt frames values as derived from *what the role protects* in the codebase — making values concrete and falsifiable. E.g., a CTO of a brightness-control utility might value "graceful degradation across hardware quirks" because that's what the codebase actually does. Without output to measure, this is structural praise — but it's worth keeping as a baseline good pattern.

**Finding #3 — `Guardrails` is positive but binary.** "2-3 things this role must never do" — same negative-scoping concern as `hr-agents-md` Finding #4. Could be reframed as positive lane-integrity. But the "2-3" cap is good — bounded guardrails are more memorable than an exhaustive list.

**Finding #4 — `SOUL.md` purpose is itself underspecified at the meta layer.** Page open-question #2 ("How does an agent actually use SOUL.md content at inference time?") is the load-bearing question. If no part of the runtime actually loads SOUL.md into agent context (e.g., it's not auto-included in `prep(role=X)` ambient context, not referenced by any system prompt), then the file is ceremonial and the prompt quality doesn't matter to behavior.

Quick check on the wiring: looking at `engine.py:341` — `soul_md, soul_tokens = llm_fn(soul_prompt, system=SOUL_MD_SYSTEM)`. So SOUL.md is generated. But where is it loaded back into an agent's context at run-time? Worth tracing — if the answer is "nowhere", then this prompt's audit is moot.

That's a structural question for engineering, not a prompt-copy iteration.

**Finding #5 — overlap with `hr-agents-md` (page's known-issue #1).** Both produce per-role markdown. AGENTS.md is "what to do", SOUL.md is "how to be." But without output capture, can't measure overlap. The page's hypothesis is plausible — when a single LLM generates both files for the same role with the same input atlas, drift between them is the natural failure mode. A side-by-side diff after capture would be the test.

**Verdict:** `analysis (no edit shipped this iteration).` Three updates:
1. **Correct page hypothesis #3** — the first-person voice is correct, the real risk is per-section voice drift.
2. **Track Finding #4** — verify whether SOUL.md is actually consumed at runtime. If not, this prompt is ceremonial and the audit is unnecessary.
3. **Capture before next iteration** — like `hr-agents-md`, need at least 2-3 roles' SOUL.md outputs to do output-driven verdicts.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §6 (Persona prompting — published evidence is genuinely mixed; SOUL.md is exactly the kind of artifact this body of work questions the value of. Worth a structural ablation: does removing SOUL.md affect agent behavior on any measurable task? If not, this prompt can be retired).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §12 (prompt versioning: SOUL.md / AGENTS.md cycle would benefit from canary/diff tooling — currently regenerates wholesale on staffing changes).

**Cross-references:** [`hr-agents-md.md`](./hr-agents-md.md) (sibling; shared engine.py:322-341 invocation, same `llm_fn` plumbing), [`hr-auto-roles.md`](./hr-auto-roles.md) (sibling; the role-inference prompt that decides whether roles exist at all).

## Open questions
- Should SOUL.md be merged into AGENTS.md, or kept distinct for a clear "instruction vs identity" split?
- How does an agent actually use SOUL.md content at inference time?

## Cross-references
- Sibling: [hr-agents-md](./hr-agents-md.md), [hr-auto-roles](./hr-auto-roles.md)
