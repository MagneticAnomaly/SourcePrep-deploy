# Phase 62 — Dual-Agent Architecture: Pi + Claude Code with Paperclip

> **Research Document 8 of 8** | Phase 62: Autonomous Pi + Human-in-the-Loop Claude Code
> Date: 2026-03-30

---

## 1. The Question

> *Can Paperclip orchestrate TWO types of agents — Claude Code for heavy/human-in-the-loop work, and Pi (powered by CoDRAG intelligence) for autonomous background tasks?*

**Short answer: Yes, this is technically feasible and architecturally sound.** Paperclip supports heterogeneous adapters. But the implementation details, cost tradeoffs, and CoDRAG's role are subtle. This document goes deep.

---

## 2. The Architecture: "Planner-Worker" Split

This maps perfectly to an established multi-agent pattern called **Planner-Worker** or **Frontier-Workhorse**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Paperclip (Layer 4)                          │
│                     Company Mission + Goals                          │
│                                                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐ │
│  │   "Architect" Agent     │    │   "Worker" Agent(s)             │ │
│  │   ────────────────      │    │   ─────────────────             │ │
│  │   Adapter: claude-local │    │   Adapter: pi-local (CUSTOM)    │ │
│  │   Model: Claude Opus    │    │   Model: Sonnet / Ollama / any  │ │
│  │   Role: Heavy lifting   │    │   Role: Autonomous batch tasks  │ │
│  │   Mode: Human-in-loop   │    │   Mode: Fully autonomous        │ │
│  │                         │    │                                   │ │
│  │   Tasks:                │    │   Tasks:                         │ │
│  │   • Architecture design │    │   • Fix linting issues           │ │
│  │   • Complex refactoring │    │   • Apply audit findings         │ │
│  │   • Security review     │    │   • Update documentation        │ │
│  │   • New features        │    │   • Resolve TODOs               │ │
│  │   • Code review         │    │   • Add missing tests           │ │
│  │                         │    │   • Format/standardize code      │ │
│  │   CoDRAG: MCP server    │    │   CoDRAG: CLI + Skill file      │ │
│  └─────────────────────────┘    └─────────────────────────────────┘ │
│                                                                      │
│  Both agents report heartbeats back to Paperclip.                    │
│  Both query CoDRAG for codebase intelligence.                        │
│  Paperclip manages budgets, queues, and org chart.                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Works

| Dimension | Claude Code (Architect) | Pi (Worker) |
|---|---|---|
| **Cost** | $100-200/mo (Anthropic API) | $5-20/mo (any API, or free with Ollama) |
| **Reasoning** | Deep (Opus-class) | Adequate for defined tasks (Sonnet/Haiku/local) |
| **Supervision** | Human reviews complex decisions | Runs autonomously, PR-gated |
| **Context** | MCP-loaded (CoDRAG + Sequential Thinking) | Skill-loaded (CoDRAG CLI) |
| **Session cost** | ~$0.50-5.00 per complex task | ~$0.02-0.50 per routine task |
| **Speed** | Slow (deliberate, multi-step reasoning) | Fast (well-defined scope) |
| **Safety** | Auto-mode classifier | Permission gate extension + PR-only merge |

### The Cost Argument

This is the strongest case for the dual-agent setup:

```
                         Without Pi (Claude Code for everything)
                         ─────────────────────────────────────
                         20 complex tasks × $3.00    = $60.00
                         50 routine tasks  × $3.00    = $150.00
                         TOTAL: $210.00/week

                         With Pi for routine work
                         ─────────────────────────────────────
                         20 complex tasks × $3.00    = $60.00  (Claude Code)
                         50 routine tasks  × $0.10    = $5.00   (Pi + Sonnet/local)
                         TOTAL: $65.00/week

                         Savings: ~70% on routine tasks
```

---

## 3. How Paperclip Enables This

### 3.1 Paperclip's Adapter Architecture

Paperclip is explicitly designed for heterogeneous agents:

```
Paperclip Agent Config
├── Agent: "Senior Architect"
│   ├── adapter: "claude-local"
│   ├── model: "claude-opus-4.5"
│   ├── concurrency: 1
│   ├── heartbeat: 30min
│   └── budget: $200/week
│
├── Agent: "Code Worker Alpha"
│   ├── adapter: "pi-local"        ← Custom adapter (to build)
│   ├── model: "claude-sonnet-4.5" (or Ollama local)
│   ├── concurrency: 3             ← Can run 3 simultaneous
│   ├── heartbeat: 10min           ← More frequent checks
│   └── budget: $20/week
│
└── Agent: "Code Worker Beta"
    ├── adapter: "pi-local"
    ├── model: "ollama/qwen2.5-coder:14b"  ← Fully local, $0 API cost
    ├── concurrency: 2
    ├── heartbeat: 15min
    └── budget: $0/week (local model)
```

### 3.2 Building a Custom `pi-local` Adapter

Paperclip's plugin system supports custom adapters via JSON-RPC over stdin/stdout. A `pi-local` adapter would:

```typescript
// pi-local-adapter (conceptual)
class PiLocalAdapter implements PaperclipAdapter {
  async execute(task: PaperclipTask): Promise<AdapterResult> {
    // 1. Build the prompt with CoDRAG context
    const codragContext = await exec('codrag context "' + task.title + '"');
    
    // 2. Spawn Pi in print/JSON mode
    const result = await exec(
      `pi --print "${task.description}\n\nContext:\n${codragContext}" ` +
      `--provider ${this.config.provider} ` +
      `--model ${this.config.model} ` +
      `--mode json`
    );
    
    // 3. Parse Pi's JSON output
    const events = parseJsonl(result.stdout);
    
    // 4. Create PR with changes (safety gate)
    await exec(`git checkout -b pi-worker/${task.id}`);
    await exec(`git add -A && git commit -m "Pi: ${task.title}"`);
    await exec(`gh pr create --title "Pi: ${task.title}" --body "${task.description}"`);
    
    // 5. Return result to Paperclip
    return {
      status: 'completed',
      transcript: events,
      tokensUsed: extractTokenCount(events),
      filesChanged: extractChangedFiles(events),
    };
  }
}
```

**Effort to build:** ~3-5 days for a functional adapter.

### 3.3 The Heartbeat Flow

```
Every 10 minutes:
┌──────────────┐
│  Paperclip   │ "Worker Alpha, check your queue"
│  heartbeat   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Pi Worker   │ "I have 2 tasks assigned to me"
│  wakes up    │
└──────┬───────┘
       │
       ├──→ codrag search "task 1 context"     ← CoDRAG intelligence
       ├──→ codrag impact --file affected.py    ← Blast radius check
       │
       ▼
┌──────────────┐
│  Pi executes │ read → edit → write → bash (run tests)
│  task 1      │
└──────┬───────┘
       │
       ├──→ git checkout -b pi/task-1
       ├──→ git commit && gh pr create
       │
       ▼
┌──────────────┐
│  Report back │ "Task 1 done. PR #42 created. 3 files changed."
│  to Paperclip│
└──────────────┘
```

---

## 4. CoDRAG's Role: The Intelligence Bridge

CoDRAG is what makes Pi effective as an autonomous worker. Without CoDRAG, Pi is a blind agent — it doesn't know the codebase structure, dependencies, or what files matter.

### 4.1 How CoDRAG Powers Each Agent

```
┌──────────────────────────────────────────────────────────────────┐
│                        CoDRAG (Layer 1)                          │
│                   Runs as background daemon                       │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │ codrag_audit│  │codrag_search│  │   codrag_impact          │ │
│  │ (findings)  │  │ (context)   │  │   (blast radius)         │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────────┘ │
│         │                │                     │                  │
└─────────┼────────────────┼─────────────────────┼──────────────────┘
          │                │                     │
    ┌─────┴────┐     ┌────┴─────┐         ┌────┴─────┐
    │          │     │          │         │          │
    ▼          ▼     ▼          ▼         ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│Claude  ││  Pi    ││Claude  ││  Pi    ││Claude  ││  Pi    │
│gets    ││gets    ││gets    ││gets    ││gets    ││gets    │
│via MCP ││via CLI ││via MCP ││via CLI ││via MCP ││via CLI │
└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘
```

### 4.2 CoDRAG as Task Generator

This is the key innovation. CoDRAG doesn't just provide passive intelligence — it **generates the tasks** that Pi workers execute:

```
CoDRAG pipeline runs
  → Health Scanner finds 23 issues
  → Advisor proposes 8 improvements
  → These become ActionItems
  → ActionItems are exported as JSON
  → Custom script pushes them to Paperclip API:
      POST /api/companies/{id}/issues
      {
        "title": "Fix circular dependency in auth module",
        "description": "CoDRAG finding HEALTH-a7b9: ...",
        "projectId": "codrag-findings",
        "priority": "P1"
      }
  → Paperclip assigns them to Pi workers
  → Pi workers execute with CoDRAG context
  → PRs are created for human review
```

**This is the full loop:**
```
CoDRAG discovers → Paperclip assigns → Pi executes → Human reviews PR
```

### 4.3 The AGENTS.md / Skill Integration

For Pi workers to be effective, they need CoDRAG context pre-loaded:

**Option A: AGENTS.md (Passive, Always-On)**
CoDRAG writes its module summary and focus areas into `.agents/AGENTS.md`. Pi automatically loads this at session start. Zero configuration needed.

**Option B: Skill File (On-Demand, Token-Efficient)**
Pi invokes CoDRAG tools only when it needs them. The skill file teaches Pi how to query CoDRAG via bash:

```
/skill:codrag → Pi learns CoDRAG commands
Pi says: "Let me check the blast radius before editing auth.py"
→ codrag impact --file src/auth/login.py
→ Pi sees 7 dependents, adjusts approach
```

**Option C: Pre-Injected Context (Best for Autonomous)**
The `pi-local` adapter pre-fetches CoDRAG context and includes it in Pi's prompt:

```typescript
// In pi-local adapter:
const context = await exec(`codrag context "${task.title}" --max-chars 6000`);
const impact = await exec(`codrag impact --file ${task.affectedFiles[0]}`);

const prompt = `
Task: ${task.title}
${task.description}

Codebase Context (from CoDRAG):
${context}

Blast Radius:
${impact}

Instructions:
1. Make the minimal change to fix this issue
2. Run tests to verify
3. Do not modify files outside the blast radius
`;
```

---

## 5. Where Pi Ends and Claude Code Begins

This is the clarity you need:

### Task Routing Rules

```
┌─────────────────────────────────────────────────────────┐
│                    Task Router                           │
│                                                          │
│  Inbound task from Paperclip                             │
│        │                                                 │
│        ├─── Is it well-defined? (scope < 5 files)        │
│        │    ├── YES → Does it need deep reasoning?       │
│        │    │         ├── NO  → Pi Worker ✅              │
│        │    │         └── YES → Claude Code ⬆️            │
│        │    └── NO  → Claude Code ⬆️                     │
│        │                                                 │
│        ├─── Examples for Pi:                             │
│        │    • "Add type hints to utils.py"               │
│        │    • "Fix linting error in auth.py"             │
│        │    • "Add docstrings to all public methods      │
│        │       in src/api/"                              │
│        │    • "Resolve TODO on line 42 of router.py"     │
│        │    • "Update import paths after module rename"  │
│        │    • "Add error handling to API endpoint"       │
│        │                                                 │
│        ├─── Examples for Claude Code:                    │
│        │    • "Refactor auth system to use JWT"          │
│        │    • "Design new plugin architecture"           │
│        │    • "Debug intermittent race condition"        │
│        │    • "Review security implications of PR #42"   │
│        │    • "Implement new feature: file upload"       │
│        │    • "Resolve architectural conflict between    │
│        │       modules A and B"                          │
│        │                                                 │
│        └─── The dividing line:                           │
│             Pi = "I can describe the exact outcome       │
│                   in one sentence"                       │
│             Claude = "I need to think about the          │
│                       approach before starting"          │
└─────────────────────────────────────────────────────────┘
```

### The Key Insight

> **Pi is not a weaker version of Claude Code. Pi is a different tool for a different job.**

| | Pi Worker | Claude Code Architect |
|---|---|---|
| **Analogy** | Junior dev executing a well-defined ticket | Senior architect solving an ambiguous problem |
| **Input** | Specific task + CoDRAG context | Ambiguous goal + human conversation |
| **Output** | PR with specific changes | Design doc + implementation + review notes |
| **Autonomy** | Full (no human needed) | Partial (human reviews decisions) |
| **Mistakes** | Caught by CI + PR review | Caught during session via Sequential Thinking |
| **Cost** | $0.02-0.50 per task | $0.50-5.00 per task |
| **Model** | Sonnet/Haiku/local (adequate) | Opus (reasoning depth) |

---

## 6. Do We Need To Build a Paperclip Adapter?

### Option A: Build `pi-local` Adapter (Custom)

**Pros:**
- Tight integration with Paperclip's heartbeat/budget system
- CoDRAG context pre-injected
- Full cost tracking per Pi task
- Pi's model flexibility (use Ollama for $0 tasks)

**Cons:**
- 3-5 days to build
- Maintenance burden (Paperclip API changes)
- Paperclip-specific (doesn't help non-Paperclip users)

### Option B: Use Paperclip's Process Adapter with Pi CLI

**Pros:**
- No custom adapter needed — Paperclip already has a generic process adapter
- Just configure: `command: "pi", args: ["--print", "${task.description}"]`
- Works today

**Cons:**
- No CoDRAG context injection (Pi runs blind)
- No PR-gated safety
- Crude output parsing

### Option C: Don't Build Adapter — Just Export Tasks

**Pros:**
- CoDRAG exports ActionItems as JSON
- User's own scripting pushes to Paperclip API
- Or user pastes ActionItem text into Claude Code session
- Remains tool-agnostic

**Cons:**
- No automation — manual step required
- Loses the "autonomous loop" benefit

### Recommendation

**Start with Option C (export), validate demand, then build Option A if warranted.**

CoDRAG's role is to generate the knowledge. The `pi-local` adapter is a Paperclip plugin, not a CoDRAG feature. If we wanted to build it, it should live in a separate repo (`paperclip-pi-adapter`) or be contributed to Paperclip's plugin ecosystem.

---

## 7. What CoDRAG Should Actually Build

### Must Build (Enables All Configurations)

| Feature | Description | Effort |
|---|---|---|
| **`codrag advise --format json`** | Export ActionItems as structured JSON | 1-2 days |
| **`codrag advise` Pi skill** | Teaches Pi how to query CoDRAG findings | Hours |
| **ActionItem → Paperclip mapper** | Script/docs showing ActionItem → Paperclip issue mapping | 1 day |
| **Configuration profile docs** | Document the dual-agent architecture as a recommended setup | 1 day |

### Could Build (If Demand Is Proven)

| Feature | Description | Effort |
|---|---|---|
| `paperclip-pi-adapter` | Custom Paperclip process adapter for Pi | 3-5 days |
| `codrag push --target paperclip` | Direct push of ActionItems to Paperclip API | 2-3 days |
| Pi extension with CoDRAG tools | Full Pi extension package | 3-5 days |

### Should NOT Build

| Feature | Reason |
|---|---|
| CoDRAG-internal task execution | This is Paperclip's job (Layer 4) |
| Built-in Pi agent management | This is Paperclip's job (Layer 4) |
| GitHub PR creation from CoDRAG | This is the agent's job (Layer 3) |

---

## 8. The Complete Vision

```
┌──────────────────────────────────────────────────────────────────────┐
│                        The Full Stack                                 │
│                                                                       │
│  Layer 4: ORCHESTRATION                                               │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Paperclip                                                        │ │
│  │  • Company mission defines direction                              │ │
│  │  • CoDRAG findings auto-imported as issues                       │ │
│  │  • Routes complex tasks → Claude Code architect                  │ │
│  │  • Routes routine tasks → Pi workers                             │ │
│  │  • Tracks budgets, progress, audit trails                        │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Layer 3: EXECUTION                                                   │
│  ┌──────────────────────┐      ┌────────────────────────────────────┐│
│  │  Claude Code          │      │  Pi Worker(s)                      ││
│  │  • Opus model         │      │  • Sonnet/Haiku/local model        ││
│  │  • MCP: CoDRAG +      │      │  • CLI: CoDRAG skill               ││
│  │    Sequential Thinking│      │  • Autonomous execution             ││
│  │  • Superpowers plugin │      │  • PR-gated output                  ││
│  │  • Human-in-the-loop  │      │  • 3-5x cheaper per task            ││
│  └──────────────────────┘      └────────────────────────────────────┘│
│                                                                       │
│  Layer 2: REASONING                                                   │
│  ┌──────────────────────┐      ┌────────────────────────────────────┐│
│  │  Sequential Thinking  │      │  (Not needed for Pi —              ││
│  │  • Complex planning   │      │   tasks are pre-defined)           ││
│  │  • Multi-step reasoning│      │                                    ││
│  └──────────────────────┘      └────────────────────────────────────┘│
│                                                                       │
│  Layer 1: INTELLIGENCE                                                │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  ★ CoDRAG ★                                                       │ │
│  │  • Codebase graph (structure, dependencies, hubs)                │ │
│  │  • Opportunity discovery (health, advisor, spaghetti)            │ │
│  │  • Context assembly (search, impact, LOD compression)            │ │
│  │  • Knowledge export (JSON, SARIF, CSV, MCP, CLI)                 │ │
│  │  • Cross-session memory (observations)                           │ │
│  │                                                                   │ │
│  │  SERVES BOTH AGENTS via:                                          │ │
│  │    Claude Code → MCP tools (codrag_search, codrag_impact, etc.)  │ │
│  │    Pi Workers  → CLI tools (codrag search, codrag impact, etc.)  │ │
│  │    Paperclip   → JSON export (ActionItems → Paperclip Issues)    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Layer 0: MODELS                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Ollama (local) │ Anthropic API │ OpenAI │ OpenRouter │ etc.     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Feasibility Assessment

| Question | Answer | Confidence |
|---|---|---|
| Can Paperclip run different adapter types simultaneously? | **Yes** — explicitly designed for this | ⭐⭐⭐⭐⭐ |
| Can Pi run headless in autonomous mode? | **Yes** — print/JSON/RPC modes | ⭐⭐⭐⭐⭐ |
| Can Pi use non-Anthropic models (cheaper)? | **Yes** — 15+ providers via pi-ai | ⭐⭐⭐⭐⭐ |
| Can CoDRAG feed both agents simultaneously? | **Yes** — MCP for Claude, CLI for Pi | ⭐⭐⭐⭐⭐ |
| Can CoDRAG generate tasks for Paperclip? | **Yes** — ActionItem export + API | ⭐⭐⭐⭐ |
| Is there a `pi-local` Paperclip adapter? | **No** — would need to be built | ⭐⭐⭐ |
| Is the cost savings real? | **Yes** — ~70% on routine tasks | ⭐⭐⭐⭐ |
| Is the quality adequate for Pi on routine tasks? | **Likely** — depends on task definition quality | ⭐⭐⭐ |

---

## 10. What CoDRAG Should Do (Action Items)

### Immediate (This Sprint)
1. ✅ **Add `codrag advise --format json`** — structured ActionItem export
2. ✅ **Document the dual-agent architecture** as a recommended configuration profile
3. ✅ **Create the Pi skill file** for CLI-based CoDRAG access

### Near-Term (If There's Demand)
4. 🟡 **Create `codrag push --target paperclip`** — direct Paperclip API integration
5. 🟡 **Create example `pi-local` adapter** — open source, lives outside CoDRAG repo
6. 🟡 **Add SARIF export** for GitHub Code Scanning integration

### Strategic (Validate First)
7. 🔵 **Build CoDRAG → Paperclip continuous loop** — auto-discover → auto-assign → auto-review
8. 🔵 **Build task complexity classifier** — auto-route "simple" tasks to Pi, "complex" to Claude Code

---

*This document should be read alongside [06_Ecosystem_And_Configurations.md](./06_Ecosystem_And_Configurations.md) and [07_Strategic_Pivot.md](./07_Strategic_Pivot.md) for the complete strategic picture.*
