# 05 — Open Questions

Judgment calls deferred. No answers committed yet. Each question has a
*leaning* — where we'd land if forced today — and the data we'd need to
answer it for real. All leanings should be re-evaluated against the
dogfooding pool (see `06_`).

---

## Q1. Blocking vs non-blocking invocation

Should overseer findings block stage advancement, or just annotate the
manifest?

- **Blocking** — Higher trust in outputs, but risk of stalls on
  false-positive flags. Bad early-stage behavior with unreliable rubrics.
- **Non-blocking (async annotation)** — Pipeline always runs to completion;
  findings attach to manifest for post-hoc review or future HITL.

**Leaning:** Non-blocking for v1, **per-checkpoint opt-in to blocking for
hub-file mutations only** (small scope, high stakes). Matches prior art
(async verifier cascades) and limits stall surface.

**Data needed:** Measured false-positive rate per checkpoint over ≥20 runs.
If FP < 10% for hub-file checkpoints, blocking is defensible there.

---

## Q2. Sync, parallel, or fully async persistence

Pipeline is currently synchronous. Overseer calls add 10–30s per decision.

- **Sync in-line** — Simplest. Blocks stage for duration of Opus call.
  Kills throughput at scale.
- **Parallel with next stage** — Checkpoint written before advancing;
  overseer runs while Stage N+1 proceeds. Complicates rollback if
  overseer later disapproves.
- **Fully async background pool** — Fire and forget; findings arrive in
  manifest eventually. Easiest to ship, weakest coupling.

**Leaning:** Fully async background pool for v1. Coupled to Q1 non-
blocking decision — if we're not gating, we don't need the pipeline to
wait.

**Data needed:** P50/P95 overseer latency per checkpoint type. If some
checkpoints are cheap enough (<5s), sync is fine there.

---

## Q3. Invocation budget

How many Opus calls per run are we willing to pay for?

- **Per-run hard cap** — e.g. "no more than 20 Opus calls per build." Forces
  checkpoint ranking; simple to reason about cost.
- **Probabilistic sampling** — Each gated checkpoint fires with probability
  p; p tuned to hit target monthly budget.
- **Dynamic / learned** — Budget allocator scores checkpoints by expected
  value (past catch rate × current uncertainty) and spends until budget
  exhausted. Most sophisticated.

**Leaning:** Per-run hard cap (e.g., 20) with priority-ordered draining:
checkpoints fire in priority order until cap hit, then skip. Easy to
reason about and explain to users.

**Data needed:** Per-checkpoint token cost × frequency × Opus price.
Quick back-of-envelope: if hub-file checkpoint averages 8k in / 2k out
and fires 5×/run, that's ~$0.60 per build at current Opus rates.

---

## Q4. Which model?

Opus? GPT-5? Local Llama-405B? A Prometheus-style dedicated judge?

- **Opus / Claude frontier** — Strongest current judgment; consistent
  with anthropic-adjacent tooling identity; user already paying for
  Claude Code.
- **GPT-5 / OpenAI frontier** — Competitive reasoning; diversifies away
  from single-vendor.
- **Local strong (Qwen-72B, Llama-405B via Ollama)** — Zero per-call cost
  after hardware. Latency + quality tradeoffs.
- **Dedicated fine-tuned judge (Prometheus-style)** — Cheaper, rubric-
  specialized. Requires training data we don't have yet.

**Leaning:** Opus initially. Swap to local strong if we can get
comparable rubric-scoring quality on Phase-116 eval set.

**Constraint from `01_`:** Avoid same-family judge/generator pairs
(Panickssery 2024). Current stack is Kimi (Moonshot) + Gemini Flash
(Google) — Opus (Anthropic) keeps the diversity. **Don't use Gemini-Ultra
as overseer** over Gemini-Flash orchestrator — inherits family bias.

---

## Q5. Rubric format

LLM-as-judge works best with explicit rubrics (Constitutional AI, Prometheus).

- **Free-form "does this look right?"** — Easy but unauditable and biased.
  Avoid.
- **YAML rubric per checkpoint** — Checklist of concrete questions;
  overseer returns per-item score + rationale. Auditable.
- **JSON schema with structured output** — Machine-consumable scores,
  easier to aggregate. Constrains overseer expressiveness.

**Leaning:** JSON schema with structured output. Required fields per
checkpoint: `pass: bool`, `per_rubric_score: dict[str, 0|1|2]`, `rationale:
str`, `suggested_action: enum[approve, flag, re-run, escalate_to_human]`.

**Data needed:** 2–3 rubric iterations against real outputs during
dogfooding to find the concrete items that correlate with catch rate.

---

## Q6. Human-in-the-loop integration

Should humans review overseer flags before they become durable?

- **No HITL** — Overseer findings are authoritative; manifest annotations
  are purely informational.
- **Optional HITL** — UI surface shows overseer flags; user can accept
  or override.
- **Required HITL for blocking checkpoints** — Pipeline halts at certain
  checkpoints until a human approves.

**Leaning:** No HITL in v1. Findings are manifest annotations only. Add a
UI surface in a later phase once we have data on which findings are
actually worth surfacing.

---

## Q7. Fallback / degradation

What happens when the overseer is unavailable (rate limit, network,
provider outage)?

- **Halt pipeline** — Safe but kills throughput for transient outages.
- **Continue with warning** — Manifest marked "overseer check skipped."
  Pipeline proceeds with the fast-tier output.

**Leaning:** Continue with warning. Overseer is advisory; a missing
advisor shouldn't block the work.

---

## Q8. Naming

(From `00_VISION.md`, unresolved.) Current candidates: Overseer, CTO,
Arbiter, Sentinel, Sage, Council, Reviewer, Inspector. Each has
connotations.

**Leaning:** **Sentinel** — watches for trouble, neutral tone, plays well
with existing "immune system / antibodies" metaphor.

---

## Q9. Framework vs point integrations

Build a generic gate abstraction, or hand-wire each checkpoint?

- **Framework** — `OverseerGate` + `CheckpointRegistry` + `Rubric`
  abstractions. More upfront work; scales to 12 checkpoints cleanly.
- **Point integrations** — Hand-write the top-3 checkpoints directly
  in stage code. Ships faster; creates duplication; refactor debt if
  we add a 4th.

**Leaning:** Framework, but a *minimal* one. Just enough abstraction to
make adding the 4th checkpoint trivially cheap. Resist over-design.

---

## Q10. Dogfooding data retention

How long do we keep overseer traces for analysis?

- **Per-run only** — Stored alongside the manifest; gone on reset.
- **Project-persistent** — In the per-project SQLite; survives across
  runs for trend analysis.
- **Global research log** — Dedicated append-only log across all projects
  for pattern mining.

**Leaning:** Project-persistent for findings, global research log for
meta-analysis (opt-in; privacy-sensitive — concept assertions may
contain proprietary domain info).
