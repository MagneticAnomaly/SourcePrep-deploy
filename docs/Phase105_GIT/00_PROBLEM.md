# 00 — Problem and Insight

## What set this off

Eric was looking at the **Graph Scope panel → Untraced** view and noticed
a group of files that had no obvious explanation for being there — just
noise. The intuition: when N files land in the untraced bucket at once,
that's not N unrelated events, it's almost always a commit, a pull, or a
branch switch. Git knows what happened. CoDRAG does not.

That was the seed. The conversation broadened from "detect commits in the
watcher queue" to the real question: **where else in CoDRAG would commit
history turn noise into signal?**

## The observation that matters

Today, `todo_scanner.py` treats every TODO identically. A `# TODO: revisit
this` in a file untouched for 18 months has the same weight as one in a
file churned 20× this month. The first is archaeology; the second is a
live signal. Without git churn data, the scanner cannot tell them apart.

That single observation — "file churn disambiguates live TODOs from
dead ones" — is the concrete, verifiable problem Phase 105 solves.

An earlier draft of this document called out a broader "past/present/
future triangulation" thesis about fusing git history into the whole
roadmap engine. After a scrutiny pass (`07_SCRUTINY.md`), that broader
framing was dropped as over-reach. The narrow TODO-gating claim is
what survives, because it is the one claim that does not couple with
`github_push.py`, `sprint_intelligence.py`, `opportunity_manager.py`,
or the dormant concept-promotion pipeline.

## The wins Phase 105 ships

After a second scrutiny pass, two consumers survived: the original
TODO gate, plus Atlas hub & hot-zone decoration. Both are on-demand
module calls. Both fail open if git evidence is unavailable. Neither
requires a new pipeline stage.

**1. Gate TODO significance with churn.** A TODO in a file untouched
for 180 days gets demoted to P3 with a "[stale: file not touched in
180d]" note. A TODO in an actively-churning file keeps its rank.

**2. Label Atlas hubs by churn.** The Atlas hub line groups hubs by
`stable | evolving | fragile` instead of emitting raw edge counts. A
new "Active zones" line lists the 3–5 most-churned directories.
Labels, not numbers. The Atlas text grows by < 50 tokens total.

**The leverage:** Atlas output is embedded into AGENTS.md and the
ambient `codrag()` MCP response. One atlas enrichment propagates
automatically to every AI agent and to the dashboard Atlas panel.
Three surfaces benefit from one integration point.

## Wins considered and deferred

These were in earlier drafts. Each was cut for a specific reason
captured in `02_SCOPE.md` and `07_SCRUTINY.md`; each has an unlock
condition documented in `06_FUTURE_PATH.md`:

- **Retire completed roadmap nodes** via commit-message matching
  (cut: couples with `github_push.py` — retiring a pushed node
  diverges from an open GitHub issue).
- **Co-change coupling as a roadmap source** (cut: couples with
  `opportunity_manager.py`; expected yield small relative to
  integration cost).
- **Churn × centrality confidence boost** (cut: competes with existing
  `sprint_intelligence.py` scorer).
- **Concept promotion pipeline** (cut: rests on unverified assumption
  that the concept store was designed for auto-promotion).

## Why "write git integration" is the wrong framing

The natural first instinct was *"let's detect commits in the watcher
queue and make indexing diff-driven."* That is a real optimization, but
it is a **performance** framing. The bigger opportunity is **semantic**:
git history is a rich signal stream that upgrades the quality of
suggestions CoDRAG is already trying to make.

Phase 105 therefore scopes itself to the semantic side. The watcher
stays untouched. Git evidence is pulled on demand by consumers that
benefit from it.

## Success criteria

Specific, verifiable. No philosophical proxies.

**TODO gate:**
- At least one TODO on this repo is correctly demoted for being in a
  cold file (Eric confirms by eyeball).
- Zero live TODOs are incorrectly demoted.
- No regression outside a git repo or on a shallow clone.

**Atlas decoration:**
- Hub line contains ≥ 1 `stable` and ≥ 1 `evolving` label matching
  reality on this repo.
- "Active zones" line lists ≥ 2 directories where recent work is
  actually happening.
- Atlas token growth < 50 tokens vs baseline.
- With `atlas_decoration=false`, atlas output matches baseline
  byte-for-byte.

**Module:**
- Churn cache refresh < 2 seconds on this repo.

Full list in `02_SCOPE.md` → Acceptance Gates.
