# Phase 33 — TODO & Next Steps

> **Last updated**: 2026-02-21
> **Status**: Decision complete — v1.5 ONNX confirmed as production embedding model.
> See [RESEARCH_CLARITY.md](RESEARCH_CLARITY.md) for how this relates to compression and context architecture (separate concerns).

---

## Decision

**`nomic-embed-text-v1.5` (ONNX) is the production embedding model.**

v1.5 wins or ties on 7/10 repos, has zero catastrophic failures, is 14× faster, and requires no external dependencies. v2-moe is preserved for future re-evaluation if Ollama fixes the 512-token embedding context limit.

Full rationale in [README.md §5](README.md#5-decision-v15-onnx-as-default).

---

## Completed

- [x] **P1 fix**: v2-moe context overflow (Ollama ignores `num_ctx` for embedding models)
- [x] Full-index eval: all 10 repos, v1.5 + v2-moe (+ v1 nomic-embed-text for comparison)
- [x] Supplementary evals: docs-only, strip-code, trace-only across all repos
- [x] Fix Ruby/PHP parser coverage, TraceBuilder gitignore, doc queries for all repos
- [x] Eval framework: `eval_real_repos.py` with 10+ repos, ground-truth queries, 4 modes
- [x] Diagnosed test2-halley 0% R@1 (duplicate content + compressed score range)
- [x] Compiled aggregate metrics (v1.5 mean R@1=50.4% vs v2-moe 48.7%)
- [x] **Decision**: v1.5 ONNX as sole production model
- [x] Document all results and decision in `README.md`

## Remaining Cleanup

- [x] Remove v2-moe from `KNOWN_OLLAMA_MODELS` active recommendations (keep code for testing)
- [ ] Verify all score thresholds are calibrated for v1.5's score range (~0.60–1.20)
- [ ] File Ollama issue re: `num_ctx` ignored for embedding models
- [ ] Run gin full-index with v2-moe (errored in overnight batch, nice-to-have for completeness)

---

## Research Questions (preserved for future)

1. **If Ollama fixes `num_ctx` for embedding models**, re-run v2-moe eval. The 512-token limit handicaps it.
2. **v2-moe's NL→structural advantage** may matter for `KnowledgeIndex` (LLM-generated summaries). Worth testing if we ever revisit dual-model.
3. **Score calibration**: if v2-moe returns, its 0.69 avg scores will need model-specific thresholds for `min_score`, adaptive-K, and `assign_lod()`.
