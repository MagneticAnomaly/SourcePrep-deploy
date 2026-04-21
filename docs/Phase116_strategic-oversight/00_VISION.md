# 00 — Vision

## The shape of the idea

Today, the Prep enrichment pipeline is a tiered LLM system:

- **Workers** — small fast models doing narrow tasks in parallel
  (Kimi reasoning on code snippets, embedding models running locally).
- **Orchestrator** — a mid-tier model consolidating worker outputs
  (Gemini 3 Flash via Ollama in our current setup).
- **(Proposed) Overseer** — a frontier model (Opus, GPT-5, or equivalent)
  invoked **sparingly** at strategically chosen moments to audit, gate, or
  correct the orchestrator's decisions.

The overseer is not a replacement for the orchestrator. It is a *sparse
consultant*. It shows up when something load-bearing is happening, reads the
artifact, asks "does this actually make sense?", and either approves or flags.

## The instinct behind it

Every tier has error modes. Kimi workers confabulate plausible-but-wrong
details from limited context. Gemini Flash orchestrators paper over worker
disagreement with smooth prose. These errors compound quietly through 10
stages. At no point does a more capable model look at the output and ask "is
this right?" — so small errors become durable knowledge, concepts, antibodies,
atlas shape.

The overseer pattern says: **the cost of one Opus call every 10-20
orchestrations is trivial compared to the cost of an incorrect concept
persisting for the life of the project.**

## Success criteria (qualitative, for now)

A successful Phase 116 deployment, post-launch, looks like:

1. **Catches real bugs.** Over a pool of 20+ builds, the overseer flags
   specific orchestrator outputs as wrong, and we can confirm (via manual
   inspection or user reports) that they were indeed wrong.
2. **Doesn't cry wolf.** False-positive rate on overseer flags stays below
   ~20% — otherwise users stop trusting the signal.
3. **Stays in budget.** Opus cost per run remains a single-digit % of
   pipeline cost. Sparse means sparse.
4. **Ships as a story.** "Prep escalates to a smarter model when its own
   reasoning is shaky" is a differentiator worth demoing — only competitors
   doing anything similar in public are Aider (architect mode) and some
   gated-escalation startups. Most agents still run flat.

## Non-goals

- **Not a human-in-the-loop UI (yet).** The overseer is another LLM, not a
  request for human approval. A future phase may add HITL; this one doesn't.
- **Not a replacement for the orchestrator.** Gemini Flash continues to do
  95%+ of the consolidation work. Opus only shows up when gated in.
- **Not a training loop.** We are not using overseer outputs to fine-tune the
  smaller models in Phase 116. That's a separate (interesting) future phase.
- **Not every stage.** Some stages (structural walk, embeddings) have no
  judgment to oversee. Only stages that produce *interpretive* outputs
  warrant a checkpoint.
- **Not synchronous / blocking by default.** Initial form is async annotation
  into the manifest; pipeline proceeds. Blocking behavior is optional and
  per-checkpoint.

## What "strategic" means in this context

The user's framing was exact: Opus is expensive. We can task it with many
things. The question is **which of those many things produce the most value
per call**. Strategic = "invoked where the marginal benefit per dollar is
highest."

The 12 candidate checkpoints in `03_CANDIDATE_CHECKPOINTS.md` are ranked
precisely on that axis: blast radius × error likelihood × ease of gating.

## Naming (open)

The working metaphor is executive-role: CTO, Overlord, Admin, Sentinel, Sage,
Council, Reviewer, Arbiter, Inspector. Each carries connotations:

- **Overseer** — neutral, accurate, slightly surveillance-y
- **CTO** — strategic, architectural, a bit corporate
- **Arbiter** — adjudicates conflicts, good for disagreement-gated triggers
- **Sentinel** — watches for trouble, good for audit-heavy framing
- **Sage / Council** — advisory, softer, less authoritarian
- **Admin / Overlord** — authoritative but too top-down for a *sparse*
  reviewer
- **Auditor** — collides with existing `prep_audit` tool; avoid.

Decision deferred. `strategic-oversight` is the current *phase* name, not the
*feature* name.
