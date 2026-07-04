# SCRUTINY — PROPOSAL_static-pointer-volatile-context v1 (first pass)

**Date:** 2026-07-04
**Scrutinizer:** Claude (Fable), same session as v1 authoring — *not* a
fresh-eyes pass; a fresh-eyes re-check before PR-2 lands remains
recommended for D1's behavior table.
**Method:** (a) executed the §15 scrutiny checklist literally
(code greps for every marker/consumer the proposal assumed safe);
(b) reverse-engineered the exit criteria back through each mechanism;
(c) resolved verification spikes V1–V3 via official docs, the Claude
Code issue tracker, and Gemini CLI docs; (d) folded in Eric's
2026-07-04 decisions (single-user migration, accept recommendations).

**Verdict:** Design holds. One **critical** defect (D1) found —
a real consumer of the moved content that v1 had only hypothesized
as risk R5. One **high** scope gap (D2). Rest is minor. All fixes
are incorporated in `PROPOSAL_static-pointer-volatile-context-v2.md`;
v1 is marked superseded.

---

## Defects found

### D1 — CRITICAL: MCP server's atlas-dedup reads the hash we are moving

v1 listed "consumers of `prep-atlas-hash`" as risk R5 / checklist
item 1. The grep confirms the risk is **real and load-bearing**:

- `src/prep/mcp/server.py:247-317` — `_project_has_rules_file()`
  checks for rules files AND extracts `prep-atlas-hash` from
  CLAUDE.md (`:293-311`) into `_rules_atlas_hash_cache`.
- `src/prep/mcp/server.py:325-333` — `_extract_atlas_hash()` regexes
  the hash comment out of rules-file content.
- `src/prep/mcp/server.py:1140-1230` — `tool_context()` (Phase 73.4):
  if a rules file exists, `prep()` **skips the atlas** in its
  response ("already in the AI's system prompt"), unless the
  rules-file hash mismatches the current atlas (stale → re-include).
  Second consumer at `:1847`.

**Failure mode if unfixed:** post-split, rules files still exist
(`has_rules=True`) but contain no hash → `rules_hash=None` → the
explicit fallback at `:1158` ("rules exist but no hash — use the old
behavior, skip atlas") suppresses the atlas in `prep()` responses
**forever**, while the tracked rules file no longer carries the atlas
either. Any P-READ client that skipped the volatile file would get
structural orientation from *nowhere*. The freshness re-include
branch (`:1199-1219`) also goes permanently dead.

**Fix (v2 §5.5, work item W1):** repoint existence+hash to
`.sourceprep/AGENT_CONTEXT.md` as the primary source with legacy
rules-file fallback (pre-migration repos keep working); volatile file
missing → `include_atlas=True`. The `_check_atlas_signal`
invalidation path (`:350-374`) carries over unchanged — it already
watches `.sourceprep/atlas_updated.signal`. Semantics are otherwise
identical to today (verified: today's flow also leaves an agent's
in-context atlas stale after a mid-session regen and skips re-send
once the hash cache refreshes — no regression introduced).

### D2 — HIGH: nested registered projects multiply churn inside one git repo

v1's migration section (§9) modeled one project per repo. The
dashboard registry (screenshot, 2026-07-04) shows **three registered
projects nested inside the SourcePrep monorepo**, and git confirms
two of them write tracked files into the *parent* repo:

- `SourcePrep_Website` (path `websites/apps`) →
  `websites/apps/AGENTS.md` and `websites/apps/.cursor/rules/prep.mdc`
  are **tracked** in the CoDRAG repo (plus a tracked
  `websites/GEMINI.md` one level up). Its regenerations dirty the
  parent repo's git status independently of the root project — churn
  ×2 from one repo's perspective.
- `PowerMateReborn` and `smoke-test` (under `tests/eval/`) are
  covered by `.gitignore:103` → harmless, no migration needed.

**Fix (v2 §9.5):** migration is enumerated **per registered project**
(15 entries), not per repo root, with nested/ignored/non-git rows
called out.

### D3 — LOW: volatile file misses the prep-self-output sentinel

`docs_grounding.py:360-380` (Phase 133b) skips prep-generated files
from concept grounding by detecting "SourcePrep structural codebase
intelligence" or `<!-- prep-managed-start -->` in the head. The v1
volatile-file header contained neither literal. Two independent
layers already exclude it (`.sourceprep` in
`DEFAULT_EXCLUDE_DIR_NAMES`, `repo_profile.py:12`, plus gitignore),
but belt-and-braces is cheap: **v2 header includes the phrase
"SourcePrep structural codebase intelligence"** so all three layers
agree. (Positive confirmation from the same grep: the walker
dir-exclude means the volatile file can never re-enter the graph —
the v1 claim checks out, and `index.py:472`'s comment about AGENTS.md
"taking 8s to embed" is independent evidence the split also helps
indexing cost.)

### D4 — MEDIUM: git-worktree sessions run in degraded mode

Not in v1 at all. The volatile file is per-checkout and the daemon
writes only the registered path. This project's workflow leans hard
on sibling worktrees (scrutiny verifiers, phase branches) — sessions
there will see pointer-but-no-file and fall back to `prep()`
(fresh-clone degradation, which D1's fix makes safe: missing volatile
file → `prep()` includes the atlas). Claude Code's documented
cross-worktree pattern is a home-directory import, which we
deliberately do not use (per-user absolute path cannot be committed
to a shared file). **Accepted limitation, documented in v2 §7;**
optional future enhancement noted in v2 §13 (daemon writes the
volatile file into all worktrees it can enumerate — deferred, YAGNI).

### D5 — INFO: C1 seam survives the split unchanged

`tests/test_rules_regen_preserves_atlas.py` monkeypatches
`write_rules_file` and asserts atlas/stats are loaded from disk when
the scope-CRUD caller omits them (rules_generator.py:318-334). The
seam is upstream of the split, so the test survives as-is; v1 §11's
"repurpose" plan stands (assert the atlas lands in the volatile
file). No defect.

### D6 — INFO: the 500-char rules-file sniff is unaffected

`_project_has_rules_file`'s cheap sniff (`"prep-managed" in
content[:500] or "Prep" in content[:500]`, mcp/server.py:287-297)
still matches slim files (markers/"SourcePrep" remain in the managed
head, and e.g. this repo's CLAUDE.md has "SourcePrep" in its first
500 chars regardless). No change needed beyond D1's repoint.

---

## Verification spikes — resolved

| ID | Question | Result | Confidence / source |
|---|---|---|---|
| V1 | Claude Code `@import` of missing file | **Silent skip.** No error, no warning; the `@path` line is dropped from context. | HIGH — docs + GitHub issue #56927 (silent failure for unresolvable import paths) |
| V2 | Approval dialog for in-repo gitignored imports | **Expected: none.** Docs gate the dialog on "external imports" (undefined term, but the canonical gitignored `CLAUDE.local.md` and in-repo `@AGENTS.md` patterns carry no approval caveat). | MEDIUM — inferred; keep the 5-minute live smoke in PR-2 (create tmp project, import gitignored file, observe) |
| V3 | Gemini CLI import support | **Confirmed.** `@file.md` memport syntax; **.md files only** (ours is .md ✓); missing file → *graceful error comment in output* (visible, unlike Claude's silent skip — acceptable; the fallback sentence explains it); circular-import protection; max depth 5. | HIGH — official memport docs |

Consequences: no existence-gating on the pointer line (v1's rejected
"ordering coupling" stays rejected); fallback sentence wording stays;
the P-IMPORT line must remain **bare** (backticks would make it
literal — v1 already regression-tests this, keep that test).

Also confirmed from docs during V1 research: **block-level HTML
comments are stripped before context injection**, and import parsing
skips only code spans/fences — so a bare import line between our two
marker comments is processed normally. v1 §5.3's mechanics hold.

---

## Reverse-engineering pass (exit criteria → mechanisms)

**Exit: `git status` clean after Rebuild All.** Requires every
writer byte-stable given unchanged template. Walked all nine:
claude/agents/gemini/copilot/cline (marker splice, static-only ✓),
cursor (frontmatter + markers, static-only ✓), windsurf new-path
(wholesale rewrite of a fully-managed file, static-only ✓ — R7 sharp
edge noted, unchanged), roo (base file static-only ✓; two mode files
already static ✓), claude_skill (write-once ✓). The
preliminary→full atlas double-write in `post_flight.py` (:98, :159)
hits only the volatile file post-split ✓. The `is_preliminary` flag
renders into the volatile header ✓. Residual mtime churn killed by
the PR-3 `_write_if_changed` guard ✓.

**Exit: branch merges clean.** Requires no volatile bytes in tracked
files (✓ by construction) AND no per-user bytes — caught: v1 already
moves `project_id` (per-daemon UUID) into the volatile file ✓.
Static-template diffs between branches remain possible only across
product versions — legitimate, rare, commit-worthy ✓.

**Exit: fresh clone / worktree works.** V1 resolved (silent skip) +
D1 fix (missing volatile file → `prep()` re-includes atlas) close the
loop: degraded mode now has *two* independent recovery paths (static
fallback instruction + server-side atlas re-include) ✓.

**Checklist item 5 (repos that never run a pipeline):**
`detect_and_regenerate` at MCP-initialize writes slim static blocks;
the volatile file never exists until a pipeline runs; both recovery
paths above apply. By design, not a defect ✓.

---

## Decisions ratified (Eric, 2026-07-04)

| Item | Decision |
|---|---|
| OQ1 file location | `.sourceprep/AGENT_CONTEXT.md` (recommendation accepted) |
| OQ2 file count | Single shared volatile file |
| OQ3 identity line in tracked AGENTS.md | No — keep the fixed point pure |
| OQ4 pointer self-heal in `detect_and_regenerate` | Yes — fold into PR-2 |
| OQ5 timestamp in volatile file | Keep (staleness signal; git-invisible) |
| OQ6 env override for volatile path | Defer (YAGNI) |
| §9.4 client-project comms | **Dropped — single-user install base.** Replaced by a manual, per-registered-project migration checklist (v2 §9.5) executed by Eric/agent after PRs land. No release-notes dependency. |

---

## Disposition

All defects and resolutions are folded into
`PROPOSAL_static-pointer-volatile-context-v2.md`. v1 retained,
marked superseded (phase convention: false starts teach the next
reviewer what to verify).

Remaining recommended checks before/during execution (carried into
v2 §10): the V2 live smoke (5 min), and a fresh-eyes read of the
W1 behavior table since this scrutiny was same-author.
