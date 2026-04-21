# Prep LLM & Model Configuration

## Overview

Prep requires multiple AI models for different tasks in a tiered processing pipeline. This document specifies the model configuration system, inspired by [Halley's AI Models settings](../../../LinuxBrain/halley_core/frontend/src/components/SettingsTabs.tsx).

---

## Model Slots

Prep uses **3 model slots** with distinct purposes:

| Slot | Purpose | Default Source | Required |
|------|---------|----------------|----------|
| **Embedding Model** | Vector embeddings for semantic search | `nomic-embed-text` via Ollama or HuggingFace | ✅ Yes |
| **Small Model** | Fast analysis, parsing, tagging | Ollama endpoint (e.g., `qwen3:4b`) | ⚠️ Recommended |
| **Large Model** | Complex reasoning, summaries, synthesis | Ollama endpoint (e.g., `mistral`, `qwen3:30b`) | ⚠️ Recommended |

### Tiered Processing Strategy

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. EMBEDDING MODEL (nomic-embed-text)                           │
│    - Encode query → vector                                       │
│    - Semantic search over index                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. SMALL MODEL (fast, 4B params)                                │
│    - Parse intent                                                │
│    - Quick relevance scoring                                     │
│    - Auto-tagging during index build                             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. LARGE MODEL (powerful, 7B-30B+ params)                       │
│    - Per-symbol summaries (build-time)                           │
│    - Complex synthesis queries                                   │
│    - "Explain this codebase" style questions                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Model Slot Specifications

### Slot 1: Embedding Model

**Purpose:** Generate vector embeddings for semantic search.

**Configuration Options:**
1. **Ollama Endpoint** (recommended for simplicity)
   - URL: `http://localhost:11434`
   - Model: `nomic-embed-text`
   
2. **HuggingFace Direct Download** (runs in-app with Python)
   - Repo: `nomic-ai/nomic-embed-text-v1.5`
   - One-click download button
   - Managed by Prep (no external server needed)

**UI Pattern:**
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔢 Embedding Model                                              │
│ Vector encoding for semantic search                             │
│                                                                 │
│ ○ Use Ollama endpoint                                           │
│   Endpoint: [http://localhost:11434    ▼]                       │
│   Model:    [nomic-embed-text          ▼] [↻]                   │
│                                                                 │
│ ○ Download from HuggingFace (runs locally)                      │
│   Model: nomic-ai/nomic-embed-text-v1.5                         │
│   Status: ● Downloaded (274MB)          [Re-download]           │
│                                                                 │
│ [Test Connection]                        Active: ● Connected    │
└─────────────────────────────────────────────────────────────────┘
```

**API Contract:**
```typescript
interface EmbeddingConfig {
  source: 'endpoint' | 'huggingface';
  // Endpoint mode
  endpoint_id?: string;   // Reference to a SavedEndpoint
  model?: string;         // e.g. 'nomic-embed-text'
  // HuggingFace mode
  hf_repo_id?: string;
  hf_downloaded?: boolean;
  hf_download_progress?: number;
}
```

**Backend Wiring:**
The dashboard's embedding config drives the backend's `_create_embedder()` function.
Changing source/endpoint/model invalidates cached indexes so the next build uses the new embedder.

---

### Slot 2: Small Model (Fast Analysis)

**Purpose:** Quick parsing, intent detection, auto-tagging.

**Configuration:**
- Endpoint selector (Ollama, OpenAI-compatible, Claude API)
- Model selector (populated from endpoint)

**Recommended Models:**
- [`ministral-3:3b`](https://ollama.com/library/ministral-3) (Ollama) - **Preferred** for edge devices
- [`qwen2.5:3b`](https://ollama.com/library/qwen2.5) (Ollama)
- [`phi3:mini`](https://ollama.com/library/phi3) (Ollama)

**UI Pattern:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚡ Small Model                                                   │
│ Fast analysis & parsing                                         │
│                                                                 │
│ Endpoint: [Select endpoint...         ▼]                        │
│ Model:    [Select model...            ▼] [↻]                    │
│                                                                 │
│ Status: ○ Not configured                                        │
│                                                                 │
│ [Test Connection]                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

### Slot 3: Large Model (Complex Reasoning)

**Purpose:** Summaries, synthesis, complex queries.

**Configuration:**
- Endpoint selector (Ollama, OpenAI-compatible, Claude API)
- Model selector (populated from endpoint)

**Recommended Models:**
- `ministral-3:8b` (Ollama) - **Preferred**
- `mistral-nemo` (Ollama)
- `qwen2.5:14b` (Ollama)
- `deepseek-coder-v2` (Ollama)

**Rationale for Mistral/Ministral:**
We recommend the **Ministral 3** family (3B, 8B) for Prep's local pipeline.
1. **Edge Optimization:** Designed specifically for low-latency local inference, matching Prep's local-first philosophy.
2. **Performance:** Ministral 3 outperforms previous 7B models in reasoning and coding tasks while being significantly faster.

**UI Pattern:** Same as Small Model, different slot.

---

## Endpoint Configuration

### Saved Endpoints

Users can save multiple endpoints for reuse across model slots.

**Supported Provider Types:**
| Provider | URL Pattern | Auth | Notes |
|----------|-------------|------|-------|
| `ollama` | `http://localhost:11434` | None | Local Ollama server |
| `openai` | `https://api.openai.com/v1` | API Key | OpenAI models |
| `openai-compatible` | Custom URL | API Key | LocalAI, vLLM, etc. |
| `anthropic` | `https://api.anthropic.com` | API Key | Claude models (BYOK) |

**UI Pattern:**
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔌 Saved Endpoints                                              │
│ Add endpoints for local or remote LLM servers                   │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ GPU Server (Ollama)                                         │ │
│ │ http://192.168.1.100:11434                    [Edit] [🗑️]   │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ OpenAI                                                      │ │
│ │ https://api.openai.com/v1                    [Edit] [🗑️]   │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ + Add Endpoint                                                  │
│                                                                 │
│ Display Name:   [Local GPU Server            ]                  │
│ Provider Type:  [Ollama                    ▼]                   │
│ Endpoint URL:   [http://localhost:11434      ]                  │
│ API Key:        [••••••••••••••••••••••••••••] (if needed)      │
│                                                                 │
│ [Test Connection]  [Save Endpoint]                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Config Schema (as implemented)

```typescript
interface LLMConfig {
  // Embedding model
  embedding: {
    source: 'endpoint' | 'huggingface';
    endpoint_id?: string;     // Reference to SavedEndpoint.id
    model?: string;           // e.g. 'nomic-embed-text'
    hf_repo_id?: string;      // e.g. 'nomic-ai/nomic-embed-text-v1.5'
    hf_downloaded?: boolean;
    hf_download_progress?: number;
  };
  
  // Small model (fast)
  small_model: {
    enabled: boolean;         // Auto-set true when user selects endpoint+model
    endpoint_id?: string;
    model?: string;           // Empty until user selects
  };
  
  // Large model (powerful)
  large_model: {
    enabled: boolean;
    endpoint_id?: string;
    model?: string;
  };
  
  // Saved endpoints
  saved_endpoints: Array<{
    id: string;
    name: string;
    provider: 'ollama' | 'openai' | 'openai-compatible' | 'anthropic';
    url: string;
  }>;
}
```

**Notes:**
- Small/Large model slots start empty — no default models are pre-filled.
- `enabled` is automatically set to `true` when the user selects an endpoint or model.
- Badge status is derived from endpoint+model presence and test results, not the `enabled` flag.

### Storage Location

```
<index_dir>/                      # Default: ./prep_data/
├── ui_config.json                # Global config including llm_config
└── ...                           # Index data, manifests, etc.

~/.cache/huggingface/hub/         # HuggingFace model cache (managed by hf_hub)
├── models--nomic-ai--nomic-embed-text-v1.5/
└── ...
```

The `llm_config` is persisted inside `ui_config.json` and loaded via the
`GET /api/code-index/config` endpoint. The dashboard auto-saves changes
via `PUT /api/code-index/config` with a 500ms debounce.

---

## Backend API

### Endpoints (as implemented)

```
GET  /api/code-index/config         Get global config (includes llm_config)
PUT  /api/code-index/config         Update global config (deep merge)
                                    ↳ Invalidates cached indexes if embedding changes

POST /api/llm/proxy/models          Fetch available models from an endpoint
POST /api/llm/proxy/test            Test endpoint connectivity
POST /api/llm/proxy/test-model      Test a specific model (readiness-aware)
                                    ↳ Embedding models use /api/embeddings
                                    ↳ Other models use /api/generate with preload
POST /api/llm/model-status          Check model readiness without test request

GET  /embedding/status              Native embedding model availability
POST /embedding/download            Download native ONNX embedding model

GET  /api/llm/status                Legacy: Ollama connectivity check
POST /api/llm/test                  Legacy: Force connectivity check
```

**Note:** Endpoint and model configuration is managed entirely through the
`llm_config` object within the global config. There are no separate CRUD
endpoints for saved endpoints — they are stored in `llm_config.saved_endpoints`
and persisted via the config update endpoint.

### HuggingFace Download Flow

```
User clicks [Download]
    │
    ▼
POST /llm/hf/download
{
  "model_type": "embedding",
  "repo_id": "nomic-ai/nomic-embed-text-v1.5"
}
    │
    ▼
Server starts background download
Returns: { "download_id": "abc123" }
    │
    ▼
Frontend polls GET /llm/hf/download/status?id=abc123
Returns: { "progress": 0.45, "status": "downloading", "bytes_downloaded": "1.2GB" }
    │
    ▼
When complete:
{ "progress": 1.0, "status": "complete", "model_path": "~/.local/share/runprep/models/nomic-embed-text" }
```

---

## UI Implementation

### Settings Page Structure

```
Settings
├── General
├── Projects
├── AI Models  ◀── NEW TAB
│   ├── Embedding Model card
│   ├── Small Model card
│   ├── Large Model card
│   └── Saved Endpoints section
└── Advanced
```

### Component Hierarchy

```
AIModelsSettings
├── ModelCard (reusable)
│   ├── EndpointSelector
│   ├── ModelSelector
│   ├── HFDownloadButton (optional)
│   ├── TestConnectionButton
│   └── StatusBadge
└── SavedEndpointsSection
    ├── EndpointList
    └── AddEndpointForm
```

### Reusable Components

**ModelCard Props:**
```typescript
interface ModelCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  
  // Endpoint mode
  endpoint?: string;
  endpointOptions: Endpoint[];
  onEndpointChange: (endpoint: string) => void;
  
  // Model selection
  model?: string;
  modelOptions: string[];
  onModelChange: (model: string) => void;
  onRefreshModels: () => void;
  loadingModels?: boolean;
  
  // HuggingFace mode (optional)
  hfDownloadEnabled?: boolean;
  hfRepoId?: string;
  hfDownloaded?: boolean;
  hfDownloadProgress?: number;
  onHFDownload?: () => void;
  
  // Status
  status: 'connected' | 'disconnected' | 'not-configured';
  onTest: () => void;
  testResult?: { success: boolean; message: string };
}
```

---

## Open Questions

1. **API Key Storage:** Encrypt at rest? Use system keychain? *(Deferred — no API key providers implemented yet)*
2. ~~**Model Download Location:** Global or per-project?~~ → **Resolved:** Global via HuggingFace cache.
3. ~~**Ollama Auto-Detect:** Should we auto-discover Ollama at localhost:11434?~~ → **Resolved:** A "Default Ollama" endpoint is pre-configured.
4. ~~**Default Models:** Should onboarding pre-select recommended models?~~ → **Resolved:** No. Model selectors start empty; user must explicitly choose. Embedding auto-suggests `nomic-embed-text` when its endpoint is selected.

---

## Implementation Status

| Priority | Task | Status |
|----------|------|--------|
| P0 | Embedding model config (drives backend embedder) | ✅ Done |
| P1 | Endpoint management UI (add/edit/delete/test) | ✅ Done |
| P1 | Small/Large model config + test connection | ✅ Done |
| P1 | Settings persistence across sessions | ✅ Done |
| P1 | Badge status reflects test results | ✅ Done |
| P2 | HuggingFace download for embeddings | ✅ Done (NativeEmbedder) |
| P3 | Claude/OpenAI BYOK support | 🔲 Planned |

---

## Related Documents

- `README.md` — Phase 04 overview
- `TRACEABILITY_AUTOMATION_STRATEGY.md` — How LLMs are used in trace augmentation
- `../../ARCHITECTURE.md` — Overall Prep architecture
