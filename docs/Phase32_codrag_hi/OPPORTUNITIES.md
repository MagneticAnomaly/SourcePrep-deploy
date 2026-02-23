# `hi_codrag` — Opportunities & Expansion Roadmap

> Last updated: 2026-02-21

## Core Principle

**The selected files ARE the context.** `hi_codrag` exists to show the user what CoDRAG can see and help them take the next step. The trace graph, atlas routing, and index are invisible infrastructure — the user cares about *their files*.

---

## Current Capabilities (shipped)

| Capability | How it works |
|-----------|-------------|
| **File inventory** | Categorizes selected files (docs, code, tests, config) with actual filenames |
| **Content-aware prompts** | Prompts adapt based on what's selected: design docs → "summarize plans", API code → "review endpoints", docs + code → "compare design to implementation" |
| **Health observations** | Stale index, low trace coverage, auto-rebuild status — mentioned naturally, not as a status page |
| **Trace as background** | Code graph mentioned as a capability ("I can trace connections"), not the lead |
| **Two-scenario AI guidance** | `_ai_note` tells the AI how to present: standalone (conversational overview + prompts) vs. with-prompt (brief ack + answer) |
| **File inventory payload** | Structured `file_inventory` dict with filenames + paths per category — AI can reference specific files |

---

## Question Categories

When a user says `hi_codrag`, the suggested prompts should match **what they're trying to do**. We can detect intent from what's selected:

### Category 1: Planning & Architecture
**Trigger:** Design docs, architecture docs, RFC/proposal docs selected
**Example prompts:**
- "What do the design docs say? Summarize the plans and identify next steps."
- "Compare the design docs to the implementation — is anything out of sync?"
- "What's the proposed architecture and what's already built?"

### Category 2: Implementation Review
**Trigger:** Code files selected (especially focused selections ≤10 files)
**Example prompts:**
- "Walk me through this code — what does each file do and how do they relate?"
- "What API endpoints are in these files? Any missing error handling?"
- "What UI components are here and how do they connect?"

### Category 3: Task Management
**Trigger:** TODO.md, ROADMAP.md, backlog, task files selected
**Example prompts:**
- "What's on the TODO/roadmap? What should I work on next?"
- "Which tasks are blocked and which can I start now?"
- "Prioritize these tasks by impact and effort."

### Category 4: Quality & Testing
**Trigger:** Test files selected, or code + tests together
**Example prompts:**
- "Review my tests — what's well-covered and what's missing?"
- "What edge cases aren't tested?"
- "Generate test cases for the untested code paths."

### Category 5: Debug & Investigation
**Trigger:** Small focused selection (1-3 files), or files with "error", "bug", "fix" in names
**Example prompts:**
- "What could go wrong in this code? Find potential bugs."
- "Trace the data flow through these files."
- "What happens when this function gets invalid input?"

### Category 6: Onboarding & Discovery
**Trigger:** Large selection (whole project), or first-time use (no prior queries)
**Example prompts:**
- "What does this project do? Give me a high-level overview."
- "What are the key data models or types?"
- "What are the most connected modules in the code graph?"

---

## Near-Term Opportunities (next 1-2 sprints)

### O-1: Doc Content Previews — ✅ SHIPPED
**What:** For .md files in the selection, include the first heading + first paragraph (~200 chars) in the response.
**Implementation:** Parallel API calls to `GET /projects/{id}/file?path=...` for top 5 .md files. Extracts `# heading` + first paragraph. Returned as `doc_previews` array in the response.
**Impact:** Transforms `hi_codrag` from "I see you have design docs" to "Your design doc covers 'Overall Upgrade Plan' (phased site redesign)..."
**Tests:** 4 tests in `test_hi_codrag.py::TestO1DocPreviews`.

### O-2: Hub File Identification — ✅ SHIPPED
**What:** Use the trace graph to identify which selected files are hubs (highest in-degree).
**Implementation:** New `GET /projects/{id}/trace/hub_files?k=5` endpoint returns top hub files by in-degree. Wired into `tool_hi()` summary: "Most connected files: `EnhancedHero.tsx` (6 connections)..."
**Impact:** Users immediately see which files are most important in their selection.
**Tests:** 4 tests in `test_hi_codrag.py::TestO2HubFiles`.

### O-3: Filename-Based Topic Detection — ✅ SHIPPED
**What:** Cluster filenames into recognizable topics (authentication, e-commerce, UI components, API layer, data models, animation, etc.).
**Implementation:** `_detect_topics()` in `tool_hi()` splits filenames (CamelCase, snake_case, kebab-case) into stems, matches against 12 keyword clusters, returns top 5 topics with matched files. Surfaced in summary: "It looks like you're working on: **authentication** (`login.py`, `session.py`)...". Topic-specific prompts generated: "Review the auth flow — any security concerns?"
**Impact:** Prompts feel project-specific instead of generic.
**Tests:** 11 tests in `test_hi_codrag.py::TestO3TopicDetection`.

### O-4: Smart Prompt Ordering — ✅ SHIPPED
**What:** Order prompts by likely relevance based on dominant file category.
**Implementation:** `_prompt_score()` scores each prompt by keyword match to the dominant category (docs, code, tests). Cross-cutting prompts get a boost when both docs+code are selected. `prompts.sort(key=_prompt_score, reverse=True)`.
**Impact:** First prompt is now the most relevant to what the user selected.
**Tests:** 3 tests in `test_hi_codrag.py::TestO4SmartPromptOrdering`.

---

## Medium-Term Opportunities (next 1-3 months)

### O-5: Ambient Context Chain — ✅ SHIPPED
**What:** Guide the AI to call `codrag` (ambient context) after `hi_codrag` for deeper content.
**Implementation:** `_ai_note` includes a "DEEPER CONTEXT" section: "For detailed file content, call `codrag` (the ambient context tool) — it returns LOD-stratified content from hub files and module summaries."
**Impact:** AI chains tools naturally without user having to manually request deeper context.
**Tests:** 2 tests in `test_hi_codrag.py::TestO5AmbientContextChain`.

### O-6: Selection-Aware Search — ✅ ALREADY HANDLED BY CORE
**Status:** The index is built from `included_paths` only (see `core/index.py` line 337). Search results are already inherently scoped to the user's file selection because unselected files never enter the index. `path_weights` further boost/demote at search time.
**Remaining opportunity:** If a user changes their file tree selection but hasn't rebuilt, results still reflect the old selection. The stale-detection system already warns about this via `hi_codrag` health notes.

### O-7: Change Detection — ✅ SHIPPED
**What:** Show which selected files have changed since the last index build.
**Implementation:** Extracts `stale` array from trace coverage response. Filenames surfaced in summary: "Changed since last build: `auth.py`, `login.tsx`." Also generates a stale-aware prompt: "Review what changed in `auth.py` since the last build."
**Impact:** Users know immediately if their context is outdated.
**Tests:** 3 tests in `test_hi_codrag.py::TestO7ChangeDetection`.

### O-8: Cross-File Relationship Summary — ✅ SHIPPED
**What:** For selections (≤30 files), show how the selected files relate using the trace graph.
**Implementation:** New `GET /projects/{id}/trace/file_edges?paths=...` endpoint returns edges between selected files. Surfaced in summary: "File connections: `HeroPhase.tsx` imports `EnhancedHero.tsx`, `EnhancedHero.tsx` imports `ParallaxController.tsx`."
**Impact:** Users see the structure of their selection at a glance.
**Tests:** 3 tests in `test_hi_codrag.py::TestO8CrossFileRelationships`.

### O-9: Question History — 🔨 NEW WORK  - not in MVP scope
**Core status:** Not in core. No query history storage.
**What:** Remember the user's last 3-5 questions and use them to make prompts more relevant.
**Why:** "You were just asking about authentication — want to continue?" is powerful continuity.
**How:** Store recent queries in SQLite (per project). Include in `hi_codrag` response.
**Consideration:** Privacy — should be opt-in or at least clearable.

---

## Long-Term Opportunities (3-6 months)

### O-10: Interactive Discovery Mode — 🔨 NEW WORK
**Core status:** Not in core. Would chain existing `codrag_search` tool calls.
**What:** After `hi_codrag`, the AI enters a "discovery mode" where it proactively explores the codebase and reports findings.
**Why:** Instead of the user asking questions, the AI says "I found 3 interesting things about your selection..."
**How:** Chain multiple `codrag_search` calls with heuristic queries based on the file inventory.

### O-11: Adaptive Prompt Learning — 🔨 NEW WORK - not in MVP scope
**Core status:** Not in core. Needs analytics/telemetry infrastructure.
**What:** Track which suggested prompts users actually use. Promote popular ones, demote ignored ones.
**Why:** Data-driven improvement of the first-contact experience.
**How:** Log prompt selections (anonymized). Use frequency to reorder.

### O-12: Multi-Selection Comparison — 🔨 NEW WORK - not in MVP scope
**Core status:** Not in core.
**What:** Allow `hi_codrag` to compare two selections: "What changed between the old auth/ and new auth/?"
**How:** Accept a `compare_to` param with a second set of paths.

### O-13: IDE Tab Awareness — ⛔ BLOCKED (MCP spec limitation)
**Core status:** Not in core. MCP spec doesn't expose open editor tabs.
**What:** If the IDE passes open editor tabs via MCP extensions, use them as a secondary signal.
**Why:** Open tabs + file tree selection = maximum context about what the user is working on.
**How:** MCP `initialize` roots give workspace, not open files. Need IDE-specific extensions.
**Status:** MCP spec doesn't support this yet. Monitor for extensions.

---

## Tool Expansion Ideas

### New tools that complement `hi_codrag`:

| Tool | Description | Trigger |
|------|-------------|---------|
| `codrag_diff` | Show what changed since last build (file-level diff summary) | User asks "what changed?" |
| `codrag_explain` | Deep-dive into a specific file with full trace context | User picks a file from `hi_codrag` inventory |
| `codrag_plan` | Generate a task plan from selected docs + code state | User has TODO/design docs selected |
| `codrag_review` | Code review of selected files using trace + test coverage | User has code + tests selected |

These are all **composable with `hi_codrag`**: the AI calls `hi_codrag` first for context, then chains with specialized tools.

---

## Example Scenarios

### Scenario A: User selects design docs + components folder
```
User: hi_codrag

AI: Hi! I'm looking at your project — you've selected 3 design docs
(DESIGN_SPEC.md, COMPONENT_GUIDE.md, UI_PATTERNS.md) and 12 React
components in components/ (Button, Modal, Sidebar, NavBar...).

From the filenames, it looks like you have UI design guidelines and
the actual component implementations. The trace graph shows Button
and Modal are the most-used components (imported by 8+ files each).

Here's what I can help with:
1. Summarize the design docs and identify next steps
2. Compare the design guidelines to the current components — anything out of sync?
3. Walk through the component hierarchy — how do they connect?
4. What UI components are missing based on the design spec?
```

### Scenario B: User selects TODO.md + a few code files
```
User: hi_codrag

AI: I can see your TODO.md and 4 code files in src/auth/ (login.py,
session.py, tokens.py, middleware.py). Looks like you're working on
the auth system.

Here's what I can help with:
1. What's on the TODO? Prioritize by impact
2. Walk me through the auth flow — how do these files connect?
3. Review the auth code for security issues
4. What's missing from the auth implementation?
```

### Scenario C: User selects a focused set of test files
```
User: hi_codrag

AI: I'm looking at 6 test files in tests/api/ (test_users.py,
test_auth.py, test_orders.py, test_payments.py, test_webhooks.py,
test_admin.py). These cover the API layer.

Here's what I can help with:
1. Review these tests — what's well-covered and what's missing?
2. What edge cases aren't tested?
3. Generate additional test cases for the gaps
4. Compare test coverage to the actual API endpoints
```

---

## Implementation Priority

| Priority | Opportunity | Effort | Impact | Status |
|----------|------------|--------|--------|--------|
| **P0** | O-1 (Doc previews) | Low | High — transforms greeting from filename-aware to content-aware | ✅ SHIPPED |
| **P0** | O-2 (Hub files) | Low | High — shows which files matter most | ✅ SHIPPED |
| **P1** | O-3 (Topic detection) | Medium | High — makes prompts feel project-specific | ✅ SHIPPED |
| **P1** | O-8 (Cross-file relationships) | Medium | High — shows structure at a glance | ✅ SHIPPED |
| **P2** | O-4 (Smart prompt ordering) | Low | Medium — improves first-click rate | ✅ SHIPPED |
| **P2** | O-6 (Selection-aware search) | Low | Medium — already partially implemented via scope boost | ✅ Core handles |
| **P2** | O-7 (Change detection) | Low | Medium — useful but not transformative | ✅ SHIPPED |
| **P3** | O-5 (Ambient context chain) | Medium | Medium — token cost concern | ✅ SHIPPED |
| **P3** | O-9 (Question history) | Medium | Medium — continuity is nice but not critical | Not in MVP |
| **P4** | O-10+ (Long-term) | High | Varies | Not in MVP |
