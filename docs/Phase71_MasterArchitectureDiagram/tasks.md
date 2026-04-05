# Master Architecture Diagram (Phase 71) Completion Checklist

This task list covers the missing components from Phase 71, specifically focusing on Phase B (Paperclip Integration & Governance) and UI refactoring to clean up the existing Phase A implementation. 

## 🎨 Visual Design Recommendations

Before diving into the checklist, here are some design recommendations for the new UI elements to match CoDRAG's premium, modern aesthetic: importanlty these should be on brand with CoDRAG's existing design system gnerally but these are a new set of components. 

**1. Semantic Issue Badges (Nodes):**
> [!TIP]
> Issue overlays should not crowd the node. Use clean, rounded indicator dots or pills anchored to the top-right corner of the `ModuleNode`.
> *   🔴 **P0/P1 Issues:** Pulsing crimson dot with the issue count (e.g., `3`). The pulsing micro-animation draws immediate attention to architectural vulnerabilities.
> *   🟡 **P2/P3 Issues:** Solid amber dot.
> *   ⚠️ **ACRs:** An amber warning triangle icon `lucide-react/AlertTriangle`.

**2. Glassmorphic Sidebar (DiagramSidebar.tsx):**
> [!NOTE]
> The sidebar inspector should use a rich glassmorphism effect (translucent dark background with a subtle border) so that the diagram remains partially visible underneath. This maintains the user's spatial context while they read ACR details or Agent notes.

**3. Interactive Flow Cues:**
> [!TIP]
> When a user clicks a node that has a linked Paperclip issue, the node should emit a brief "ripple" effect, and the corresponding issue card in the Sidebar should briefly flash to associate the two elements visually.

**4. EntryPoint Nodes (Diamond shape):**
> [!TIP]
> Diamonds can sometimes look blocky. Ensure the diamond shape uses a subtle `border-radius: 4px` on its vertices and an inner gradient fill to make it look like a cohesive, modern part of the CoDRAG design system rather than a legacy UML diagram.

---

## 📋 Task Checklist

### 1. Frontend Refactoring & Cleanup (Phase A Remediation)
- `[ ]` Extract `<DiagramSidebar />` out of `ArchitectureDiagramDetail.tsx`.
- `[ ]` Extract `<DiagramToolbar />` out of `ArchitectureDiagramDetail.tsx`.
- `[ ]` Extract `<BreadcrumbNav />` out of `ArchitectureDiagramDetail.tsx`.
- `[ ]` Build `<EntryPointNode />` (Diamond shape) for API surfaces.

### 2. Backend Governance APIs (Phase B)
- `[ ]` Build `src/codrag/core/architecture_acr.py` for ACR lifecycle (Create, Approve, Reject).
- `[ ]` Add `GET /projects/{id}/architecture/acrs` to `architecture.py`.
- `[ ]` Add `POST /projects/{id}/architecture/acrs` to `architecture.py`.
- `[ ]` Add `PUT /projects/{id}/architecture/acrs/{acr_id}/approve` to `architecture.py`.
- `[ ]` Add issue-linking endpoints (`POST /link-issue`, `DELETE /link-issue`) to `architecture.py`.

### 3. Agent & Paperclip Integration (Phase B)
- `[ ]` Add `POST /projects/{id}/architecture/create-task` endpoint to handle right-click node -> Paperclip Issue creation via `PaperclipClient`.
- `[ ]` Add `POST /projects/{id}/architecture/briefing` to generate text briefings for agents.
- `[ ]` Expand `codegen` context in `mcp/server.py` to ensure it dynamically reads linked ACRs and issues from the architecture state.

### 4. UI Governance Overlays (Phase B)
- `[ ]` Build `<IssueBadge />` and integrate into `<ModuleNode />` and `<FileNode />`.
- `[ ]` Build `<ACRPanel />` inside the new `<DiagramSidebar />` for reviewing Architecture Change Requests.
- `[ ]` Wire right-click context menu to trigger "Create Paperclip Task".

### 5. Automated Agent Governance (Phase C - Future)
- `[ ]` Update Researcher Agent to auto-generate ACRs based on Audit architecture findings.
- `[ ]` Update Custodian Agent to mark dead/unused modules on the diagram.
