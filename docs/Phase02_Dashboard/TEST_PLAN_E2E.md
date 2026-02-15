# Phase 02 Dashboard E2E Smoke Test Plan

This document outlines the End-to-End (E2E) smoke test strategy for the CoDRAG Dashboard (Phase 02).
The goal is to verify the critical "Trust Loop" user journey works from the frontend perspective, supported by the backend API.

## User Journey: "The Trust Loop"

1.  **Onboarding**: User adds a local project.
2.  **Indexing**: User triggers a build and sees progress.
3.  **Discovery**: User searches for a concept.
4.  **Inspection**: User views a code chunk and opens the source file.
5.  **Action**: User assembles context for an LLM.

## Automated Smoke Test (API Level)

Implemented in: `tests/test_dashboard_e2e_flow.py`

This test simulates the Dashboard's API calls using `TestClient`.

### Steps Covered:
1.  **Add Project**: `POST /projects`
    *   *Verify*: Project appears in `GET /projects`.
2.  **Initial Status**: `GET /projects/{id}/status`
    *   *Verify*: Status is "pending" or "not built".
3.  **Trigger Build**: `POST /projects/{id}/build`
    *   *Verify*: Status transitions to "building".
4.  **Poll Completion**: Loop `GET /projects/{id}/status`
    *   *Verify*: Status becomes "fresh" (`index.exists=True`).
5.  **Search**: `POST /projects/{id}/search`
    *   *Verify*: Results returned with scores and paths.
6.  **Read File (Pin/Open)**: `GET /projects/{id}/file?path=...` (New P02 feature)
    *   *Verify*: Content of the file corresponding to a search result is returned.
    *   *Verify*: Security guards (path traversal) work.
7.  **Assemble Context**: `POST /projects/{id}/context`
    *   *Verify*: Context string is generated.

## Manual Smoke Test (UI Level)

To be executed manually against a running dev server (`npm run dev` + `python -m codrag.server`).

### Prerequisites
- CoDRAG Daemon running on port 8400.
- Dashboard running on port 5173 (or embedded).
- A valid test repository (e.g., `tests/fixtures/mini_repo`).

### Test Script

| Step | Action | Expected Outcome |
| :--- | :--- | :--- |
| **1. Setup** | Open Dashboard. Ensure "No Project Selected" or empty state. | App loads without white screen. Sidebar is visible. |
| **2. Add** | Click "+" in Sidebar. Enter path to `mini_repo`. Click "Add". | Project appears in Sidebar. "Index Status" card shows "Not Built". |
| **3. Build** | Click "Initialize" or "Rebuild" on Status Card. | Badge changes to "Building". Progress bar appears. Event logs show activity. Badge becomes "Fresh" (Green). |
| **4. Search** | Go to "Knowledge Query". Type "hello". Press Enter. | "Retrieved Context" panel populates with chunks. |
| **5. Inspect** | Click a result in "Retrieved Context". | "Chunk Preview" shows content. |
| **6. Pin/Open** | (If enabled) Click file path or "Pin" icon. | "Pinned Files" panel opens/updates with full file content. |
| **7. Context** | Go to "Context Options". Click "Get Context". | "Prompt Buffer" populates with formatted context. |
| **8. Settings** | Open Settings (Gear icon). Change Theme. | UI theme updates immediately. |

## Regression Checklist (P02-T2)

- [ ] **Error Handling**:
    - Try adding a non-existent path -> Should show toast error.
    - Try searching before build -> Should show "Index not built" error in panel.
- [ ] **State Persistence**:
    - Reload page -> Selected project remains selected.
    - Reload page -> Pinned files remain pinned.
