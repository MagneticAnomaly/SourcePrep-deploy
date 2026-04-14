# 02 — Feature Proposals

Concrete designs for the top seven items on the Phase 103 roadmap. Each feature has: scope, artifact shape, emission logic, budget, and open questions.

## F1. Role-projected subagents

**Outputs:** `.claude/agents/<role>.md` per configured role.

**Artifact shape:**
```markdown
---
name: security-engineer
description: Security-focused reviewer. Use for auth, crypto, session, permissions work.
tools: Read, Grep, Glob, codrag_search, codrag_impact, codrag_concepts
---
You are a security-focused engineer reviewing this codebase.

## Scoped atlas (role=security, detail=practitioner)
[role-projected atlas: ~1200 chars]

## Active concerns
- Constraints: {constraint concepts tagged security}
- Past findings: {observations tagged security, last 30 days}

## Antibodies in scope
- {antibodies with security-tagged anchors}

## Canonical files
- src/codrag/core/auth.py — authentication entrypoint
- [etc, from role projection]

## Gotchas
- {extracted from security-tagged incidents/concepts}

<!-- codrag-role-hash:<hash> generated:<timestamp> -->
```

**Emission logic:** New `rules_generator._write_claude_subagents(roles: list[str])`. Reads roles from `codrag_data/ui_config.json` (user-selected). Calls `role_projection.project_atlas_for_role()` to get file list + budget-clipped atlas. Merges with concepts/antibodies filtered by tag overlap with role vector.

**Budget:** 2 KB per subagent. Up to 5 subagents by default = 10 KB on disk but **zero cost to cold-start context** (subagents only load when Task-dispatched).

**Open:** Default role set? Proposal: `security`, `frontend`, `backend`, `testing`, `documentation`. Others opt-in via CLI.

**Effort:** M. Atlas projection exists; emission + format is new.

---

## F2. Slash commands

**Outputs:** `.claude/commands/codrag-*.md`

**Artifact shape (minimal):**
```markdown
---
description: Review a file with impact analysis, concepts, and antibodies.
argument-hint: <file-path>
---
Review {{1}}. Steps:
1. Call codrag_impact with file="{{1}}"
2. Call codrag_concepts with anchor="{{1}}"
3. Summarize blast radius, relevant concepts, antibody firings. Flag risks.
```

**Emission logic:** Static list of 6 commands shipped with CoDRAG, written by `rules_generator._write_claude_commands()`. Content is fixed (not project-specific) for v1. v2 adds project-custom commands from user config.

**Commands (v1):** `codrag-onboard`, `codrag-review`, `codrag-plan`, `codrag-investigate`, `codrag-health`, `codrag-concept`.

**Budget:** ~200 chars per command. Off the cold-start path (commands are invoked, not loaded by default).

**Open:** Should commands be opt-in or default? Proposal: default. They're tiny and discoverable.

**Effort:** S.

---

## F3. PostToolUse hooks

**Outputs:** additions to `.claude/settings.json` — `hooks.PostToolUse` entries.

**Artifact shape (settings.json fragment):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "codrag hook post-edit \"$CLAUDE_TOOL_FILE_PATH\"" }
        ]
      }
    ]
  }
}
```

**`codrag hook post-edit <file>` does:**
1. Compute impact (blast radius) for `<file>`; if > threshold, print `WARN: editing hub file, N dependents`.
2. Fetch concepts anchored to `<file>`; if any, print 1-line reminder per concept.
3. Check antibodies registered for `<file>`; if any fire on recent diff, surface as `WARN`.
4. Exit 0 (advisory) unless user has `enforcement=blocking` in settings.

**Performance:** Target p95 < 150ms. Uses SQLite queries, not full atlas rebuild.

**Emission logic:** `mcp_config._ensure_claude_settings()` extended to write hooks block when user runs `codrag install --hooks`. Opt-in to avoid surprising users.

**Budget:** zero on prompt; cost is runtime latency per edit.

**Open:** Do we want Stop hooks too? (E.g., "on turn end, remind about uncovered tests.") Probably v2.

**Effort:** M. Hook script + CLI subcommand + install flow.

---

## F4. Skills as folders

**Outputs:** `.claude/skills/codrag/` directory with `SKILL.md`, `references/`, `scripts/`.

**Artifact shape:**
```
.claude/skills/codrag/
├── SKILL.md                    # frontmatter + description + gotchas
├── references/
│   ├── tools.md                # detailed tool calling guide
│   ├── concepts.md             # top 10 active concepts for this project
│   └── antibodies.md           # active antibodies + enforcement mode
└── scripts/
    ├── impact.sh               # wrapper for codrag_impact
    └── diff-concepts.sh        # show concept drift since last run
```

**SKILL.md Gotchas section is derived:**
- Top 5 `failure` or `constraint` concepts become bullet points.
- Antibodies with recent fires become "watch out" entries.
- Observations flagged `pitfall` become entries.

**Budget:** SKILL.md ≤ 2 KB (loads when skill is invoked). References are on-demand.

**Migration:** Existing `.claude/skills/codrag.md` single file is moved to `.claude/skills/codrag/SKILL.md` on next rules-regeneration. Preserve any user content.

**Effort:** M. Mostly layout and derivation logic.

---

## F5. Atlas budget + auto-split

**Problem:** The managed block in CLAUDE.md can exceed 200 lines on large projects (our own repo is already at 293 lines total). The best-practices repo's research says agents ignore sections as files grow.

**Proposal:**
- Hard budget: managed block ≤ 4000 chars (roughly 80 lines).
- Over budget: emit full content to `.claude/rules/codrag-atlas.md`, keep a ≤ 1200 char summary in CLAUDE.md with a `@.claude/rules/codrag-atlas.md` import pointer.
- Preserve splice markers in both files.

**Artifact shape (split mode CLAUDE.md block):**
```
<!-- codrag-managed-start -->
## CoDRAG Integration
Project: <name> (id: <uuid>)
Stack: <one-line summary>
Role tools: codrag, codrag_search, codrag_impact, codrag_audit, codrag_observe, codrag_concepts
Full atlas: @.claude/rules/codrag-atlas.md
<!-- codrag-managed-end -->
```

**Effort:** S. Existing writers need char counting + conditional split.

---

## F6. Concept seed promotion

**Problem:** 366 seeds, 0 active. Seeds are insight we've already extracted but don't surface.

**Proposal:**
1. Add `codrag concept promote-ready` CLI — lists seeds with ≥ 1 anchor to an existing file and a testable assertion, ready for promotion.
2. Dashboard UI: one-click promote with human review.
3. On promotion, a concept is automatically considered for artifact emission (atlas inline note, skill reference, antibody).
4. Promote-rate target: 10% of seeds → active within 30 days of the feature shipping.

**Emission downstream:**
- Constraint concepts → antibody registry (F3).
- Rationale concepts → `.claude/skills/codrag/references/concepts.md` (F4).
- Pattern concepts → convention mining dataset (F10 in roadmap).

**Effort:** M. Mostly UX + criteria for "promote-ready."

---

## F7. Runtime awareness

**Proposal:** A separate small file `.claude/rules/codrag-runtime.md`, updated by the daemon every time it starts or when `codrag serve` boots.

**Artifact shape:**
```markdown
<!-- codrag-runtime-start -->
# Runtime (live)
Updated: 2026-04-13T21:04:00Z

- daemon: :8400 (pid 4213, uptime 2h14m)
- dashboard: :5174 (running)
- last index rebuild: 2h ago (incremental, 3 files)
- recent activity: 7 files edited in last 24h
- hot modules (last 24h): src/codrag/services/pipeline, src/codrag/mcp
- open worktrees: 2 (busy-swirles, selfheal-fixes)
<!-- codrag-runtime-end -->
```

**Emission logic:** Daemon writes this on startup + every 15 min heartbeat. `rules_generator` imports the block into CLAUDE.md via `@.claude/rules/codrag-runtime.md` OR leaves it as a standalone imported rule file.

**Budget:** ≤ 500 chars. Strict.

**Risk:** File-write churn if we refresh too aggressively. Mitigation: only rewrite if content changed *or* > 15 min since last write.

**Effort:** S. Daemon lifecycle + formatter.

---

## Implementation sequence (suggested)

**Milestone 1 — foundations (2 weeks):**
- F5 atlas budget + auto-split (prerequisite for everything else)
- F2 slash commands (cheap, immediate UX win)
- F7 runtime awareness (cheap, demonstrable)

**Milestone 2 — the differentiators (4 weeks):**
- F1 role-projected subagents (biggest unique asset)
- F4 skills as folders (raises perceived quality)
- F6 concept seed promotion (flywheel input)

**Milestone 3 — enforcement + feedback (4 weeks):**
- F3 PostToolUse hooks (requires F6 concept promotion to have content)
- Stop hooks (small addition to F3 once PostToolUse lands)
- Test-map (roadmap item 8; depends on graph work)

**Milestone 4 — predictive (ongoing):**
- Session-aware context layer (roadmap item 9)
- Cross-session memory compaction (roadmap item 10)

## Dependencies across features

```
F5 (budget) ──┬── F1 (subagents need budget enforcement)
              ├── F4 (skills need budget enforcement)
              └── F7 (runtime must fit budget)

F6 (concepts) ──┬── F3 (hooks consume active concepts/antibodies)
                └── F4 (Gotchas consume active concepts)

F1 (subagents) ── requires role_projection.py (exists)
F2 (commands) ── standalone
F7 (runtime)  ── requires daemon heartbeat write path
```

F5 is the keystone — ship first.

## Metrics for success

| Feature | Metric | Target |
|---|---|---|
| F1 | Users with ≥1 subagent file generated | 30% in 60 days |
| F2 | Slash-command invocations per active project per week | ≥ 3 |
| F3 | Antibody-fire events surfaced via hooks | ≥ 5/project/week |
| F4 | Skills loaded in session (vs flat-file reads) | 80% |
| F5 | Projects with managed block ≤ 4 KB | 100% post-ship |
| F6 | Concept seeds promoted | 10% within 30 days |
| F7 | Projects with live runtime block present | 100% post-ship |

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Too many generated files overwhelm client repos | All features write under `.claude/` or `.codrag/`; visible but contained |
| Hooks break user workflows | Advisory-default, blocking opt-in; every hook has a disable flag |
| Stale artifacts drift from atlas | Hash stamping + freshness warnings + `codrag refresh` |
| User customizations lost on regeneration | Splice markers on every managed file; test for user content preservation |
| Role subagents leak sensitive content cross-role | Role projection filters; explicit tool allowlist per agent |
| Cold-start context bloat from sum of artifacts | Total budget cap; auto-split to on-demand import |
