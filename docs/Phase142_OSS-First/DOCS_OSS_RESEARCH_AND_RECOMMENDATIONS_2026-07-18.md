# Docs-Site Held-Items Research + Recommendations — 2026-07-18

> **Status:** Second-pass research report. Companion to
> `DOCS_OSS_READINESS_AUDIT_2026-07-18.md` (the first pass). This doc deep-researched
> every "held for Eric" item from the first pass against the live repo, ran an
> adversarial blind-spots panel, and **corrects several first-pass errors**.
>
> **Method:** 16-agent workflow (10 deep-research agents over the held items +
> 5 blind-spots agents → 1 synthesizer), then a main-loop verification pass.
> ~1M tokens, 406 tool calls. Sources cited inline as `file:line` or URL.
>
> **What changed since the first pass:** 16 additional safe-now fixes applied
> (pass 2) + 1 first-pass fix reverted (M5). The first-pass audit's treatment of
> 4 items was **wrong** and is corrected below (§2). 13 items remain Eric-gated
> (§3), each with one recommended option.

---

## 0. TL;DR

The first pass was directionally right but had real defects that the second pass
caught by verifying against code instead of memory:

- **The "legacy pages" framing was inverted.** dynamic-model-loading was
  *restored* on 2026-05-14 (not hidden), and byok-batching is actively wired
  through the live pipeline. The first pass's "remove from nav" option is
  **rejected** — it contradicts Eric's own strategy. Both pages stay.
- **The Ollama slug `manutic/nomic-embed-code` is correct.** WebFetch verified it
  is the canonical community slug (6,979 downloads); `nomic-ai/` does not publish
  it to Ollama. The first pass's "likely a typo" speculation was wrong. The
  **dashboard** (`AIModelsSettings.tsx:103`) is what's wrong (uses the
  namespace-less `nomic-embed-code` that 404s) — that's an Eric-gated code fix.
- **The phone-home cluster is a real falsehood, not "already fine."** Docs
  `enterprise-deploy:247` makes a *stronger* present-tense claim than marketing
  hedges. It must be hedged (Eric-gated, coordinated with the license-crypto
  replacement).
- **The first-pass M5 fix was reverted.** Research verified the headless
  indexer (`team_config`) IS hard-gated to Team/Enterprise in code
  (`feature_gate.py:60`). Removing the "Requires Team/Enterprise license" line
  preempted Eric's ungate decision — the same error as asserting Apache-2.0
  before the relicense. Line restored.

The docs site is materially more accurate after pass 2 but still **not
OSS-shippable** — it depends on Eric's decisions in §3, and (gating everything)
the actual Apache-2.0+DCO relicense application + the `build_public_mirror.py`
storefront tool.

---

## 1. Pass-2 fixes APPLIED (16 safe-now + 1 revert), commit pending

| # | File:line | Fix | Source |
|---|---|---|---|
| P1 | `mcp/paperclip/page.tsx:278` | "It's MIT-licensed." → "See the repository LICENSE for licensing details." (license-neutral; true regardless of relicense state) | L1-interim |
| P2 | `how-it-works/compression/page.tsx:298` | Deleted false "built and available in the settings panel" callout (no BERT/language-compression feature exists in code; resolves the page's internal contradiction) | U2 |
| P3 | `troubleshooting/page.tsx:158` | Removed false "language compression loads a ~178 MB BERT model on demand" clause (0 BERT in code) | blind-spot |
| P4 | `guides/knowledge-scope/page.tsx:100` | Dropped false "Pro-tier" qualifier (auto-rebuild is gated at `Tier.FREE` in `feature_gate.py:52,65` — available to all) | U3 |
| P5 | `how-it-works/dynamic-model-loading/page.tsx:120` | Corrected the AdvancedLLMSettings caption (panel ships only cloud token-safety + max thinking budget; per-slot "Always Available" lives in the AI Gateway) | U4 |
| P6 | `how-it-works/embeddings/page.tsx:38` | "Requires a GPU." → "GPU strongly recommended." + CPU-fallback note (Ollama falls back to CPU; 7B is too slow for practical indexing) | U9 |
| P7 | `guides/models/page.tsx:150` | Same "Requires a GPU" softening | U9 |
| P8 | `cli/commands/page.tsx:99` | Expanded `--ide` list to all ten accepted values (cursor, windsurf, vscode, claude/claude-desktop, claude-code, jetbrains, gemini, antigravity, zed, all) | U12 |
| P9 | `cli/commands/page.tsx:34` | Fixed "prep add starts initial indexing" → "Run `prep build` to start the initial index" (cli.py:276-278 confirms it does NOT auto-build) | blind-spot |
| P10 | `cli/commands/page.tsx:69` | Added the missing `--role` flag | blind-spot |
| P11 | `cli/commands/page.tsx:101` | Added the missing `--daemon` flag (default `http://127.0.0.1:8400`) | blind-spot |
| P12 | `sitemap.ts:42` | Removed `/search` from the sitemap (client-side search-results pages should not be indexed) | blind-spot |
| P13 | `robots.ts` | Added `disallow: ['/search']` (mirrors marketing's pattern) | blind-spot |
| P14 | `public/storybook` | `git rm` the tracked symlink (served 8.7 MB Storybook at `/storybook/` including "Upgrade to Pro" / "Free tier" / "5 projects" UI — directly contradicts OSS; no docs page links to it; canonical storybook.sourceprep.io deploys via packages/ui/netlify.toml) | blind-spot |
| P15 | `public/opengraph-image.png` | Deleted orphan OG image (Apr 2, unreferenced, stale) | blind-spot |
| P16 | `public/images/og-image-dashboard.png` + `og-image.png` | Deleted two orphan OG images (Apr 2, unreferenced) | blind-spot |
| R1 | `guides/enterprise-deploy/page.tsx:24` | **Reverted first-pass M5** — restored "Requires a Team or Enterprise license." (the gate is real in code; removing it preempted Eric's ungate decision) | audit correction |

Docs app `tsc --noEmit` clean after all edits.

---

## 2. Audit corrections — where the first pass was wrong

### C1. U8 — the Ollama slug was NOT a typo (first pass was wrong)
**First-pass claim:** "`manutic` is not a known Ollama publisher; `ollama pull
manutic/nomic-embed-code` would 404; the canonical slug is `nomic-embed-code` or
`nomic-ai/nomic-embed-code`."
**Correction:** Wrong on both counts. `manutic/nomic-embed-code` IS a real,
popular public Ollama entry (WebFetch succeeded: 6,979 downloads, `:latest`
7.5 GB / `:7b` 14 GB, 32K context). `ollama.com/library/nomic-embed-code` returns
404 and `ollama.com/nomic-ai/nomic-embed-code` also 404s — nomic-ai has **not**
published nomic-embed-code to Ollama (only HuggingFace). The docs and
`embedder.py:64` are correct and consistent; Roo-Code PR #5688 adopted the same
community slug. The first pass would have sent Eric on a wild-goose chase.
**Evidence:** WebFetch https://ollama.com/manutic/nomic-embed-code (success);
WebFetch https://ollama.com/library/nomic-embed-code (404);
WebFetch https://ollama.com/nomic-ai/nomic-embed-code (404); `embedder.py:64`.

### C2. U4/U5/U6/U7 — the "legacy/hidden" framing was inverted (first pass was wrong)
**First-pass claim:** dynamic-model-loading and byok-batching pages are
"legacy/hidden" (per a 2026-05-14 memory note); offered "remove from nav +
sitemap" as an option.
**Correction:** Inverted. Eric's LLM-strategy memory says only `/guides/model-advisor`
was hidden on 2026-05-14; dynamic-model-loading was explicitly **restored**
that day ("keep for local-LLM users"). `Phase132_DocsBehavioralFidelity/00_progress_tracker.md:131`
confirms "🟢 visible 2026-05-14 | RESTORED." Byok-batching is actively wired
(`batch_profiles.py` imported into `cluster.py:1823`, `inferred_edges.py:247`,
`group_reasoning.py:576`, `concept_seeder.py:635`; `EndpointManager` rendered in
the live dashboard). The "remove from nav" option is **rejected** — it
contradicts Eric's own strategy and would orphan the docs link referenced from
`batch_profiles.py:12`. The one real defect (the wrong AdvancedLLMSettings
caption) was a safe-now fix (P5).
**Evidence:** `~/.claude/.../memory/project_llm_strategy.md`;
`docs/Phase132_DocsBehavioralFidelity/00_progress_tracker.md:131,39`;
`src/prep/core/batch_profiles.py:12`; `src/prep/dashboard/src/hooks/useDashboardPanels.tsx:688`.

### C3. §3 — the phone-home cluster was NOT "already fine" (first pass was wrong)
**First-pass claim:** "Docs already match marketing's no-phone-home stance;
the legacy lemon_squeezy.py polling code is the real cleanup item, not a docs
edit. Keep all four."
**Correction:** Wrong. Docs make a **stronger** present-tense claim than
marketing. `enterprise-deploy:247` "SourcePrep does not phone home, collect
usage data, or send any information to external servers" and `:252` "No
internet required after activation" are present-tense and **false today**
(`lemon_squeezy.py:43` `VALIDATION_INTERVAL_SECONDS = 7 days`;
`api/routers/license.py:214` "Called periodically (every 7 days)" with 30-day
downgrade; the poll sends `license_key`+`instance_id`+machine name to
`api.lemonsqueezy.com`). Marketing **hedges** (`security/page.tsx:142-148`:
"License infrastructure **will** exist only in the Pro installer ... the
current license crypto is being replaced before launch"). Docs is LESS hedged
than marketing, not matching it. The first pass let a real user-facing falsehood
stand. → Eric-gated hedge (§3 E5).
**Evidence:** `enterprise-deploy/page.tsx:247,252`;
`lemon_squeezy.py:43,78-83,149-156`; `api/routers/license.py:210-217`;
`marketing/src/app/security/page.tsx:142-148`.

### C4. The "docs should match marketing" principle was internally inconsistent
**First-pass claim:** Used "match marketing" to dismiss the phone-home cluster
(§3) while holding a more-conservative line than marketing on the license claim
(§1).
**Correction:** The principle is wrong. Marketing has already shipped premature
Apache-2.0 present-tense claims (`terms/page.tsx:100` "licensed under the Apache
License 2.0"; `page.tsx:36`; `changelog/page.tsx:22`) while the repo root
`LICENSE` is still proprietary. "Match marketing" cannot be the truth test when
marketing is itself forward-looking/false. Correct principle: **docs should be
at least as conservative as marketing on forward-looking claims; where
marketing has shipped a premature assertion, docs should NOT mirror it.** §1
follows this; §3 violated it.
**Evidence:** `marketing/src/app/terms/page.tsx:100`; `LICENSE:1` (proprietary).

### C5. §6 — the "already clean" evidence was overstated
**First-pass claim:** "0 codename leaks across the docs app."
**Correction:** Conclusion correct (no leak in production) but evidence
overstated. The `.next/` build cache contains `CoDRAG` in absolute dev-machine
paths (`.next/types/app/layout.ts:1`, `.next/server/next-font-manifest.json:1`,
`.next/cache/eslint/.cache_*`). Source files (`websites/apps/docs/src/`) are
genuinely clean. `.next/` is gitignored and rebuilt fresh on deploy, so no real
leak — but a reviewer running `grep -r codrag websites/apps/docs/` without a path
filter would draw the wrong conclusion. Tighten to "0 hits in
`websites/apps/docs/src/` and `public/` (source)."

### C6. §6 — the sidebar was NOT fully clean
**First-pass claim:** "all sidebar hrefs resolve to real routes."
**Correction:** Missed the **duplicate** `/guides/team-sync` entry:
`config/docs.ts:56` (Guides section, title "Team Sync") and `:64` (Deployment
section, title "Team Sync (CI/CD)") both reference the same route. Not a 404
but a redundancy. → Eric-gated (§3 E9).

### C7. The first pass missed three false-claim surfaces entirely
- `troubleshooting/page.tsx:158` "language compression loads a ~178 MB BERT
  model on demand" — false (0 BERT in code). Fixed as P3.
- `public/storybook` symlink shipping retired Free/Pro/Team tier UI ("Upgrade
  to Pro", "5 projects", "Free tier", "Upgrade to a Team plan") at `/storybook/`
  — directly contradicts OSS. Fixed as P14.
- Orphan `opengraph-image.png` + `public/images/og-image-dashboard.png` +
  `og-image.png` (all Apr 2 2026, unreferenced). Fixed as P15/P16.

---

## 3. Eric-gated recommendations (13 items, each with one recommended option)

### E1. [high] Paperclip final Apache-2.0 wording — *after* relicense + mirror allowlist
Apply "It is licensed under Apache-2.0 (with a Developer Certificate of Origin
sign-off requirement) — see the repository LICENSE for details." only once
(a) root LICENSE is relicensed to Apache-2.0+DCO AND (b) `tools/build_public_mirror.py`
is built and `packages/paperclip-plugin-prep` is confirmed in the storefront
allowlist (else the GitHub URL at line 275 404s at launch). The license-neutral
interim wording is already applied (P1).
**Recommended option:** Hold for both gates; apply the Apache wording at relicense time.

### E2. [high] SourcePrep-deploy links — populate the deploy repo via subtree push
7 dead links across `team-sync` + `enterprise-deploy` point at the empty
`MagneticAnomaly/SourcePrep-deploy` repo. Templates live at
`public/sourceprep-deploy/` locally. `git ls-remote deploy` returns zero refs.
**Recommended option (b):** run `scripts/publish_deploy_subtree.sh --promote` to
publish `public/sourceprep-deploy/` to the deploy remote. **Zero docs edits
needed** — all 7 links already point at the correct URL and resolve once it has
content. Aligns with `OPEN_CORE_SPLIT.md:71` (air-gapped deploy scripts are
Enterprise-only → must NOT go in the OSS storefront mirror, which rules out the
"repoint to flagship" option). Eric owns the publish timing (Phase 1 vs Phase 2).

### E3. [high] Team-sync guide — reframe as "coming soon," pull from sidebar
The tier clause at `team-sync/page.tsx:20` is **accurate to code** (not a stale
paywall — `team_config` is hard-gated to `Tier.TEAM` in `feature_gate.py:60`,
enforced at 5 sites). But the feature is not shippable at OSS launch: no Docker
image published (TEAMS_SYNC_REVIVE_PLAN Task 5 ⏳ Eric-run), Teams is Phase 2
"coming soon", Pro checkout itself unwired. A tier-clause drop alone leaves an
OSS user hitting a `cli.py:1408` license error + 404 on
`ghcr.io/magneticanomaly/prep-headless:cpu`.
**Recommended option (b):** replace the tier clause with a roadmap banner, gate
the Quick Start/Advanced/Enterprise/CLI sections behind "coming soon" framing,
and pull the page from `config/docs.ts`. Eric also owns the `team_config`
feature_gate decision (keep gated vs ungate for OSS).

### E4. Compression section final reframe
The "Coming Soon: Language Compression" heading + "A future Pro feature will add
... BERT model" paragraph remain (the false callout was removed in P2). BERT
dual-compressor was archived research (Phase 31, never implemented).
**Recommended option:** Relabel "Coming Soon" → "Roadmap", drop the "Pro
feature" framing (Pro is $29 one-time not-yet-live; OSS = full engine) and BERT
specificity — describe it as a research thread with no committed timeline.

### E5. [high] Phone-home hedge (coordinated with the license-crypto replacement)
Hedge `enterprise-deploy/page.tsx:247` and `:252` to mirror marketing's hedge.
**Recommended option:** Reframe as "Under OSS, no license calls. Paid-tier
license verification is being redesigned for offline Ed25519 verification (the
current license crypto is being replaced before launch — see the security
page)." Coordinate with the §3 code cleanup (remove the legacy
`lemon_squeezy.py` 7-day polling) so the claim becomes true.

### E6. BYOK privacy wording
`byok-batching/page.tsx:77` "No data is sent to SourcePrep servers" is narrowly
true for BYOK code/analysis data but reads as a blanket no-phone-home assurance.
**Recommended option:** Replace with "Your code and the generated analysis are
never sent to SourcePrep's servers. All BYOK API calls go directly from your
machine to the LLM provider you configured — SourcePrep is not in the path."

### E7. Docs home lede
`app/page.tsx:63` "Everything you need to build your epistemic graph" leads with
a coined jargon term. Eric's `feedback_marketing_voice` memory names
"epistemic" as jargon to demote.
**Recommended option:** "Everything you need to install SourcePrep, connect it
to your AI tools, and get better output from every prompt — a structural map of
your codebase that every agent can share." (Optionally append "(SourcePrep
calls this map your epistemic graph.)" to keep the term for returning readers.)
The do-not-touch-hero rule does not apply (this is the docs home, not the
marketing hero), but Eric's approval is warranted on a high-visibility surface.

### E8. Model-advisor orphan route
`/guides/model-advisor` exists (200-line interactive page) but is NOT in the
sidebar, NOT in sitemap.ts, and has ZERO internal links. Legacy sibling of
`/guides/models`.
**Recommended option:** Delete the route directory — nothing links to it and
`page.tsx:7-8` self-documents that definitive recommendations live in core, not
docs. Diff against `guides/models/page.tsx` first and port any unique content
into `guides/models` before deleting.

### E9. Duplicate team-sync sidebar entry
`config/docs.ts:56` (Guides) and `:64` (Deployment) both list `/guides/team-sync`.
**Recommended option:** Drop the standalone "Deployment" section and move only
"Enterprise Deploy" under "Guides" (team-sync gets a single canonical home).
Overlaps with E3 — if team-sync is pulled from the sidebar entirely (per E3),
both entries go.

### E10. Footer copyright line (post-relicense)
`ClientLayout.tsx:63` "© 2026 Magnetic Anomaly llc. All rights reserved." —
`llc` casing + "All rights reserved" inaccurate after Apache-2.0 (which
requires §2 copyright notice + NOTICE, not ARR).
**Recommended option:** Bundle with the relicense application: change to
"Copyright 2026 Magnetic Anomaly LLC. Licensed under Apache-2.0 (see LICENSE
and NOTICE)."

### E11. Keep dynamic-model-loading + byok-batching in nav (reject removal)
Per the C2 correction: both pages were restored/are-wired, not hidden.
**Recommended option:** Keep both pages, both sidebar entries, both sitemap
entries as-is. De-emphasizing relative to Ollama-Cloud-first (relabel/reorder)
is Eric's product-positioning call, but **do not remove** — removal would
contradict Eric's strategy and orphan the `batch_profiles.py:12` docs link.

### E12. [code/UX] Dashboard recommended-embedding-model slug (NOT docs)
`packages/ui/src/components/llm/AIModelsSettings.tsx:103` lists
`nomic-embed-code` (no namespace) which **404s on Ollama** — the docs correctly
use `manutic/nomic-embed-code`. A user following the dashboard hint would 404.
Also: `embedder.py:64` (manutic entry) lacks the `query_prefix`/`document_prefix`
that line 59 (`nomic-embed-code`) has — a latent quality regression if the
dashboard sends the manutic name.
**Recommended option:** Change the dashboard `RECOMMENDED_MODELS.embedding`
label to `manutic/nomic-embed-code` (match docs + registry); mirror the prefixes
from `embedder.py:59` to the `embedder.py:64` manutic entry. Eric owns the
dashboard UX and embedder preset table.

### E13. [code] Remove legacy license-polling code (unblocks E5)
`lemon_squeezy.py` + `api/routers/license.py` implement 7-day revalidation +
30-day downgrade to `api.lemonsqueezy.com`. Marketing + (post-E5) docs both
claim "no phone-home." The code must match before OSS launch.
**Recommended option:** Remove/stub the legacy polling path as part of the
Phase 146 license-crypto replacement (offline Ed25519). This is a code task, not
a docs task, but it gates E5's truth.

---

## 4. Recommended next steps (Eric-gated, in dependency order)

1. **Apply the relicense** (Apache-2.0 + DCO) → unblocks E1 (paperclip Apache
   wording), E10 (copyright line), and the docs-vs-marketing consistency question
   (whether docs mirrors marketing's "open source / Apache 2.0" framing or
   stays license-neutral).
2. **E13 → E5** (remove legacy polling code, then hedge the docs phone-home
   claim) so docs and code agree on "no phone-home."
3. **E2** (populate SourcePrep-deploy repo) — unblocks all 7 dead links with zero
   docs edits.
4. **E3 + E9** (team-sync "coming soon" reframe + sidebar dedup) — one
   coordinated decision.
5. **E8** (delete model-advisor orphan) — quick cleanup once confirmed
   subsumed by `/guides/models`.
6. **E12** (dashboard Ollama slug) — code/UX fix surfaced by research.
7. **E4, E6, E7** — product-positioning rewrites (compression section, BYOK
   privacy wording, docs home lede).
8. **Build `tools/build_public_mirror.py`** (the storefront allowlist tool) —
   gates E1's URL resolution and the broader mirror curation.

---

## 5. Pass 3 — Audit-the-Audit (2026-07-19)

A 42-agent workflow (8 reviewers over all 33 docs pages → per-finding
adversarial verification in worktree isolation → synthesis), ~2.3M tokens,
653 tool calls. Re-audited every docs claim under the corrected principle
("docs ≥ marketing conservative; assume every claim wrong until proven with
code AND intention; if provable with intention but not code, FLAG don't fix").

**Result:** 33 findings, all 33 verified. 29 CONFIRMED-FALSE, 1
INTENTION-ONLY, 3 refuted-as-TRUE (the audit caught and dismissed its own
false positives — good). Of the 29 CONFIRMED-FALSE, 4 were **worktree-base
artifacts** (the worktrees branched from `origin/main` = `6dc42b85`, which
does NOT include the local pass-1/2 commits `a6ad1c7f`/`31e8d210`; those 4
findings — codebase-audit `POST /audit` & `prep audit`, knowledge-scope
Pro-tier, cli/commands `--ide` list & `prep add` auto-build — were already
fixed locally and were re-verified as present-and-correct in the working
tree). Reconciliation left **24 genuinely-unfixed safe-now findings**, all
code-verified + license-neutral. **All 24 were applied this pass** + the
orphan-card `</div>` from the graph-enrichment six→five-dimension edit.
Docs app `tsc --noEmit` clean.

### 5.1 Pass-3 fixes APPLIED (24 safe-now + 1 structural, commit `________`)

| # | File:line | Fix (claim → correction) | Code evidence |
|---|---|---|---|
| 3.1 | `app/page.tsx:39` | Embedding card "(CPU, GPU, BYOK)" → "(CPU or GPU)" — no BYOK embedder exists | `embedder.py` defines only `NativeEmbedder` + `OllamaEmbedder` |
| 3.2 | `getting-started/page.tsx:90` | SSE URL `localhost:8400/mcp/sse` → `localhost:8401/sse` via `prep mcp --transport http` | `cli.py:727` (port 8401); `mcp/transport.py:174` (`/sse` at root, not `/mcp/sse`) |
| 3.3 | `how-it-works/compression/page.tsx:292-296` | "Coming Soon: …future Pro feature…BERT model" → "Roadmap: …evaluated LLMLingua-2…removed it" (callout was already deleted in P2; this fixes the body paragraph) | `search.py:369-375` returns `NoopCompressor`; `compressor.py` only Noop+Structural |
| 3.4 | `how-it-works/indexing/page.tsx:205-208` | "first build kicks off automatically" → "trigger the first build with `prep build`" | `cli.py:275-305` `add` does NOT auto-build |
| 3.5 | `how-it-works/embeddings/page.tsx:169-172` | "Upgrade to nomic-embed-code…for highest retrieval quality" → "ONNX has the best accuracy…nomic-embed-code is a flexibility option, not a quality upgrade" (resolves page self-contradiction: table shows ONNX 84.6% > nomic-embed-code 82.1%) | page's own table :124; `embedder_factory.py` defaults to `NativeEmbedder` |
| 3.6 | `how-it-works/embeddings/page.tsx:186` | "Tier 1: nomic-embed-code via Ollama (recommended)" → drop "(recommended)" (ONNX is the recommended default per :79) | same-page :79 |
| 3.7 | `how-it-works/context/page.tsx:49` | "Two engines…Documentation…lightweight language model (~2.4×)" → "One CPU-only engine…Documentation passes through with structural compression only" | `search.py:369-375`; `compressor.py` |
| 3.8 | `how-it-works/context/page.tsx:138` | "Chunks (k): Default: 20" → "Default: 5" | `useSearchContext.ts:30`; `models.py:47` `k=5` |
| 3.9 | `how-it-works/context/page.tsx:143` | "Max chars: Default: 24,000 (32k windows)" → "Default: 6,000 (8k windows)" | `useSearchContext.ts:31` `6000`; `models.py:48` `max_chars=12000` |
| 3.10 | `how-it-works/graph-enrichment/page.tsx:197-220` | "weighted composite of **six** dimensions" (with Temporal currency 15%) → **five** dimensions (Summary 23.5%, Validation status 17.7%, Neighbor coverage 23.5%, Cross-ref 17.7%, Enrichment depth 17.6%); removed the Temporal currency card + orphan `</div>` | `epistemic_score.py:33-39` (5 weights); docstring "c6 staleness weight deleted in Phase 134; remaining 5 renormalized" |
| 3.11 | `guides/codebase-audit/page.tsx:252` | "When you run with `--synthesize`" → "When you run an audit with `synthesize: true` (via MCP `prep_audit` or the REST API)" | no `--synthesize` flag in `cli.py`; `synthesize: true` is the real API param |
| 3.12 | `guides/audit-enrichment/page.tsx:134` | 'hub_status = "unknown"' → 'dependents: 0 and hub_status: "low"' | `mcp/server.py:2568-2614` defaults to `hub_status="low"`; no "unknown" value exists |
| 3.13 | `guides/concurrency-discovery/page.tsx:85` | "open Settings → Diagnostics → Concurrency Health" (as the only path) → primary: `GET /compute/concurrency/history?node_id=…` API; "(in dev builds, Settings → Diagnostics…)" | `routeParser.ts:9-11` Diagnostics is dev-only; `compute.py:315` API available to all |
| 3.14 | `guides/concurrency-discovery/page.tsx:202` | Same dev-only-UI correction (Concurrency Health view → HTTP API primary) | same |
| 3.15 | `guides/concurrency-discovery/page.tsx:79` | Example queue icon `8/12 🌧️` → `8/12 ↗` (🌧️ doesn't exist; only 🔒/🔻/↗/📈) | `SidebarPipelineQueue.tsx:342-346` |
| 3.16 | `guides/models/page.tsx:222-223` | "structural LOD rendering (no model needed) plus an optional 178 MB BERT model for prose compression" → "structural LOD rendering — no model needed" | `search.py:369-375`; `compressor.py` |
| 3.17 | `guides/byok-batching/page.tsx:166-170` | "1. Retries once. 2. Splits in half. 3. Individual fallback." → "1. Retries on 429. 2. Subdivides + falls back to individual in production." (halving only happens in exploratory mode for sizes exactly 4-5; production goes straight to per-item) | `batch_strategy.py:370-373`; `llm_client.py:399` (`_MAX_429_RETRIES=2`) |
| 3.18 | `cli/config/page.tsx:35-48` | Deleted false `.sourceprep/config.json` override + the entire `.sourceprep/ignore` subsection + example block; replaced with accurate SQLite + `repo_policy.json` + "respects .gitignore automatically" | no code reads either file; `index.py:338-344` parses only `.gitignore`; Rust walker excludes `**/.sourceprep/**` |
| 3.19 | `troubleshooting/page.tsx:136` | Windsurf config path `~/.codeium/windsurf/mcp_config.json` (legacy Codeium-era) → `.windsurf/mcp.json` in project root | `mcp_config.py:126` writes `.windsurf/mcp.json` (`path_hint: "Project root"`) |
| 3.20 | `troubleshooting/page.tsx:156` | "excluding large folders…in `.sourceprep/ignore`" → "via your `.gitignore` or per-project `exclude_globs` in the Dashboard" | no `.sourceprep/ignore` parser |
| 3.21 | `troubleshooting/page.tsx:157` | "max_file_bytes…via Dashboard or `.sourceprep/config.json`" → "via Dashboard, or set the global default with `prep config max_file_bytes <bytes>`" | `max_file_bytes` read from `proj.config` (SQLite) at `build.py:30-31` |
| 3.22 | `troubleshooting/page.tsx:186` | Dropped "Check for a `.sourceprep/ignore` file." bullet | same as 3.18 |
| 3.23 | `troubleshooting/page.tsx:197` | "Increase the limit: `prep config max_file_bytes 1000000`" (implies global CLI fixes an existing project's FILE_TOO_LARGE) → "via the Dashboard project settings, or the scope/project config endpoints. (The global `prep config` only sets the default for newly-created projects.)" | `cli.py:1078` PUTs `/global/config`; `build.py:30-31` reads per-project |
| (V2) | `guides/models/page.tsx:112` | (pre-workflow) "Requires a GPU and Ollama installed locally" → "GPU strongly recommended — Ollama…falls back to CPU" (2nd occurrence P7 missed) | `embedder`/Ollama CPU fallback (same as P6/P7) |

### 5.2 Refuted (audit caught & dismissed its own false positives — no edit)

- `cli/commands/page.tsx:61` — reviewer claimed `prep context` omits `--role`.
  **Refuted:** line 69 lists `--role` (matches `cli.py:611`). Pass-1/2 fix already landed.
- `ClientLayout.tsx:60` — reviewer claimed footer GitHub link `…/SourcePrep` 404s.
  **Refuted:** the finding misquotes the URL; actual link is `…/SourcePrep-MCP` (HTTP 200).
  *(Separate real dead-link flagged out of scope: `mcp/paperclip/page.tsx:275` and
  marketing `links.ts:3` `GITHUB_REPO_URL = …/SourcePrep` DO 404 — see E1/E2 family.)*

### 5.3 New Eric-gated items (continuing E1–E13 numbering)

#### E14 `getting-started/installation/page.tsx:81` — code-TRUE paywall text, relicense-blocked
The 3-project Free-tier + Lemon Squeezy + "works fully offline" licensing paragraph
is **accurate to current code** (`feature_gate.py:46` 3-project limit; `lemon_squeezy.py`
LS-as-MoR; `license.py` activation; 30-day offline grace). Pass-1 commit `a6ad1c7f`
(on local main, NOT on origin/main) already retired this with license-neutral wording.
The workflow worktree branched from `origin/main` so it saw the pre-fix state. Under
the corrected principle, re-applying the neutral wording here would assert an OSS
posture before the relicense lands. **Recommended option:** leave as-is in the working
tree (the pass-1 neutral wording already covers it once these commits land on
origin); do NOT re-apply manually. Resolve when the local pass-1/2/3 commits reach
origin/main alongside the relicense.

#### E15 `guides/enterprise-deploy/page.tsx` + `guides/team-sync/page.tsx` — dead external links (INTENTION-ONLY)
Links to `github.com/MagneticAnomaly/SourcePrep-deploy` (7 links) and
`ghcr.io/magneticanomaly/prep-headless:{cpu,gpu}` image refs as if both already exist.
In-repo artifacts DO exist (`public/sourceprep-deploy/Dockerfile.{cpu,gpu}`,
`entrypoint.sh`, `modal/`, `runpod/`, `aws/`, `github-actions/`, plus
`.github/workflows/docker-headless.yml` with `push: true`) — clear design intent. BUT:
(a) `git ls-remote deploy` returns zero refs (subtree repo still empty);
(b) no `app-v*` git tag exists, so `docker-headless.yml` has never run → GHCR images
NOT published; (c) `REPO_TOPOLOGY.md` (decided 2026-07-17) collapses the public
topology to a single `MagneticAnomaly/SourcePrep` storefront; `SourcePrep-deploy` is
not in the decided topology. **Recommended option:** Eric decides at launch —
(1) populate + make public `MagneticAnomaly/SourcePrep-deploy` AND cut an `app-v*`
tag to publish the GHCR images (page true as written), or (2) rewrite the external
links to "available to Enterprise customers on request" (`mailto:enterprise@sourceprep.io`)
or repoint to the future storefront. Do NOT silently fix. (Same family as E2, but
E2 was scoped to the deploy-repo subtree links; E15 adds the GHCR image refs and the
REPO_TOPOLOGY inconsistency.)

### 5.4 Cross-cutting follow-ups flagged (out of scope for docs site — code/marketing)

- Stale LLMLingua-2/BERT copy in `packages/ui` (`CompetitorMatrix.tsx`,
  `TechStackMatrix.tsx:44`, `AIModelsSettings.tsx:1167`, `researchSources.ts`) —
  same stale-claim pattern as 3.3/3.16; worth a parallel **marketing** sweep.
- Stale `lingua`/`auto` enum values still advertised in `mcp_tools.py:633-637`
  schema (handler returns `NoopCompressor`) — internal schema cleanup, code task.
- `audit.py:7-8` module docstring still lists the deleted `POST /projects/{id}/audit`
  endpoint — internal consistency only.
- `scope_orchestrator.py:13` docstring says "Pro gets auto-rebuild, Free gets
  manual" — stale relative to authoritative `feature_gate.py:65` (`auto_scope_rebuild`
  is `Tier.FREE`).
- Dead `…/SourcePrep` (no-suffix) links: `mcp/paperclip/page.tsx:275` and marketing
  `links.ts:3` `GITHUB_REPO_URL` 404 (separate from the `…/SourcePrep-deploy` E15
  cluster).

### 5.5 Updated next steps (Eric-gated, dependency order, supersedes §4)

1. **Apply the relicense** (Apache-2.0 + DCO) → unblocks E1, E10, E14, and the
   docs-vs-marketing license-framing question.
2. **E13 → E5** (remove legacy `lemon_squeezy.py` polling, then hedge the docs
   phone-home claim).
3. **E2 / E15** (populate `SourcePrep-deploy` repo + cut `app-v*` tag for GHCR
   images) — unblocks all 7+ dead deploy links with zero docs edits; OR rewrite
   the links per E15 option (2).
4. **E3 + E9** (team-sync "coming soon" + sidebar dedup).
5. **E8** (delete model-advisor orphan, diff vs `/guides/models` first).
6. **E12** (dashboard `AIModelsSettings.tsx:103` slug → `manutic/nomic-embed-code`;
  mirror prefixes in `embedder.py:64`).
7. **E4, E6, E7** (compression/BYOK-privacy/docs-home-lede rewrites).
8. **Build `tools/build_public_mirror.py`** — gates E1 URL resolution + mirror
   curation; also resolves the `…/SourcePrep` no-suffix dead links (5.4).
9. **Marketing sweep** (5.4) — the same BERT/LLMLingua-2 and no-suffix-GitHub-URL
   stale claims recur in `packages/ui` + marketing; coordinate so docs and
   marketing land consistent wording.

## 6. Pass 4 — Structural scrutiny via prep MCP (2026-07-19)

A 46-agent workflow (`docs-structural-scrutiny`, run `wf_60bc3c6d-ca8`) re-audited
the docs against the live app **structurally**, not lexically. Nine reverse-engineer
agents (one per claim cluster) used `prep_search` + `prep_impact` + `Read` to verify
wiring, then each finding was adversarially re-verified by an independent agent.
Counts: 36 raw findings → 34 CONFIRMED-FALSE, 1 INTENTION-ONLY, 0 INSUFFICIENT,
1 refuted-TRUE (the audit caught and dismissed its own false positive).

### 6.1 Reconciliation — worktree-base artifacts (critical)

The workflow agents ran in worktrees branched from `origin/main` (`6dc42b85`),
which does **not** include the local pass-1/2/3 commits (`a6ad1c7f`, `31e8d210`,
`04e108a0`). So many "CONFIRMED-FALSE" findings describe text the working tree
already fixed. **Every finding was re-grepped against the actual working tree
before applying.** Worktree artifacts skipped (already fixed locally):

- `S13` ("`prep audit` CLI command" at codebase-audit:347) — working tree already
  says "trigger an audit via the MCP `prep_audit` tool, the REST API, or the
  dashboard Audit panel."
- `S17` (audit-enrichment:134 `hub_status = "unknown"`) — already `hub_status:
  "low"`, `dependents: 0`.
- `S25` (installation:85 "Payments are processed by Lemon Squeezy") — already
  removed (pass-1, `a6ad1c7f`).
- `S27` (models:222 "optional 178 MB BERT model") — already "no model needed"
  (pass-3, `04e108a0`).
- `S31` main claim (concurrency-discovery:79 🌧️ rain icon) — already `8/12 ↗`.
- All eight §6.4 "INCOMPLETE pass-3" roster entries except two residuals
  (embeddings GPU badge :43 + table :124; compression nav label :16) — the
  roster's "did not land" claims were worktree artifacts; pass-3 did land them
  on the working tree.

This re-confirms the pass-3 lesson: **workflow findings must be reconciled
against the actual working tree before applying.**

### 6.2 Safe-now fixes APPLIED this pass (24 fixes, all code-verified)

Every fix below was verified against the cited code (not just the workflow's
claim) before editing. `tsc --noEmit` clean on both `websites/apps/docs` and
`packages/ui`.

| # | file:line | was (false) | now (true, code-verified) |
|---|---|---|---|
| S1 | embeddings:85-87; models:160-162 | "Runs entirely on CPU — no GPU" | "Runs on CPU by default with automatic GPU acceleration (CoreML/CUDA/DirectML) when available" — `NativeEmbedder._detect_onnx_providers` (embedder.py:409-445), `MLComputeUnits="CPUAndGPU"` (:496), class docstring "GPU acceleration is automatic when available" (:708). |
| S1b | embeddings:93 badge | "CPU only · no GPU needed" | "CPU default · GPU auto when available" |
| S2 | enterprise-deploy:301 | "Audit logging" row = Roadmap | Available — `audit_log.py` built/mounted (server.py:821,833), POST/GET `/admin/audit-log` (settings.py:539,565), `feature_gate.py:61` gates to ENTERPRISE. (Code caveat surfaced separately: `/admin/audit-log` endpoints don't call `require_feature('audit_log')` — enforcement gap, not a docs fix.) |
| S3 | compression:136,142 | Tier 2 Neighbour "LOD 2 (signatures)"; Tier 2.5 Hub "4 at LOD 2" | "LOD 2.5 (sigs + docstrings)"; "4 at LOD 2.5" — `context_tier.py:64` `neighbor_lod=25`, `:78` `hub_lod=25` (both "LOD 2.5"); `lod_extractor.py:662` dispatches `lod==25`→`_build_lod25`. |
| S4 | compression:193-207 | "select LOD (Structural) from the Compression dropdown"; curl sends `"compression":"lod"` | "LOD compression is always applied. In the Context Assembler panel, click Assemble…"; dropped `"compression":"lod"` (silently dropped — no such field; `types.ts:1294` `context_compression` is `@deprecated LOD compression is always-on`). |
| S5 | compression:165-167 | Flow diagram: 3 thresholds/tier → LOD 0/2/4 (no LOD 5) | Added 4th branch per tier (`<0.15`/`<0.20`/`<0.25` → LOD 5) — `lod_extractor.py:540-578` `assign_lod` has 4 outcomes (return 0/2/4/5). |
| S7 | cli/commands:178-182 | `prep flow <query>` "Visualizes the RAG flow for a given query" | `prep flow` "Renders a demo RAG-flow visualization… A real query-driven flow is not yet wired" — `cli.py:1330-1364` signature is `flow(project_id,host,port)`, hardcoded `demo_flow` dict, comment "For now just show demo." |
| S8 | cli/commands:76 | `prep status` "Prints the health of the daemon, connected projects, and index statistics" | "Prints index status for a project… Pass an optional `<project_id>`… (For a daemon-wide overview, use `prep overview`.)" — `cli.py:480-529` calls only `/projects/{pid}/status`; `overview` is the separate `:1197` command. |
| S9 | mcp/page.tsx:27 | "plus MCP-aware VS Code extensions (Cline, Roo, CodeGPT)" | "plus MCP-aware VS Code extensions like Cline" — `mcpSetup.ts` has 6 IDE entries (no Roo/CodeGPT); `mcp_config.py` has no roo/codegpt target. |
| S10 | codebase-audit:150-152 | `POST /projects/{id}/audit` "Trigger audit (Tier 1 + optional Tier 2)" | `POST /projects/{id}/pipeline/stages/audit/run` "Trigger audit as a finalize stage through the orchestrator (runs Tier 1, then attempts Tier 2…)" — `audit.py:37-42` deletion comment; real trigger `pipeline.py:309`. |
| S11 | codebase-audit:30-32; 344-347 | "AutoAudit is **not** a pipeline stage. It's an independent tool" | "AutoAudit is a finalize pipeline stage (stage 14 of 15, running in finalize wave 2 after deep enrichment)…" — `stages.py:31` `AUDIT="audit"`, `:76` FINALIZE_STAGES, `:50` BuildType.AUDIT; `workers/__init__.py:478,1794` `_audit_worker`. |
| S12 | codebase-audit:302-311 | Settings table rows `auto_run_after_deep` + `auto_synthesize` | Removed both rows — dead config: only refs are `config_manager.py:198-199` (defaults) + `packages/ui/types.ts:1461` (type) + docs; `_load_audit_config` reads neither. |
| S14 | codebase-audit:351 | "If `auto_run_after_deep` is enabled, Tier 1 analyzers run automatically…" | "If the per-project `auto_config.finalize` is set to `auto`, the audit stage runs automatically (Tier 1 + Tier 2) when deep enrichment completes" — `orchestrator.py:1923-1942` `_is_finalize_auto`. |
| S15 | codebase-audit:288-291 | "configurable via the dashboard Settings panel or the `audit_config` section" | "configurable via the `audit_config` section in `ui_config.json` (edit the file directly; thresholds are read at audit-run time)" — no dashboard Settings page exposes audit_config (grep empty across 13 settings pages). |
| S16 | codebase-audit:282-284; 352 | "indexed by SourcePrep's search engine…query them via `prep_search`" | "served via the audit REST API (GET `/audit/reports`, GET `/audit/report/{name}`) and through the MCP `prep_audit` tool with action `report`" — audit `.md` writes to `.sourceprep/audit/` which is walker-excluded (`repo_profile.py:12`); access is REST/MCP `action=report`, not `prep_search`. |
| S18 | graph-enrichment:246-250 | Score Decay table presents 5 events as live | Tagged the 3 dead events "(planned)" + footnote "Only the first two events are wired in production today" — `apply_decay` has ONE production callsite (`deepening.py:203` `neighbor_enriched`); `doc_updated`/`trace_rebuilt`/`module_resynthesized` have zero production callers. |
| S19 | graph-enrichment:224 | "The Atlas Lens is what consumes the understanding score" | "The Atlas Lens projects the codebase through role-specific lenses… using the epistemic enrichment produced during Enrich — architecture layers, domain tags, and per-node confidence" — `compute_role_relevance` (atlas/role_projection.py:325) takes `epistemic_confidence` (raw float, default 0.5), NOT the composite; composite consumers are only `epistemic_score.py`/`deepening.py`/`post_flight.py`. |
| S20 | graph-enrichment:256-258 | "the Deepening stage processes this queue until the graph converges or the token budget is exhausted" | "until the graph converges or the iteration limit is reached (max 10 deepening passes)" — `ConvergenceTracker` (`deepening.py:224-316`) `max_iterations=10`, `budget_exhausted` = max iterations; no token counter. |
| S21 | graph-enrichment:256 | "File C…decays even less" (implies hop-attenuation) | "decays by the same factor…each non-stale neighbor decayed once (×0.95 against its original score)" — `deepening.py:190-206` applies `apply_decay(old_score,"neighbor_enriched")` per hop, `old_score` = original composite, guard `if neighbor not in report.decayed_nodes` (:201). |
| S23 | byok-batching:152-160 | "When supported by the provider (OpenAI, Anthropic, Google)" | "When supported by the provider (OpenAI, Google, and Ollama for supported models)… For providers without structured output support (such as Anthropic), SourcePrep falls back to robust JSON extraction" — Anthropic payload (`llm_client.py:1079-1091`) drops `response_schema`; `response_format` set only for OpenAI (:988) / Ollama (:814). |
| S24 | byok-batching:168 | "subdivides the batch and retries the pieces — falling back to processing items individually in production" | "In production, a failed batch falls back directly to processing items individually (no subdivision)… A test-only exploratory mode subdivides the batch" — `batch_strategy.py:370-373` production `return [[item] for item in failed_items]`; exploratory `:361-369` subdivides. |
| S26 | embeddings:43,124 | badge "GPU required (Ollama)"; table GPU? "Required" | "GPU recommended (Ollama)"; "Recommended" — `OllamaEmbedder` (embedder.py:117-179) never probes/enforces a GPU; pass-2 softened models but missed these two embeddings locations. |
| S28 | `packages/ui` AIModelsSettings.tsx:1167 | "Compression: LLMLingua-2 prunes docs/markdown tokens; LOD extracts code" | "Compression: LOD extracts code at configurable detail levels (no model needed)" — `_get_compressor` (search.py:369-375) returns `NoopCompressor()` unconditionally; ships in the real dashboard (`useDashboardPanels.tsx:688`) AND the docs models live-preview. |
| S29 | compression:16 | SECTIONS nav label `language-compression` = "Coming Soon" | "Roadmap" — pass-3 rewrote the section body to "Roadmap: Language Compression…removed it" (`:292`) but left the nav label contradicting it. |
| S30 | `packages/ui` mcpSetup.ts:103-104 | `file: '~/.codeium/windsurf/mcp_config.json'`, `fileHint: 'Global config (applies to all projects)'` | `'.windsurf/mcp.json'`, `'Project root'` — canonical generator `prep mcp-config` emits `.windsurf/mcp.json` (`mcp_config.py:125-127`); pass-3 fixed the troubleshooting page but never touched the single-source registry that `/mcp/ides` renders verbatim. |

### 6.3 Eric-gated (new, E16–E19) — flag, not applied

**E16 — installation:81** "free to use with all features included and unlimited
projects — you can build the desktop app yourself from source. See the repository
LICENSE for licensing details." The specific "3 active projects" sub-claim the
worktree flagged is a worktree artifact (already removed locally), but the
surviving text raises two genuine product-truth questions for Eric: (a) is
"all features included" honest when `feature_gate.py:60-61` gates `team_config`
(Team) and `audit_log` (Enterprise)? (b) does "build the desktop app from source"
survive the current proprietary LICENSE (see E19)? **Recommended:** Eric decides
the honest phrasing; until then do not silently rewrite.

**E17 — concurrency-discovery:90-95** `DemoLLMStatusWidget` caption "each cloud
endpoint shows its live concurrency state and last-probe outcome." The widget
(`LLMStatusWidget.tsx`) shows connectivity only (connected/disconnected/disabled);
concurrency/probe state lives in the separate `ConcurrencyHealth` panel the page
already points to at :84-88. **Recommended:** (a) drop the redundant
`DemoLLMStatusWidget` block, or (b) replace with a `DemoConcurrencyHealth`
snippet. License-neutral; gated only on drop-vs-replace.

**E18 — enterprise-deploy:287** "Offline licensing…Ed25519-signed license files,
no phone-home after activation." The path is mechanically real and local
(`verify_license_key` licensing.py:24, live not dead) BUT the verifying public
key is a hardcoded **placeholder** — `licensing.py:22 DEFAULT_PUBLIC_KEY_HEX` =
the RFC 8032 Ed25519 test vector; comments :17-21 say "random…for
demonstration/dev purposes." Anyone with the test private key can forge an
enterprise license. **This is the structural trap grep misses:** the symbol
exists and routes, so a string audit says "true," but the crypto guarantee is a
placeholder the code flags as dev-only. **Recommended:** (a) add a qualifier
matching marketing ("Ed25519 offline verification is planned for the Pro
installer; the current license crypto is placeholder and being replaced before
launch"), or (b) move the row to Roadmap alongside SSO/SCIM.

**E19 — installation:81-82** (INTENTION-ONLY) "build the desktop app yourself
from source. See the repository LICENSE." Building from source requires
copying/modifying — exactly what `LICENSE:10-12` forbids ("NO REDISTRIBUTION:
You may not copy, modify, merge, publish, distribute…without prior written
consent"). The claim is contradicted by the very LICENSE it defers to.
Apache-2.0+DCO is decided but not applied. **Recommended:** (a) soften to future
tense matching marketing ("an Apache-2.0 open-source release is planned, which
will allow building the desktop app from source"), or (b) wait for the relicense
to land on root LICENSE before claiming build-from-source.

### 6.4 Flagged to Eric but not applied (from the safe-now set)

- **S6 — concurrency-discovery:74** uses `cloud:default_ollama` as the running
  example for the 🔒 locked state, but `default_ollama` has `auto_detect: false`
  (`concurrency_limits.json:8`), so `_derive_node_state` can never return
  "locked" for it (`scheduler.py:281-301` requires `discovered_ceiling is not
  None`). The locked example is unreachable for the provider the page uses
  throughout. **Recommended:** swap the running example to an auto-detect
  provider (`cloud:my-openai`) OR add a callout that Ollama Cloud/Gemini/Kimi use
  the user's max as authoritative. Gated on Eric's choice of provider naming.
- **S22 — enterprise-deploy:248** "No telemetry. SourcePrep does not phone home…"
  (present-tense blanket) folds into the existing **E5/E13** phone-home cluster:
  the license router phones home to `api.lemonsqueezy.com` every 7 days
  (`lemon_squeezy.py:140-156`, `VALIDATION_INTERVAL_SECONDS=7d` `:43`). Docs are
  less conservative than marketing (`security/page.tsx:149-150` "the current
  license crypto is being replaced before launch"). A license-neutral hedge is
  possible but Eric owns the wording (E5) — do not auto-apply.

### 6.5 Refuted (settled TRUE, no change)

- **graph-enrichment:33** — Stage 6 labeled "Epistemic scoring — layers,
  domains, confidence ratings." Verifier confirmed the composite is computed in
  stage 9 (via `DeepeningLoop`), not stage 6, but the label is defensible: stage
  6's `EpistemicEnricher.run` does produce per-node `epistemic_confidence` ratings
  (`epistemic_enrichment.py:645-652`), and the dash clause says "confidence
  ratings," not "understanding score." Style nit only — not reported per
  pass-3 instructions. (Surfaced during this verification: the "Understanding
  Score" section at :197-223 was already corrected to "five dimensions" by
  pass-3 — confirmed in the working tree.)

### 6.6 Dogfooding notes — what prep MCP surfaced that grep could not

The structural pass's value was **concentrated in a few high-leverage findings,
not uniform across the set.** Most safe-now fixes (S3–S16, S20–S21) could be
settled by `grep` + `Read` once you knew where to look; prep's marginal value
there was confirming zero dependents / dead config (real but modest). The
findings where prep MCP genuinely changed the verdict vs. a lexical audit:

- **S19 (Atlas Lens)** — prep_search intent=trace + cross-package grep for
  `.composite`/`EpistemicScore` across `atlas/`/`api/`/dashboard proved "consumes
  the understanding score" is a mis-attribution. grep alone over the single docs
  file could not have ruled out a hidden composite consumer in another package.
- **S22 (no-telemetry)** — grep for "telemetry"/"phone home" in `license.py`
  returns nothing; the claim and code share no vocabulary. Only
  `prep_impact` on `license.py` (3 dependents incl. `server.py` confirming the
  router is mounted) + Read of the LemonSqueezy POST path exposed the live
  phone-home.
- **E18 (Ed25519 placeholder)** — `prep_impact` confirmed `verify_license_key`
  is wired into the license router (live, not dead) — precisely why a string
  audit says "true" while the crypto guarantee is a placeholder. The structural
  trap is that the symbol exists and routes; only reading the key value + the
  self-documenting comments reveals the defect.

**prep_search index gaps worth flagging (product feedback):** symbol-locate
returned `NODE_NOT_FOUND` for real, exported, called symbols — `assign_lod`
(S5), `compute_all_scores`/`compute_epistemic_score` (refuted finding),
`query_audit_log`/`export_audit_log` (S2), `auto_run_after_deep`/`auto_synthesize`
(S12). grep+Read was the settling fallback each time. A docs-claim-vs-legal-file
comparator (E19) is a class of question prep MCP has no instrument for — the
LICENSE has no symbols, imports, or call graph.

**Net dogfooding verdict:** prep MCP's marginal value over a disciplined
grep+Read audit is real but **narrow** — it shines on cross-package
mis-attribution (S19), vocabulary-mismatched claims (S22), and
exists-but-placeholder traps (E18). For the bulk of factual code-corrections,
grep was sufficient once the workflow pointed at the right file:line. The
46-agent structural pass found 24 genuine new fixes pass-3 missed (esp. the
codebase-audit pipeline-connection cluster, LOD 2.5, and the Anthropic
structured-output gap) — most of which a careful human grep would also catch,
but prep MCP raised confidence that no hidden callers/wiring contradicted the
fix.

### 6.7 Cumulative totals

- Pass 1: 6 fixes. Pass 2: 16 fixes + 1 revert. Pass 3: 24 fixes + V2.
- Pass 4: 24 safe-now fixes (table above) + 4 new Eric-gated items (E16–E19) +
  2 flagged-but-deferred (S6, S22→E5).
- **Grand total: ~70 docs/UI fixes across 4 passes.** Docs + `packages/ui`
  `tsc --noEmit` clean. No codename leaks. No premature license assertions.
  All Eric-gated items (E1–E19) collected in §3/§5.3/§6.3 for batch decision.