# Phase 56: UI Strategy for Per-Endpoint Concurrency

**Goal:** Let multiple projects run simultaneously by making the scheduler aware of how many concurrent requests each endpoint can handle. No per-project model assignment — every project uses the same global model slots (Fast, Thinking, Code).

---

## The Key Insight

CoDRAG already has the model slot system built:
- **Fast Model** → `catalogue`, `inferred_edges` (via Structured) 
- **Thinking Model** → `enrichment`, `group_reasoning`, `clustering`, `atlas`, `deepening`
- **Code Model** → `inferred_edges`
- **Embedding** → ONNX (independent, no LLM contention)

Each slot points to an **Endpoint** (e.g., Ollama at `localhost:11434`, or OpenAI API). The missing piece is that the scheduler doesn't know _how many concurrent requests_ that endpoint can handle.

## What We Add: Concurrency on the Endpoint

When a user edits an Endpoint in the AI Gateway, we add one or two fields depending on the provider type:

### For Ollama / LM Studio Endpoints

```
┌─────────────────────────────────────────────┐
│  🟢 Ollama (localhost)                       │
│  URL: http://localhost:11434                 │
│                                              │
│  Local GPU Concurrency:  [ 1 ▾]             │
│  ℹ️ Models running on your physical hardware  │
│                                              │
│  Cloud Model Concurrency: [ 3 ▾]            │
│  ℹ️ Models proxied through cloud (kimi, etc.) │
└─────────────────────────────────────────────┘
```

The backend already knows which models are cloud-proxied via `is_cloud_model_via_ollama()`. So when three projects all start their `catalogue` stage simultaneously:
- If the Fast Model is `qwen3:4b` (local) → only 1 runs at a time, others queue
- If the Fast Model is `kimi-k2.5` (cloud via Ollama) → up to 3 run concurrently

### For Direct Cloud Providers (OpenAI, Anthropic, Google)

```
┌─────────────────────────────────────────────┐
│  🟢 OpenAI                                   │
│  API Key: sk-•••••••                         │
│                                              │
│  Concurrent Requests:  [ 3 ▾]               │
│  ℹ️ Max parallel API calls across all slots   │
└─────────────────────────────────────────────┘
```

### For Remote GPU (e.g., Linux box on LAN)

```
┌─────────────────────────────────────────────┐
│  🟢 Linux Workstation                        │
│  URL: http://192.168.1.50:11434              │
│                                              │
│  Local GPU Concurrency:  [ 2 ▾]             │
│  ℹ️ RTX 4090 — fits ~2 models simultaneously  │
└─────────────────────────────────────────────┘
```

---

## How It Works (Your Use Case)

1. You have one Ollama endpoint configured globally.
2. Your **Fast Model** = `qwen3:4b` (local), your **Thinking Model** = `kimi-k2.5` (cloud via Ollama).
3. You set Local GPU = 1, Cloud = 3 on that endpoint.
4. You start 4 projects simultaneously:
   - All 4 hit `structural` (Rust, CPU) → all run instantly (no slot needed).
   - All 4 advance to `catalogue` (uses Fast Model = local `qwen3:4b`) → 1 runs, 3 queue.
   - As each finishes and moves to `enrichment` (uses Thinking Model = cloud `kimi-k2.5`), they enter the **cloud queue**, which allows 3 concurrent → 3 run simultaneously.
   - **Total parallel throughput: 1 local + 3 cloud = 4 concurrent pipeline stages.**

The scheduler just round-robins. No per-project model assignment. Every project uses the exact same global slots.

---

## Where This Fits in the UI

**No new UI screens needed.** We modify the existing `EndpointManager` edit modal:

1. **Current state:** URL, Name, Provider, API Key fields.
2. **New state:** Same fields + a "Concurrency" section at the bottom:
   - Ollama: Two number inputs (Local GPU / Cloud Model)
   - Cloud providers: One number input (Concurrent Requests)
   - Default values: Local = 1, Cloud = 1 (safe defaults, user opts up)

The `ComputeNodePanel` component we already built can be **removed** — it was over-engineered. The concurrency settings live directly on the endpoint.

---

## Backend Translation

When the scheduler loads settings, it reads each saved endpoint's concurrency values and auto-generates internal compute nodes:

```
SavedEndpoint {                    →  Internal Compute Nodes
  id: "ep-1",                         ┌─ "local:ep-1"  (max_concurrent: 1)
  provider: "ollama",                  └─ "cloud:ep-1"  (max_concurrent: 3)
  url: "localhost:11434",
  local_concurrency: 1,
  cloud_concurrency: 3,
}

SavedEndpoint {                    →  Internal Compute Node
  id: "ep-2",                         └─ "cloud:ep-2"  (max_concurrent: 5)
  provider: "openai",
  url: "api.openai.com",
  concurrency: 5,
}
```

When `_advance_pipeline()` runs a stage, it checks which model slot the stage uses, looks up that slot's endpoint, determines if the resolved model is local or cloud, and routes to the correct internal node. **Zero user-facing complexity.**

---

## Data Model Changes

### TypeScript (`types.ts`)
```diff
 export interface SavedEndpoint {
   id: string;
   name: string;
   provider: LLMProvider;
   url: string;
   api_key?: string;
-  compute_node_id?: string | null;
+  /** Max concurrent local model requests (VRAM-bound). Default: 1. */
+  local_concurrency?: number;
+  /** Max concurrent cloud model requests (rate-limit-bound). Default: 1. */
+  cloud_concurrency?: number;
 }
```

### Python (`scheduler.py`)
```diff
 def load_from_settings(self) -> None:
     """Load compute node configuration from the settings store."""
     llm_config = settings.get("llm_config") or {}
+    for ep in llm_config.get("saved_endpoints", []):
+        local_c = ep.get("local_concurrency", 1)
+        cloud_c = ep.get("cloud_concurrency", 1)
+        self.configure_node(f"local:{ep['id']}", max(1, local_c))
+        if cloud_c > 0:
+            self.configure_node(f"cloud:{ep['id']}", max(1, cloud_c))
```

### Python (`orchestrator.py`)
```diff
 def _advance_pipeline(self, run):
     stage = StageId(run.stages[run.current_stage_index])
+    node_id = self._resolve_node_for_stage(run.project_id, stage)
-    if not pipeline_scheduler.can_start(run.project_id, stage):
+    if not pipeline_scheduler.can_start(run.project_id, stage, node_id):
```
