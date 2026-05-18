# Rules — AGENTS.md (managed block, shipped to clients)

**File:** `src/prep/core/rules_generator.py` — `_build_managed_content()` / `_write_agents_md()` (~line 760)
**Symbols:** `_build_managed_content`, `_write_agents_md`
**Invoked by:** CLI + API after atlas generation; written to `<client-repo-root>/AGENTS.md`
**Pipeline stage:** rules (post-atlas)
**Output schema:** markdown with `<!-- prep-managed-start --> ... <!-- prep-managed-end -->` markers; user-authored content outside the markers is preserved
**Status:** baseline

## Purpose
The AGENTS.md content shipped to **client projects** that use SourcePrep. Not an LLM call — fully templated — but it's the *prompt* that every downstream AI agent (Claude Code, Cursor, Windsurf, Copilot, Cline, Roo, Zed, etc.) reads first when working in a SourcePrep-indexed repo. Changes to this content alter how every AI agent in every client project behaves.

This is the single highest-leverage "prompt" in Phase 140: one edit affects every IDE on every project worldwide that uses SourcePrep.

## Grounding (inputs)
Template inputs (deterministic, not LLM):
- Project ID (for routing in MCP tool calls)
- Codebase Atlas (embedded inline)
- Per-IDE adjustments (Claude / Cursor / Windsurf / Copilot etc. — `_write_*` functions)
- Tool call instructions (hardcoded in `_build_managed_content`)

## Output schema
Markdown. Required structure:
1. Routing block: `prep_project_id` + "ALWAYS include this in tool calls"
2. Tool table (6 MCP tools + when to use each)
3. Atlas (IDENTITY / STACK / WORKSPACE MAP / CROSS-CUTTING)
4. Refresh hints
5. `<!-- prep-managed-start --> ... <!-- prep-managed-end -->` markers around the managed block

## Known issues / hypotheses
- **Highest blast radius**: every edit here ships to every client project. Iterations MUST go through extra-careful capture and review.
- **Aggressive tone**: instructions are deliberately aggressive ("IMMEDIATELY call", "No announcements"). Hypothesis: tone could be softer without losing compliance, since SourcePrep already auto-approves MCP calls. Worth A/B testing on real agent sessions.
- **Tool-list staleness**: the table of 6 tools is hardcoded. If a tool is renamed (`hi_prep` → `prep`), this file has to be updated by hand. Already happened — verify it's current.
- **Brand split** (memory: `project_brand_split.md`). User-facing copy must say "SourcePrep" / "sourceprep.io"; tool calls / project IDs / env vars stay `prep` / `PREP_*`. Audit current output for the split.
- **Marketing voice** (memory: `feedback_marketing_voice.md`). Lead plain-language, jargon as supporting detail. AGENTS.md is the first thing an agent reads — its voice matters.

## Snapshot 2026-05-17
- Source file SHA: `c880edc924cd` (1296 lines)
- Outputs captured:
  - Slot A (SourcePrep self): TBD — the live `AGENTS.md` at this repo's root (currently produces "prep"/"SourcePrep" naming correctly)
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/rules-agents-md/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/rules-agents-md/powermate-reborn.md) — **last regenerated 2026-04-20, before the codrag→prep rename. See Iteration #1 finding below.**

## Iterations

### 2026-05-17: baseline capture surfaces stale-branding finding

- **Finding (not an iteration on prompt copy):** PowerMate's `AGENTS.md` still uses the legacy `codrag` / `CoDRAG` naming throughout the managed block (lines 1-35+ in the captured file). The file was last regenerated on 2026-04-20 — before the project rename. The rules-generator code today produces `prep` / `SourcePrep` naming correctly (verified against this repo's own `AGENTS.md`), so this is **not a prompt-copy bug — it's a regeneration-cadence bug.**
- **Hypothesis:** Any client project indexed before the rename and not re-indexed since carries stale branding. We have no automatic detection or re-trigger for "rules content drifted because the generator changed."
- **Verdict:** **n/a (not a prompt change).** Logged as a structural finding to address outside Phase 140:
  - Option 1: Add a "regenerate-rules-on-version-bump" hook to the daemon when the rules-generator's managed-content hash changes.
  - Option 2: Surface a stale-AGENTS.md warning in `prep`'s ambient context when a client project's managed-block content differs from what the current generator would produce.
  - Option 3: Document it as a known limitation and recommend `prep rules` as a periodic maintenance command.
- **Follow-up:** Manually run `prep rules` against PowerMate to regenerate a fresh AGENTS.md, then re-capture as the actual prompt-copy baseline.

## Open questions (revised)

- Pre-existing questions stand. Plus: does the rules-generator have any notion of "managed-content version" that could trigger re-runs on bump?

## Open questions (original list)
- Should the aggressive tone be softened now that auto-approve is universal?
- Should the embedded atlas be summarized (vs verbatim) to keep AGENTS.md under a token budget for context-constrained agents?
- Should per-IDE writers diverge meaningfully, or is one canonical content + light per-IDE wrapper enough?

## Cross-references
- Memory: `project_brand_split.md`, `feedback_marketing_voice.md`, `feedback_agents_md_in_graph.md`
- Sibling: [hr-agents-md](./hr-agents-md.md) — per-role AGENTS.md for SourcePrep's *own* HR agent (different surface entirely)
- AGENTS.md generation pipeline documented in CLAUDE.md (this repo)
