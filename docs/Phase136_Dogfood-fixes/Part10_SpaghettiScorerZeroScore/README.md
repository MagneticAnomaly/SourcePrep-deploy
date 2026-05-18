# Part 10 — Spaghetti scorer silent zero-score regression

> **Status:** Stub / awaiting investigation
> **Trigger:** 2026-05-17 rebuild telemetry vs 2026-05-11 baseline
> **Work order:** ships third in Phase 136 (after Parts 02 and 09)

## The bug in one paragraph

The spaghetti scorer ran on the 2026-05-17 rebuild and **scored zero
files**. No exception, no error event, no log entry. The next stage
(audit synthesis) continued normally on the empty hotspot list.
Six days earlier (2026-05-11), the same scorer over a similar file
set produced 657 scored files with 35 critical hotspots. Something
broke between those two builds and nothing caught it.

## Evidence

**2026-05-17 (current):**

```json
{"event": "spaghetti_scored",
 "file_count": 1961, "scored_count": 0,
 "severity_counts": {}, "top_hotspots": []}
```

**2026-05-11 (last known good):**

```json
{"event": "spaghetti_scored",
 "file_count": 1902, "scored_count": 657,
 "severity_counts": {"critical": 35, "warning": 413, "info": 209},
 "top_hotspots": [
   {"file_path": "packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx", ...},
   {"file_path": "src/prep/core/audit/synthesizer.py", ...},
   {"file_path": "src/prep/services/pipeline/recovery.py", ...},
   {"file_path": "src/prep/core/group_reasoning.py", ...},
   {"file_path": "packages/ui/src/components/enterprise/EnterpriseAdminPanel.tsx", ...}
 ]}
```

Same scorer, same kind of input (~2000 files), 657 → 0.

## Investigation plan

1. **Locate the scorer.** Grep for `spaghetti_scored` event emission;
   should land in `src/prep/core/audit/` or `src/prep/services/pipeline/`.
2. **Bisect the 2026-05-11 → 2026-05-17 commit range.** `git log
   --since 2026-05-11 --until 2026-05-17 -- src/prep/core/audit/
   src/prep/services/pipeline/`. The breakage is in this window.
3. **Reproduce locally.** Once the scorer entry point is known, run
   it directly against the current index without the full pipeline.
   See whether the iterator is empty, the threshold dropped everything,
   or the scoring returns falsy.
4. **Identify the silent-failure path.** Whatever it is — empty input
   set, all-zero scores filtered out, default cutoff inverted — the
   path needs a loud warning, not a silent zero.

## Hypotheses to test (refined 2026-05-17 after code read)

The scorer at `src/prep/core/audit/spaghetti_scorer.py:205` reads
seven signals per file and computes a percentile-normalized composite
score. Files below `INFO_THRESHOLD` are filtered out via
`continue # Skip healthy files` (line 351). The 2026-05-17 telemetry
shows `file_count: 1961, scored_count: 0` — meaning `ctx.file_nodes`
was populated but **every file fell below INFO_THRESHOLD**.

Three of the seven score signals come from LLM-derived data:
- `W_LOW_CONFIDENCE * n_conf[i]` — reads `ctx.epistemic[nid]["epistemic_confidence"]`
- `W_TECH_DEBT * n_td[i]` — reads `ctx.epistemic[nid]["tech_debt"]`
- `W_FAN_OUT/IN` — reads `ctx.in_degree/out_degree`

**Leading hypothesis (LLM-signal collapse):** Phase 134's
Changeset-driven pipeline may have changed how `ctx.epistemic` and
`ctx.augmentations` are loaded into `AuditContext`. If every file's
`epi_confidence == -1.0` (the "no data" sentinel), `conf_raw` becomes
all-`0.5`, percentile normalization yields a constant array, and the
W_LOW_CONFIDENCE term contributes nothing variant. Same for
`tech_debt` if `epi.get("tech_debt")` is always empty. The composite
score's variance collapses, every file scores below INFO_THRESHOLD.

**Secondary hypothesis (degree collapse — same root cause as Part 02):**
If `ctx.in_degree(nid)` and `ctx.out_degree(nid)` are skewed because
of the bimodal-node bug (Part 02), all files with package-style
imports look orphaned, dragging fan_in/fan_out percentiles toward
zero across the board.

**Tertiary hypothesis (audit context migration regression):** Phase
134 commits `9b9e10a31` (`audit StalenessAnalyzer rewrite — orphan +
coverage-gap checks`) and adjacent `feat(phase134): drop vestigial
ctx.file_hashes from AuditContext` may have changed AuditContext
construction. Check the AuditContext loader pre/post Phase 134.

## Why fixing is non-trivial

This is a *score collapse*, not a single broken line. The proper fix
requires understanding which signals collapsed and either restoring
the underlying data source OR adjusting thresholds. A guard rail
(emit WARNING when `scored_count == 0` AND `file_count > 100`) is the
load-bearing minimum to prevent the next silent regression.

## Files likely touched

- `src/prep/core/audit/spaghetti_*.py` (find by grepping the event name)
- `src/prep/services/pipeline/*.py` (audit stage wiring)
- Possibly `src/prep/core/audit/analyzers/` (analyzer composition)

## Test plan

### Layer 1 — pytest

- `tests/test_spaghetti_scorer_emits_findings.py` (new)
  - Fixture: a tmp project with known structural debt (e.g. an
    obviously-circular import + one large file).
  - Run the scorer.
  - Assert `scored_count > 0` and `top_hotspots` non-empty.
  - This test would have caught the regression on 2026-05-11 → 17.

### Layer 2 — live telemetry assertion

After fix, a fresh rebuild of `.sourceprep/` shows
`spaghetti_scored.scored_count >= 100` and `severity_counts` non-empty.
The known critical files (`audit/synthesizer.py`,
`group_reasoning.py`, `pipeline/recovery.py`, etc.) reappear in
`top_hotspots`.

### Layer 3 — guard rail

Add an event-level assertion: if `scored_count == 0` AND
`file_count > 100`, emit a WARNING-level log
`spaghetti_scorer_zero_score` with the configured thresholds. Future
silent regressions become loud.

## Acceptance

Part 10 is shipped when:

1. Root cause identified by bisecting the 2026-05-11 → 2026-05-17
   commit range.
2. Live rebuild produces non-empty `top_hotspots` on the SourcePrep
   repo itself.
3. The warning guard rail is added — `scored_count == 0` on a
   non-empty file set is no longer silent.

## Risks

- **Bisect window could be wide** if many commits touched audit
  internals. Mitigation: focus on `spaghetti_*` and `audit/analyzers/`
  changes first.
- **The regression could be intentional.** A recent refactor may have
  moved scoring logic without telling the telemetry layer. Mitigation:
  if intentional, replace the `spaghetti_scored` event with whatever
  superseded it.

## Cross-refs

- `00_Status_2026-05-17.md` — telemetry comparison
- 2026-05-11 telemetry baseline (same file, earlier entries)
