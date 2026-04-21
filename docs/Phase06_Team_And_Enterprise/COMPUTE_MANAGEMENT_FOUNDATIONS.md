# Team/Enterprise Compute Management Foundations

> **Status:** Planning (foundations only)
> **Dependency:** Phase 45 (Multi-GPU Concurrency for Pro desktop)
> **Goal:** Document the architectural bridge between Pro-tier desktop compute
> management and Team/Enterprise centralized compute management.

---

## 1. Scope Separation

### Pro Desktop App (Phase 45, building now)

Single user manages their own compute resources:
- Local machine (Mac, Linux, Windows)
- Remote machines on LAN (SSH/network Ollama instances)
- Cloud API endpoints (OpenAI, Anthropic, etc.)
- Config stored locally in SQLite settings store
- Pipeline scheduling for 1-N active projects on the user's hardware

### Prep Manager (Team/Enterprise, future)

Multi-user centralized compute management:
- Deployed as a **web service** on the team's infrastructure
- NOT part of the Tauri desktop app
- Manages shared GPU pools across team members
- Priority queuing, cost tracking, fleet health monitoring
- Each team member's desktop app connects to Prep Manager as a client

---

## 2. Architecture Decision: Prep Manager as Web Service

### Why Not In-App?

1. **Multi-user coordination** requires a central server that all team
   members' desktop apps can reach. Embedding this in each desktop app
   would create N competing schedulers.

2. **GPU fleet management** (health monitoring, cost tracking, priority
   queuing) is an ops concern, not a developer UX concern. It belongs
   in an admin dashboard.

3. **Deployment flexibility** — teams may run Prep Manager on:
   - A shared server in the office
   - A cloud VM (AWS/GCP/Azure)
   - A Kubernetes cluster
   - The same machine that hosts the GPU fleet

### How Desktop App Connects

```
Desktop App (Pro)                Prep Manager (Team)
  |                                    |
  | --- compute/register-node -------> |  "I have a 4090 at 192.168.1.50"
  | <-- compute/ack ------------------- |  "Registered as node-xyz"
  |                                    |
  | --- pipeline/request-slot -------> |  "Project A needs deep model slot"
  | <-- pipeline/slot-assigned -------- |  "Use node-xyz, concurrency slot 2"
  |                                    |
  | --- pipeline/slot-released ------> |  "Done with slot 2"
  | <-- pipeline/ack ------------------- |  "Released"
```

The desktop app's `PipelineScheduler` (Phase 45D) becomes a **client**
that asks Prep Manager for compute slots instead of managing them locally.

---

## 3. Data Model Bridge

### Pro Desktop (Local)

```python
# Stored in local SQLite settings store
class ComputeNode:
    id: str
    name: str
    type: 'local' | 'remote' | 'cloud'
    max_concurrent: int
    endpoint_ids: List[str]
```

### Team/Enterprise (Prep Manager)

```python
# Stored in Prep Manager's database
class ManagedComputeNode(ComputeNode):
    # Extends the Pro model with team features:
    owner_id: str              # Which team member registered this node
    shared: bool               # Available to all team members?
    priority_tier: int         # 0 = best-effort, 1 = standard, 2 = priority
    cost_per_hour: float       # For cost tracking (optional)
    health_status: str         # "healthy" | "degraded" | "offline"
    last_health_check: float   # Epoch timestamp
    current_load: int          # How many slots currently in use
    reserved_by: List[str]     # User IDs currently holding slots
```

**Key insight:** The Pro `ComputeNode` is a strict subset of the Team
`ManagedComputeNode`. When upgrading from Pro to Team, the migration is
additive — existing nodes gain management fields without losing anything.

---

## 4. What We Build Now (Pro Foundations)

These Pro-tier features are designed to be **Team-extensible**:

| Pro Feature | Team Extension |
|---|---|
| `ComputeNode` model | + owner, shared, priority, cost |
| Local scheduler | Delegates to Manager when connected |
| Per-node concurrency | + cross-user slot reservation |
| Node CRUD in settings | + Node registration API |
| LAN IP detection | + Node discovery protocol |
| Endpoint-node association | + Shared endpoint catalog |

### API Surface (Pro, local-only)

```
GET  /compute/nodes              — List compute nodes
POST /compute/nodes              — Create a node
PUT  /compute/nodes/{id}         — Update a node
DEL  /compute/nodes/{id}         — Delete a node
GET  /compute/nodes/{id}/status  — Node health + current load
```

### Future API Surface (Team, Prep Manager)

```
POST /compute/register           — Desktop app registers a node
POST /compute/request-slot       — Request a compute slot for a stage
POST /compute/release-slot       — Release a compute slot
GET  /compute/pool               — Admin: view full pool status
POST /compute/priority           — Admin: set project/user priorities
GET  /compute/costs              — Admin: cost report
```

The Pro API is local (same process). The Team API is remote (HTTP to Manager).
The desktop app's scheduler abstracts this — it calls the same interface
regardless of whether it is managing locally or delegating to Manager.

---

## 5. Migration Path: Pro to Team

When a Pro user's organization upgrades to Team:

1. **Prep Manager is deployed** (by IT/admin) on team infrastructure
2. **Desktop apps are configured** with the Manager URL (one-time setup)
3. **Existing local nodes are registered** with the Manager:
   - User's Mac becomes a "personal" node (not shared by default)
   - Shared GPU servers are registered as "shared" nodes
4. **Pipeline scheduling switches** from local to Manager-delegated
5. **No data loss** — all local config remains as fallback if Manager is unreachable

---

## 6. Open Questions (for future research)

1. **Manager deployment model:** Docker image? Helm chart? Binary?
   - Recommendation: Docker image first, Helm for K8s teams later.

2. **Auth between desktop and Manager:** API keys? SSO/OIDC?
   - Recommendation: API keys for v1, SSO integration for Enterprise.

3. **Offline resilience:** What happens when Manager is unreachable?
   - Recommendation: Fall back to local scheduling with last-known node list.

4. **Node auto-discovery:** Should Manager discover GPUs on the network?
   - Recommendation: No. Nodes are explicitly registered by users/admins.
