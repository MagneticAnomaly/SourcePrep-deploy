# R7 — Automatic Observation: Growing the Graph Without Agent Initiative

**Goal:** Capture observations automatically via PostToolUse hooks so the knowledge graph grows even when agents don't voluntarily write to it.
**Time budget:** 1 week
**Decision at end:** ship auto-capture hook, or skip and stay manual.

## Core question

Scrutiny (06) identified a structural problem: **MCP is read-biased. Agents read `codrag_*` tools all day but rarely call `codrag_observe`.** The "shared brain" promise is consumer-heavy, producer-starved. Without a write-incentive layer, the graph stagnates. Can we fix this by having the hook layer capture observations automatically?

## Hypothesis

**H1:** A lightweight PostToolUse hook that writes a minimal observation per `Edit`/`Write` tool call (file touched, rough diff summary, tool sequence used) grows the observation store 10–100× faster than manual capture.

**H2:** Most auto-captured observations are low-signal individually but aggregate into patterns — which become seed candidates for R5's promotion pipeline.

**H3:** Cost is acceptable: <100ms per hook invocation, <1MB/day of observation storage per active developer.

## Literature check

- **Claude Code hooks reference** — PostToolUse is standard; execution model well-defined.
- **arxiv 2505.18279 Collaborative Memory** — captured memory with access control is a design pattern.
- **Zep / MAGMA** — both assume a write-capture layer; neither requires agent initiative.

## What an auto-captured observation looks like

Minimal shape:

```yaml
id: obs-2026-04-13-7421
captured_at: 2026-04-13T21:07:15Z
captured_by: hook:post-edit
session_id: claude-code-session-abc123
file: src/codrag/services/pipeline/resume.py
tool: Edit
event: edit
diff_summary: "added 12 lines, removed 4 lines in resume_pipeline()"
context:
  preceding_tools: [Grep, Read, Read, Edit]
  task_hint: "fix pipeline resume bug"  # from Claude Code transcript if available
tags: [pipeline, resume]  # from file's module tags
```

Note: **no full diffs stored.** Just a summary. Full diff is in git; our job is the pattern signal.

## Experiment

**Step 1 — Implement (2 days):**
- `codrag hook post-edit <file>` CLI subcommand.
- Writes observation to `codrag_data/observations/` in JSONL format (append-only).
- Integrate with our existing `codrag_observe` write path so dashboard sees auto-captures.

**Step 2 — Install and run (3 days):**
- Opt-in installation via `codrag install --auto-capture`.
- Install on CoDRAG's own repo, let me/the team work normally for 3 days.
- Measure observation volume, storage cost, latency impact.

**Step 3 — Value analysis (2 days):**
- How many observations captured per hour of active development?
- How many form clusters (same file edited repeatedly, same tool sequence)?
- How many of those clusters become seed-promotion candidates (R5 pipeline)?
- How many hooks fire with no useful signal (pure noise)?

## Proposed filters

Auto-capture should not write observations for trivial events. Filter out:

- Edits to files classified as AGENT_DIRECT (F0 exclusion policy — don't observe our own output).
- Edits to `docs/` unless specifically marked observable.
- Tool sequences under 3 steps (too short to be a pattern).
- Duplicates within 60 seconds (debounce).

## Signal extraction

An observation by itself is low-value. **Observations become useful when clustered.** Run periodic (daily) clustering:

- Group observations by file → spots hot files and frequent-edit patterns.
- Group by tool sequence → spots workflow patterns (read→read→grep→edit is different from grep→edit).
- Group by session → captures intent-sequences ("user was debugging auth").

Clusters above a threshold become seed candidates: *"User repeatedly edited `pipeline/resume.py` after error in tests. Observation pattern suggests a concept about test-guided debugging flows for pipeline code."*

This is where observations re-enter the R5 promotion pipeline.

## Privacy and consent

**Default: off.** Auto-capture is opt-in per project. Users enable via `codrag install --auto-capture` or a dashboard toggle.

**Retention:** 30 days default. Configurable. After retention, raw observations are deleted; clusters derived from them persist.

**Scope:** project-local by default. Cross-project observation sharing requires explicit opt-in (future work; cf. arxiv 2505.18279).

## Simplicity audit

Can we get observation capture without hooks? Two alternatives:

- **Periodic polling** (every 15 min, look at git status, write observations). Loses tool-sequence signal.
- **Manual only**. Fails — that's today's 366-seeds-0-active state.

Hooks give us cheap, real-time, tool-sequence-aware capture. They're the right fit.

The risk is scope creep — turning auto-capture into a full observability platform. Keep the captured fields to the five above. Don't add request tracing, LLM-output logging, session replay. Those are different products.

## Decision

**Path 1 — Clear signal:** Auto-capture produces ≥10× manual observation rate and clusters yield ≥3 promotion candidates in the test period. Ship.

**Path 2 — Noise dominates:** Lots of captures, few clusters. Tune filters harder, retest. If still noisy after tuning, ship only as an opt-in power-user feature.

**Path 3 — Capture rate low:** Hook fires rarely because developers use Task-dispatched subagents (parent hook misses subagent edits). Investigate hook coverage; may need to install hooks inside generated subagents too.

## Dependencies

- F0 (exclusion policy) must be in place so we don't auto-capture our own output.
- R5 must be running so clusters feed an active pipeline.

## Success criteria

- ✅ Auto-capture hook implemented and opt-in installable.
- ✅ Observation rate 10–100× manual.
- ✅ <100ms p95 hook latency.
- ✅ <1MB/day storage per developer.
- ✅ Clustering produces ≥3 seed-promotion candidates per week on CoDRAG's own repo.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R7_results.md`:
- Hook implementation notes.
- Capture rate, storage cost, latency data.
- Clustering examples.
- Recommendations on default filters.
- Connection to R5 promotion pipeline with concrete examples.
