# Phase 145 Finding — Edge Discovery completion time is hard to interpret (cache hits look like live runs); rebuild progress bar style switches mid-run

**Status:** Open. 2026-06-19. Two related observations from the same Rebuild session, kept together because they surfaced from the same user prompt.
**Found:** 2026-06-19, Eric. HomeColab and SourcePrep cross-comparison.
**Severity:** Medium for the manifest-reporting issue; Low (cosmetic) for the progress-bar style lag.
**Linked symptom in README:** §2t.

---

## 1. Symptom (as reported)

User clicked Rebuild All on HomeColab:

> "this just ran through the edge discovery in 21 seconds for a rebuild and that's seem way too fast. did it actually do that task?"

Plus a UX observation on rebuild start:

> "very minor issue when I first started the rebuild it showed the blue progress bar like initial but then switched to the rebuild-style progress bars about 1/3 the way through edge discovery (about 7 seconds) about the same point that the top 'Rebuilding All stage 2/15' banner appeared."

## 2. Direct answer to "did Edge Discovery actually do that task?" — yes on HomeColab, but the way it's reported makes adjacent runs ambiguous

### 2.1 HomeColab — Edge Discovery genuinely ran

Direct read of `/Volumes/Thunderbolt/XcodeProjects/HomeColab/.sourceprep/trace_inferred_manifest.json` confirms the work:

```json
"started_at":       "2026-06-19T13:28:17.766008+00:00",
"finished_at":      "2026-06-19T13:28:38.474187+00:00",
"elapsed_seconds":  20.71,
"model":            "kimi-k2.7-code:cloud via ollama",
"quality": {
  "total_items": 171, "processed": 171, "skipped": 0, "failed": 0,
  "success_rate": 1.0,
  "avg_confidence": 0.843, "min_confidence": 0.6, "max_confidence": 1.0,
  "parse_errors": 0
},
"output_files": { "trace_inferred_edges.jsonl": { "item_count": 171, "size_bytes": 77219 } },
"throughput":   { "items_per_second": 8.26 }
```

`wc -l trace_inferred_edges.jsonl` → 171 lines, matches `item_count`. **8.26 items/sec is plausible cloud-LLM throughput for a small project.** 171 items × ~120ms per inference, batched moderately, lands in the 20-second range.

### 2.2 SourcePrep — the same stage's manifest from the daemon-restart screenshot was actually mostly cache hits

Cross-check, same model: `/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/trace_inferred_manifest.json`:

```json
"started_at":       "2026-06-19T12:10:34.439113+00:00",
"finished_at":      "2026-06-19T12:10:35.266885+00:00",
"elapsed_seconds":  0.82,
"quality": {
  "total_items": 214, "processed": 214, "skipped": 0, "failed": 0,
  "success_rate": 1.0,
  "avg_confidence": 0.771
},
"throughput":   { "items_per_second": 260.51 }
```

**214 items in 0.82s = 260.51 items/sec.** With the same model, on the same backend, HomeColab gets 8.26/sec and SourcePrep gets 260.51/sec — a 30× difference that has no physical explanation in cloud-LLM round-trip times. **The only plausible cause is per-item caching: most of the 214 items were cache hits from the prior 8h-stalled rebuild (§2s), returned instantly, and the wall-clock-divided throughput reflects that without distinguishing.**

Notes that support this:

- The 12:10 SourcePrep timestamp matches the daemon-restart screenshot timing — the rebuild was resuming/re-running after the user restarted the daemon to clear the §2s 8h Edge Discovery hang. Many items would have been processed before the hang.
- `parse_errors: 0`, `success_rate: 1.0`, `avg_confidence: 0.771` — real confidence values, but they could be the cached prior results.
- The manifest schema has no `cache_hits` field. There's no way for a user or for downstream tooling to know whether 214 items were freshly LLM'd or pulled from cache.

### 2.3 The actual bug

The manifest's `processed` count and `throughput.items_per_second` conflate "fresh LLM work" and "cache lookups." When the elapsed time is short, **the user has no signal whether the stage actually did the LLM work or whether the manifest is reporting a cache replay.** This is a §2o-family issue (manifest reporting doesn't distinguish "ran" from "succeeded-trivially") on a different stage.

This matters in three places:

- **User trust.** "21 seconds" feels suspicious to the user even when it's fine (HomeColab case). "0.82 seconds" should feel suspicious — but the UI's `<1s` badge gives no warning.
- **Resume / restart correctness.** If the cached items include some that were partially processed before the §2s hang, are they actually current? If the stage cache key doesn't account for partial-completion staleness, a buggy resume could surface stale edges as "new."
- **Debugging future stalls.** When the next §2s recurrence happens and the user restarts, the post-restart Edge Discovery completion time tells us nothing about whether the new run actually re-processed everything or just hit cache.

## 3. Hypotheses for §2.2 (untested)

- **H-T1 — Per-item LLM caching exists and is mostly hitting on SourcePrep's restart.** Likely; an item-level cache keyed by content hash would naturally return instantly on a re-run with the same inputs.
- **H-T2 — The manifest's `throughput` calculation divides items by wall-clock with no awareness of cache.** Almost certainly true — `260 items/0.82s` is just division.
- **H-T3 — The stage worker doesn't distinguish "computed freshly" from "loaded from cache" in its emit path.** Worth checking — adding `cache_hits` / `fresh_compute` to the quality block would resolve the ambiguity at the manifest level.

## 4. Minor UX — progress bar style switches mid-rebuild

> "when I first started the rebuild it showed the blue progress bar like initial but then switched to the rebuild-style progress bars about 1/3 the way through edge discovery (about 7 seconds) about the same point that the top 'Rebuilding All stage 2/15' banner appeared."

Likely cause: the UI doesn't know it's a rebuild until it receives a specific event/payload from the daemon. Until that event arrives, the per-row progress bars render in the default-run style. When the orchestrator emits the rebuild-context signal (probably tied to writing the `.reset_barrier` or similar S6 marker), the dashboard re-renders with the rebuild style + banner.

**User-visible effect:** a ~7-second window where the user can't tell whether what they clicked actually triggered a rebuild or a normal incremental. Cosmetic; doesn't affect correctness.

**Suggested fix shape:** the dashboard's Rebuild button click should optimistically set rebuild-style locally *immediately* (before round-tripping to the daemon), then either confirm or roll back when the first daemon event arrives. Same pattern as toast feedback on Cancel.

## 5. What this finding does NOT claim

- HomeColab Edge Discovery is broken — it's not, it ran cleanly.
- SourcePrep's recent Edge Discovery is wrong — the edges may be correct; the reporting of *how the work happened* is what's ambiguous.
- The cache itself is wrong — caching is fine; the absence of a cache-hit signal in the manifest is the gap.

## 6. Diagnostic commands

```bash
# Compare any project's Edge Discovery throughput to a reference
for proj in $(ls /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/trace_inferred_manifest.json \
                  /Volumes/Thunderbolt/XcodeProjects/*/.sourceprep/trace_inferred_manifest.json \
                  /Volumes/Thunderbolt/AI/*/.sourceprep/trace_inferred_manifest.json 2>/dev/null); do
    python3 -c "
import json
m = json.load(open('$proj'))
print('${proj%/.sourceprep*}', m['quality']['processed'], 'items in', m['elapsed_seconds'], 's =',
      round(m['throughput']['items_per_second'], 1), 'items/s')
" 2>/dev/null
done

# A throughput much above ~20 items/sec for a cloud LLM stage almost certainly means cache hits.
```

Outliers in that output point at projects where the manifest is misleading about how the work was done.

## 7. Relationship to other open findings

- **§2o** (`FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`) — same family: manifest writer doesn't faithfully represent the work that actually happened. §2o is about partial-completion-lying-as-success. §2t is about cache-hit-lying-as-fresh-compute.
- **§2s** (`FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md`) — this finding is downstream of §2s. The user restarted the daemon to clear the §2s 8h hang; on restart, Edge Discovery re-ran but mostly hit cache. The 260/sec throughput on SourcePrep is a direct artifact of recovering from §2s.
- **Phase 145 §4a row-state contract** (REFERENCE doc) — should grow a row decoration distinguishing "ran fresh" from "ran cached" if the manifest grows the signal.

## 8. Cross-references

- HomeColab manifest: `/Volumes/Thunderbolt/XcodeProjects/HomeColab/.sourceprep/trace_inferred_manifest.json`.
- SourcePrep manifest: `/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/trace_inferred_manifest.json`.
- Code: `src/prep/core/inferred_edges.py` (the worker), `src/prep/services/pipeline/manifest_store.py` (manifest writer + quality block schema).
- Phase 145 README §2o, §2s, §2t.
- Proposal context: this finding is independent of T1–T4 but supports the "manifest writers should not lie about what work happened" pattern that connects §2o + §2t.
