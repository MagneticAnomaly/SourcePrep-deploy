# Phase 45: Multi-GPU Concurrency & AI Gateway Consolidation

> **Status:** Design
> **Goal:** Consolidate resource/hardware settings into AI Gateway, fix active
> project limit enforcement, and design a multi-GPU concurrency system that
> scales from single-Mac to multi-machine setups.

---

## 1. Bug Fix: Max Active Projects Not Enforced Correctly

### Problem

The "Max Active Projects" setting is set to 3 but only 1 project can be toggled
active. Root cause: **all existing projects default to `config.active: True`**
(backward compat), so the enforcement code counts ALL projects as "active":

```python
# crud.py:186-188 counts ALL projects because config.active defaults to True
for p in reg.list_projects():
    if p.id != project_id and get_project_activity_status(p.id) == "active":
        active_count += 1  # counts 11 projects, blocks at >= 3
```

### Fix

Only count projects that were **explicitly activated** by the user (have
`config.active` field explicitly set to True), not projects that just exist
with default config:

```python
for p in reg.list_projects():
    if p.id != project_id:
        cfg = p.config if isinstance(p.config, dict) else {}
        if "active" in cfg and cfg["active"] is True:
            active_count += 1
```

Additionally, the frontend at `App.tsx:417` hardcodes `Infinity` for paid tiers:
```typescript
const projectLimit = effectiveTier === 'free' ? 1 : Infinity
```
This should use the actual setting:
```typescript
const projectLimit = effectiveTier === 'free'
  ? 1
  : (maxActiveProjects === 'infinite' ? Infinity : maxActiveProjects)
```

---

## 2. UI Restructure: Move Settings to AI Gateway

### Current State

- **Global Settings drawer** contains:
  - Resource Limits (Max Active Projects)
  - Hardware Profile (Apple Silicon / Discrete GPU / Intel)
  - UI Preferences, etc.

- **AI Gateway** (detail view) contains:
  - Saved Endpoints
  - Model slots (Structured mode) or Assignment Blocks (Mapped mode)

### Proposed Change

**Move out of Global Settings into AI Gateway:**
- Resource Limits (Max Active Projects)
- Hardware Profile

**Add to Global Settings (replacement):**
- "AI Gateway" section headline with a button to open the AI Gateway detail view
  (same overlay as clicking "AI Models" panel, just a second entry point)

**Placement in AI Gateway:**
- Just below the Saved Endpoints panel, above the model slot cards

---

## 3. Multi-GPU Concurrency Design

### 3.1 Problem Statement

The current system assumes a single compute environment:
- **Apple Silicon:** concurrency locked to 1 (unified memory)
- **Discrete GPU:** concurrency 1-8 based on VRAM
- **Cloud endpoints:** handled by batch profiles (high concurrency)

This breaks when a user has:
- A Mac for development + a Linux machine with a 4090 for heavy LLM work
- Multiple GPUs on the same machine
- A mix of local + cloud endpoints
- 3 simultaneous active projects that need pipeline work

### 3.2 Key Insight: Endpoints Already Model the Compute Layer

The existing **Saved Endpoints** system already captures:
- Provider (Ollama, LM Studio, OpenAI, Anthropic, etc.)
- URL (localhost vs network IP vs cloud API)
- API key

What is missing is the **compute resource metadata** attached to each endpoint:
- Is this endpoint running on the same machine or a remote one?
- What GPU/hardware backs this endpoint?
- How many concurrent requests can it handle?

### 3.3 Proposed Architecture

#### Tier 1: Single Compute (Current, Simplified)

For users with one machine (Mac or single-GPU PC):

```
AI Gateway
  Saved Endpoints
    - Ollama (localhost:11434)
    - LM Studio (localhost:1234)
    - OpenAI (api.openai.com)

  Compute Profile
    [Single Compute]  [Multi-GPU]

    Hardware: [Apple Silicon (Mac)]
    Max Active Projects: [3 (Standard)]

    i Concurrency: 1 (Apple Silicon)
    i Cloud endpoints auto-scale via batching
```

**Behavior:**
- All local endpoints share one concurrency limit (the hardware profile)
- Cloud endpoints bypass the limit (batching handles throughput)
- Works exactly as today with zero config change for single-machine users

#### Tier 2: Multi-GPU (New)

For users with multiple compute resources:

```
  Compute Profile
    [Single Compute]  [Multi-GPU]

    Max Active Projects: [3 (Standard)]

    Compute Nodes
      Mac Studio (local)
        Hardware: Apple Silicon
        Concurrency: 1
        Endpoints: Ollama, LM Studio

      Linux Workstation (192.168.1.50)
        Hardware: NVIDIA RTX 4090 (24GB)
        Concurrency: 4
        Endpoints: Ollama (remote)

      Cloud
        Concurrency: auto (batch profile)
        Endpoints: OpenAI, Anthropic

      [+ Add Compute Node]
```

### 3.4 Data Model

#### Compute Node (New Concept)

```typescript
interface ComputeNode {
  id: string;
  name: string;                    // "Mac Studio", "Linux 4090", "Cloud"
  type: 'local' | 'remote' | 'cloud';
  hardware_profile?: 'apple_silicon' | 'nvidia' | 'amd' | 'intel' | 'cloud';

  // Concurrency
  max_concurrent: number;          // 1 for Apple Silicon, 4 for 4090, etc.

  // GPU details (optional, for display/recommendations)
  gpu_name?: string;               // "RTX 4090", "M3 Max", etc.
  gpu_vram_gb?: number;            // 24, 96, etc.

  // Associated endpoints
  endpoint_ids: string[];          // References to SavedEndpoint.id
}
```

#### Enhanced Endpoint (Existing + Extension)

```typescript
interface SavedEndpoint {
  // ... existing fields ...
  id: string;
  name: string;
  provider: string;
  url: string;
  api_key?: string;

  // NEW: Compute association
  compute_node_id?: string;        // null = auto-detect (local or cloud)
}
```

#### Auto-Detection Logic

When a user creates an endpoint, CoDRAG auto-classifies it:

| URL Pattern | Auto-Type | Auto-Profile | Concurrency |
|---|---|---|---|
| `localhost:*` or `127.0.0.1:*` | local | (from hardware dropdown) | (from hardware dropdown) |
| `192.168.*`, `10.*`, custom hostname | remote | **prompt user** | **prompt user** |
| `api.openai.com`, `api.anthropic.com` | cloud | cloud | auto (batch profile) |
| Other HTTPS URLs | cloud | cloud | auto (batch profile) |

**Key UX insight:** When a user adds an endpoint with a LAN IP, we show a
one-time prompt: *"This looks like a remote machine. Would you like to set up
a compute node for it?"* This naturally unlocks the Multi-GPU tab.

### 3.5 Pipeline Scheduling with Multi-GPU

#### Current (Single Compute)

```
Project A pipeline -> Stage 5 (epistemic) -> Ollama queue -> sequential
Project B pipeline -> waiting... (blocked by Project A)
Project C pipeline -> waiting... (blocked by Project A)
```

#### Multi-GPU

```
Compute Nodes:
  Mac Studio:     concurrency=1, endpoints=[ollama-local, lmstudio]
  Linux 4090:     concurrency=4, endpoints=[ollama-remote]
  Cloud:          concurrency=auto, endpoints=[openai, anthropic]

Pipeline Scheduler:
  Project A -> enrichment stage -> assigned to ollama-remote (4090) -> runs
  Project B -> catalogue stage -> assigned to ollama-local (Mac) -> runs
  Project C -> epistemic stage -> assigned to openai (cloud) -> runs

  All three run simultaneously because they are on different compute nodes!
```

#### Scheduling Algorithm

```python
def schedule_stage(project_id, stage):
    """Pick the best compute node for a stage.

    Priority:
    1. If the model assignment specifies an endpoint, use that
       endpoint's compute node.
    2. If the assigned compute node has capacity, run there.
    3. If full, queue -- but check OTHER nodes for compatible models.
    4. Cloud nodes always have capacity (batching).
    """
    task_id = STAGE_TASK_ID[stage]
    endpoint = resolve_endpoint_for_task(task_id)
    node = get_compute_node(endpoint.compute_node_id)

    if node.current_load < node.max_concurrent:
        return node  # Has capacity

    # Check if another node has the same model available
    for alt_node in get_all_nodes():
        if alt_node.id == node.id:
            continue
        if alt_node.current_load < alt_node.max_concurrent:
            if has_compatible_model(alt_node, task_id):
                return alt_node  # Spill to alternate node

    return node  # Will queue until capacity frees
```

### 3.6 Concurrency Resolution Per Node

Each compute node has its own concurrency limit. The pipeline scheduler
respects these independently:

| Scenario | Mac (c=1) | 4090 (c=4) | Cloud (c=inf) | Total |
|---|---|---|---|---|
| 3 projects, all local | 1 | - | - | 1 |
| 3 projects, Mac + 4090 | 1 | 4 | - | 5 |
| 3 projects, Mac + cloud | 1 | - | 3 | 4 |
| 3 projects, all three | 1 | 4 | 3 | 8 |

### 3.7 Edge Cases

#### Same Machine, Two Servers (Already Handled)

**Example:** Ollama + LM Studio both on localhost.
**Resolution:** Both belong to the same "local" compute node. They share the
concurrency limit. The model assignment (structured/mapped) decides which
server handles which task. No change needed.

#### Remote Endpoint Goes Offline

**Example:** Linux 4090 machine is powered off.
**Resolution:** The pipeline scheduler falls back to the next available
compute node. If no other node has a compatible model, the stage queues
(same as today). The health check (existing `/llm/slots/status`) detects
"unreachable" and the UI shows the status.

#### Cloud Budget Exhaustion

**Example:** OpenAI rate limit hit.
**Resolution:** Existing batch profile + budget throttle (Phase 26) handles
this. The scheduler queues the stage on the cloud node until the rate limit
resets. No change needed.

#### Two GPUs on Same Machine

**Example:** Dual 4090 workstation.
**Resolution:** This is modeled as one compute node with higher concurrency
(e.g., 8) or two separate nodes if the user wants per-GPU control. If
the inference server (Ollama/vLLM) handles multi-GPU internally, one node
with max_concurrent matching the server's capacity is simplest.

#### Model Not Available on Preferred Node

**Example:** Deep thinking model only on 4090, user assigns all 3 projects
to deep enrichment.
**Resolution:** Projects queue on the 4090 node. If the fast catalogue
stage runs concurrently on the Mac (different model assignment), throughput
still improves. The scheduler does NOT auto-download models to other nodes.

---

## 4. Implementation Plan

### Phase 45A: Bug Fixes + UI Move (1-2 days)

1. Fix max_active_projects counting (only count explicit `config.active: True`)
2. Fix frontend `projectLimit` to use actual `maxActiveProjects` setting
3. Move Resource Limits + Hardware Profile into AI Gateway
4. Add "AI Gateway" button in Global Settings

### Phase 45B: Compute Node Foundation (2-3 days)

1. Add `ComputeNode` data model to settings store
2. Auto-create a "Local" node from existing hardware profile
3. Auto-create a "Cloud" node when cloud endpoints exist
4. Add `compute_node_id` field to `SavedEndpoint`
5. Auto-detect LAN IPs on endpoint creation and prompt for node setup
6. Single Compute / Multi-GPU tab UI in Compute Profile section
7. Multi-GPU tab: CRUD for compute nodes (name, hardware, concurrency, endpoints)

### Phase 45C: Multi-Node Pipeline Scheduler (3-5 days)

1. Per-node concurrency tracking in `BuildOrchestrator`
2. Node-aware stage scheduling in `PipelineOrchestrator`
3. Spill-to-alternate-node logic
4. Queue visualization in UI (which project is on which node)
5. Tests: multi-project concurrent pipelines on different nodes

### Phase 45D: Team/Enterprise Extensions (Future)

1. Shared compute nodes across team members
2. Central GPU pool management
3. Priority queuing (some projects get GPU priority)
4. Cost tracking per node (cloud spend, GPU hours)
5. Node health monitoring dashboard

---

## 5. Migration Path

### Existing Users (Zero Disruption)

When upgrading, CoDRAG auto-creates:
- **One "Local" compute node** from the existing hardware profile setting
  - All localhost endpoints assigned to it
  - Concurrency from existing hardware profile
- **One "Cloud" compute node** (auto) if any cloud endpoints exist
  - All cloud endpoints assigned to it
  - Concurrency = auto (batch profile)

The "Single Compute" tab is selected by default. Everything works identically
to before. The "Multi-GPU" tab is available but not required.

### Discovering Multi-GPU

The Multi-GPU tab unlocks naturally when:
1. User adds an endpoint with a LAN IP (we prompt)
2. User manually switches to Multi-GPU tab and adds a node
3. No forced migration, no breaking changes

---

## 6. Embedding Queue Separation

### Key Insight

The **NativeEmbedder** (default) uses ONNX with hardware-specific acceleration:
- **macOS:** CoreML (Apple Neural Engine + Metal GPU)
- **NVIDIA:** CUDA (via onnxruntime-gpu)
- **Windows:** DirectML
- **Fallback:** CPU

This is a **completely separate compute path** from the LLM inference servers
(Ollama, LM Studio, cloud APIs). NativeEmbedder never touches the LLM queue.

### Implication for Pipeline Scheduling

Knowledge Embedding stages (Stage 5 and Stage 11) should **NOT count against
the LLM concurrency limit** when using NativeEmbedder. They can run in
parallel with LLM stages without contention.

```
Pipeline Stage Map:

  LLM Queue (respects concurrency limit):
    Stage 2: Inferred Edges (code model)
    Stage 3: Catalogue (fast model)
    Stage 6: Epistemic Enrichment (deep model)
    Stage 7: Group Reasoning (deep model)
    Stage 8: Module Synthesis (deep model)
    Stage 9: Atlas Building (deep model)
    Stage 10: Continuous Deepening (deep model)

  Embedding Queue (independent, always runs):
    Stage 5: Knowledge Embedding (NativeEmbedder / CoreML / CUDA)
    Stage 11: Deep Knowledge Embedding (same)

  No Queue (Rust, CPU-only):
    Stage 1: Structural Graph (Rust engine)
    Stage 4: Relationship Validation (Rust engine)
```

### Exception: OllamaEmbedder

If the user explicitly configures embedding via an Ollama endpoint (instead
of NativeEmbedder), then Stages 5/11 DO compete with LLM tasks on that
endpoint. The scheduler should detect this and include them in the LLM
concurrency queue for that compute node.

### State Machine Integration

The pipeline state machine (Phase 25B) needs a `queue_type` concept:

```python
class QueueType(str, enum.Enum):
    LLM = "llm"          # Competes for LLM server slots
    EMBEDDING = "embedding"  # Independent ONNX/native path
    RUST = "rust"         # CPU-only, no queue needed

STAGE_QUEUE_TYPE = {
    StageId.STRUCTURAL: QueueType.RUST,
    StageId.INFERRED_EDGES: QueueType.LLM,
    StageId.CATALOGUE: QueueType.LLM,
    StageId.VALIDATION: QueueType.RUST,
    StageId.KNOWLEDGE: QueueType.EMBEDDING,
    StageId.ENRICHMENT: QueueType.LLM,
    StageId.GROUP_REASONING: QueueType.LLM,
    StageId.CLUSTERING: QueueType.LLM,
    StageId.ATLAS: QueueType.LLM,
    StageId.DEEPENING: QueueType.LLM,
    StageId.DEEP_KNOWLEDGE: QueueType.EMBEDDING,
}
```

This means:
- Rust stages run immediately (no GPU contention)
- Embedding stages run on their own lane (CoreML/CUDA, not Ollama)
- LLM stages respect the per-node concurrency limit
- A project can have its structural build, embedding, AND an LLM stage
  all running simultaneously on a single machine

---

## 7. Abstract Hardware Profiles

### Problem with Current Naming

The current dropdown labels ("Apple Silicon (Mac)", "Discrete GPU", "Intel")
are too specific and confusing. A user with a Mac Studio M3 Ultra sees
"Apple Silicon: Concurrency locked to 1" and wonders if they are limited.

### Proposed: Concurrency Levels with Guidance

Replace hardware-named profiles with **abstract concurrency levels**:

```
LLM Concurrency
  How many LLM requests can run simultaneously on your local hardware.
  This does NOT affect embeddings (which run independently via ONNX).

  [1]  [2]  [3]  [4]  [6]  [8]

  Guidance:
  - 1: Single GPU, 8-16GB VRAM (Mac M1/M2, RTX 3060, any 8b+ model)
  - 2: 16-32GB VRAM (Mac M3/M4, RTX 3070/4060, 4b models)
  - 4: 32-48GB VRAM (Mac Pro/Ultra, RTX 4090, 4b-8b models)
  - 6+: 64GB+ VRAM or multiple GPUs (Mac Ultra 128GB, dual 4090)

  Each concurrent request needs its own KV cache in VRAM.
  When in doubt, start at 1 and increase if you have headroom.
```

**Key changes:**
- No "Apple Silicon" or "NVIDIA" labels — just numbers with guidance
- Guidance references common hardware as examples, not categories
- Explicitly states embeddings are separate
- Default is 1 (safe for everyone)

### Per-Stage Concurrency (Advanced, Collapsed)

Power users can expand an "Advanced" section to set per-stage concurrency:

```
Advanced Concurrency (optional)
  Fast stages (Catalogue): [same as above ▾]
  Code stages (Edge Discovery): [same as above ▾]
  Deep stages (Epistemic, Clustering, etc.): [same as above ▾]
```

This maps to the existing `llm_concurrency_fast`, `llm_concurrency_code`,
`llm_concurrency_deep` settings. Most users never touch this.

---

## 8. State Machine Integration

The pipeline state machine (Phase 25B, `state_machine.py`) needs extensions
for multi-project scheduling:

### New Concepts

```python
# In the state machine or a new scheduler layer:

class PipelineScheduler:
    """Manages concurrent pipeline runs across multiple projects.

    Respects per-node concurrency limits and queue types.
    """

    def can_start_stage(self, project_id: str, stage: StageId) -> bool:
        """Check if a stage can start given current compute load."""
        queue_type = STAGE_QUEUE_TYPE[stage]

        if queue_type == QueueType.RUST:
            return True  # Always OK, CPU-only

        if queue_type == QueueType.EMBEDDING:
            # NativeEmbedder: always OK (separate ONNX session)
            # OllamaEmbedder: check LLM node capacity
            if is_native_embedder():
                return True
            # Fall through to LLM check

        # LLM queue: check compute node capacity
        node = get_compute_node_for_stage(project_id, stage)
        return node.current_load < node.max_concurrent

    def enqueue_stage(self, project_id: str, stage: StageId) -> None:
        """Add a stage to the appropriate queue."""
        if self.can_start_stage(project_id, stage):
            self.start_stage(project_id, stage)
        else:
            self.queue_stage(project_id, stage)
            # Will be started when a slot frees up
```

### State Machine Events for Queuing

```python
# New events for the pipeline state machine:
QUEUED = "queued"           # Stage waiting for compute capacity
STAGE_DEQUEUED = "stage_dequeued"  # Capacity freed, stage can start

# New state:
QUEUED = "queued"           # Pipeline is waiting for compute capacity

# Transition: RUNNING + no_capacity -> QUEUED
# Transition: QUEUED + capacity_freed -> RUNNING
```

### Multi-Project Coordination

When Project A's stage completes and frees a compute slot:
1. State machine fires `Event.STAGE_COMPLETED`
2. Scheduler checks the queue for other projects waiting on that node
3. If found, fires `Event.STAGE_DEQUEUED` on the waiting project's SM
4. That project's pipeline resumes

This is where the state machine pays off — each project has its own SM,
and the scheduler coordinates between them without ad-hoc state hacks.

---

## 9. Team/Enterprise Scope Separation

### Decision

Team/Enterprise compute management is **NOT part of the desktop app**.
It belongs in a separate **CoDRAG Manager** application:

- **Pro tier (desktop app):** Single user, local + remote compute nodes,
  multi-GPU from one machine. All config is local.
- **Team/Enterprise (CoDRAG Manager):** Multi-user, shared GPU pools,
  priority queuing, cost tracking. Deployed as a web service on the
  team's infrastructure.

### What We Build Now (Pro Desktop)

- Compute Node CRUD (local, remote, cloud)
- Per-node concurrency limits
- Pipeline scheduler with queue types
- State machine integration
- Abstract concurrency profiles

### What We Defer (CoDRAG Manager)

- Shared compute nodes across team members
- Central GPU pool management
- Priority queuing across users
- Cost tracking per node
- Node health monitoring dashboard
- Admin UI for fleet management

See `docs/Phase06_Team_And_Enterprise/COMPUTE_MANAGEMENT_FOUNDATIONS.md`
for the foundations doc that bridges desktop → manager.

---

## 10. Revised Implementation Plan

### Phase 45A: Bug Fixes + Immediate UX (1-2 days)

1. **Fix max_active_projects counting** (done — only count explicit active)
2. **Fix frontend projectLimit** (done — use actual maxActiveProjects)
3. Move Resource Limits + Hardware Profile into AI Gateway
4. Add "AI Gateway" button in Global Settings
5. Replace hardware profile labels with abstract concurrency levels + guidance

### Phase 45B: Embedding Queue Separation (1 day)

1. Add `STAGE_QUEUE_TYPE` mapping
2. Embedding stages bypass LLM concurrency check when NativeEmbedder active
3. Detect OllamaEmbedder and route to LLM queue when applicable
4. Verify: embedding + LLM stages run concurrently on same machine

### Phase 45C: Compute Node Foundation (2-3 days)

1. `ComputeNode` data model in settings store
2. Auto-create "Local" node from existing concurrency setting
3. Auto-create "Cloud" node when cloud endpoints exist
4. `compute_node_id` field on `SavedEndpoint`
5. Auto-detect LAN IPs on endpoint creation → prompt for node setup
6. Single Compute / Multi-GPU tab UI
7. Multi-GPU tab: CRUD for compute nodes

### Phase 45D: Multi-Project Pipeline Scheduler (3-5 days)

1. Per-node concurrency tracking in `BuildOrchestrator`
2. `QUEUED` state in pipeline state machine
3. Node-aware stage scheduling in `PipelineOrchestrator`
4. Queue: when node is full, park the pipeline SM in QUEUED state
5. Dequeue: when slot frees, resume next waiting project
6. Tests with tiny repos and small model

### Phase 45E: Polish (1-2 days)

1. Queue visualization in UI (which project is waiting on what)
2. Concurrency guidance on docs site
3. Per-stage concurrency (advanced, collapsed by default)
