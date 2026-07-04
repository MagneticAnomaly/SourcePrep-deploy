# PROPOSAL — Split Managed Rules Blocks into Static Pointer + Gitignored Volatile Context (v2)

**Status:** Scrutinized-and-revised — ready for execution pending one
fresh-eyes read of §5.5 (W1) and the V2 live smoke (§10).
**Date:** 2026-07-04 (v1: 2026-07-04, superseded)
**Supersedes:** `PROPOSAL_static-pointer-volatile-context-v1.md`
(see `SCRUTINY_v1_static-pointer-volatile-context.md` for what
changed and why — headline: v1's hypothesized risk R5 turned out to
be a real, critical consumer in `mcp/server.py`, now work item W1).
**Phase:** 147 — see `README.md`.
**Primary files:** `src/prep/core/rules_generator.py`,
`src/prep/mcp/server.py` (new in v2).

Changes from v1 at a glance:

1. **W1 (new, critical):** `mcp/server.py` atlas-dedup must be
   repointed at the volatile file (Scrutiny D1) — added §5.5 and
   folded into PR-2 with tests.
2. **Migration rewritten for reality (Scrutiny D2 + Eric's call):**
   single-user install base → no release-notes machinery; instead a
   careful manual per-registered-project checklist, §9.5, covering
   all 15 dashboard-registered projects including the three nested
   inside this monorepo.
3. **Volatile header gains the prep-self-output sentinel**
   (Scrutiny D3).
4. **Worktree degraded mode documented** (Scrutiny D4).
5. **V1–V3 verification spikes resolved** — silent skip confirmed
   (Claude), graceful error comment (Gemini), design unchanged.
6. **All OQs resolved** (Eric, 2026-07-04) — decisions inlined, no
   open questions block anything.

---

## §1 Problem statement

SourcePrep's rules generator writes a "managed block" into up to nine
per-IDE instruction files inside every registered project (and this
repo, since we dogfood). The block mixes two fundamentally different
kinds of content:

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
files, every pipeline run dirties git-tracked files. Two failure
modes result:

**FM-1 — Phantom WIP.** An agent session starts, reads `git status`,
sees `M CLAUDE.md`, `M AGENTS.md`, `M .cursor/rules/prep.mdc`, and
concludes a *different session* left uncommitted work. It hedges,
asks, or tries to preserve daemon noise as if it were work. Live in
the current working tree right now.

**FM-2 — Same-file-tail merge conflicts.** Branches regenerate at
different times; every merge conflicts in the same managed regions.
Recorded during the 2026-06-29 Phase 145 merge train as the
"pr-M/pr-N same-file-tail conflict pattern."

History quantifies it: **48 commits touch CLAUDE.md, 40 touch
AGENTS.md**, including pure-noise commits like `2dae33eb
chore(prep-managed): regenerate AGENTS.md / Cursor rule / CLAUDE.md
atlas`. And per Scrutiny D2 the multiplier is worse than v1 modeled:
the nested `SourcePrep_Website` project (path `websites/apps`)
independently dirties `websites/apps/AGENTS.md` and
`websites/apps/.cursor/rules/prep.mdc` — tracked in the *same* git
repo — whenever *its* pipeline runs.

---

## §2 Evidence — where the churn is manufactured

### §2.1 The unconditional timestamp

```python
# rules_generator.py:482-483
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
stat_parts = [f"Last updated: {now}"]
```

Every write differs from the previous write **by construction**.
This alone guarantees FM-1 on every regeneration.

### §2.2 Genuinely volatile payloads in tracked files

| Content | Source lines (rules_generator.py) | Changes when |
|---|---|---|
| Timestamp header | 482–493 | every write |
| node/edge counts | 484–490 (via `_get_current_stats`, 272–295) | every reindex |
| `prep_project_id` + ROUTING banner | 496–504 | per-daemon registration (would differ per teammate) |
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

Varies only per product version.

### §2.4 Regeneration triggers

| Trigger | Call site |
|---|---|
| Post-Stage-1 preliminary atlas | `services/pipeline/post_flight.py:98` |
| Post-enrichment final atlas | `services/pipeline/post_flight.py:159` |
| Worker-level rewrites | `services/pipeline/workers/__init__.py:1488`, `:1516` |
| Pipeline start (marker-missing repair only) | `services/pipeline/orchestrator.py:1985` → `detect_and_regenerate` |
| Scope CRUD (debounced 2 s) | `api/routers/scopes.py:30` → `schedule_rules_regeneration` (rules_generator.py:298–339) |
| CLI `prep rules` | `cli.py:919` |
| Dashboard "Generate Rules" button | same API path |

`detect_and_regenerate`'s non-force path (179–201) already skips
files whose markers are present; the churn comes from the post_flight
and worker call sites, which write unconditionally with fresh
atlas/stats.

### §2.5 Files affected

From `_detect_targets` (rules_generator.py:1232–1296):

| Target | Path | Typically tracked? | Embeds volatile today? |
|---|---|---|---|
| agents_md | `AGENTS.md` | **yes** | yes (verbose "universal" profile) |
| claude | `CLAUDE.md` | **yes** | yes ("claude" profile) |
| cursor | `.cursor/rules/prep.mdc` | **yes** | yes |
| windsurf | `.windsurf/rules/prep.md` (legacy `.windsurfrules`) | **yes** | yes |
| gemini | `GEMINI.md` | **yes** | yes |
| copilot | `.github/copilot-instructions.md` | **yes** | yes |
| cline | `.clinerules` | **yes** | yes |
| roo_code | `.roo/rules/prep.md` (+2 static mode files) | **yes** | yes (base file only) |
| claude_skill | `.claude/skills/prep.md` | yes | **no** — already static, write-once (931–977). No change. |

---

## §3 Root-cause statement

> Volatile, machine-generated, per-daemon state is being persisted
> into files whose contract is "shared, human-curated,
> version-controlled project configuration." The marker system
> solves *ownership* (who may edit which region) but not *volatility*
> (which region belongs in git at all).

Give the volatile state its own file with the correct git contract
(ignored); leave behind only a stable pointer.

---

## §4 Alternatives considered and rejected

(Unchanged from v1; summarized.)

- **A1 gitignore the tracked files themselves** — inert on tracked
  files; would discard human-authored content. Structurally wrong.
- **A2 skip-if-unchanged only** — kills no-change churn but atlas
  changes every enrichment run; FM-2 survives. Adopted anyway as
  belt-and-braces (§8), not as the fix.
- **A3 `.gitattributes merge=ours` driver** — needs per-clone config;
  masks FM-2, ignores FM-1.
- **A4 write into `CLAUDE.local.md`** — collides with the user's
  personal file; solves one target of nine.
- **A5 `git update-index --skip-worktree`** — per-clone invisible
  footgun; rejected even as stopgap.
- **A6 drop embedded atlas entirely, rely on `prep()`** — the
  embedded atlas is deliberate always-on priming for agents that
  never call tools. The pointer design preserves priming; import
  targets lose nothing at all.

---

## §5 Design

### §5.1 The split

`_build_managed_content()` (rules_generator.py:462–700) splits into
two pure functions plus one writer:

```
_build_static_instructions(target, project_name) -> str
    # §2.3 content only. No datetime. No stats. No project_id.
    # Deterministic for a given (target, product version).

_build_volatile_context(project_name, atlas_content, included_paths,
                        is_preliminary, stats, project_id) -> str
    # §2.2 content only. Target-independent; one rendering serves
    # all IDEs.

_write_volatile_context(project_path, ...) -> bool
    # → <project>/.sourceprep/AGENT_CONTEXT.md  (atomic via _write;
    #   mkdir -p .sourceprep/)
```

`write_rules_file()` (59–140) calls `_write_volatile_context()`
first, then per-target writers, which embed only the static
instructions plus a pointer (§5.3).

### §5.2 The volatile file

**Path:** `.sourceprep/AGENT_CONTEXT.md` (OQ1 — decided).

Location rationale: `.sourceprep/` is the product's per-project state
dir (`read_project_pointer` already reads `.sourceprep/project.json`,
rules_generator.py:91–95); already gitignored in this repo
(`.gitignore:78`); and **already excluded from indexing** via
`DEFAULT_EXCLUDE_DIR_NAMES` (`repo_profile.py:12`) — so atlas text in
it can never re-enter the trace graph, independently fixing the
"generated AGENTS.md pollutes the graph" complaint. The writer
mkdir-p's, so standalone-mode projects simply gain the directory.

**Layout** (header updated per Scrutiny D3 — the first line contains
the literal phrase `SourcePrep structural codebase intelligence` so
`docs_grounding._looks_like_prep_self_output()` (docs_grounding.py:
360–380) recognizes it as a third protection layer):

```markdown
<!-- SourcePrep structural codebase intelligence — auto-generated -->
<!-- volatile context. DO NOT EDIT, DO NOT COMMIT. Regenerated     -->
<!-- after every index run. Git-ignored by design.                 -->
# SourcePrep Agent Context — <project_name>

Last updated: <ISO8601> | <N> nodes | <M> edges [| Full analysis in progress]

prep_project_id: <uuid>
**ROUTING: When calling ANY SourcePrep tool, ALWAYS include
`project_id: "<uuid>"` in the arguments.**

<!-- prep-atlas-hash:<12hex> -->
## Codebase Atlas
<atlas text>

## Documentation Map            (Phase 124 T9 section, if present)
## Focus Areas                  (if configured)
## Scopes                       (if any)
```

No managed markers — the whole file is ours.

**`project_id` moves here deliberately:** it is a per-daemon
registration UUID (a guaranteed cross-user conflict if ever tracked);
runtime auto-detection from the workspace root remains the fallback.
**Timestamp stays** (OQ5 — decided): git-invisible, and staleness is
real signal for whoever reads the file.

### §5.3 Per-target pointer mechanics

**Species P-IMPORT (native inline import — zero behavior loss):**

| Target | Pointer line |
|---|---|
| claude (`CLAUDE.md`) | `@.sourceprep/AGENT_CONTEXT.md` |
| gemini (`GEMINI.md`) | `@.sourceprep/AGENT_CONTEXT.md` |

Verified mechanics (Scrutiny V1–V3, HIGH confidence unless noted):

- Claude Code: imports expand at launch; relative paths resolve
  against the importing file; max depth four hops; **missing file =
  silent skip** (docs + issue #56927); gitignore status irrelevant;
  block-level HTML comments are stripped *before* injection and
  import parsing skips only code spans/fences — so a **bare** import
  line between our two marker comments is processed. The pointer
  must never be wrapped in backticks (that makes it literal) —
  regression-tested.
- Gemini CLI (memport): `@file.md` syntax; **.md files only** (ours
  is .md ✓); missing file → graceful *error comment in output*
  (visible, unlike Claude — acceptable; fallback sentence explains);
  circular-import protection; depth 5.
- Approval dialog: docs gate it on "external imports" (undefined);
  the canonical gitignored `CLAUDE.local.md` / in-repo `@AGENTS.md`
  patterns carry no approval caveat → expected none for in-repo
  paths (MEDIUM — 5-minute live smoke in §10 confirms).

Accompanying static fallback sentence (both import targets):

> If the imported context file is missing, this project has not been
> indexed on this machine yet — call `prep()` for live context, or
> start the SourcePrep daemon to generate it.

**Species P-READ (instruction to read the file):**

| Target | Wording in static block |
|---|---|
| agents_md, cursor, windsurf, copilot, cline, roo_code | "**At the start of every task**, read `.sourceprep/AGENT_CONTEXT.md` (if present) for the current codebase atlas, project id, focus areas, and scopes — or call `prep()` for the live equivalent." |

Cline's keyword trigger block (1138–1142) stays — it is static. Roo's
two mode files (1204–1224) are already fully static — untouched.
claude_skill — no change (write-once). OQ3 — decided: **no** identity
line remains in tracked AGENTS.md; the fixed point stays pure.

### §5.4 What remains in each tracked file

E.g. `AGENTS.md`'s managed region becomes (~40 lines, fixed point):

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

Changes only when the product template changes — legitimately
commit-worthy.

### §5.5 W1 — repoint the MCP server's atlas-dedup (NEW in v2, critical)

**The consumer:** `mcp/server.py` Phase 73.4 logic.
`_project_has_rules_file()` (:247–317) detects rules files and
extracts `prep-atlas-hash` from CLAUDE.md into
`_rules_atlas_hash_cache`; `_extract_atlas_hash()` (:325–333) does
the regex; `tool_context()` (:1140–1230, second consumer :1847) uses
them: *rules file exists → skip atlas in `prep()` responses*
(assumed already in the agent's system prompt), *hash mismatch →
re-include fresh atlas*.

**Failure if unfixed:** post-split, `has_rules=True` but
`rules_hash=None` → the `:1158` fallback ("rules exist but no hash —
skip atlas") suppresses the atlas in `prep()` **permanently**, while
tracked rules no longer carry it. A P-READ client that skipped the
volatile file would get structural orientation from nowhere, and the
staleness re-include branch (:1199–1219) goes dead.

**Fix — behavior table (fresh-eyes review requested here):**

| State on disk | `include_atlas` in `prep()` | Rationale |
|---|---|---|
| `.sourceprep/AGENT_CONTEXT.md` exists, hash matches current atlas | skip (tentative, as today) | context file is fresh; import clients have it in-context, P-READ clients were told to read it |
| volatile file exists, hash mismatches | include | stale context file (regen raced, or file preserved from older run) |
| volatile file **missing**, legacy fat rules file present (pre-migration repo) | today's exact behavior (hash from rules file) | back-compat during transition; no flag day |
| volatile file missing, rules files slim or absent | **include** | degraded/fresh-clone/worktree mode — server is now the only atlas source |

Implementation: `_project_has_rules_file` keeps its role as
"instructions present?" signal; hash extraction moves to a new
`_get_context_file_atlas_hash(project_path)` reading the volatile
file first, falling back to legacy rules-file extraction when the
volatile file is absent. Cache + invalidation unchanged — the
existing `_check_atlas_signal` (:350–374) already watches
`.sourceprep/atlas_updated.signal` and clears the caches after every
atlas write. Verified no-regression: today's flow likewise leaves an
agent's *in-context* atlas stale after a mid-session regen (the hash
cache refreshes from the regenerated file and skips re-send);
semantics are identical, only the file read changes.

---

## §6 `.gitignore` management

New helper (in `rules_generator.py`, or `core/gitignore_utils.py` if
we want a test seam):

```python
_GITIGNORE_ENTRY = ".sourceprep/AGENT_CONTEXT.md"
_GITIGNORE_COMMENT = "# SourcePrep volatile agent context (auto-added; keep ignored)"

def _ensure_gitignore_entry(project_path: Path) -> bool:
    """Ensure the volatile context file is git-ignored.

    - No-op when project_path has no .git (not a repo).
    - No-op when existing .gitignore already covers the path
      (pathspec check — already a dependency, cf. index.py:343).
      Covers this repo's blanket `.sourceprep/` entry.
    - No-op when a negation pattern re-includes it (user's deliberate
      choice; log INFO once, do not fight).
    - Otherwise append comment + entry (atomic), creating .gitignore
      if absent. Coverage-check-then-skip makes reruns idempotent.
    """
```

Called from `_write_volatile_context()`. Failure is non-fatal
(WARNING): a missing entry degrades to today's behavior for one file
instead of nine. We ignore the *specific file*, never the directory —
embedded mode documents `.sourceprep/` as git-trackable for teams
that commit their index.

---

## §7 Degradation behavior

State: volatile file absent (fresh clone, sibling worktree, never
indexed) — pointer present, target missing.

| Surface | Behavior |
|---|---|
| Claude Code `@import` | Silent skip (V1, HIGH). Static fallback sentence covers the gap. |
| Gemini CLI import | Graceful error comment in output (V3, HIGH). Same fallback sentence. |
| P-READ targets | Wording says "(if present)" — agent falls back to `prep()`. |
| `prep()` response | **W1 row 4: atlas re-included by the server** — the degraded state now self-corrects on the first tool call. |
| First daemon run | `_write_volatile_context()` creates the file; gitignore entry already committed → zero tracked-file changes. Steady state restored. |

**Worktree note (Scrutiny D4, accepted limitation):** the volatile
file is per-checkout; the daemon writes only the registered path.
Sessions in sibling worktrees (heavily used here) run in degraded
mode above — safe by the two recovery paths (fallback sentence +
W1 row 4). Cross-worktree sharing via home-dir import is deliberately
not used (per-user absolute path cannot live in a committed file).
Optional future enhancement (deferred, YAGNI): daemon enumerates
`git worktree list` and mirrors the file.

Degraded is *strictly better than today's* failure mode: today a
fresh clone carries a **stale committed atlas** (silently wrong);
post-split it carries no atlas plus two working recovery paths.

---

## §8 No-op write guard (belt-and-braces)

```python
def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False          # byte-identical — leave mtime alone
    _write(path, content)     # atomic, as today
    return True
```

Adopted by all per-target writers (kills mtime churn → IDE
rules-reload, watcher noise, change badges). The volatile writer
keeps unconditional `_write` (its timestamp legitimately changes; it
is git-invisible). Writer return values become honest
"did anything change" signals through `write_rules_file`'s result
dict (86, 136–139).

---

## §9 Migration

### §9.1 Mechanics (automatic)

No special-case code: the existing marker-splice logic
(`_write_claude_rules` 911–923, `_write_agents_md` 1011–1022, etc.)
replaces whatever sits between markers. First regeneration under new
code shrinks fat blocks to slim ones. Large one-time diff.

### §9.2 Pointer self-heal (OQ4 — decided: yes, PR-2)

`detect_and_regenerate`'s marker-presence check (179–201) also
treats "markers present but pointer absent" as needs_write, so
legacy fat blocks self-heal to slim at the next pipeline start /
MCP initialize without waiting for a full regen path.

### §9.3 In-flight branches of this repo

Any branch still carrying a fat managed block conflicts **once**
against slimmed main, in the managed region only. Mechanical
resolution rule (goes in the migration commit message): **always
take the slim side.** Then conflicts in these files end permanently.

### §9.4 ~~Client projects in the wild~~ — dropped

v1 planned release-notes comms for external users. **There are no
external users yet** (Eric, 2026-07-04) — the install base is the 15
dashboard-registered projects below, all Eric's. Replaced by §9.5.

### §9.5 Manual migration checklist — all registered projects (NEW)

> **Execute after PR-1..3 land and the daemon is restarted**
> (standing rule: no hot-reload — stale in-memory code silently
> validates against old behavior). Work through the table one
> project at a time, **carefully**: several of these repos have
> unrelated WIP, and one is nested inside this monorepo.

**Per-project procedure (P0–P6):**

- **P0** `git status` first. Note pre-existing dirty files — the
  migration commit must contain *only* rules files + `.gitignore`.
- **P1** Regenerate rules: dashboard "Generate Rules", or the CLI
  regenerate command (`cli.py:858` — `prep rules`), or any pipeline
  run. Do **not** trigger a full rebuild just for this (matters for
  HomeColab, 45–90 min).
- **P2** Inspect the diff: managed block slim; no timestamp / atlas /
  project_id / focus areas in tracked files; pointer line present
  and **bare** (not backticked); user content above/below markers
  intact.
- **P3** Verify `.sourceprep/AGENT_CONTEXT.md` exists and carries
  atlas + hash + project_id; verify `git check-ignore
  .sourceprep/AGENT_CONTEXT.md` passes (generator should have
  ensured the entry; if the repo ignores `.sourceprep/` wholesale,
  that's fine too).
- **P4** Commit rules files + `.gitignore` only, message
  `chore(phase147): slim prep-managed blocks to static pointer`.
- **P5** **No pushes.** Standing rule: never push without an
  explicit signal — applies doubly to forks of third-party projects.
- **P6** Spot-check one agent session in the repo (any IDE): context
  loads, no phantom-WIP complaint, `prep()` works.

**Project inventory (dashboard registry, 2026-07-04 screenshot):**

| # | Project | Path | Special handling |
|---|---|---|---|
| 1 | SourcePrep | `/Volumes/4TB-BAD/HumanAI/CoDRAG` | The dogfood-first migration (§9.6). Tracked: `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/prep.mdc`. `.sourceprep/` already ignored (`.gitignore:78`). |
| 2 | SourcePrep_Website | `…/CoDRAG/websites/apps` | **Nested in #1's git repo.** Tracked in parent: `websites/apps/AGENTS.md`, `websites/apps/.cursor/rules/prep.mdc`, plus stray `websites/GEMINI.md`. Migrate in the **same commit** as #1 to keep one clean migration point. Its volatile file lands at `websites/apps/.sourceprep/AGENT_CONTEXT.md` — confirm the generator's gitignore-ensure targets the **repo root** `.gitignore` (or that the blanket `.sourceprep/` entry covers nested paths — it does: gitignore patterns match at any depth). |
| 3 | PowerMateReborn | `…/CoDRAG/tests/eval/real_repos/PowerMateReborn` | Under gitignored `tests/eval/` (`.gitignore:103`) — regenerate for hygiene, **nothing to commit**. |
| 4 | smoke-test | `…/CoDRAG/tests/eval/sample_repos/…` | Same as #3. Also: eval harnesses that assert on generated AGENTS.md content may need fixture updates — check `tests/eval/` expectations. |
| 5 | Halley | `/Volumes/4TB-BAD/HumanAI/LinuxBrain` | Standard P0–P6. |
| 6 | HomeColab | `/Volumes/Thunderbolt/XcodeProjects/HomeColab` | **Do not full-rebuild** (45–90 min). P1 via CLI/dashboard regen only. |
| 7 | DebateHaus | `/Volumes/Thunderbolt/XcodeProjects/DebateHaus/DH` | Standard. Note registered root is a subdir of the checkout — verify which level holds `.git` so P4 commits from the right place. |
| 8 | SkyPath | `/Volumes/Thunderbolt/XcodeProjects/SkyPath2025/SkyPath` | Standard. |
| 9 | SkyPath-Restart | `/Volumes/Thunderbolt/XcodeProjects/SkyPath2025/SkyPath-Restart…` | Standard. Sibling of #8 — if they share one git repo, fold into one commit like #1/#2. |
| 10 | ChatUserMemory | `/Volumes/Thunderbolt/ChatUserMemory` | Standard. |
| 11 | AI-App-Management | `/Volumes/Thunderbolt/AI/AI-App-Management` | Standard. |
| 12 | Deep-Live-Cam | `/Volumes/Thunderbolt/AI/deep-live-cam` | Likely a fork of a public upstream — P5 (no push) is critical; if the repo has no rules files with our markers, nothing to do beyond P3. |
| 13 | Applifier | `/Volumes/Thunderbolt/AI/ApplicationBrowser` | Standard. |
| 14 | Dinner.Vision | `/Volumes/Thunderbolt/XcodeProjects/DinnerVisionApp/DinnerVis…` | Standard. |
| 15 | Applivation-Android | `/Volumes/Thunderbolt/AI/Applivation-Android` | Standard. |

Non-git or never-indexed entries degrade gracefully: gitignore-ensure
no-ops without `.git`; P4/P5 skip.

### §9.6 This repo (dogfood-first, do before the sweep)

1. Land PR-1..3 on a branch; restart daemon.
2. Regenerate → verify slim blocks for **both** the root project and
   the nested `websites/apps` project; volatile files populated.
3. `git status` shows exactly the slimmed tracked files once; commit
   as the migration commit (rule "take the slim side" in the
   message, for in-flight branches).
4. Run one full pipeline → **exit criterion: `git status` untouched.**
5. Then execute §9.5 for projects 3–15.

---

## §10 Implementation plan

Three PRs, each independently landable, TDD throughout. Repo
convention applies: at least one test per seam exercises the real
import chain, unmocked (Phase 112 Fix 8).

### PR-1 — Content split + volatile writer (no consumer change yet)

*Tests first:*

- `test_rules_split_static_deterministic` — two calls to
  `_build_static_instructions(t)` byte-identical; output contains no
  ISO-8601 timestamp, no `prep_project_id`, no `prep-atlas-hash`,
  for all three profiles.
- `test_rules_split_volatile_contains_all_dynamic_sections` —
  volatile output contains timestamp, stats, ROUTING banner, atlas +
  hash comment, focus areas, scopes when provided; omits sections
  cleanly when absent (mirrors 604–652 conditionals); **first line
  contains the D3 sentinel phrase**.
- `test_volatile_writer_creates_sourceprep_dir` — mkdir-p + atomic
  write on a tmp project.
- Characterization: for the "universal" profile, every section
  present in legacy `_build_managed_content` output appears in
  exactly one of (static, volatile) — section-by-section presence
  assertions, explicitly including the Phase 119 concurrency hint
  and the cline trigger block (easy to lose silently).

*Code:* `_build_static_instructions`, `_build_volatile_context`,
`_write_volatile_context`; `_build_managed_content` stays as a thin
deprecated shim one release (`core/__init__.py:78` exports
unchanged).

### PR-2 — Pointer wiring + gitignore ensure + **W1 server repoint**

*Tests first:*

- Per-target pointer tests (update
  `tests/test_rules_generator_targets.py`): P-IMPORT line present
  and **bare** (regression: not inside backticks/fence); P-READ
  sentence present; tracked output contains no volatile bytes.
- `tests/test_rules_regen_preserves_atlas.py` — repurpose: C1
  no-wipe semantics (318–334) now guard the **volatile file**; a
  scope-CRUD regen with omitted atlas args must not blank the atlas
  there; tracked files must be atlas-free.
- `test_gitignore_ensure_*` — no-repo no-op / covered-by-blanket
  no-op (including **nested project under a parent repo whose root
  .gitignore has `.sourceprep/`** — the D2 case) / negation-respect /
  append + idempotent rerun.
- **W1 tests** (`tests/test_mcp_atlas_dedup_context_file.py`, new):
  the four rows of the §5.5 behavior table — fresh hash → skip;
  stale hash → include; missing volatile + legacy fat rules →
  legacy hash path; missing volatile + slim rules → include. Plus:
  `_check_atlas_signal` still invalidates after a regen (existing
  coverage extended, not mocked at the seam under test).
- Full-chain unmocked test: `write_rules_file` twice on a tmp git
  repo with *changed atlas between runs* → `git status --porcelain`
  empty after the second run (**the FM-1 kill shot**).
- OQ4 self-heal: seed a fat legacy block; `detect_and_regenerate`
  (non-force) rewrites it slim.

*Code:* nine writers slimmed; `_ensure_gitignore_entry`; W1 in
`mcp/server.py` (`_get_context_file_atlas_hash` + `tool_context`
adjustments at :1149–1230 and :1847); `detect_and_regenerate`
pointer-presence check; `tests/test_atlas_hash.py` updated (hash
asserts move to the volatile file).

*Verification (was spikes V1–V3 — resolved by scrutiny, one live
check left):* 5-minute smoke — tmp project, CLAUDE.md importing the
gitignored volatile file, confirm content loads via `/memory` and no
approval dialog appears (V2 was MEDIUM-confidence inference).

### PR-3 — No-op write guard + dogfood migration

*Tests first:*

- `test_write_if_changed_preserves_mtime` (`st_mtime_ns` compare) /
  `test_write_if_changed_updates_on_template_change`.
- Migration characterization: fat legacy block + user content above
  and below → regenerate → user content intact, block slim.

*Code:* `_write_if_changed` + writer adoption; then §9.6 on this
repo (restart daemon first), migration commit; then the §9.5 sweep.

---

## §11 Test-inventory impact

| Existing test | Impact |
|---|---|
| `tests/test_rules_generator_targets.py` | Pointer present / volatile absent, per target; `:86` hash assert moves to volatile file |
| `tests/test_rules_generator_scopes.py` | Scopes asserted in volatile file |
| `tests/test_rules_regen_preserves_atlas.py` | C1 seam survives unchanged (Scrutiny D5); assertions repointed to volatile file |
| `tests/test_atlas_hash.py` | Hash-comment asserts (`:20,:33,:40`) repointed to volatile file |
| MCP server context tests | Extended for W1 behavior table |
| `tests/eval/` harnesses | Check for fixture assertions on fat AGENTS.md content (§9.5 row 4) |

New: `tests/test_rules_split.py`, `tests/test_gitignore_ensure.py`,
`tests/test_mcp_atlas_dedup_context_file.py`.

---

## §12 Risks (updated)

| ID | Risk | Status / mitigation |
|---|---|---|
| R1 | Claude missing-import louder than expected | **Closed** — silent skip confirmed (V1, HIGH) |
| R2 | Non-agentic AGENTS.md consumer loses atlas priming | Accepted (OQ3 decided); W1 row 4 makes `prep()` the safety net |
| R3 | Gitignore append offends strict-hygiene users | Comment line + negation-respect; single-user base today |
| R4 | External tooling greps rules files for `prep_project_id` | Grep clean — only kwarg names in paperclip/push_engine, no parsers. `read_project_pointer` stays canonical |
| R5 | `prep-atlas-hash` consumers break | **Promoted to W1 (critical, §5.5)** — the one real consumer found and specced |
| R6 | In-flight branches hit the one-time conflict blind | Migration-commit message carries the "take the slim side" rule |
| R7 | Windsurf new-path writer overwrites wholesale (817–862) | Pre-existing; file is fully-managed by convention; code comment |
| R8 | Volatile file large → P-READ context cost | Same bytes they ingest today; live-path budgets (`mcp/server.py:123-138`) unchanged |
| R9 (new) | Worktree sessions degraded | Accepted + documented (§7); two recovery paths; optional future mirror via `git worktree list` |
| R10 (new) | W1 behavior table wrong in an edge case (same-author scrutiny) | Fresh-eyes read requested before PR-2 merge; table is small and unit-tested row-by-row |

---

## §13 Resolved decisions (formerly OQ1–OQ6)

| Was | Decision (Eric, 2026-07-04) |
|---|---|
| OQ1 location | `.sourceprep/AGENT_CONTEXT.md` |
| OQ2 file count | One shared volatile file |
| OQ3 identity line in AGENTS.md | No |
| OQ4 pointer self-heal | Yes — PR-2 (§9.2) |
| OQ5 timestamp | Keep, in volatile file only |
| OQ6 path env override | Defer (YAGNI); worktree-mirror idea likewise deferred (§7) |

---

## §14 Out of scope

Unchanged from v1: atlas generation/hashing internals; MCP tool
schemas; direct-mode parity; history rewrite; `mcp_config.py`
outputs. Additionally out of scope (noted during scrutiny): the
`.agents/**/AGENTS.md` files are a *different* generator (staffing
agents / SOUL.md flow, cf. docs_grounding.py:104–114) — not touched
by this phase.

---

## §15 Execution gate

Before PR-2 merges: (a) fresh-eyes read of the §5.5 W1 behavior
table; (b) the 5-minute V2 live smoke. Before declaring the phase
done: §9.6 exit criterion (clean `git status` after a full pipeline
run) plus the §9.5 sweep completed for all 15 registered projects.
