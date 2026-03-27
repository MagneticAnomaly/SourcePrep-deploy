# Phase 55: Deep Codebase Audit & Cleanup

## Executive Summary

After 54 phases of rapid development, the CoDRAG repo has accumulated significant cruft. This audit uses CoDRAG's own `codrag_audit` tool against itself to produce actionable findings.

### Counts

| Metric | Value |
|--------|-------|
| Python source files (`src/codrag/`) | 158 |
| Total Python LOC | 59,154 |
| Test files (`tests/`) | 74 |
| Doc markdown files | 678 |
| Doc LOC | 125,151 |
| Phase directories | 56 (Phase00–Phase54) |
| Root-level throwaway scripts | **67** |
| **Audit findings (total)** | **977** |
| Critical | 11 |
| Warning | 133 |
| Info | 833 |

---

## MCP Audit Findings (codrag_audit)

### 🔴 Critical (11)

**Source Code God Files:**

| File | Lines | Role |
|------|-------|------|
| `services/pipeline/orchestrator.py` | 2,459 | Pipeline orchestration monolith |
| `mcp/server.py` | 2,251 | All MCP tool handlers in one file |
| `core/augmenter.py` | 2,096 | Augmentation + prompts + batching |

**Oversized Data/Config:**

| File | Lines | Note |
|------|-------|------|
| `package-lock.json` (root) | 17,177 | Expected for monorepo |
| `packages/ui/package-lock.json` | 15,353 | Consider `.gitignore` |
| `docs/Phase13_Storybook/...package-lock.json` | 2,919 | Stale demo project |
| `logs/overnight_2026-02-21.json` | 2,266 | Should be gitignored |

**Oversized Docs:**

| File | Lines |
|------|-------|
| `docs/MASTER_TODO.md` | 2,683 |
| `docs/Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | 2,336 |
| `docs/Phase50_MCP-interfacing/PLAN.md` | 2,171 |

### 🟡 Warning (top 20 of 133)

**Python source files >1000 lines:**
- `core/index.py` — 1,843 lines (search + index + scoring)
- `core/atlas/generator.py` — 1,729 lines (generation + prompts)
- `core/cluster.py` — 1,395 lines
- `api/routers/llm.py` — 1,347 lines
- `core/epistemic_enrichment.py` — 1,237 lines
- `api/routers/projects/search.py` — 1,075 lines
- `cli.py` — 1,276 lines

**TypeScript/React components >1000 lines:**
- `CompetitorMatrix.tsx` — 1,437 lines
- `GraphEnrichmentPipeline.tsx` — 1,339 lines
- `AIModelsSettings.tsx` — 1,263 lines
- `client.ts` (API) — 1,256 lines
- `EnterpriseAdminPanel.tsx` — 1,134 lines
- `useDashboardPanels.tsx` — 1,059 lines

**Other:**
- `engine/crates/codrag-graph/src/lib.rs` — 1,321 lines
- `scripts/eval_real_repos.py` — 1,165 lines
- Multiple log files in `logs/`

### 🟢 Root-Level Script Pollution (67 files)

| Pattern | Count |
|---------|-------|
| `patch_*.py` | 24 |
| `fix_*.py` | 16 |
| `update_*.py` | 4 |
| `format_*.py` | 2 |
| Other (`debug_`, `enhance_`, `modify_`, `refactor_`, `verify_`, `test_`, `backend_`, `mcp_debug`) | 17 |
| Non-Python (`*.js`, `*.sh`) | 4 |
| Stale data files (`*.log`, `*.db`, `*.txt`) | 4 |

---

## Prioritized TODO

### P0 — Do Now
- [x] Fix MCP project ambiguity when `cwd=/` (Antigravity, Gemini CLI)
- [x] Make `codrag_context` alias always available (remove DEV_MODE gate)
- [x] Add `CODRAG_PROJECT` env var for explicit pinning
- [x] Add most-recently-active project heuristic fallback
- [ ] Archive root-level scripts → `scripts/archive/`
- [ ] Delete stale data files (`overnight.log`, `v2-eval.log`, `test.db`, `tmp_grid.txt`)
- [ ] Gitignore `logs/*.json`, `scripts/archive/`

### P1 — God File Splits (Python backend)
- [ ] Split `orchestrator.py` (2459L) — extract stage definitions, retry/checkpoint, state transitions
- [ ] Split `mcp/server.py` (2251L) — extract handlers per tool domain (audit, search, observe, impact)
- [ ] Split `augmenter.py` (2096L) — extract prompt templates and batch logic
- [ ] Split `index.py` (1843L) — separate search from index management
- [ ] Split `atlas/generator.py` (1729L) — separate prompts from generation logic

### P2 — God File Splits (Frontend)
- [ ] Split `CompetitorMatrix.tsx` (1437L)
- [ ] Split `GraphEnrichmentPipeline.tsx` (1339L)
- [ ] Split `AIModelsSettings.tsx` (1263L)
- [ ] Split `client.ts` (1256L) — break API client by domain
- [ ] Split `useDashboardPanels.tsx` (1059L)

### P3 — Documentation Cleanup
- [ ] Prune `MASTER_TODO.md` (2683L / 107KB)
- [ ] Archive completed Phase directories
- [ ] Create Phase summary index

---

*Generated: 2026-03-25 using `codrag_audit` MCP tool*  
*Project ID: `1d6f0b35-45cb-427b-ae9d-aac3c6371a4b`*
