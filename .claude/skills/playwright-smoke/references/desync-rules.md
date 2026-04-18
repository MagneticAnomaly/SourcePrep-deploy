# Desync Canonicalisation Rules

Both API state and DOM state are normalised to a four-state canon before
diffing: `pending`, `running`, `complete`, `failed`. The harness only flags
disagreements that survive canonicalisation.

## DOM → canon

Source: `DOM_STATE_TO_CANON` in `tools/playwright_smoke.py`.

| `data-stage-state` | Canon |
|---|---|
| `running` | `running` |
| `rerunning` | `running` |
| `queued` | `pending` |
| `not_built` | `pending` |
| `disabled` | `pending` |
| `paused` | `pending` |
| `complete` | `complete` |
| `stale` | `complete` |
| `warning` | `complete` |
| `error` | `failed` |
| (empty / unknown) | `pending` (defensive) |

Rationale: `paused` and `disabled` are intentional non-running states from
the user's perspective, so we treat them as "not actively progressing"
which is closest to `pending`. `stale`/`warning` mean a stage has output
but it may be out of date — still `complete` at the state-machine level.

## API → canon

The harness does **not** read per-stage status directly. It computes a
verdict from the group phase + the group's `current_stage`:

1. Group phase is `running` and `current_stage == this stage` → `running`
   (with optional progress %).
2. Group phase is `running` and this stage is **earlier** in `STAGE_ORDER`
   than `current_stage` → `complete` (already done in this run).
3. Group phase is `running` and this stage is **later** than
   `current_stage` → `pending` (this run hasn't reached it).
4. Anything else → **no verdict** (None). The harness refuses to compare
   against ambiguous API state — this is by design and avoids the
   "panel may legitimately show last-known state between runs" false
   positives that plagued earlier versions.

Source: `api_stage_verdict()` in `tools/playwright_smoke.py`.

## Disagreement kinds

| Kind | Trigger |
|---|---|
| `api_running_dom_not_running` | API verdict = `running`, DOM canon ≠ `running` |
| `api_complete_dom_still_running` | API verdict = `complete`, DOM canon ∈ {`running`, `failed`} |
| `progress_gap` | Both running, but `abs(api_pct - dom_pct) > 5` |
| `dom_claims_running_while_api_idle` | No group is running, but DOM canon = `running` for some stage |

Each `(stage_id, kind)` pair fires at most once per transition.
