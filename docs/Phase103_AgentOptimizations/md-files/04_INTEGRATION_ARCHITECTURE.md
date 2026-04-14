# 04 — Integration Architecture: CoDRAG as the Single Source of Truth for Agents

## The convergence

Phase 103 is not a standalone agent-optimization effort. It sits inside an architecture CoDRAG has been building for over a year. Reading the prior phase docs makes this clear:

- **Phase 67 (HR-concept-adapter)** defined the `agents/<RoleName>/` file layout: `AGENTS.md` (guardrails), `SOUL.md` (identity), `KNOWLEDGE.md` (scoped atlas).
- **Phase 88 (Agent Generator)** specified the two-pass universal generator: Pass 1 discovers what roles *should* exist from structural signals; Pass 2 generates the Phase 67 files via RoleVector-scoped sub-atlas, then syncs to Paperclip via REST.
- **Phase 94 (OpenClaw Research)** verified that OpenClaw consumes the same SOUL.md convention and MCP tools natively — zero glue code needed.
- **Phase 64–67** built the Paperclip plugin (Pull via MCP, Push via REST) and mapped CoDRAG's layer model: *Layer 1 = CoDRAG (codebase intelligence); Layer 4 = Paperclip (orchestration)*.

Phase 103 adds **the client-side IDE layer** that was missing: `.claude/agents/*.md`, `.claude/commands/*.md`, `.claude/skills/codrag/**`, PostToolUse hooks. These are the artifacts the developer's local coding agent (Claude Code, Cursor, etc.) needs.

**The insight:** all four surfaces — Paperclip roles, OpenClaw agents, Claude Code subagents, and IDE rules — are *different projections of the same underlying role definition*. CoDRAG has the only structurally-grounded role specification system in the market. We should emit into every agent runtime that exists, from one source of truth.

## Current architecture (after Phase 88 + 94)

```
                         CoDRAG Knowledge Graph
                  (code AST + concepts + antibodies + atlas)
                                   │
                                   ▼
                        RoleVector + Role Projection
                           (Phase 67 / Phase 88)
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            Paperclip REST    OpenClaw MCP    ???? (gap)
            (Phase 88 sync)   (Phase 94)      IDE-local agents
```

The IDE-local box is empty. Claude Code, Cursor, Windsurf developers have no CoDRAG-generated subagents to Task-dispatch to. They only get the generic CLAUDE.md / AGENTS.md rules-file.

## Target architecture (after Phase 103)

```
                         CoDRAG Knowledge Graph
                                   │
                                   ▼
                        RoleVector + Role Projection
                                   │
         ┌──────────┬──────────────┼──────────────┬─────────────┐
         ▼          ▼              ▼              ▼             ▼
   Paperclip    OpenClaw      Claude Code     Cursor        ????
   roles        agents        subagents       rules +       future IDEs
   (REST)       (SOUL.md +    (.claude/       agents        (emerging)
                MCP tools)     agents/*.md)   (.cursor/
                                              agents/*)
```

A role is defined once. It emits into four (soon many) agent runtimes with format-specific projections. Each projection filters knowledge scope, tool allowlist, and persona style to the target runtime's conventions.

## The unified role spec

The role spec becomes the portable, canonical artifact. It lives in `codrag_data/roles/<role_slug>/` and contains:

```
codrag_data/roles/security-engineer/
├── role.yaml              # Canonical definition: vector, modules, tools, persona
├── knowledge.sub-atlas.md # RoleVector-scoped sub-atlas (Phase 67 output)
├── antibodies.json        # Antibodies in this role's scope
├── concepts.json          # Concepts in this role's scope
└── emissions/
    ├── paperclip.json     # JSON payload for Paperclip REST API
    ├── openclaw.soul.md   # SOUL.md for OpenClaw
    ├── claude.agent.md    # .claude/agents/security-engineer.md
    ├── cursor.agent.yaml  # Cursor subagent format (when available)
    └── generic.agent.md   # Fallback for unknown IDEs
```

All emissions are derived, not authored. Change the role spec → re-emit → every target updates in lockstep. This is what Phase 88 already specifies for Paperclip; Phase 103 generalizes it across IDE targets.

### role.yaml canonical format

```yaml
name: security-engineer
slug: security-engineer
title: "Security Engineer"
rationale: "Resolves 3 coupling hotspots in src/codrag/auth/; owns session/token code; addresses security concept violations."

vector:
  domains: [auth, crypto, session, permissions]
  architecture_layers: [infrastructure, service]
  hub_files:
    - src/codrag/core/auth.py
    - src/codrag/services/session.py
  modules_owned: [src/codrag/core/auth, src/codrag/services/session]
  modules_read_only: [src/codrag/api/routers]
  modules_out_of_scope: [packages/ui, packages/vscode]

persona:
  tone: "precise, skeptical, paranoid by design"
  style: "terse, flags risks early, cites concepts by id"

tools:
  required: [codrag, codrag_search, codrag_impact, codrag_concepts]
  optional: [codrag_audit]
  forbidden: [Bash(rm *), Bash(git push *)]

knowledge:
  max_chars_practitioner: 4000
  max_chars_executive: 1500
  include_concepts_by_tag: [security, auth]
  include_antibodies_by_anchor: modules_owned

fitness:
  current_score: 0.82
  drift_trend: stable
  last_evaluated: 2026-04-13T21:00:00Z
```

This format is the contract. All emissions are pure functions of it (plus the live knowledge graph state).

## Per-target emission

### Paperclip (Phase 88 — already specified)

- `POST /agents` with `{ name, promptTemplate, scope, tools }` where `promptTemplate` is the concatenation of AGENTS.md + SOUL.md + KNOWLEDGE.md.
- Drift sync via `PATCH /agents/:id` when role spec changes.
- No auto-delete; eliminated roles flagged for review.

### OpenClaw (Phase 94 — verified zero-glue)

- `openclaw.soul.md` contains the persona, rules, tool allowlist.
- OpenClaw's `mcporter` skill connects to CoDRAG's stdio MCP server; tool allowlist is enforced per-agent.
- Channels (Slack, Discord, WhatsApp) surface the agent via OpenClaw's gateway — relevant for the "CoDRAG Reporter" example Phase 94 describes.

### Claude Code (Phase 103 — new)

- `.claude/agents/<slug>.md` with frontmatter: `name`, `description`, `tools`.
- System prompt body is persona + scoped atlas + antibodies + gotchas.
- Claude Code's `Task` tool dispatches to the subagent with a fresh context window — perfect for progressive disclosure.

### Cursor / Windsurf / others (Phase 103 — as formats emerge)

- Cursor's subagent format is still evolving. We emit whatever their convention settles on, and fall back to generating an IDE-appropriate rule file variant when true subagents aren't supported.

### Generic / fallback

- A format-agnostic `AGENT.md` that any MCP-capable host can consume as instructions.

## How Phase 103 features map to the architecture

Revisiting Phase 103 features F1–F7 with the integration lens:

| Feature | Role spec consumer? | Paperclip impact | OpenClaw impact |
|---|---|---|---|
| F1 Role-projected subagents | **Yes — primary** | Same role specs sync to Paperclip | Same specs emit SOUL.md |
| F2 Slash commands | No (workflow templates) | — | OpenClaw can expose commands too |
| F3 PostToolUse hooks | Partial (antibodies per role) | Paperclip agents get same antibody enforcement via their own hook wiring | OpenClaw agents consume antibody events |
| F4 Skills-as-folders | Yes (Gotchas come from role-scoped concepts) | Skills layer is IDE-only | — |
| F5 Atlas budget / split | Underlies everything | Applies to Paperclip KNOWLEDGE.md too | Applies to OpenClaw KNOWLEDGE.md too |
| F6 Concept seed promotion | **Yes — upstream of everything** | Promoted concepts feed Paperclip persona | Promoted concepts feed OpenClaw SOUL |
| F7 Runtime awareness | Shared live state | Paperclip dashboard can ingest same feed | OpenClaw gateway can surface it |

F0 exclusion policy: applies to all emission targets. Every generated agent file across every runtime must be classified as AGENT_DIRECT in the walker.

## The flywheel

Once the architecture is unified, a virtuous loop emerges:

1. **Observation** recorded in Claude Code session via `codrag_observe`.
2. Observation pattern **promoted** to concept seed.
3. Seed **validated** (anchors + assertions) → active concept.
4. Active concept **assigned to roles** by tag overlap.
5. On next regen, **all four runtimes** receive updated KNOWLEDGE.md / SOUL.md / antibody set.
6. Claude Code subagent now knows what the Paperclip agent learned and vice versa.

This is the argument for CoDRAG as critical infrastructure: **the longer it runs, the smarter the whole agent fleet becomes**, across every runtime, without human curation.

## Integration priorities

From the pool of Phase 64/67/88/94/103 work, these are the highest-leverage pieces to build next *because they make the integration real*:

1. **Unify the role spec** (Phase 88 → formalize `role.yaml`, promote it to the canonical artifact). This is an 80%-done item once Phase 88 ships.
2. **Add Claude Code subagent emission** (Phase 103 F1 — directly derives from Phase 88's Pass 2).
3. **Add OpenClaw SOUL.md emission** (Phase 103 extension — trivial once Phase 88 file gen exists; Phase 94's research already confirmed zero-glue).
4. **Ship the exclusion policy** (Phase 103 F0) so all newly generated files don't pollute the index across every runtime.
5. **Ship the concept promotion flywheel** (Phase 103 F6) so the knowledge graph actually grows.
6. **Runtime awareness block** (Phase 103 F7) emitted consistently across IDE rules, Paperclip dashboards, OpenClaw channels.

## Paperclip — treat as close dependency, not downstream

Re-reading Phase 64/88: Paperclip is not a "nice-to-have customer" of CoDRAG. It is the **orchestration layer** in the layer model. This has implications:

- **API contract stability matters.** Paperclip's REST shape for agent push/pull is a public contract across our system.
- **Role spec changes are API changes.** If we evolve `role.yaml`, we must bump the Paperclip sync version.
- **Dogfooding:** CoDRAG's own dev team should be using a Paperclip-orchestrated agent fleet generated from the CoDRAG index of its own codebase. If we aren't, the loop isn't real.
- **Paperclip plugin (`packages/paperclip-plugin-codrag`)** needs to absorb the emission layer, not just the sync layer.

Recommended: a shared "role-spec-emitter" crate/package that both `codrag` CLI and `paperclip-plugin-codrag` depend on, so there's exactly one implementation of the projection logic.

## OpenClaw — treat as strategic beachhead for community reach

OpenClaw has 347K GitHub stars. Its audience skews toward developers who want local-first, messaging-channel-driven agents. Phase 94 showed integration is zero-glue today. What's missing is:

- **A first-class OpenClaw emission target** in the generator (we have the logic; we need the output path).
- **A reference `CoDRAG Reporter` agent** shipped as an OpenClaw skill preset, so users can drop it into their workspace and get daily codebase health digests in Slack/Discord.
- **Joint case study / blog post** — OpenClaw + CoDRAG as the "local-first code intelligence agent stack."

Recommended: track OpenClaw issues/releases as a product dependency. When they publish new agent conventions, we emit to them. This is cheap leverage — we ride their distribution.

## New questions raised by this integration lens

1. **Should `role.yaml` live in the indexed project's repo or in CoDRAG's data dir?**
   - In-repo: version-controlled with the code, survives CoDRAG reinstall, shareable in PRs.
   - Data-dir: out of the user's way, CoDRAG owns the schema evolution.
   - Likely answer: **both, with data-dir as cache and in-repo as source of truth if present** (like `codrag.toml`).

2. **Do we need a role-spec schema versioning story?**
   - Yes. `role.yaml` should have `schema: 1` at the top, and emitters should gracefully handle older specs.

3. **How do role specs handle multi-project / monorepo?**
   - A role can span projects (security-engineer across frontend + backend). The spec should reference project IDs, not be project-scoped.

4. **Can Claude Code subagents and Paperclip agents coordinate directly?**
   - Yes via CoDRAG observations and concepts as shared state. A Claude Code subagent writes an observation; the next Paperclip run sees it. This is the "shared brain" promise.

5. **What's the update propagation story?**
   - On role spec change: re-emit all target files locally, then sync to Paperclip. OpenClaw picks up changes at gateway restart. Claude Code picks up changes when the file is re-read (no restart needed, since subagents load on-demand).

## Concrete next-up proposal

**Phase 103a — "Unified Role Emission"** (2-3 weeks, does not require rearchitecting):

1. Factor Phase 88's Pass 2 file generator into a target-agnostic core (`core/role_emitter.py`) plus per-target writers.
2. Add `claude_code_agent_writer.py` (new).
3. Add `openclaw_soul_writer.py` (new).
4. Wire `codrag agents generate` to optionally emit to any subset of targets: `--target paperclip,claude,openclaw`.
5. Ship Phase 103 F0 (exclusion policy) in the same PR so new generated files don't pollute indexes.

**Phase 103b — "Flywheel"** (follows 103a):

6. Phase 103 F6 (concept seed promotion) — activates our 366 seeds.
7. Phase 103 F3 (hooks) — enforces antibodies generated from promoted concepts.
8. Phase 103 F4 (skills-as-folders) — surfaces promoted concepts in Gotchas.

At the end of this sequence, CoDRAG is the single role-specification engine for Paperclip + OpenClaw + Claude Code + Cursor, with a living knowledge graph that keeps all four runtimes synced.

## Bottom line

The strategy is clearer now: **CoDRAG is not competing with agent runtimes; it is the knowledge and role authority underneath them.** Phase 88 built that authority for Paperclip. Phase 94 verified it for OpenClaw. Phase 103 extends it to the IDE-local agents that most developers see every day. All three converge on one role spec, one knowledge graph, one source of truth.

This is a defensible moat: anyone can build an indexer, but no one else is positioned to own the role specification that spans orchestration, messaging, and IDE agents simultaneously.
