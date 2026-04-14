# 05 — Research Survey: Anchoring Our Claims to Published Evidence

Before committing to this roadmap, we stress-tested each major premise against recent (late-2025 / 2026) research, Anthropic publications, academic papers, and competitor disclosures. This document is the audit trail: *what do we actually know?*

## Evidence map — claims by source

| Phase 103 claim | Evidence status | Source |
|---|---|---|
| Context bloat degrades agent performance | **Strong** | Chroma "Context Rot"; Lost-in-the-Haystack (2026) |
| Progressive disclosure dramatically cuts token usage | **Strong** | Microsoft Agent-Skills research: 94.7% savings measured |
| Knowledge graphs cut coding-agent tokens | **Strong** | 6.8×–49×–120× reductions reported in multiple independent implementations |
| Persona/role prompting reliably improves output | **Contested** | 2603.18507 "Expert Personas Improve Alignment but **Damage Accuracy**"; no reliable benefit across 162 roles |
| Hooks > prompts for enforcement | **Strong** | Anthropic Claude Code hooks docs: "hooks guarantee, prompts suggest" |
| Subagent isolation reduces context pollution | **Strong** | Anthropic + InfoQ coverage; 10-concurrent Task batches |
| Agentic RAG outperforms traditional RAG for complex tasks | **Moderate** | arxiv 2501.09136 survey; trade-off is latency + reliability |
| Temporal knowledge graphs beat flat memory | **Strong** | Zep 63.8% vs Mem0 49.0% on LongMemEval |
| Single-source-of-truth role specs avoid drift | **Plausible** | No direct study; industry consensus from multi-agent frameworks |

## 1. Context rot is empirically real (validates F5, F4, budget obsession)

Chroma's Context Rot research and the "Lost in the Haystack" paper (2026) establish two findings that matter here:

- **Performance degrades as input tokens grow, even when added content is technically relevant.** It's not just about finding the needle — overall model coherence drops.
- **Smaller "gold contexts" degrade worse and amplify positional sensitivity.** Critical for us: if we project a role down to 2K tokens but that 2K is scattered or not positioned at beginning/end of the context, recall accuracy drops.

**Research-backed recommendations refining our plan:**
- Place critical constraints (antibodies, forbidden tools) at the **start and end** of every generated artifact. The middle is the worst position.
- Test knowledge-scope sizes empirically. Phase 88 targets 2–5K for KNOWLEDGE.md; research suggests 3–5K may be safer than 2K due to positional-sensitivity amplification at small sizes.
- Per-artifact budgets aren't enough. We need a **sum-of-all-CoDRAG-content** budget for cold-start context (proposed 8 KB in F5 is a good starting point; verify empirically).

## 2. Progressive disclosure is validated at scale (validates F4)

Microsoft's Agent-Skills research measured **94.7% context savings** using the four-stage pattern (advertise at startup → load SKILL.md on match → read resources on demand → run scripts on demand). Their reported numbers: **8K tokens used vs. 150K for naive loading**.

Claude's own documentation echoes this: treat context as a finite attention budget; every token competes for attention.

**Implication for F4 (skills-as-folders):** this is not a stylistic choice — it's table stakes. Our current single-file `.claude/skills/codrag.md` is leaving double-digit-% context efficiency on the table. Folder structure with `SKILL.md` + `references/` + `scripts/` is the objectively correct pattern.

**Stronger recommendation than the original F4 spec:** add explicit "advertise at startup" metadata. SKILL.md frontmatter should include a tight `when_to_use` field that the host uses to decide whether to fork in the full skill — not just `description`.

## 3. Knowledge-graph-over-code is the right architecture (validates CoDRAG's core thesis)

Multiple independent implementations in 2026 report massive token reductions by moving from file-reading to graph-querying:

- 49× token reduction on Claude Code workflows via tree-sitter + knowledge graph
- 120× token reduction reported in DEV Community case study
- 6.8× on code reviews, 2.1× fewer tool calls, 83% answer quality at 10× fewer tokens (Codebase-Memory arxiv paper, 2603.27277)

The arxiv paper **Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP** (2603.27277) is essentially an academic description of the architecture CoDRAG already implements. We should:

1. **Read and cite the paper** in our external docs/marketing. Positions CoDRAG as the production-grade instance of a validated architecture.
2. **Compare benchmarks.** Run CoDRAG against their reported metrics (83% answer quality, 10× token reduction). If we're comparable or better, it's a credible public benchmark. If we're worse, it's an internal fix-list.
3. **Differentiate on concepts + antibodies.** The paper covers structural knowledge. Our concept/antibody layer is *on top* — it's what they don't have.

## 4. Persona/role prompting effectiveness is mixed — this is the one we have to be careful with

The strongest counter-evidence to our F1 (role-projected subagents) came from research on persona prompting generally:

- arxiv 2603.18507 **"Expert Personas Improve LLM Alignment but Damage Accuracy"** — the title alone is a warning.
- OpenReview **"LLM Generated Persona is a Promise with a Catch"** — persona generation adds risk.
- ACL 2025 studies showing effectiveness is **task- and model-dependent**; blanket claims are oversimplified.
- Some studies report **no reliable benefit across 162 roles** and **degraded zero-shot reasoning**.

**This undermines a naïve reading of F1**, where we'd just write rich personas and expect quality gains.

**The refinement:** our role-projected subagents should not lean on persona for output quality. They should lean on persona for **three structural things:**

1. **Knowledge scope narrowing.** Giving a security subagent only security-relevant files is an operational constraint, not a personality trick. Research on context rot supports this as independently beneficial.
2. **Tool allowlist / forbidden-action constraints.** Hooks and tool filtering are mechanism-level guarantees. They work regardless of whether "personality" helps.
3. **Antibody activation.** A security subagent fires different antibodies than a frontend subagent. That's routing, not roleplay.

What we should **not** do:
- Generate flowery SOUL.md personality text and call it quality improvement.
- Claim role prompting alone produces better code — research is at best ambivalent.

**Action:** revise F1 and Phase 88's SOUL.md generation to de-emphasize persona theater and emphasize scope + tool + antibody routing. Measure the improvement that comes from scope filtering *independently* of the improvement that might come from persona prompting.

## 5. Hooks > prompts for enforcement (strongly validates F3)

Claude Code's official docs put it clearly:

> *Without this hook, you would need to write "never run dangerous commands" in your CLAUDE.md and trust that the model always follows the instruction. With this hook, dangerous commands are physically blocked at the execution layer. The agent cannot bypass it, forget it, or reason its way around it.*

Key technical details that refine F3:
- **Only PreToolUse can block.** PostToolUse runs after the tool executes — good for linting, quality checks, telemetry, not prevention. Our F3 needs to split antibody enforcement by type: constraint antibodies → PreToolUse; quality antibodies → PostToolUse.
- **Since v2.0.10, PreToolUse hooks can modify tool input.** This is more valuable than blocking — we can rewrite edits to comply with concepts rather than rejecting them. A concept-aware PreToolUse hook that, e.g., adds a missing type annotation rather than blocking the edit.
- **Exit code semantics:** hooks communicate via exit codes and stdout. Hook output format is stable; this is safe infrastructure to build on.

**Stronger recommendation than the original F3 spec:** build both PreToolUse (blocking/modifying) and PostToolUse (observing) variants. Constraint concepts become PreToolUse blocks; observation concepts become PostToolUse annotations. This is infrastructure competitors cannot easily match because they'd need the concept layer first.

## 6. Subagent isolation has known limitations (caveats F1)

- Parent agent cannot monitor subagents during execution.
- Subagents cannot communicate with parent mid-task.
- Subagents cannot communicate with sibling subagents.

**Implication for F1:** when emitting `.claude/agents/<role>.md`, we cannot assume the subagent can "check back in" mid-task. Its knowledge scope must be **complete at spawn time**. This means our role-filtered KNOWLEDGE.md has to anticipate sub-questions the agent will ask.

**The CoDRAG advantage:** because the subagent has MCP access to CoDRAG, it can query the daemon mid-task. The shared brain works *via* MCP, not via subagent IPC. This is consistent with Agent-MCP's approach (github.com/rinadelph/Agent-MCP). Make sure our generated subagent files explicitly instruct use of MCP for mid-task queries.

## 7. Multi-agent shared memory is competitive territory

"The Agent Memory Race of 2026" — five repos with 80K combined stars all trying to solve AI agent memory persistence. Key signal:

- **Zep vs Mem0 LongMemEval gap:** 63.8% vs 49.0% — a 15-point gap attributed to Zep's use of **temporal knowledge graphs with validity windows** (when a fact was true vs superseded).
- **Neo4j + Multi-Agent Shared Graph Memory** — Neo4j is positioning for the agent shared-memory use case.
- **Collaborative Memory (arxiv 2505.18279)** — multi-user + multi-agent with asymmetric time-evolving access control.

**Gap in CoDRAG today:** our concepts and observations are stored but don't have explicit *temporal validity windows*. A concept that was true three months ago but is now superseded is not automatically demoted.

**Recommendation (new roadmap item):** add temporal edges to concepts and observations. Every active concept has a `valid_from` and optional `superseded_by`. The audit can surface drift where a concept no longer matches reality. This would put us on par with Zep and differentiate us structurally from Mem0.

## 8. Competitive positioning (reality check)

Reviewing the 2026 AI-coding-tool landscape:

- **Cursor**: dynamic context loading, no persistent index. Fast to start; weaker on repo-wide semantics.
- **Sourcegraph Cody**: full repo indexing via RAG; strong semantic search; slow setup; enterprise positioning.
- **Augment Code**: "Deep Context Threading" — builds a map of connections, distinguishes behavioral from ceremony code. *This is close to our repo-map territory.*
- **Claude Code**: agentic search-first philosophy (Anthropic's public stance is that agentic search + grep often beats RAG). Subagents, hooks, skills, commands all built-in.
- **Continue**: BYO-model, VS Code-focused.

**CoDRAG's unique positions:**
- Only tool combining **concepts + antibodies + role vectors** — a validated-knowledge layer above the code graph.
- Only tool emitting across **Paperclip + OpenClaw + IDE subagents** from a single role spec (once Phase 103a ships).
- Local-first with stdio MCP is friendlier than Cody's hosted model for enterprise air-gap customers.

**CoDRAG's exposed flanks:**
- Augment Code's "Deep Context Threading" is marketing-adjacent to our repo-map. If their implementation is strong, buyers may not see the conceptual distinction.
- Anthropic's own messaging favors agentic search over RAG. We need a crisp story for *"why have a persistent index when the model can just grep?"* — our answer is concepts + antibodies + roles, which are not derivable from grep.
- The 49× / 120× token reduction claims from independent GraphRAG projects mean **the idea is not a moat anymore**. Execution quality is. We need public benchmarks on our own numbers.

## 9. Anthropic's 2026 direction (implications for us)

From Anthropic's "Effective context engineering for AI agents" and the 2026 Agentic Coding Trends Report:

- Compaction, just-in-time retrieval, and hooks are officially blessed patterns.
- Claude Opus 4.6 with 1M context exists, but effective context remains far smaller in practice — research consistently shows degradation well before the advertised limit.
- Managed Agents (`/v1/agents`, `/v1/sessions`) is Anthropic's new orchestration API.

**Implication:** CoDRAG should be discoverable *by* Claude Managed Agents. Emitting to that target (in addition to Claude Code subagents, OpenClaw, Paperclip) may be a Phase 104 item. It's a different format (API-registered, not file-based).

## 10. Summary: what to change in the plan based on research

| Doc | Item | Change |
|---|---|---|
| 02_FEATURE_PROPOSALS | F1 | De-emphasize persona theater; emphasize scope filtering + tool allowlist + antibody routing as the value |
| 02_FEATURE_PROPOSALS | F3 | Split into PreToolUse (blocking constraint antibodies) and PostToolUse (observing quality concepts) |
| 02_FEATURE_PROPOSALS | F4 | Add explicit `when_to_use` metadata in SKILL.md frontmatter; target the Microsoft 4-stage pattern exactly |
| 02_FEATURE_PROPOSALS | F5 | Budget should be per-artifact AND total-across-all-CoDRAG-content on cold-start |
| 04_INTEGRATION_ARCHITECTURE | (new) | Add temporal validity to concepts and observations — match Zep's architecture |
| README | (new) | Add "Phase 104 preview: Claude Managed Agents emission target" |

## Sources

- [Effective context engineering for AI agents (Anthropic)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [2026 Agentic Coding Trends Report (Anthropic)](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance (Chroma)](https://research.trychroma.com/context-rot)
- [Lost in the Haystack: Smaller Needles are More Difficult for LLMs to Find (PMC/OpenReview)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12478432/)
- [Expert Personas Improve LLM Alignment but Damage Accuracy (arxiv 2603.18507)](https://arxiv.org/pdf/2603.18507)
- [LLM Generated Persona is a Promise with a Catch (OpenReview)](https://openreview.net/forum?id=qh9eGtMG4H)
- [Progressive Disclosure in Agent Skills (Microsoft / AgentHub)](https://www.agentskillsmarket.space/blog/progressive-disclosure-agent-skills)
- [Microsoft Agent Skills (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [Claude Code Hooks reference (Anthropic)](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks: The Deterministic Control Layer for AI Agents (Dotzlaw)](https://www.dotzlaw.com/insights/claude-hooks/)
- [Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP (arxiv 2603.27277)](https://arxiv.org/abs/2603.27277)
- [Agentic Retrieval-Augmented Generation: A Survey (arxiv 2501.09136)](https://arxiv.org/abs/2501.09136)
- [The Agent Memory Race of 2026 (OSS Insight)](https://ossinsight.io/blog/agent-memory-race-2026)
- [Multi-Agent Shared Graph Memory (Neo4j)](https://neo4j.com/nodes-ai/agenda/multi-agent-shared-graph-memory-building-collective-knowledge-for-agents/)
- [Collaborative Memory: Multi-User Memory Sharing in LLM Agents (arxiv 2505.18279)](https://arxiv.org/html/2505.18279v1)
- [Create custom subagents (Anthropic Claude Code)](https://code.claude.com/docs/en/sub-agents)
- [Claude Code Subagents Enable Modular AI Workflows with Isolated Context (InfoQ)](https://www.infoq.com/news/2025/08/claude-code-subagents/)
- [Building agents with the Claude Agent SDK (Anthropic)](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Scaling Managed Agents (Anthropic)](https://www.anthropic.com/engineering/managed-agents)
- [Agent-MCP framework (github.com/rinadelph/Agent-MCP)](https://github.com/rinadelph/Agent-MCP)
- [I Built a Knowledge Graph That Cuts Claude Code's Token Usage by 49x (Medium)](https://tirthkanani18.medium.com/i-built-a-knowledge-graph-that-cuts-claude-codes-token-usage-by-49x-ca73ef078981)
- [How I Cut My AI Coding Agent's Token Usage by 120x With a Code Knowledge Graph (DEV)](https://dev.to/deusdata/how-i-cut-my-ai-coding-agents-token-usage-by-120x-with-a-code-knowledge-graph-4a3d)
- [Repository Intelligence in AI Coding Tools (BuildMVPFast)](https://www.buildmvpfast.com/blog/repository-intelligence-ai-coding-codebase-understanding-2026)
- [Cursor vs Sourcegraph Cody: Embeddings and Monorepo at Scale (Augment Code)](https://www.augmentcode.com/tools/cursor-vs-sourcegraph-cody-embeddings-and-monorepo-scale)
- [AI IDE Comparison 2026: Cursor vs Claude Code vs Sourcegraph Cody (SitePoint)](https://www.sitepoint.com/ai-ides-compared-cursor-claude-code-cody-2026/)
