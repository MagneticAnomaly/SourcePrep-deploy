# Goalposts: Deep R&D Analysis — Opportunities & Flaws

## Verdict: Is This Worth Building?

**Yes, strongly.** The CoDRAG architecture is *uniquely positioned* to offer this because it already builds the epistemic knowledge graph that all competing tools lack. The existing pipeline gives us:
1. A structured understanding of every file (domain tags, architecture layers, tech debt).
2. Module clustering (semantically grouped file clusters with summaries).
3. An Atlas (compressed codebase identity document).
4. A budget-controlled LLM analysis framework (Deep Analysis).
5. An audit framework (graph-only analyzers + LLM synthesis).

**No other tool on the market offers forward-looking planning grounded in a structural codebase graph.** GitHub Copilot, Cursor, etc. are reactive ("help me write this code"). Goalposts would be proactive ("here's what you should build next, based on what you have").

---

## Flaws Found in the Initial Plan

### Flaw 1: Proposing a New Pipeline Stage Is Over-Engineered
The initial plan proposed adding a `StageId.GOALPOSTS` to the build orchestrator. This is **wrong**:
- The epistemic pipeline (11 stages) is a *data construction* pipeline. Goalposts is a *consumer* of that data, not a producer.
- Adding it as a stage would mean it blocks/interferes with normal enrichment runs and requires scheduler coordination.
- **Correction:** Goalposts should be an *independent background job*, similar to how `DeepAnalysisOrchestrator` works — it reads the existing index data and runs separately.

### Flaw 2: "Sprints" Framing Is Too Opinionated
The initial plan uses heavy Agile terminology (sprints, kanban). Many users don't use sprints:
- Solo devs use todo lists.
- Startups use roadmaps.
- Enterprise uses epics/stories.
- **Correction:** Use the word "Goalposts" (plural goal-items), not "sprints". Each goalpost is a *proposed future milestone* — the user decides if it maps to a sprint, a PR, or a research phase.

### Flaw 3: Dashboard UI Was Vague
The initial plan said "Kanban or List view" without mapping to the existing panel architecture. The dashboard uses a `ModularDashboard` → `useDashboardPanels` pattern where each panel is a keyed React component registered in a central map. A "Goalposts tab" doesn't exist in this architecture — it's a **panel**.
- **Correction:** Goalposts should be a new dashboard panel (like `AuditPanel`), not a tab. This follows the existing drag-and-drop panel architecture.

### Flaw 4: No Product Goals Input Mechanism
The plan assumes the user has already defined "product goals". Where? There's no existing field for this. Without user-defined intent, the LLM can only guess.
- **Correction:** Must build a simple Product Intent Editor (a text area where the user describes their product's purpose and direction). This is the #1 input to the Goalposts planner.

---

## Design Opportunities Discovered

### Opportunity 1: Reuse the Audit/Synthesizer Architecture Wholesale
The `AuditRunner` + `AuditSynthesizer` pattern is almost exactly what Goalposts needs:
- **Tier 1 (graph-only):** Analyze current codebase completeness vs. stated goals using the epistemic data (domain tags, architecture layers, tech debt).
- **Tier 2 (LLM):** Synthesize the gap into structured goalpost proposals.
- **Storage:** `goalposts.json` in the index dir, parallel to `audit/findings.json`.
- **Dashboard hook:** `useGoalpostsSystem` (mirrors `useAuditSystem` exactly).

### Opportunity 2: Leverage the Atlas as the "Codebase Identity Card"
The Atlas already compresses the codebase into a ~4K char identity document. Instead of feeding the full `trace_epistemic.jsonl` to the LLM (expensive, 50K+ chars), we can:
1. Feed the Atlas (~4K chars) as the "what exists" context.
2. Feed the tech debt summary from the audit (~2K chars) as "what needs fixing".
3. Feed the user's Product Intent (~500 chars) as "where we're going".
This creates a ~7K char prompt — **affordable even on local models**, not the "large and expensive" call feared in the initial concept.

### Opportunity 3: Epistemic Questions → "Design Decisions" Panel
The initial concept of "research phases / questions to the user" maps beautifully to **design decisions**:
- The LLM can detect ambiguity: "Auth exists but no authorization model — RBAC or ABAC?"
- These become first-class objects in the UI: `GoalpostQuestion` items the user answers.
- Answers feed back into the next Goalposts run, creating a *conversational design loop*.

### Opportunity 4: Background Idle Processing Already Exists
The `MultiProjectCoordinator` scheduler and `watcher.py` auto-rebuild system already handle idle/background processing. Goalposts can:
- Register a listener on `BuildOrchestrator.add_listener()` for `COMPLETED` events.
- When a deep enrichment or audit completes, queue a Goalposts regeneration (if enabled).
- **Zero new infrastructure needed** for background scheduling.

### Opportunity 5: Connect to the MCP Server for AI Coding Assistants
Once Goalposts data exists on disk (`goalposts.json`), the MCP `codrag_audit` tool pattern can be extended with a `codrag_goalposts` tool that surfaces the user's approved goalposts directly in their AI coding assistant. This closes the loop: "Plan in the dashboard → Execute in the editor."

---

## Revised UX Concept: Clear & Simple

The user sees **one new panel** in their dashboard: **Goalposts**.

### Panel States:
1. **Off** → "Enable Goalposts" toggle + Product Intent text area. No cost until enabled.
2. **Generating** → Spinner. "Analyzing codebase architecture against your goals..."
3. **Ready** → List of goalpost proposals, each with:
   - Title, rationale, category badge (Architecture / Security / Feature / Tech Debt).
   - Actions: ✅ Approve, ❌ Dismiss, 💬 Refine.
4. **Questions** → "Before I can plan further, I need your input on:" → list of design questions.

### Where Data Comes From:
```
Atlas (compressed identity) ──┐
Audit Tech Debt Summary ──────┤─→ GoalpostsPlanner (LLM) ─→ goalposts.json
User Product Intent ───────────┘
```

### Where Data Goes:
```
goalposts.json ──→ Dashboard Panel (approve/dismiss/refine)
               ──→ MCP Tool (codrag_goalposts) for coding assistants
               ──→ Next Goalposts run (approved items excluded, refined items steered)
```

---

## Open Design Questions (For Next Phase)

1. **Granularity:** Should a goalpost be one task ("add rate limiting") or a group of tasks ("Security Hardening Sprint: rate limiting + CORS + auth refresh")?
2. **Persistence format:** JSON file vs. SQLite table? JSON is simpler and consistent with existing data. SQLite would be needed if we want query/filter performance on large goalpost histories.
3. **Cost control:** Should we present estimated token cost before running? The Audit system doesn't do this but Deep Analysis has budget controls we could mirror.
4. **History:** Should dismissed goalposts be remembered? (To avoid re-proposing the same thing.)
