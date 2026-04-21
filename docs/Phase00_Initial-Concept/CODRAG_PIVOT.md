# Phase 69 — Pivot to CoDRAG

**Date:** 2026-01-30  
**Status:** Active

---

## Summary

The Phase 69 research has evolved from a project-embedded `code_index` approach to a **standalone multi-project application** called **CoDRAG** (Code Documentation and RAG).

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Name** | CoDRAG | "Code Documentation and RAG" — clear, memorable |
| **Architecture** | Standalone daemon | Resource efficiency, multi-project management |
| **Team Focus** | Enterprise MVP | Build for teams from day one, not afterthought |
| **UI Strategy** | Web UI → Tauri | Fast dev iteration, native MVP launch |
| **Location** | `CoDRAG/` | Sibling to LinuxBrain for testing |

---

## What This Means for Phase 69

### Research Documents (Still Valid)
The following research documents remain relevant and inform CoDRAG design:

- `TRACE_INDEX_RESEARCH.md` — Trace index architecture → CoDRAG TraceManager
- `AI_INFRASTRUCTURE_RESEARCH.md` — LLM stack → CoDRAG LLMCoordinator
- `STANDALONE_APP_FEASIBILITY.md` — Feasibility study → Adopted as CoDRAG plan

### Implementation Target
- **Old plan:** Build `code_index/` as git submodule
- **New plan:** Build CoDRAG as standalone app at `CoDRAG/`

### LinuxBrain as Test Project
LinuxBrain becomes the primary test project for CoDRAG:
```bash
codrag add LinuxBrain --name "LinuxBrain"
codrag build linuxbrain
codrag search linuxbrain "how does image generation work?"
```

---

## CoDRAG Repository Structure

```
CoDRAG/
├── README.md                 # Project overview, quick start
├── CONTRIBUTING.md           # Contribution guidelines
├── LICENSE                   # MIT license
├── pyproject.toml            # Python project config
├── src/codrag/               # Python package
│   ├── __init__.py
│   ├── cli.py                # CLI entry point
│   ├── server.py             # FastAPI app
│   ├── core/                 # Core engine
│   │   ├── registry.py       # Project registry (SQLite)
│   │   ├── embedding.py      # Embedding index
│   │   ├── trace.py          # Trace index
│   │   ├── watcher.py        # File watcher
│   │   └── llm.py            # LLM coordinator
│   └── api/                  # API routes
├── dashboard/                # React dashboard (to be created)
├── docs/
│   ├── ARCHITECTURE.md       # Technical design
│   ├── ROADMAP.md            # Development phases
│   └── DECISIONS.md          # ADRs
└── tests/                    # Test suite
```

---

## Development Roadmap

| Phase | Focus | Duration |
|-------|-------|----------|
| 0 | Foundation (CLI, API, core engine) | 2 weeks |
| 1 | Dashboard (React, project tabs) | 2 weeks |
| 2 | Auto-Rebuild (file watching) | 1 week |
| 3 | Trace Index (symbols, edges) | 2 weeks |
| 4 | MCP Integration (Windsurf/Cursor) | 1 week |
| 5 | Team Features (embedded mode, network mode) | 2 weeks |
| MVP | Tauri Wrapper (native app) | 1 week |

**Total: ~12 weeks to MVP**

---

## Migration from code_index

The existing `LinuxBrain/code_index/` research code can be migrated to CoDRAG:

| code_index Component | CoDRAG Destination |
|---------------------|-------------------|
| `mcp_codrag/` | `src/codrag/core/embedding.py` |
| `mcp_codrag_py/` | `src/codrag/core/embedding.py` |
| `dashboard/` | `dashboard/` (with modifications) |

### What to Keep
- Chunking logic
- Embedding/search logic
- On-disk format (documents.json, embeddings.npy)

### What to Change
- Add project registry (multi-project)
- Add project scoping to all operations
- Add file watching
- Add trace index

---

## Related Documents

- [CoDRAG README](../../../README.md)
- [CoDRAG Architecture](../../../docs/ARCHITECTURE.md)
- [CoDRAG Roadmap](../../../docs/ROADMAP.md)
- [CoDRAG Decisions](../../../docs/DECISIONS.md)

---

## Next Steps

1. ✅ Create CoDRAG repo structure
2. ✅ Write foundational docs
3. ⏳ Begin Phase 0 implementation (core engine, CLI)
4. ⏳ Migrate embedding logic from code_index
5. ⏳ Build dashboard
