# Phase 87 — Codebase Immune System: Proactive Architectural Defense

**Date:** 2026-04-08
**Status:** Design finalized
**Scope:** Transform concepts and observations into active defenses ("antibodies") that detect and warn about architectural violations in real-time, shifting CoDRAG from reactive intelligence to proactive guardian
**Dependencies:** Phase 84 (concepts formalization — antibodies derive from structured concepts), Phase 83 (audit structural mode — violation detection logic is reused)
**Predecessor:** Phase 82 doc 15 (Codebase Immune System)

---

## Executive Summary

Phases 83-86 make CoDRAG smarter about answering questions and enriching findings. Phase 87 makes CoDRAG **proactive** — it watches for problems before anyone asks.

The metaphor is a biological immune system:
- **Innate defense:** Structural checks that are always true (circular dependencies are bad, extreme hub concentration is risky). These exist today in the audit tool.
- **Adaptive defense:** Learned protections specific to this codebase, derived from concepts and observations. "Pi Agent must never import LLM libraries." "The dashboard state should never poll the API directly." These are **antibodies** — (pattern, response) pairs that activate when violated.
- **Surveillance:** The file watcher monitors changes and checks them against active antibodies in real-time.
- **Alerts:** When a violation is detected, the system surfaces it through the appropriate channel — ambient context injection, MCP notification, dashboard warning.

The immune system doesn't block anything. It **informs**. Everything is overridable. The goal is to prevent accidental architectural drift, not to gatekeep commits.

---

## User Flow

The immune system should feel like a **helpful colleague who remembers things**, not a CI gate that blocks you. Here's how it fits into daily work:

### 1. Concepts Accumulate Naturally
Developers and AI agents create concepts as they work. "This module should never depend on X." "State comes from SSE, not polling." These build up organically — no dedicated "concept creation session" required.

### 2. Antibodies Are Suggested, Not Demanded
When a constraint concept is saved, CoDRAG suggests: "Want to enforce this?" The developer can accept (creates antibody in testing mode), dismiss, or ignore. No mandatory step, no friction.

### 3. Alerts Surface Passively
Developers don't go looking for violations. They appear where you already are:
- **AI agents:** Call `codrag()` to orient → see "2 warnings since your last session" at the top of ambient context. The agent factors it into its work.
- **Dashboard:** Subtle warning indicators on affected files in the trace visualization. Not a modal, not a popup — a visual signal you notice when you're already looking.
- **No interruptions:** Nothing pops up during editing, nothing blocks saves or commits.

### 4. Resolution Is Lightweight
- **In dashboard:** Click to dismiss, snooze, or resolve. One action, not a form.
- **AI agents:** Acknowledge and either fix or explain why it's intentional. The agent decides.
- **Override is always available:** "Yes, I know, this is intentional" is a valid response. The antibody records it and moves on.

### 5. The System Learns What Matters
- Antibodies that trigger constantly and get dismissed → probably too noisy. Surface in antibody health metrics so the developer can tune or disable.
- Antibodies that catch real mistakes → earn trust, justify the system's existence.
- Antibody health is visible in the dashboard — trigger frequency, dismiss rate, false positive rate.

### Key UX Principle
No mandatory screens. No forced acknowledgments. No modals. Information appears where you already are. The immune system is ambient — it adds context to things you're already doing, it doesn't create new workflows to manage.

---

## Design

### What Is an Antibody?

An antibody is a runtime defense derived from a concept or observation. It has three parts:

```
Antibody:
  id: uuid
  name: string                    # Human-readable identifier
  source: ConceptRef | ObservationRef  # Where this antibody came from
  trigger: Trigger                # What change pattern activates this antibody
  response: Response              # What happens when activated
  severity: enum                  # inform | warn | review
  status: enum                    # active | disabled | testing
  created_at: datetime
  last_triggered: datetime | null
  trigger_count: int
  dismiss_count: int              # Track how often alerts are dismissed (noise signal)
```

### Trigger Types

| Trigger Type | What It Watches | Example |
|-------------|----------------|---------|
| **import_added** | A new import statement in a specific file/module | `{type: "import_added", target: "src/codrag/pi_agent.py", pattern: "llm_client\|openai\|anthropic"}` |
| **file_created** | A new file in a specific directory | `{type: "file_created", target: "src/codrag/core/", pattern: "*.generated.*"}` |
| **file_modified** | Any change to a specific file | `{type: "file_modified", target: "src/codrag/mcp_tools.py"}` |
| **dependency_added** | A new edge in the trace graph | `{type: "dependency_added", from: "dashboard/*", to: "core/llm_*"}` |
| **symbol_removed** | A public symbol is deleted or renamed | `{type: "symbol_removed", target: "src/codrag/mcp/server.py", pattern: "tool_*"}` |
| **coupling_threshold** | A file's dependent count exceeds a limit | `{type: "coupling_threshold", target: "src/codrag/mcp/server.py", max_dependents: 30}` |
| **pattern_match** | A regex matches in modified file content | `{type: "pattern_match", target: "src/codrag/pi_agent/**", pattern: "import requests\|aiohttp"}` |

### Response Types

| Response Type | Behavior | Example |
|--------------|----------|---------|
| **ambient_inject** | Add a warning to the next `codrag()` ambient context call | "Warning: recent change to pi_agent.py added an LLM import — Pi Agent is designed as zero-LLM" |
| **audit_finding** | Generate a finding in the next `codrag_audit()` structural scan | Finding with concept reference and violation details |
| **observation_auto** | Automatically save an observation recording the violation | "2026-04-07: LLM import detected in pi_agent.py — violates zero-LLM concept" |
| **dashboard_badge** | Show a warning indicator on the file in the dashboard | Visual signal in trace visualization (subtle, not modal) |

### Severity Escalation

| Level | Meaning | What the Agent/Developer Sees |
|-------|---------|-------------------------------|
| **inform** | Soft guidance — FYI | Brief note in ambient context. Suppressed after first delivery per session. |
| **warn** | Should consider — likely violates an architectural decision | Prominent warning in ambient context. Persists until acknowledged. |
| **review** | Stop and evaluate — strong signal this is a mistake | Review block in ambient context with concept reference. Persists until resolved. |

All levels are **informational only**. Nothing is blocked. Never.

### Antibody Derivation

#### From Concepts (Phase 84)

Every concept with category `constraint` or `architecture` is a candidate:

```
Concept: "Pi Agent must never import LLM client libraries — zero-LLM architecture"
  category: constraint
  anchors: [{type: file, target: "src/codrag/pi_agent.py"}]
  
  → Suggested Antibody:
    trigger: {type: "import_added", target: "src/codrag/pi_agent.py", pattern: "llm_client|openai|anthropic|ollama"}
    response: {type: "ambient_inject", message: "Zero-LLM violation: ..."}
    severity: review
    status: testing  ← always starts in testing mode
```

**Derivation modes:**
- **Manual** — developer explicitly creates an antibody from a concept
- **Suggested** — CoDRAG suggests when a constraint concept is created. Developer accepts/dismisses.
- **Auto-derived** — for simple constraint concepts (import restrictions, file presence rules), CoDRAG generates the antibody automatically into testing mode. Human reviews before activating.

#### From Observations (Patterns of Past Problems)

When observations reveal recurring issues:

```
Observation history:
  "2026-03-01: server.py complexity increased after adding search handler"
  "2026-03-15: server.py complexity increased after adding concepts handler"  
  "2026-04-01: server.py complexity increased after adding enrichment handler"
  
  → Pattern detected (3+ similar observations threshold met)
  → Suggested antibody:
    trigger: {type: "file_modified", target: "src/codrag/mcp/server.py"}
    response: {type: "ambient_inject", message: "server.py has grown with each new tool handler. Consider extracting to a per-tool module."}
    severity: inform
    status: testing
```

Observation-derived antibodies are **always suggested, never auto-activated.** Requires 3+ similar observations before suggesting (conservative threshold to avoid noise).

### The Four Layers

```
┌─────────────────────────────────────────────┐
│  Layer 4: ALERTS                            │
│  ambient_inject | audit_finding |            │
│  observation_auto | dashboard_badge          │
├─────────────────────────────────────────────┤
│  Layer 3: SURVEILLANCE                      │
│  File watcher → change detection →           │
│  antibody matching → trigger evaluation      │
├─────────────────────────────────────────────┤
│  Layer 2: ADAPTIVE DEFENSE (antibodies)     │
│  Derived from concepts + observations        │
│  Project-specific learned protections        │
├─────────────────────────────────────────────┤
│  Layer 1: INNATE DEFENSE                    │
│  Structural checks: cycles, coupling,        │
│  hub concentration, module boundaries        │
│  (Already exists in audit structural mode)   │
└─────────────────────────────────────────────┘
```

### Integration Points

**With file watcher (`src/codrag/core/watcher.py`):**
1. File change detected → watcher notifies index updater AND immune system
2. Immune system evaluates matching antibodies (indexed by target file/directory for O(1) lookup)
3. Triggered antibodies queue their responses
4. Responses delivered on the next relevant MCP tool call

**Fallback when daemon isn't running (direct MCP mode):**
Antibodies evaluated lazily on the next `codrag_audit()` call instead of real-time. Degraded but functional.

**With ambient context (`codrag()`):**
Check for queued alerts. Inject at the top under "Recent Warnings" section. Max 3 alerts per call, prioritized by severity. Inform-level alerts suppressed after first delivery per session.

**With audit (`codrag_audit()`):**
Antibody violations included in structural mode as their own category: "concept_violation" or "observation_pattern".

**With concepts (`codrag_concepts()`):**
When a new concept with category `constraint` is saved, prompt: "This constraint could be enforced as an antibody. Generate one?" Creates in testing mode if accepted.

### Antibody Management via MCP

```
codrag_audit(action="antibodies")                              → list all active antibodies
codrag_audit(action="antibodies", status="testing")            → list antibodies in testing mode
codrag_audit(action="antibodies", id="...", status="disabled") → disable an antibody
codrag_audit(action="antibodies", id="...", status="active")   → activate after testing
```

### Antibody Health Metrics

Visible in dashboard:
- **Trigger frequency** — how often does this fire?
- **Dismiss rate** — how often do people ignore it? (high = probably too noisy)
- **False positive rate** — triggered but the change was intentional
- **Concept coverage** — what percentage of constraint concepts have antibodies?

### Git Hook (Opt-In)

Optional pre-commit hook that runs antibody evaluation:
- **Always exits 0** — advisory only, never blocks a commit
- **Prints warnings** to stderr for any triggered antibodies
- **Opt-in only** — not installed by default, documented clearly
- Consistent with "never block" principle

---

## Implementation Plan

### Stage 1: Antibody Data Model & Storage

**New file:** `src/codrag/core/antibodies.py`

**What to build:**
1. Antibody dataclass with all fields (trigger, response, severity, status, dismiss_count)
2. Trigger type definitions (import_added, file_created, etc.)
3. Response type definitions (ambient_inject, audit_finding, etc.)
4. Storage: alongside concepts/observations
5. CRUD operations: create, read, update, disable
6. Index by target file/directory for fast lookup

### Stage 2: Concept → Antibody Derivation

**Files to modify:**
- `src/codrag/core/concepts.py` (Phase 84) — Hook into concept creation

**What to build:**
1. Constraint concept analyzer: can we auto-derive an antibody?
2. Import-restriction antibody generator (most common pattern)
3. File-presence antibody generator
4. Suggestion flow: concept saved → analyze → suggest → testing mode if accepted

### Stage 3: Watcher Integration (Surveillance Layer)

**Files to modify:**
- `src/codrag/core/watcher.py` — Add immune system hook

**What to build:**
1. Change event classifier (file modified, created, deleted)
2. Antibody matcher: indexed lookup by target file/directory
3. Trigger evaluator per type (import analysis, pattern matching, threshold checking)
4. Alert queue for triggered responses
5. Lazy evaluation fallback for direct MCP mode

### Stage 4: Response Delivery

**Files to modify:**
- `src/codrag/mcp/server.py` — Inject alerts into ambient context and audit

**What to build:**
1. Alert queue consumer on `codrag()` calls
2. Ambient context injection ("Recent Warnings" section, max 3, priority sorted)
3. Audit finding injection for structural mode
4. Auto-observation on trigger (optional)
5. Alert deduplication per session
6. Inform-level suppression after first delivery

### Stage 5: Observation Pattern Detection

**New file:** `src/codrag/core/pattern_detector.py`

**What to build:**
1. Observation pattern scanner (recurring themes)
2. Recurrence detection: 3+ similar observations threshold
3. Antibody suggestion from pattern
4. Surface suggestions via MCP or dashboard

### Stage 6: Dashboard Integration

**What to build:**
1. Antibody status display (active, testing, disabled)
2. Trigger history and dismiss tracking
3. Health metrics (trigger frequency, dismiss rate, false positive rate)
4. One-click dismiss/snooze/resolve for alerts
5. Warning indicators on affected files in trace visualization

### Stage 7: Git Hook (Opt-In)

**What to build:**
1. Pre-commit hook script that queries active antibodies
2. Always exit 0 (advisory)
3. Print warnings to stderr
4. Installation docs and opt-in instructions

### Stage 8: Dogfooding & Tuning

1. Create 5-10 antibodies for CoDRAG from existing concepts/observations
2. Run in testing mode: evaluate against recent git history
3. Activate and monitor over 2 weeks
4. Track false positive and dismiss rates
5. Tune observation pattern threshold based on results
6. Document: which concept types produce good antibodies?

---

## Success Criteria

1. **Constraint concepts auto-suggest antibodies** — >80% of constraint concepts produce valid suggestions
2. **Zero false positives in testing mode** — validated against current codebase before activation
3. **<5% false positive rate in production** — measured over 2 weeks
4. **Ambient injection works** — `codrag()` surfaces relevant warnings when antibodies trigger
5. **Latency budget** — antibody evaluation adds <100ms to file change processing
6. **Non-blocking** — no antibody ever prevents a save, commit, or push
7. **Observable** — every trigger is logged and queryable
8. **User flow is frictionless** — no mandatory screens, no forced acknowledgments, information appears where you already are

---

## Design Principles

1. **Never block, always inform.** Advisory only. Blocking is a linter's job.
2. **Derived, not invented.** Every antibody traces to a concept or observation. Provenance always visible.
3. **Graceful degradation.** Watcher down → lazy evaluation on next audit. Concepts empty → innate defenses still work.
4. **Minimal alert fatigue.** Max 3 per ambient call. Deduplicated per session. Inform suppressed after first delivery.
5. **Testable before activation.** Every antibody runs in testing mode first. No blind activation.
6. **Ambient, not intrusive.** Feels like a helpful colleague, not a CI gate.

---

## The Long View

Phase 87 is where CoDRAG becomes more than a knowledge retrieval tool. The progression:

- **Phase 83:** CoDRAG answers "what's structurally important?" (audit redesign)
- **Phase 84:** CoDRAG remembers "why things are designed this way" (concepts)
- **Phase 85:** CoDRAG enriches external tools with structural context (SARIF)
- **Phase 86:** CoDRAG understands what you're asking (intent classification)
- **Phase 87:** CoDRAG watches your back (immune system)

Together, these phases transform CoDRAG from a passive intelligence layer into an **active architectural partner** — one that remembers decisions, understands intent, enriches other tools, and proactively warns when the codebase drifts from its own stated principles.

---

## Resolved Questions

1. **Watcher dependency** — Lazy evaluation on next `codrag_audit()` when daemon isn't running. Degraded but functional.
2. **Cross-file triggers** — Evaluate on individual file changes with current graph state for V1. Batch evaluation across related changes is future work.
3. **Antibody versioning** — Suggest update when concept changes, don't auto-apply. Trigger patterns may need manual adjustment.
4. **Performance at scale** — Antibodies indexed by target file/directory. O(1) lookup per file change.
5. **Observation pattern quality** — Require 3+ similar observations before suggesting. Conservative start, tune threshold with experience.
6. **Git hooks** — Opt-in pre-commit hook, always exit 0, prints warnings. Advisory only. Consistent with "never block" principle.
