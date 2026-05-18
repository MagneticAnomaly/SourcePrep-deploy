# Phase 140 — Prompt Dogfooding

**Started:** 2026-05-17
**Status:** Active (long-term)
**Owner:** Eric Bintner

## Goal

Audit the *content* of every LLM prompt SourcePrep ships, then iterate one prompt at a time, rebuild, and compare outputs across multiple repos. The goal is not to ship a faster pipeline or fix a particular bug — it is to make every prompt do its job better, with attributable changes and durable evidence.

## Why this phase exists

Earlier dogfooding phases tackled different surfaces:

| Phase | What it audited | What it left alone |
|---|---|---|
| **Phase82** (`MCP-Dogfooding`) | UX of *calling* MCP tools | Prompt content inside the tools |
| **Phase83** (`MCP-Dogfooding-External`) | Cross-IDE adapter behavior | Prompt content |
| **Phase122** (`FeatureUtilizationAudit`) | What's wired vs dormant | Quality of wired LLM output |
| **Phase125c** (`QualityCheckedConceptSwarm`) | Concept-pipeline *architecture* | Prompt copy itself, head-to-head |
| **Phase136** (`Dogfood-fixes`) | Atlas/search/impact *behavior* (classifier, projection) | The prompts feeding those behaviors |

Phase 140 takes the next step: **the prompt text itself is the object of study.** We assume the pipeline is wired and the architecture is correct, and we ask whether the LLM is being asked the right thing in the right way.

## Scope

In scope:
- The ~30 LLM prompt sites cataloged in [`01_Inventory.md`](./01_Inventory.md).
- Their grounding (what context is fed in).
- Their output schemas (what we expect back).
- The downstream artifacts they produce (atlas docs, concepts, audit reports, agent role files, AGENTS.md).

Out of scope:
- Pipeline orchestration (Phase125c, Phase134).
- Embedding quality (Phase139).
- MCP tool dispatch / classifier routing (Phase136).
- Cloud LLM concurrency tuning (Phase82-derived auto-discovery).

If a prompt change requires touching orchestration, that work belongs to a child phase or a separate ticket — Phase140 stays focused on prompt copy + grounding + schema.

## How to use this phase

1. Read [`00_Methodology.md`](./00_Methodology.md) — the five non-negotiables and the snapshot/iteration protocol.
2. Skim [`03_PromptEngineeringGrounding.md`](./03_PromptEngineeringGrounding.md) — the research canon. Iterations should cite sources from here when possible.
3. Browse [`01_Inventory.md`](./01_Inventory.md) — pick a prompt site to audit (or follow [`04_Roadmap.md`](./04_Roadmap.md) for the recommended sequence).
4. Open the corresponding [`prompts/<site>.md`](./prompts/) page — fill in the snapshot, then propose an iteration.
5. Capture outputs under [`snapshots/<date>_<label>/outputs/<site>/<repo>.json`](./snapshots/).
6. Record verdict (`kept` / `reverted` / `partial`) at the bottom of the site page.

## Files in this phase

- [`README.md`](./README.md) — you are here
- [`00_Methodology.md`](./00_Methodology.md) — protocol (5 non-negotiables, snapshot+iteration loop)
- [`01_Inventory.md`](./01_Inventory.md) — master table, 30 sites grouped by family
- [`02_TestRepos.md`](./02_TestRepos.md) — curated test-repo slots
- [`03_PromptEngineeringGrounding.md`](./03_PromptEngineeringGrounding.md) — research canon mapped to our prompt patterns
- [`04_Roadmap.md`](./04_Roadmap.md) — sequencing recommendation; Sprint 1A/1B/2 proposals
- [`prompts/`](./prompts/) — one page per prompt site
- [`snapshots/`](./snapshots/) — captured outputs per site × per repo

## Cross-references

- [Phase 82 — MCP Dogfooding](../Phase82_MCP-Dogfooding/) (tool UX)
- [Phase 83 — MCP Dogfooding External](../Phase83_MCP-Dogfooding-External/) (external IDE adapters)
- [Phase 122 — Feature Utilization Audit](../Phase122_FeatureUtilizationAudit/) (wired vs dormant)
- [Phase 125c — Quality-Checked Concept Swarm](../Phase125c_QualityCheckedConceptSwarm/) (concept pipeline architecture)
- [Phase 136 — Dogfood Fixes](../Phase136_Dogfood-fixes/) (search/atlas/impact behavior fixes)
- [Phase 139 — Embedder Memory Hardening](../Phase139_EmbedderMemoryHardening/) (embedding stack — not prompts)

## Status snapshot

| Bucket | Count | Status |
|---|---|---|
| Prompt sites inventoried | 30 | ✅ baseline captured 2026-05-17 |
| Sites with at least one repo's outputs captured | 14 | ✅ Slot B (PowerMateReborn) — see [`snapshots/2026-05-17_baseline/capture-notes.md`](./snapshots/2026-05-17_baseline/capture-notes.md) |
| Sites with at least one iteration entry | 1 | `rules-agents-md` (stale-branding finding) |
| Sites marked `stable` | 0 | — |

See [`01_Inventory.md`](./01_Inventory.md) for the per-site status table.
