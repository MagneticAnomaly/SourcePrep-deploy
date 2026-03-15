# Phase 49: Multi-Model Provenance (Mid-Stage Model Swap)

## The Edge Case

Users can pause the pipeline mid-stage, change their LLM model in AI Gateway, and resume. The incremental workers skip already-processed entries and continue with the new model. The resulting JSONL file contains entries produced by **multiple models**.

Example: User starts Fast Catalogue with `qwen3:8b`, pauses at 40%, switches to `qwen3:14b`, resumes.

```
trace_augmented.jsonl:
  line 1-100:   model = "qwen3:8b"      (from first run)
  line 101-247: model = "qwen3:14b"     (from resumed run)
```

## What We Already Have

Every entry in the LLM-produced JSONL files has per-entry model attribution:

| File | Model Field | Timestamp Field |
|------|-------------|-----------------|
| `trace_augmented.jsonl` | `model` | `augmented_at` |
| `trace_epistemic.jsonl` | `model` | `enriched_at` |
| `trace_inferred_edges.jsonl` | via LLM client | `created_at` |
| `trace_group_reasoning.jsonl` | `model` | `created_at` |

This means we can compute a per-model breakdown by scanning the JSONL file. **No new data capture needed.**

## What's Currently Wrong

The stage manifest (`trace_augment_manifest.json`) only records the model from the **last** worker run. If model A processed 60% and model B processed 40%, the manifest says "model B" — losing model A entirely.

## Solution: Multi-Model Breakdown in Provenance

### Backend: Enhanced Quality Aggregation

Add a `model_breakdown` field to the quality metrics computed by `aggregate_quality_metrics()`. Instead of just avg_confidence across all entries, also group by model:

```json
{
  "quality": {
    "total_items": 247,
    "avg_confidence": 0.85,
    "model_breakdown": [
      {
        "model": "qwen3:8b",
        "count": 100,
        "percentage": 40.5,
        "avg_confidence": 0.82
      },
      {
        "model": "qwen3:14b",
        "count": 147,
        "percentage": 59.5,
        "avg_confidence": 0.87
      }
    ]
  }
}
```

This is computed at manifest-write time by scanning the JSONL file. Cost: one pass through the file (~milliseconds for typical repos).

### Backend Changes

1. **`provenance.py`** — New function `aggregate_model_breakdown(jsonl_path, model_field="model")`:
   - Scans JSONL, groups entries by `model` field
   - Returns list of `{model, count, percentage, avg_confidence}`
   - Only returns breakdown when >1 model is present (single-model = no breakdown)

2. **`_write_stage_manifest_and_update_run()`** in orchestrator — Include `model_breakdown` in manifest quality metrics

3. **Provenance API** — Include `model_breakdown` in response when present

### Frontend Display

**Single model (common case)** — exactly as today:
```
  (o) Fast Catalogue           Fast     [check]
      95% coverage · 87% conf
      qwen3:14b via ollama · 2m 31s · today · v0.9.0
```

**Multiple models (swap case)** — show the dominant model with a split indicator:
```
  (o) Fast Catalogue           Fast     [check]
      95% coverage · 85% conf
      qwen3:14b (60%) + qwen3:8b (40%) · 2m 31s · today
```

This is still one line. The key insight: **don't show two detail lines** — that would be confusing and cluttered. Instead, condense the multi-model info into a single readable format:

```
{dominant_model} ({pct}%) + {other_model} ({pct}%) · {elapsed} · {date}
```

If there are more than 2 models (rare), show top 2 and "+N more":
```
qwen3:14b (50%) + qwen3:8b (30%) +1 more · 2m 31s · today
```

### Why One Line, Not Two

- Two detail lines per stage would double the visual weight and break the compact pipeline view
- Users don't need per-model timing breakdowns — they need to know "is my data from one model or mixed?"
- The percentage split instantly communicates the ratio
- If they want deep detail, the full manifest JSON is available via API

### Type Changes

```typescript
// Add to StageProvenance
export interface StageProvenance {
  // ... existing fields ...
  model_breakdown?: {
    model: string;
    count: number;
    percentage: number;
    avg_confidence?: number;
  }[];
}
```

### Frontend Helper Update

```typescript
function formatProvenanceLine(p: StageProvenance): string {
  const parts: string[] = [];
  
  // Model(s)
  if (p.model_breakdown && p.model_breakdown.length > 1) {
    // Multi-model: show split
    const sorted = [...p.model_breakdown].sort((a, b) => b.count - a.count);
    if (sorted.length === 2) {
      parts.push(`${sorted[0].model} (${sorted[0].percentage}%) + ${sorted[1].model} (${sorted[1].percentage}%)`);
    } else {
      parts.push(`${sorted[0].model} (${sorted[0].percentage}%) + ${sorted[1].model} (${sorted[1].percentage}%) +${sorted.length - 2} more`);
    }
  } else if (p.model) {
    parts.push(p.provider ? `${p.model} via ${p.provider}` : p.model);
  } else {
    // ... existing non-LLM stage logic
  }
  
  // ... rest unchanged
}
```

## Implementation Plan

### Sprint 1: Backend (2-3 hours)

1. **`provenance.py`** — Add `aggregate_model_breakdown()` function
2. **Orchestrator** `_write_stage_manifest_and_update_run()` — Include breakdown in quality
3. **Provenance API** — Include `model_breakdown` in response

### Sprint 2: Frontend (1-2 hours)

1. **`types.ts`** — Add `model_breakdown` to `StageProvenance`
2. **`GraphEnrichmentPipeline.tsx`** — Update `formatProvenanceLine` for multi-model display

### Sprint 3: Testing (1 hour)

1. Unit test: `aggregate_model_breakdown` with single model
2. Unit test: `aggregate_model_breakdown` with multiple models
3. Visual test: verify multi-model line renders correctly

**Total: 4-6 hours**

## Edge Cases

### Only One Model (99% of cases)
`model_breakdown` is `undefined` or has length 1. Frontend uses existing single-model display. Zero visual change.

### Model Names Are Long
`qwen3-coder-next:cloud (60%) + qwen3.5-27b:q8 (40%)` could be long. The detail line already has `truncate` CSS, so it clips gracefully. The full info is in the manifest JSON.

### Deepening Loop (Multiple Iterations)
Deepening runs multiple iterations. If the model changes between iterations, the breakdown captures this naturally — each entry has its own model field.

### Knowledge Embedding Stages
Embedding stages don't use LLMs, so `model_breakdown` is always empty. No change needed.

### Zero Entries From One Model
If the user paused at 0% and resumed with a new model, there are 0 entries from model A. Breakdown only shows model B — effectively single-model.

## Decision: Build Now or Defer?

**Recommendation: Build the backend aggregation now, defer the frontend until someone hits it.**

The backend change is small (one new function in `provenance.py`) and ensures we capture the data correctly from day one. The frontend change is also small but lower priority — the current single-model display is accurate for 99% of users. When someone does swap models, the worst case is the detail line shows the last model used (which is still useful, just incomplete).

Alternatively, build both now — it's only 4-6 hours total and the multi-model line format is clean and doesn't add complexity to the UI.
