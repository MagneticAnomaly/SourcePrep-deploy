> **SUPERSEDED** by `docs/superpowers/specs/2026-04-21-prep-rename-design.md`. Kept for historical context.

# Phase 102: INSTRUCTIONS FOR AI AGENT - Prep to Prep Migration

## Target State
- Application Name: **Prep**
- Domain/URL: **runprep.io**
- CLI Command: `prep`
- MCP Tool Prefix: `prep_`

## Dear AI Agent:
You are tasked with executing a zero-disruption, hard-cutover rename of the codebase from "Prep" to "Prep". There are no active users, so backward compatibility is NOT required. 
**Follow these instructions EXACTLY in the order presented. DO NOT batch all changes into a single mega-commit without verifying steps. Run the verification commands after each phase.**

---

## User Action Checklist (To-Do Before / During Migration)
- [x] **Select Domain:** `runprep.io` (and optionally `runprep.dev`).
- [ ] **Register Domain:** Purchase `runprep.io` via Cloudflare/Namecheap.
- [ ] **Check Registries:** Verify `prep` npm scopes (`@prep/ui`), Rust crates, and Python PyPI availability.
- [ ] **Claim Socials:** Secure GitHub org (`MagneticAnomaly`), Twitter handle, etc.
- [ ] **Duplicate & Link Repos:** Create the following empty repositories under the `MagneticAnomaly` organization on GitHub, duplicate your local folders, and link them to their new remotes:
  - Main App: `https://github.com/MagneticAnomaly/Prep`
  - Public MCP: `https://github.com/MagneticAnomaly/Prep-MCP`
  - Dev MCP: `https://github.com/MagneticAnomaly/Prep-MCP-DEV`
  - Deployment: `https://github.com/MagneticAnomaly/Prep-deploy`

---

### Phase 1: Physical File and Directory Renaming
Use `git mv` (or standard `mv` if untracked) to rename files and folders. Update imports only after files are moved.

**Directories to rename:**
1. `src/prep/` ➔ `src/prep/`
2. `packages/paperclip-plugin-prep/` ➔ `packages/paperclip-plugin-prep/`
3. `public/prep-deploy/` ➔ `public/prep-deploy/`
4. `public/prep-mcp/` ➔ `public/prep-mcp/`
5. `engine/crates/prep-chunking/` ➔ `engine/crates/prep-chunking/`
6. `engine/crates/prep-engine/` ➔ `engine/crates/prep-engine/`
7. `engine/crates/prep-graph/` ➔ `engine/crates/prep-graph/`
8. Untracked local data directories: `prep_data/` ➔ `prep_data/`

**Files to rename:**
1. `prep-daemon.spec` ➔ `prep-daemon.spec`
2. `scripts/prep-mcp-wrapper.sh` ➔ `scripts/prep-mcp-wrapper.sh`
3. `public/images/Prep.png` ➔ `public/images/Prep.png`
4. `prep-logo.png` ➔ `prep-logo.png`

**Verification 1:** Run `ls -la src/prep` to ensure the move succeeded.

---

### Phase 2: Configuration & Manifest Updates
Before executing global search/replace, surgically update the build systems.

1. **Python (`pyproject.toml`):**
   - Change `name = "prep"` to `name = "prep"`
   - Update entry points: `prep = "prep.cli:main"` ➔ `prep = "prep.cli:main"`
2. **Rust (`engine/Cargo.toml` and nested `Cargo.toml` files):**
   - Rename crates from `prep-*` to `prep-*`.
   - Update relative path dependencies inside the workspace.
3. **Node/TypeScript (`package.json` files):**
   - Dashboard: Update name to `@prep/dashboard`
   - UI: Update name to `@prep/ui`
   - VSCode: Update name to `prep-vscode`
   - Update workspace dependencies linking these packages.
4. **Monorepo/Tools:** 
   - `turbo.json`, `mcp-server.json`, `uv.lock`, `package-lock.json`. Update all internal tool references.

**Verification 2:** Run `npm install` and `uv lock` (or equivalent python lock) to ensure the package managers accept the new manifests.

---

### Phase 3: Global Codebase Search & Replace
Perform exact case-sensitive replacements across the entire `src/`, `packages/`, `engine/`, `scripts/`, `tests/`, and `docs/` directories. **DO NOT touch the `.git/` directory.**

**Replacements (Execute in this order to avoid collisions):**
1. **Environment Variables:** 
   - `PREP_DEV_MODE` ➔ `PREP_DEV_MODE`
   - `PREP_API_KEY` ➔ `PREP_API_KEY`
   - `PREP_TIER` ➔ `PREP_TIER`
   - Any other `PREP_` ➔ `PREP_`
2. **MCP Tools & API Endpoints:** 
   - `prep_search` ➔ `prep_search`
   - `prep_impact` ➔ `prep_impact`
   - `prep_audit` ➔ `prep_audit`
   - `prep_observe` ➔ `prep_observe`
   - `prep_concepts` ➔ `prep_concepts`
3. **Python & Rust Imports:** 
   - `from prep.` ➔ `from prep.`
   - `import prep` ➔ `import prep`
   - `use prep_` ➔ `use prep_`
4. **URLs & Domains:** 
   - `runprep.io` ➔ `runprep.io`
   - `prep.com` ➔ `runprep.io`
   - `github.com/EricBintner/Prep` ➔ `github.com/MagneticAnomaly/Prep`
   - `github.com/EricBintner/prep-mcp` ➔ `github.com/MagneticAnomaly/Prep-MCP`
   - `github.com/EricBintner/prep-deploy` ➔ `github.com/MagneticAnomaly/Prep-deploy`
5. **Text & UI Labels (Case Sensitive):** 
   - `Prep` ➔ `Prep`
   - `prep` ➔ `prep` (for remaining lowercase instances)
   - `PREP` ➔ `PREP` (for remaining uppercase instances)

---

### Phase 4: Local Storage & DB Migration
Update the paths where the daemon reads/writes data locally on the user's machine.
- Update `~/.prep/` string references in the Rust daemon and Python backend to `~/.prep/`.
- Ensure SQLite connection strings point to `prep_*.db` instead of `prep_*.db`.

---

### Phase 5: Final Verification & Testing
The agent must execute these commands to prove the migration did not break the build:
1. `pytest` (Must pass all Python tests).
2. `cd engine && cargo check` (Must compile Rust without errors).
3. `npm run build` (Turbo must successfully build all JS/TS workspaces).
4. Start the daemon manually and verify the CLI command `prep` works.
