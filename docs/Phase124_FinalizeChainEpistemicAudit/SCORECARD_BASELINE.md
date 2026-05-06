# Finalize Chain Audit Scorecard

- Project: `CoDRAG`
- Generated: 2026-05-01T21:10:20.967913+00:00
- Overall: **7.8/10**

| Stage | Score | Anti-patterns |
|---|---:|---|
| 11_ATLAS Atlas | 8.0 | AP-2, AP-3 |
| 12_RULES Rules | 10.0 | — |
| 13_CONCEPTS Concepts | 7.0 | AP-5 |
| 14_AUDIT Audit | 5.0 | AP-6 |
| 15_ANTIBODIES Antibodies | 9.0 | — |

## 11_ATLAS Atlas — 8.0/10
- ✓ atlas.json present
- ✓ 10 atlas segments
- ✓ segments carry file_paths (members enumerable)
- ✓ 51% of code modules have ≥1 doc mention
- ✗ AP-2: 9/10 segments have zero docs mentioning their own members
- ✗ AP-3: docs/Phase13_Storybook/ — 249 files unsegmented
```json
{
  "atlas_age_hours": 3.6,
  "atlas_present": true,
  "bulk_dropped_dirs": [
    [
      "Phase13_Storybook",
      249
    ]
  ],
  "finished_at": "2026-05-01T17:36:56.863579+00:00",
  "modules_total": 410,
  "modules_with_relevant_docs_pct": 50.7,
  "routing_present": true,
  "segment_count": 10,
  "segments_with_zero_internal_doc_mentions": 9,
  "unsegmented_md_count": 255
}
```

## 12_RULES Rules — 10.0/10
- ✓ AGENTS.md present (126 lines)
- ✓ contains prep tool-calling instructions
- ✓ contains atlas snippet
- ✓ contains concepts mention
- ✓ contains project_id routing instruction
```json
{
  "agents_md_chars": 7926,
  "agents_md_lines": 126,
  "elapsed_seconds": 0.0,
  "finished_at": "2026-05-01T17:36:56.905206+00:00",
  "has_atlas": true,
  "has_concepts": true,
  "has_project_id": true,
  "has_tool_calling": true
}
```

## 13_CONCEPTS Concepts — 7.0/10
- ✓ 13 concepts in store
- ✓ 100% of concepts have anchors
- ✓ 8 categories covered
- ✓ 7 unanswered concept questions surfaced
- ✗ AP-5: only 13 concepts on a 1848-file project (target 30-80)
```json
{
  "anchor_pct": 100.0,
  "category_breakdown": {
    "architecture": 4,
    "constraint": 1,
    "decision": 1,
    "domain": 1,
    "pattern": 1,
    "process": 2,
    "product": 1,
    "security": 2
  },
  "category_diversity": 8,
  "count": 13,
  "elapsed_seconds": 1098.19,
  "finished_at": "2026-05-01T17:55:15.129836+00:00",
  "questions": 7,
  "status_breakdown": {
    "active": 1,
    "seed": 12
  }
}
```

## 14_AUDIT Audit — 5.0/10
- ✓ all 5 audit markdown reports present
- ✓ spaghetti.json present
- ✗ AP-6: spaghetti.json mtime drifts 1190s from markdown reports — likely written by manual REST probe, not pipeline
- ✗ average audit report is 21 KB — risk of token sprawl
```json
{
  "avg_md_report_kb": 20.7,
  "elapsed_seconds": 253.55,
  "finished_at": "2026-05-01T17:59:28.751252+00:00",
  "markdown_reports_expected": 5,
  "markdown_reports_present": 5,
  "spaghetti_present": true,
  "spaghetti_vs_md_mtime_drift_s": 1190.1
}
```

## 15_ANTIBODIES Antibodies — 9.0/10
- ✓ 5 antibodies derived
- ✓ 100% of eligible concepts produced antibodies
- ✓ 2 distinct severities
- ✗ derivation reported 0.0s for 5 antibodies — likely served from cache; verify generation actually ran
```json
{
  "antibody_to_eligible_ratio": 1.0,
  "count": 5,
  "elapsed_seconds": 0.0,
  "eligible_source_concepts": 5,
  "finished_at": "2026-05-01T17:59:28.778803+00:00",
  "severity_breakdown": {
    "inform": 4,
    "warn": 1
  }
}
```
