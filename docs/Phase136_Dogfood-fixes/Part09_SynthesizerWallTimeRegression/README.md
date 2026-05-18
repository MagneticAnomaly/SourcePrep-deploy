# Part 09 — Synthesizer wall-time regression (1334 questions lost)

> **Status:** Stub / awaiting investigation
> **Trigger:** 2026-05-17 rebuild telemetry; `project_synthesizer_wall_time_regression` memory
> **Work order:** ships second in Phase 136 (after Part 02)

## The bug in one paragraph (CORRECTED 2026-05-17)

Concept-synthesis at `concept_seeder.py:903` emits
`concepts_synthesis_failed`, but **the data is not lost**. The
fallback path at `concept_seeder.py:870-892` merges worker outputs by
deduping concepts on title and questions on `(text, target_module)`,
saving them as seed concepts and pending questions. The 2026-05-17
run resulted in 1795 module-rationale concepts (all at seed status)
and 1334 questions (pending). The `prep()` output confirms both are
saved and retrievable.

The **actual regression** is quality: the synthesis pass produced
empty output despite running within budget (914s stage elapsed; cloud
cap is 1500s per `concept_seeder.py:676` — the 2026-05-02 bump *did*
land in this path). Synthesis isn't timing out, it's returning
empty/unparseable. Worker outputs survive as seed but bypass the
validation pass that promotes high-quality, semantically-coherent
concepts to "active" status.

The remediation message ("increase the swarm wall-time budget") is
misleading — wall time is not the failure mode.

## What `prep()` confirms

```
15 concepts (9 active, 0 seed, 6 triage)
+ 1795 module rationale (0 active, 1795 seed)
+ 1334 questions pending
```

- **15 active/triage**: came from the Phase 125c multi-pass
  refinement pass (separate from concept_seeder)
- **1795 seed**: fallback worker concepts, saved but not validated
- **1334 pending**: fallback worker questions, saved

Data preserved. Quality of curation is what regressed.

## Evidence (verbose telemetry, run-50071c9e0869)

```json
{"ts": "2026-05-17T20:27:11Z",
 "event": "concepts_synthesis_failed",
 "fallback_concepts": 1795, "fallback_questions": 1334,
 "worker_count": 798, "successful_workers": 798,
 "remediation": "Synthesis produced no concepts. Worker outputs were merged
  as a fallback. To recover synthesis, increase the swarm wall-time budget
  for the configured cloud model."}
```

Stage elapsed: 914.37s. The synthesizer is given budget _after_ workers
complete, so worker phase consumed the lion's share.

A separate `generate_swarm_complete` later in the same stage recovered
18 candidates → 9 activated + 6 triaged + 3 archived via Phase 125c
multi-pass refinement. So the *concepts that show up in `prep()`* are
real and useful. The 1334 questions, though, are gone.

## Investigation plan (REVISED 2026-05-17)

1. **Inspect the synthesizer LLM output for the 2026-05-17 run.** The
   synthesis call returns "no concepts" — was the response empty,
   unparseable, or did the parser reject it? Add structured logging
   inside the synthesis path that records the raw LLM response on a
   failed parse. Without that, we're guessing.
2. **Compare synthesis prompt size pre/post Phase 124 T4 enrichment.**
   T4 adds ~+2.5K chars per worker prompt. For 798 workers the
   synthesis pass sees a much larger consolidation prompt; the model
   may be hitting an output-token cap before producing valid JSON.
3. **Hypothesis: output-token budget exhausted.** Cloud-LLM
   `synthesis_timeout_s=600s` is sufficient for ~500-worker runs but
   the consolidation prompt for 798 workers may exceed the model's
   output token budget, returning a truncated/empty response.
4. **Path A — chunk the synthesis pass.** Synthesize in batches of
   200 workers, then synthesize the synthesis outputs. Avoids
   single-prompt token cap.
5. **Path B — feed the multi-pass refinement (Phase 125c) the
   synthesis-failed worker outputs.** Currently 1795 seed concepts
   sit unpromoted because the refinement loop expects high-quality
   synthesis input. Wire the seed-concept set into refinement as a
   distinct intake source.

Both paths complementary: Path A restores synthesis on large repos;
Path B prevents quality cliffs when synthesis still fails.

## Already verified

- `concept_seeder.py:676` IS at `max_wall_time_s=1500.0` for cloud.
  The 2026-05-02 bump landed in this path.
- `concept_seeder.py:665-667` also at the bumped `300s`/`600s`/`180s`
  per-phase timeouts.
- `cluster.py:1528` and `group_reasoning.py:495` are still at 900s
  cloud cap. These are DIFFERENT swarm paths (cluster synthesis ≠
  concept synthesis) and were not affected by this finding.
  Possible follow-up: do they need the same bump? Out of scope for
  Part 09 unless evidence of failure surfaces.

## Files likely touched

- `src/prep/core/cluster.py` — synthesis prompts, fallback path
- `src/prep/core/swarm_orchestrator.py` — wall-time budget
- `src/prep/services/concept_*.py` — concept generation pipeline
- LLM endpoint / task assignment config — per-task budgets

## Test plan

### Layer 1 — pytest

- `tests/test_synthesis_fallback_preserves_questions.py` (new)
  - Force a synthesis timeout in a fixture.
  - Assert `fallback_questions` > 0 are still individually saved,
    not just counted.

### Layer 2 — live MCP probe

```
Before: prep() → "1334 questions pending. Use prep_concepts to explore."
        (questions counted but not retrievable as discrete items)

After:  prep_concepts(action=questions) returns the 1334 questions
        OR a successful synthesis stage emits real concepts and the
        pending count is much lower (target: < 200)
```

### Layer 3 — telemetry assertion

`pipeline_telemetry.jsonl` from a post-fix run does NOT contain
`concepts_synthesis_failed`, OR contains it with
`fallback_questions=0`.

## Acceptance

Part 09 is shipped when:

1. The 2026-05-02 budget bump status is documented (landed or not).
2. Synthesis on the SourcePrep repo itself completes without falling
   back, OR the fallback path preserves the 1334 questions losslessly.
3. A regression test fires before another silent question-loss event
   ships.

## Risks

- **Bigger budget hides workload growth.** If we just bump to 2400s,
  the next swarm scale-up trips the same wall. Mitigation: ship
  Path B (lossless fallback) as the structural fix, then Path A is a
  buffer.
- **Cost.** Bumping cloud-model wall time costs LLM tokens. Verify
  the bump is necessary; don't over-allocate.

## Cross-refs

- `project_synthesizer_wall_time_regression` memory (saved 2026-05-02)
- `00_Status_2026-05-17.md` — Probe 1 + telemetry evidence
- Phase 123 + Phase 125c — concept-pipeline history
