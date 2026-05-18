# Test repos

The curated set of repos that SourcePrep is run against during prompt iteration. The goal is **shape diversity** — not size diversity. A prompt that works on three Python libraries of different sizes is still overfit to Python.

## Slots

| Slot | Purpose | Picked? | Path / URL | Commit SHA | File count |
|---|---|---|---|---|---|
| **A — SourcePrep self-host** | Biggest signal; we know this codebase intimately. Catches regressions in the prompts we own. | ✅ | `/Volumes/4TB-BAD/HumanAI/CoDRAG/` | `01ba3252` (baseline) | ~2,000 |
| **B — Small non-Python lib** | Fast turnaround. Catches Python-centric assumptions baked into prompts. (Originally framed as "small Python lib" — replaced with Swift since PowerMate already exists indexed and Swift gives stronger non-Python signal.) | ✅ | `tests/eval/real_repos/PowerMateReborn/` (Swift, single-segment, ~15 source files) | `git ls-remote` TBD | 25 |
| **C — TS-only React project** | Was "TS-only React" — slot B now covers the non-Python diversity goal. Slot C reframed as: a doc-heavy or multi-language repo to stress the doc-classification + atlas-segment prompts. | ⏳ TBD | — | — | — |
| **D — Monorepo (optional)** | Tests workspace-segment handling. Activate once segment-aware prompts (root/segment atlas) start iterating. | ⏳ deferred | — | — | — |
| **E — Doc-heavy repo (optional)** | Tests doc-classification prompts (`batch-doc`, `batch-narrative`, `batch-epi-doc`). The corpus bias toward MD (see memory: `project_search_docs_bias.md`) means this slot matters. | ⏳ deferred | — | — | — |

## Selection criteria

A good slot-B/C/D/E repo:
- Is publicly available (so iterations are reproducible).
- Has a stable commit we can pin (snapshots reference SHAs).
- Is small enough to index in under 5 minutes on a development machine.
- Does NOT use SourcePrep itself (avoid contamination).
- Has at least one named entry point and one configuration file (so atlas/identity prompts have something to chew on).

## Suggested picks for remaining slots (TBD — confirm before using)

- **C:** a small Python lib (~50 files) — e.g., `click`, `requests` core, or a small internal lib. This fills the "Python diversity outside SourcePrep" gap that slot B was originally going to fill.
- **D:** Nx or Turborepo example monorepo, or `vercel/turbo` examples. Activates atlas-root / atlas-segment captures.
- **E:** a repo where the README + `docs/` outweigh the code — Vue docs site, a writing tool, or a documentation-site project. Stresses doc-classification prompts.

## Anti-picks

Avoid:
- **SourcePrep forks / siblings.** They share the prompt corpus — no diversity signal.
- **Massive repos (>10K files).** Full rebuilds will eat hours; not a good iteration cadence.
- **Closed/private codebases for which you cannot share output snippets.** Snapshots are committed to this repo.

## Adding a repo to the rotation

1. Pick a commit SHA, write it into the slot row above.
2. Run a full daemon rebuild against it from scratch.
3. Capture outputs for every prompt site (see [`00_Methodology.md`](./00_Methodology.md) on capture mechanics).
4. Drop them in `snapshots/2026-05-17_baseline/outputs/<site>/<repo-label>.json`.
5. Commit.

## Promotion ladder

A test repo earns a slot by demonstrating it surfaces a prompt issue that the existing slots missed. Slots churn rarely — replacing a slot invalidates prior baselines and forces re-capture.
