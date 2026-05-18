# Test repos

The curated set of repos that SourcePrep is run against during prompt iteration. The goal is **shape diversity** — not size diversity. A prompt that works on three Python libraries of different sizes is still overfit to Python.

## Slots

| Slot | Purpose | Picked? | Path / URL | Commit SHA | File count |
|---|---|---|---|---|---|
| **A — SourcePrep self-host** | Biggest signal; we know this codebase intimately. Catches regressions in the prompts we own. | ✅ | `/Volumes/4TB-BAD/HumanAI/CoDRAG/` | `01ba3252` (baseline) | ~2,000 |
| **B — Small Python lib (~50 files)** | Fast turnaround. Sanity check that prompts behave on a *normal* Python project. | ⏳ TBD | — | — | — |
| **C — TS-only React project** | Catches Python-centric assumptions baked into prompts. SourcePrep prompts often default to Python framings. | ⏳ TBD | — | — | — |
| **D — Monorepo (optional)** | Tests workspace-segment handling. Activate once segment-aware prompts (root/segment atlas) start iterating. | ⏳ deferred | — | — | — |
| **E — Doc-heavy repo (optional)** | Tests doc-classification prompts (`batch-doc`, `batch-narrative`, `batch-epi-doc`). The corpus bias toward MD (see memory: `project_search_docs_bias.md`) means this slot matters. | ⏳ deferred | — | — | — |

## Selection criteria

A good slot-B/C/D/E repo:
- Is publicly available (so iterations are reproducible).
- Has a stable commit we can pin (snapshots reference SHAs).
- Is small enough to index in under 5 minutes on a development machine.
- Does NOT use SourcePrep itself (avoid contamination).
- Has at least one named entry point and one configuration file (so atlas/identity prompts have something to chew on).

## Suggested first picks (TBD — confirm before using)

- **B:** something like `click` (Python CLI lib, ~50 files), `requests` core (large but well-known), or a small internal lib of yours.
- **C:** a small Vite + React starter, or a stripped-down Next.js app. The point is "no Python."
- **D:** Nx or Turborepo example monorepo, or `vercel/turbo` examples.
- **E:** a repo where the README + `docs/` outweigh the code — Vue's docs site, a writing tool, or a documentation site project.

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
