# Stash Inventory & Triage — 2026-07-18

> **Status:** catalog of all `git stash` entries with a recommended disposition.
> **Nothing here has been applied or dropped** (standing rule: never drop a stash
> without surfacing). Decisions are Eric's. `git stash show -p stash@{N}` shows a
> full diff without applying. Indices shift when a stash is dropped — re-run
> `git stash list` before acting.

## Summary

| # | Base / label | Contents (one line) | Disposition |
|---|---|---|---|
| `stash@{0}` | audit branch @ `6f71a69f` "add Teams Sync engineering handoff" | **Phase-145 UI + pipeline feature WIP** (see below) | **KEEP — follow up to land** |
| `stash@{1}` | main, `pre-merge 2026-05-31` | 5 backend files (trace/augmenter/enrichment/pipeline) | **REVIEW** — documented in `stash-2026-05-31.md` |
| `stash@{2}` | main @ `5be26d2b` | empty diff (`git stash show --stat` returns nothing) | Likely DROP (verify empty first) |
| `stash@{3}` | `feat/phase70-dashboard-hydration-controller` | runtime DB binaries (`codrag_data/*.db-wal/-shm`) + 1-line blog-copy edit | Likely DROP (DB binaries are runtime junk) |
| `stash@{4}` | main @ `3ab105f6` | codename-era `.cursor/rules/codrag.mdc`, DB binaries, `package-lock.json` (+2503), **deletes** `packages/paperclip-plugin/*` | Likely DROP (stale codename + superseded) |
| `stash@{5}` | `restore-today` | docs TODO edits + UI (`CopyButton`/`BuildCard`/`IndexStatusCard`) | Likely DROP (duplicate of `{6}`, old) |
| `stash@{6}` | `restore-today` | **identical file list to `{5}`** | Likely DROP (duplicate) |
| `stash@{7}` | main, `before codrag-mcp subtree publish` | old business/pricing/licensing docs (`PRICING_STRATEGY`, `BUSINESS_MODELS_AND_PRICING`, `LICENSING_IMPLEMENTATION`, `DECISIONS.md`) | Likely DROP (superseded by 2026-07 pricing/licensing decisions — glance first) |

## `stash@{0}` — the one worth recovering

Base: the concept-pipeline-audit branch. Substantial uncommitted feature work that
was stashed when switching to `main`, never landed:

- **UI / LLM model-settings:** `packages/ui/src/components/llm/ModelCard.tsx` (+105),
  `AIModelsSettings.tsx` (+23), `primitives/SearchableSelect.tsx` (+53),
  `viz/IndexHealthPanel.tsx` (+43).
- **A new 521-line behavioral test:** `packages/ui/.../GraphEnrichmentPipeline.behavioral.test.tsx`.
- **Backend:** `src/prep/api/routers/llm.py` (+163), `core/augmenter.py` (+88),
  `core/deepening.py`, `core/batch_profiles.py`.
- Plus doc/rule edits (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/prep.mdc`,
  Phase143/145 docs).

**Action:** decide whether to recover and land this (it's real feature work + a
sizable test), or supersede it. Recover with `git stash apply stash@{0}` on a
scratch branch, resolve any drift against current `main`, review, commit. Do NOT
`git stash pop` on `main` blindly — apply on a branch and diff first.

## The rest

`stash@{1}` is already documented in `stash-2026-05-31.md`. `stash@{2}`–`{7}` are
almost certainly stale (codename-era content, runtime DB binaries, duplicates, or
doc edits superseded by the 2026-07 pricing/licensing decisions) — but each should
get a 2-minute `git stash show -p` glance before dropping, to confirm nothing
unique is lost.
