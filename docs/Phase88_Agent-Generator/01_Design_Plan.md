# Phase 88 — Agent Generator: Universal Two-Pass Role Architect

**Date:** 2026-04-08
**Status:** Design finalized
**Scope:** Build a universal agent description generator that derives optimal Paperclip agent teams from CoDRAG's epistemic knowledge graph, replacing hardcoded team definitions with structurally-grounded, auto-generated role files
**Dependencies:** Phase 83 (Audit Redesign — structural mode findings), Phase 67 (HR Agent Architecture — role file format, RoleVector scoring, drift detection)
**Predecessor:** `paperclip-agent-builder-v3.md` (hardcoded), Phase 67 HR-concept-adapter research

---

## Executive Summary

Today, Paperclip agent teams are defined manually — someone writes a prompt file like `paperclip-agent-builder-v3.md` that hardcodes roles, responsibilities, and knowledge scope. This doesn't scale: as codebases evolve, roles drift from reality, knowledge scopes bloat (the 28K boilerplate problem), and gaps emerge where no agent covers a domain.

Phase 88 replaces this with a **Universal Two-Pass Generator** that acts as a "Role Architect." Pass 1 reads the codebase's structural reality (via Phase 83 audit intelligence) to determine *what roles should exist*. Pass 2 generates the exact file layout specified by Phase 67's HR architecture (AGENTS.md, SOUL.md, KNOWLEDGE.md per role), with knowledge strictly scoped via RoleVector-filtered sub-atlas generation.

The result: agent teams that are structurally grounded, automatically scoped, drift-detectable, and natively syncable to Paperclip.

---

## Design

### Two-Pass Architecture

#### Pass 1: Discovery & Org Design (Gap & Drift Analysis)

The generator does not rely on templates or manual input. It reads the physical codebase reality to assess what is missing or breaking.

**Inputs from CoDRAG Engine:**

| Input | Source | What It Provides |
|-------|--------|-----------------|
| Module hierarchy & domain vectors | `codrag()` structural overview | Module count, diversity, architecture layer spread, orphaned domains |
| Coupling hotspots | `codrag_audit()` structural mode | Files carrying too much weight, requiring dedicated agent attention |
| Hub concentration risk | `codrag_audit()` structural mode | Over-centralized logic that needs architectural stewardship |
| Concept violations & architectural drift | `codrag_audit()` + `codrag_concepts()` | Where reality departs from planned intent |
| Import cycle risks & boundary violations | `codrag_audit()` structural mode | Module boundary health, isolation failures |
| Current Paperclip workforce | Paperclip API (`GET /agents`) | Existing deployed agents for drift comparison |

**Action (Thinking LLM):**

The LLM receives the structural signals and reasons about organizational needs:

- 10 coupling hotspots in the UI module with severe boundary violations --> propose a "UI Architect" to resolve localized structural failures
- Heavy infrastructure modules with no agent coverage --> propose an "SRE / DevOps Agent"
- Auth + payments + API domains with security concept violations --> propose a "Security Specialist"
- Small codebase with few modules --> propose fewer, more generalist roles instead of specialists

**Drift Evaluation (when existing agents are present):**

Compare the structural analysis against the currently deployed Paperclip workforce using RoleVector fitness scoring:

| Fitness Score | Recommendation |
|--------------|----------------|
| > 0.8 | Healthy — no action |
| 0.6 - 0.8 | Minor drift — suggest priority reordering, file scope update |
| 0.4 - 0.6 | Significant drift — recommend role description update |
| < 0.4 | Critical — propose elimination, merger, or promotion to new role |

Cross-role analysis detects overlap (merge candidates), gaps (new hire needed), and over/under-specialization.

**Output: The Proposed Roster**

A list of specific job titles, the structural rationale for each (e.g., "resolves 3 coupling hotspots in `src/codrag/mcp/`"), and the mapped primary modules/domains for execution.

---

#### Pass 2: Generation & Provisioning (Phase 67 Onboarding)

Once the roster is finalized, the system builds the exact filesystem layout specified by Phase 67's HR-concept-adapter.

**Action (Instruct LLM + Auto-Populate Vetting):**

For each role in the roster, the generator:

1. Runs RoleVector mappings against the knowledge graph to extract precise contextual bounds
2. Generates role-filtered sub-atlas (only hub files, module summaries, and graph centralities within the role's scope)
3. Produces three files per role in `agents/<RoleName>/`

**Output Files:**

**1. `AGENTS.md` (Behavioral Guardrails)**
- Identity statement and priority-ranked tasks
- Explicit CoDRAG integration constraints:
  - Must call `codrag(role="<role_slug>")` on task start
  - Must call `codrag_impact` before modifying files
  - Must call `codrag_audit(scope="<owned_modules>")` for structural health checks
- Reporting lines and collaboration axes
- Role vector scoring metadata for HR audit

**2. `SOUL.md` (Identity & Values)**
- Tone and communication style (derived from role type — an SRE agent communicates differently than a UX agent)
- Behavioral boundaries based on reporting lines
- Escalation rules (when to defer to another agent vs. act independently)
- Personality traits aligned with the role's function

**3. `KNOWLEDGE.md` (Strictly Scoped Injection)**
- Resolves the 28K boilerplate problem: no global atlas dump
- Contains *only* module summaries, graph centralities, and hub files within the agent's vetted RoleVector scope
- Generated via Phase 67's role-filtered sub-atlas generation
- File-path-specific context: which files this agent owns, which it should read but not modify, which are out of scope

---

### Sync & Lifecycle

Once files are generated on disk, the system engages its Paperclip Sync Client:

```
1. Read generated agents/<RoleName>/ directories
2. For each role:
   a. Check if agent exists in Paperclip (GET /agents?name=<role_slug>)
   b. If new: POST /agents with promptTemplate assembled from AGENTS.md + SOUL.md + KNOWLEDGE.md
   c. If existing: PATCH /agents/:id with updated promptTemplate
   d. If eliminated (drift score < 0.4): flag for manual review (no auto-delete)
3. Report sync results: created N, updated M, flagged K for review
```

**No auto-deletion.** Agents flagged for elimination require manual confirmation. The generator recommends; a human (or a designated oversight agent) decides.

---

### Generation Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Fresh generation** | No existing agents + CoDRAG project indexed | Full Pass 1 + Pass 2 from scratch |
| **Drift adaptation** | Existing agents + CoDRAG project re-indexed | Pass 1 compares current vs. deployed, Pass 2 regenerates only changed roles |
| **Adoption** | Existing agents but no CoDRAG-generated files | Pass 1 evaluates existing roles against codebase, Pass 2 enriches with CoDRAG intelligence |
| **Dry run** | Any trigger + `--dry-run` flag | Full analysis but no file writes or API calls — outputs proposed roster + diff |

---

### RoleVector Scoring

The mathematical core that connects structural signals to role definitions:

```
RoleVector(role) = weighted combination of:
  - domain_affinity[d]     : how strongly this role maps to each domain tag
  - module_coverage[m]     : which modules fall within this role's responsibility
  - architecture_layer[l]  : which layers (infra, service, API, UI) this role operates in
  - hub_ownership[h]       : which hub files this role is the primary steward of

Fitness(role, codebase) = cosine_similarity(RoleVector(role), CodebaseVector(current_state))
```

Fitness is computed per-role during drift evaluation and determines whether the role is still aligned with codebase reality.

---

### Knowledge Scope: Solving the 28K Problem

The key innovation over hardcoded agents: **KNOWLEDGE.md is role-filtered, not global.**

Current state (hardcoded): Every agent gets a copy of the full atlas. For a large project this means 28K+ tokens of boilerplate context that the agent mostly ignores, wasting context window and slowing response.

Phase 88 approach:
1. Compute RoleVector for the role
2. Query the knowledge graph for entities within the RoleVector scope
3. Generate a sub-atlas containing only:
   - Module summaries for owned modules
   - Hub files within scope (with dependent counts)
   - Relevant concepts anchored to owned modules
   - Cross-cutting concerns that affect owned modules
4. Result: a KNOWLEDGE.md that is typically 2-5K tokens, focused and actionable

---

## Implementation Plan

### Stage 1: Roster Engine (Pass 1)

**New file:** `src/codrag/core/agent_generator.py`

**What to build:**
1. `discover_roles()` — Collects structural signals from CoDRAG (module map, audit findings, concepts, hub files)
2. `propose_roster()` — Sends structural signals to Thinking LLM with a structured prompt, receives proposed roles with rationale
3. `evaluate_drift()` — Compares proposed roster against existing Paperclip agents using RoleVector fitness scoring
4. Roster data model: `ProposedRole(title, slug, rationale, modules, domains, layers, hub_files)`
5. Unit tests: mock structural inputs, verify roster proposals make sense for known codebase shapes

### Stage 2: RoleVector & Fitness Scoring

**New file:** `src/codrag/core/role_vector.py`

**What to build:**
1. `RoleVector` dataclass — domain affinity, module coverage, architecture layer, hub ownership vectors
2. `compute_role_vector()` — Derives RoleVector from a role's proposed modules/domains
3. `compute_codebase_vector()` — Derives current codebase state vector from CoDRAG index
4. `fitness_score()` — Cosine similarity between role vector and codebase vector
5. Cross-role analysis: overlap detection, gap detection, specialization balance
6. Unit tests with synthetic vectors to verify fitness scoring edge cases

### Stage 3: File Generator (Pass 2)

**New file:** `src/codrag/core/agent_file_gen.py`

**What to build:**
1. `generate_agents_md()` — Produces AGENTS.md from role definition + CoDRAG integration constraints
2. `generate_soul_md()` — Produces SOUL.md from role type + reporting lines + LLM-generated personality
3. `generate_knowledge_md()` — Produces KNOWLEDGE.md via role-filtered sub-atlas (the 28K solution)
4. `write_role_directory()` — Creates `agents/<RoleName>/` with all three files
5. Sub-atlas generation: filter the project atlas by RoleVector scope, emit only in-scope entities
6. Integration tests: generate files for a mock project, verify correct scoping

### Stage 4: Paperclip Sync Client

**Files to modify:**
- `packages/paperclip-plugin-codrag/` — Add sync methods to existing plugin

**What to build:**
1. `sync_roster()` — Pushes generated roles to Paperclip via REST API
2. `diff_roster()` — Compares local generated files vs. Paperclip-deployed agents, reports differences
3. Assembly logic: combine AGENTS.md + SOUL.md + KNOWLEDGE.md into a single `promptTemplate` for Paperclip
4. Dry-run mode: full analysis output without API calls
5. Error handling: Paperclip API failures, partial sync recovery, conflict detection

### Stage 5: CLI & MCP Integration

**Files to modify:**
- `src/codrag/cli.py` — Add `codrag agents generate`, `codrag agents drift`, `codrag agents sync` commands
- `src/codrag/mcp_tools.py` — Expose generation as a new MCP tool or extend `codrag_audit` with agent recommendations

**What to build:**
1. CLI commands:
   - `codrag agents generate [--dry-run]` — Full fresh generation
   - `codrag agents drift` — Drift analysis report
   - `codrag agents sync [--dry-run]` — Push to Paperclip
   - `codrag agents adopt <path>` — Import existing agents and enrich
2. MCP integration: decide whether this is a new tool (`codrag_agents`) or an extension of existing tools
3. Output formatting: Markdown report for CLI, structured JSON for MCP

### Stage 6: Dogfooding & Tuning

**What to do:**
1. Run the generator against CoDRAG's own codebase — does it propose sensible roles?
2. Compare generated roster against the manually-built `paperclip-agent-builder-v3.md` — are the generated roles better aligned?
3. Measure KNOWLEDGE.md sizes — are they in the 2-5K target range?
4. Test drift detection: modify the codebase, re-run, verify drift is detected
5. Test Paperclip sync round-trip: generate --> sync --> verify agents in Paperclip --> modify code --> drift report
6. Collect feedback on generated SOUL.md quality — are agent personalities useful or noise?

---

## Success Criteria

1. **Structurally grounded** — Every proposed role has a traceable rationale linking it to specific structural signals (modules, hotspots, concept violations)
2. **Knowledge scoping works** — KNOWLEDGE.md files are 2-5K tokens (not 28K+), containing only in-scope entities
3. **Drift detection accurate** — Fitness scoring correctly identifies roles that have drifted from codebase reality
4. **Paperclip sync works** — Generated roles can be pushed to Paperclip via API and are functional
5. **Dry-run is useful** — Operators can preview the full proposed roster and diff before committing
6. **No auto-deletion** — Eliminated roles are flagged for review, never auto-removed
7. **Modes work** — Fresh generation, drift adaptation, adoption, and dry-run all produce correct output
8. **Dogfooding validates** — Running against CoDRAG's own codebase produces roles at least as good as the manual builder

---

## Resolved Questions

1. **Fresh vs. incremental generation** — Both supported. Fresh generation runs full Pass 1 + Pass 2. Drift adaptation only regenerates changed roles. Mode is auto-detected from presence of existing agents.
2. **Auto-deletion of roles** — No. Eliminated roles are flagged for human review. The generator recommends, it doesn't unilaterally act.
3. **KNOWLEDGE.md scope** — Strictly role-filtered via RoleVector. Sub-atlas generation replaces global atlas dump.
4. **Paperclip vs. file-only** — Both. Files are always generated on disk. Paperclip sync is a separate, opt-in step.
5. **New MCP tool vs. extension** — TBD during Stage 5. Likely a new `codrag_agents` tool given the distinct purpose, but could be an agent recommendation mode on `codrag_audit`.
6. **LLM dependency** — Pass 1 roster proposal requires a Thinking LLM. Pass 2 file generation uses Instruct LLM for SOUL.md personality. Both are optional-degradation: without LLM, the system can still produce template-based roles from structural signals alone.

---

## Future Work (Roadmapped)

- **Agent performance feedback loop** — Track which generated agents perform well in Paperclip (task completion, quality scores) and feed that signal back into RoleVector tuning. Agents that consistently underperform have their roles adjusted automatically.
- **Multi-project team generation** — Generate a unified team across multiple CoDRAG-indexed projects (e.g., a monorepo with frontend + backend + infra).
- **Real-time drift alerts** — Instead of on-demand drift analysis, the CoDRAG watcher triggers drift re-evaluation when structural changes exceed a threshold, pushing notifications to Paperclip.
- **Role evolution history** — Track how roles change over time (what was added, removed, merged) as a form of organizational memory.
