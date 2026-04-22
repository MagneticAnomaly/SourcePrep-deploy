# SourcePrep Rename — Design Spec

**Date:** 2026-04-22
**Branch:** will create `rename/runprep-to-sourceprep` off `main`
**Supersedes:** `docs/superpowers/specs/2026-04-21-prep-rename-design.md` (prior CoDRAG→RunPrep/prep split)
**Source doc:** `docs/Phase102_Prep_rename/SOURCEPREP_RENAME_INSTRUCTIONS.md`

## 1. Goal

Rebrand the user-facing product from **RunPrep** to **SourcePrep** (domain `sourceprep.io`) while preserving the code-level **`prep`** identifier — the CLI binary, MCP tool names, Python package, npm scope, Rust crates, env var prefix, and internal routing — completely unchanged.

Any leftover `codrag` in live code (not migration-source markers) is cleaned up to `prep` in the same sweep.

### Starting baseline

Commit `e1d8191d` ("rebrand: CoDRAG/RunPrep → SourcePrep across codebase", 2026-04-22 11:12:13) is already on `main`. It covers a partial prose sweep: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/prep.mdc`, marketing hero + dashboard `App.tsx` + settings overlay files, docs guides (`concepts/`, `guides/*`), marketing site pages (`faq`, `pricing`, `research`, `integrations`), new logo assets, plus the source doc itself. It does **not** touch:

- Tauri config (`src-tauri/tauri.conf.json`)
- VS Code extension (`packages/vscode/package.json`)
- Rename gate (`scripts/rename_gate.sh`)
- Data-dir migration chain (`src/prep/core/paths.py`, `data_dir_migration.py`)
- `pyproject.toml` metadata
- Leftover `codrag` in live code

The plan treats `e1d8191d` as done-and-trusted. Phase 4 (brand prose sweep) becomes an *audit + complete* pass rather than a from-scratch sweep — it will inventory what remains against the commit's 55-file footprint and fill the gaps. No phase re-does work already committed.

## 2. Naming Architecture

### Code-level (`prep`, unchanged)

The user **types** these or they exist only inside code. They follow the shorthand convention and match the CLI binary name per shell convention (`GIT_*`/`git`, `DOCKER_*`/`docker`).

| Surface | Value |
|---|---|
| CLI binary | `prep` |
| MCP tool names | `prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`, `prep_concepts` |
| Python package / imports | `src/prep/`, `from prep.core import ...` |
| Python PyPI package name | `prep` |
| npm scope | `@prep/*` (workspace-only, unpublished) |
| Rust crates | `prep-engine`, `prep-walker`, `prep-parser`, `prep-graph`, `prep-chunking`, `prep-sanitize`, `prep-selfheal` |
| Env var prefix | `PREP_*` (e.g., `PREP_DATA_DIR`, `PREP_S3_ACCESS_KEY`) |
| MCP routing key | `prep_project_id` in AGENTS.md |
| Wrapper / helper scripts | `prep-mcp-wrapper.sh`, `scripts/publish_prep_mcp_subtree.sh` |
| Public subtree mirror paths | `public/prep-deploy/`, `public/prep-mcp/` |
| Sidecar binary name | `binaries/prep-daemon` |
| Internal URI scheme | `prep://project_id/ITEM-ID` (audit/paperclip addresses) |
| Sentinel files | `/tmp/prep_daemon_stop`, `/tmp/prep_daemon_logs/` |
| VS Code extension name | `prep-vscode` (package name) |
| VS Code icon assets | `packages/vscode/media/prep-icon.png`, `prep-sidebar.svg` |
| Paperclip plugin package dir | `packages/paperclip-plugin-prep/` |

### Brand-level (`SourcePrep` / `sourceprep`, new)

The user **reads** these as the product name, or sees them as user-facing paths/URLs.

| Surface | Current | Target |
|---|---|---|
| Brand prose (UI, docs, marketing, README, LICENSE) | "RunPrep" | "SourcePrep" |
| Dashboard window title / header | "RunPrep" | "SourcePrep" |
| Tauri `productName` | "RunPrep" | "SourcePrep" |
| Tauri bundle identifier | `io.runprep.app` | `io.sourceprep.app` |
| Tauri updater endpoint | `github.com/MagneticAnomaly/RunPrep/releases/latest/download/latest.json` | `github.com/MagneticAnomaly/SourcePrep/releases/latest/download/latest.json` |
| Tauri window `title` | "RunPrep" | "SourcePrep" |
| VS Code `displayName` | "RunPrep — Local Code Context Engine" | "SourcePrep — Local Code Context Engine" |
| VS Code statusBar / tooltip / webview titles | "RunPrep …" | "SourcePrep …" |
| VS Code `homepage`, `repository`, `bugs` | `MagneticAnomaly/RunPrep`, `runprep.io` | `MagneticAnomaly/SourcePrep`, `sourceprep.io` |
| Primary domain | `runprep.io` | `sourceprep.io` |
| Subdomains | `api.runprep.io`, `docs.runprep.io`, `payments.runprep.io`, `support.runprep.io` | `api.sourceprep.io`, `docs.sourceprep.io`, `payments.sourceprep.io`, `support.sourceprep.io` |
| Email addresses | `support@`, `security@`, `licenses@`, `hello@`, `noreply@` at `runprep.io` | same mailboxes at `sourceprep.io` |
| Embedded data dir | `.runprep/` | `.sourceprep/` |
| XDG data dir | `~/.local/share/runprep/` | `~/.local/share/sourceprep/` |
| localStorage keys | `runprep_*` | `sourceprep_*` |
| GitHub repos (main org) | `MagneticAnomaly/RunPrep`, `RunPrep-MCP`, `RunPrep-MCP-DEV`, `RunPrep-deploy` | `MagneticAnomaly/SourcePrep`, `SourcePrep-MCP`, `SourcePrep-MCP-DEV`, `SourcePrep-deploy` |
| Error messages / user-visible logs | "RunPrep could not …" | "SourcePrep could not …" |
| pyproject.toml `description` / `authors` / URLs | "Prep" / "Prep Team" / RunPrep URLs | "SourcePrep" / "SourcePrep Team" / SourcePrep URLs |
| Paperclip plugin manifest `author` | `RunPrep <hello@runprep.io>` | `SourcePrep <hello@sourceprep.io>` |
| Marketing site metadataBase / OG / twitter:card | `https://runprep.io` | `https://sourceprep.io` |

### Brand asset files

Rename file AND refs:

- `websites/apps/marketing/public/prep-logo.png` → `sourceprep-logo.png`
- `websites/apps/marketing/public/prep-logo-dark.png` → `sourceprep-logo-dark.png`
- `websites/MagneticAnomaly/public/Prep-Logo2.png` → `SourcePrep-Logo2.png` (note: `App.jsx:799` currently references a non-existent `/RunPrep-Logo2.png` — rename fixes this incidentally)
- `websites/MagneticAnomaly/app-content/Prep.md` → `SourcePrep.md`

VS Code icon filenames stay `prep-icon.png` / `prep-sidebar.svg` (internal asset refs, code-level).

### Frozen / do-not-touch

- **VS Code marketplace publisher**: `magnetic-anomaly` (marketplace identity — renaming orphans all existing installs).
- **Migration source markers** in live code — these name the thing we're migrating FROM and must remain legible:
  - `src/prep/core/paths.py` — `legacy_cwd_data_dir()` returning `codrag_data`
  - `src/prep/core/data_dir_migration.py` — migrates from `.codrag/`, `~/.local/share/codrag/`, `~/.local/share/runprep/`
  - `src/prep/core/watcher.py` — `codrag_data` ignore rule
  - `tests/test_data_dir_migration.py`, `tests/test_paths.py`, `tests/test_no_cwd_relative_codrag_data.py` — regression tests validating migration behaviour
- **Historical docs** in `docs/Phase*/` — frozen artifacts of prior phases; do not sweep.
- **Research JSON dumps** (`docs/Phase103_AgentOptimizations/research/*.json`) — frozen experimental artifacts.
- **Prior rename's spec & plan** (`docs/superpowers/specs/2026-04-21-prep-rename-design.md`, `docs/superpowers/plans/2026-04-21-prep-rename-implementation.md`) — historical record.
- **Marketing home-page hero** (`websites/apps/marketing/src/app/page.tsx`) — off-limits for autonomous edits per standing rule. Flag any hero-text suggestions for explicit go-ahead.

### Leftover `codrag` in live code (clean up)

Per user rule: any `codrag` outside legitimate migration-source markers must be renamed. Apply the same brand/code split:

- **Code identifier** (function name, class name, variable, tool name, filename, module ref, dict key, test fixture path): rename to **`prep`** (matches CLI / MCP tool convention).
- **User-visible prose** (error message, log message shown to the user, UI string, docstring surfaced to an end user): rename to **`SourcePrep`**.

Most of the leftovers are code identifiers; prose occurrences are rare but must be classified during the audit.

- `src/prep/mcp/tool_hi.py` (3 refs to `codrag_hi`) → `prep_hi`
- `src/prep/mcp_tools.py` (3 refs) — audit and rename
- `src/prep/mcp_direct.py` (3 refs) — audit and rename
- `src/prep/mcp/server.py` (2 refs) — audit and rename
- `src/prep/a2a/handler.py` (6 refs) — audit and rename
- `src/prep/adapters/push_engine.py`, `paperclip_adapter.py`, `pm_adapter.py` — audit
- `src/prep/api/routers/*` — audit (query.py, system.py, opportunities.py, projects/build.py)
- `src/prep/services/*` — audit (pipeline_metadata.py, config_manager.py)
- `src/prep/cli.py` (4 refs) — audit
- `src/prep/server.py` (4 refs) — audit
- `src/prep/core/*` — audit non-migration files (stage_manifest.py, provenance.py, project_registry.py, repo_profile.py, rules_generator.py, __init__.py)
- `tests/test_codrag_hi.py` → `tests/test_prep_hi.py` (file rename)
- `tests/test_codrag_hi_scenario.py` → `tests/test_prep_hi_scenario.py` (file rename)
- `tests/test_no_cwd_relative_codrag_data.py` — **keep filename**. The file regression-tests the rule that legacy `codrag_data/` isn't created under CWD; the filename marks that regression intent and is itself a migration-source marker.
- `tests/fixtures/mini_repo/.runprep/` → `.sourceprep/` (fresh fixture, not a migration source)
- `.cursor/mcp.json`, `.claude/mcp.json` — already use `"prep"` server name; verify no leftover `codrag` strings
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/prep.mdc` — audit

**Stale artifact to delete:** `packages/vscode/codrag-vscode-0.1.0.vsix` (leftover compiled VSIX from CoDRAG era).

## 3. Data-dir migration chain

The product now supports three legacy generations of user data. Each migration is one-shot, sentinel-gated, and idempotent.

```
./codrag_data/          ──┐                             (CWD-relative, Phase 113)
~/.local/share/codrag/  ──┼──▶ ~/.local/share/runprep/ ──▶ ~/.local/share/sourceprep/
                          │     (prior XDG target)          (new XDG target)
.codrag/ (embedded)     ───────▶ .runprep/ (embedded) ──▶ .sourceprep/ (embedded)
```

**New migration link added in this rename:**

1. **XDG:** `~/.local/share/runprep/` → `~/.local/share/sourceprep/`, gated by sentinel `<new>/.migrated_from_runprep`.
2. **Embedded:** `.runprep/` → `.sourceprep/`, gated per-project by atomic rename or sentinel file in `paths.py:_migrate_embedded_dir()`.

**Conflict resolution** (both source and target populated): preserve legacy side as `<name>.migration-conflict.<ISO8601>`, same pattern as `migrate_from_legacy_codrag()`.

**Env var override:** `PREP_DATA_DIR` (absolute path) continues to override the default. Unchanged behaviour.

## 4. Env var policy (confirmed)

Env vars stay `PREP_*`. Rationale:

- Shell convention is tight: env vars match the binary name (`GIT_*` for `git`, `DOCKER_*` for `docker`, `npm_*` for `npm`).
- The CLI binary stays `prep` (doc-mandated). `prep serve` with `PREP_DATA_DIR` reads naturally; `SOURCEPREP_DATA_DIR prep serve` is cognitively jarring.
- No existing `PREP_*` user base would need migration.
- The source doc's "change `CODRAG_` → `SOURCEPREP_`" guidance is stale; the prior RunPrep rename already moved them to `PREP_*`, and the code-level classification still applies.

No `PREP_*` → `SOURCEPREP_*` renaming in this rename.

## 5. Rename gate

`scripts/rename_gate.sh` is the CI guard that blocks re-introducing old brand strings. Today it blocks `codrag|clara|codrag.io|codrag.ai`.

**Update:** extend the regex to also block `\brunprep\b|runprep\.io` so future commits can't regress. The gate reads `.rename-allowlist.txt` for legitimate exceptions — update that allowlist with:

- Migration-source markers (`src/prep/core/paths.py`, `data_dir_migration.py`, `watcher.py`, migration tests)
- Historical docs under `docs/Phase*/` (already excluded by directory skip list, but add pattern-based exceptions for any stragglers)
- This design doc itself and the plan file produced from it
- Prior rename's spec/plan files

## 6. GitHub repos & git history

Four new repos already exist:

- `https://github.com/MagneticAnomaly/SourcePrep` (main, replacing `RunPrep`)
- `https://github.com/MagneticAnomaly/SourcePrep-MCP` (replacing `RunPrep-MCP`)
- `https://github.com/MagneticAnomaly/SourcePrep-MCP-DEV` (replacing `RunPrep-MCP-DEV`)
- `https://github.com/MagneticAnomaly/SourcePrep-deploy` (replacing `RunPrep-deploy`)

**Preserve git history on main repo.** Re-point git remotes with fast-forward push (no squash, no rebase, no force-push to the new remote), same pattern as the prior RunPrep cutover. Tag a pre-rename backup (`pre-sourceprep-rename`) for rollback.

Subtree publish scripts (`scripts/publish_deploy_subtree.sh`, `scripts/publish_prep_mcp_subtree.sh`) keep their defaults — only the remote URLs change when remotes are rewired. Scripts themselves stay named `publish_*prep*_subtree.sh` (code-level).

## 7. Scope ordering (implementation phases)

The plan will sequence work so each commit is reviewable and the rename gate stays green between phases.

| Phase | Scope | Rationale |
|---|---|---|
| 0 | Rename gate extension + allowlist update | Gate must accept new `sourceprep`/`SourcePrep` before any rename commits can pass CI |
| 1 | Data-dir migration chain (`.runprep/` → `.sourceprep/`, XDG equivalent) + `paths.py` + tests | Lands migration infra first so subsequent code running against `.sourceprep/` works on fresh installs and legacy installs |
| 2 | Leftover `codrag` cleanup in live code | Tightens code-level naming before brand sweep (avoids mixing code renames with prose changes in diffs) |
| 3 | App identity — Tauri + VS Code extension | Isolated, high-signal change: bundle ID, displayName, URLs, statusBar, webview titles |
| 4 | Brand prose sweep — React UI, dashboard, marketing sites, docs site, README, SUPPORT.md, LICENSE, pyproject.toml, paperclip plugin | Largest touch count but mechanically uniform ("RunPrep" → "SourcePrep" case-matched) |
| 5 | URLs & subdomains + email addresses | Mechanical `runprep.io` → `sourceprep.io` sweep, all subdomains inclusive |
| 6 | Brand asset files — rename PNGs + refs | Logo file renames + updated `img src` / `icon:` references |
| 7 | Git remote rewire + push to new repos | Preserves history; includes pre-rename backup tag |
| 8 | Verification — rename gate green, typecheck (TS + mypy), pytest, Tauri dev build, dashboard smoke | Confirms no regressions |

Marketing hero edits in Phase 4 are flagged-not-executed — require explicit go-ahead per standing rule.

## 8. Out of scope

- Historical docs (`docs/Phase*/`) — frozen.
- VS Code marketplace publisher rename — would orphan existing installs.
- Social media handle migration — user handles separately.
- DNS / email deliverability setup for `sourceprep.io` subdomains — ops task. Code assumes the hostnames will resolve at release time.
- PyPI package rename from `prep` — code-level stays.
- npm registry publication of `@prep/*` — still workspace-only.
- Python module renames (e.g., `src/prep/` → `src/sourceprep/`) — code-level stays.
- MCP tool name changes — explicitly forbidden by source doc.
- `prep://` URI scheme — code-level routing, stays.

## 9. Success criteria

- `bash scripts/rename_gate.sh | wc -l` returns `0` (no rogue `codrag`, `clara`, `runprep`, `runprep.io` outside allowlist).
- `ruff check src/`, `mypy src/`, `pytest tests/ -v`, `npm run typecheck`, `npm run lint` all pass.
- `prep serve` starts cleanly; `~/.local/share/sourceprep/` is created; legacy `~/.local/share/runprep/` migrates automatically on first launch.
- Tauri dev build launches with window title "SourcePrep".
- Dashboard UI shows "SourcePrep" in header, error messages, update banner.
- `git log` on main repo shows intact history ending in post-rename commits; no rebased/squashed ancestry.
- All external links in user-visible surfaces point to `sourceprep.io` domain; no `runprep.io` links in live code.

## 10. Rollback

If the rename must be reverted:

1. `git reset --hard pre-sourceprep-rename` on main (the backup tag created in Phase 7).
2. `git push --force-with-lease` (only if the rename was already pushed — decide per user consent at rollback time).
3. Data-dir migrations are forward-only but non-destructive: legacy `~/.local/share/runprep/` is preserved alongside the new `~/.local/share/sourceprep/` (not moved), so reverting code makes the daemon use the old dir again.

Embedded `.runprep/` → `.sourceprep/` migration uses atomic rename; reverting the code doesn't rename the directory back. If a user reverts, they rename `.sourceprep/` → `.runprep/` manually (single `mv`); no helper script needed.
