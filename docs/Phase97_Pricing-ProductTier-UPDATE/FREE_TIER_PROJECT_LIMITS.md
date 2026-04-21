# Free Tier Project Limits: "Archive vs Purge" Strategy

## The Problem: The "Musical Chairs" Loophole
We recently updated the CoDRAG Free tier to be fully featured (removing the manual-only restriction) but enforced a hard limit of **3 max projects**. 

However, this creates a loophole: a user could theoretically bypass the 3-project limit by constantly deleting a project to free up a slot, adding a 4th project, and then deleting that to re-add the 1st project. While this causes some friction, if the indexer is fast enough or the user is determined enough, they can avoid upgrading to the Pro tier indefinitely.

## The Solution: "Archive & Lock" vs "Delete & Purge"
To protect the value of the Pro tier ($79 perpetual license) while keeping the Free tier genuinely useful, we introduce a high-friction choice when a Free user attempts to remove a project to free up a slot.

When a Free user hits the 3-project limit and clicks "Remove" on a project, they are presented with a modal offering two distinct paths:

### Option 1: Archive & Lock (The Upsell Path)
*   **Mechanic**: The project's status is changed to `archived` (or `locked`). It no longer counts towards the 3-project active limit, freeing up a slot.
*   **Data Retention**: The trace graph, embeddings, and pipeline data remain safely on disk in the application's data directory.
*   **UX**: The project remains visible in the dashboard sidebar but is visually grayed out with a "Lock" icon. 
*   **Friction**: The user cannot open, search, or update this project. Clicking on it opens a modal: *"Archived projects require a Pro license to unlock. [Enter License Key]"*
*   **Psychology**: This builds a "graveyard of locked value." The user sees projects they have already spent time and API tokens embedding. Paying $79 to instantly unlock all of them feels like a high-ROI decision compared to losing that work.

### Option 2: Delete & Purge (The Friction Path)
*   **Mechanic**: The project is removed from the database entirely, freeing up a slot.
*   **Data Destruction**: We strictly enforce `purge=True` on the backend. The project's UUID folder in `~/.local/share/prep/projects/<uuid>` is permanently wiped from the disk.
*   **Friction**: If the user ever wants to work on this project again, they must re-add it as a brand new project. It will start at 0% context. They must wait for the file walker, the AST parser, the trace graph builder, and crucially, they must pay the time and API token cost (if using BYOK cloud models) to re-embed the entire codebase from scratch.
*   **Psychology**: "Musical chairs" becomes computationally and temporally expensive. Normal users will gladly pay $79 to avoid rebuilding large repositories repeatedly.

## Why this is difficult to hack (UUID Protection)
When a project is added, it is assigned a unique UUID (e.g., `Project-A`). All its data is stored under `~/.local/share/prep/projects/Project-A`. 
If a user deletes the project (triggering the purge), that folder is wiped.
If they try to be clever by copying the `Project-A` folder to their desktop before deleting, and then pasting it back later, it won't work out-of-the-box. When they re-add the repository, the system generates a completely new UUID (`Project-B`). The user would have to manually hack the SQLite `projects.db` to remap the UUIDs, rename the folders, and update internal JSON pointers. This is a level of friction that 99.9% of users will not bother with to save $79.

---

## Implementation Strategy

### 1. Database & Core Logic Updates
*   **State Management**: Update the `ActivityStatus` types (or add an `archived` boolean) in `project_registry.py` and `project_helpers.py`. Currently, Phase 41 implemented `active`, `inactive`, `frozen`, and `locked`. We need to adapt this so Free users can have exactly **3 `active`** projects, and unlimited `locked` (archived) projects.
*   **Limit Enforcement**: Update `feature_gate.py` and `project_helpers.py` to ensure `get_feature_limit("projects_max")` strictly checks the count of `active` projects, ignoring `locked` ones.
*   **Purge Enforcement**: Ensure the `remove_project` method in `project_registry.py` and the `DELETE /projects/{id}` endpoint in `crud.py` correctly accept and execute the `purge=True` parameter to wipe the UUID directory from disk.

### 2. Backend API Updates
*   **Archive Endpoint**: Create a new endpoint (e.g., `POST /projects/{id}/archive` or `PATCH /projects/{id}/status`) that transitions a project from `active` to `locked`.
*   **Unlock Endpoint**: Ensure restoring a project checks the license tier before allowing the transition from `locked` to `active`.
*   **Guardrails**: Update `require_project_writable` to strictly block any pipeline, build, search, or MCP operations on `locked` projects.

### 3. Frontend & UI Updates
*   **Types**: Update `ActivityStatus` in `packages/ui/src/api/types.ts`.
*   **Remove Project Modal**: Redesign the deletion flow. Instead of a simple confirmation, show a split-choice modal: "Archive Project" (recommended/default) vs "Permanently Delete" (destructive, red button).
*   **Sidebar Project List**: Render `locked` projects with a lock icon, disabled state, and an onClick handler that triggers the Pro License Upsell modal rather than routing to the project dashboard.
*   **License Upsell Component**: Create or update the modal that explains the benefits of Pro and provides the input field for the Lemon Squeezy license key.

### 4. Testing & Security
*   **Test Cases**: Write tests to ensure a Free user can only have 3 active projects, but can archive a 4th. Ensure archived projects cannot be searched or rebuilt.
*   **Bypass Prevention**: Ensure the API does not allow renaming or tricking the system into reading an orphaned UUID folder without a valid database entry.
