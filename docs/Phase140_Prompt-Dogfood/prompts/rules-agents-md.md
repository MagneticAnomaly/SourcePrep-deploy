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

## Snapshot 2026-05-17 → updated 2026-05-18 post-cleanup
- Source file SHA: `c880edc924cd` (1296 lines) — unchanged
- Outputs captured:
  - Slot A (SourcePrep self): TBD — the live `AGENTS.md` at this repo's root (clean, single prep-managed block, no double-block bug)
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/rules-agents-md/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/rules-agents-md/powermate-reborn.md) — **post-cleanup**, 103 lines / 5897 bytes (was 196 lines / 11437 bytes with the double-block bug). See Iteration #1.

## Iterations

### 2026-05-17/18: double-block bug — rules-generator does not migrate legacy markers

- **Finding (revised after deeper inspection):** PowerMate's `AGENTS.md` did NOT have stale branding from a missed regeneration — the rules stage actually ran successfully on 2026-05-18T06:11:01Z (per `pipeline_run_metadata.json`, 0.01s elapsed). The bug is more interesting: **the rules-generator appended a fresh `<!-- prep-managed-start ... prep-managed-end -->` block but did not remove the pre-existing `<!-- codrag-managed-start ... codrag-managed-end -->` block.** End result: 196-line file with two managed blocks, two `## Codebase Atlas` headings, two tool tables, two project IDs (the codrag block referenced project `2e356d01...`, the prep block references `6955793f...`).
- **Why this happens (hypothesis):** `_write_agents_md` in `src/prep/core/rules_generator.py` probably finds-and-replaces content between `prep-managed-start`/`prep-managed-end` markers. When only the OLD `codrag-managed-*` markers exist, the splicer sees no match for `prep-managed-*` and appends a brand-new block, leaving the legacy block untouched.
- **Impact:** Any client project that was indexed under the old `codrag` naming and re-indexed under `prep` ends up with a bloated, contradictory AGENTS.md telling downstream agents to call `codrag` AND `prep` against two different project IDs.
- **Verdict — user decision (2026-05-18):** **Do not fix the rules-generator.** The legacy migration is not worth fixing in code. Manually clean up the affected files as we encounter them.
- **Action taken:** Manually deleted the entire `<!-- codrag-managed-start ... codrag-managed-end -->` block (lines 3-94) from `tests/eval/real_repos/PowerMateReborn/AGENTS.md`. Snapshot re-captured to reflect the post-cleanup state (103 lines).
- **Audit done:** Confirmed our own repo's `AGENTS.md` does NOT have the legacy block (`grep -c codrag-managed AGENTS.md` returned 0). So this is a one-off for PowerMate within Phase 140 scope.
- **Open question (not blocking):** Are there other client projects (beyond PowerMate) that were indexed pre-rename and need similar manual cleanup? Outside Phase 140 scope unless we encounter them.

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
