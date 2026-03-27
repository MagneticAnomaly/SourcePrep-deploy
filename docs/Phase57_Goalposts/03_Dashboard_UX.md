# Goalposts: Dashboard UI & UX Design

## 1. The Goalposts Panel

The core user interface for this feature will be a new dedicated panel in the CoDRAG Dashboard project view, likely accessible via a new tab (e.g., Overview, Chat, **Goalposts**, Settings).

### 1.1 Sprint Proposals (The Inbox)
When the Goalposts pipeline completes a run, it populates an "Inbox" of proposed sprints. For each sprint proposal, the user sees:
- **Title & Abstract:** What the sprint achieves.
- **Rationale:** *Why* the AI is suggesting this based on the codebase's current epistemology (e.g., "Noticed you have a data layer for Users, but no presentation layer yet.").
- **Actions:**
  - **Approve:** Moves the sprint to the "Active Roadmap".
  - **Reject:** Discards the idea completely.
  - **Ignore/Snooze:** Pushes it down the priority list.
  - **Interrogate/Refine:** Opens a localized chat thread with the planning LLM to steer the sprint ("I like this, but let's use standard UUIDs for the auth tokens instead of JWTs.")

### 1.2 The Active Roadmap
Approved sprints populate a standard developer workflow board (Kanban or List view). 
Users can click into an approved sprint to see the generated sub-tasks, and begin executing them using the standard CoDRAG coding assistant tools.

## 2. Epistemic Questions & Research Phases
Sometimes, the AI cannot plan a sprint because it lacks product direction. The Goalposts panel will have a section for **Questions for the User**.
- e.g., "Do you plan to monetize this app? If so, I will propose a Stripe Integration sprint."
- e.g., "Your auth endpoints exist, but there is no rate limiting. Should I plan a security sprint?"
Answering these feeds directly back into the `GoalpostsPlanner` context for the next background run.

## 3. Settings Integration
Because the background planning job uses significant tokens and compute:
- **Default State:** OFF.
- **Enable Toggle:** A prominent toggle in the Goalposts panel: "Enable Continuous Goalpost Planning".
- **Compute Budgeting:** Optional settings to limit how often it runs (e.g., "Only run on manual request", "Run weekly", "Run whenever epistemic index changes heavily").
