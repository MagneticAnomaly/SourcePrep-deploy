# Phase 132 Tier F — Operational

> **Pages audited:** `/troubleshooting`, `/dashboard`
> **Method:** desk verification on 2026-05-14 against `src/prep/cli.py`,
> `src/prep/core/index.py`, `src/prep/mcp/server.py`, and
> `packages/ui/src/config/panelRegistry.ts`.

## `/troubleshooting`

### Claims verified

- **Daemon port 8400** ✅ matches CLAUDE.md.
- **Native ONNX embedder, ~132 MB, downloaded from HuggingFace, cached at
  `~/.cache/huggingface/hub`** ✅ matches Tier C audit + Tier D embeddings.
- **`min_score` default 0.15** ✅ `cli.py:565`.
- **`max_file_bytes` default 500 KB** ✅ confirmed at `core/index.py:218`
  (`500_000`) and `server.py:382, 410, 413`.
- **`PROJECT_SELECTION_AMBIGUOUS` error code** ✅ defined at
  `mcp/server.py:80` as `-32004`; surfaced verbatim in `mcp_tools.py`
  tool descriptions.
- **`~/.codeium/windsurf/mcp_config.json` config path** ✅ matches
  `mcp-setup.ts:103` Windsurf entry.

### Drift fixes landed 2026-05-14

| Fix | Why |
|---|---|
| Two references to `prep serve --debug` → `prep mcp --debug` | The `serve` command at `cli.py:222-256` only accepts `--host`, `--port`, `--reload`. There is no `--debug` flag on serve. The real verbose-logging path is `prep mcp --debug` (also documented on `/cli/commands` after the Tier E fix). |
| `prep config set max_file_bytes 1000000` → `prep config max_file_bytes 1000000` | The actual signature at `cli.py:1023-1027` takes two positional args (`key`, `value`), not a `--set` flag or a `set` subcommand. |

### Result

🟢 Desk-done with three drift fixes.

## `/cli/commands` (cross-cutting fix from Tier F)

While verifying the `prep config` syntax for troubleshooting, caught a
related drift on the CLI commands page:

| Fix | Why |
|---|---|
| `prep config [<key>] [--set <value>]` → `prep config [<key>] [<value>]` + dot-notation example | Signature is two positional args, not `--set`. |

This fix landed in Tier F session but technically corrects a Tier E page.
Logged here for audit trail.

## `/dashboard`

### Claims verified

- **4 panel categories** — exactly `status`, `search`, `context`, `config`
  per `panelRegistry.ts` (every panel's `category` field is one of these
  four). ✅ Matches dashboard page narrative.
- **Panel count ~27** — `panelRegistry.ts` has 27 entries with `category:`
  declarations. The page doesn't claim a specific count, just says "every
  panel belongs to one of four categories" — no count drift.
- **Panel Picker controls (toggle / refit / reset / copy / paste)** — UI
  claim; not source-verified this pass.
- **StoryEmbed references** — 5 embeds on this page. Not verified
  individually this pass; they're shared with stories audited in prior
  tiers. Flag for Phase 137 (live-asset integration) sweep.
- **Link to `/concepts/graph-enrichment` + `/concepts/code-graph`** — will
  need updating after Phase 138 (Concepts rename). Out of Tier F scope.

### Result

🟢 No edits required. Panel-category claim is accurate.

## Summary of fidelity fixes landed 2026-05-14

| Fix | Page |
|---|---|
| Two `prep serve --debug` → `prep mcp --debug` | `/troubleshooting` |
| `prep config set <key> <value>` → `prep config <key> <value>` | `/troubleshooting` |
| `prep config [--set]` syntax → positional `[<key>] [<value>]` | `/cli/commands` |

## Cross-session observation saved

- **TBD** — anchored to `src/prep/cli.py`; captures the `serve` command's
  actual flag surface and the `config` command's positional-arg syntax.
