# Finalize Chain Audit Scorecard

- Project: `CoDRAG`
- Generated: 2026-05-01T22:08:47.936231+00:00
- Overall: **8.6/10**

| Stage | Score | Anti-patterns |
|---|---:|---|
| 11_ATLAS Atlas | 8.0 | AP-2, AP-3 |
| 12_RULES Rules | 10.0 | — |
| 13_CONCEPTS Concepts | 9.0 | — |
| 14_AUDIT Audit | 7.0 | — |
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
  "atlas_age_hours": 0.5,
  "atlas_present": true,
  "bulk_dropped_dirs": [
    [
      "Phase13_Storybook",
      249
    ]
  ],
  "finished_at": "2026-05-01T21:39:07.231956+00:00",
  "modules_total": 410,
  "modules_with_relevant_docs_pct": 50.7,
  "routing_present": true,
  "segment_count": 10,
  "segments_with_zero_internal_doc_mentions": 9,
  "unsegmented_md_count": 256
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
  "agents_md_chars": 7974,
  "agents_md_lines": 126,
  "elapsed_seconds": 0.0,
  "finished_at": "2026-05-01T21:39:07.269900+00:00",
  "has_atlas": true,
  "has_concepts": true,
  "has_project_id": true,
  "has_tool_calling": true
}
```

## 13_CONCEPTS Concepts — 9.0/10
- ✓ 1779 concepts in store
- ✓ doc-rich regime: 1779 concepts, 30% .md-anchored
- ✓ 100% of concepts have anchors
- ✓ 11 categories covered
```json
{
  "anchor_pct": 100.0,
  "category_breakdown": {
    "architecture": 406,
    "brand": 26,
    "constraint": 188,
    "decision": 196,
    "domain": 142,
    "epistemic": 35,
    "pattern": 44,
    "process": 200,
    "product": 225,
    "security": 43,
    "technical": 274
  },
  "category_diversity": 11,
  "count": 1779,
  "elapsed_seconds": 1140.47,
  "finished_at": "2026-05-01T21:58:07.781208+00:00",
  "md_anchor_pct": 30.5,
  "questions": 0,
  "status_breakdown": {
    "seed": 1779
  }
}
```

## 14_AUDIT Audit — 7.0/10
- ✓ all 5 audit markdown reports present
- ✓ spaghetti.json present
- ✓ spaghetti.json written inside audit-worker window (pipeline origin)
- ✗ average audit report is 22 KB — risk of token sprawl
```json
{
  "avg_md_report_kb": 22.2,
  "elapsed_seconds": 431.35,
  "finished_at": "2026-05-01T22:05:19.229000+00:00",
  "markdown_reports_expected": 5,
  "markdown_reports_present": 5,
  "spaghetti_in_audit_window": true,
  "spaghetti_offset_from_start_s": 4.8,
  "spaghetti_present": true
}
```

## 15_ANTIBODIES Antibodies — 9.0/10
- ✓ 594 antibodies derived
- ✓ 100% of eligible concepts produced antibodies
- ✓ 3 distinct severities
- ✗ derivation reported 0.06s for 594 antibodies — likely served from cache; verify generation actually ran
```json
{
  "antibody_to_eligible_ratio": 1.0,
  "count": 594,
  "elapsed_seconds": 0.06,
  "eligible_source_concepts": 594,
  "finished_at": "2026-05-01T22:05:19.326233+00:00",
  "severity_breakdown": {
    "inform": 394,
    "review": 5,
    "warn": 195
  }
}
```
