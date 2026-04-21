# Phase 73.3 — Compression System Testing & Improvement Audit

> Date: 2026-04-05 | Audit of the two compression engines: LOD Extractor + LLMLingua-2

---

## Executive Summary

Prep advertises "dual-engine compression" (structural LOD for code, LLMLingua-2 for docs). LOD is **well-tested and actively used** in production. LLMLingua-2 is **built but never tested, never installed, and never runs**. The `auto` dual-channel mode that the UI and marketing reference has no backend implementation. This document catalogs what works, what doesn't, and what to test/fix.

---

## Current State

### LOD Extractor — Working

| Aspect | Status | Evidence |
|--------|--------|----------|
| Unit tests | 46 tests, all pass | `tests/test_lod_extractor.py` |
| Production use (search) | Active | `search.py:252-357` — score→LOD mapping applied to search results |
| Production use (ambient) | Active | `search.py:589-658` — LOD 2 for neighbor files in `prep` tool |
| Languages covered | Python, TS, Rust, Go, Java | Tests for Python + TS; regex patterns for 14 languages |
| Real-file validation | Missing | All tests use synthetic 30-line fixtures |
| Compression ratios validated | Partial | Tests check monotonicity and minimums but not documented 3-20x range |

### LLMLingua-2 Compressor — Not Operational

| Aspect | Status | Evidence |
|--------|--------|----------|
| Unit tests | **None** | No `tests/test_compressor.py` exists |
| `llmlingua` dependency | **Not installed** | Not in `pyproject.toml`, not in `.venv` |
| Model downloaded | **No** | HF model not cached; download button in UI requires `llmlingua` |
| Production use | **Never runs** | `_get_compressor()` returns `LinguaCompressor()` but `.compress()` falls back to noop |
| Feature gate | Exists | `context_compression` gated at Pro tier in `feature_gate.py:57` |
| API endpoint | Exists | `GET /compression/status`, `POST /compression/download` in `llm.py:286-358` |
| UI settings | Built | `AIModelsSettings.tsx` has enable toggle, download button, mode/level selectors |
| Marketing claims | Active | "3-20x structural compression", "language-aware compression for docs", "dual-engine" |

### "Auto" Dual-Channel Mode — Not Implemented

The UI (`AIModelsSettings.tsx:829`) offers an "Auto (dual-channel)" compression mode. The search options panel (`ContextOptionsPanel.tsx`) has `lod` and `lingua` as separate options. But there is **no backend routing logic** that:
1. Detects whether content is code vs. documentation
2. Routes code → LOD, docs → LLMLingua
3. Applies both engines in a pipeline

The `_get_compressor()` function in `search.py:360-364` is a simple if/else that either returns `LinguaCompressor()` or `NoopCompressor()`. There is no content-type detection or dual routing.

---

## Testing Gaps (Prioritized)

### P0: LinguaCompressor Unit Tests (Critical)

**What**: Create `tests/test_compressor.py` covering:
- `NoopCompressor` always returns input unchanged
- `LinguaCompressor.is_available()` returns False when `llmlingua` not installed
- `LinguaCompressor.compress()` graceful fallback when model unavailable
- `CompressResult` dataclass fields (ratio, timing, error)
- `LinguaCompressor.FORCE_TOKENS` preservation (mock test)
- `LinguaCompressor.LEVEL_RATES` map the three presets correctly

**Why**: The compressor is customer-facing (Pro feature), shipped in the settings UI, and has zero test coverage. If someone installs `llmlingua` and enables compression, we have no assurance it works.

**Effort**: Small — can test the abstraction layer without requiring `llmlingua` installed (mock or skip).

### P1: LOD Real-File Validation

**What**: Test LOD extraction on actual Prep source files, not just synthetic fixtures:
- Pick 5 real files of varying size: `orchestrator.py` (large), `compressor.py` (medium), `ids.py` (small), `types.ts` (TS hub), `server.py` (MCP)
- Measure actual compression ratios at each LOD level
- Validate the documented "3-20x" range from marketing
- Check that LOD 2 retains all public function/class names
- Check that LOD 4 retains all import paths
- Test files with unusual structures: decorator-heavy, async generators, nested classes

**Why**: The 46 existing tests only use 30-line synthetic fixtures. Real files have complex nesting, decorators, multi-line type hints, and conditional imports that may break LOD assumptions.

**Effort**: Medium — needs the trace index to be built, or can use raw file parsing.

### P2: End-to-End Search Compression

**What**: Integration test that exercises the full path:
1. `prep_search(query="...", compression="lod")` via MCP
2. Verify returned context has LOD metadata (lod level, compression_ratio per chunk)
3. Verify higher-scored chunks get LOD 0, lower-scored get LOD 4-5
4. Verify total output fits within `max_chars` budget
5. Test `compression="lingua"` returns graceful error/fallback when not installed

**Why**: The LOD-in-search wiring (`search.py:252-357`) is complex — it loads trace nodes, deduplicates by file, applies per-chunk LOD, and budget-truncates. This path has no integration test.

**Effort**: Medium — needs a test project with an index.

### P3: Install and Validate LLMLingua-2

**What**: 
1. Add `llmlingua` to `pyproject.toml` extras (e.g., `[compression]`)
2. Install and download the HF model
3. Run `scripts/test_code_in_docs_compression.py` on real repos
4. Validate the marketing claims: "~1.6x ratio, 89% concept retention"
5. Benchmark latency on CPU (the only mode we support)
6. Test the `FORCE_TOKENS` list — does it actually preserve structural markers?

**Why**: We're selling this as a feature to Pro users. It should work.

**Effort**: Medium-Large — model download (~178MB), GPU-less latency concerns, may need tuning.

### P4: Implement Dual-Channel Auto Mode

**What**: Build the content routing logic:
1. Detect content type: file extension → code or doc
2. Code files → LOD compression (already working)
3. Markdown/text files → LLMLingua-2 token pruning
4. Mixed files (markdown with code fences) → splice strategy (strip fences, compress prose, recombine)
5. Wire into `_apply_compression()` when `compression="auto"`

**Why**: The UI already offers "Auto (dual-channel)" but it does nothing. This is the advertised core differentiator.

**Effort**: Large — needs P3 done first, plus the splice strategy from `scripts/test_code_in_docs_compression.py` promoted to production code.

---

## Marketing vs Reality Gap

| Marketing Claim | Reality | Fix |
|----------------|---------|-----|
| "3-20x structural compression for code" | LOD achieves this but untested on real files | P1: real-file validation |
| "Language-aware compression for docs (~1.6x, 89% retention)" | LLMLingua-2 never runs | P3: install + validate |
| "Dual-engine compression" | Only LOD runs; no auto-routing | P4: implement dual-channel |
| "Smart compression built in — zero extra dependencies" | `llmlingua` is an extra dependency that isn't installed | Update marketing or make it truly zero-dep |
| Download button in settings | Fails silently without `llmlingua` package | P3: add to extras |

---

## Compression Ratio Targets (Proposed)

Based on the LOD level documentation and expected real-world behavior:

| LOD Level | Description | Target Ratio | Test Fixture | Real File Target |
|-----------|-------------|-------------|-------------|-----------------|
| 0 | Full source | 1.0x | ✅ verified | N/A |
| 1 | Strip comments | ~1.1-1.3x | ✅ verified (reduces) | Validate on heavily-commented files |
| 2 | Signatures + docstrings | ~2-4x | ✅ ≥1.2x on small fixture | Target ≥2.5x on 200+ line files |
| 3 | Class skeletons only | ~4-6x | ✅ ≤ LOD 2 | Target ≥3.5x |
| 4 | Imports + names | ~5-10x | ✅ ≥2.0x | Target ≥5x on 200+ line files |
| 5 | Summary only | ~10-25x | ✅ smallest | Target ≥8x |

For LLMLingua-2:

| Level | Keep Rate | Target Ratio | Concept Retention | Latency (CPU) |
|-------|-----------|-------------|-------------------|---------------|
| Light | 60% | ~1.6x | ≥90% | <500ms/chunk |
| Standard | 40% | ~2.5x | ≥80% | <800ms/chunk |
| Aggressive | 25% | ~4x | ≥65% | <1000ms/chunk |

---

## Recommended Test Script: `scripts/test_compression_real.py`

A script to validate both engines against real Prep files:

```python
#!/usr/bin/env python3
"""Validate compression engines against real Prep source files.

Runs LOD extraction on actual project files and reports:
- Compression ratio per LOD level per file
- Signature/name retention rates
- Whether marketing claims (3-20x) hold on real code

Optionally runs LLMLingua-2 on documentation files if installed.
"""

# Targets:
# 1. Load trace_nodes.jsonl from the live Prep index
# 2. Pick 10 representative files (mix of sizes, languages)
# 3. Extract at all LOD levels, measure ratios
# 4. Validate name/signature retention
# 5. If llmlingua installed: compress markdown docs, measure retention
# 6. Print summary table with pass/fail against targets
```

---

## Relationship to Other Phase 73 Findings

- **Doc 08 (Context Volume Tiering)**: LOD compression is the mechanism that makes tiered budgets work — LOD 1 vs LOD 2 for neighbors directly controls how much content fits in the budget. If LOD ratios aren't what we expect, the tier math is wrong.
- **Doc 09 (Budget Empirical Analysis)**: Found that hub content was starved (7% of output). LOD compression on neighbors could recover budget for more hub files — but only if LOD 2-4 actually achieve the expected 3-10x ratios on real files.
- **Doc 07 (Prompt Architecture)**: The pipeline prompts could benefit from LLMLingua-2 compression if/when it works — batch prompts carry significant boilerplate that could be pruned.

---

## Next Steps

1. **Immediate**: Write `tests/test_compressor.py` (P0) — takes <30 min, high value
2. **This week**: Run LOD on 10 real files and publish ratio table (P1)
3. **Next sprint**: Decide whether to invest in LLMLingua-2 (P3) or update marketing to reflect LOD-only reality
4. **Future**: Dual-channel auto mode (P4) only after P3 validates the value proposition
