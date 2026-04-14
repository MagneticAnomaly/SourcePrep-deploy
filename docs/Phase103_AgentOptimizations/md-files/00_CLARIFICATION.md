# 00 — Clarification: Knowledge Honing, Not Persona Prompting

**Read this first. It corrects a framing error in earlier drafts of this phase plan.**

## The distinction that matters

There are two mechanistically different ways to "give an agent a role":

### 1. Persona-prompting (the AGENTS.md / SOUL.md convention)

The host agent is given **instructions about who to be**:
> *"You are a security engineer. You are paranoid by design. You flag risks early. You cite concepts by id."*

The mechanism is **prompt text**. The agent's knowledge doesn't change — only its instructions do. The same files, same context, same tools, but the model is steered by an identity instruction.

**Research on this is mixed to negative.** arxiv 2603.18507 ("Expert Personas Improve Alignment but Damage Accuracy"), PersonaGym, and others find that persona prompting often hurts accuracy, varies wildly by model and task, and can amplify bias. This is the evidence I cited in 05 / 06.

### 2. Knowledge-honing (CoDRAG's approach)

The agent is given **a different selection of what to read**:
- A sub-atlas weighted toward files a security reviewer would care about.
- Concepts tagged with security/auth/crypto surfaced; UI concepts demoted.
- Antibodies anchored in security modules active; others silent.
- Hub files within the role's responsibility shown first.

The mechanism is **graph-based knowledge selection + RAG**. The agent's *instructions* do not change — no "you are a security engineer" prompt. Only the **corpus of knowledge** the agent has access to is filtered through a role-weighted sub-atlas.

**Research on this is largely absent.** The knowledge-graph + agent papers (Codebase-Memory, arxiv 2603.27277; the Zep memory architecture) measure token-efficiency gains from graph-over-files retrieval, but *not* specifically the value of role-weighted vs. uniform sub-atlas selection on agent task performance.

**This is the question Phase 103's research path is meant to answer.**

## Why this distinction matters for our plan

In my earlier drafts (especially 05 and 06), I cited persona-prompting research and inferred caution for *all* role-related work. That was overreach. Persona prompting and knowledge honing are different mechanisms with different research bases. The persona evidence says *"don't wrap everything in persona prose."* It says nothing about *"don't change what knowledge you serve based on role."*

CoDRAG's thesis — **hone what the agent can see; leave what the agent does alone** — is exactly the theory that isn't covered by the persona literature. It's untested. The research sub-phases are how we test it.

## What this corrects

| Earlier framing (wrong) | Corrected framing |
|---|---|
| "Persona research shows role prompting hurts — de-emphasize roles." | "Persona research shows *prompt-based identity framing* hurts. CoDRAG does knowledge-based scope selection, which is untested separately." |
| "R3 must decide keep-or-kill role projection." | "R3 must decide whether **knowledge-honing** (role-weighted sub-atlas) improves agent performance over uniform atlas. Persona prompting is a separate axis and is expected to be a non-factor or slight negative." |
| "F1 subagent emission is persona theater." | "F1 subagent emission is a **delivery vehicle** for role-weighted knowledge. The subagent file carries the sub-atlas, concepts, and antibodies. Persona prose is optional and minimal." |
| "We are not building agents." | "We are not writing persona prompts. We *are* providing scoped knowledge. The agent already exists in the host; we change what it can see." |
| "Role spec → many emission targets is too architecture-heavy." | "Role spec → many emission targets is the correct design because each host needs a different carrier format for the same scoped knowledge. The content is the sub-atlas, not a persona." |

## What the UI already does (and why R3 is validation, not rebuilding)

As established in Phase 67 / Phase 88 and the existing dashboard:

- We compute **role vectors** — weighted combinations of domain tags, architecture layers, module coverage, and hub ownership.
- We compute **sub-atlases** per role by filtering + weighting the full atlas through the role vector.
- The dashboard exposes role selection; the sub-atlas engine runs under the hood.
- Paperclip already consumes role-scoped context via `codrag(role="rolename")`.
- The UI is built. The mechanism works. **What's missing is evidence that it makes agents measurably better.**

So R3 is **validation of an existing feature**, not design-in-the-dark. The finishing work is wiring the existing sub-atlas output into other MCP clients (via R4's universal API) and measuring the agent-quality delta.

## How this updates each research sub-phase

### R1 Context Rot & Position
No change. Position-aware layout applies equally to role-scoped and uniform context. **Both** conditions in R3 benefit from good layout.

### R2 Progressive Disclosure Minimum
No change to core design. The minimum-viable context for a role-scoped response and a uniform-atlas response may differ (role-scoped likely needs less since it's pre-filtered) — this becomes an interesting secondary finding.

### R3 Role Scoping Validation
**Meaningful reframe.** The 2×2 factorial stays, but the axes are relabeled:

- **Knowledge axis (the important one):** uniform atlas ↔ role-weighted sub-atlas
- **Persona-prompt axis (the noise check):** no persona text ↔ persona instruction ("you are...")

The cells become:
| | Uniform atlas | Role-weighted sub-atlas |
|---|---|---|
| No persona prompt | A (baseline) | **B (CoDRAG's pure thesis)** |
| Persona prompt | C (persona-only) | D (belt + suspenders, Paperclip's current default) |

**The cell that matters most is B vs A.** If B meaningfully outperforms A, CoDRAG's knowledge-honing thesis is validated. If B = A, we're in trouble — it means our sub-atlas weighting isn't delivering signal. But note: this is not the same failure as the persona research would predict. It's its own question.

The persona axis (A vs C, B vs D) lets us *confirm* that persona prompting adds little or is noise, consistent with literature. We expect C ≤ A and D ≤ B, or very close. That's fine — it supports the story that knowledge-honing is where the value is.

### R4 Universal Client API
No change. The `codrag(role="...", task="...")` call delivers role-weighted sub-atlas context regardless of whether the host also wants to wrap persona text around it. The MCP response is knowledge; persona is a client-side concern.

### R5 Concept Activation
No change. Active concepts feed into role-weighted sub-atlases by tag overlap with the role vector. Concept-to-role mapping is already part of the sub-atlas engine.

### R6 Temporal Validity
No change.

### R7 Automatic Observation
No change. Observations captured automatically enrich the concept pool, which enriches role-weighted sub-atlases.

### R8 Benchmark & Eval Harness
**Clarified.** The four conditions in R8 now map cleanly:

- **A baseline:** no CoDRAG, flat file reads.
- **B uniform CoDRAG:** full atlas, no role weighting.
- **C role-weighted CoDRAG:** sub-atlas filtered by role vector — this is the thesis under test.
- **D oracle:** hand-picked minimal context (upper bound).

If C > B meaningfully, knowledge-honing is validated. If C ≈ B, either our role vectors are poorly calibrated (fixable) or role-weighting provides no lift for code agents (unexpected, requires rethinking).

## Restating the thesis cleanly

> **CoDRAG hones what the agent can see by serving role-weighted sub-atlases over MCP. We do not prompt the agent to "be" a role; we change the knowledge available to it. The hypothesis is that selective knowledge outperforms uniform knowledge for code tasks, independent of any persona framing. Phase 103's research path is the first rigorous test of that hypothesis.**

## What this means for delivery mechanisms

The shanraisshan best-practices repo and Claude Code's native mechanisms give us excellent *delivery vehicles* for role-weighted knowledge:

- **`.claude/agents/<role>.md`** — carrier for a role-weighted sub-atlas + antibody set. The frontmatter declares tool access; the body is our scoped knowledge. Persona prose stays minimal or absent.
- **`.claude/skills/codrag/references/<role>.md`** — progressive-disclosure reference files that hold role-scoped knowledge, loaded only when the skill is invoked.
- **MCP response body** — when a client calls `codrag(role="security", task="review auth.py")`, the returned context *is* the sub-atlas. No files needed.

All three are valid delivery paths for the same content (the role-weighted sub-atlas). The research in R3 tells us which path works best; R4 picks the API shape; R8 measures the delta.

## Bottom line

- **The approach is unchanged:** role-weighted sub-atlases via graph-based knowledge selection.
- **The research is unchanged:** test whether this mechanism improves agent performance.
- **The framing is corrected:** we hone knowledge, we do not prompt personas. The persona-prompting literature's caveats do not automatically apply.
- **The existing UI + sub-atlas engine is the thing being validated**, not rebuilt.
- **R3 is the critical test** of our core thesis, and we should run it proudly, not defensively.

If the earlier docs in this folder read as though we were backing away from role scoping, disregard that tone. We are not. We are running the experiment that tells us whether the thing we already built works — and if so, how to deliver it across every agent runtime.
