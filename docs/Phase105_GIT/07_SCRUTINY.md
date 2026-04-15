# 07 — Scrutiny Pass (2026-04-14)

Preserved so future readers see why Phase 105 scope shrank. The original
brainstorm proposed a four-tier plan (T0–T3) culminating in a concept
promotion pipeline. A deliberate scrutiny pass cut it back to what
became **Option β**: ship one primitive + one safe integration.

## What held up under scrutiny

- **`roadmap_miner` is live.** Invoked from
  `src/codrag/api/routers/roadmap.py:665` with user-visible CRUD in
  `src/codrag/dashboard/src/hooks/useRoadmapSystem.ts`. The roadmap view
  has real users. Improving its signal quality is a real payoff.
- **`git_evidence.py` as a clean read-only module** is the right shape.
- **JSON cache + HEAD-signature** remains right (SQLite WAL unreliable
  on the 4TB-BAD USB dev machine per memory).
- The existing-infrastructure audit in `01_EXISTING_INFRASTRUCTURE.md`
  is accurate.

## What cracked

1. **Surface area was under-reported.** `RoadmapNode` has more
   downstream consumers than the brainstorm acknowledged:
   - `core/sprint_intelligence.py` scores nodes. The "churn boosts
     priority" integration would have competed with an existing scorer
     instead of integrating with it.
   - `core/github_push.py` pushes nodes to GitHub as issues. **Auto-
     retiring a pushed node silently diverges local state from an open
     GitHub issue.** This was never addressed in the original plan.
   - `core/audit/opportunity_manager.py` is a sibling "opportunities"
     surface adjacent to the roadmap. Adding new signal producers
     risks duplicate surfacing.

2. **"Three modified files" was false.** Honest count for T1 including
   scorer coordination, GitHub-push policy, and opportunity de-dup:
   5–7 files plus a real retire-vs-keep-issue-open product decision.
   Not fatal, but the "small surface" claim masked it.

3. **Drift from the user's literal pain point.** The conversation
   started at the Untraced scope panel. The tiered plan designed
   nothing for that surface and instead grew into a fusion-engine
   upgrade.

4. **"Triangulation" framing was marketing-speak.** Sounded pretty,
   added zero engineering value. Removed.

5. **"0/366 concepts ratio" thesis was a guess.** No evidence that
   seeds were ever *meant* to auto-promote. They may exist as
   candidates humans curate by design. T2's "pulse" narrative rested
   on that assumption without verification.

6. **Co-change coupling: real but oversold.** Industry use (Microsoft
   et al) confirms the pattern is meaningful. However, most pairs in
   any repo are trivial (code+test, code+doc). Expected yield after
   tight filters is 3–5 meaningful pairs per project, not a flood.
   Worth doing eventually; not worth leading with.

## Why Option β is the honest answer

The single integration that survives every concern above is **TODO
churn gating**:

- No coupling with `sprint_intelligence` — adjusts one input (priority),
  the scorer naturally respects it.
- No coupling with `github_push` — we never retire a node, never touch
  the GitHub issue stream.
- No coupling with `opportunity_manager` — we don't emit new node
  types.
- No `RoadmapNode` schema change — no migration risk.
- No keyword-matching heuristic — just a boolean "file churned in
  window" check.
- Only one new git primitive required (`recent_churn_by_file`); other
  primitives (`cochange_pairs`, `commit_message_index`) can be added
  later when consumers exist.

The visible payoff is real: dead TODOs in un-touched files stop
polluting the roadmap; live TODOs in active files keep their rank. That
is the cleanest demonstration that git evidence is a trustworthy signal
before we make bigger bets on it.

## Path-forward principle adopted

**Earn each next integration with dogfood evidence from the previous
one.** Do not design the full ladder up front. Each phase ships a
self-contained value increment; the decision to build the next is
informed by the observed quality of the last.

See `06_FUTURE_PATH.md` for the sequenced list.

---

## Addendum — β → γ upgrade (same session, later pass)

After the β doc set was complete, a second pass asked: *can git
evidence be leveraged earlier in the pipeline, or in the Atlas?*

**What the probe revealed:**

- The pipeline has 15 stages in 3 groups of 5 (`stages.py`). Stages 2
  and 3 (`INFERRED_EDGES`, `CATALOGUE`) are LLM stages — expensive.
  Adding git work there doesn't save anything; the natural slot for a
  deterministic producer is between STRUCTURAL (1) and INFERRED_EDGES
  (2) as a new stage.
- The Atlas (stage 11) is a uniquely high-leverage consumer. Its
  output is embedded into AGENTS.md and the ambient `codrag()` MCP
  response. **One atlas enrichment → three surfaces get smarter** at
  zero extra integration cost.
- A new pipeline stage carries risk because the memory-flagged
  sequencing bug is still outstanding. Better to prove the signal with
  on-demand consumers first.

**The upgrade decision.** Add the Atlas as a second on-demand consumer
(Option γ) without promoting `git_evidence` to a pipeline stage. Ship:

- TODO churn gating (β deliverable, unchanged)
- Atlas hub classification (stable / evolving / fragile)
- Atlas "active zones" line

**Key guard rail discovered during this pass.** The Atlas must not
become a stats dump. Labels only, no raw numbers. Token-growth
acceptance gate set at < 50 tokens.

**What did not change.** The module design, cache layout, exclusion
list, error-handling, and sequencing-risk posture are identical
between β and γ. γ adds two helpers (`classify_hub`, `hot_zones`) and
one more consumer integration site.

**Promotion to pipeline stage (δ) explicitly deferred.** The "new
stage" architectural option was reconsidered and pushed to Phase 106.
Rationale: unlock it only after γ dogfood proves that multiple
consumers would benefit — at which point the sequencing-bug risk is
justified by the leverage.
