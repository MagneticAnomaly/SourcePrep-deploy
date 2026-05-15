# Phase 132 Tier B — MCP Integration

> **Pages audited:** `/mcp` (prior session), `/mcp/ides`, `/mcp/terminal`,
> `/mcp/paperclip`
> **Method:** desk verification on 2026-05-14 against single-source registries
> (`websites/apps/docs/src/config/mcp-setup.ts`,
> `packages/paperclip-plugin-prep/`).

## `/mcp` overview

Audited in a prior session (Task #20). Compare row stays valid; surfaced
undocumented `roadmap` action branch in `server.py:4252` flagged for product
decision (out of scope here).

## `/mcp/ides`

Page renders from `MCP_TOOLS.filter(t => t.category === 'ide')` in
`mcp-setup.ts`. Registry contains 6 IDE entries: Cursor (primary), Windsurf,
Antigravity, GitHub Copilot, Zed, Cline.

### Claims

1. **Cursor (primary), Windsurf, Antigravity, GitHub Copilot, Zed, Cline** —
   ✅ all present in registry; primary flag on Cursor matches.
2. **Per-IDE config blocks** — ✅ each entry's `config`, `serverKey`, `file`,
   `fileHint`, `notes` rendered verbatim from the registry. Trust the
   registry; fidelity is centralized.
3. **Intro line referencing "Cline, Roo, CodeGPT"** — ⚠ **fixed 2026-05-14**:
   only Cline is in the single-source registry. Reworded to "...and Cline"
   plus a generic "other MCP-aware editors" catch-all. Roo and CodeGPT have
   no representation in the registry and shouldn't be claim-listed.
4. **AnimatedIDE Storybook embed** (`website-demos-animatedide--default`) —
   ✅ verified: `packages/ui/src/stories/console/AnimatedIDE.stories.tsx`
   declares `title: 'Website/Demos/AnimatedIDE'`. StoryId resolves.

### Result

🟢 Done. Single-source-of-truth design means future drift will be a registry
edit, not a per-page edit.

## `/mcp/terminal`

Page renders from `MCP_TOOLS.filter(t => t.category === 'cli')`. Registry
contains 3 CLI entries: Claude Code (primary), OpenAI Codex, Gemini CLI.

### Claims

1. **"Claude Code, OpenAI Codex, Gemini CLI"** — ✅ matches registry exactly.
2. **Per-CLI config blocks** — ✅ rendered from registry; same single-source
   guarantee as `/mcp/ides`.
3. **No StoryEmbed on this page** — N/A.

### Result

🟢 Done. No edits required.

## `/mcp/paperclip`

Hardcoded page (no registry binding). Audited against
`packages/paperclip-plugin-prep/` source-of-truth.

### Claims

1. **"5 tools" + tools table (prep:context, prep:search, prep:impact,
   prep:audit, prep:observe)** — ✅ exactly matches the 5 tool registrations
   in `packages/paperclip-plugin-prep/src/worker/index.ts:94-212`. **Plugin
   does NOT bridge `prep:concepts`** — only 5 of the 6 prep MCP tools are
   exposed through the Paperclip plugin worker. If a future plugin version
   adds concepts, update this docs page.
2. **`pnpm paperclipai plugin install @prep/paperclip-plugin`** — ✅ npm
   package name matches `packages/paperclip-plugin-prep/package.json:2`
   (`"name": "@prep/paperclip-plugin"`).
3. **Daemon at `localhost:8400`** — ✅ matches CLAUDE.md daemon port.
4. **Settings table: `daemon_url` / `project_id` / `auto_context`** — not
   verified against the plugin's settings schema this pass. Flag for next
   audit cycle if the plugin worker exposes a richer schema.
5. **"SourcePrep Desktop App — Download from prep.dev"** — ⚠ **fixed
   2026-05-14**: updated to `sourceprep.io/download` per brand split.
6. **GitHub source link `packages/paperclip-plugin`** — ⚠ **fixed
   2026-05-14**: actual directory is `packages/paperclip-plugin-prep`.
   Updated link and label.
7. **AgentOpsPanel Storybook embed
   (`dashboard-agents-agentopspanel--active`)** — ✅ verified:
   `packages/ui/src/stories/agents/AgentOpsPanel.stories.tsx` declares
   `title: 'Dashboard/Agents/AgentOpsPanel'` with `Active` export. StoryId
   resolves.
8. **"Three SourcePrep agents (HR, Researcher, Custodian)" in caption** —
   not fact-checked against current agent registry. Flag for next audit
   cycle alongside settings table verification.

### Result

🟢 Desk-done. Two desk fixes landed. Two soft items deferred (settings
table schema verification + 3-agent count verification).

## Summary of fidelity fixes landed 2026-05-14

| Fix | Page |
|---|---|
| Reworded intro to drop registry-absent extensions (Roo, CodeGPT) | `/mcp/ides` |
| `prep.dev` → `sourceprep.io/download` (brand split) | `/mcp/paperclip` |
| `packages/paperclip-plugin` → `packages/paperclip-plugin-prep` | `/mcp/paperclip` |

## Cross-session observations saved

- **6033c783697a** anchored to `websites/apps/docs/src/app/mcp/paperclip/page.tsx` — captures the 5-tool plugin scope, npm-name verification, and brand/path fixes.

## Deferred items for the next audit cycle

- `/mcp/paperclip` settings table (`daemon_url` / `project_id` /
  `auto_context`) verification vs plugin schema.
- `/mcp/paperclip` "three agents (HR, Researcher, Custodian)" count vs
  current agent registry.
- Install-required: actually wire each IDE config and confirm the AI agent
  successfully calls a SourcePrep tool. Batch with Tier A install-required
  session.
