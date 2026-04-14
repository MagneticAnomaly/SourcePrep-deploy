# 09 — Focused Build Plan

**Purpose:** Pull the conversation together into a decisive, phased build schedule. Preserves the early design wins. Names the agent-lifecycle model. Keeps emission targets and antibody hooks explicitly on the roadmap (deferred, not dropped). Ready to execute.

## The north-star interface (preserved from early design)

**CoDRAG's only footprint in any AGENTS.md / CLAUDE.md / role file is one line:**

> *"On task start, call `codrag(role='<your role>')` — or `codrag()` if unsure — for scoped project context."*

That's it. No atlas dumps. No concept lists. No antibody inventories. No persona prose. No 28K KNOWLEDGE.md.

Everything substantive lives **server-side**, behind that one call. The call returns a scoped sub-atlas weighted by role vector, enriched with active concepts and antibodies relevant to the role, layout-templated per R1, budget-sized per R2.

This is the universal integration. Every agent runtime (Claude Code, Cursor, Windsurf, Copilot, Paperclip, OpenClaw, Managed Agents) gets the same one-liner, makes the same MCP call, receives format-appropriate scoped context. No emission format churn. No role-file regeneration. No drift.

**The content is the product, not the carrier.**

## The agent lifecycle model (the hybrid)

Agents engage with CoDRAG at one of three tiers. They can move between tiers fluidly. Registration is always optional.

### Tier 1 — Anonymous (zero setup)

- Agent calls `codrag()` with no role, no identity.
- Server returns a default project atlas (existing behavior).
- Works immediately in any MCP-capable client.
- **Use case:** ad-hoc Cursor session; one-off investigation; first-time Claude Code user.

### Tier 2 — Role-hinted (stateless, pass a role)

- Agent calls `codrag(role="security")` or `codrag(task="...")` and server infers the role.
- Server computes a role-weighted sub-atlas from default role vectors (the existing `project_atlas_for_role()` path).
- No per-agent state persisted; same call, same response, every time.
- **Use case:** Claude Code subagent dispatch where the Task tool hints a role; Paperclip agents today; the 80% case.

### Tier 3 — Registered (stateful, per-agent tuning)

- User registers an agent in CoDRAG UI: assigns a stable ID, picks a role preset (or custom), opens the file-tree scope tuner, checks in/out files, adjusts role-vector weights, optionally attaches hooks and observation capture.
- Agent authenticates to CoDRAG (session token, project credential, or MCP client ID).
- Calls to `codrag()` return that agent's *user-tuned* projection, not the default.
- **Use case:** long-lived Paperclip agents; OpenClaw messaging-channel agents; enterprise Managed Agents; any case where the team wants curated scope.

The same MCP call works across all three tiers. The server decides what to return based on the caller's state. Clients don't change between tiers — they just get richer responses as users invest more in registration.

### The UI file-tree scope tuner (finish existing work)

Already partly built in the dashboard. The 103b item is **finishing it**:

- File-tree browser with three states per path: **in-scope**, **out-of-scope**, **boosted**.
- Role overlays: *"for my security agent, boost `src/codrag/core/auth/**`; mute `packages/ui/**`."*
- Agent-gallery page: list of registered agents, one per card, click-through to scope-tuner.
- Changes persist to `codrag_data/agents/<agent_id>.yaml` and override server-side sub-atlas generation for that agent.
- F0 exclusion policy applies as a floor — generated agent files are always excluded, regardless of user boosts.

## How this satisfies the "simple AGENTS.md integration" goal

We stop treating AGENTS.md as a canvas and start treating it as a **signpost**. The agent-context file says "go here for context"; the server provides the context. Compare:

**Before (generate content into files):**
- 8 per-IDE rule writers.
- Phase 88 three-file output (AGENTS.md + SOUL.md + KNOWLEDGE.md) per role.
- Atlas bloat in every CLAUDE.md.
- Constant drift between file content and live codebase state.

**After (emit a signpost, serve content live):**
- One line in AGENTS.md/CLAUDE.md/GEMINI.md etc: *"call `codrag(role=...)`."*
- All substance served live via MCP.
- Zero drift — every call returns fresh state.
- Role-weighted sub-atlas, concepts, antibodies, hooks all belong to the server, not the file.

## The phased roadmap (preserves all items, orders them honestly)

Emission targets and antibody hooks are **explicitly scheduled**, not dropped. They sit behind the measurement that validates knowledge-honing first.

### Phase 103 POC (~2 weeks) — *"measure the mechanism"*

Already detailed in `08_POC_EXECUTION.md`. The trimmed R1–R8 runs. Primary deliverable: R3 answers whether knowledge-honing produces measurable lift.

**Outputs:**
- Extended `eval_runner.py` with condition flags.
- Measured layout template, default budget, role-honing lift.
- v2 `codrag(task, role, working_dir, max_chars)` spec.
- 10 active concepts, 4-field temporal schema, 1 PostToolUse observation hook.

**Gate:** R3 shows pattern 1/2/5 → proceed to 103b. Pattern 4 → tune role vectors and re-run before proceeding.

### Phase 103b — *"register and finish the UI"* (~4–6 weeks)

Builds the registered-agent tier and finishes the UI file-tree scope tuner.

- **Registered agent store:** `codrag_data/agents/<agent_id>.yaml` schema. CRUD via dashboard + CLI.
- **Agent authentication:** session/credential/client-id passed through MCP; server resolves to registered agent state.
- **File-tree scope tuner:** in-scope/out-of-scope/boosted toggle per path; per-role overlays; persist to agent record.
- **Sub-atlas override:** when a registered agent calls `codrag()`, server applies the agent's user-tuned overrides on top of default role vectors.
- **F0 exclusion policy (walker + classifier + manifest column).** Prevents the registration-emission feedback loop that would otherwise pollute indexes.
- **F0.5 per-project override file** (`.codrag/index_overrides.yaml`).
- **F5 atlas budget + auto-split** to keep any managed block ≤ 4 KB.

**Ships:** a usable "register your agents, tune their scope, they work better" product surface.

### Phase 103c — *"emission targets"* (~4 weeks)

Adds format-native carriers for clients that can't or won't call MCP — plus the "one-line signpost" version of our managed block for clients that can.

- **Claude Code subagent emission:** `.claude/agents/<role>.md` with the one-line signpost + optional sub-atlas snapshot for offline reference.
- **OpenClaw SOUL.md emission:** stdio MCP integration is zero-glue (Phase 94); this adds a tool-allowlist + role preset.
- **Cursor / Windsurf / Copilot rule emission:** one-line signpost in the native rule format.
- **Paperclip REST sync continues** (Phase 88 work).
- **Unified role-spec emitter** in `core/role_emitter.py` with per-target writers, as designed in `04_INTEGRATION_ARCHITECTURE.md`.
- **Legacy managed-block migration:** existing CoDRAG installs' bloated CLAUDE.md blocks get compressed to the one-liner on next regen; user content preserved via splice markers.

**Ships:** emission architecture from doc 04, but each target emits a signpost + reference snapshot, not a full role-file generation.

### Phase 103d — *"enforcement and autonomous feedback"* (~4 weeks)

Adds antibody hooks and the observation flywheel enforcement layer.

- **F3a PreToolUse hooks** — constraint antibodies that block/modify edits (requires ≥10 active constraint concepts from R5).
- **F3b PostToolUse hooks** — quality antibodies that observe and annotate.
- **F11 Automatic observation capture** — ship the R7 hook broadly; enable opt-in cluster-to-seed pipeline.
- **F6 Concept promotion UI** — assisted promotion with one-click accept; auto-accept rule for high-confidence + anchored + non-duplicate.
- **F12 Temporal validity auto-detection** — flag stale concepts when anchor files drift > 30%.

**Ships:** the "CoDRAG enforces what it knows" story, backed by active concepts (not empty containers).

### Phase 104+ — *"beyond the single build"*

Planning items for after 103d, worth naming so they stay on the radar:

- **Managed Agents emission** (Anthropic's `/v1/agents`, `/v1/sessions`).
- **Cross-project shared memory** with access control (arxiv 2505.18279 pattern).
- **Role-preset marketplace** — teams share tuned role vectors and file-tree scopes.
- **Binary distribution / zero-daemon mode** for cold-start UX parity with Cursor.
- **Public benchmark publication** after internal eval stabilizes (R8-derived numbers).
- **Multi-project monorepo atlas projection** — one agent scoped across multiple indexed projects.
- **Privacy-preserving per-user observation stores**.

## The design discipline

Four principles we apply throughout every phase above:

1. **Signpost, not substance.** Files emitted into client projects point to CoDRAG; they don't duplicate what CoDRAG knows. Substance lives server-side and is served live.
2. **Hybrid lifecycle.** Every feature must work at Tier 1 (anonymous) and scale up to Tier 3 (registered). If a feature requires registration to function at all, it's wrong. If it only adds value at Tier 3, that's fine.
3. **Measured first, generated second.** No emission target ships before R3 confirms knowledge-honing produces lift. No antibody hook ships before concepts are active. The flywheel must spin before we bolt chrome on it.
4. **Trimmed over thorough.** Each phase ships the minimum that validates the thesis for that phase. Scale-up runs follow based on results.

## This week's focus (execution)

1. **Day 1:** extend `eval_runner.py` with `--condition` flag (R8 work).
2. **Day 2:** baseline existing gold queries; tag them by role; add 3–5 security/frontend queries if coverage thin.
3. **Day 3–5:** run R3 (knowledge-honing 2×2 POC) + R1 (layout) + R2 (budget) through the extended harness.
4. **Day 6:** R4 universal API tweak (add optional `task` param); R5 manual concept promotion pass.
5. **Day 7:** R6 schema change; R7 PostToolUse hook implementation.
6. **Day 8–9:** write up results; make decisions; set 103b/c/d priorities based on what R3 said.

Everything beyond this week is planned above; only this week is actively in flight.

## Success at end of POC

- R3 produces a crisp measured answer (any of pattern 1/2/3/5 with clean data).
- The extended harness is our shared infrastructure for all future measurement.
- The `codrag(task?, role?, working_dir?, max_chars?)` v2 spec is documented and backward-compatible.
- 10 active concepts exist on our own repo.
- Observation hook captures real signal (or is explicitly deferred with cause).
- Phase 103b/c/d are prioritized in light of R3's finding (not in the abstract).

## Why this plan holds the whole vision

- **"Universal simple AGENTS.md integration"** — satisfied by the signpost design (one line; substance server-side).
- **"Sub-atlas and concepts weighted to tune"** — satisfied by the existing role projection engine, validated in R3, user-tunable via the file-tree UI in 103b.
- **"UI, file tree, user-scoped RAG"** — satisfied by 103b finishing the existing scope-tuner UI.
- **"Agents can come and go, role or not, register or not"** — satisfied by the three-tier lifecycle (anonymous / role-hinted / registered).
- **"Much is beyond a single build"** — satisfied by the 103a→b→c→d→104+ progression.
- **"Emission targets and antibody hooks on roadmap"** — explicitly scheduled in 103c and 103d respectively; not dropped, just sequenced.
- **"Measured before grand"** — POC is 2 weeks of measurement; every subsequent phase is gated on what the measurements say.

This is the whole thing, focused. Time to execute.
