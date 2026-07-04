# PROPOSAL — Split Managed Rules Blocks into Static Pointer + Gitignored Volatile Context (v1)

**Status:** SUPERSEDED by → `PROPOSAL_static-pointer-volatile-context-v2.md`
(2026-07-04). Scrutiny findings in
`SCRUTINY_v1_static-pointer-volatile-context.md` — headline: risk R5
was a real critical consumer (`mcp/server.py` atlas-dedup, now W1),
and migration must be per-registered-project (nested projects dirty
the parent repo). Retained per phase convention — do not execute
from this version.
**Date:** 2026-07-04
**Author:** Claude (Fable), from research session with Eric on 2026-07-02.
**Phase:** 147 — see `README.md` in this directory.
**Primary file:** `src/prep/core/rules_generator.py`
**Supersedes:** nothing (first proposal in this phase).

---

## §1 Problem statement

SourcePrep's rules generator writes a "managed block" into up to nine
per-IDE instruction files inside every client project (and this repo,
since we dogfood). The block mixes two fundamentally different kinds
of content:

- **Static instructions** — the tool table, "call `prep` first",
  auto-approve snippets. These change only when we ship a new
  template. They are legitimately part of the project's shared,
  git-tracked configuration.
- **Volatile context** — `Last updated:` timestamp, node/edge
  counts, the full Codebase Atlas text, docs-per-module links, focus
  areas, named scopes, and the `project_id`. These change on every
  index rebuild, every scope edit, and (because of the timestamp)
  **on every single regeneration even when nothing else changed**.

Because both kinds live between the same markers in the same tracked
files, every pipeline run dirties git-tracked files. Two distinct
failure modes result:

**FM-1 — Phantom WIP.** An agent session (Claude Code, Cursor, or a
scripted workflow) starts, reads `git status`, sees
`M CLAUDE.md`, `M AGENTS.md`, `M .cursor/rules/prep.mdc`, and
concludes a *different session* left uncommitted work. It then
hedges, asks the user, tries to preserve or merge the "work", or
refuses to branch cleanly. This burned real time repeatedly during
the Phase 145 merge train. It is happening in the current working
tree right now: `.cursor/rules/prep.mdc`, `AGENTS.md`, and
`CLAUDE.md` are all modified purely from daemon regeneration.

**FM-2 — Same-file-tail merge conflicts.** Branch A and branch B
each ran pipelines at different times. Both hold different
timestamps, different atlas text, different counts in the same
region of the same files. Every merge produces conflicts that are
100% noise but must be hand-resolved. Recorded during the
2026-06-29 Phase 145 merges as the "pr-M/pr-N same-file-tail
conflict pattern" (AGENTS.md tail).

History quantifies the churn: **48 commits touch CLAUDE.md, 40 touch
AGENTS.md** in this repo, including pure-noise commits like
`2dae33eb chore(prep-managed): regenerate AGENTS.md / Cursor rule /
CLAUDE.md atlas`.

This is a product defect. Every client project inherits it the day
their pipeline runs twice on two branches.

---

## §2 Evidence — where the churn is manufactured

### §2.1 The unconditional timestamp

`_build_managed_content()` opens with:

```python
# rules_generator.py:482-483
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
stat_parts = [f"Last updated: {now}"]
```

Every write differs from the previous write **by construction**,
even if atlas, stats, and config are all byte-identical. This alone
guarantees FM-1 on every regeneration.

### §2.2 Genuinely volatile payloads in tracked files

| Content | Source lines (rules_generator.py) | Changes when |
|---|---|---|
| Timestamp header | 482–493 | every write |
| node/edge counts | 484–490 (via `_get_current_stats`, 272–295) | every reindex |
| `prep_project_id` + ROUTING banner | 496–504 | per-daemon registration (differs per teammate!) |
| Codebase Atlas (+ `prep-atlas-hash` comment) | 604–611 | every atlas rebuild / enrichment run |
| Docs-per-module section (Phase 124 T9) | 613–623, `_render_docs_per_module_section` 345+ | every T2 rerun |
| Focus Areas | 625–633 | dashboard config edits |
| Scopes (Phase 120) | 635–652 | scope CRUD |

### §2.3 The static remainder

| Content | Source lines |
|---|---|
| Tool table + "call prep first" | 506–519 |
| Audit enrichment snippet | 520–527 |
| Search-intent snippet | 528–531 |
| Concurrency-limits hint (Phase 119 T16) | 532–545 |
| Target-specific instructions (claude/cursor/universal) | 547–602 |
| Fallback + refresh hints | 654–663 |
| Universal-only verbose sections (tool rules, MCP resources/prompts) | 665–698 |

None of this varies per project state. It varies only per product
version.

### §2.4 Regeneration triggers (why "it keeps happening")

| Trigger | Call site |
|---|---|
| Post-Stage-1 preliminary atlas | `services/pipeline/post_flight.py:98` |
| Post-enrichment final atlas | `services/pipeline/post_flight.py:159` |
| Worker-level rewrites | `services/pipeline/workers/__init__.py:1488`, `:1516` |
| Pipeline start (marker-missing repair only) | `services/pipeline/orchestrator.py:1985` → `detect_and_regenerate` |
| Scope CRUD (debounced 2 s) | `api/routers/scopes.py:30` → `schedule_rules_regeneration` (rules_generator.py:298–339) |
| CLI `prep rules` | `cli.py:919` |
| Dashboard "Generate Rules" button | via the same API path |

Note `detect_and_regenerate` (rules_generator.py:143–236) is already
polite — its non-force path (179–201) skips files whose markers are
present. The churn comes from the **post_flight and worker call
sites**, which call `write_rules_file` unconditionally with fresh
atlas/stats.

### §2.5 Files affected (the full blast radius)

From `_detect_targets` (rules_generator.py:1232–1296) and the writer
table (101–111):

| Target | Path | Typically tracked? | Embeds volatile content today? |
|---|---|---|---|
| agents_md | `AGENTS.md` | **yes** | yes (verbose "universal" profile) |
| claude | `CLAUDE.md` | **yes** | yes ("claude" profile) |
| cursor | `.cursor/rules/prep.mdc` | **yes** | yes |
| windsurf | `.windsurf/rules/prep.md` (legacy `.windsurfrules`) | **yes** | yes |
| gemini | `GEMINI.md` | **yes** | yes |
| copilot | `.github/copilot-instructions.md` | **yes** | yes |
| cline | `.clinerules` | **yes** | yes |
| roo_code | `.roo/rules/prep.md` (+2 mode files) | **yes** | yes (base file only; mode files are already static) |
| claude_skill | `.claude/skills/prep.md` | yes | **no** — already static, write-once (931–977). No change needed. |

---

## §3 Root-cause statement

> Volatile, machine-generated, per-daemon state is being persisted
> into files whose contract is "shared, human-curated, version-
> controlled project configuration." The marker system
> (`<!-- prep-managed-start/end -->`) solves *ownership* (who may
> edit which region) but not *volatility* (which region belongs in
> git at all).

The fix is to give the volatile state its own file with the correct
git contract (ignored), and leave behind only a stable pointer.

---

## §4 Alternatives considered and rejected

**A1 — Gitignore CLAUDE.md / AGENTS.md themselves.**
Rejected, two hard blockers: (1) `.gitignore` has no effect on
already-tracked files — every existing repo would need
`git rm --cached`, a destructive migration we cannot automate from a
daemon; (2) these files carry *human-authored* content (this repo's
entire hand-written CLAUDE.md preamble, users' own AGENTS.md
sections) that must remain shared with the team. Only our managed
region is the problem, and you cannot gitignore a region.

**A2 — Skip-if-unchanged writes only (no split).**
Necessary but not sufficient. Dropping the timestamp and comparing
before writing kills the *no-change* churn, but the atlas and counts
genuinely change on every enrichment run, so tracked files still
churn on every pipeline run and FM-2 survives intact. (We adopt the
write-guard anyway as belt-and-braces — see §8.)

**A3 — `.gitattributes` merge driver (`merge=ours` on rules files).**
Rejected: merge drivers must be configured per-clone in
`.git/config` (the `.gitattributes` line alone is inert), which we
cannot do for every contributor/CI environment; it also masks FM-2
without touching FM-1 (files still dirty in `git status`).

**A4 — Reuse `CLAUDE.local.md`.**
Claude Code's official gitignored-personal-instructions file loads
automatically — tempting. Rejected: it is semantically *the user's
personal file*; the daemon writing to it would collide with users
who maintain their own, and it solves nothing for the other eight
targets. Same reasoning rejects hijacking `~/.claude/` paths.

**A5 — `git update-index --skip-worktree` as a stopgap.**
Rejected even as interim mitigation: per-clone, invisible,
notoriously confusing when the file legitimately changes upstream,
and we would be teaching users a footgun.

**A6 — Stop embedding the atlas entirely; rely on `prep()`.**
Seriously considered — the volatile content is largely redundant
with what the `prep` MCP tool returns live, and "prep the context
via MCP" is the product thesis. Rejected *as the whole fix* because
the embedded atlas is deliberate "always-on priming" for agents that
never call tools (the biggest documented failure mode of agent
integrations is agents ignoring MCP and grepping). The pointer
design (§5) preserves priming at the cost of one file-read; targets
with native import (Claude Code, Gemini CLI) lose nothing at all.

---

## §5 Design

### §5.1 The split

`_build_managed_content()` (rules_generator.py:462–700) is split
into two pure functions:

```
_build_static_instructions(target, project_name) -> str
    # §2.3 content only. No datetime call. No stats. No project_id.
    # Deterministic for a given (target, product version).

_build_volatile_context(project_name, atlas_content, included_paths,
                        is_preliminary, stats, project_id) -> str
    # §2.2 content only: timestamp, stats, project_id + ROUTING,
    # atlas (+ hash comment), docs-per-module, focus areas, scopes.
    # Target-independent (one rendering serves all IDEs).
```

A new writer persists the volatile side once per regeneration:

```
_write_volatile_context(project_path, ...) -> bool
    # → <project>/.sourceprep/AGENT_CONTEXT.md   (atomic, via _write)
```

`write_rules_file()` (59–140) calls `_write_volatile_context()`
first, then the per-target writers, which now embed only
`_build_static_instructions(target)` plus a pointer line (§5.3).

### §5.2 The volatile file

**Path:** `.sourceprep/AGENT_CONTEXT.md` (OQ1 discusses the name).

Rationale for the location:

- `.sourceprep/` is already the product's designated per-project
  state directory (embedded-mode indexes, `project.json` pointer
  read by `read_project_pointer` — see rules_generator.py:91–95).
- In this repo it is *already gitignored* (`.gitignore:78`), so the
  dogfood migration is free.
- Files under a gitignored path drop out of the trace graph
  naturally (the Rust walker respects `.gitignore` — cf. the
  `docs_grounding.py:45-47` precedent), which independently fixes
  the "AGENTS.md atlas pollutes the graph" complaint.
- The writer `mkdir -p`s the directory, so standalone-mode projects
  that lack `.sourceprep/` today simply gain it (acceptable: it is
  the product's documented per-project dir).

**Layout:**

```markdown
<!-- auto-generated by SourcePrep. DO NOT EDIT, DO NOT COMMIT.   -->
<!-- Regenerated after every index run. Git-ignored by design.   -->
# SourcePrep Agent Context — <project_name>

Last updated: <ISO8601> | <N> nodes | <M> edges

prep_project_id: <uuid>
**ROUTING: When calling ANY SourcePrep tool, ALWAYS include
`project_id: "<uuid>"` in the arguments.**

<!-- prep-atlas-hash:<12hex> -->
## Codebase Atlas
<atlas text>

## Documentation Map            (Phase 124 T9 section, if present)
...

## Focus Areas
...

## Scopes
...
```

No managed markers needed — the whole file is ours; the header
comment states the contract.

**`project_id` moves here deliberately.** It is a per-daemon
registration UUID: two teammates registering the same repo receive
different IDs, so a tracked `project_id` is a guaranteed FM-2
conflict *between users*, independent of pipeline timing. Runtime
auto-detection from the workspace root already exists as fallback
(`write_rules_file` rules_generator.py:90–95; MCP server resolves
per-workspace too).

### §5.3 Per-target pointer mechanics

Two pointer species, chosen by the target's capabilities:

**Species P-IMPORT (native inline import — zero behavior loss):**

| Target | Pointer line in static block |
|---|---|
| claude (`CLAUDE.md`) | `@.sourceprep/AGENT_CONTEXT.md` |
| gemini (`GEMINI.md`) | `@.sourceprep/AGENT_CONTEXT.md` |

Claude Code documents `@path` imports: expanded at launch, relative
paths resolve against the importing file, max depth four hops,
imports inside code spans/fences are skipped (so the pointer must
NOT be wrapped in backticks). Gemini CLI has the equivalent memport
feature (V3 verifies syntax parity).

Accompanying fallback sentence (also static):

> If the imported context file is missing, this project has not been
> indexed on this machine yet — call `prep()` for live context, or
> start the SourcePrep daemon to generate it.

**Species P-READ (instruction to read the file — one tool call):**

| Target | Wording (in static block) |
|---|---|
| agents_md (`AGENTS.md`) | "**At the start of every task**, read `.sourceprep/AGENT_CONTEXT.md` (if present) for the current codebase atlas, project id, focus areas, and scopes — or call `prep()` for the live equivalent." |
| cursor (`.cursor/rules/prep.mdc`) | same wording |
| windsurf (`.windsurf/rules/prep.md`) | same wording |
| copilot (`.github/copilot-instructions.md`) | same wording |
| cline (`.clinerules`) | same wording (keyword trigger block at 1138–1142 stays — it is static) |
| roo_code (`.roo/rules/prep.md`) | same wording (the two mode files, 1204–1224, are already fully static — untouched) |

All P-READ consumers are agentic tools with file-read capability;
the cost is one read per session. Non-agentic consumers (rare: pure
autocomplete surfaces that inject the md as raw context) lose atlas
priming but keep every instruction — accepted trade-off, recorded as
OQ3.

**claude_skill** (`.claude/skills/prep.md`, 931–977): already
static and write-once. No change.

### §5.4 What remains in each tracked file

After migration, e.g. `AGENTS.md`'s managed region becomes (~40
lines, fixed point):

```markdown
<!-- prep-managed-start -->
## SourcePrep Integration

[tool table — 6 rows]
[call prep first / auto-approve / audit-enrichment / search-intent /
 concurrency-hint / tool-calling-rules / MCP resources & prompts]

**Live project context** (atlas, project id, focus areas, scopes):
read `.sourceprep/AGENT_CONTEXT.md` at task start — or call `prep()`.
If the file is missing, the project has not been indexed on this
machine yet; work normally and call `prep()` once the daemon runs.
<!-- prep-managed-end -->
```

It changes only when the product template changes — a legitimately
commit-worthy event.

---

## §6 `.gitignore` management

New helper in `rules_generator.py` (or `core/gitignore_utils.py` if
we prefer a seam for testing):

```python
_GITIGNORE_ENTRY = ".sourceprep/AGENT_CONTEXT.md"
_GITIGNORE_COMMENT = "# SourcePrep volatile agent context (auto-added; safe to move, keep ignored)"

def _ensure_gitignore_entry(project_path: Path) -> bool:
    """Ensure the volatile context file is git-ignored.

    - No-op when project_path is not a git repo (no .git).
    - No-op when an existing .gitignore already *covers* the path
      (checked with pathspec, already a dependency — index.py:343),
      e.g. this repo's blanket `.sourceprep/` entry.
    - No-op when a negation pattern explicitly re-includes it: the
      user has made a deliberate choice; we do not fight (log INFO
      once instead).
    - Otherwise append comment + entry (atomic via _write), creating
      .gitignore if absent.
    - Sentinel: only ever append once per repo. Recheck-and-append
      on every regen would fight users who deliberately delete the
      line; coverage-check-then-skip naturally provides this as long
      as the entry is present, and the negation clause covers
      deliberate removal. No extra state file needed.
    """
```

Called from `_write_volatile_context()`. Failure is non-fatal
(WARNING log): a missing gitignore entry degrades to today's
behavior for one file instead of nine.

**Embedded-mode nuance:** CLAUDE.md documents `.sourceprep/` as
"git-trackable" for teams that want to commit their index. That is
precisely why we ignore the *specific file*, never the directory.
For repos (like this one) that ignore the whole directory anyway,
the pathspec coverage check makes us a no-op.

---

## §7 Degradation behavior (fresh clone, daemon-less)

State: teammate clones repo; `.sourceprep/AGENT_CONTEXT.md` does not
exist (ignored, never pushed); daemon not yet run.

| Surface | Behavior |
|---|---|
| Claude Code `@import` of missing file | Expected: silently skipped (V1 verifies; docs do not specify). Static fallback sentence covers the semantic gap either way. |
| Gemini CLI import of missing file | V3 verifies. |
| P-READ targets | Wording says "(if present)" — agent proceeds, falls back to `prep()`. |
| First daemon run on the clone | `_write_volatile_context()` recreates the file; `_ensure_gitignore_entry()` is a no-op (entry already committed in .gitignore). Steady state restored with zero tracked-file changes. |

The degraded state is *strictly better* than today's failure mode:
today a fresh clone carries a **stale committed atlas** (silently
wrong context); post-split it carries *no* atlas plus an instruction
to fetch live context.

---

## §8 No-op write guard (belt-and-braces)

Even with the split, tracked files should stop being rewritten when
their content is unchanged — an unchanged rewrite still churns
mtimes, triggers IDE rules-reload, file watchers, and Tauri/VS Code
change badges.

```python
def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False          # byte-identical — leave mtime alone
    _write(path, content)     # atomic (atomic_io), same as today
    return True
```

Adopted by all nine per-target writers (the volatile writer keeps
unconditional `_write`: its timestamp legitimately changes and it is
ignored anyway — though the same guard minus the timestamp line is a
cheap option, see OQ5). Writer return values then become honest
"did anything change" signals, which `write_rules_file`'s result
dict (86, 136–139) already propagates to logs.

---

## §9 Migration

### §9.1 Mechanics (automatic, all repos)

No special-case code needed: the existing marker-splice logic
(`_write_claude_rules` 911–923, `_write_agents_md` 1011–1022, etc.)
replaces whatever sits between the markers. First regeneration under
the new code shrinks the fat block to the slim static block. The
diff is large but one-time.

### §9.2 This repo (dogfood-first)

1. Land PR-1..3 on a branch; restart daemon (no hot-reload —
   standing rule).
2. Trigger regeneration (CLI `prep rules` or pipeline run).
3. Verify: slim managed blocks; `.sourceprep/AGENT_CONTEXT.md`
   populated; `git status` shows exactly the nine slimmed files once.
4. Commit the slimmed files as the migration commit.
5. Subsequent pipeline runs: `git status` stays clean — the exit
   criterion.

### §9.3 In-flight branches

Any branch still carrying a fat managed block conflicts **once**
against slimmed main, in the managed region only. Resolution rule
(mechanical, documentable in the migration commit message):
**always take the slim side**. After that, conflicts in these files
end permanently.

### §9.4 Client projects in the wild

No action required from users. Next daemon regeneration slims their
files; their next commit includes the one-time diff plus the
gitignore entry. Release notes should state this explicitly so the
diff is not a surprise.

---

## §10 Implementation plan

Three PRs, each independently landable, TDD throughout
(per repo convention: at least one test per seam must exercise the
real import chain, not a mock — Phase 112 Fix 8 lesson).

### PR-1 — Content split + volatile writer (no behavior change yet)

*Tests first:*

- `test_rules_split_static_deterministic` — two calls to
  `_build_static_instructions("claude")` are byte-identical; result
  contains no ISO-8601 timestamp, no `prep_project_id`, no atlas
  marker, for all three profiles (claude/cursor/universal).
- `test_rules_split_volatile_contains_all_dynamic_sections` —
  volatile output contains timestamp, stats, ROUTING banner,
  atlas + `prep-atlas-hash`, focus areas, scopes when inputs
  provided; omits sections cleanly when inputs absent (mirrors
  today's conditionals at 604–652).
- `test_volatile_writer_creates_sourceprep_dir` — writer mkdir-p's
  and writes atomically to a tmp project.
- Characterization test: legacy `_build_managed_content` output ==
  static + pointer + (volatile referenced) reassembly for the
  "universal" profile, so nothing silently vanishes in the split
  (assert section-by-section presence, not byte equality).

*Code:* introduce `_build_static_instructions`,
`_build_volatile_context`, `_write_volatile_context`;
`_build_managed_content` becomes a thin deprecated shim (kept one
release for any external caller; `core/__init__.py:78` re-exports
unchanged symbols).

### PR-2 — Pointer wiring + gitignore ensure

*Tests first:*

- Per-target: managed region contains the pointer
  (P-IMPORT: bare `@.sourceprep/AGENT_CONTEXT.md` **not** inside
  backticks/fence — regression-test this explicitly, since import
  parsing skips code spans; P-READ: the read-instruction sentence)
  and does NOT contain timestamp/atlas/project_id. Update
  `test_rules_generator_targets.py` accordingly.
- `test_rules_regen_preserves_atlas.py` — repurpose: atlas must now
  be preserved *in the volatile file* across regens (C1 semantics at
  318–334 move with it); tracked files must be atlas-free.
- `test_gitignore_ensure_*` — four cases: no repo (no-op), covered
  by blanket `.sourceprep/` (no-op), negation present (no-op + log),
  append path (creates/appends with comment, idempotent on rerun).
- Full-chain test (unmocked seam): `write_rules_file` on a tmp git
  repo end-to-end → assert `git status --porcelain` after a second
  regeneration with changed atlas shows **nothing** (the FM-1 kill
  shot, as a unit-level invariant).

*Code:* update the nine writers; add `_ensure_gitignore_entry`;
update `_detect_targets` docs; scrub generator docstrings.

### PR-3 — No-op write guard + dogfood migration

*Tests first:*

- `test_write_if_changed_preserves_mtime` — unchanged content, mtime
  identical (compare `st_mtime_ns`).
- `test_write_if_changed_updates_on_template_change`.
- Migration characterization: seed a file with a fat legacy managed
  block + user content above/below; regenerate; assert user content
  intact, block slim.

*Code:* `_write_if_changed`, writer adoption; then §9.2 steps on
this repo (restart daemon before live validation — standing rule),
migration commit.

### Verification spikes (before or parallel to PR-2)

| ID | Question | Method | Gates |
|---|---|---|---|
| V1 | Does Claude Code error, warn, or silently skip on `@import` of a missing file? | tmp project, CLAUDE.md importing absent path, run `claude`, inspect `/memory` + stderr | fallback-sentence wording; whether P-IMPORT needs an existence-guard (write pointer only when file exists — rejected by default: creates ordering coupling) |
| V2 | Does the external-import approval dialog trigger for *in-repo* relative imports? | same spike, watch for dialog | if yes: UX note in release notes; pointer stays (dialog is one-time) |
| V3 | Exact Gemini CLI import syntax + missing-file behavior | Gemini CLI docs + tmp project | GEMINI.md pointer line; fallback to P-READ species if imports unsupported in current release |

---

## §11 Test-inventory impact

| Existing test file | Impact |
|---|---|
| `tests/test_rules_generator_targets.py` | Update assertions: pointer present, volatile absent, per target |
| `tests/test_rules_generator_scopes.py` | Scopes section asserted in volatile file, not tracked files |
| `tests/test_rules_regen_preserves_atlas.py` | Repurpose to volatile file (C1 no-wipe semantics preserved) |
| `tests/test_atlas_hash.py` | Verify `prep-atlas-hash` marker relocation doesn't break hash-based skip logic, if any consumer greps tracked files for it (**scrutiny: check consumers of this marker before assuming**) |

New files: `tests/test_rules_split.py`,
`tests/test_gitignore_ensure.py` (names illustrative).

---

## §12 Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Claude Code missing-import behavior is louder than expected (error banner) | V1 before PR-2; fallback sentence; worst case gate pointer on file existence |
| R2 | Some AGENTS.md consumer neither imports nor reads files (pure context-injection surface) → loses atlas priming | Accepted (OQ3); static block still routes to `prep()`; atlas redundant with MCP by design |
| R3 | Gitignore append offends users with strict gitignore hygiene | Comment line explains itself; negation-respect rule; docs |
| R4 | External tooling greps AGENTS.md for `prep_project_id` (our own or third-party scripts) | Repo-wide grep for consumers during PR-2; `read_project_pointer` (`.sourceprep/project.json`) is the canonical source and remains |
| R5 | `prep-atlas-hash` marker consumers break when it moves | §11 scrutiny item; grep before landing |
| R6 | In-flight branches hit the one-time migration conflict without context | Migration-commit message carries the "take the slim side" rule; note in Phase 145 merge-state memory |
| R7 | Windsurf new-path writer overwrites whole file (817–862, no user-content preservation on `.windsurf/rules/prep.md`) — pre-existing sharp edge becomes more visible when users open the now-slim file | Out of scope but flag: the file is entirely ours by convention; note in code comment |
| R8 | Volatile file grows large (atlas + docs-map) and P-READ agents burn context reading it whole | Same content they ingest today via tracked files; if it grows, that is an atlas-size problem, not a pointer problem — existing per-client context budgets (`mcp/server.py:123-138`) remain the live-path control |

---

## §13 Open questions (answer during scrutiny, before PR-2)

- **OQ1 — Filename/location.** `.sourceprep/AGENT_CONTEXT.md` vs
  root-level `sourceprep.md` (Eric's original suggestion). Proposal
  prefers `.sourceprep/`: already the product's state dir, already
  ignored here, hides root clutter, auto-excluded from the graph.
  Root-level is more discoverable to humans. Decide.
- **OQ2 — One volatile file or per-target?** Proposal: one shared
  file (volatile content is target-independent today). Per-target
  only becomes necessary if profiles ever diverge on *data* rather
  than instructions.
- **OQ3 — Keep a one-line identity string in tracked AGENTS.md?**
  E.g. just the IDENTITY sentence, which changes rarely, as minimal
  priming for non-agentic consumers. Costs occasional churn when
  identity re-synthesizes. Proposal: no — purity of the fixed point
  wins; revisit on evidence.
- **OQ4 — Should `detect_and_regenerate`'s marker-presence check
  also validate pointer presence** (so old fat blocks self-heal to
  slim on pipeline start rather than waiting for a full
  `write_rules_file`)? Proposal: yes, cheap — treat "markers present
  but pointer absent" as needs_write. Fold into PR-2 if scrutiny
  agrees.
- **OQ5 — Timestamp policy in the volatile file.** Keep (useful
  staleness signal for agents reading it) or drop (pure noise)?
  Proposal: keep — it is ignored by git, and staleness is real
  signal for a context file.
- **OQ6 — `PREP_` env override for the volatile path?** For exotic
  layouts (bazel monorepos, read-only checkouts). Proposal: defer —
  YAGNI until a user asks; `$PREP_DATA_DIR` precedent exists if
  needed.

---

## §14 What this proposal does NOT do

- Does not change atlas generation, hashing, or the enrichment
  pipeline.
- Does not touch MCP server/tool behavior — live context via
  `prep()` is unchanged and remains the primary path.
- Does not rewrite this repo's history (the 88 churn commits stay).
- Does not migrate `mcp_config.py` outputs (`.claude/mcp.json` etc.)
  — those are config, not content, and do not churn per-run.
- Does not fix direct-mode drift (tracked separately).

---

## §15 Scrutiny checklist for the reviewer

1. Grep for consumers of `prep-atlas-hash`, `prep_project_id`, and
   `Last updated:` outside the generator + tests (R4/R5).
2. Confirm the C1 no-wipe semantics (rules_generator.py:318–334)
   survive relocation: a scope-CRUD regen with empty atlas args must
   not blank the atlas *in the volatile file*.
3. Challenge OQ3 with a real non-agentic consumer list — is there
   one that matters?
4. Verify the characterization-test strategy in PR-1 actually pins
   every section (easy to lose the Phase 119 concurrency hint or the
   cline trigger block silently).
5. Confirm the `agents_md` "ALWAYS generated" rule (1255–1256)
   interacts sanely with the no-op guard on repos that never run
   pipelines (pointer file absent forever — is the static block's
   fallback wording sufficient?).
6. Decide OQ1 (naming) before PR-2 lands anything user-visible.
