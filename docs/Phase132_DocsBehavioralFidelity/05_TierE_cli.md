# Phase 132 Tier E — CLI Reference

> **Pages audited:** `/cli/commands`, `/cli/config`
> **Method:** desk verification on 2026-05-14 against `src/prep/cli.py` (Typer
> CLI) and env-var consumers across `src/prep/`.

## `/cli/commands`

### Claims verified — 20 commands all real

Every command documented on the page maps to a real `@app.command()` function
in `src/prep/cli.py`:

| Doc'd command | Real def | Line |
|---|---|---|
| `prep serve` | `def serve(...)` | 222 |
| `prep add` | `def add(...)` | 258 |
| `prep build` | `def build(...)` | 532 |
| `prep search` | `def search(...)` | 561 |
| `prep context` | `def context(...)` | 606 |
| `prep status` | `def status(...)` | 481 |
| `prep mcp` | `def mcp(...)` | 715 |
| `prep mcp-config` | `mcp-config` Typer name | 769 |
| `prep list` | `list` Typer name | 308 |
| `prep ui` | `def ui(...)` | 704 |
| `prep models` | `models` Typer name | 674 |
| `prep activity` | `def activity(...)` | 944 |
| `prep coverage` | `def coverage(...)` | 1084 |
| `prep overview` | `def overview(...)` | 1172 |
| `prep remove` | `def remove(...)` | 362 |
| `prep config` | `def config(...)` | 1023 |
| `prep drift` | `def drift(...)` | 1275 |
| `prep flow` | `def flow(...)` | 1328 |
| `prep opportunities` | `def opportunities(...)` | 1504 |
| `prep version` | `def version(...)` | 215 |

### Drift fix landed 2026-05-14

| Fix | Why |
|---|---|
| `prep serve` "set <code>PREP_LOG_LEVEL=DEBUG</code>" hint → "use <code>prep mcp --debug</code>" | `PREP_LOG_LEVEL` is fictional — no `getenv` call for it anywhere in `src/`; `cli.py:1399` and `server.py:56` hardcode `logging.INFO`. The real way to get verbose output is `prep mcp --debug`, which the same page already documents on the `mcp` command. |

### Not documented (intentionally or accidentally?)

`cli.py` exposes many more commands not surfaced in the docs:

- `delete` (376), `prune` (387) — destructive cleanup
- `rules-regenerate` (829) — IDE rules refresh
- `sync-headless` (1365) — headless build
- `hr-*` (1642+), `research-*`, `custodian-*`, `agents`, `agents-discover` —
  agent feature commands (Paperclip integration)
- Several unnamed commands at lines 703, 943, 1022, 1083, 1171, 1274, 1327, 1503

Flag for product decision: are the missing commands intentionally hidden
from public docs (e.g., destructive ops, internal agent ops), or has the
CLI grown faster than the page? Recommend a sweep when the agent feature
goes public.

### Result

🟢 Desk-done with one drift fix.

## `/cli/config`

### Claims verified

- **Default state location `~/.local/share/sourceprep/`** ✅ matches
  CLAUDE.md daemon-state location.
- **`PREP_DATA_DIR` override** ✅ at `core/paths.py:31` (`_ENV_VAR = "PREP_DATA_DIR"`).
- **`PREP_DATA_DIR` must be absolute path** ✅ — `paths.py` rejects non-absolute paths.
- **`PREP_ENGINE` (auto/rust/python)** ✅ at `core/__init__.py:10-11`.
- **`PREP_TIER` (free/pro/team/enterprise)** ✅ at `feature_gate.py:168`,
  but with a gotcha: only takes effect if `PREP_DEV_MODE=1` is also set
  (security check at line 170-176). The previous docs didn't mention this
  dependency.
- **`.sourceprep/config.json` project override + `.sourceprep/ignore`** —
  not deeply verified this pass; standard config-file conventions.
- **Phase 113 migration sentinel `.migrated_from_cwd`** ✅ documented in
  CLAUDE.md "Daemon State Location" section.

### Drift fixes landed 2026-05-14

| Fix | Why |
|---|---|
| Removed `PREP_LOG_LEVEL` env-var row | Variable is not read anywhere — `grep -r PREP_LOG_LEVEL src/` returns 0 matches. Logging level is hardcoded to `INFO` at multiple sites. |
| Added `PREP_DEV_MODE` row and amended `PREP_TIER` description to note the dev-mode dependency | Verified at `feature_gate.py:170-176`: PREP_TIER is ignored unless PREP_DEV_MODE=1, with a SECURITY warning logged otherwise. |

### Result

🟢 Desk-done with two drift fixes.

## Cross-reference: `/guides/codebase-audit` Quick Start

While verifying CLI commands I caught a related drift on the codebase-audit
guide page (Tier D territory but only surfaced here):

| Fix | Why |
|---|---|
| `/guides/codebase-audit` CLI Quick Start: replaced fictional `prep audit` with real `prep opportunities` | `prep audit` does not exist as a CLI command. Audits are triggered via the MCP `prep_audit` tool, the REST API (`POST /projects/{id}/audit`), or the dashboard's Audit panel. `prep opportunities` (cli.py:1504) is the real CLI for reading audit findings, with support for SARIF/JSON/AI-prompt output. |

This fix landed on the codebase-audit page, not the CLI page, but logging
here for the audit trail.

## Summary

3 drift fixes landed across 3 pages, all rooted in claims about CLI/env
behavior that didn't match the actual code:

1. `prep serve` no longer claims a `PREP_LOG_LEVEL` toggle (fictional)
2. `PREP_LOG_LEVEL` removed from env-var table; `PREP_DEV_MODE` added
3. `/guides/codebase-audit` no longer claims `prep audit` (use
   `prep opportunities`)
