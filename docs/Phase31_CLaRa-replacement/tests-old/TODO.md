# Phase 31: CLaRa Testing — Execution Checklist

## Prerequisites

- [ ] CLaRa server running (`clara-server` at localhost:8765)
- [ ] CoDRAG daemon running (`codrag serve` at localhost:8400)
- [ ] At least one project indexed in CoDRAG
- [ ] 16GB+ unified memory (Mac) or 14GB+ VRAM (NVIDIA)

## Phase A: Smoke Test ✅ (2026-02-20)

- [x] CLaRa responds to /health
- [x] CLaRa reports correct backend (mps)
- [x] Direct test produces output (but **hallucinated** what CoDRAG means)
- **Finding**: 20–42s latency on MPS. CLaRa fabricates acronym expansions.

## Phase B: Code Retention Tests ❌ (2026-02-20)

- [x] ~~Function name retention ≥80%~~ → **70% avg** (FAIL)
- [x] ~~Class name retention ≥80%~~ → **44% avg** (FAIL)
- [x] ~~File path retention ≥80%~~ → **0%** (FAIL — never preserves paths)
- [x] ~~Key fact retention ≥60%~~ → **19% avg** (FAIL)
- [x] Hallucination count <5 avg per test → **4.0 avg** (PASS, barely)
- [x] Identify best max_new_tokens → 512 tested, moot given retention failures
- **Finding**: 29% overall retention. CLaRa generates QA prose, not code.

## Phase C: Latency Profile ❌ (2026-02-20)

- [x] Cold start <30s (MPS) → **14.7s** (PASS)
- [x] ~~Warm latency <2s per request (MPS)~~ → **11–65s** (FAIL)
- [x] Latency scales linearly → **Yes, ~2.2s per chunk** (linear confirmed)
- [x] Identify practical volume ceiling → **1 chunk = 11s already over budget**
- **Finding**: MPS latency is 5–22× over the 3s target. Unusable for interactive.

## Phase D: End-to-End Benchmark ❌ (2026-02-20, quick mode)

- [x] Baseline (K=5) produces results → **6,031 chars, 1.2s**
- [x] CLaRa K=30 produces compressed results → **618 chars, 26.2s**
- [x] ~~CLaRa mode references ≥2× more files~~ → 0 files either way (path extraction TBD)
- [x] ~~Output stays within 6000 char target~~ → 618 chars (too small, not too big)
- **Finding**: Baseline delivers 10× more content at 21× lower latency.

## Phase E: Quality Analysis — SKIPPED

Skipped — Phase B/D results are conclusive. CLaRa is not suitable for code.

## Phase F: Write Findings ✅ (2026-02-20)

- [x] Created `docs/Phase31_CLaRa-tests/FINDINGS.md`
- **Verdict**: CLaRa fails 3 of 4 decision gates. Not ready for code context.

---

## Decision Gates

| Gate | Criteria | Action if FAIL |
|------|----------|----------------|
| **G1: Code Accuracy** | Function/class names survive at ≥80% | Investigate prompt engineering for CLaRa |
| **G2: No Hallucination** | <5 fabricated names per test | Add post-compression validation layer |
| **G3: Latency Budget** | <3s total on MPS | Reduce default K or use compression-128 |
| **G4: Quality Win** | CLaRa ≥ baseline on 60% of queries | Reconsider compression strategy |

---

*Last updated: 2026-02-20*
