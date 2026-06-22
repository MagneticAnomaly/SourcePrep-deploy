# Phase 145 UAT Scorecard — 2026-06-22

**Project:** `6955793f-d824-4e1c-8cb6-417a08bd6669`
**Iterations per op:** 3
**Operations:** Op-1, Op-2, Op-3, Op-4
**Session id:** 2026-06-22T180157Z
**Out root:** `tests/eval/ui_smoke`
**Iterations recorded:** 12/12 (complete)

**Status legend:** `pass` = all invariants held; `FAIL` = at least one invariant fired OR smoke exited non-zero; `ERR` = subprocess crash / missing summary; `skip` = daemon /health unreachable.

## Results

| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |
|---|---:|:--:|:--:|:--:|:--:|:--:|---|
| Op-1 Rebuild All clean | 1 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-1 Rebuild All clean | 2 | FAIL | ✓ | ✓ | ✗ | ✗ | cancel-quiesce: already idle (nothing to cancel) |
| Op-1 Rebuild All clean | 3 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-2 Incremental Update | 1 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-2 Incremental Update | 2 | FAIL | ✗ | ✓ | ✗ | ✗ | cancel-quiesce: already idle (nothing to cancel) |
| Op-2 Incremental Update | 3 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 1 | FAIL | ✗ | ✓ | ✗ | ✗ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 2 | FAIL | ✗ | ✓ | ✗ | ✗ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 3 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 1 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 2 | FAIL | ✗ | ✓ | ✗ | ✗ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 3 | FAIL | ✓ | ✓ | ✗ | ✓ | cancel-quiesce: already idle (nothing to cancel) |

## Rolled-up trends

- **Op-1 I3** failure rate **3/3 (100.0%)** — Rebuild All clean
- **Op-1 I13** failure rate **1/3 (33.3%)** — Rebuild All clean
- **Op-2 I1** failure rate **1/3 (33.3%)** — Incremental Update
- **Op-2 I3** failure rate **2/3 (66.7%)** — Incremental Update
- **Op-2 I13** failure rate **1/3 (33.3%)** — Incremental Update
- Op-2: 1/3 iter(s) failed without invariant evidence — see Notes column
- **Op-3 I1** failure rate **2/3 (66.7%)** — Mid-rebuild refresh
- **Op-3 I3** failure rate **3/3 (100.0%)** — Mid-rebuild refresh
- **Op-3 I13** failure rate **2/3 (66.7%)** — Mid-rebuild refresh
- **Op-4 I1** failure rate **1/3 (33.3%)** — Update during Rebuild
- **Op-4 I3** failure rate **3/3 (100.0%)** — Update during Rebuild
- **Op-4 I13** failure rate **1/3 (33.3%)** — Update during Rebuild

## Mapped to findings

| Failure | Maps to | Evidence file(s) |
|---|---|---|
| Op-1 iter 1 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/006_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/012_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/015_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/018_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/021_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/026_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/029_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T180214Z/rebuild/032_invariant_I3_FAIL.png` |
| Op-1 iter 2 I13 | §2u §6.2 | `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/027_invariant_I13_FAIL.png` |
| Op-1 iter 2 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/006_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/010_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/013_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/018_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/021_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/026_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/030_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T181643Z/rebuild/033_invariant_I3_FAIL.png` |
| Op-1 iter 3 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/006_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/010_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/015_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/018_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/021_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/025_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/028_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T182857Z/rebuild/032_invariant_I3_FAIL.png` |
| Op-2 iter 1 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T184346Z/incremental/008_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184346Z/incremental/012_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184346Z/incremental/015_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184346Z/incremental/025_invariant_I3_FAIL.png` |
| Op-2 iter 2 I1 | §2r (intra-group) | `tests/eval/ui_smoke/run_20260622T184710Z/incremental/004_invariant_I1_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184710Z/incremental/011_invariant_I1_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184710Z/incremental/016_invariant_I1_FAIL.png` |
| Op-2 iter 2 I13 | §2u §6.2 | `tests/eval/ui_smoke/run_20260622T184710Z/incremental/006_invariant_I13_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184710Z/incremental/013_invariant_I13_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184710Z/incremental/017_invariant_I13_FAIL.png` |
| Op-2 iter 2 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T184710Z/incremental/005_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T184710Z/incremental/012_invariant_I3_FAIL.png` |
| Op-3 iter 1 I1 | §2r (intra-group) | `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/016_invariant_I1_FAIL.png` |
| Op-3 iter 1 I13 | §2u §6.2 | `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/018_invariant_I13_FAIL.png` |
| Op-3 iter 1 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/007_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/011_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/012_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/017_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/021_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/024_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/026_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/029_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185024Z/rebuild/032_invariant_I3_FAIL.png` |
| Op-3 iter 2 I1 | §2r (intra-group) | `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/016_invariant_I1_FAIL.png` |
| Op-3 iter 2 I13 | §2u §6.2 | `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/018_invariant_I13_FAIL.png` |
| Op-3 iter 2 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/007_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/011_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/012_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/017_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/021_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/024_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/028_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/031_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T185852Z/rebuild/034_invariant_I3_FAIL.png` |
| Op-3 iter 3 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/005_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/009_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/010_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/013_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/016_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/020_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/026_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/029_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T190920Z/rebuild/032_invariant_I3_FAIL.png` |
| Op-4 iter 1 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T191946Z/rebuild/005_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T191946Z/rebuild/009_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T191946Z/rebuild/013_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T191946Z/rebuild/018_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T191946Z/rebuild/022_invariant_I3_FAIL.png` |
| Op-4 iter 2 I1 | §2r (intra-group) | `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/018_invariant_I1_FAIL.png` |
| Op-4 iter 2 I13 | §2u §6.2 | `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/020_invariant_I13_FAIL.png` |
| Op-4 iter 2 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/007_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/011_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/014_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/019_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192455Z/rebuild/026_invariant_I3_FAIL.png` |
| Op-4 iter 3 I3 | §2r (intra-group); cross-group leak NOT covered — see §9.1 | `tests/eval/ui_smoke/run_20260622T192825Z/rebuild/007_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192825Z/rebuild/011_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192825Z/rebuild/014_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192825Z/rebuild/017_invariant_I3_FAIL.png`; `tests/eval/ui_smoke/run_20260622T192825Z/rebuild/021_invariant_I3_FAIL.png` |
