# 07 — Dogfooding Log

Rolling log of observations from manual overseer simulations and
checkpoint-signal analysis. Template today; fill in as runs are captured.

## Log format

```
### <YYYY-MM-DD> — <project_id> — run <run_id>

**Checkpoint:** <checkpoint name / number>
**Gate signal that fired:** <e.g. "swarm synthesis stddev = 0.42 on group X">
**Input to overseer:** <brief: what we gave Opus>
**Overseer verdict:** <pass / flag / re-run / escalate>
**Rubric scores:** <JSON from the rubric>
**Ground truth:** <was it actually wrong? how do we know?>
**Catch category:** <true-positive / false-positive / true-negative / false-negative>
**Cost:** <tokens in / out, $ estimate>
**Latency:** <seconds>
**Notes:** <anything surprising>
```

## Rolling summary table

Maintain at the top of this file as entries accumulate:

```
| Checkpoint | Fired | TP | FP | TN | FN | Catch rate | Avg cost | Avg latency |
|---|---|---|---|---|---|---|---|---|
| #1 Swarm synthesis |   |   |   |   |   |   |   |   |
| #2 Concept promotion |   |   |   |   |   |   |   |   |
| #3 Audit synthesis |   |   |   |   |   |   |   |   |
| #4 Hub mutations |   |   |   |   |   |   |   |   |
| #5 Role atlas |   |   |   |   |   |   |   |   |
| #6 Epistemic anomalies |   |   |   |   |   |   |   |   |
| #7 Inferred edge |   |   |   |   |   |   |   |   |
| #8 Cross-cutting |   |   |   |   |   |   |   |   |
| #9 Validation rejection |   |   |   |   |   |   |   |   |
| #10 Antibody grounding |   |   |   |   |   |   |   |   |
| #11 Deepening convergence |   |   |   |   |   |   |   |   |
| #12 Filter universality |   |   |   |   |   |   |   |   |
```

---

## Entries

*(No entries yet. First entries will be from historical-build analysis
using the `checkpoint_signals.json` script described in `06_`.)*
