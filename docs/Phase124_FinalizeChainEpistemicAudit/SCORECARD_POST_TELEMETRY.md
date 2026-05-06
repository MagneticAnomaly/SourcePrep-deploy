# Finalize Chain Audit Scorecard

- Project: `CoDRAG`
- Generated: 2026-05-02T15:19:57.347494+00:00
- Overall: **8.9/10**

| Stage | Score | Anti-patterns |
|---|---:|---|
| 11_ATLAS Atlas | 9.5 | — |
| 12_RULES Rules | 10.0 | — |
| 13_CONCEPTS Concepts | 9.0 | — |
| 14_AUDIT Audit | 7.0 | — |
| 15_ANTIBODIES Antibodies | 9.0 | — |

## 11_ATLAS Atlas — 9.5/10
- ✓ atlas.json present
- ✓ 10 atlas segments
- ✓ segments carry file_paths (members enumerable)
- ✓ 9/10 segments have docs (90% coverage) — minor gap
- ✓ 51% of code modules have ≥1 doc mention
```json
{
  "atlas_age_hours": 0.4,
  "atlas_present": true,
  "bulk_dropped_dirs": [],
  "finished_at": "2026-05-02T14:57:52.125338+00:00",
  "modules_total": 410,
  "modules_with_relevant_docs_pct": 50.7,
  "routing_present": true,
  "segment_count": 10,
  "segment_doc_coverage_pct": 90.0,
  "segments_with_zero_doc_mentions": 1,
  "unsegmented_md_count": 11
}
```

## 12_RULES Rules — 10.0/10
- ✓ AGENTS.md present (163 lines)
- ✓ contains prep tool-calling instructions
- ✓ contains atlas snippet
- ✓ contains concepts mention
- ✓ contains project_id routing instruction
```json
{
  "agents_md_chars": 9914,
  "agents_md_lines": 163,
  "elapsed_seconds": 0.02,
  "finished_at": "2026-05-02T14:57:52.363971+00:00",
  "has_atlas": true,
  "has_concepts": true,
  "has_project_id": true,
  "has_tool_calling": true
}
```

## 13_CONCEPTS Concepts — 9.0/10
- ✓ 1590 concepts in store
- ✓ doc-rich regime: 1590 concepts, 51% .md-anchored
- ✓ 100% of concepts have anchors
- ✓ 11 categories covered
```json
{
  "anchor_pct": 100.0,
  "category_breakdown": {
    "architecture": 350,
    "brand": 19,
    "constraint": 167,
    "decision": 174,
    "domain": 123,
    "epistemic": 28,
    "pattern": 39,
    "process": 203,
    "product": 204,
    "security": 48,
    "technical": 235
  },
  "category_diversity": 11,
  "count": 1590,
  "elapsed_seconds": 948.63,
  "finished_at": "2026-05-02T15:13:41.193715+00:00",
  "md_anchor_pct": 50.9,
  "questions": 0,
  "status_breakdown": {
    "seed": 1590
  }
}
```

## 14_AUDIT Audit — 7.0/10
- ✓ all 5 audit markdown reports present
- ✓ spaghetti.json present
- ✓ spaghetti.json written inside audit-worker window (pipeline origin)
- ✗ average audit report is 21 KB — risk of token sprawl
```json
{
  "avg_md_report_kb": 21.4,
  "elapsed_seconds": 355.69,
  "finished_at": "2026-05-02T15:19:36.966681+00:00",
  "markdown_reports_expected": 5,
  "markdown_reports_present": 5,
  "spaghetti_in_audit_window": true,
  "spaghetti_offset_from_start_s": 5.2,
  "spaghetti_present": true
}
```

## 15_ANTIBODIES Antibodies — 9.0/10
- ✓ 517 antibodies derived
- ✓ 100% of eligible concepts produced antibodies
- ✓ 3 distinct severities
```json
{
  "antibody_to_eligible_ratio": 1.0,
  "count": 517,
  "elapsed_seconds": 0.35,
  "eligible_source_concepts": 517,
  "finished_at": "2026-05-02T15:19:37.347300+00:00",
  "severity_breakdown": {
    "inform": 340,
    "review": 10,
    "warn": 167
  }
}
```
