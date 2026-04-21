# Settings TODO — Phase 02 (Dashboard)

## Purpose
This document consolidates **all settings/configuration knobs** referenced across `docs/` (phases, TODOs, opportunities, API contract), and maps them to a dashboard settings UX plan.

It is split into:
- **Required**: settings we must surface to satisfy near-term phase plans (Phase 02–05) and current daemon/UI config surfaces.
- **Opportunities**: additional controls that improve trust, performance, and debuggability, but can be staged.

---

## Required settings (Phase02 MVP + Phase03/04/05 alignment)

### 1) Project identity + scope (per-project)
- **Repo root / project path**
  - **Scope:** per-project
  - **Source:** `docs/Phase02_Dashboard/README.md` (project add flow)
  - **UI control:** path input + validation

- **Roots selection: `core_roots` + `working_roots`**
  - **Scope:** per-project
  - **Source:** daemon UI config (`ui_config.json`) already supports these fields
  - **UI control:** folder tree multi-select (two buckets)
  - **Why:** supports “index only what matters” without relying solely on globs

### 2) Index input policy (per-project)
- **Include patterns: `include_globs`**
  - **Scope:** per-project
  - **Source:** `docs/API.md` (`PUT /projects/{project_id}`), `docs/Phase02_Dashboard/README.md`, `docs/Phase04_TraceIndex/REPO_DISCOVERY_AND_POLICY.md`
  - **UI control:** tag list editor (add/remove)

- **Exclude patterns: `exclude_globs`**
  - **Scope:** per-project
  - **Source:** same as include
  - **UI control:** tag list editor (add/remove)

- **Max file size: `max_file_bytes`**
  - **Scope:** per-project
  - **Source:** `docs/API.md`, `docs/Phase01_Foundation/README.md`, `docs/Phase02_Dashboard/README.md`
  - **UI control:** number input (bytes) with helper text (recommended presets)

### 3) Auto-rebuild / watch controls (per-project; Phase03)
- **Auto-rebuild enabled: `auto_rebuild.enabled`**
  - **Scope:** per-project
  - **Source:** `docs/Phase03_AutoRebuild/README.md`, `docs/API.md` project config schema
  - **UI control:** toggle

- **Debounce interval: `watch.debounce_ms` / `auto_rebuild.debounce_ms`**
  - **Scope:** per-project
  - **Source:** `docs/Phase03_AutoRebuild/README.md` watch block
  - **UI control:** number input (ms) with preset buttons (3s/5s/10s)

- **Min rebuild gap: `min_rebuild_gap_ms`**
  - **Scope:** per-project
  - **Source:** `docs/Phase03_AutoRebuild/TODO.md` (storm control layers)
  - **UI control:** number input (ms)

### 4) Trace settings + bounded traversal (per-project; Phase04)
- **Trace enabled toggle: `trace.enabled`**
  - **Scope:** per-project
  - **Source:** `docs/API.md` project config schema; `docs/Phase02_Dashboard/README.md`; `docs/Phase04_TraceIndex/README.md`
  - **UI control:** toggle + “Build trace now” action

- **Trace neighbors caps (default UI controls; enforce server hard caps)**
  - **Scope:** per-request defaults (stored as UI defaults)
  - **Source:** `docs/API.md` trace neighbors endpoint; `docs/Phase04_TraceIndex/opportunities.md`
  - **Controls:**
    - `direction` (`in|out|both`) dropdown
    - `edge_kinds` multi-select
    - `hops` stepper (1–2)
    - `max_nodes` number input

### 5) Search + context budgets (per-request defaults, Phase02/05)
- **Search budget**
  - **Source:** `docs/API.md` search contract; Phase05 “bounded outputs”
  - **Controls:** `k`, `min_score`

- **Context budget**
  - **Source:** `docs/API.md` context contract; `docs/Phase02_Dashboard/TODO.md` (bounded UI)
  - **Controls:** `k`, `max_chars`, `min_score`, `include_sources`, `include_scores`, `structured`

- **Trace-aware context expansion budget**
  - **Source:** `docs/Phase04_TraceIndex/opportunities.md`
  - **Controls:** `max_additional_chunks`, `max_additional_chars` (and an “enabled” toggle)

### 6) Providers (global; Phase02 baseline)
- **Ollama URL**
  - **Scope:** global
  - **Source:** `docs/Phase02_Dashboard/README.md`, `docs/API.md` (`/llm/status`, `/llm/test`)
  - **UI control:** text input + “Test” button

- **Default embedding model**
  - **Scope:** global
  - **Source:** `docs/Phase02_Dashboard/README.md`
  - **UI control:** model dropdown populated from `/llm/status` models

---

## Opportunities (more control, better trust UX)

### A) Settings presets (Phase02 opportunities)
- **Preset selector**: “Laptop / Workstation / Monorepo”
  - Suggested to control:
    - `debounce_ms`, `min_rebuild_gap_ms`
    - future: embedding batch size / concurrency
    - future: polling fallback behavior

### B) Watch storm control + fallback modes (Phase03 opportunities)
- **Polling fallback toggle + polling interval bounds**
- **Throttle behavior controls** (when changes never settle)
- **Manual reconciliation tool** (“re-scan for missed changes”)
- **Loop avoidance inspector**: show resolved ignore list, warn if index dir is inside watched tree

### C) Index coverage + diagnostics (Phase02/07 opportunities)
- **Index coverage explorer**: extension counts, top excluded matches, skip reasons (too large/binary)
- **First-class logs UI**: per-project build logs + daemon log
- **Copy diagnostics bundle**: version/OS/config snapshot/last error codes (redaction-friendly)

### D) Config diff + provenance (Phase02/06 opportunities)
- **Settings diff**: current vs default
- **Config provenance UI**: show source for each setting:
  - default / global / team policy / project override

### E) Team/enterprise safety settings (Phase06/11 alignment)
- **Network mode indicator + auth-required status** (post-MVP implementation)
- **API base URL + API key management** (client-side config)
- **Offline mode indicator** (air-gapped posture; disable internet calls)

### F) Advanced model configuration (Phase04 LLM model config)
- **Saved endpoints** (Ollama/OpenAI/Anthropic/openai-compatible) with per-endpoint API keys
- **Model slots** (embedding/small/large) + test actions
- **HuggingFace download UX** for embedding (optional)

---

## Storybook / component checklist (what the settings panel needs)

### Already present in `packages/ui` (should be used by the dashboard)
- **Per-project settings**: `ProjectSettingsPanel` (+ story exists)
- **Provider + model settings**: `AIModelsSettings`, `EndpointManager`, `ModelCard` (+ stories exist)
- **Watch indicators**: `WatchStatusIndicator` (+ story exists)

### Missing or should be standardized (add to Storybook)
- **Settings layout primitives**
  - `SettingsPageLayout` (tabs/sections)
  - `SettingsSection` (title + description)
  - `SettingsRow` (label/description + control)

- **Form primitives**
  - `ToggleSwitch` (currently inline inside `ProjectSettingsPanel`)
  - `NumberField` (min/max + unit + validation message)
  - `TagListEditor` (extract from include/exclude editors)

- **Budgets primitives**
  - `BudgetPill` (e.g., `max_chars`, `max_nodes`)
  - `BudgetPreview` (estimated chars/tokens)

- **Policy/provenance primitives**
  - `ConfigProvenanceRow` (default/global/team/project)
  - `ConfigDiffSummary` (changed vs default)

- **Diagnostics primitives**
  - `ProviderTestButton` / `ConnectivityStatusRow`
  - `CopyDiagnosticsButton`

---

## Notes
- This list is intentionally **UI-first** and does not assume a final backend storage schema.
- Any setting that can affect privacy/security (API keys, remote mode) should follow the Phase06/11 guidance: **secret-free configs are repo-committable; secrets remain per-user/local**.
