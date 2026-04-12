# Phase 95: Path Weights

Discovered via marketing fact-check (2026-04-10): path weights are advertised but not implemented.

## TODO

### 1. Explicit Path Weights = Specific folders and files selected on the Knowledge Graph UI
- [ ] Add `path_weights` config to project settings (e.g. `{"docs/": 0.5, "src/core/": 1.5, "vendor/": 0.3}`) >> 
- [ ] Apply weights during context assembly in `lod_extractor.py` / search ranking
- [ ] Surface in `codrag_search` and `codrag` tool params or project config
- [ ] Validate weights propagate through Atlas routing and LOD compression

### 2. Role-Based Weights via `codrag(role="...")` = this is designed for paperclip first but could be leveraged by any agent identifying with job title or clear role
- [ ] Ensure `role` param on `codrag` and `codrag_search` applies weight modifiers derived from role definitions
- [ ] Role resolver (`core/atlas/role_resolver.py`) should map roles to implicit path weight overrides (e.g. `role="security"` boosts `auth/`, suppresses `ui/`)
- [ ] `role="ceo"` should produce a high-level architectural view — boost hub files, atlas summaries, suppress implementation details
- [ ] Verify role weights compose with explicit path weights (explicit takes precedence)

### 3. Integration
- [x] Dashboard UI for configuring path weights per project >>> this is done this is the Knowledge Graph in the dashboard, the role weights don't need UI
- [ ] Document in AGENTS.md generated content
- [ ] Add demo script for marketing site showing path weight usage
