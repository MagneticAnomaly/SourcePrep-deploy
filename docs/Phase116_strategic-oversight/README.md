# Phase 116 — Strategic Oversight (Post-MVP Exploration)

**Status:** Research / exploration. No implementation yet.
**Timing intent:** Post-MVP. Candidate "first buzz feature" after launch.
**Owner:** Eric
**Opened:** 2026-04-17

## The one-sentence pitch

Add an **optional, sparse, high-authority "overseer" LLM** (Opus / GPT-5-class)
that is invoked only at strategically chosen checkpoints in the existing 10-stage
enrichment pipeline — auditing, correcting, or gating outputs from the fast
small-model tier (Kimi / Gemini Flash / Ollama) before they become durable
knowledge.

Think: a **CTO / Overlord / Admin / Sentinel** that reads the room every 1-in-N
decisions, not every decision. Expensive, but a force-multiplier when used
sparingly and well.

## Why this phase exists (and why not yet)

- The **idea is real and promising** — multiple streams of prior art converge
  on the pattern (FrugalGPT cascades, process reward models, Aider architect
  mode, Mixture-of-Agents). We are not inventing from scratch.
- But the **ROI depends entirely on *where* we invoke the overseer**, and we
  don't yet have enough real build data to know which checkpoints actually
  catch errors Gemini Flash misses. The exploration surfaced **12 candidate
  checkpoints** ranked on intuition + code inspection, but intuition is not
  dogfooding data.
- **Pre-MVP risk:** If we ship this before we have a pool of real build outputs
  to measure against, we'll bake in checkpoint choices we can't defend with
  data. Worse, we'd burn Opus budget on false positives.
- **Post-MVP opportunity:** After launch, we'll have a steady stream of builds
  from real projects. That's the dataset we need. *First buzz feature* framing
  means: once we have data, this becomes a visible differentiator — "Prep
  notices when its own reasoning is shaky and escalates to a smarter model."

## What this folder contains

| File | What it is | Status |
|---|---|---|
| [`00_VISION.md`](00_VISION.md) | The abstract idea, post-MVP framing, non-goals, success criteria | Draft |
| [`01_PRIOR_ART.md`](01_PRIOR_ART.md) | Research brief — hierarchical LLMs, LLM-as-judge, escalation, consensus, failure modes, production case studies | Draft |
| [`02_PIPELINE_MAP.md`](02_PIPELINE_MAP.md) | Current 10-stage pipeline: ingests / produces / models / entry points / known weirdness | Draft |
| [`03_CANDIDATE_CHECKPOINTS.md`](03_CANDIDATE_CHECKPOINTS.md) | 12 ranked overseer-invocation candidates with file:line citations + uncertainty gates | Draft |
| [`04_EXISTING_ABSTRACTIONS.md`](04_EXISTING_ABSTRACTIONS.md) | What's already in-tree that a future overseer could extend (guards, manifests, checkpoints, swarm) | Draft |
| [`05_OPEN_QUESTIONS.md`](05_OPEN_QUESTIONS.md) | Judgment calls deferred until data is available | Draft |
| [`06_DOGFOODING_PLAN.md`](06_DOGFOODING_PLAN.md) | **The work we do NOW.** How to collect build-output samples, what to measure, how to manually simulate overseer calls to generate ground truth | Draft |
| [`07_DOGFOODING_LOG.md`](07_DOGFOODING_LOG.md) | Rolling log of observations from dogfooding probes (empty template today) | Template |
| [`08_SURPRISES_AND_FEEDBACK.md`](08_SURPRISES_AND_FEEDBACK.md) | Incidental product findings the exploration turned up — some actionable independent of Phase 116 | Draft |

## Current posture

- **No code changes planned in Phase 116 itself.**
- **No design spec.** We are deliberately staying open-ended until the
  dogfooding data gives us something to design *against*.
- **Parallel tracks allowed:** The surprises in `08_` (e.g., stage-advancement
  regression note, confidence-field inconsistency, silent swarm-worker
  timeouts) are *independent* actionable findings. If any are worth promoting
  to their own mini-phase or patch, do that out-of-band — don't wait on 116.

## When this phase moves from research → design

Trigger: we have **N ≥ 20 real builds** captured with per-stage outputs,
confidence distributions, and known post-hoc errors (user corrections, audit
findings, or manual Opus probes). At that point, we can rank the 12 candidate
checkpoints by measured *actual error rate* instead of guessed blast radius,
and turn the top 3 into a spec.

Until then, `06_DOGFOODING_PLAN.md` is the active document.
