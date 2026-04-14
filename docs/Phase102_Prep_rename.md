# Phase 102: Renaming CoDRAG to Prep

## Summary
This document outlines the complete, zero-disruption strategy for renaming the "CoDRAG" application to "Prep" (and its associated domain `runprep.io`). The migration involves replacing the application name, CLI commands, MCP tool prefixes, environment variables, local data directory paths, and all internal package namespaces. 

Because the app currently has 0 active users, no backward-compatibility or data migration scripts are required. We will perform a clean, hard cutover.

---

## User Action Checklist (To-Do Before / During Migration)
- [x] **Select Domain:** `runprep.io` (and optionally `runprep.dev`).
- [ ] **Register Domain:** Purchase `runprep.io` via Cloudflare/Namecheap.
- [ ] **Check Registries:** Verify `prep` npm scopes (`@prep/ui`), Rust crates, and Python PyPI availability.
- [ ] **Claim Socials:** Secure GitHub org, Twitter handle, etc.

---

## Thorough Implementation Plan

### Phase 1: Directory & File Renaming
*We will rename physical paths and files containing `codrag` to `prep`. This requires careful git maneuvering.*
- `src/codrag/` ➔ `src/prep/`
- `codrag_data/` ➔ `prep_data/`
- `packages/paperclip-plugin-codrag/` ➔ `packages/paperclip-plugin-prep/`
- `public/codrag-deploy/` ➔ `public/prep-deploy/`
- `public/codrag-mcp/` ➔ `public/prep-mcp/`
- `scripts/codrag-mcp-wrapper.sh` ➔ `scripts/prep-mcp-wrapper.sh`
- `codrag-daemon.spec` ➔ `prep-daemon.spec`
- Data files: `codrag_concepts.db` ➔ `prep_concepts.db`, etc.

### Phase 2: Package & Project Configuration Updates
*Update build files, manifests, and lockfiles to reflect the new namespace before touching source code.*
- **Python (`pyproject.toml`):** Rename package from `codrag` to `prep`. Update entry points (`codrag=codrag.cli:main` ➔ `prep=prep.cli:main`).
- **Rust (`engine/Cargo.toml`):** Rename crates (`codrag-engine` ➔ `prep-engine`, `codrag-graph` ➔ `prep-graph`, etc.).
- **Node/TypeScript (`package.json`):** Rename dashboard, UI, and VSCode extension packages (e.g., `@codrag/ui` ➔ `@prep/ui`).
- **Workspace (`turbo.json`, `mcp-server.json`):** Update all internal workspace references.

### Phase 3: Global Codebase Search & Replace
*Perform case-sensitive and case-insensitive replacements across the codebase.*
1. **Environment Variables:** `CODRAG_` ➔ `PREP_` (e.g., `CODRAG_DEV_MODE` ➔ `PREP_DEV_MODE`, `CODRAG_API_KEY` ➔ `PREP_API_KEY`).
2. **MCP Tools:** `codrag_` ➔ `prep_` (e.g., `codrag_search` ➔ `prep_search`, `codrag_impact` ➔ `prep_impact`).
3. **Python Imports:** `from codrag.` ➔ `from prep.` and `import codrag` ➔ `import prep`.
4. **Rust Imports:** `use codrag_` ➔ `use prep_`.
5. **Text / UI:** `CoDRAG` ➔ `Prep` (in React components, Markdown docs, logs, etc.).
6. **URLs / Domains:** Replace `codrag.io` with the new domain.

### Phase 4: Local Storage & DB Migration
*Update the paths where the app reads/writes data.*
- Update `~/.codrag/` references in the Rust daemon and Python backend to `~/.prep/`.
- Ensure SQLite connection strings point to the newly named `prep_*.db` files.

### Phase 5: Verification & Testing
- Run `pytest` to ensure all Python backend tests pass.
- Run `cargo check` and `cargo test` in the `engine/` directory.
- Run `npm run build` from the root to verify Turbo builds the UI, dashboard, and VSCode extensions.
- Launch the daemon via the newly compiled CLI (`prep`).
- Test the MCP tools (`prep_search`, etc.) inside Claude/Cursor to ensure the integration works flawlessly.
