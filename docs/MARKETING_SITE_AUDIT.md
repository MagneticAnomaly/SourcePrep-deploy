# Marketing Site Audit — Issue Tracking

> **First audited:** 2026-05-03
> **Last updated:** 2026-05-06
> **Status:** Open issues requiring follow-up

---

## Quick Summary

Marketing site has 30+ pages but sitemap only covers 12. Several pages have outdated content, future-dated changelogs, or internal notes exposed. **New as of 2026-05-06:** the public-facing graph-enrichment story is internally inconsistent (9-stage doc vs 15-stage marketing page, and "sync = instant" copy contradicts what the pipeline actually does), and integration naming/grouping drifts between every page that lists IDEs and CLIs. Codex is missing from most pages despite being supported.

---

## Issues to Address

### 1. Sitemap Coverage Gap **[MEDIUM]**
**File:** `websites/apps/marketing/src/app/sitemap.ts`

Sitemap lists 12 routes, ~20 additional pages exist and are not indexed:
`/about`, `/claude-code`, `/community`, `/compare` + 2 subpages, `/graph-enrichment`, `/immune-system`, `/integrations`, `/paperclip`, `/research`, `/support`.

**Action:** Add missing routes to sitemap or intentionally exclude with reason.

---

### 2. Changelog Dates Are Future-Dated **[HIGH]**
**File:** `websites/apps/marketing/src/app/changelog/page.tsx:15-43`

Release dates listed as "Early March 2026", "Late Feb 2026" but current date is May 2026.

**Action:** Update dates to match actual release history or restructure as "Upcoming" vs "Released".

---

### 3. Integrations Page Contains Internal TODO **[LOW]**
**File:** `websites/apps/marketing/src/app/integrations/page.tsx:3-8`

Comment reads: `TODO(MVP): Re-add the 'VS Code Extension' section once the native extension... is back in MVP scope`. Still ships in production source.

**Action:** Remove TODO once VS Code extension positioning decided.

---

### 4. Careers Page Contradictory Messaging **[MEDIUM]**
**File:** `websites/apps/marketing/src/app/careers/page.tsx:111-113`

Lists 3 open positions but contains explicit note: "We are not actively hiring at this exact moment".

**Action:** Either remove positions and say "Not hiring" OR remove the disclaimer and accept applications.

---

### 5. Contact Page Is Just a Redirect **[LOW]**
**File:** `websites/apps/marketing/src/app/contact/page.tsx:8-12`

Redirects to `mailto:support@sourceprep.io`. Still listed in sitemap as a real destination.

---

### 6. Privacy Content Location **[LOW]**
**File:** `websites/apps/marketing/src/app/security/page.tsx:215-308`

Privacy policy (sections 8-10) lives inside Security page. Verify `/privacy` page content; decide if merged Security+Privacy is intentional.

---

### 7. Dev-Only Page Accessible **[RESOLVED 2026-05-06]**
**File:** `websites/apps/marketing/src/app/dev/cli-demos/page.tsx`

Marked as "dev · not linked · not indexed" but publicly accessible. Resolution: added `marketing/src/app/dev/layout.tsx` that calls `notFound()` in production and applies `noindex` robots metadata. Local development still works.

---

### 8. Graph Enrichment Pipeline — Inaccurate "Sync is Instant" Claim **[RESOLVED 2026-05-06]**
**File:** `websites/apps/marketing/src/app/graph-enrichment/page.tsx:184`

Marketing page says: *"Sync... Completes in seconds with minimal LLM use."* But the listed Sync stages include:
- Stage 3 `CATALOGUE` — "Fast model catalogues every file with a one-line summary and tags" (LLM, every file)
- Stage 5 `KNOWLEDGE` — "First LLM pass. Enriches key nodes with semantic descriptions and builds the search index." (LLM)

Two LLM-bound stages over the entire repo cannot be characterized as "seconds with minimal LLM use" — that's the longest part of any cold sync on a non-trivial codebase. Stage 1 (STRUCTURAL) and 2/4 are the genuinely fast parts.

**Resolution (Option B applied 2026-05-06):**
- Each Sync stage card now carries a `Rust` / `LLM` / `Embedding` compute badge that mirrors `STAGE_QUEUE_TYPE` in `src/prep/services/pipeline/stages.py` (the source of truth).
- Code research uncovered two further inaccuracies that were also fixed:
  - Stage 2 (`INFERRED_EDGES`) was described as "git history co-occurrence" — it is actually an LLM stage finding cross-language API calls, dynamic dispatch, interface satisfaction, and implicit dependencies (`inferred_edges.py:1-21`). Git co-occurrence is a separate offline helper (`inferred_edges.py:880+`), not Stage 2.
  - Stage 5 (`KNOWLEDGE`) was described as "first LLM pass" — it is actually embedding-only (`STAGE_TASK_ID[KNOWLEDGE] = None`, `QueueType.EMBEDDING`).
- Sync section header copy rewritten to honestly split "Rust — instant" from "LLM — minutes" from "Embedding — seconds–minutes". Journey card relabeled "Sync — Structure first."
- Trimmed redundant prose in The Journey section.

---

### 9. Two Conflicting Graph Enrichment Articles — Structural Problem, Not Just Stale Copy **[RESOLVED 2026-05-07]**

Two public pages describe graph enrichment:

| URL | File | Purpose problem |
|-----|------|-----------------|
| `https://sourceprep.io/graph-enrichment` | `websites/apps/marketing/src/app/graph-enrichment/page.tsx` | Current after Issue 8 fix |
| `https://docs.sourceprep.io/concepts/graph-enrichment` | `websites/apps/docs/src/app/concepts/graph-enrichment/page.tsx` | Stale 9-stage pipeline AND structurally misplaced — it's an informative concept page, not a how-to-use page |

The duplication is not "marketing has the headline, docs has the deep version" — both pages tell the same conceptual story. The docs page just has more depth on epistemology / decay / research foundations. None of that is operator-grade; it's all about understanding the product.

**Per durable instruction (memory: `feedback_marketing_vs_docs_split.md`):** marketing = WHAT/WHY, docs = HOW-TO. Concept content belongs in marketing.

**Resolved 2026-05-07 (reframed direction):** The docs concept page is the canonical home, NOT marketing. (Per user direction: "I don't want docs links to be linking back to the marketing site.")

Applied changes:
- `websites/apps/docs/src/app/concepts/graph-enrichment/page.tsx` rewritten with the marketing-page sectioned layout (sticky anchor nav, stage cards, dividers) AND all 15 stages (Sync 1–5 / Enrich 6–10 / Finalize 11–15). Preserved the docs-side depth: Understanding Score, Score Decay table, Documentation Mining, Why It Matters, Research Foundation.
- Top-of-page back-link is **referrer-aware** — if the user came from sourceprep.io it shows "← Back to sourceprep.io"; otherwise defaults to "← Back to Docs".
- `websites/apps/marketing/src/app/graph-enrichment/` deleted entirely (page + layout). Replaced with a server-side redirect in `marketing/next.config.js`: `/graph-enrichment → https://docs.sourceprep.io/concepts/graph-enrichment`.
- `packages/ui/src/components/marketing/FeatureBlocks.tsx` Graph Enrichment entry: badge fixed `'Pro' → 'Built-in'` (per `feature_gate.py:64` `auto_deep_enrichment: Tier.FREE`); `href` repointed to docs.

Two adjacent fixes piggybacked:
- Pure-hub pages `/concepts` and `/guides` (just menu duplicates of the sidebar) deleted; sidebar headers for these sections become non-clickable text. `next.config.js` redirects `/concepts → /concepts/indexing` and `/guides → /guides/embeddings` so direct URL hits land somewhere sensible.
- `DocsSidebarNav.tsx` now renders section headers as clickable links when `section.href` is set — fixes the "discovery-poor hub" UX for the four kept hubs (`/getting-started`, `/cli`, `/dashboard`, `/mcp`). Removed `href` from the deleted Concepts and Guides sections so their headers stay plain text.
- All `← Back to Concepts` / `← Back to Guides` back-links in concept and guide sub-pages repointed to `← Back to Docs` (`href="/"`).

Step C (apply same marketing-style layout to `/concepts/indexing`, `/concepts/code-graph`, `/concepts/context`) is the natural follow-up — substantive content rewriting per page, deferred to focused passes.

---

### 10. Integration Naming and Grouping Is Inconsistent Everywhere **[RESOLVED 2026-05-06]**

Different pages list IDE/CLI integrations in different orders, with different sets, using different categorization. Examples:

| Surface | What's listed | Issue |
|---------|--------------|-------|
| `marketing/.../page.tsx:39` (home, paragraph) | "Claude Code, Antigravity, Cursor, VS Code" | Mixes CLI + IDE; no grouping; missing Codex; missing Windsurf |
| `marketing/.../page.tsx:66` (home, second mention) | "Claude Code, Antigravity, Cursor" | Different selection from line 39 above |
| `marketing/.../page.tsx:128-137` (home, integrations grid) | Claude Code, Cursor, Windsurf, VS Code, GitHub Copilot, Gemini CLI, Paperclip, "See all" | Mixes IDE + CLI; no Codex; no Antigravity |
| `marketing/.../integrations/page.tsx:20-25` (CLI list) | Claude Code, Gemini CLI, Qwen Code, "Any MCP CLI" | **Missing Codex** |
| `marketing/.../integrations/page.tsx:27-32` (IDE list) | Cursor, Antigravity, Windsurf, VS Code | No Zed, no Cline, no JetBrains |
| `marketing/.../integrations/page.tsx:156-160` (Client-aware) | Claude Code, Cursor, Windsurf | Inconsistent with IDE/CLI lists above |
| `marketing/.../faq/page.tsx:97,124` | "Cursor, Windsurf, Antigravity" / "Claude Code" | No Codex |
| `marketing/.../setup/page.tsx:42-183` | 10 entries — all of: Claude Code, Cursor, Windsurf, GitHub Copilot, Gemini CLI, Antigravity, Claude Desktop (mislabeled as "Claude Code"), Zed, Cline, OpenAI Codex | Most complete; **bug — duplicate `name: 'Claude Code'` for Claude Desktop entry at line 132** |
| `marketing/.../about/page.tsx:113` | "Cursor, Windsurf, VS Code, and Claude Code" | No Codex |
| `marketing/.../claude-code/page.tsx:194-197` | Cursor, Windsurf, VS Code | No Codex |
| `docs/.../mcp/page.tsx:26,36` | IDEs: "Cursor, Windsurf, Copilot, and Zed" / Terminals: "Claude Code and Gemini CLI" | No Codex, no Antigravity |
| `docs/.../mcp/terminal/page.tsx:23` | "like Claude Code" | No Codex (though backing data has it) |
| `docs/src/config/mcp-setup.ts` | 10 entries, includes `openai-codex` (terminal) and `antigravity` (ide) | Source of truth — most complete |
| `src/prep/core/rules_generator.py` | cursor, windsurf, claude, gemini, copilot, cline, roo_code | No Codex; no Antigravity rules file generated |

**Per user direction (2026-05-06):** Marketing copy should follow a clean, consistent taxonomy:

#### Proposed canonical taxonomy

**Primary CLI agent:** Claude Code (deepest integration, primary target).

**Other CLI agents (group, when listing more than one):**
1. Claude Code *(primary)*
2. OpenAI Codex
3. Gemini CLI
4. Qwen Code
5. *(other MCP-aware CLIs as a group: Aider, Amp, Zed terminal, etc.)*

**Primary IDE:** Cursor.

**Other IDEs (group):**
1. Cursor *(primary)*
2. Windsurf (Codeium)
3. Antigravity (Google)
4. VS Code + GitHub Copilot
5. Zed
6. JetBrains *(future / via plugin)*

**Power-user IDEs (mention once, in a meaningful place — likely setup/integrations long-tail or docs):**
- Cline, Roo Code, CodeGPT — bundled as a "AI coding extensions inside VS Code" footnote.

#### Three approved phrasings

When marketing copy needs to mention integrations, pick ONE of these patterns:

1. **Headline / hero (short list, two each):** "Claude Code, Codex, Cursor, Windsurf — and any other MCP-aware tool."
2. **Section copy (CLI-first or IDE-first context):**
   - CLI context → "Claude Code is the primary target; Codex, Gemini CLI, and Qwen Code use the same MCP server."
   - IDE context → "Cursor is the primary target; Windsurf, Antigravity, and VS Code (via GitHub Copilot) all speak MCP."
3. **Comprehensive list (setup pages, integrations long-tail):** Group cleanly as "CLI Agents" and "IDEs", in the order above. Cline / Roo / CodeGPT appear once as a VS Code-extension cluster.

#### Forbidden patterns

- Mixed CLI + IDE in a single comma list with no grouping ("Claude Code, Antigravity, Cursor, VS Code").
- Listing Antigravity or Windsurf without Cursor present.
- Omitting Codex from any "comprehensive" list.
- Using "Claude Code" as the name for the Claude Desktop config entry (see Issue 11).

**Resolution applied 2026-05-06:**
- `marketing/integrations/page.tsx` — `CLI_AGENTS` now leads with Claude Code (primary), then OpenAI Codex, Gemini CLI, Qwen Code, "Any MCP CLI". `IDES` reordered to Cursor (primary), Windsurf, Antigravity, VS Code + Copilot, Zed, "VS Code extensions" (Cline/Roo/CodeGPT). Client-Aware section adds a 4th card for Codex. Prose paragraphs reference the canonical taxonomy.
- `marketing/page.tsx` — integration grid restructured: 3 CLIs (Claude Code, Codex, Gemini CLI) + 3 IDEs (Cursor, Windsurf, VS Code+Copilot) + Paperclip + "See all". Combined former separate VS Code and GitHub Copilot cards (they were the same integration). SEO sr-only paragraph and Live Demos intro reworded with "Claude Code, Codex, Cursor, Windsurf — and any other MCP-aware tool" headline phrasing. Hero left untouched.
- `marketing/faq/page.tsx` — Q97 reworded to "Cursor, Windsurf, Antigravity / Claude Code, Codex". Editor portability row updated. Q318 "Which editors does it work with?" rewritten to list CLIs and IDEs in the canonical order.
- `marketing/about/page.tsx` — "works with everything" callout updated.
- `marketing/claude-code/page.tsx` — Other Clients list adds Codex.
- `docs/mcp/page.tsx` — IDE/CLI navigation cards rewritten ("Terminal Agents" → "CLI Agents"; full canonical list mentioned in each card).
- `docs/mcp/terminal/page.tsx` — title "Terminal Agents" → "CLI Agents"; subtitle and intro now mention Claude Code, Codex, Gemini CLI explicitly.
- `docs/mcp/ides/page.tsx` — subtitle now lists Cursor (primary), Windsurf, Antigravity, VS Code+Copilot, Zed, plus VS Code extension cluster.

**Out of scope follow-up:** `src/prep/core/rules_generator.py` should emit a Codex AGENTS.md target (Codex reads AGENTS.md natively). Tracked separately as product backlog.

---

### 11. Setup Page Had a Spurious Claude Desktop Entry **[RESOLVED 2026-05-06]**
**File:** `websites/apps/marketing/src/app/setup/page.tsx`

Setup page had two `name: 'Claude Code'` entries — one was actually Claude Desktop (`claude_desktop_config.json`, `~/Library/Application Support/Claude/`). Resolution: Claude Code is the headline product, Claude Desktop is a footnote because the same JSON works. Removed the standalone Claude Desktop card; folded a one-line "same JSON works for Claude Desktop — see ~/Library/Application Support/Claude/ etc." into the Claude Code entry's notes. Docs site config (`docs/src/config/mcp-setup.ts`) never included Claude Desktop — no follow-up needed there.

---

### 12. Public Docs Site Likely Broadly Stale **[MEDIUM]** *(new 2026-05-06)*

The 9-stage-vs-15-stage gap on `/concepts/graph-enrichment` strongly suggests other docs pages are similarly out of date relative to product reality. User flag: "the whole public-facing docs are a bit old."

**Action:** Spawn a separate audit pass over `websites/apps/docs/src/app/**`. Track findings in this same document (new section per page). Suggested priority order: `concepts/`, `mcp/`, `guides/`, `cli/`. Compare each against current source-of-truth (pipeline stages, MCP tool list in `src/prep/mcp_tools.py`, CLI commands in `src/prep/cli.py`, dashboard panels).

---

### 14. Cross-App Streamline — Inventory + Purpose Classification **[HIGH]** *(inventory completed 2026-05-06)*

Total: **27 marketing pages + 37 docs pages + 4 support pages + 3 payments pages = 71 user-facing pages.** Inventoried by reading each. Per durable split (memory: `feedback_marketing_vs_docs_split.md`): marketing = WHAT/WHY, docs = HOW-TO, support = problems, payments = checkout.

**Legend:** ✅ correct app · ⚠ misplaced or duplicated · 🪦 dead/redirect-only · 🔧 content fix needed (tracked elsewhere).

#### Marketing (`websites/apps/marketing/src/app/`)

| Route | Verdict | Notes |
|-------|---------|-------|
| `/` | ✅ | Home. Hero off-limits per durable instruction. |
| `/about` | ✅ | Company / positioning. |
| `/pricing` | ✅ | PPP-aware pricing cards. |
| `/blog` | ✅ | Index page; posts come from `config/blog.ts`. |
| `/research` | ✅ | Research-flavoured value page. |
| `/immune-system` | ✅ | Concept page. Same shape as `/graph-enrichment`. |
| `/graph-enrichment` | ✅ | Concept page. Issue 8 fixed. |
| `/paperclip` | ✅ | Integration story page. |
| `/claude-code` | ✅ | Primary-CLI deep-dive. |
| `/integrations` | ✅ | IDE/CLI grid (Issue 10 will rewrite contents, page itself is fine). |
| `/compare`, `/compare/prep-vs-cursor-indexing`, `/compare/prep-vs-greptile` | ✅ | Competitive matrix + 1:1 comparisons. |
| `/community` | ✅ | Discord/GitHub recruitment. |
| `/faq` | ✅ | Buyer-facing FAQ. Overlaps docs `/faq` — see Cross-Cutting #2. |
| `/security` | ✅ | Security posture; absorbs Privacy too (Issue 6). |
| `/terms` | ✅ | Legal. |
| `/careers` | ✅ | Job listings (content fix in Issue 4). |
| `/changelog` | ✅ | Release notes (date fix in Issue 2). |
| `/setup` | ⚠ | **HOW-TO content in marketing.** 10 copy-paste MCP configs; same data fed to docs `/mcp/ides` + `/mcp/terminal` from `docs/src/config/mcp-setup.ts`. Cross-Cutting #1. |
| `/download` | ⚠ | **Also has MCP_CONFIGS** (lines ~10–80). Triple-source for the same JSON. Should be "where to get the binary" only. |
| `/support` | ⚠ | Just links out to `docs.sourceprep.io` + `support.sourceprep.io`. Redundant with the support.sourceprep.io property itself. |
| `/privacy` | 🪦 | Single redirect to `/security#data-collection`. Replace with a Next.js redirect at the routing layer. |
| `/contact` | 🪦 | Single redirect to `mailto:`. Replace with a Next.js redirect; footer can mailto: directly. |
| `/dev/cli-demos` | 🪦 | "dev · not linked · not indexed" but publicly accessible. Move out of `/app` or auth-gate (Issue 7). |
| `/dev/cli-demos2` | 🪦 | A/B variant of cli-demos. Drop. |
| `/rss` (route.ts) | ✅ | RSS feed. Keep. |

#### Docs (`websites/apps/docs/src/app/`)

| Route | Verdict | Notes |
|-------|---------|-------|
| `/` | ✅ | Docs nav hub. |
| `/getting-started`, `/getting-started/installation`, `/getting-started/quick-start` | ✅ | Install + first-run how-to. |
| `/cli`, `/cli/commands`, `/cli/config` | ✅ | CLI reference. |
| `/mcp` | ✅ | MCP overview (Issue 10 will sweep prose). |
| `/mcp/ides`, `/mcp/terminal`, `/mcp/paperclip` | ✅ | Per-host setup. Overlaps marketing `/setup` — Cross-Cutting #1. |
| `/dashboard`, `/dashboard/projects` | ✅ | UI walkthrough. Operator-facing. |
| `/troubleshooting` | ✅ | Problem-solving. |
| `/search` | ✅ | Site search UI. |
| `/faq` | ⚠ | Overlaps marketing `/faq`. Cross-Cutting #2. |
| `/concepts` (hub) | ⚠ | Lists 4 concept pages — all misplaced. |
| `/concepts/code-graph` | ⚠ | Informative explainer. Move to marketing or delete. |
| `/concepts/context` | ⚠ | Informative explainer. Move to marketing or delete. |
| `/concepts/indexing` | ⚠ | Informative explainer (Vector Indexing). Move or delete. |
| `/concepts/graph-enrichment` | ⚠ | Stale 9-stage duplicate (Issue 9). Delete or stub. |
| `/guides` (hub) | ✅ | Index of 16 how-to guides. |
| `/guides/embeddings` | ✅ | Real how-to. |
| `/guides/models` | ✅ | Real how-to (has TODO about model refresh — content fix). |
| `/guides/model-advisor` | ✅ | Operator-facing model picker. |
| `/guides/dynamic-model-loading` | ✅ | Real how-to. |
| `/guides/byok-batching` | ✅ | Real how-to. |
| `/guides/path-weights` | ✅ | Real how-to. |
| `/guides/knowledge-scope` | ✅ | Real how-to. |
| `/guides/smart-search` | ✅ | Real how-to. |
| `/guides/audit-enrichment` | ✅ | Real how-to. |
| `/guides/codebase-audit` | ✅ | Real how-to. |
| `/guides/team-sync` | ✅ | Real how-to (Team/Enterprise). |
| `/guides/enterprise-deploy` | ✅ | Real how-to (Enterprise). |
| `/guides/concurrency-discovery` | ✅ | Real how-to. |
| `/guides/compression` | ✅ | Real how-to. |
| `/guides/clara` | 🪦 | Single-line `redirect('/guides/compression')`. Replace with Next.js redirect. |

#### Support (`websites/apps/support/src/app/`)

| Route | Verdict | Notes |
|-------|---------|-------|
| `/` | ✅ | Support hub. Pulls live GitHub Discussions. |
| `/admin` | ✅ | Redirect to `/admin/reports`. Internal-only routing helper. |
| `/admin/reports`, `/admin/reports/[id]` | ✅ | Bug triage admin. Keep. |
| `api/*` (4 routes) | ✅ | Bug-report ingestion + metrics. Keep. |

#### Payments (`websites/apps/payments/src/app/`)

| Route | Verdict | Notes |
|-------|---------|-------|
| `/` | ✅ | Checkout cards. |
| `/recover` | ✅ | License recovery form. |
| `/success` | ✅ | Post-purchase. |
| `api/recover` | ✅ | Recovery endpoint. |

#### Cross-Cutting Findings

1. **MCP config triple-source.** `marketing/setup/page.tsx` defines 10 configs inline; `marketing/download/page.tsx` defines a separate `MCP_CONFIGS` array; `docs/src/config/mcp-setup.ts` is the registry that powers `docs/mcp/ides` + `docs/mcp/terminal`. Three places, three slightly different shapes (and Issue 11 caught a duplicate-name bug in the marketing copy). Resolution: docs registry becomes the single source of truth; marketing `/setup` either disappears (replaced by a "Setup → docs" call-out card on `/download`) or is reduced to a one-screen marketing summary that links to docs/mcp for the actual JSON.

2. **Two FAQ pages.** Marketing `/faq` and docs `/faq` exist with different content. Marketing FAQ is buyer-oriented (price, privacy, model recommendations); docs FAQ is mostly cloud-upload reassurance. Since the boundary is genuinely real (buyer Qs vs operator Qs), keep both — but audit each so questions live in the right one (operator Qs in marketing FAQ should move to docs FAQ or troubleshooting; vice versa).

3. **Concept content stranded in docs.** Five docs pages are conceptual not instructional: `/concepts` (hub), `/concepts/code-graph`, `/concepts/context`, `/concepts/indexing`, `/concepts/graph-enrichment`. Issue 9 already proposed deleting `/concepts/graph-enrichment`; same logic applies to the rest. *But see reverse-engineering pass below — the operator-grade payload inside these pages should not be lost.*

4. **Three pages are bare redirects** (`marketing/privacy`, `marketing/contact`, `docs/guides/clara`). Each is a React component that does one redirect; replace with Next.js `redirects` config or `next.config.js` rewrites. Saves bundle weight and removes the "page exists but is empty" failure mode.

5. **`marketing/dev/*` is leaking internal pages.** `/dev/cli-demos` and `/dev/cli-demos2` are dev-only A/B test surfaces. They're indexable. Move out of `/app` or auth-gate; delete `cli-demos2` outright (it's a variant of cli-demos).

6. **`marketing/support` is redundant with the `support.sourceprep.io` property** itself. The page is mostly outbound links to docs and the support subdomain. Replace with a redirect.

#### Reverse-Engineering Pass — What Would We Lose?

For each proposed change, asking "does this delete content the user actually needs, and what's the minimum-loss alternative?"

| Proposed change | What we'd lose | How to preserve |
|-----------------|----------------|-----------------|
| Delete `marketing/privacy` page | Direct `/privacy` URL discoverability | Next.js redirect `/privacy → /security#data-collection`. URL still works. |
| Delete `marketing/contact` page | Direct `/contact` URL | Next.js redirect `/contact → mailto:support@…` or `/support`. |
| Delete `marketing/support` page | Anchor for "Support" links in nav/footer | Redirect to `support.sourceprep.io`. |
| Delete `docs/guides/clara` | None — it's a one-line redirect | `next.config.js` redirect. |
| Move `marketing/setup` content into `docs/mcp` | Marketing-tier SEO + JSON-LD HowTo schema; hand-authored marketing copy framing | Keep a slim `/setup` page on marketing as a one-screen "you've got this" summary that links to docs/mcp for the per-tool blocks. JSON-LD HowTo can live on the docs page. |
| Strip `MCP_CONFIGS` from `marketing/download` | Visual "look how easy it is" near the binary | Replace with a single example config + "see /setup for all 10 tools." |
| Delete `docs/concepts/graph-enrichment` | The deep epistemology / decay table / research-foundation prose | **Preserve into marketing.** Two options: (a) extend `marketing/graph-enrichment` with an expandable "Foundations" section; (b) create `marketing/research/graph-enrichment-foundations` (cleaner — `/research` already hosts research-flavoured content). Recommend (b). |
| Delete `docs/concepts/code-graph` | Explainer of Rust engine + node/edge model | **Preserve.** Most of this content already exists in scattered form on marketing (`/graph-enrichment` Stage 1; `/research`). One additional research-flavoured page or an expandable section on `/graph-enrichment` covers it. |
| Delete `docs/concepts/context` | Context-assembly explainer (retrieval → trace expansion → LOD compression) | **Preserve.** This is essentially the differentiator narrative — strong fit for a marketing concept page. Recommend new `marketing/context-assembly` (matches the `/graph-enrichment` and `/immune-system` siblings). |
| Delete `docs/concepts/indexing` | Vector indexing explainer + Rust walker mention | **Partially preserve.** Operator-facing slice (BLAKE3 hashing, .gitignore handling, file watcher) belongs in `docs/getting-started` or a new `docs/guides/indexing-internals`. The conceptual half merges into the marketing `/graph-enrichment` Stage 1 + 5 cards. |
| Delete `docs/concepts` hub | Nav landing for the 4 concept pages | If all 4 children move/delete, the hub goes too. |
| Delete `marketing/dev/cli-demos2` | Internal A/B copy | Snapshot to gist or delete; no public loss. |
| Auth-gate `marketing/dev/cli-demos` | None public | Move to a separate Storybook story or behind a `NODE_ENV` check. |

**Net effect on user-visible pages, if all proposals applied:**
- marketing: 27 → ~22 (delete privacy, contact, support, dev/cli-demos2; reduce dev/cli-demos to non-public; possibly drop /setup if folded into /download). Add 1–2 new concept pages absorbing docs content (`/context-assembly`, `/research/graph-enrichment-foundations`). Net ~22.
- docs: 37 → ~32 (delete 5 concept pages, delete clara redirect, delete one or two redundant FAQs depending on Cross-Cutting #2 outcome). Add ~1 concept-aware operator page (`/guides/indexing-internals`). Net ~33.
- support: unchanged (4).
- payments: unchanged (3).

**Total: 71 → ~62 user-facing pages, with no concept content lost — only relocated to its right home.**

#### Proposed Target Structure (the streamlined target)

**marketing** = WHAT/WHY:
- Home, About, Pricing, Blog, FAQ (buyer Qs), Compare/*, Community, Careers, Changelog, Security (+ embedded Privacy), Terms, Research, RSS.
- **Concept pages** (the differentiator surface): `/graph-enrichment`, `/immune-system`, `/context-assembly` (new), optionally `/research/graph-enrichment-foundations` (new, absorbs docs/concepts/graph-enrichment depth).
- **Integration pages**: `/integrations`, `/claude-code`, `/paperclip`, plus a slim `/setup` summary (or fold into `/download`).

**docs** = HOW-TO:
- Home, Getting Started (+ install + quick start), CLI (+ commands + config), MCP (+ ides + terminal + paperclip — single source of truth for IDE configs), Dashboard (+ projects), Troubleshooting, Search, FAQ (operator Qs), Guides/* (16 guides + maybe new `indexing-internals`).
- **No `/concepts/*`.** That tree disappears.

**support**, **payments** = unchanged.

#### Action — User Decisions (2026-05-06)

| Finding | Decision |
|---------|----------|
| 1. MCP setup triple-source | **Resolved 2026-05-06.** Canonical registry created at `packages/ui/src/config/mcpSetup.ts`, exported from `@prep/ui`. Consumers updated: `marketing/setup`, `marketing/download`, `docs/src/config/mcp-setup.ts` (now a thin re-export), `docs/mcp/ides`, `docs/mcp/terminal`. All surfaces now read from one source. JSON-LD HowTo schema preserved on `/setup` for AI/SEO discoverability. New `category: 'cli' \| 'ide'` and `primary?: boolean` fields drive the integration taxonomy from Issue 10. |
| 2. Two FAQs | **Resolved 2026-05-06.** Corrected per user direction: there should be no docs FAQ at all. Intended structure is marketing landing page (small teaser FAQ snippet, not yet present) + marketing `/faq` (comprehensive, already exists). Deleted `docs/src/app/faq/` entirely. Docs sidebar already correctly pointed FAQ link to `${MARKETING_URL}/faq`. Removed `/faq` from docs sitemap. **Follow-up resolved 2026-05-06:** added "Got questions? Read the FAQ →" link in the trust-strip / CTA section of the landing page (below hero, not in hero). No FAQ snippet on the landing page — just the link, per user direction. |
| 3. Concepts in docs | **Deferred.** Reframe: concept content in docs is fine if it makes sense. Re-evaluate during a focused reorganization session later. Continue to take notes. |
| 4. Bare redirects | **Greenlit.** Replace React-component redirects with `next.config.js` server-side redirects (instant, no flash, better SEO). Applies to `marketing/privacy`, `marketing/contact`, `docs/guides/clara`. |
| 5. `dev/cli-demos*` | **Resolution 2026-05-06:** Storybook does NOT currently mirror `dev/cli-demos/variants.ts` (1888 lines of A/B candidates feeding manual curation into `packages/ui/.../demo-scripts.ts`). Applied Option C: added `marketing/src/app/dev/layout.tsx` that calls `notFound()` in production and `noindex` robots metadata. Local `npm run dev` still works for curation. Future improvement: migrate the variant catalog into Storybook stories so dev page can be deleted entirely. |
| 6. `marketing/support` | **Deferred.** Subdomain may not be launched; investigate after confirming the support site is fully integrated. |

#### Bonus finding from FAQ cleanup (2026-05-06)

The docs sitemap (`websites/apps/docs/src/app/sitemap.ts`) contains stale entries for routes that don't exist (`/mcp/cursor`, `/mcp/windsurf`, `/concepts/trace-index`, `/dashboard/settings`) and is missing real entries (most `/guides/*` subroutes). Tracked under Issue 12 (full docs staleness pass).

#### Reframed Concept-in-Docs Note (Finding 3, deferred)

Per durable instruction (memory: `feedback_marketing_vs_docs_split.md`, updated 2026-05-06): concept content **can** live in docs if it serves operators directly. The rule isn't "no concepts in docs" — it's "if the same concept appears in multiple places, populate from a single source." Duplication-by-drift is the failure mode, not duplication itself. The `docs/concepts/*` pages are not blocked from existing; they need a thoughtful pass to decide which serve operators (keep, anchor to source) and which are pure marketing-in-disguise (move/delete). Defer to a focused session.

#### Execution Order (greenlit only)

1. **Bare-redirect cleanup** (Finding 4) — `next.config.js` redirects for `marketing/privacy`, `marketing/contact`, `docs/guides/clara`. Delete the React stubs.
2. **`dev/cli-demos*` cleanup** (Finding 5) — verify Storybook coverage; if confirmed, delete both public pages.
3. **MCP single-source-of-truth** (Finding 1) — extract a shared registry that feeds `marketing/setup`, `marketing/download`, `docs/mcp/ides`, `docs/mcp/terminal`. AI/SEO-friendly — JSON-LD on at least one surface.
4. **FAQ alignment** (Finding 2) — pick which is the small/teaser version, audit Q placement, link teaser → full.

Findings 3 and 6 deferred for later focused work.

---

### 13. SourcePrep Atlas Output Contains Apparent Prompt Injection **[HIGH — product bug]** *(new 2026-05-06, dogfooding finding)*

Calling `prep` on this repo today returned an atlas whose role-projection block contained:
1. A meta-instruction to the LLM ("I need to write a concise project orientation header based on the provided data, following strict rules: plain text only, no markdown, no bold...").
2. A long string of repeated `加油` Chinese characters (likely a token-bomb injection).

This is in the live atlas this repo serves to its own MCP clients. Not a marketing site issue, but discovered during marketing audit work. Cross-filing as a product bug — likely a poisoned concept entry, a stuck atlas cache, or a compromised generation prompt.

**Action:**
- File a separate ticket against the atlas / role-projection subsystem.
- Inspect `prep_concepts` for entries containing the meta-instruction text or the 加油 string.
- Inspect the atlas regeneration cache; consider purging and rebuilding.
- This is a dogfooding-grade finding — exactly the kind of thing the CLAUDE.md "critically evaluate SourcePrep results" guidance asks us to flag.

---

## Notes / Cross-Cutting

- Model names in FAQ are accurate (GPT-5.5, Claude variants, Gemini 3.1 Pro, Qwen3-Coder-480B).
- Centralized "Recommended Models" doc still proposed but not created. See suggestion below.
- Per durable instruction (memory: `feedback_do_not_touch_hero.md`), the home-page hero/tagline is off-limits for autonomous edits — flag suggestions but wait for explicit go-ahead.

---

## Centralized Model Recommendations

**Suggestion:** Create `docs/AI_MODEL_RECOMMENDATIONS.md` as the single source of truth that both marketing copy and technical docs reference.

**Current models referenced in FAQ:**
- GPT-5.5
- Claude Sonnet 4.6
- Claude Opus 4.7
- Gemini 3.1 Pro
- Qwen3-Coder-480B

---

## Completed Actions

| Date | Action | File |
|------|--------|------|
| 2026-05-03 | Commented out links to `/graph-enrichment` and `/immune-system` from main page | `page.tsx:173-191` |
| 2026-05-06 | Audit refresh — added issues 8–13 (graph-enrichment accuracy, integration naming taxonomy, Codex, Claude Desktop mislabel, doc staleness, atlas injection) | this file |
