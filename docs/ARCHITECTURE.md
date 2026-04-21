# Prep Architecture

## Design Principles

### 1. Local-First, Team-Ready
- All data stored locally by default
- No cloud dependencies for core functionality
- Optional network mode for team collaboration
- Embedded mode allows git-tracked indexes

### 2. Resource Efficiency
- Single daemon serves all projects
- Shared LLM connections (Ollama)
- Lazy loading of indexes (load on access)
- Auto-unload of idle resources

### 3. Progressive Enhancement
- Works without LLMs (keyword search only)
- Embeddings improve search quality
- Code Graph index adds structural understanding
- LLM augmentation adds intelligent summaries

### 4. IDE Agnostic
- HTTP API for any integration
- MCP support for modern IDEs (Windsurf, Cursor)
- CLI for scripting and automation
- Dashboard for visual exploration

---

## System Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interfaces                                   │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│    CLI      │  Dashboard  │   MCP       │  HTTP API   │  Future: VSCode     │
│  (prep)   │  (React)    │  (stdio)    │  (REST)     │  Extension          │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴─────────────────────┘
       │             │             │             │
       └─────────────┴─────────────┴─────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Server                                     │
│                         (localhost:8400)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Routes:                                                                    │
│  ├── /projects/*        → ProjectRouter                                    │
│  ├── /projects/{id}/*   → IndexRouter (search, context, build)             │
│  ├── /trace/*           → CodeGraphRouter                                  │
│  └── /llm/*             → LLMRouter                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Core Engine                                        │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│  ProjectRegistry │  CodeIndex       │  CodeGraph       │  Embedders         │
│  (SQLite)        │  (per-project)   │  (per-project)   │  (shared)          │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│  - projects      │  - DocumentStore │  - GraphBuilder  │  - NativeEmbedder  │
│  - configs       │  - Chunker       │  - prep_engine │  - OllamaEmbedder  │
│  - build_history │  - Embeddings    │  - GraphQuery    │  - LODExtractor    │
│  - settings      │  - PathWeights   │  - Neighbors     │  - FeatureGate     │
├──────────────────┴──────────────────┴──────────────────┴────────────────────┤
│  AutoRebuildWatcher (per-project, triggers CodeIndex + TraceBuilder)        │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Storage Layer                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Standalone Mode:                                                           │
│  ~/.local/share/prep/                                                     │
│  ├── registry.db              (SQLite: projects, settings)                  │
│  ├── cache/                   (LLM response cache)                          │
│  └── projects/                                                              │
│      ├── {project-id}/                                                      │
│      │   ├── manifest.json    (build metadata)                              │
│      │   ├── documents.json   (chunked documents)                           │
│      │   ├── embeddings.npy   (vector index)                                │
│      │   ├── trace_nodes.jsonl                                              │
│      │   └── trace_edges.jsonl                                              │
│      └── ...                                                                │
│                                                                             │
│  Embedded Mode:                                                             │
│  /path/to/project/.prep/    (same structure, lives in project)            │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          External Services                                  │
├──────────────────────────────┬──────────────────────────────────────────────┤
│  Ollama (localhost:11434)    │  Built-in Compression (LOD)                  │
│  ├── nomic-embed-text        │  ├── Structural code compression (3–20×)     │
│  └── (optional, not needed)  │  └── No GPU, no sidecar, no extra model      │
├──────────────────────────────┼──────────────────────────────────────────────┤
│  Native ONNX (built-in)      │  License (~/.prep/license.json)            │
│  ├── nomic-embed-text-v1.5   │  ├── Ed25519 signed offline token            │
│  └── No external deps needed │  └── PREP_TIER env override (dev)          │
└──────────────────────────────┴──────────────────────────────────────────────┘
```

---

## Component Details

### ProjectRegistry

**Purpose:** Manage project configurations and metadata.

**Storage:** SQLite database at `~/.local/share/prep/registry.db`

**Schema:**
```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,           -- UUID
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    mode TEXT DEFAULT 'standalone', -- 'standalone' | 'embedded'
    config JSON,                    -- include/exclude globs, trace settings
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE builds (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    status TEXT,                    -- 'pending' | 'running' | 'completed' | 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    stats JSON,                     -- document count, embedding count, etc.
    error TEXT
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value JSON
);
```

**Operations:**
- `add_project(path, name, mode, config)` → project_id
- `get_project(id)` → Project
- `list_projects()` → List[Project]
- `update_project(id, config)` → Project
- `remove_project(id, purge=False)`

---

### IndexManager

**Purpose:** Manage embedding indexes for each project.

**Per-Project Files:**
```
{index_dir}/
├── manifest.json       # Build metadata, file hashes
├── documents.json      # Chunked documents with metadata
└── embeddings.npy      # NumPy array of vectors (N × dim)
```

**Classes:**

```python
class IndexManager:
    """Manages embedding indexes for all projects."""
    
    def __init__(self, registry: ProjectRegistry, llm: LLMCoordinator):
        self.registry = registry
        self.llm = llm
        self._indexes: Dict[str, EmbeddingIndex] = {}  # Lazy-loaded
    
    def get_index(self, project_id: str) -> EmbeddingIndex:
        """Get or load index for project."""
        ...
    
    def build(self, project_id: str, incremental: bool = True) -> BuildResult:
        """Build or rebuild index."""
        ...
    
    def search(self, project_id: str, query: str, k: int) -> List[SearchResult]:
        """Semantic search in project."""
        ...
    
    def context(self, project_id: str, query: str, max_chars: int) -> ContextResult:
        """Assemble context for LLM prompt."""
        ...


class EmbeddingIndex:
    """Single project's embedding index."""
    
    def __init__(self, index_dir: Path, llm: LLMCoordinator):
        self.index_dir = index_dir
        self.llm = llm
        self.manifest: Optional[Manifest] = None
        self.documents: List[Document] = []
        self.embeddings: Optional[np.ndarray] = None
    
    def load(self) -> None:
        """Load index from disk."""
        ...
    
    def build(self, project_path: Path, config: ProjectConfig) -> Manifest:
        """Build index from project files."""
        ...
    
    def search(self, query_embedding: np.ndarray, k: int) -> List[SearchResult]:
        """Vector similarity search."""
        ...
```

---

### Code Graph Manager### Code Graph Manager (TraceManager)

**Purpose:** Manage structural/graph indexes for code understanding.

**Per-Project Files:**
```
{index_dir}/
├── trace_manifest.json   # Build metadata
├── trace_nodes.jsonl     # One node per line (file, symbol, etc.)
└── trace_edges.jsonl     # One edge per line (import, call, etc.)
```

**Node Schema:**
```json
{
  "id": "node-abc123",
  "kind": "symbol",           // file | symbol | endpoint | doc_section
  "name": "generate_image",
  "file_path": "halley_core/api/routes/image.py",
  "span": {"start": 112, "end": 145},
  "language": "python",
  "metadata": {
    "symbol_type": "function",
    "is_public": true,
    "docstring": "Handles image generation...",
    "summary": "API handler for /api/image/generate"  // LLM-generated
  }
}
```

**Edge Schema:**
```json
{
  "id": "edge-def456",
  "kind": "imports",          // imports | calls | implements | documented_by
  "source": "node-abc123",
  "target": "node-xyz789",
  "metadata": {
    "confidence": 1.0         // 1.0 for static analysis, <1.0 for LLM-inferred
  }
}
```

**Operations:**
- `build_trace(project_id)` — Extract symbols and edges
- `search_nodes(project_id, query)` — Find nodes by name/kind
- `get_node(project_id, node_id)` — Get node details
- `get_neighbors(project_id, node_id, direction, edge_kinds)` — Graph traversal

---

### LLMCoordinator

**Purpose:** Manage connections to Ollama, handle request queuing and caching.

```python
class LLMCoordinator:
    """Shared LLM connection pool."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.ollama = OllamaClient(config.ollama_url)
        self._cache = LLMCache(config.cache_dir)
    
    async def embed(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for texts (batched, cached)."""
        ...
    
    async def embed_query(self, query: str) -> np.ndarray:
        """Get embedding for a single query."""
        ...
    
    async def augment(self, prompt: str, context: str) -> str:
        """Generate augmentation (summary, tags, etc.)."""
        ...
    
    async def compress(self, context: str, query: str) -> str:
        """Compress context using LOD (structural) or LLMLingua-2."""
        ...
    
    def status(self) -> LLMStatus:
        """Check connection status for all services."""
        ...
```

---

### FileWatcher

**Purpose:** Monitor project directories for changes, trigger incremental rebuilds.

```python
class FileWatcher:
    """Watches project directories for changes."""
    
    def __init__(self, registry: ProjectRegistry, index_manager: IndexManager):
        self.registry = registry
        self.index_manager = index_manager
        self._debounce_timers: Dict[str, Timer] = {}
    
    def start(self) -> None:
        """Start watching all projects with auto_rebuild enabled."""
        ...
    
    def stop(self) -> None:
        """Stop all watchers."""
        ...
    
    def _on_change(self, project_id: str, changed_files: List[Path]) -> None:
        """Handle file change event (debounced)."""
        ...
```

---

## Data Flow

### Build Flow

```
User: prep build <project-id>
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Load project config from registry│
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Scan files matching include globs│
│    (exclude gitignored, excluded)   │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Chunk files into documents       │
│    (respect symbol boundaries if    │
│     trace enabled)                  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Embed chunks via Ollama          │
│    (batched, cached)                │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 5. Build trace index (if enabled)   │
│    - Parse symbols (AST)            │
│    - Extract import edges           │
│    - Optional: LLM summaries        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 6. Save to index_dir                │
│    - manifest.json                  │
│    - documents.json                 │
│    - embeddings.npy                 │
│    - trace_*.jsonl                  │
└─────────────────────────────────────┘
```

### Search Flow

```
User: prep search <project-id> "how does auth work?"
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Embed query via Ollama           │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Vector similarity search         │
│    (cosine distance, top-k)         │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Optional: Trace expansion        │
│    - Find related symbols           │
│    - Include callers/callees        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Return ranked results            │
│    - file path, span, score         │
│    - preview text                   │
│    - trace node info (if available) │
└─────────────────────────────────────┘
```

### Context Assembly Flow

```
User: prep context <project-id> "how does auth work?" --max-chars 8000
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Search (as above)                │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Assemble top chunks              │
│    (fit within max_chars budget)    │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Optional: LOD compression         │
│    (structural code compression)    │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Return assembled context         │
│    - Full text for LLM prompt       │
│    - Source citations               │
└─────────────────────────────────────┘
```

---

## API Design

### RESTful Conventions

- **GET** for reads
- **POST** for actions (build, search) and creates
- **PUT** for updates
- **DELETE** for removes

### Response Format

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### Error Format

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project with ID 'xyz' not found"
  }
}
```

### Pagination

```json
{
  "data": {
    "items": [...],
    "total": 100,
    "offset": 0,
    "limit": 20
  }
}
```

---

## Dashboard Architecture

### Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Framework** | React 18+ | Familiar, large ecosystem |
| **Build** | Vite | Fast dev, simple config |
| **Styling** | TailwindCSS | Utility-first, consistent |
| **Components** | Tremor | Accessible, dashboard-focused |
| **State** | Zustand | Simple, TypeScript-first |
| **Data Fetching** | TanStack Query | Caching, background refresh |
| **Icons** | Lucide | Consistent, tree-shakeable |

### Page Structure

```
App
├── Layout
│   ├── Sidebar (project list, add button)
│   └── Main
│       ├── ProjectTabs (active project tabs)
│       └── ProjectView
│           ├── StatusPage
│           ├── SearchPage
│           ├── TracePage
│           └── SettingsPage
└── GlobalSettings (modal)
```

### State Management

```typescript
interface AppState {
  // Projects
  projects: Project[];
  activeProjectId: string | null;
  openProjectIds: string[];  // Tab order
  
  // UI
  sidebarOpen: boolean;
  settingsOpen: boolean;
  
  // Actions
  addProject: (path: string, name: string) => Promise<void>;
  removeProject: (id: string) => Promise<void>;
  setActiveProject: (id: string) => void;
  openProject: (id: string) => void;
  closeProject: (id: string) => void;
}
```

---

## Tauri Integration (MVP)

### Why Tauri?

- **Small binary:** ~10MB vs Electron's ~150MB
- **Native performance:** Rust backend, WebView frontend
- **System integration:** Tray icon, auto-start, file dialogs
- **Cross-platform:** macOS, Windows, Linux

### Architecture with Tauri

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Tauri App                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    WebView (React Dashboard)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ IPC                                    │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Tauri Core (Rust)                                 │   │
│  │  - Window management                                                 │   │
│  │  - System tray                                                       │   │
│  │  - File dialogs                                                      │   │
│  │  - Auto-start                                                        │   │
│  │  - Sidecar management                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ Sidecar                                │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Python Backend (sidecar)                          │   │
│  │  - FastAPI server                                                    │   │
│  │  - All core engine logic                                             │   │
│  │  - Ollama communication                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sidecar Strategy

1. **Bundle Python:** Use PyInstaller/PyOxidizer to create standalone binary
2. **Launch on app start:** Tauri starts Python sidecar automatically
3. **Health check:** Tauri monitors sidecar, restarts if needed
4. **Graceful shutdown:** Tauri signals sidecar to stop on app quit

---

## Security Considerations

### Local Mode (Default)

- All data stays on local machine
- No network access required
- No authentication needed

### Network Mode (Team)

- API key authentication required
- TLS recommended for remote access
- Project-level access control (roadmap)

### Data Isolation

- Projects are strictly isolated
- Cross-project queries require explicit opt-in
- No data shared between projects by default

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Search (hot) | <100ms | Index in memory |
| Search (cold) | <500ms | Load index first |
| Context assembly | <200ms | LOD compression is in-process, no network |
| Incremental build | <10s per 100 files | Hash-based skip |
| Full build | ~1min per 1000 files | Depends on Ollama speed |

---

## Related Documents

- [ROADMAP.md](ROADMAP.md) — Development phases
- [API.md](API.md) — Full API specification
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Contribution guidelines
