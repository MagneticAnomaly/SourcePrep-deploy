# Phase 132 — Docs Behavioral Fidelity Audit

> **Source issues:** Phase 130 (docs staleness sweep) outcome log; Issue 13 follow-up.
> **Origin date:** 2026-05-09
> **Status:** Scoped, not started.

## Why this phase exists

Phase 130 sweept the public docs for *surface* staleness — panel names, URL paths, CLI command lists, MCP tool counts, model-slot numbers. It used a question of the form:

> "Does the *thing* this page references still exist (file, route, command, panel id, story)?"

That sweep landed 8 commits and resolved Issue 12 in `MARKETING_SITE_AUDIT.md`. The docs are now structurally correct: registries match real routes, no dead Storybook ids, no defunct mental models, no broken cross-links.

Phase 132 is the next, deeper question:

> "If a user follows this page literally, does SourcePrep actually behave the way the page describes?"

This is **behavioral fidelity**, not just structural fidelity. It catches a different class of drift: features that exist but don't work the way the docs say they do; behaviour the app exhibits that the docs don't mention; gating, timeouts, error paths, fallbacks, and edge cases the docs gloss over.

## Out of scope

- Pure copy-editing for tone or length. (Phase 130 already trimmed; further trim only when behaviorally motivated.)
- Marketing-site copy. The marketing/docs split (memory: `feedback_marketing_vs_docs_split.md`) still applies — concept-level prose lives in marketing, how-to lives in docs.
- New product features. This phase is documentation, not implementation. If we discover a real product gap (the docs describe behaviour that *should* exist but doesn't), file it as a separate task and move on.

## Method

For each docs page, walk through every **claim** and **instruction** literally, with a fresh local SourcePrep installation and the live `prep` MCP attached. Record one of three outcomes per claim:

| Outcome | Meaning | Action |
|---------|---------|--------|
| ✅ Verified | Did the thing the page describes; got the result the page promises. | Note in the page checklist; no edit needed. |
| ⚠ Drift | Behaviour partially matches but is materially different in some user-visible way (timeouts, formats, error messages, gating). | Fix the docs page to describe the actual behaviour. |
| ❌ Missing | Page describes a feature/output/flow that doesn't happen. | Either fix the docs (remove/rewrite the claim) or file a product task if the docs describe what *should* exist. |

A "claim" or "instruction" is anything load-bearing for the user: a numbered step, a code block they're meant to run, a sentence describing what something returns, a screenshot caption, a stated tier-gate, a default value, a per-page anchor.

## Concrete page checklist

Tier ordering is by likelihood that a user follows the page **literally** (onboarding > reference > optional guide).

### Tier A — onboarding & first-run

Highest user impact. Get these right before the rest.

- [ ] `getting-started/installation`
  - First-launch experience: does the desktop app actually start the daemon? Does `prep --version` work after a fresh install on each platform?
  - Mac App Store / Microsoft Store: do these listings actually exist today?
  - First-time license activation flow: does it really require one online round-trip then work offline?
- [ ] `getting-started/quick-start`
  - Step 4: select files in Scope panel → call `prep` → does the agent actually receive a baseline that mentions hub files / focus areas / immune-system alerts?
  - Step 5: ask "Audit my codebase" → does the agent actually invoke `prep_audit`? Does it return severity-tagged findings (`ARCH-1`, `QUAL-3`) as claimed?
  - Free-tier note about manual trace build: does the dashboard actually require manual build on Free, with auto-build on paid? Verify against `feature_gate.py`.
- [ ] `getting-started` (parent) — the "trust loop" sequence and the 11-analyzer audit claim. Walk it once on a clean repo and a 50k-file repo.

### Tier B — MCP integration (the front door for AI agents)

- [ ] `mcp/page.tsx` — Tools Reference table accuracy (row-by-row against actual handler behaviour, not just schema). Every action enum value (`scan`, `antibodies`, `refactor`, `verify`, `report`, `advise`) on `prep_audit` should produce *something* documented; if any are no-ops on the current handler, page should say so.
- [ ] `mcp/ides` — Cursor, Windsurf, VS Code (via Copilot), Antigravity, Zed. Each config copy-paste must result in a working MCP attachment. Per-host gotchas (e.g. config path, restart procedure) belong on the page only if they're real.
- [ ] `mcp/terminal` — Claude Code, Codex, Gemini CLI. Same end-to-end verification. The "Claude Code (primary)" framing should be true in practice — does Claude Code actually surface SourcePrep tools more reliably than the others?
- [ ] `mcp/paperclip` — installable plugin path; check claimed "5 tools, dashboard widgets, event-driven context".

### Tier C — concept pages (already rewritten in Step C, but behavioral-check)

- [ ] `concepts/indexing` — every claim about what gets indexed, what's deduplicated, embedding tier choice. Verify the tier-default-by-hardware claims against the embedder fallback chain.
- [ ] `concepts/code-graph` — edge kinds (contains, imports, implements, configures, listens_to). Are those the only ones? Are the file/symbol-level granularity claims accurate?
- [ ] `concepts/graph-enrichment` — 15-stage pipeline. Each stage's claimed inputs/outputs against `STAGE_INPUT_FILES` and `STAGE_OUTPUTS` in `services/pipeline/stages.py`. The "Sync vs Enrich vs Finalize" group claims against actual scheduling.
- [ ] `concepts/context` — query intent classification, atlas routing, LOD compression, citation format. Run a real query and compare to what the page promises.

### Tier D — guides (deep behavioral checks)

The Phase 130 sweep verified each guide's *fields* and *endpoints* exist. Phase 132 should verify the *flows* work.

- [ ] `guides/embeddings` — three-tier flow: switch between built-in ONNX → nomic-embed-text via Ollama → nomic-embed-code via Ollama. Each switch + rebuild should complete and improve/maintain retrieval. R@1 numbers on the comparison table — are they still current after model and indexer changes?
- [ ] `guides/audit-enrichment` — actually pipe a `ruff check src/ --output-format json` through `prep_audit(findings=...)`. Check that every documented enrichment field appears on at least one finding. Re-run with a SARIF input to verify SARIF round-trip.
- [ ] `guides/codebase-audit` — run an audit, check the format options (`table`, `json`, `sarif`, `csv`, `md`, `ai_prompt`). Verify the documented analyzers all run and produce findings.
- [ ] `guides/smart-search` — submit one query of each intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER) and verify the result shape and the auto-detected intent match. Confirm the tiebreaker order (`TRACE > RATIONALE > COMPARE > EXAMPLE > DISCOVER > LOCATE > EXPLAIN`) actually fires that way.
- [ ] `guides/compression` — run a query against a small repo with a Tier 1 / Tier 2 / local client signature; verify the LOD ratios on real source.
- [ ] `guides/concurrency-discovery` — actually trigger a reset (`POST /compute/concurrency/clear?node_id=cloud:default_ollama`) and verify the behaviour described (lock cleared, jumpstart resumes, lock re-establishes after probing).
- [ ] `guides/path-weights` — set + get weights via the documented API; submit a search and check that ranking actually reflects the weights.
- [ ] `guides/knowledge-scope` — toggle scope via the panel and via the API. Verify only selected files end up in the index after rebuild.
- [ ] `guides/byok-batching` — configure a BYOK endpoint (use a small/cheap cloud model), run a build, verify batching actually happens (1 API call covering many files) and that the cost-estimation banner appears.
- [ ] `guides/team-sync` — defer until SourcePrep-deploy repo state is settled (the doc references a public repo whose existence we haven't verified).
- [ ] `guides/enterprise-deploy` — same SourcePrep-deploy caveat. Defer or, at minimum, confirm the public-repo links resolve.
- [ ] `guides/dynamic-model-loading` — VRAM-aware loading + unloading flow. Run a build with two configured slots that exceed available VRAM and confirm the docs' described unload/reload cadence.
- [ ] `guides/model-advisor` — *blocked by Phase 130 follow-up #17 (live pricing research).* Don't behavior-check until pricing is refreshed; otherwise feedback will conflate "wrong model" with "stale price".

### Tier E — CLI reference

- [ ] `cli/commands` — every documented command run end-to-end against a sample project. Particularly the four added in Phase 130 (`config`, `drift`, `flow`, `opportunities`).
- [ ] `cli/config` — `PREP_DATA_DIR` override actually works (set to a custom dir, daemon writes there). The Phase 113 migration sentinel — confirm a fresh install lands at `~/.local/share/sourceprep/` with no legacy `./prep_data/` artifacts.

### Tier F — operational

- [ ] `troubleshooting` — each documented symptom + remediation pair. Reproduce the symptom artificially, run the remediation, confirm it resolves. The "ONNX model ~132 MB" claim was fixed in Phase 130 — verify the actual download size on a fresh install.
- [ ] `dashboard` (page) — every panel category claim and the 27-panel count. The Panel Picker copy/paste-layout claim (the actual feature exists, but does paste validate the schema as described?).

## Specific dogfooding tests this phase should automate

Phase 130 caught some of these via direct file reads. Phase 132 can graduate them to actual integration tests.

| Test | Asserts | Source-of-truth |
|------|---------|-----------------|
| Sidebar / sitemap registry | every entry's path resolves to a `page.tsx` under `src/app/` | `apps/docs/src/config/docs.ts`, `apps/docs/src/app/sitemap.ts` |
| Panel-registry docsUrl anchors | every `docsUrl` anchor resolves to an `AnchorHeading id=` on the target page | `packages/ui/src/config/panelRegistry.ts` ↔ `apps/docs/src/app/dashboard/page.tsx` |
| Storybook-id resolution | every `<StoryEmbed storyId=...>` in docs resolves to a real story title + export | `apps/docs/src/app/**/page.tsx` ↔ `packages/ui/src/stories/**/*.stories.tsx` |
| Atlas IDENTITY brand check | structural-only atlas IDENTITY is `SourcePrep`, not the filesystem dir name | `src/prep/core/atlas/generator.py:_build_structural_sections` |
| Active-zones ghost filter | regenerated atlas never lists empty / removed directories | `src/prep/core/git_evidence.py:hot_zones` (added in Issue 13 follow-up) |

A small CI job that runs these against the actual `apps/docs` build would catch most Phase-130-class regressions automatically.

## Definition of done

- Every page in the Tier A–F checklist has a verdict: ✅ verified, ⚠ fixed, or ❌ punted to a product task.
- Three persistent fidelity tests (above) wired into CI so the next round of drift surfaces in PR review, not in user-reported bugs.
- A short "what we found" memo at the bottom of this README listing the top three behavioral-vs-documented gaps as a feedback signal to the broader team.

## Risk / blockers

- Each Tier A and Tier B page costs a real fresh install (Mac, Windows, ideally Linux) and an hour or so of click-through. Plan to batch.
- Tier D guides that involve cloud LLM calls will incur real API spend. Use Phase 119 concurrency-aware paths and the smallest possible models for verification runs.
- Some "claims" are aspirational — they describe a flow that exists in concept but is gated behind incomplete features (especially around Pro/Team tiers). Keep `feature_gate.py` open while reading.
- This phase intersects Phase 131 (storybook curation) — when Phase 131 renames or hides stories, the storyId resolver test (above) will catch it. Coordinate via the same MARKETING_SITE_AUDIT log.

## What this phase is NOT

- Not a redesign. The dashboard rewrite from Phase 130 stands.
- Not a re-tone. Phase 130 trimmed; trimming further is a separate session.
- Not a sweep of the marketing site. Marketing has its own audit doc.
- Not "ship faster" — fidelity is slower than staleness, by design.
