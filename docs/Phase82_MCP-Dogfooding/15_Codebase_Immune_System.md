# 15 — The Codebase Immune System

## The Metaphor

A biological immune system doesn't just fight infections — it *remembers* them. It learns from past encounters, builds antibodies for known threats, and has an innate response for novel threats. The memory is distributed across the body, operates continuously in the background, and distinguishes "self" (healthy patterns) from "non-self" (threats).

CoDRAG already has all the components of a codebase immune system. They're just not connected yet.

| Biological Component | CoDRAG Component | Current State |
|---------------------|-----------------|---------------|
| **Innate immunity** (generic defense) | Audit analyzers | Active but noisy (Phase 82 findings) |
| **Adaptive immunity** (learned defense) | Observations + Concepts | Active but passive — stores knowledge, doesn't act on it |
| **Antibodies** (specific responses) | Concept assertions | Not yet built |
| **Memory cells** (long-term recall) | Cross-session memory | Works, but observation-only |
| **Immune surveillance** (continuous monitoring) | File watcher | Active for rebuild triggers, not for threat detection |
| **Inflammatory response** (alert signal) | Dashboard/MCP notifications | Limited — no proactive alerts |

The immune system vision: CoDRAG doesn't just answer questions when asked — it *proactively protects* the codebase by detecting when changes violate learned patterns, repeat known mistakes, or drift from stated architecture.

## How It Works: Three Layers

### Layer 1: Innate Defense (Pattern-Based, Always On)

These are structural checks that apply to every codebase regardless of its specific history. They're CoDRAG's equivalent of skin and mucous membranes — basic defenses that catch common threats.

**What exists today:**
- Circular dependency detection
- Module coupling analysis
- Hub bottleneck identification
- File size warnings (to be refined per doc 13)

**What to add:**
- **Import direction enforcement**: Check declared dependency directions (from concepts) against actual imports. This is the concept-as-assertion idea from doc 13.
- **Module boundary monitoring**: When a new import crosses a module boundary, flag it. Not all cross-boundary imports are bad, but new ones deserve scrutiny.
- **Pattern consistency**: If 90% of API routers follow pattern X, flag the one that doesn't. The "immune system" learns what's normal and flags deviations.

**Trigger:** Continuous — runs on file change events via the watcher.

### Layer 2: Adaptive Defense (Memory-Based, Learned)

These are defenses built from the project's specific history. Every bug observation, every architectural decision, every failed approach becomes an antibody.

**The antibody model:**

An antibody is a (pattern, response) pair derived from an observation or concept:

```python
@dataclass
class Antibody:
    """A learned defense against a known problem pattern."""
    id: str
    name: str
    source: str  # observation_id or concept_id that generated this
    
    # Detection
    trigger_type: str  # "file_change", "import_added", "function_modified", "pattern_match"
    trigger_pattern: dict  # what to watch for
    
    # Response
    severity: str  # "block", "warn", "inform"
    message: str  # what to tell the agent
    context: str  # link back to the source observation/concept
```

**Example antibodies derived from existing observations:**

```yaml
# From observation: "Phase 66 — All Pi scenarios are pure Python, zero LLM"
- name: "Pi Agent LLM dependency"
  source: obs_phase66_pi_agent
  trigger_type: import_added
  trigger_pattern:
    file: "src/codrag/services/pi_agent.py"
    imports: ["*llm*", "*openai*", "*anthropic*", "*ollama*"]
  severity: warn
  message: >
    Pi Agent is designed to be zero-LLM (pure Python analysis). Adding
    an LLM import would violate this design principle. If LLM is needed,
    consider creating a separate enrichment scenario instead.
  context: "See observation: Phase 66 Pi Agent design"

# From concept: "dependency direction: agents/ → services/ → core/"
- name: "Reverse dependency violation"
  source: concept_dependency_direction
  trigger_type: import_added
  trigger_pattern:
    source_dir: "src/codrag/core/"
    target_dir: "src/codrag/agents/"
  severity: warn
  message: >
    This import goes from core/ to agents/, violating the declared dependency
    direction. Dependencies should flow agents/ → services/ → core/.
  context: "See concept: dependency direction (Phase 67)"

# From observation: "mocked tests passed but prod migration failed"
- name: "Mock database in integration tests"
  source: obs_mock_burned
  trigger_type: pattern_match
  trigger_pattern:
    file: "tests/test_*.py"
    content: ["mock.*database", "MagicMock.*db", "patch.*sqlite"]
  severity: warn
  message: >
    Mocking the database in tests has caused production failures before.
    Integration tests should use a real (test) database.
  context: "See observation: mock/prod divergence incident"

# From concept: "CoDRAG is a knowledge provider, not a PM tool"
- name: "PM feature creep"
  source: concept_strategic_pivot
  trigger_type: file_change
  trigger_pattern:
    new_file: true
    path: "src/codrag/**/pm_*"
  severity: inform
  message: >
    New file matching PM tool pattern detected. CoDRAG pivoted away from
    PM features (Phase 62). Verify this aligns with the knowledge provider
    identity.
  context: "See concept: strategic pivot (Phase 62)"
```

**Antibody generation pipeline:**

```
Observation/Concept saved
    │
    ▼
Extract actionable patterns
    │ - What specific code patterns does this warn against?
    │ - What file paths or import patterns are relevant?
    │ - What severity should violations have?
    │
    ▼
Generate antibody candidate
    │
    ▼
Human review (optional — stored as "draft" until confirmed)
    │
    ▼
Active antibody (monitored by watcher)
```

**Auto-generation vs manual creation:**

Some antibodies can be auto-generated from well-structured observations:
- "Never import X from Y" → import trigger
- "Files in dir/ should not exceed N lines" → file change trigger
- "Always use pattern X in tests" → pattern match trigger

Others require human judgment to extract the antibody from a narrative observation. For V1, focus on manual creation with good tooling. For V2, use LLM extraction from observation text.

### Layer 3: Immune Surveillance (Proactive Monitoring)

The watcher already monitors file changes for rebuild triggers. Extend it to check antibodies on every file save.

```python
class ImmuneWatcher(AutoRebuildWatcher):
    """Extends file watcher with antibody checking."""
    
    def __init__(self, repo_root, index_dir, antibodies: List[Antibody]):
        super().__init__(repo_root, index_dir)
        self.antibodies = antibodies
        self.recent_alerts: Dict[str, datetime] = {}  # dedup
    
    def on_file_changed(self, path: Path, change_type: str):
        """Check antibodies on every file change."""
        super().on_file_changed(path, change_type)
        
        for antibody in self.antibodies:
            if self._matches_trigger(antibody, path, change_type):
                self._alert(antibody, path)
    
    def _matches_trigger(self, antibody: Antibody, path: Path, change_type: str) -> bool:
        if antibody.trigger_type == "file_change":
            return self._match_file_pattern(antibody.trigger_pattern, path)
        if antibody.trigger_type == "import_added":
            return self._check_new_imports(antibody.trigger_pattern, path)
        if antibody.trigger_type == "pattern_match":
            return self._grep_pattern(antibody.trigger_pattern, path)
        return False
    
    def _alert(self, antibody: Antibody, path: Path):
        # Dedup: don't alert for the same antibody + file within 5 minutes
        key = f"{antibody.id}:{path}"
        if key in self.recent_alerts:
            if (datetime.now() - self.recent_alerts[key]).seconds < 300:
                return
        self.recent_alerts[key] = datetime.now()
        
        # Emit alert via event bus
        emit_immune_alert(ImmuneAlert(
            antibody=antibody,
            file=path,
            timestamp=datetime.now(),
            severity=antibody.severity,
            message=antibody.message,
        ))
```

**Alert delivery channels:**
1. **MCP notification** — Push alert to the connected IDE/agent via MCP protocol notifications
2. **Dashboard indicator** — Show immune alerts in the dashboard health panel
3. **CLI output** — `codrag watch` shows alerts in the terminal
4. **Log file** — All alerts logged for later review
5. **Agent context injection** — When an agent calls `codrag()` or `codrag_search()`, include relevant recent immune alerts

## The Agent Experience

### Without Immune System (Today)

```
Agent: *modifies pi_agent.py to add an LLM call*
CoDRAG: *silent*
Agent: *commits the change*
Agent: *moves on to next task*
... 3 weeks later ...
Human: "Why is Pi Agent now requiring Ollama? It was supposed to be zero-LLM."
Agent: "I don't know, let me check git blame..."
```

### With Immune System (Proposed)

```
Agent: *starts modifying pi_agent.py*
CoDRAG (via ambient context): 
  ⚠ Immune alert: "Pi Agent LLM dependency"
  Adding an LLM import to pi_agent.py would violate the zero-LLM design.
  Source: Phase 66 decision — "All Pi scenarios are pure Python analysis"
  
Agent: *reads the alert, understands the constraint*
Agent: "I need LLM analysis here. Let me create a separate enrichment 
        scenario instead of adding it to the core Pi Agent."
Agent: *creates new file instead, preserving the design principle*
```

The immune system doesn't *prevent* the change — it *informs* the agent about the constraint, the history, and the rationale. The agent can still override it (maybe the constraint is outdated), but they make an informed choice rather than accidentally violating a design principle they didn't know existed.

## Integration with Existing Tools

### Concepts → Antibodies

Every concept with a testable assertion can generate antibodies:

```python
def concept_to_antibodies(concept: Concept) -> List[Antibody]:
    """Extract antibodies from a concept's testable assertions."""
    antibodies = []
    
    # Parse concept content for assertion patterns
    if "never" in concept.content.lower():
        # "Dependencies should NEVER flow from core/ to agents/"
        antibodies.extend(extract_never_patterns(concept))
    
    if "always" in concept.content.lower():
        # "API routers should ALWAYS validate input with Pydantic"
        antibodies.extend(extract_always_patterns(concept))
    
    if "must" in concept.content.lower():
        # "Hub files MUST have test coverage > 80%"
        antibodies.extend(extract_must_patterns(concept))
    
    return antibodies
```

### Observations → Antibodies

Bug observations are natural antibody sources:

```python
def bug_observation_to_antibody(obs: Observation) -> Optional[Antibody]:
    """Convert a bug observation into a preventive antibody."""
    if obs.category != "bug":
        return None
    
    # Extract the file and pattern that caused the bug
    return Antibody(
        name=f"Prevent: {obs.content[:50]}",
        source=obs.id,
        trigger_type="pattern_match",
        trigger_pattern={
            "file": obs.file_path,
            "content": extract_bug_patterns(obs.content),
        },
        severity="warn",
        message=f"⚠ A similar pattern caused a bug previously: {obs.content[:200]}",
        context=f"See bug observation: {obs.id}",
    )
```

### Audit → Immune Memory

When the audit finds a circular dependency and an agent fixes it, the fix becomes a new antibody:

```python
# After fixing circular dep between queue.py and events.py:
antibody = Antibody(
    name="queue.py ↔ events.py cycle prevention",
    source="audit_fix_20260407",
    trigger_type="import_added",
    trigger_pattern={
        "source": "src/codrag/api/routers/queue.py",
        "target_imports": ["events"],
    },
    severity="warn",
    message="This import would re-introduce the circular dependency between "
            "queue.py and events.py that was fixed on 2026-04-07.",
)
```

The immune system *remembers* fixes and prevents regressions. This is the adaptive immunity in action.

## Escalation Model

Not all immune responses are equal. The severity levels determine agent behavior:

| Severity | Agent experience | When to use |
|----------|-----------------|-------------|
| **inform** | Injected as context in `codrag()` response. Agent sees it but no interruption. | Soft guidance, stylistic preferences, informational notes |
| **warn** | Highlighted in search/impact results. Agent should consider before proceeding. | Design principle violations, known risk patterns, deprecated approaches |
| **block** | Shown as top-level alert before any tool response. Agent should stop and evaluate. | Reverting a fix, introducing known-bad patterns, security-relevant violations |

**"block" is advisory, not enforced.** CoDRAG is a knowledge provider, not a gatekeeper. The agent (or human) always has final say. But a "block" alert makes ignoring the constraint a conscious, documented choice rather than an accident.

### Escalation logic:

```python
def determine_severity(antibody: Antibody, context: ChangeContext) -> str:
    """Escalate severity based on context."""
    base = antibody.severity
    
    # Escalate if the change is in a hub file
    if context.file_is_hub and base == "inform":
        return "warn"
    
    # Escalate if the change reverses a recent fix
    if context.reverses_recent_fix:
        return "block"
    
    # De-escalate if the change is in a test file
    if context.is_test_file and base == "warn":
        return "inform"
    
    return base
```

## Immune System as a Product Feature

### For Individual Developers
"CoDRAG remembers why your codebase is the way it is, and warns you before you accidentally undo it."

### For Teams
"When a new developer joins, they inherit the entire team's institutional knowledge. CoDRAG prevents the 'we tried that, it broke everything' cycle."

### For Agent Fleets (Paperclip)
"When multiple agents work on the same codebase, CoDRAG ensures they all respect the same architectural constraints — even if they were established in a different agent's session."

This is particularly powerful for the Paperclip use case. The CEO agent makes a strategic decision (concept). The CTO agent implements it. The immune system ensures future QA/engineer agents don't accidentally violate it. The institutional memory is distributed across all agents via CoDRAG.

## Data Model

### Antibody Storage

```python
@dataclass
class Antibody:
    id: str                          # unique identifier
    name: str                        # human-readable name
    description: str                 # what this antibody protects against
    source_type: str                 # "concept", "observation", "audit_fix", "manual"
    source_id: str                   # ID of the source concept/observation
    
    # Trigger
    trigger_type: str                # "file_change", "import_added", "pattern_match", "metric_threshold"
    trigger_pattern: Dict[str, Any]  # what to match
    trigger_scope: List[str]         # file paths or globs this applies to
    
    # Response
    severity: str                    # "inform", "warn", "block"
    message_template: str            # with {placeholders} for context
    suggestion: Optional[str]        # what to do instead
    
    # Lifecycle
    created_at: datetime
    last_triggered: Optional[datetime]
    trigger_count: int
    enabled: bool
    
    # Staleness
    anchored_files: List[str]        # files this antibody relates to
    stale: bool                      # true if anchored files changed significantly
```

### Storage Location

Antibodies live alongside concepts and observations in CoDRAG's project data:

```
.prep/
├── concepts/
├── observations/
├── antibodies/           ← NEW
│   ├── ab_001.yaml
│   ├── ab_002.yaml
│   └── ...
└── immune_log.jsonl      ← NEW (alert history)
```

### MCP Tool Interface

```python
# New tool: codrag_immune
codrag_immune(action="list")                    # list active antibodies
codrag_immune(action="create", ...)             # create new antibody
codrag_immune(action="alerts", since="1h")      # recent immune alerts
codrag_immune(action="check", file_path="...")  # check a file against all antibodies
codrag_immune(action="disable", id="ab_001")    # temporarily disable
```

Or, simpler: integrate immune alerts into existing tools:
- `codrag()` ambient response includes a "Recent Immune Alerts" section
- `codrag_impact()` includes antibody warnings for the target file
- `codrag_audit()` includes concept-violation findings (which ARE antibodies)

The second approach (integration) is probably better for V1 — it doesn't require agents to learn a new tool. The dedicated `codrag_immune` tool can come in V2 for agents that want to manage antibodies directly.

## Implementation Phases

### Phase 1: Manual Antibodies + Concept Assertions (2-3 days)
- Add antibody data model and YAML storage
- Build concept-as-assertion checker in audit (checks dependency direction, module boundary, etc.)
- Surface concept violations in `codrag_audit` findings
- Manual antibody creation via `codrag_immune(action="create")` or YAML files

### Phase 2: Observation-Derived Antibodies (2-3 days)
- Auto-generate antibody candidates from bug observations
- Human review workflow: candidates are "draft" until confirmed
- Surface antibody warnings in `codrag_impact` for affected files

### Phase 3: Watcher Integration (1-2 days)
- Extend file watcher to check antibodies on file change
- Alert delivery via MCP notifications and dashboard
- Dedup and escalation logic

### Phase 4: Ambient Injection (1 day)
- Include recent immune alerts in `codrag()` ambient response
- Include relevant antibodies in `codrag_search` results for affected files
- Include antibody context in `codrag_impact` for hub files

### Phase 5: Agent Feedback Loop (ongoing)
- Track which alerts agents act on vs ignore
- Auto-disable antibodies that are consistently overridden (they may be outdated)
- Auto-promote frequently-triggered alerts to higher severity

## The Big Picture

```
     ┌───────────────────────────────────────────────┐
     │              Agent / Developer                 │
     │                                                │
     │  1. Makes a change                             │
     │  2. Immune system checks antibodies            │
     │  3. Gets contextual warning (if triggered)     │
     │  4. Makes informed decision                    │
     │  5. Change becomes new immune memory           │
     │                                                │
     └──────────┬───────────────────┬────────────────┘
                │                   │
      ┌─────────▼─────────┐  ┌─────▼──────────────┐
      │   CoDRAG Tools    │  │  Immune System      │
      │                   │  │                      │
      │  codrag()         │  │  Antibodies (YAML)   │
      │  codrag_search()  │◄─┤  Watcher integration │
      │  codrag_impact()  │  │  Alert delivery      │
      │  codrag_audit()   │  │  Escalation logic    │
      │  codrag_observe() │──┤  Auto-generation     │
      │  codrag_concepts()│──┤  Staleness tracking  │
      └───────────────────┘  └──────────────────────┘
                                      │
                              ┌───────▼───────┐
                              │ Knowledge Base │
                              │                │
                              │ Concepts       │──→ "why" → architectural antibodies
                              │ Observations   │──→ "what happened" → preventive antibodies  
                              │ Trace Graph    │──→ "what connects" → impact-aware escalation
                              │ Audit History  │──→ "what was fixed" → regression antibodies
                              └────────────────┘
```

The codebase immune system is not a single feature — it's the *emergent behavior* of concepts, observations, audit, and the trace graph working together proactively. Each component already exists. The immune system is the connective tissue that makes them protective rather than merely informational.

## Why This Matters

Every software project accumulates institutional knowledge: why things are the way they are, what was tried and failed, what constraints exist and why. Today, this knowledge lives in people's heads, gets lost in Slack threads, and evaporates when developers leave.

CoDRAG already captures this knowledge (concepts, observations). The immune system makes it *active* — turning passive knowledge into protective intelligence. The codebase doesn't just have a memory; it has *reflexes*.

For AI agents especially, this is transformative. An agent has no institutional memory between sessions. It doesn't know that "we tried mocking the database and it burned us" or "the dependency direction is core/ → services/ → agents/, not the reverse." Without the immune system, every agent session starts from zero and risks repeating every past mistake. With it, the codebase itself remembers — and every agent inherits that memory.

That's not just a tool feature. That's a new category of developer tooling.
