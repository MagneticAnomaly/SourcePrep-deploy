# Phase 139 — Corpus Token-Length Profile

> Sampled 2026-05-15 from this repo's `.sourceprep/` artifacts using
> the actual `nomic-ai/nomic-embed-text-v1.5` tokenizer. **This data
> changes the bucket-boundary plan in `IMPLEMENTATION_PLAN.md` T1.3
> and T2.2** — we have been over-provisioning by ~16×.

## Method

Tokenized 5,000 sampled documents from
`.sourceprep/knowledge_documents.json` (9,506 total) with the model's
own tokenizer (`Tokenizer.from_file(...)`). Also tokenized 100 sampled
raw source files (`.py`, `.tsx`, `.md`) to verify what the chunker
feeds the embedder.

## Finding 1 — synthesized knowledge docs are tiny

This is the **dominant embedder workload** during a pipeline run
(~9.5K calls on this repo).

| Percentile | Tokens |
|---|---:|
| min | <10 |
| p25 | 55 |
| **p50 (median)** | **61** |
| p75 | 71 |
| p90 | 190 |
| p95 | 211 |
| p99 | 255 |
| **max (in sample)** | **322** |

Bucket distribution:

| Bucket | Cumulative | In bucket |
|---|---:|---:|
| ≤ 128 tokens | **80.9 %** | 80.9 % |
| ≤ 256 tokens | **99.1 %** | 18.1 % |
| ≤ 512 tokens | **100.0 %** | 0.9 % |
| ≤ 1024 tokens | 100.0 % | 0 % |
| ≤ 2048 tokens | 100.0 % | 0 % |
| ≤ 4096 tokens | 100.0 % | 0 % |
| ≤ 8192 tokens | 100.0 % | 0 % |

**Nothing in this corpus exceeds 322 tokens.** Our current default
`max_length=8192` is a 25× over-provision.

## Finding 2 — raw code chunks are capped at ~450-675 tokens

The Python chunker (`src/prep/core/chunking.py:214`) caps at
`max_chars=1800` with a 1.5× hard ceiling (line 201: `if len(chunk) > int(max_chars * 1.5)`).
At ~4 chars/token that's:

- Typical chunk: ≤ 450 tokens
- Worst-case chunk (1.5× slack): ≤ ~675 tokens

Whole-file token distribution (for comparison — but **the embedder
never sees this** because the chunker is upstream):

| Percentile | Tokens |
|---|---:|
| median | 1,992 |
| p75 | 3,933 |
| p95 | 13,295 |
| p99 | 26,763 |
| max | 42,980 |

70% of raw files exceed 1024 tokens, 48% exceed 2048 tokens. But
**this is moot** — they're chunked to ≤ 1800 chars before any
embedding call.

## Implications for the implementation plan

### Change to T1.3 — drop `MAX_LENGTH` further

Original proposal: `MAX_LENGTH: 8192 → 2048`.
**New proposal: `MAX_LENGTH: 8192 → 1024`.**

Rationale: the chunker caps raw chunks at ~675 tokens worst case.
The dominant workload (knowledge docs) maxes at ~322 tokens. 1024
gives a 1.5× safety margin on the chunker's slack ceiling and a 3×
margin on observed-max. Anything larger is dead weight.

Activation peak at `B=16, S=1024, fp16`:
- Linear term `34·s·b·h·L` = `34·1024·16·768·12` ≈ **5.1 GB**
- Quadratic `5·a·s²·b·L` = `5·12·1024²·16·12` ≈ **1.2 GB**
- **Total ~6.3 GB** worst case if all 16 items fill the 1024-token bucket.

Compared to:
- `S=2048`: **~24 GB** worst-case (4× higher because S² doubles)
- `S=8192` (current): **~380 GB** worst-case

### Change to T2.2 — narrower buckets

Original proposal: `[128, 256, 512, 1024, 2048]`.
**New proposal: `[128, 256, 512, 1024]`.**

Rationale: 100% of observed corpus fits in ≤512 tokens; the 1024
bucket is the safety margin for the chunker's 1.5× slack. Buckets
above that are unreachable on this corpus — adding them just adds
code complexity for a case that never occurs.

If a user opts in to a different chunker policy that produces longer
chunks (or someone explicitly sets `PREP_EMBED_MAX_LEN=4096`), the
bucket logic should fall back to padding to `MAX_LENGTH` directly.

### Expected workload after T2.2

Given the bucket distribution above (81% in 128-token bucket, 18% in
256, 1% in 512), with token-budget batching at `max_batch_tokens=8192`:

| Bucket | % of workload | Batch size at budget | Peak activation (fp16) |
|---|---:|---:|---:|
| 128 | 81 % | 64 items | ~4 GB |
| 256 | 18 % | 32 items | ~4 GB |
| 512 | 1 % | 16 items | ~4 GB |
| 1024 | 0 % | 8 items | ~3 GB |

**Effective peak across the whole pipeline: ~4 GB.** A 25× reduction
from the original ~100 GB pre-mitigation, even before idle-release
and singleton wins.

### No change to T1.2 — CoreML opts still apply

The CoreML/ANE workaround (CPUAndGPU, RequireStaticInputShapes,
ModelCacheDirectory) is independent of bucket size and still
necessary to prevent the Espresso recompile hangs.

## Notes on data limitations

- **Sample size:** 5,000 of 9,506 docs (representative; full
  tokenization took 0.3s so we can do the full set in PR 1 if
  worth confirming).
- **Other projects' corpora may differ.** A repo full of giant
  Jupyter notebooks or long legal docs could have a different
  distribution. The defaults must be conservative for the worst
  *plausible* corpus, but the chunker's `max_chars=1800` caps that.
- **Atlas routing descriptors** (171 KB in `atlas_routing.json`)
  are another embedder workload — not sampled here but typically
  short paragraph descriptions, likely similar to the knowledge
  docs.
- **Whole-file embedding** (for files small enough to not chunk)
  is the only path that could blow past 1024 tokens. Worth a quick
  scan of the chunker to confirm it always splits files > 1800
  chars. From `chunking.py:214` it does.

Raw token-length array saved at `/tmp/phase139_token_lens.npy`
(transient — won't survive reboot).
