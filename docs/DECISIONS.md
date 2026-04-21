# Prep Decision Records

This document captures key architectural and strategic decisions for Prep.

---

## ADR-001: Project Name — Prep

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need a memorable, descriptive name for the standalone multi-project RAG application.

### Decision
**Prep** — Code Documentation and RAG

### Rationale
- Clear meaning: combines "Code", "Documentation", and "RAG"
- Memorable and pronounceable
- Available as a unique identifier
- Works as CLI command: `prep`

### Alternatives Considered
- `codebase-rag` — Too long for CLI
- `code-rag` — Less descriptive
- `devrag` — Doesn't indicate documentation focus

---

## ADR-002: Standalone App Architecture

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Original plan was project-embedded (git submodule). User proposed standalone app like Ollama.

### Decision
Build a **standalone daemon** that manages multiple projects, with a unified dashboard.

### Rationale
- **Resource efficiency:** Single Ollama connection shared across projects
- **UX simplicity:** One port, one dashboard, project tabs
- **Operational ease:** No per-project server management
- **Enterprise fit:** Central management for team deployments

### Trade-offs
- Index not portable via git (mitigated by embedded mode)
- Requires app installation (acceptable for target users)

### Related Documents
- `Phase00_Initial-Concept/STANDALONE_APP_FEASIBILITY.md`

---

## ADR-003: Hybrid Index Mode

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Standalone mode stores indexes centrally, which doesn't work for teams wanting to share indexes via git.

### Decision
Support **two modes**:
1. **Standalone** (default): Index at `~/.local/share/prep/projects/{id}/`
2. **Embedded**: Index at `{project}/.prep/`

### Rationale
- Power users prefer standalone (simpler, no project clutter)
- Teams need embedded (git-tracked, instant onboarding)
- Same core engine, just different storage location

### Implementation
```bash
prep add /path/to/project                # standalone (default)
prep add /path/to/project --embedded     # embedded mode
```

---

## ADR-004: Web UI for Development, Tauri for MVP

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need to balance development speed with polished end-user experience.

### Decision
- **Development phases:** React/Vite web dashboard (served by FastAPI)
- **MVP launch:** Wrap in Tauri for native app experience

### Rationale
- Web UI enables fast iteration (hot reload, browser DevTools)
- Tauri adds native feel without development slowdown
- Tauri is smaller than Electron (~10MB vs ~150MB)
- Python backend runs as sidecar (proven pattern)

### Implementation Timeline
- Weeks 1-10: Web UI only
- Week 11: Polish
- Week 12: Tauri wrapper

---

## ADR-005: Team/Enterprise Focus from Day One

**Date:** 2026-01-30  
**Status:** Superseded

Superseded by ADR-012 (MVP boundary: enterprise implementation post-MVP; enterprise UX case studies).

### Context
Could build for individual developers first, add team features later.

### Decision
Design for **team/enterprise use cases** in MVP:
- Embedded mode for git-tracked indexes
- Network mode for shared server
- API key authentication
- Multi-user access control (basic)

### Rationale
- Retrofitting team features is harder than designing for them
- Enterprise customers drive sustainable revenue
- Individual users benefit from team-grade features

### Features in MVP
- [x] Embedded mode (git-tracked index)
- [x] Network mode (shared server)
- [x] API key auth
- [ ] Full RBAC (post-MVP)
- [ ] SSO integration (post-MVP)

---

## ADR-006: Repository Location

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Where should the Prep source code live?

### Decision
Create new repo at `Prep/`, sibling to:
- `CLaRa-Remembers-It-All/`
- `LinuxBrain/`
- `Halley.Chat/`

### Rationale
- Prep is a standalone product, not part of LinuxBrain
- Sibling repos allow testing Prep with LinuxBrain as target
- Clear separation of concerns
- Easier to open-source independently

### Migration
- Move relevant code from `LinuxBrain/code_index/` to `Prep/src/`
- Update `LinuxBrain/Docs_Halley/Phase69_CodeRAG/` to reference Prep

---

## ADR-007: Python Backend with FastAPI

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need to choose backend technology for the daemon.

### Decision
**Python 3.11+ with FastAPI**

### Rationale
- Existing code_index is Python (direct reuse)
- FastAPI is async, fast, well-documented
- Native NumPy/scikit-learn for vector operations
- Easy Ollama client integration
- Familiar to target developer audience

### Alternatives Considered
- **Rust:** Faster, but slower development, less familiar
- **Node.js:** Possible, but NumPy equivalent is weaker
- **Go:** Good performance, but ecosystem less rich for ML

---

## ADR-008: SQLite for Project Registry

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need persistent storage for project configurations, build history, settings.

### Decision
**SQLite** with single file at `~/.local/share/prep/registry.db`

### Rationale
- Zero configuration (no separate database server)
- ACID transactions
- Sufficient for thousands of projects
- Easy backup (single file)
- Python stdlib support (`sqlite3`)

### Schema
See `ARCHITECTURE.md` for full schema.

---

## ADR-009: NumPy for Vector Storage (MVP)

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need to store and search embedding vectors.

### Decision
**NumPy `.npy` files** for MVP, with option to add FAISS/Annoy later.

### Rationale
- Simple, no dependencies
- Fast enough for <100k vectors per project
- Easy to understand and debug
- Can swap in FAISS for scale (same interface)

### Future Enhancement
```python
# Current (MVP)
from prep.core.embedding import NumpyVectorStore

# Future (post-MVP)
from prep.core.embedding import FaissVectorStore
```

---

## ADR-010: MCP as Primary IDE Integration

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need to integrate with IDEs (Windsurf, Cursor, VS Code).

### Decision
**Model Context Protocol (MCP)** as primary integration method.

### Rationale
- Windsurf and Cursor support MCP natively
- Standard protocol, not vendor-specific
- Simple stdio interface
- Tools map directly to Prep operations

### MCP Tools
- `prep_status`
- `prep_build`
- `prep_search`
- `prep` (context)
- `prep_trace`

### Future
- VS Code extension (wraps MCP or direct API)
- JetBrains plugin (direct API)

---

## ADR-011: Trace Index Data Model

**Date:** 2026-01-30  
**Status:** Accepted

### Context
Need a structure for code graph (symbols, imports, calls).

### Decision
**Nodes and Edges in JSONL format**

### Rationale
- JSONL is streamable, appendable
- Human-readable for debugging
- Easy to parse and index
- Compatible with future graph database migration

### Format
```
trace_nodes.jsonl: {"id": "...", "kind": "symbol", "name": "...", ...}
trace_edges.jsonl: {"id": "...", "kind": "imports", "source": "...", "target": "...", ...}
```

### Future Enhancement
- Neo4j/DGraph for complex queries
- In-memory graph for fast traversal

---

## ADR-012: MVP Boundary — Enterprise Implementation Post-MVP (Design-Only Case Studies in MVP)

**Date:** 2026-01-31  
**Status:** Accepted

### Context
Prep should be enterprise-friendly, but the MVP must prioritize a reliable, local-first trust loop.

Shipping network mode, authentication, and administrative surfaces in MVP increases security risk and scope, and can destabilize the core experience.

### Decision
- MVP ships the local-first single-user product with dashboard + MCP + Tauri.
- Team/enterprise deployment features (network mode, auth, admin UX) are **post-MVP implementation**.
- Enterprise/team workflows are maintained as UX case studies and guardrails in `WORKFLOW_RESEARCH.md`.

### Rationale
- Preserves focus on trust invariants (right project, freshness, verification via citations).
- Reduces security foot-guns and operational complexity in MVP.
- Keeps the roadmap enterprise-aligned without forcing premature implementation.

### Consequences
- `ROADMAP.md` and phase plans enforce MVP boundaries.
- Phase06 remains valid as a design target, but implementation is scheduled post-MVP.
- The API remains compatible with future auth, but local-only mode remains usable without it.

---

## Decision Template

```markdown
## ADR-XXX: [Title]

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Deprecated | Superseded

### Context
[What is the issue that we're seeing that is motivating this decision?]

### Decision
[What is the change that we're proposing and/or doing?]

### Rationale
[Why is this the best choice among alternatives?]

### Alternatives Considered
[What other options were considered?]

### Consequences
[What becomes easier or more difficult as a result?]
```
