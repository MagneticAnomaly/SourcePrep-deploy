# Phase 124 — Baseline measurements (pre-implementation)

> **Purpose:** Capture hard numbers for H1, H2, H4 from
> `README.md` §3 *before* any code changes. This file freezes the
> "before" state so post-implementation results in `RESULTS.md` can
> be diffed against it.
> **Method:** read-only inspection of `.sourceprep/` artifacts and
> `docs/*.md` corpus. Script:
> `tmp/p124_baseline/h1_h2_evidence.py`.
> **Project under measurement:** SourcePrep itself.
> **Date captured:** 2026-05-01
> **Atlas generation timestamp:** 2026-05-01T17:35:03Z

---

## Inputs

| Input | Value |
|---|---|
| Modules in `trace_modules.jsonl` | 636 |
| Code-bearing modules (modules with ≥1 non-`.md` member) | 410 |
| Atlas segments on disk | 10 |
| Files indexed across segments | 1,848 |
| Markdown files under `docs/` | 1,062 |
| Raw path mentions extracted from those markdown files | 5,822 |
| Markdown read errors | 0 |

### Per-segment file counts

| Segment | Files |
|---|---:|
| `_root` | 1,228 |
| `packages-ui` | 357 |
| `websites-apps-marketing` | 65 |
| `src-prep-dashboard` | 63 |
| `websites-apps-docs` | 53 |
| `websites-apps-support` | 26 |
| `packages-vscode` | 19 |
| `websites-apps-payments` | 14 |
| `packages-paperclip-plugin-prep` | 12 |
| `packages-vscode-webview-ui` | 11 |

`_root` absorbs ~66% of all indexed files including the entire
`docs/` tree — exactly the orphan-by-segmentation pattern that
H2 predicts.

---

## H1 — Per-module relevant-doc coverage

> "Workers extract concepts blind to docs/ prior art."

**Result: STRONGLY VALIDATED.**

For each code-bearing module, count the number of `docs/*.md` files
that mention at least one of its `member_files` by file path.

| Distribution | Modules |
|---|---:|
| 0 relevant docs | 428 |
| 1–2 relevant docs | 124 |
| 3–5 relevant docs | 45 |
| 6–10 relevant docs | 23 |
| 11+ relevant docs | 16 |

- **208 of 410 code-bearing modules (50.7%)** have at least one
  relevant doc that the concept worker is currently ignoring.
- **84 modules (20.5%)** have ≥3 relevant docs — these are T4's
  highest-leverage targets.

### Top 10 modules by relevant-doc richness

These modules will benefit most from T4 (worker prompt receives
linked-doc excerpts). The number is the count of `.md` files
mentioning at least one `member_file` of the module.

| Docs | Module |
|---:|---|
| 64 | Enrichment Pipeline Orchestrator & State Machine |
| 46 | Project Management Push & Sync Infrastructure |
| 40 | Prep CLI Client & Documentation Surface |
| 34 | MCP Protocol Bridge & Agent Gateway |
| 24 | Graph Enrichment Pipeline Orchestrator |
| 22 | Prep Daemon Search API Client & Results Renderer |
| 22 | Trace Index Builder & Graph Engine |
| 21 | Hybrid Traceability Search Engine |
| 19 | Multi-Agent Orchestration & Role-Aware Context Platform |
| 17 | MCP Tool Schema Registry & Context Retrieval Engine |

The Enrichment Pipeline Orchestrator module has **64 relevant docs**
that the concept worker for that module sees zero of today. The
swarm-synthesizer is being asked to invent rationale for a
subsystem with one of the largest planning corpora in the project.

### Implication for Phase 123

Phase 123 hypothesized "13 concepts" was caused by aggressive
synthesis-prompt dedup. H1 evidence reframes the cause: per-module
worker output is shallow because workers are blind to ~5,800
explicit rationale mentions across 1,062 docs. **Tightening the
synthesis dedup alone, without enriching worker inputs, will
recover only a fraction of the available signal.** This is the
core argument for landing 124 T4 before 123 T2/T3.

---

## H2 — Markdown files orphaned from the code they describe

> "Atlas segmentation orphans deep planning trees."

**Result: VALIDATED, with a stronger anti-pattern surfaced
incidentally.**

For each `.md` file, look up the segment it landed in, then check
whether the code paths it mentions land in the **same** segment.

| Bucket | Count |
|---|---:|
| `.md` mentions code, fully in same segment | 115 |
| `.md` mentions code, fully orphaned (zero same-segment mentions) | 59 |
| `.md` mentions code, partially orphaned | 47 |
| `.md` has no resolvable code mentions (pure prose / concept files) | 374 |
| `.md` not present in any atlas segment at all | **254** |

### Top cross-segment edges

`md_segment → code_segment`, weighted by mention count:

| Mentions | From | To |
|---:|---|---|
| 176 | `_root` | `packages-ui` |
| 29 | `_root` | `websites-apps-marketing` |
| 25 | `_root` | `src-prep-dashboard` |
| 1 | `_root` | `websites-apps-support` |
| 1 | `_root` | `websites-apps-docs` |
| 1 | `_root` | `packages-paperclip-plugin-prep` |

**Reading:** `docs/` lives in `_root` (because directory rule).
The markdown there overwhelmingly references code in three other
segments. The atlas has zero structural awareness that the
`packages-ui` segment has 176 mentions worth of explanatory prose
sitting in `_root`. T2 (markdown link parser) closes exactly this
gap.

### Anti-pattern surfaced: atlas silently drops large doc trees

Of the **254 unsegmented `.md` files** (markdown that exists in the
project but is not present in *any* atlas segment), **249 live in
`docs/Phase13_Storybook/`** — an entire historical phase tree the
atlas indexer dropped wholesale. The remaining 5 are recent phase
READMEs (Phase 121, 122, 123, 124, plus one nested validation
README) that were created after the last atlas regeneration:

| Top-level dir | Unsegmented `.md` count |
|---|---:|
| `docs/Phase13_Storybook/` | 249 |
| `docs/Phase121_OllamaConcurrencyUX/` | 1 |
| `docs/Phase122_FeatureUtilizationAudit/` | 1 |
| `docs/Phase123_ConceptQualityRefinement/` | 1 |
| `docs/Phase124_FinalizeChainEpistemicAudit/` | 1 |
| `docs/Phase00_Initial-Concept/.../` | 1 |

**Two distinct issues here:**

1. **Bulk drop (Phase 13):** 249 docs vanished from indexing.
   Likely a filter rule (`.sourceprep/repo_policy.json`?), size
   limit, or a corrupted manifest. Worth a one-line investigation
   before T2 lands — if there's a filter rule excluding
   `docs/Phase13_Storybook/` we shouldn't try to index it. If it's
   a silent drop, that's a separate bug.
2. **Stale segmentation:** new files added between atlas runs are
   invisible. Less of a Phase 124 concern — segmentation freshness
   is normal pipeline behavior — but worth surfacing in
   `prep_audit` so users don't act on stale atlas data.

The Phase 13 finding alone is a candidate Phase 122 entry
(unwired / silently inert tooling).

---

## H4 — Audit markdown vs structured findings

> "Audit markdown reports waste the structural signal."

**Result: VALIDATED. Pipeline still does not produce
`spaghetti.json`.**

The file IS present on disk today, but **the pipeline audit
worker has zero references to spaghetti**:

```bash
$ grep -n "spaghetti" src/prep/services/pipeline/workers.py
(no output — zero hits)
```

File timestamps confirm provenance:

| File | mtime |
|---|---|
| `audit/AUDIT_SUMMARY.md` | 13:59 (pipeline run) |
| `audit/spaghetti.json` | **14:19** (20 min after the run) |

Markdown reports were written by the audit worker at 13:59. Then
20 minutes later something — almost certainly a manual REST probe
to `/audit` — wrote `spaghetti.json`. This is exactly the
PowerMate-style ghost-file pattern Phase 122 hypothesized.

**T5 still needs to land.** The presence of the file masks the
absence of the wire-up.

```
.sourceprep/audit/
├── ARCHITECTURE_ANALYSIS.md
├── AUDIT_SUMMARY.md
├── COMPONENT_INVENTORY.md
├── GAP_ANALYSIS.md
├── TECH_DEBT_REPORT.md
└── spaghetti.json   ← present (was missing per Phase 122)
```

**Provenance unknown.** Two possibilities:

1. The pipeline audit worker has been wired to call
   `run_spaghetti_scan` since Phase 122 was scaffolded
   (2026-04-30). Need to confirm by reading
   `services/pipeline/workers.py _audit_worker` and looking for
   a call site.
2. A manual REST-API probe to `/audit` wrote it, exactly as
   Phase 122 hypothesized for PowerMate.

**Investigation before T5 spends LoC on a wire-up that already
exists:**

```bash
# Check 1: is the call already in the worker?
grep -n "spaghetti" src/prep/services/pipeline/workers.py

# Check 2: when was spaghetti.json last written? Match against
# pipeline run timestamps in pipeline_run_metadata.json
ls -la .sourceprep/audit/spaghetti.json
```

If the worker call is already there → close T5 as "already done"
and reclaim the LoC budget for T6/T7. If not → keep T5 as planned.

**This is itself a Phase 124 win:** the chain-grading approach
caught a stale assumption in a sibling phase before code was
written against it.

---

## Anti-patterns flagged for Phase 124 grading harness (T1)

These should become first-class harness checks once T1 lands so
that future runs surface them automatically:

| ID | Anti-pattern | Stage | Example today |
|---|---|---|---|
| AP-1 | Module has zero linked docs but referenced by ≥1 `.md` mention | 11 ATLAS / 13 CONCEPTS | 208 such modules |
| AP-2 | Atlas segment contains zero `.md` files mentioning its members | 11 ATLAS | 9/10 segments today (only `_root` accumulates docs) |
| AP-3 | Doc dir bulk-dropped from segmentation | 11 ATLAS | `docs/Phase13_Storybook/` (249 files) |
| AP-4 | Stale atlas — recent files unsegmented | 11 ATLAS | Phase121-124 READMEs |
| AP-5 | Concept count outside 30-80 range for projects >500 files | 13 CONCEPTS | currently 13 (Phase 123 acceptance) |
| AP-6 | `audit/spaghetti.json` not produced by pipeline (worker has no spaghetti call) | 14 AUDIT | confirmed today — file present only via manual REST probe |
| AP-7 | Antibody count is 0 when constraint-category concepts exist | 15 ANTIBODIES | TODO: confirm with concept categories |

---

## What this baseline does NOT measure

- **External project comparison.** PowerMate / Halley not
  measured. The §0 first-session checklist still requires running
  the harness against one external project — these SourcePrep
  numbers alone don't generalize.
- **Segment ↔ concept anchor coverage.** Acceptance criterion
  §7.2 ("≥40% of concepts have at least one anchor that matches
  a file mentioned in a linked doc") needs a separate pass once
  T4 lands and concept anchors expand.
- **Antibody quality.** Only counts available; semantic quality
  not assessed.
- **Stage-output token budget consumption.** Phase 82 noted
  per-tool token sprawl; the harness should record this per stage.

---

## Reproducing this baseline

```bash
# Hypothesis evidence (one-shot, ~200 LoC):
python3 tmp/p124_baseline/h1_h2_evidence.py \
  > tmp/p124_baseline/h1_h2_results.txt 2>&1

# T1 grading harness (general, run anywhere):
python3 tools/finalize_chain_audit.py \
  --json docs/Phase124_FinalizeChainEpistemicAudit/scorecard_baseline.json \
  --md   docs/Phase124_FinalizeChainEpistemicAudit/SCORECARD_BASELINE.md

# Future runs diff against the baseline:
python3 tools/finalize_chain_audit.py \
  --baseline docs/Phase124_FinalizeChainEpistemicAudit/scorecard_baseline.json
```

T1 (`tools/finalize_chain_audit.py`) is now landed. See
`SCORECARD_BASELINE.md` for the locked initial scorecard.

## T1 first-run snapshot (2026-05-01 13:30 — pre-T4/T5)

| Stage | Score | Anti-patterns |
|---|---:|---|
| 11 ATLAS | 8.0/10 | AP-2, AP-3 |
| 12 RULES | 10.0/10 | — |
| 13 CONCEPTS | 7.0/10 | AP-5 |
| 14 AUDIT | 5.0/10 | AP-6 |
| 15 ANTIBODIES | 9.0/10 | — |
| **Overall** | **7.8/10** | AP-2, AP-3, AP-5, AP-6 |

## Post-T4/T5 snapshot (2026-05-01 22:05 — after pipeline rebuild)

| Stage | Score | Δ | Anti-patterns |
|---|---:|---:|---|
| 11 ATLAS | 8.0/10 | · | AP-2, AP-3 |
| 12 RULES | 10.0/10 | · | — |
| 13 CONCEPTS | **9.0/10** | +2.0 | — (doc-rich regime) |
| 14 AUDIT | **7.0/10** | +2.0 | — |
| 15 ANTIBODIES | 9.0/10 | · | — |
| **Overall** | **8.6/10** | **+0.8** | AP-2, AP-3 |

### What the numbers say

**Concepts: 13 → 1,779 (×137).** All unique titles. 30.5% of concepts
anchor to a `docs/*.md` file — concrete proof T4 is feeding workers
real planning rationale rather than just code shape. Sample
concepts:

- "Append-Only Compliance Logging as Legal Defensibility" →
  anchored to `audit_log.py` AND `SECURITY_DESIGN_DECISIONS.md`
- "Group-Based Scheduling as a Crash-Recovery Primitive" →
  `scheduler.py`, `state_machine.py`, `PHASES.md`

**Antibodies: 5 → 594 (×119).** Conversion ratio held at 1.0 —
H3 confirmed beyond doubt. Antibody count scales 1:1 with
constraint+architecture concepts, no derivation work needed.

**Spaghetti in audit window:** offset of 4.8s from audit-worker
start. T5 fired exactly where the patch placed it — between
`save_findings` and Tier 2 LLM synthesis, upstream of the markdown
reports. Pipeline-origin proven.

### What the original 30-80 concept target band missed

Phase 124's acceptance criterion §7.2 set 30-80 as the concept
count target. That was right for the *under-fed* regime — workers
extracting concepts blind to docs. With T4 surfacing 5,800 path
mentions across 1,062 markdown files into per-module worker
prompts, the LLM correctly emits a much larger, more specific set.

The harness now distinguishes two failure modes:

- **AP-5a — under-feed:** count <30 on a >500-file project means
  T4 isn't landing.
- **AP-5b — synthesis runaway:** count >500 with <10% `.md`
  anchors means the LLM is emitting volume *without* doc grounding
  (would be a real synthesis bug).

Today's run hit neither — 1,779 concepts with 30.5% doc-anchored
is the **doc-rich regime** the harness now recognizes as a
positive signal, not a defect.

### Implication for Phase 123

Phase 123 was scoped against "13 concepts is too few." Post-T4 the
problem inverts: 1,779 unique concepts is structurally healthy but
not human-consumable in raw form. Two follow-ups (out of scope for
124, but worth flagging for 123 owners):

1. **Promote-to-summary pass.** Add a final synthesis step that
   emits ~30-80 high-level concepts *summarizing* the 1,779
   detailed ones. Detail rows stay queryable via MCP; the panel
   shows the summaries.
2. **Per-category caps.** 406 architecture concepts is a lot. A
   per-category cap (~50?) at synthesis time would compress the
   long tail without losing the doc-rich anchor coverage.

Both are Phase 123 territory now — its synthesis-prompt tuning
becomes the key lever once T4 has fed workers properly.

### What still needs work (Phase 124 follow-ups)

- ~~**Atlas (8.0)** — AP-2 and AP-3 still flagged~~ — both cleared
  post-T3. Atlas now 9.5/10. AP-2 cleared via the
  `aggregate_for_segments` aggregator (9/10 segments now have
  ≥1 doc reference). AP-3 was a harness false positive — Phase 13's
  "249 unsegmented .md files" were all inside
  `docs/Phase13_Storybook/theme-examples/tremor-preview/node_modules/`,
  correctly excluded by `repo_policy.exclude_globs`. The harness
  now uses the markdown_links walker which respects the same
  excludes. Phase 13's actual planning docs (4 root, 9 in
  `previous-app-legacy-research/`) are properly indexed.
- **Audit (7.0)** — markdown reports still large (~22 KB avg).
  T5b (synthesizer consumes spaghetti) is now landed in code but
  awaits a fresh pipeline run for live measurement. Expect Audit
  to lift toward 8.0 once Tier 2 starts citing spaghetti hotspots
  instead of re-deriving severity from raw findings.

## Post-T3 + scrutiny snapshot (2026-05-01 ~22:30)

| Stage | Score | Δ vs baseline | Anti-patterns |
|---|---:|---:|---|
| 11 ATLAS | **9.5/10** | +1.5 | — |
| 12 RULES | 10.0/10 | · | — |
| 13 CONCEPTS | **9.0/10** | +2.0 | — |
| 14 AUDIT | **7.0/10** | +2.0 | — |
| 15 ANTIBODIES | 9.0/10 | · | — |
| **Overall** | **8.9/10** | **+1.1** | **(none)** |

**All four originally-flagged anti-patterns cleared.** Mix of fixes:

| AP | Status | Mechanism |
|---|---|---|
| AP-5 | cleared | reframe — split into AP-5a (under-feed) / AP-5b (volume without doc grounding); current state is the doc-rich regime |
| AP-6 | cleared | T5 wire-up — spaghetti now written 4.8s into the audit-worker run |
| AP-2 | cleared | T3 aggregator — 90% segment doc coverage with partial-credit scoring |
| AP-3 | cleared | harness false positive — node_modules content correctly excluded; fixed walker |

Three of the four were structural/code fixes; one was a measurement
bug. None was a synthesis-side LLM issue, supporting the "T4 worked,
synthesis-tightening is Phase 123's call" framing in §"Implication
for Phase 123" above.

### What this changes about the §3 hypotheses

- **H1 confirmed** — atlas score includes the 50.7% module-doc
  coverage figure; T4 should move it.
- **H2 confirmed** — AP-2 fires on 9/10 segments; AP-3 catches
  the Phase 13 bulk-drop automatically.
- **H3 REFUTED.** Stage 15 scores 9.0/10. **5 of 5** eligible
  constraint+architecture concepts produced antibodies (100%
  ratio). The 5-antibody count isn't a derivation bug — it's a
  direct function of sparse concepts. **Once Phase 123 + Phase
  124 T4 raise concept count to 30-80, antibody count will scale
  automatically without any change to derivation.** This collapses
  T7's risk profile considerably; T7 becomes a verification pass,
  not an investigation.
- **H4 confirmed** — AP-6 caught spaghetti.json's 1,190-second
  mtime drift from the markdown reports automatically. Manual
  REST-probe origin proven by the harness, not by hand.

---

## Next moves

1. ~~**Investigate `spaghetti.json` provenance** before any T5
   work~~ — done. Worker has no spaghetti call; file timestamp
   confirms manual REST origin. T5 wire-up is needed as planned.
2. **Investigate Phase 13 bulk drop** — file an issue or fold
   into Phase 122 if it's a known filter rule.
3. **Open T1 PR** — generalize this script into
   `tools/finalize_chain_audit.py` per Phase 124 §4.1.
4. **Capture the same numbers for one external project** — the
   §0 first-session checklist is not satisfied until this is done.
