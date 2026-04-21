# Knowledge Base Status Widget — Improvements

## Context
The `IndexStatusCard` component (`packages/ui/src/components/dashboard/IndexStatusCard.tsx`)
renders the "Knowledge Base Status" panel in the modular dashboard. Several layout and
data-display issues need addressing.

## Problems (from screenshot)
1. **"No project loaded" text area** — truncates too aggressively; long project paths
   or the fallback text get cut off.
2. **Badge baseline alignment** — the "Stale" / "Building" badges float above the text
   baseline instead of sitting centered with it.
3. **Missing lines-indexed coverage stat** — users want to see
   `lines_indexed / lines_total` (total indexable, excluding ignored files) as a clear
   ratio with a coverage percentage.
4. **Missing docs-vs-code line breakdown** — the existing file-count breakdown
   (`files_docs` / `files_code`) should be complemented by a **line-level** breakdown
   so the user can see what fraction of indexed content is documentation (.md, .rst, …)
   versus actual source code.

## Plan

### Part 1 — Layout Fix (frontend only)
- Change the top `<Flex>` row so the text area wraps instead of truncating.
- Align badges to `items-center` on the text baseline (use `self-center`).
- Allow `index_dir` / project name to break across lines gracefully.

### Part 2 — Backend: Add `lines_docs` / `lines_code` stats
- In `src/prep/core/index.py`, track `lines_docs` and `lines_code` alongside
  `files_docs` / `files_code` during the build loop.
- In `src/prep/core/manifest.py`, add `lines_docs` and `lines_code` to
  `ManifestBuildStats` and the serialised manifest dict.

### Part 3 — Frontend Types
- Add `lines_docs?: number` and `lines_code?: number` to `IndexBuildStats` in:
  - `packages/ui/src/types.ts`
  - `packages/ui/src/components/dashboard/IndexStatusCard.tsx` (local duplicate)

### Part 4 — UI Enhancements
- **Lines coverage row**: Show `{lines_indexed} / {lines_scanned} lines ({pct}%)` as a
  primary stat, making it clear this is "indexed vs total indexable."
- **Docs-vs-code bar**: Convert the existing file-count bar into a **line-level** bar
  using `lines_docs` / `lines_code`. Fall back to file counts if line data is absent.
- Keep existing chunk count and model name stats.

### Part 5 — Verify
- Spin up dev server and confirm visual rendering.
- Confirm backward compatibility (widget degrades gracefully when `lines_docs` /
  `lines_code` are absent from older build data).
