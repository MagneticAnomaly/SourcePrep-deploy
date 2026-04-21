# Refactor 2 — Progress Tracker

**Final status: 1,178 passed, 7 pre-existing failures, 0 regressions.**

## Pre-existing Work (found already done)
| Item | Status | Notes |
|------|--------|-------|
| GAP-1: LLMClient → llm_client.py | ✅ DONE | 461 lines, re-exports in augmenter.py |
| GAP-3: query preprocessing → core/query.py | ✅ DONE | projects.py imports from prep.core.query |
| GAP-9: _get_project_globs() utility | ✅ DONE | Already exists in projects.py |

## Phase 0: Quick Wins (Gaps)
| Item | Status | Notes |
|------|--------|-------|
| GAP-1 cleanup: migrate downstream imports | ✅ DONE | 8 files + 1 test migrated to .llm_client |
| GAP-2: deduplicate TraceBuilder external module handling | ✅ DONE | Already had _collect_analyzer_result |

## Phase 1: Core Subsystem Decoupling
| Item | Status | Notes |
|------|--------|-------|
| 1.1 trace.py → core/trace/ | ✅ DONE | 10 files: models, utils, analyzers/×4, builder, index, coverage |
| 1.2 atlas.py → core/atlas/ | ✅ DONE | 5 files: models, prompts, routing, generator, __init__ |

## Phase 2: API Layer Refinement
| Item | Status | Notes |
|------|--------|-------|
| 2.1 projects.py → routers/projects/ | ✅ DONE | 9 files: helpers, models, crud, watch, files, build, search, atlas_endpoints, __init__. 24 routes. |
| 2.2 trace router → routers/trace_routes/ | ✅ DONE | 4 files: shared, query, enrichment, __init__. 27 routes. |

## Backend Services
| Item | Status | Notes |
|------|--------|-------|
| pipeline_orchestrator → pipeline/ | ✅ DONE | 4 files: stages, workers, orchestrator, __init__. Thin compat wrapper at pipeline_orchestrator.py. |
| mcp_server → mcp/ | ✅ DONE | 4 files: errors, server, transport, __init__. Thin compat wrapper at mcp_server.py. |

## Phase 3: Frontend
| Item | Status | Notes |
|------|--------|-------|
| 3.1 types.ts → types/ | ✅ DONE | Barrel index.ts created. Full domain split deferred (cross-file type refs). |
| 3.2 MarketingHero → heroes/ | ✅ DONE | 825→35 lines. 10 variants extracted to heroes/ directory. |
| 3.3 FolderTree extraction | ⬜ DEFERRED | Low priority, complex selection/explosion logic tightly coupled to rendering. |

## Cleanup
| Item | Status | Notes |
|------|--------|-------|
| .bak files | ✅ DONE | All 6 removed after final verification |

## Verified Line Counts (Mar 1 2026)
| File | Plan | Actual |
|------|------|--------|
| trace.py | 2,460 | 2,402 |
| atlas.py | 2,315 | 2,318 |
| projects.py | 2,228 | 2,183 |
| augmenter.py | 1,978 | 1,563 (LLMClient extracted) |
| index.py | 1,926 | 1,926 |
| mcp_server.py | 1,784 | 2,046 |
| trace router | 1,606 | 1,599 |
| pipeline_orch | 1,482 | 1,514 |
| cluster.py | 1,359 | 1,359 |
| cli.py | 1,320 | 1,320 |
| types.ts | 997 | 1,112 |
| client.ts | 889 | 926 |
| useDashboardPanels | 883 | 902 |
| GraphEnrichmentPipeline | 851 | 856 |
| MarketingHero | 825 | 825 |
| FolderTree | 719 | 719 |
