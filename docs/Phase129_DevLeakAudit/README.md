# Phase 129 — Dev-Leak Audit

> Status: Scaffolded 2026-05-07. Initial telemetry-leak fix landed via the same
> session (commits to follow). Remaining sweep is the work this phase tracks.

## Why this phase exists

SourcePrep is shipping. Some shipped source code contains internal development
nomenclature — phase numbers, commit dates, internal class names, "follow-up
landed" narration — written into runtime values that reach the user's disk
(telemetry JSONL, logs, generated AGENTS.md) and the user's AI agents (LLM
prompts).

Two sessions of dogfood scrutiny on 2026-05-06/07 surfaced concrete examples:

1. **Telemetry payload leak** — `record_event(..., phase="124", ...)` wrote a
   literal `"phase": "124"` JSON field plus remediation strings like
   *"Phase 123 follow-up landed 2026-05-07 — workers emit their own clarifying
   questions, so synthesis failure no longer zeroes them. To recover synthesis
   itself, bump SwarmOrchestrator max_wall_time_s above 900 for cloud models."*
   to `<project>/.sourceprep/pipeline_telemetry.jsonl` on every synthesis
   failure. *Fixed in the same session — see §"Initial sweep landed" below.*

2. **Worker-prompt leak** — the concept-seeding swarm worker prompt contained
   the literal phrase *"Questions survive synthesis failure (Phase 123): if
   synthesis times out we still keep questions emitted at the worker layer."*
   That string was sent to the LLM. The LLM never needs to know what Phase 123
   is. *Fixed in the same session.*

These two were caught because the user opened a diff and noticed. There are
plausibly many more across the codebase that haven't been caught yet. Phase 129
is the systematic sweep.

## What counts as a dev leak

The bar: **a string literal (not a comment, not a docstring) that ships to a
user, an end-user log, an LLM, or a generated AGENTS.md, and references our
internal development nomenclature.**

Concrete patterns to search for:

| Pattern | Example | Why it's a leak |
|---|---|---|
| `Phase \d+` in any non-comment string | `"Phase 124 T4 enriches each worker's prompt"` | Internal phase numbers are project-management concepts, not product concepts |
| `landed YYYY-MM-DD` / `scaffolded YYYY-MM-DD` | `"Phase 123 follow-up landed 2026-05-07"` | Commit-message-style narration |
| `F-\d+` bug IDs | `"F-36 batch save"`, `"F-59 part 5"` | Internal bug-tracker IDs |
| `Phase \d+ follow-up` / `Phase \d+ territory` | `"Phase 123 territory — bump..."` | Status-of-work language |
| Internal class names in user copy | `"bump SwarmOrchestrator max_wall_time_s"` | User doesn't see SwarmOrchestrator; they see CLI flags or env vars |
| Phase-numbered tasks (`T3`, `T4`, `T9`) | `"Phase 124 T2 writes the file"` | Sub-task notation only meaningful to internal planning |

**What is NOT a leak (don't fix in this phase):**

- `# Phase 113 migrate legacy ...` — comments are not shipped strings.
- `"""Phase 125b — cross-cutting concept synthesizer."""` — module/function
  docstrings are accessible via `__doc__` but agents/users don't usually see
  them. Triage-but-deprioritize.
- `phase` as a variable name for pipeline state values like `"paused"`,
  `"failed"`, `"pausing"` (e.g. `useEnrichment.ts`). These are operational
  states with semantic meaning, not dev numbering.

## High-visibility cluster landed (2026-05-27, Lane C)

Daemon-startup logs and the continuous watchdog/heartbeat logs were the
loudest user-facing leaks — every daemon start and every watcher tick
wrote them.  Rewritten to plain operational copy:

- `src/prep/server.py` — concept-store migration logs (3 sites,
  `Phase 96/F-36`), system-concept seeding fallback (`Phase 119`),
  crashed-run startup banner (`Phase 25`).
- `src/prep/core/watcher.py` — five watchdog / selfheal logs
  (`Phase 61B`, `Phase 72`).
- `src/prep/core/embedder.py` — CoreML opts banner (`Phase 139`).
- `src/prep/core/system_concept_seeder.py` — system-seed summary
  (`Phase 119`).
- `src/prep/mcp/server.py` — MCP scope-filter debug (`Phase 120`).

## Pipeline-orchestration cluster landed (2026-05-28, Lane C)

Pipeline-stage logs that fire during every build — drain timeouts,
branch transitions, recovery banners, journal authority checks,
manifest stale checks.  Same rewrite shape: drop the dev-numbering
prefix, keep all args + log level + exc_info intact.

- `src/prep/services/pipeline/orchestrator.py` — 22 sites
  (`Phase 91`, `Phase 60D`, `Phase 61B`, `Phase 72D`, `Phase 49`,
  `Phase 50`, `Phase 118 U22`, `Phase 60B`, `Phase 128`,
  `Phase 127 T3.2`, `F-67`, `F-87`, `F-76`).
- `src/prep/services/pipeline/recovery.py` — 22 sites
  (`Phase 61B`, `Phase 72D`, `Phase 60D`, `Phase 60B`, `Phase 128`,
  `Phase 93`, `Phase 72C`).
- `src/prep/services/pipeline/resume.py` — 3 sites (`Phase 128`).
- `src/prep/services/pipeline/post_flight.py` — 5 sites
  (`Phase 50`, `Phase 64A`).
- `src/prep/services/pipeline_metadata.py` — 1 site (`Phase 61B`).
- `src/prep/core/trace/builder.py` — 2 sites (`Phase 133`).

## Regression guard

`tests/test_phase129_dev_leak_regression.py` walks each cleaned
module's AST and asserts no `logger.*` positional string literal starts
with `Phase N` / `Phase NNX` / `F-NN`.  The `CLEAN_MODULES` list in
that test is the source of truth for what has shipped — add a module
to it once sanitized so the regression guard grows monotonically.

## Recipe verdicts (2026-05-28)

- **Recipe 1** (Phase N in non-comment literals): **0 hits** in
  `src/prep/**.py` outside docstrings.
- **Recipe 2** (commit-narration "landed YYYY-MM-DD"): **0 hits**.
- **Recipe 3** (F-NN bug IDs in user-visible strings): **0 hits**.
- **Recipe 4** (`rules_generator` AGENTS.md content): **0 hits**
  outside docstrings.
- **Recipe 5** (LLM-bound prompts): no `prompt=` / `system=`
  string-literal assignment in `src/prep/` matches `"Phase N"` or
  `"F-NN"`.
- **Recipe 6** (telemetry `remediation` / `message` fields): no
  matches in `src/prep/`.

Module / function docstrings still mention phase numbers as
chronology breadcrumbs for source readers; per this phase's
non-goals these are intentionally left in place.

## Initial sweep landed (2026-05-07)

Already fixed in the session that scaffolded this phase:

- `pipeline_telemetry.record_event` no longer persists the `phase` kwarg
  (still accepted for back-compat; silently dropped). The on-disk schema
  drops the `phase` field.
- 17 `record_event(..., phase="N", ...)` call sites in `concept_seeder.py`,
  `concept_synthesizer.py`, `concept_promotion_pipeline.py`,
  `concept_t3_refine.py`, `rules_generator.py`, `audit/synthesizer.py`,
  `services/pipeline/workers.py` — kwarg removed.
- Concept-seeder synthesis-failed remediation string rewritten to user-facing
  copy.
- Concept-seeder swarm worker prompt's `(Phase 123)` reference removed.
- Tests updated; 16/16 telemetry + worker-question tests pass.

## Remaining sweep — search recipes

Run these from the repo root and triage hits.

### 1. Phase numbers in non-comment string literals

```bash
grep -rEn '"Phase [0-9]+|"phase [0-9]+|f"Phase [0-9]+' \
  src/prep --include="*.py" 2>/dev/null \
  | grep -vE '^[^:]+:[0-9]+: *#' \
  | grep -v __pycache__
```

Expected hits (start of phase): user-facing log strings in `server.py`,
`watcher.py`, `system_concept_seeder.py`. Triage each — if it's a
`logger.warning` that ships to user logs, rewrite. If it's a docstring,
deprioritize.

### 2. Commit-message narration in payloads

```bash
grep -rEn 'landed [0-9]{4}-|"scaffolded|follow-up landed|"Phase [0-9]+ follow' \
  src/prep --include="*.py" 2>/dev/null | grep -v __pycache__
```

### 3. F-NN bug IDs in user-visible strings

```bash
grep -rEn '"F-[0-9]+|f"F-[0-9]+|message.*F-[0-9]+' \
  src/prep --include="*.py" 2>/dev/null | grep -v __pycache__
```

### 4. AGENTS.md / generated-rules content

The rules generator (`src/prep/core/rules_generator.py`) writes
`AGENTS.md`, `.cursor/rules/*.mdc`, etc. into client projects. Audit
every string that flows into `_build_managed_content()` and friends —
those land in *every* downstream user's repo.

```bash
grep -nE '"Phase|F-[0-9]+|landed|follow-up' \
  src/prep/core/rules_generator.py | grep -v "^[^:]*: *#"
```

### 5. LLM-bound prompts

Anything passed as `prompt=` or `system=` to an `llm.generate()` call.
LLM-bound strings are the highest blast radius — every reasoning model
that processes them sees our internal nomenclature.

```bash
grep -rEn 'llm\.generate\(|prompt=|system=' \
  src/prep --include="*.py" 2>/dev/null | grep -v __pycache__
```

Cross-reference each prompt-builder function and check the resulting
template for Phase / F-NN / "follow-up" leaks.

### 6. Telemetry payload `remediation` / `message` fields

```bash
grep -rEn '"remediation"|"message".*Phase|"message".*F-[0-9]' \
  src/prep --include="*.py" 2>/dev/null | grep -v __pycache__
```

## How to triage a hit

For each result, decide one of three buckets:

1. **Rewrite to user-facing operational copy.** Default for log warnings,
   telemetry payloads, generated rule files, LLM prompts. Replace
   "Phase 123 follow-up landed 2026-05-07 — bump X" with "X needs to be
   increased above N".
2. **Move to a comment / docstring.** If the chronology is genuinely useful
   for a future contributor reading the source, move it to a `#` comment
   above the line and replace the runtime string with a clean version.
3. **Delete entirely.** Stale TODO-flavored breadcrumbs that don't belong
   anywhere — the chronology is in `git log`.

## Done-criteria

- [ ] All six search recipes return zero non-comment / non-docstring hits in
      `src/prep/`, OR every hit is explicitly triaged in this README.
- [ ] A `grep -rEn '"Phase [0-9]+'` run on the source tree returns only
      docstring or comment matches (no string-literal matches).
- [ ] Generated AGENTS.md content (`rules_generator._build_managed_content()`)
      contains no Phase / F-NN references.
- [ ] LLM prompts that go to `llm.generate()` contain no Phase / F-NN
      references in their template text.
- [ ] A regression test mirroring `test_pipeline_telemetry.test_record_event_silently_drops_phase_kwarg`
      exists for any other store/log API that previously took dev-number
      kwargs.

## Dependencies / non-goals

- **Not a renaming pass.** Class names like `SwarmOrchestrator`,
  `PipelineScheduler`, `ConceptStore` stay — they're the project's actual
  public API surface for in-process callers. The leak is when those internal
  names appear in *user-facing copy* (e.g. *"bump SwarmOrchestrator
  max_wall_time_s"* — a user doesn't run SwarmOrchestrator, they set an env
  var or a settings field).
- **Not a comment cleanup.** Comments and docstrings are out of scope.
  Future contributors reading source benefit from chronology breadcrumbs;
  end-user telemetry consumers don't.
- **Not a CHANGELOG generation.** Phase numbers in commits and the master
  TODO are the right home for chronology — don't try to scrub git history.

## Tooling option (deferred)

A custom Ruff rule or a `tools/check_dev_leaks.py` pre-commit hook could
enforce these patterns going forward. Out of scope for the initial sweep
but worth scoping after the manual pass demonstrates which patterns are
worth automating. The recipes above are the spec for that hook.
