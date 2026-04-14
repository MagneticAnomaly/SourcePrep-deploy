# Phase 103: Agent Optimizations

> **Read `00_CLARIFICATION.md` before anything else in this folder.** It corrects a framing error that appeared in earlier drafts of this plan. Short version: CoDRAG does **knowledge-honing** (graph-based scoped RAG), not **persona prompting** (AGENTS.md-style "you are X" instructions). The persona-prompting research does not apply to our mechanism; our mechanism is largely untested in the literature; Phase 103's research path is how we test it.

## Thesis

**CoDRAG hones what the agent can see by serving role-weighted sub-atlases over MCP.** We do not tell the agent who to be. We change the knowledge corpus the agent operates on — a sub-atlas filtered through the role's domain, layer, module, and hub-ownership vectors, enriched with concepts and antibodies tagged for that role. The agent's instructions, tools, and reasoning stay in the host. We provide scoped knowledge.

Our `codrag(role="rolename")` Paperclip integration proves the mechanism works end-to-end. The sub-atlas engine, role vectors, and UI are built and live. What we have not done is **measured** whether the knowledge-honing produces better agent output than a uniform atlas would. That is the research question Phase 103 answers, and everything else (emission formats, hooks, concept activation, benchmarks) hangs off the answer.

Previous framings to discard:
- ❌ *"emit agent files with personas"* — we emit scoped knowledge, not personas.
- ❌ *"we are not building agents"* — accurate but incomplete; we are providing **knowledge** that changes how existing agents behave.

Corrected framing:
- ✅ *"We hone knowledge, we don't prompt personas. Agents live in the host; scoped knowledge lives in CoDRAG."*

See `07_RESEARCH_PATH.md` for the sub-phase structure that validates and refines this thesis, **`08_POC_EXECUTION.md` for the trimmed POC plan (~2 weeks)**, and **`09_FOCUSED_BUILD_PLAN.md` for the full phased roadmap including preserved emission targets and antibody hooks in later phases**.

## What we discovered while planning

Before committing to new construction, we verified the existing surface of the repo:

- `codrag()` **already accepts `role` as an MCP parameter** (`src/codrag/mcp_tools.py:43`).
- `project_atlas_for_role()` **already exists** (`src/codrag/core/atlas/role_projection.py:533`).
- `RoleVector` class **already defined** (`src/codrag/core/atlas/role_vectors.py:92`).
- `tests/eval/eval_runner.py` (246 lines) + `gold_queries.json` + `overnight.py` (654) + `e2e_pipeline.py` (897) — **a 2,000+ line eval harness already exists.**

Phase 103 is therefore primarily *extension + measurement*, not new construction. The POC plan is correspondingly small.

## Context

- **Reference:** `shanraisshan/claude-code-best-practice` — catalogues the community's current best practices for preparing Claude Code: small CLAUDE.md files, feature-specific subagents, `.claude/commands/`, skills-as-folders, PreToolUse/PostToolUse hooks, wildcard permission scaffolding, `context:fork` progressive disclosure.
- **Our audit (this conversation):** We have strong per-IDE rule writers (8 IDEs), a role-projection engine that never emits files, a single flat skill stub, zero hooks, zero slash commands, 366 concept seeds but 0 active concepts, antibodies that are informational only, and no runtime context (daemon state, recent activity, test map).
- **Strategic gap:** Competitors (Cursor, Continue, Augment) index code. None of them have our concept layer, antibody layer, or role projection engine. These are unique assets we are currently under-leveraging.
- **Adjacent phases already planned:**
  - **Phase 67 (HR-concept-adapter)** — role file format: `AGENTS.md` + `SOUL.md` + `KNOWLEDGE.md` per role.
  - **Phase 88 (Agent Generator)** — two-pass universal generator (discover roles from structural signals → generate Phase 67 files via RoleVector-scoped sub-atlas → sync to Paperclip via REST).
  - **Phase 94 (OpenClaw Integration)** — verified zero-glue MCP stdio integration with OpenClaw (347K-star agent framework); SOUL.md + tool allowlist convention shared.
  - **Phase 64–67 Paperclip work** — layer model (CoDRAG = Layer 1 knowledge provider; Paperclip = Layer 4 orchestrator); Pull (MCP) + Push (REST) architecture; plugin at `packages/paperclip-plugin-codrag`.
- **Phase 103's place:** Adds the missing **client-side IDE layer** (`.claude/agents/*.md`, `.claude/commands/*.md`, skills-as-folders, PostToolUse hooks) on top of the role-spec architecture Phase 88 already designed for Paperclip. See `04_INTEGRATION_ARCHITECTURE.md` for how Claude Code + Cursor + Paperclip + OpenClaw converge on **one role spec, many emission targets**.

## Design principles

1. **Generate, don't lecture.** Every insight CoDRAG has about a codebase should land as an artifact the AI sees without having to call a tool — a file, a skill, a hook. Tool calls are for what the artifact can't encode.
2. **Budget is a first-class constraint.** Every artifact has a char budget. Atlas too big? Split. Skill too long? Fork. Subagent context too wide? Project. Never let a generated file exceed a threshold without splitting.
3. **Static → Live → Predictive.** Layer 1 is files (CLAUDE.md, skills). Layer 2 is MCP queries. Layer 3 is proactive context — the atlas *anticipates* what the AI will need based on what it just did.
4. **Unique assets first.** Concepts, antibodies, role projection — these are things only CoDRAG can generate. Prioritize features that surface them over features that mimic what other tools already do.
5. **Dogfood every output.** Every artifact CoDRAG generates should be something we use on CoDRAG itself. If we won't read it, the customer won't either.

## Prioritized roadmap

### Feature schedule across phases 103a–104+

Features are preserved in sequence, not dropped. The schedule is dictated by the measurement gate (R3) and the flywheel dependency (active concepts before hooks).

| # | Feature | Phase | Notes |
|---|---|---|---|
| R1–R8 | POC measurement suite | **103a (POC, ~2 wks)** | Baseline; validates knowledge-honing |
| F0 | Agent-artifact exclusion policy (walker + classifier) | **103b** | Prerequisite for any emission work; prevents circular authority |
| F0.5 | Per-project index override file | **103b** | Softens F0 for teams treating CLAUDE.md as living docs |
| F5 | Atlas budget + auto-split | **103b** | Enables ≤ 4 KB managed block |
| — | Registered agent store (`codrag_data/agents/<id>.yaml`) | **103b** | Tier 3 of lifecycle hybrid |
| — | UI file-tree scope tuner (finish existing work) | **103b** | In-scope / out-of-scope / boosted toggles |
| — | Sub-atlas override persistence per registered agent | **103b** | User tunings survive between calls |
| F1 | Claude Code subagent emission (signpost style) | **103c** | `.claude/agents/<role>.md` with one-liner + snapshot |
| — | OpenClaw SOUL.md emission | **103c** | Zero-glue per Phase 94 |
| — | Cursor / Windsurf / Copilot rule emission (signpost) | **103c** | One-line call-codrag directive |
| F2 | Slash commands (`.claude/commands/codrag-*.md`) | **103c** | Cheap UX win |
| F4 | Skills-as-folders with Gotchas | **103c** | Progressive disclosure per R2/R4 findings |
| F7 | Runtime awareness block | **103c** | Daemon + recent-activity feed |
| F6 | Concept promotion UI (assisted + auto-accept) | **103d** | Flywheel input |
| F3a | PreToolUse hooks (blocking constraint antibodies) | **103d** | Requires ≥10 active constraint concepts |
| F3b | PostToolUse hooks (observing quality antibodies) | **103d** | Paired with F3a |
| F11 | Automatic observation capture (broad rollout) | **103d** | Closes write-starvation of the graph |
| F12 | Temporal validity + auto-staleness detection | **103d** | Zep-class temporal model |
| F8 | Test-map as first-class context | **104+** | After graph matures |
| F9 | Predictive context ("just edited X, likely need Y") | **104+** | Differentiator |
| F10 | Cross-session memory compaction | **104+** | Managed Agents emission target |
| — | Managed Agents emission (Anthropic `/v1/agents`) | **104+** | New carrier format as it stabilizes |
| — | Role-preset marketplace | **104+** | Network effect play |
| — | Binary distribution / zero-daemon mode | **104+** | Cold-start UX parity |
| — | Public benchmark publication (from R8) | **104+** | After internal eval stabilizes |

Nothing dropped. Order is dictated by dependencies: measure (103a) → register & tune (103b) → emit signposts (103c) → enforce & grow (103d) → expand surface (104+).

See `01_OPPORTUNITIES.md` for the deeper analysis, `02_FEATURE_PROPOSALS.md` for concrete designs of items 1–7, `03_EXCLUSION_POLICY.md` for F0, and `04_INTEGRATION_ARCHITECTURE.md` for how this work plugs into Phase 88 (Paperclip) and Phase 94 (OpenClaw).

## Recommended implementation sequence (revised with integration context)

**Phase 103a — Unified Role Emission** (2–3 weeks)
1. F0 exclusion policy (walker pattern list + classifier pass).
2. Factor Phase 88's Pass 2 file generator into target-agnostic core + per-target writers.
3. Add Claude Code subagent emission (F1).
4. Add OpenClaw SOUL.md emission (trivial extension of F1).
5. F5 atlas budget / auto-split (prerequisite for all emission paths).
6. F2 slash commands (cheap UX win, parallel work).

**Phase 103b — Flywheel** (follows 103a)
7. F6 concept seed promotion (activates 366 idle seeds).
8. F3 PostToolUse hooks (depends on F6 to have antibody content).
9. F4 skills-as-folders (Gotchas derive from promoted concepts).
10. F7 runtime awareness block.

**Phase 103c — Predictive** (ongoing)
11. Test-map as first-class context.
12. Session-aware predictive context.
13. Cross-session memory compaction.

## Scrutiny-driven revisions (from 06_SCRUTINY.md)

After stress-testing the plan against recent research (see `05_RESEARCH_SURVEY.md`) and reverse-engineering the competitive playbook:

- **F6 (concept promotion) is a hard prerequisite for F3/F4.** No active concepts → no hook content, no skill Gotchas. The flywheel must run before features built on it.
- **F3 splits into F3a (PreToolUse blocking) and F3b (PostToolUse observing).** Different primitives, different risks.
- **New F11 — Automatic observation capture** via PostToolUse hook. Solves write-starvation: agents read but rarely write. Auto-capture keeps the graph growing.
- **New F12 — Temporal validity** on concepts and observations. Parity with Zep's temporal knowledge graph (Zep 63.8% vs Mem0 49% on LongMemEval).
- **New F13 — Eval harness.** Measure agent-preparation quality gain vs unprepared. We claim but can't prove today. Benchmark template: Codebase-Memory paper (83% answer quality, 10× fewer tokens).
- **F1 messaging revision:** scope + tools + antibody routing is the value. De-emphasize persona theater — research shows persona prompting has mixed empirical results.
- **F5 expanded** to include total-cross-artifact budget (8 KB cold-start ceiling), not just per-artifact.
- **Position-aware template standard:** critical content at start+end, derivable content in middle. Matches 85–95% recall zones from context-rot research.
- **New F0.5 — Per-project index override file** (`.codrag/index_overrides.yaml`). Makes F0 exclusion policy non-punishing for teams who treat CLAUDE.md as living documentation.
- **role.yaml schema versioning** + per-target writer versioning + public compatibility matrix.

## Success criteria

- A fresh AI dropped into a CoDRAG-prepared project should, without calling any tool, know: what the project is, what role it's playing, which files are dangerous to touch, which workflows are canonical, and what has changed recently.
- The first 5 tool calls should be *enrichment*, not *orientation*. Orientation is already in the prompt context.
- For a 300-file project, the total generated artifact footprint should sit under 4 KB of prompt-visible content, with everything else available on demand via MCP / resources.
- Every generated artifact should reference a concept, antibody, or atlas node — nothing hand-written, nothing hallucinated.

## Non-goals

- We are not building an orchestration runtime (tmux, worktree spawning, cron). Claude Code has those; we generate inputs for them.
- We are not replacing CLAUDE.md or AGENTS.md. We are adding companions around them.
- We are not building a chat UI for agents. CoDRAG remains the backend.

## Open questions

- Should role projection be *static* (regenerated on atlas rebuild) or *dynamic* (served via MCP on demand)? Probably both, but which first?
- How do we keep generated subagent files from drifting when the code changes underneath them? Versioning + freshness markers? Splice with atlas-hash?
- Should antibody hooks be installed by default, or opt-in via a flag? Opt-in is safer; default is more valuable.
- Is there a risk that too many generated files *bloat* the AI's initial context and hurt rather than help? We need a budget story *across* artifacts, not just within each.
