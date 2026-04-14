# 06 — Scrutiny & Reverse Engineering

This document does three things:
1. **Steelmans the counter-argument** to each major premise in the plan.
2. **Stress-tests optimizations** we haven't made yet.
3. **Reverse-engineers the competitive playbook** — how would a smart team beat CoDRAG at this?

Nothing here is a reason to stop shipping. Every item is a guard-rail, a risk flag, or a missing optimization.

---

## Part A — Steelmanning our own premises

### Premise 1: "Agent-artifact files should be excluded from the index"

**Our claim (03_EXCLUSION_POLICY):** CLAUDE.md, .claude/**, .cursor/**, etc. are noise in the index. Indexing them creates circular authority.

**Steelman counter:** In some teams, CLAUDE.md is **living documentation that humans also search**. Excluding it means a human asking *"what did we tell Claude about auth?"* gets no hit. The agent-artifact framing assumes agents are the only consumers, but in practice these files often double as the team's README.

**Defense:**
- This is exactly what the mixed-content splitter (Strategy C) addresses: user-authored portions remain searchable; CoDRAG-managed portions do not.
- UI override path is required, not optional — we flagged this in 03. Reinforce it.
- We should ship F0 with a default-strict classifier *and* a per-project override file so teams can opt files back in when they treat them as living docs.

**Revision:** make the override path table-stakes, not v3. At least a YAML file `.codrag/index_overrides.yaml` in v1.

### Premise 2: "Role-projected subagents improve agent output"

**Our claim (F1):** Emitting `.claude/agents/<role>.md` with scoped atlas improves agent quality.

**Steelman counter:** Research (arxiv 2603.18507, others) shows persona/role prompting has **mixed-to-negative** empirical results. Anthropic's own stance favors agentic search over persona tricks. We may be building elaborate persona infrastructure for marginal gains while the real win — scope filtering — is hidden inside it.

**Defense:**
- Scope filtering *is* independently valuable (context rot research validates this).
- Tool allowlists are a mechanism-level constraint, not persona.
- Antibody routing is concrete behavior, not roleplay.

**Revision (carried from 05):** kill the "persona writes better prose" fantasy. Market F1 as **"scoped knowledge bundles that happen to be addressable by role name."** Strip flowery SOUL.md prose from the default generator; let users opt in to tone/style sections if they want them. Measure scope-filter benefit independent of persona.

### Premise 3: "One source of truth → many emission targets"

**Our claim (04_INTEGRATION_ARCHITECTURE):** A single `role.yaml` canonically defines a role; emissions flow out to Paperclip + OpenClaw + Claude Code + Cursor.

**Steelman counter:** Every emission format evolves on its own timeline. Claude Code's subagent schema has changed multiple times already. OpenClaw renamed twice in three months. Paperclip's API is alpha. We'll be carrying version-migration debt in our emitters indefinitely — and each target will occasionally get a feature the others don't support (hooks vs. no hooks, tool scoping vs. none).

**Defense:**
- The *canonical spec* absorbs evolution; emitters are where the churn lives. That's the correct place for it.
- Per-target features that can't be expressed in `role.yaml` get escape-hatch fields (`target_specific.claude_code.extra_hooks`, etc.).

**Revision:** explicitly version the spec (`schema: 1.0`). Version the per-target writers independently. Write a compatibility matrix doc that states which spec fields each target supports, refreshed per release.

### Premise 4: "Concepts scale as a flywheel"

**Our claim (F6):** Observations → seeds → active concepts → artifacts. The longer CoDRAG runs, the smarter everything gets.

**Steelman counter (harsh):** We have **366 seeds and 0 active concepts on our own project**. The flywheel is not running. If promotion has been blocked for this long on the reference codebase, shipping more emission targets won't help — we'll emit empty Gotchas sections and trivial antibody sets. We're planning against a capability we haven't demonstrated.

**Defense:** fair; this is the most honest risk in the whole plan.

**Revision:** promote F6 from "roadmap item" to **"must complete before F3/F4 ship."** Concept promotion either works or the downstream features are theater. Specifically:

- Before F3 hooks, we need ≥10 active constraint concepts on our own repo.
- Before F4 skills-as-folders, we need ≥20 active concepts to fill Gotchas meaningfully.
- If we can't promote that many in two weeks, the flywheel premise is broken and F3/F4 need different content sources.

### Premise 5: "CoDRAG as the shared brain across runtimes"

**Our claim (04):** Observations/concepts written by one agent are visible to the next.

**Steelman counter:** MCP is a read-only-biased protocol. Writes (`codrag_observe`, `codrag_concepts`) require the agent to actually call them. Agents overwhelmingly read, rarely write. The shared-brain promise is **consumer-heavy and producer-starved.** Without deliberate write incentives, the graph stagnates.

**Defense:**
- PostToolUse hooks can auto-write observations ("file X was edited, note the change") without requiring agent initiative.
- Paperclip agents run longer-lived tasks and can be configured to write back more naturally.

**Revision:** add a **write-incentive layer** — PostToolUse hook that captures minimal observations automatically (edited file, tool calls made, tests run). This feeds the graph even when agents don't voluntarily write. This is a new roadmap item worth naming: **F11 — Automatic observation capture**.

### Premise 6: "Antibodies as hooks are a differentiator"

**Our claim (F3):** Antibody-driven hooks are unique to CoDRAG.

**Steelman counter:** Hooks are infrastructure that anyone can implement. Our differentiator is the *content* of the hooks, not the mechanism. That content comes from antibodies, which come from constraint concepts — which require active concepts (see Premise 4). We're differentiating on a layer we haven't activated yet.

**Defense:** exactly right. F3's value is gated on F6. Ship ordering must reflect this.

**Revision:** restate F3 dependency on F6 in all roadmap docs. No hook work before concept promotion delivers at least 10 constraint concepts on the dogfood repo.

---

## Part B — Optimizations we have not yet made

### Optimization 1: Temporal validity on concepts and observations

**Gap:** Today concepts exist or don't. No "this was true in Q1 2026 but superseded after the Phase 102 rename." Zep beats Mem0 by 15 points on LongMemEval using temporal validity windows.

**Fix:** Add `valid_from`, `valid_until`, `superseded_by` fields to concepts and observations. Audit surface: "stale concepts — last validated > 90 days ago." Emission targets respect validity (stale concepts don't appear in KNOWLEDGE.md).

**Value:** parity with Zep; enables "what *used to be* true?" queries; automatic drift detection.

### Optimization 2: Position-aware artifact layout

**Gap:** Our generated files place content in what-feels-right order. Context-rot research says the **start and end** of a context have 85–95% recall, the middle much worse.

**Fix:** Every generator that produces a prompt-visible artifact (CLAUDE.md block, SKILL.md, subagent file) should use a standardized template where:
- **Start:** the most critical constraints (forbidden tools, active antibodies, hard rules).
- **Middle:** derivable knowledge (scoped atlas, concepts, references).
- **End:** the active task framing, the "call codrag first" directive, the current focus.

**Value:** measurable recall improvement on the artifacts we already generate.

### Optimization 3: Eval harness for agent preparation

**Gap:** We have **no benchmark** measuring whether CoDRAG-prepared agents actually perform better than unprepared ones. We're flying blind. Every optimization above is a hypothesis.

**Fix:** Build a minimal eval harness: a set of prepared tasks against CoDRAG's own codebase (fix bug X, implement feature Y, review file Z), run them with and without CoDRAG preparation, measure correctness + token cost + time. Codebase-Memory paper provides a direct benchmark template (83% answer quality, 10× tokens).

**Value:** can claim real numbers, not just architectural elegance. Competitive differentiation relies on measurement.

### Optimization 4: Emission caching and incremental regen

**Gap:** Every role-spec change triggers re-emission of every target. Small change to concepts → Paperclip sync + Claude subagent regen + OpenClaw push.

**Fix:** Content-addressable emission. Each target output has a hash of its inputs. On regen, skip writes where hash matches. Only fan-out to Paperclip REST on actual content change.

**Value:** faster dev loop; fewer Paperclip API calls; cleaner git history when emissions are checked in.

### Optimization 5: Binary distribution / zero-daemon mode

**Gap:** CoDRAG requires `.venv + daemon on :8400 + maturin + tree-sitter grammars`. This is high-friction for casual users. Cursor's "boots in minutes" story beats us on cold-start UX.

**Fix:** A single binary (`codrag-mini`) that packages the Rust engine + essential Python into one artifact, with embedded ONNX models. For read-only usage (search, impact, atlas), no daemon needed.

**Value:** closes the cold-start-time gap to near-zero for new users. Enables one-command install (`brew install codrag`, single `curl | sh`).

### Optimization 6: Streaming MCP responses for large queries

**Gap:** Large `codrag_search` or `codrag_audit` queries block. The MCP client sees latency.

**Fix:** Support SSE transport for streaming chunks — respond with preliminary high-confidence results first, refine over time. Client can display early while deeper analysis continues.

**Value:** better perceived latency; matches modern RAG UX.

### Optimization 7: Artifact freshness hooks

**Gap:** Generated `.claude/agents/security.md` has a hash stamped in, but nothing *checks* freshness when the agent loads it. It can be arbitrarily stale.

**Fix:** A PreToolUse hook that, before `Task` dispatches to a subagent, verifies the subagent file's atlas-hash matches the current atlas. If stale, print a warning (or regenerate on the fly if under a time budget).

**Value:** closes the staleness loop; prevents agents operating on outdated scope.

### Optimization 8: Privacy-preserving shared memory

**Gap:** Observations are global to a project. In a multi-tenant or multi-user scenario (paperclip-hosted), we need per-user private memory + shared memory with access control — exactly what arxiv 2505.18279 "Collaborative Memory" describes.

**Fix:** Add user-scoped observation store. Default to private; promotion to project-shared requires explicit action.

**Value:** enterprise requirement; unblocks multi-user Paperclip deployments.

---

## Part C — Reverse engineering the competitive playbook

If a well-resourced competitor wanted to beat CoDRAG at agent preparation, what would they build? This matters because our moat depends on what's *hard* to replicate.

### Attack vector 1: Fatter repo-map + faster cold start

**Competitor move:** Build a compelling repo-map like Augment's "Deep Context Threading," distribute as a VS Code / Cursor extension (no daemon), get to value in 30 seconds on install.

**Our weakness:** Our atlas is good but our install friction is high. Cold-start UX is an exposed flank.

**Defense:** Optimization 5 (binary distribution). Also: publish benchmark numbers. If our atlas quality > theirs, users will tolerate more install friction for enterprise use. But we need the numbers.

### Attack vector 2: Lean into agentic search, skip persistent index entirely

**Competitor move:** Follow Anthropic's public stance that agentic search + grep > RAG. Build a thin wrapper that teaches Claude Code to search well, no persistent index.

**Our weakness:** Persistent index is our thing. If the community decides it's unnecessary, we're fighting uphill.

**Defense:** The persistent index is where **concepts, antibodies, role vectors, and observations live**. None of these are derivable from grep. We have to crisply articulate what the index *is for*, not just that it exists.

The market-positioning story: *CoDRAG's index is not a search cache — it's a validated-knowledge layer. Grep finds text; concepts explain decisions; antibodies enforce constraints; role vectors route context. These require a persistent store.*

### Attack vector 3: Copy our role specification, emit faster

**Competitor move:** Read our role.yaml format (when public), build their own emitters, undercut on ecosystem breadth by adding targets we don't.

**Our weakness:** `role.yaml` is trivially replicable. Our emitters are trivially replicable.

**Defense:** The spec isn't the moat. **The concept graph feeding the spec is the moat.** A role.yaml generated from our knowledge graph (with validated concepts, role-aware antibodies, observation history) is richer than one generated from a repo-map alone. We should over-invest in the *input* to role specs (concepts, observations, antibodies), not over-invest in the emitter code.

### Attack vector 4: Temporal knowledge graph + eval harness

**Competitor move:** Someone forks Zep's temporal approach, adapts it to code, publishes LongMemEval-for-code benchmarks, wins on measurement.

**Our weakness:** We have no temporal story and no benchmarks (see Optimizations 1 and 3).

**Defense:** Build both urgently. Both are straightforward engineering. If we ship temporal concepts and a public eval harness before a competitor does, we own the narrative.

### Attack vector 5: Own the IDE directly

**Competitor move:** Cursor, Windsurf, or Continue absorb our ideas into their core product. The IDE vendor has zero-friction distribution; we don't.

**Our weakness:** IDE vendors own the UX; we bolt onto it.

**Defense:** **Be the backend for the IDE, not the competitor.** Partnership with smaller IDE vendors (Zed, Qwen, Cursor's plugin market) where CoDRAG is the intelligence provider and they own presentation. This is the Paperclip model applied to IDEs: layer 1 knowledge, layer 4 execution, different companies per layer.

### Attack vector 6: Anthropic ships it natively

**Competitor move:** Anthropic releases Claude-Code-native knowledge graph + concept layer as part of Managed Agents. Free, integrated, zero-config.

**Our weakness:** Structural risk. Anthropic can do this.

**Defense:** 
- Be cross-client. Anthropic will never be cross-client — they optimize for Claude. Cursor users, Zed users, OpenClaw users need us.
- Be local-first. Anthropic's managed offerings tilt toward cloud; regulated industries need local.
- Move faster on niche features (antibodies, paperclip integration) that Anthropic won't build because they're too specific.

---

## Part D — The "are we really optimizing?" audit

For each core aspect of our plan, rate: are we optimizing, satisficing, or neglecting?

| Aspect | Status | Evidence |
|---|---|---|
| Context budget per artifact | Satisficing | We have 2–5K target but no measurement |
| Context budget across artifacts | Neglecting | No total ceiling enforcement |
| Position-aware placement (start/end) | Neglecting | Templates don't enforce this |
| Progressive disclosure in skills | Planned | F4 addresses it correctly |
| Hook enforcement correctness (Pre vs Post) | Satisficing | Research says split; our F3 now reflects this |
| Temporal validity on concepts | Neglecting | Critical gap (Optimization 1) |
| Eval benchmarks | Neglecting | Critical gap (Optimization 3) |
| Emission caching | Neglecting | Minor gap (Optimization 4) |
| Cold-start UX / distribution | Neglecting | Strategic gap (Optimization 5) |
| Artifact freshness at load time | Neglecting | Minor gap (Optimization 7) |
| Privacy / multi-user scoping | Neglecting | Enterprise-blocker (Optimization 8) |
| Write-incentive for the graph | Neglecting | Premise-5 gap (new F11) |
| Documentation-as-code for external audiences | Satisficing | Good in-repo docs; need public benchmarks |

**Honest count:** 8 "Neglecting," 4 "Satisficing," 2 "Planned" or "Optimizing."

Most of these are not hard. They're gaps because the roadmap hadn't gone deep enough. This document closes that gap.

---

## Part E — Revised priorities after scrutiny

Starting from the original roadmap in `README.md`, these are the revisions scrutiny demands:

1. **Promote F6 (concept promotion) to a hard prerequisite** for F3 and F4. No concept promotion → no hooks and no skills Gotchas. Fix the flywheel before building on top of it.

2. **Split F3 into F3a (PreToolUse blocking constraint antibodies) and F3b (PostToolUse observing quality concepts)**. They have different primitives, different risks, different rollout.

3. **Add F11 — Automatic observation capture via PostToolUse hook.** Solves the write-starvation problem for the shared brain.

4. **Add F12 — Temporal validity on concepts and observations.** Match Zep's architecture; enable drift detection.

5. **Add F13 — Eval harness.** Measure what we claim. Publish numbers. Without this, every other feature is architecturally elegant but epistemically unproven.

6. **Revise F1 messaging** across all docs: role subagents provide scope + tools + routing. Persona theater is optional and not load-bearing.

7. **Revise F5 to include total-cross-artifact budget**, not just per-artifact.

8. **Add a position-aware template standard** that all artifact generators use: critical content at start+end, derivable content in middle.

9. **Add F0.5 — Per-project index override file.** Makes the F0 exclusion policy non-punishing for teams who treat agent-files as living docs.

10. **Add explicit schema versioning to role.yaml** with a compatibility matrix doc.

---

## Closing thought

The research survey (05) shows that CoDRAG is building on a validated architectural foundation: tree-sitter + knowledge graph + MCP is empirically proven to save 6.8–120× tokens. That's not in question.

The scrutiny (06) shows where our execution is thin: we have grand architecture but under-invested infrastructure for temporal validity, eval harnesses, and automatic write-capture. The moat is real (concepts + antibodies + roles), but it's only a moat if the *water actually fills it*. Right now, 0 active concepts means the moat is dry.

Ship F0, F5, F6 first. Measure. Then earn the right to ship F1, F3, F4. Prioritize the flywheel over the chrome.
