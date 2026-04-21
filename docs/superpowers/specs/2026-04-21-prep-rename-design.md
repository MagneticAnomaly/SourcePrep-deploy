# Design: Rename CoDRAG → Prep

**Date:** 2026-04-21
**Status:** Design — awaiting user review; implementation plan to follow
**Supersedes:** `docs/Phase102_Prep_rename/Phase102_Prep_rename.md` (draft)

---

## Summary

Rename the entire CoDRAG project to **Prep**. The product is unchanged; the name, identifiers, content, and websites all change. This is an alpha-stage project with no external users, so we do a hard cutover with no backward-compatibility shims. Git history is preserved on all four repos via GitHub's native transfer + rename.

**Guiding rule: no visual redesign.** This is a pure text / identifier rename. Image files are renamed (filename changes) but their visual contents are not redrawn — the existing logos, OG cards, icons, and favicons keep their current pixels. A visual refresh is a separate work item if/when desired.

**End state:**

| Surface | Value |
|---|---|
| App name | Prep |
| Tagline meaning | "prep the context before any AI call" |
| Primary domain | `runprep.io` |
| Subdomains | `docs.runprep.io`, `support.runprep.io`, etc. |
| CLI binary | `prep` |
| Python package | `prep` (import `prep`) |
| Rust crates | `prep-*` |
| npm scope | `@prep/*` |
| MCP tools | `prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`, `prep_concepts` |
| MCP server key | `"prep"` |
| Data directory | `~/.local/share/prep/` |
| Env var | `PREP_DATA_DIR` |
| Embedded per-project dir | `.prep/` |
| Tauri bundle ID | `io.runprep.app` |

**GitHub repos (post-rename):**

| Current | → | New |
|---|---|---|
| `EricBintner/CoDRAG` | → | `MagneticAnomaly/Prep` (transfer + rename) |
| `MagneticAnomaly/CoDRAG-MCP` | → | `MagneticAnomaly/Prep-MCP` (rename) |
| `MagneticAnomaly/CoDRAG-MCP-DEV` | → | `MagneticAnomaly/Prep-MCP-DEV` (rename) |
| `MagNeticAnomaly/codrag-deploy` | → | `MagneticAnomaly/Prep-deploy` (rename + case fix) |
| `EricBintner/CLaRa-Remembers-It-All` | → | untouched on GitHub; `clara-dev` remote removed locally |

---

## Strategy

**Approach:** Big-bang hard cutover on a `rename/prep` branch. All renaming happens on the branch; `main` stays buildable. Branch merges to `main` in one commit, *then* GitHub ops fire (transfer + rename the four repos, rewire local remotes).

**Alternatives considered and rejected:**
- *Flip GitHub first, then rewrite in place* — repo called "Prep" while code still says "CoDRAG" is confusing; pollutes main's history with 20+ rename commits.
- *Incremental PR sequence* — intermediate states are half-renamed and broken; no review value when there's only one reviewer.

**Verification gate:** a zero-occurrence grep for `codrag|CoDRAG|CODRAG` (minus a curated allowlist of legitimate historical references) must return empty. Build + tests + daemon smoke all green before merge.

---

## Inventory (what actually gets renamed)

Exhaustive scan of the repo surfaces the following:

| Category | Approximate count |
|---|---|
| Files referencing `codrag` in any case | 400+ Python, 200+ TypeScript, 300+ docs/content |
| `codrag.io` URL references | 115 files |
| `CODRAG_DATA_DIR` / `.prep/` / `~/.local/share/prep` | 176 files |
| `@codrag/*` npm imports | 292 occurrences / 157 files |
| `codrag.ai` references | 5 files — **delete**, domain never existed |
| CLaRa references | ~115 files (most in historical phase docs) |

### Directories to rename (via `git mv`)

```
src/codrag/                             → src/prep/
src/codrag_data/                        → src/prep_data/       (untracked local scratch)
engine/crates/codrag-chunking/          → engine/crates/prep-chunking/
engine/crates/codrag-engine/            → engine/crates/prep-engine/
engine/crates/codrag-graph/             → engine/crates/prep-graph/
engine/crates/codrag-parser/            → engine/crates/prep-parser/
engine/crates/codrag-sanitize/          → engine/crates/prep-sanitize/
engine/crates/codrag-selfheal/          → engine/crates/prep-selfheal/
engine/crates/codrag-walker/            → engine/crates/prep-walker/
packages/paperclip-plugin-codrag/       → packages/paperclip-plugin-prep/
public/codrag-mcp/                      → public/prep-mcp/     (contains nested .git)
public/codrag-deploy/                   → public/prep-deploy/  (contains nested .git)
```

### Files to rename

```
codrag-mcp-wrapper.sh                          → prep-mcp-wrapper.sh
codrag-daemon.spec                             → prep-daemon.spec
scripts/publish_codrag_mcp_subtree.sh          → scripts/publish_prep_mcp_subtree.sh
public/images/CoDRAG.png                       → public/images/Prep.png
public/codrag-mcp/codrag-logo.png              → public/prep-mcp/prep-logo.png
public/codrag-mcp/codrag-github-header.png     → public/prep-mcp/prep-github-header.png
public/codrag-deploy/codrag-github-header.png  → public/prep-deploy/prep-github-header.png
packages/vscode/media/codrag-icon.png          → packages/vscode/media/prep-icon.png
packages/vscode/media/codrag-sidebar.svg       → packages/vscode/media/prep-sidebar.svg
src/codrag/agents/shared/codrag_data.py        → src/prep/agents/shared/prep_data.py
src/codrag_data/codrag_settings.db             → src/prep_data/prep_settings.db
```

### Top-10 silent-breakage list

Renames where a miss produces no compile error but wrong runtime behavior. The verification plan specifically hunts for these.

1. **`io.codrag.app`** (Tauri bundle ID in `tauri.conf.json`) — macOS Gatekeeper rejects updates.
2. **MCP server key `"codrag"`** in `.claude/mcp.json`, `.cursor/mcp.json`, `mcp-server.json` — clients silently can't find the server.
3. **SQLite filenames** `codrag_settings.db`, `codrag_antibodies.db`, `codrag_token_telemetry.db` — fresh install orphans user data.
4. **Tauri updater endpoint** URL → must point at `MagneticAnomaly/Prep` releases.
5. **CLI entry point** in `pyproject.toml` — if `prep = "prep.cli:main"` is miswired, `pip install -e .` installs nothing executable.
6. **Tauri `externalBin: ["codrag-daemon"]`** — desktop app launches but has no backend.
7. **Paperclip manifest tool IDs** — use `:` (`codrag:context`) not `_`; different convention from MCP-native tools.
8. **VS Code config schema keys** (`codrag.daemonPort`) — if renamed but reads still look up `codrag.*`, users get defaults.
9. **Data path literal** `~/.local/share/prep/` in `paths.py` — wrong path = empty data dir, app looks "freshly installed".
10. **Rules generator templates** — the AGENTS.md/CLAUDE.md that Prep writes into *client projects* still say "codrag" unless `rules_generator.py` strings are updated.

---

## Phase sequencing

The rename is done in ordered phases on a single `rename/prep` branch. Each phase ends with a commit and a verification check. Ordered so the codebase stays buildable at most phase boundaries.

| # | Phase | Buildable after? |
|---|---|---|
| 0 | Branch + freeze | ✅ |
| 2 | Python: dir + manifest (`src/codrag` → `src/prep`, pyproject, imports) | ❌ atomically within one commit |
| 3 | Python: internal strings (data paths, env vars, SQLite filenames, MCP server name, tool registrations) | ✅ |
| 4 | Rust workspace (`engine/crates/codrag-*` → `prep-*`, all `use` statements) | ✅ |
| 5 | Python ↔ Rust bindings (`maturin develop`, `import codrag_engine` → `import prep_engine`) | ✅ full backend |
| 6 | npm workspace + package.json names (`@codrag/*` → `@prep/*`) | ❌ temporarily |
| 7 | npm imports + workspace linking | ✅ `npm run typecheck` green |
| 8 | VS Code extension (package, commands, config keys, icons) | ✅ |
| 9 | PyInstaller sidecar spec + wrapper scripts (`codrag-daemon.spec` → `prep-daemon.spec`, sidecar build script) — must precede Tauri phase so `externalBin` has a binary to reference | ✅ |
| 10 | Tauri desktop (bundle ID, externalBin, updater endpoints) — depends on Phase 9 sidecar rename | ✅ |
| 11 | Public subtrees (`public/codrag-mcp/`, `public/codrag-deploy/`) | ✅ |
| 12 | MCP configs (server key `"codrag"` → `"prep"`) | ✅ |
| 13 | Rules generator + generated templates (`AGENTS.md`, `.cursor/rules/codrag.mdc`) | ✅ |
| 14 | Websites (4 Next.js apps; domains, copy, routes, sitemap, robots) | ✅ |
| 15 | Assets (logos, icons, favicons) | ✅ |
| 16 | Root docs (README, CLAUDE.md, SUPPORT.md, LICENSE, CHANGELOG entry) | ✅ |
| 17 | CLaRa scrub (live code, remote removal, historical allowlist) | ✅ |
| 18 | Delete `websites/MagneticAnomaly/` (defunct) | ✅ |
| 19 | Lock files regen + full test suite | ✅ |
| 20 | Zero-occurrence grep gate | ✅ hard gate |
| 21 | Merge to `main` | ✅ |
| 22 | GitHub ops (transfer + rename 4 repos, rewire local remotes, remove `clara-dev`) | ✅ |

### Per-phase commit policy

Each phase = one commit with prefix `rename(phase-N):`. Makes the merge commit's history skimmable; enables bisect if regression surfaces.

---

## Per-surface design

### Section 5 — Python package & CLI

**Directory rename:** `git mv src/codrag src/prep` (and `src/codrag_data` if it's tracked).

**`pyproject.toml`:**
```toml
[project]
name = "prep"                                      # was "codrag"
description = "Prep — prepare context before any AI call"

[project.scripts]
prep = "prep.cli:main"                             # was: codrag = "codrag.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["prep*"]                                # was: ["codrag*"]

[tool.ruff.lint.isort]
known-first-party = ["prep"]

[tool.mypy]
packages = ["prep"]
```

**Import rewrites** (automated):
- `from codrag.` → `from prep.`
- `import codrag` → `import prep`
- Relative imports unchanged.

**User-visible strings** in `cli.py`, `server.py`:
- `typer.Typer(help="CoDRAG ...")` → `help="Prep ..."`
- FastAPI `title="CoDRAG Daemon"` → `title="Prep Daemon"`
- `User-Agent: codrag/{version}` → `prep/{version}`

**Verification:** `pytest tests/ -x`, `.venv/bin/prep serve`, `.venv/bin/prep --help` contains no "codrag".

### Section 6 — Rust workspace

**Directory renames** (per-crate `git mv`).

**`engine/Cargo.toml`** workspace members → `prep-*`. Each crate's `Cargo.toml`: `name`, `[lib].name`, path deps → `prep-*`. All `.rs` files: `use codrag_foo` → `use prep_foo`.

**`engine/pyproject.toml`** (PyO3 bindings): module name `codrag_engine` → `prep_engine`. Python import at boundary crosses into Phase 5.

**Verification:** `cargo check --workspace`, `cargo test --workspace`, `maturin develop`.

**Open:** confirm no crates are published to `crates.io` today (no evidence found); if so, this is purely internal.

### Section 7 — npm workspaces + VS Code extension

**Package renames** (every `package.json`):

| Path | Old `name` | New `name` |
|---|---|---|
| `packages/ui/` | `@codrag/ui` | `@prep/ui` |
| `packages/vscode/` | `codrag-vscode` | `prep-vscode` |
| `packages/vscode/webview-ui/` | (verify in package.json) | `@prep/vscode-webview` (or mirror current pattern) |
| `packages/paperclip-plugin-codrag/` → `packages/paperclip-plugin-prep/` | `@codrag/paperclip-plugin` | `@prep/paperclip-plugin` |
| `packages/paperclip-skill/` | (verify — scan missed this detail) | `@prep/*` if currently `@codrag/*`, else skip |
| `src/prep/dashboard/` | (verify in package.json) | `prep-dashboard` / `@prep/dashboard` |
| `websites/apps/marketing/` | (verify) | `@prep/marketing-site` |
| `websites/apps/docs/` | (verify) | `@prep/docs-site` |
| `websites/apps/support/` | (verify) | `@prep/support-site` |
| `websites/apps/payments/` | (verify) | `@prep/payments-site` |

The implementation plan will confirm each package's current `name` field from its `package.json` during Phase 6 inventory before renaming. The rename outcome is determined by the grep: whatever `@codrag/*` currently reads, becomes `@prep/*`.

**Import rewrite** (~292 occurrences in 157 files): `from "@codrag/ui"` → `from "@prep/ui"`.

**VS Code extension** (user-visible surface):

| Surface | Change |
|---|---|
| `package.json` → `name` | `prep-vscode` |
| `package.json` → `displayName` | `Prep` |
| `package.json` → `icon` | `media/prep-icon.png` (+ rename file) |
| `package.json` → `homepage`/`repository` | `runprep.io` / `MagneticAnomaly/Prep` |
| `contributes.commands` (`codrag.search`, etc.) | `prep.search`, `prep.assembleContext`, etc. |
| `contributes.configuration` keys (`codrag.daemonPort`) | `prep.daemonPort` |
| `contributes.viewsContainers` (id `codrag-sidebar`) | `prep-sidebar` |
| `media/codrag-icon.png`, `codrag-sidebar.svg` | rename files |
| `src/extension.ts` registerCommand calls | `"prep.search"`, etc. |
| `src/extension.ts` `getConfiguration("codrag")` | `"prep"` |

No settings migration for users (alpha, no users).

**Publisher ID** `magnetic-anomaly`: decision D8 — recommend keep.

**Verification:** `npm install`, `npm run typecheck`, extension builds .vsix, Storybook loads, dashboard dev server runs.

### Section 8 — MCP surface

**Tool renames** in `src/prep/mcp_tools.py`, `mcp/server.py`, `mcp_direct.py`:

| Old | New |
|---|---|
| `codrag` | `prep` |
| `codrag_search` | `prep_search` |
| `codrag_impact` | `prep_impact` |
| `codrag_audit` | `prep_audit` |
| `codrag_observe` | `prep_observe` |
| `codrag_concepts` | `prep_concepts` |

**MCP server name** `"codrag"` → `"prep"` in `mcp-server.json`, `src/prep/mcp/server.py`, `src/prep/mcp_direct.py`.

**Client configs in this repo:**
- `.claude/mcp.json`: `"codrag"` server key → `"prep"`; command path → `prep-mcp-wrapper.sh`
- `.cursor/mcp.json`: same
- `codrag-mcp-wrapper.sh` → `prep-mcp-wrapper.sh`

**Paperclip plugin** (`packages/paperclip-plugin-prep/src/manifest.ts`):
- Plugin `id: 'codrag'` → `id: 'prep'`
- Tool IDs use colons: `codrag:context` → `prep:context`, `codrag:search` → `prep:search`, etc.
- `src/ui/SettingsPage.tsx` — all user-visible strings.

**Rules generator** (`src/prep/core/rules_generator.py`):
- `_build_managed_content()`: every "CoDRAG"/`codrag.io`/tool-name example → Prep/`runprep.io`/prep-tools.
- `_write_agents_md()`: `<!-- codrag-managed-start -->` markers → `<!-- prep-managed-start -->`.
- `.cursor/rules/codrag.mdc` filename → `prep.mdc`.
- Cursor/Windsurf/Claude/Copilot per-IDE writers: all "codrag" strings updated.

**Verification:** `prep serve`, each of six tools callable from a client under new name; regenerate this repo's `AGENTS.md`, confirm zero codrag references.

### Section 9 — Tauri desktop

**`src/prep/dashboard/src-tauri/tauri.conf.json`:**

| Field | Old | New |
|---|---|---|
| `productName` | `CoDRAG` | `Prep` |
| `identifier` | `io.codrag.app` | `io.runprep.app` |
| `externalBin` | `["codrag-daemon"]` | `["prep-daemon"]` |
| `updater.endpoints` | `github.com/MagneticAnomaly/CoDRAG-MCP/releases/...` | `github.com/MagneticAnomaly/Prep/releases/...` |
| `app.windows[].title` | `CoDRAG` | `Prep` |
| `bundle.icon` refs | `codrag-*.png` | `prep-*.png` |

**Icon assets**: size-named files (`32x32.png`, `icon.icns`) stay; any `codrag-*.png` in the icon dir renames.

**Rust side** (`src/main.rs`, `lib.rs`): window titles, `const APP_NAME`, sidecar spawn `Command::new_sidecar("codrag-daemon")` → `"prep-daemon"`.

**Sidecar** (`codrag-daemon.spec` → `prep-daemon.spec`, internal `name="codrag-daemon"` → `"prep-daemon"`, `scripts/build_sidecar.sh` updates).

**Updater impact (⚠ one-way door):** Bundle ID change means existing CoDRAG installs will not auto-update to Prep. macOS treats `io.runprep.app` as a different app entirely. For alpha, acceptable — document in release notes. Internal testers need a fresh install; CoDRAG.app and Prep.app can coexist.

**Signing cert** unchanged — certs are per-team, not per-app.

**Verification:** `cargo tauri build --debug` produces `Prep.app`; launch shows "Prep" title; sidecar runs as `prep-daemon`.

### Section 10 — Data paths, env vars, SQLite, embedded mode

**Path table:**

| Variable | Old | New |
|---|---|---|
| XDG data path | `~/.local/share/prep/` | `~/.local/share/prep/` |
| Legacy path | `~/.prep/` | `~/.prep/` |
| CWD-relative legacy | `./codrag_data/` | `./prep_data/` |
| Embedded per-project | `.prep/` | `.prep/` |
| Env override | `CODRAG_DATA_DIR` | `PREP_DATA_DIR` |

**Core files:** `src/prep/core/paths.py` (path construction), `src/prep/core/data_dir_migration.py` (Phase 113 migration logic extended).

**Env vars** (~125 files): `CODRAG_DATA_DIR`, `CODRAG_PORT`, `CODRAG_DEV_MODE`, `CODRAG_API_KEY`, `CODRAG_TIER`, others. `tests/conftest.py` updates in lockstep.

**SQLite files in `~/.local/share/prep/`:**
- `codrag_settings.db` → `prep_settings.db`
- `codrag_antibodies.db` → `prep_antibodies.db`
- `codrag_token_telemetry.db` → `prep_token_telemetry.db`
- Others surfaced by grep during Phase 3.

**SQLite schemas**: grep for `CREATE TABLE codrag_*`, `ALTER TABLE codrag_*`, column names containing `codrag`. Rename any hits.

**Auto-migration (decision D4, recommended):** extend `data_dir_migration.py` with a one-shot `codrag → prep` migration on first `prep serve`. Sentinel-file gated (`<data_dir>/.migrated_from_codrag`), same pattern as Phase 113's `.migrated_from_cwd`. Protects against losing your own dogfood data.

**Embedded `.prep/` migration (decision D5):** on project open, if `.prep/` exists and `.prep/` does not, rename atomically. Otherwise ignore.

**Test coverage:** extend `tests/test_data_dir_migration.py`, update `tests/test_paths.py`, `tests/conftest.py`.

**Verification:** first `prep serve` with pre-existing `~/.local/share/prep/` → migrates to `~/.local/share/prep/`, sentinel written; second run → no re-migration.

### Section 11 — Websites & domains

**Domain table:**

| Old | New |
|---|---|
| `codrag.io` | `runprep.io` |
| `codrag.ai` (5 refs, non-existent) | **delete** |
| `docs.codrag.io` | `docs.runprep.io` |
| `support.codrag.io` | `support.runprep.io` |
| `support@codrag.io`, `security@codrag.io` | `support@runprep.io`, `security@runprep.io` |

**Per-app changes** (each of `marketing/`, `docs/`, `support/`, `payments/`):

- `package.json` name: `@codrag/*-site` → `@prep/*-site`
- `netlify.toml`: site name, env vars, redirects
- `next.config.js`: `NEXT_PUBLIC_SITE_URL`, rewrites
- `src/app/layout.tsx`: `<title>`, OG meta, canonical URL
- `src/app/sitemap.ts`, `robots.ts`: base URL
- `src/app/rss/route.ts` (if exists): feed URL
- All `*.tsx` content: "CoDRAG" → "Prep"

**Marketing-specific:**
- Route renames: `compare/codrag-vs-greptile` → `compare/prep-vs-greptile`; same for `codrag-vs-cursor-indexing`
- Hero components in `packages/ui/src/components/marketing/heroes/*.tsx`
- `src/lib/pricing.ts` copy
- Feature-gate link `codrag.io/pricing` → `runprep.io/pricing` (in `src/prep/core/feature_gate.py` AND `tests/test_feature_gate.py` assertion)
- OG / Twitter card images (flag for visual redesign — decision D6)
- Blog / changelog copy

**Docs-specific:** CLI reference routes (`src/app/cli/page.tsx` etc.) — every `codrag <cmd>` → `prep <cmd>`.

**Support-specific:** bug report route payload fields; `DiscussionList.tsx` links post-GitHub-rename.

**Payments-specific:** Lemon Squeezy product names / SKUs, success page copy, license recovery email templates.

**`websites/MagneticAnomaly/`:** kept in place (decision D3). Any "CoDRAG" references inside (scan found at least one in `src/App.jsx`) get the same find/replace treatment as other content. No deletion, no directory rename.

**Verification:** dev server for each site, grep DOM for "codrag" returns 0 matches, built `sitemap.xml` uses `runprep.io` only.

### Section 12 — Assets & UI strings

**Image/icon files renamed** (see Files list above).

**Update every reference**: `<img src>`, `<Image src>`, CSS `url()`, VS Code `icon:` ref.

**OG / Twitter card / favicon images** (decision D6): rename filenames only. Visual contents (existing logos, pixel art, typography) are preserved as-is; only the filename + references update. Image recreation is a separate work item outside this rename.

**User-visible UI strings in dashboard** (`src/prep/dashboard/src/`):
- `StartupScreen.tsx`, `UpdateBanner.tsx` (version banner), `Toast.tsx`, `ErrorToast.tsx`
- `SettingsDrawer.tsx` section headers / tooltips
- `UsageGuidePanel.tsx` help text
- `components/site/SiteHeader.tsx`, `SiteFooter.tsx` brand
- `components/team/EmbeddedModeIndicator.tsx` (`.prep/` → `.prep/`)
- `components/project/AddProjectModal.tsx` copy

**Error messages with URLs**: `raise RuntimeError("See codrag.io/...")`, JSON envelopes with `docs_url: "https://codrag.io/..."`.

**Verification:** click-through of dashboard, VS Code extension — no "CoDRAG" anywhere; deliberate error → "Prep" in message.

### Section 13 — Content rewrites (root docs + templates)

| File | Strategy |
|---|---|
| `README.md` | Rewrite intro/positioning paragraphs; find/replace in Build/Architecture sections |
| `CLAUDE.md` | Rewrite dogfooding section; find/replace elsewhere |
| `AGENTS.md` | Auto-generated by rules_generator — regenerate, don't hand-edit |
| `SUPPORT.md` | Email + URL updates; copy refresh |
| `SECURITY.md` | Same |
| `CHANGELOG.md` | Append rename entry; historical entries stay |
| `LICENSE` | `"CoDRAG"` in copyright line → `"Prep"` |
| `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/CLI.md`, `docs/TROUBLESHOOTING.md` | Find/replace + coherence pass |
| `docs/MASTER_TODO.md`, `docs/MARKETING_MASTER_TODO.md`, `docs/PRODUCT_AND_BUSINESS_OVERVIEW.md` | Find/replace |
| `docs/superpowers/plans/*.md`, `docs/superpowers/specs/*.md` | Find/replace (historical) |

**`.gitignore`**: `.prep/` → `.prep/`, `codrag_data/` → `prep_data/`.

**`.github/` surfaces:**
- `ISSUE_TEMPLATE/*.yml`
- `workflows/release.yml` — artifact names, release body
- `workflows/docker-headless.yml` — image name
- `workflows/engine-wheels.yml` — wheel filename `codrag_engine-*.whl`
- `workflows/security-audit.yml`, `workflows/websites-ci.yml`
- `CODEOWNERS` if present

**Verification:** read `README.md` and `CLAUDE.md` cover to cover — do they read as coherent Prep docs, not find/replaced CoDRAG docs?

### Section 14 — CLaRa scrubbing

**Decision D2: delete.** CLaRa is gone everywhere, no archive.

**Live code — scrub completely:**
- `src/prep/core/lod_extractor.py` docstring/comment refs
- `pyproject.toml` optional-dependencies `clara` extra — remove
- `scripts/publish_clara_subtree.sh` — delete
- `src/prep/core/trace/analyzers/*` — scrub any CLaRa mentions
- CLaRa in test files → delete dead tests, rename files

**Historical docs — delete entirely:**
- `docs/Phase31_CLaRa-replacement/` — `git rm -rf` the whole directory
- `docs/Phase00_Initial-Concept/STAGE2_CLARA_QUERYTIME.md` — `git rm`
- Any other file with `CLaRa` in the filename — delete
- Any `CLaRa` mention in other phase docs — scrub from content

**`.git/config`:** remove `clara-dev` remote (Phase 0 / Phase 22). GitHub repo `EricBintner/CLaRa-Remembers-It-All` untouched on GitHub; just no longer referenced locally.

**Similarly-named-but-not-CLaRa (keep):**
- `docs/Phase64_prep-for-agents+paperclip/` — uses "prep" as verb, coincidental
- `docs/Phase67_AGENTS/HR-concept-adapter/` — unrelated

**Verification:** `grep -rni "clara\|CLaRa" --exclude-dir=.git --exclude-dir=node_modules` → 0 hits across the repo.

### Section 15 — Historical phase docs

`docs/` contains ~110 `Phase*/` dirs. Most reference "CoDRAG" pervasively because they predate the rename.

**Classification:**

| Class | Treatment |
|---|---|
| **Living** (in-flight, or referenced in CLAUDE.md / ROADMAP / MASTER_TODO) | Full find/replace + coherence pass |
| **In-between** (landed but still actively referenced) | Find/replace |
| **Archival** (completed, no active references) | **Leave as-is**, allowlist out of grep gate |

**Rule of thumb:** if not referenced outside its own dir → archival → allowlist. Default to archival when uncertain.

**Allowlist mechanics:** `.rename-allowlist.txt` at repo root lists paths excluded from the grep gate count. Example entries:
```
docs/Phase00_Initial-Concept/
docs/Phase01_Foundation/
docs/Phase02_Dashboard/
CHANGELOG.md
```
(No `docs/archive/` entry — decision D2 deletes CLaRa docs rather than archiving.)

**Phase102 draft doc (this file supersedes it)**: keep `docs/Phase102_Prep_rename/Phase102_Prep_rename.md` with a one-line pointer header noting supersession, rather than deleting.

**Verification:** iterative — run grep gate, for each hit decide rewrite vs allowlist, capture decisions. Final: `<gate> | wc -l` = 0.

---

## Git operations

### Local clone (during branch work)

```
git checkout main
git pull origin main
git checkout -b rename/prep
git remote remove clara-dev
# ... all phases commit into this branch ...
git push -u origin rename/prep    # backup during work
```

### Subtree handling (`public/codrag-mcp/`, `public/codrag-deploy/`)

Not git submodules — plain directories each containing an independent `.git/`. Published via `scripts/publish_*_subtree.sh` → sibling GitHub repos.

1. `git mv public/codrag-mcp public/prep-mcp` (outer repo records rename; nested `.git` moves along).
2. Rename publish script + update its remote URL.
3. *After* GitHub ops (Phase 22), update script's remote URL to `git@github.com:MagneticAnomaly/Prep-MCP.git`.
4. Re-publish once to sync the renamed sibling repo.

### GitHub ops (Phase 22, after merge to `main`)

1. **On github.com:**
   - `EricBintner/CoDRAG` → Settings → Transfer → `MagneticAnomaly` → Rename → `Prep`
   - `MagneticAnomaly/CoDRAG-MCP` → Rename → `Prep-MCP`
   - `MagneticAnomaly/CoDRAG-MCP-DEV` → Rename → `Prep-MCP-DEV`
   - `MagNeticAnomaly/codrag-deploy` → Transfer to canonical-cased `MagneticAnomaly` → Rename → `Prep-deploy`
2. **Locally, rewrite remote URLs:**
   ```
   git remote set-url origin git@github.com:MagneticAnomaly/Prep.git
   git remote remove codrag-mcp
   git remote remove codrag-mcp-dev
   git remote remove dev
   git remote remove deploy-public
   git remote add mcp     git@github.com:MagneticAnomaly/Prep-MCP.git
   git remote add mcp-dev git@github.com:MagneticAnomaly/Prep-MCP-DEV.git
   git remote add deploy  git@github.com:MagneticAnomaly/Prep-deploy.git
   git fetch --all
   ```
3. `git push origin main` — verify.

### History preservation

All four repos: native GitHub transfer+rename preserves commits, PRs, issues, stars, tags, releases. Local `git log` unaffected; SHAs stable.

### Tags/releases (decision D1)

Recommended: leave historical tags (`v0.x.x` with CoDRAG-named release artifacts). Start a new tag series when cutting first Prep release.

---

## Verification

### Per-phase checks

- **After every phase:** `ruff check`, `mypy` (if Python touched), `cargo check` (if Rust), `npm run typecheck` (if TS).
- **After phase 3, 5, 7:** full `pytest -x`.
- **After phase 9 (sidecar):** `pyinstaller prep-daemon.spec` produces `dist/prep-daemon`; binary runs.
- **After phase 10 (Tauri):** `cargo tauri build --debug` dry-run produces `Prep.app`.
- **After phase 14:** `scripts/dev.sh` and visit each of the 4 sites; grep DOM for "codrag" (0 matches); check no 404s or broken images.
- **After phase 19:** end-to-end — `prep serve`, open dashboard :5174, trigger index build, exercise each MCP tool from a client.

### Zero-occurrence grep gate (Phase 20)

```bash
grep -rni "codrag\|clara\|codrag\.io\|codrag\.ai" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=target --exclude-dir=dist --exclude-dir=build \
  --exclude-dir=__pycache__ \
  --exclude=package-lock.json --exclude=Cargo.lock --exclude=uv.lock \
  . | grep -v -f .rename-allowlist.txt
```

Must return 0 lines. Allowlist entries (Section 15).

---

## Decisions (resolved 2026-04-21)

| # | Decision | Resolution |
|---|---|---|
| D1 | Tags/releases on current GitHub | Leave historical `v0.x` tags; start new series at first Prep release |
| D2 | CLaRa historical docs | **Delete** — no archive, no allowlist |
| D3 | `websites/MagneticAnomaly/` | **Keep in place**; "CoDRAG" refs inside get same find/replace as other content |
| D4 | Data-dir auto-migration | Implement — one-shot migration in `data_dir_migration.py`, sentinel-gated |
| D5 | Embedded `.prep/` migration in client repos | Auto-detect and rename to `.prep/` on project open |
| D6 | OG / Twitter / favicon images | Rename filenames only; visual content preserved (no redesign) |
| D7 | PyPI / crates.io / npm publishing | Not today, soon. Separate task: check `prep` name availability on PyPI, npm, crates.io before first publish (see Prerequisites for follow-ups) |
| D8 | VS Code publisher ID `magnetic-anomaly` | Keep |
| D9 | Tauri bundle-ID format | `io.runprep.app` |
| D10 | Phase102 draft doc | Keep with "superseded" header pointing at this spec |

---

## Risks

| Risk | Mitigation |
|---|---|
| Missed string in SQLite schema | Grep all `.sql` + `CREATE TABLE` during Phase 3 |
| Tauri updater misconfigured → no auto-updates | Explicit verification of `updater.endpoints`; dry-run release |
| Public subtrees out of sync | Explicit re-publish in Phase 11 + Phase 22 |
| Generated `.cursor/rules/codrag.mdc` lingers in client projects | `prep.mdc` coexists; old file harmless but cosmetic |
| User shell has `export CODRAG_DATA_DIR=...` | Daemon prints one-time warning if `CODRAG_*` detected, suggests new name |
| Missed lazy/dynamic import (`importlib.import_module("codrag.foo")`) | Full test suite catches |
| `prep` name taken on PyPI/npm | Out of scope — no publishing in this rename |

---

## Scope

**In scope**: every identifier, file, directory, URL, image, docstring, config key, user-visible string, and generated template that says "CoDRAG", "codrag", or "CODRAG". Git ops across 4 repos. Scrub dead CLaRa references. Archive historical CLaRa phase docs.

**Out of scope**: feature changes, visual redesign beyond asset rename + OG image flagging, PyPI/crates.io/npm/VS Code Marketplace publishing, documentation restructure beyond find/replace + coherence passes, Phase113/Phase117 or other in-flight work (rename branch rebases on top of any merges).

---

## Prerequisites before execution

1. ~~Answers to the 10 open decisions~~ — resolved 2026-04-21.
2. No concurrent branch work during the rename window.
3. `runprep.io` registered before Phase 14 (or explicit `TODO_DOMAIN` marker placeholder).

## Follow-ups (outside this rename)

- **Registry name check** (from D7): before first public publish, verify `prep` is available on PyPI, `@prep` on npm, and `prep-*` crate names on crates.io. If any collide, pick a disambiguated publish name (e.g., `runprep`, `prep-ai`) without changing internal identifiers — only the published distribution name changes.
- **Visual refresh** (from D6 and guiding rule): if/when a logo / OG card redesign is desired, it's a separate work item. The rename leaves existing pixels untouched.
- **Stale users of deleted `clara-dev` remote**: none expected; if anyone had this remote configured in a fork/clone, they'll hit a "remote not found" on fetch.

---

## Next step

Implementation plan (via superpowers:writing-plans skill) will translate this design into concrete per-phase task lists with file-level specificity, commit scaffolding, and verification commands.
