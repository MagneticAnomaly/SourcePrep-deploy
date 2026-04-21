# HR Agent — Edge Cases & Generation Modes

> **Phase 67 Research** | Date: 2026-04-01
> How the HR Agent handles insufficient data, first-run behavior, and the three generation modes.

---

## 1. The Three Generation Modes

### 1.1 Mode: `list`

**User provides exact roles. System generates exactly those.**

```
Input:  ["CTO", "UX Designer"]
Output: Exactly 2 agents — CTO and UX Designer, scoped to this codebase
```

**Behavior:**
1. User types or selects role titles from a suggestion palette
2. HR Engine generates a RoleVector for each title using the LLM role resolver (Phase 64)
3. HR Engine writes AGENTS.md + SOUL.md for each, using codebase context to ground the descriptions
4. No analysis of "what the codebase needs" — user knows what they want

**When to use:** User has an existing team structure or specific roles in mind. They want Prep to generate high-quality role files but don't need organizational advice.

**Dashboard UX:**
```
┌──────────────────────────────────────────────────────┐
│  Generate Agent Workforce                             │
│                                                       │
│  Mode: ○ Auto   ○ Auto + Roles   ● Specific Roles    │
│                                                       │
│  Add roles:                                           │
│  ┌─────────────────────────────────┐                  │
│  │ CTO                          ✕  │                  │
│  │ UX Designer                  ✕  │                  │
│  └─────────────────────────────────┘                  │
│  [+ Add Role]                                         │
│                                                       │
│  [Generate 2 Agents]                                  │
└──────────────────────────────────────────────────────┘
```

---

### 1.2 Mode: `auto`

**System analyzes the codebase and generates its best-guess workforce.**

```
Input:  (nothing — just the codebase)
Output: N agents, where N is determined by codebase complexity
```

**Behavior:**
1. HR Engine reads module clusters, architecture layer distribution, domain tag frequency, hub files
2. Determines organizational needs:
   - Many presentation modules + design system → suggests UX role
   - Heavy infrastructure/deploy → suggests DevOps role
   - Multiple API modules + auth → suggests Security role
   - Large codebase (>200 files) → more specialized roles
   - Small codebase (<50 files) → fewer, more generalist roles
3. Uses the Thinking LLM to reason about the optimal team structure
4. Generates all roles with full AGENTS.md + SOUL.md + org chart

**When to use:** User wants Prep to figure out the ideal team for their codebase. Greenfield setup.

**Dashboard UX:**
```
┌──────────────────────────────────────────────────────┐
│  Generate Agent Workforce                             │
│                                                       │
│  Mode: ● Auto   ○ Auto + Roles   ○ Specific Roles    │
│                                                       │
│  Prep will analyze your codebase and recommend      │
│  the optimal agent team structure.                    │
│                                                       │
│  Optional context:                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ E-commerce platform for artisan goods...    │      │
│  └─────────────────────────────────────────────┘      │
│  (Help the HR agent understand your business)         │
│                                                       │
│  [Analyze & Generate]                                 │
└──────────────────────────────────────────────────────┘
```

---

### 1.3 Mode: `auto+list`

**System runs auto analysis but MUST include the user-specified roles.**

```
Input:  ["Social Media Manager", "Mobile Engineer"]
Output: N agents (auto-determined), guaranteed to include Social Media Manager 
        and Mobile Engineer, plus whatever else the codebase analysis suggests
```

**Behavior:**
1. HR Engine runs the full auto analysis (same as Mode 2)
2. Before finalizing the role list, checks that the user-specified roles are present
3. If the auto analysis already suggested a matching role → merge (prefer user's title if different)
4. If the auto analysis didn't suggest it → add it to the list with a note: "Added by user request; limited codebase evidence for this role"
5. Generates all roles with inter-role relationships properly wired

**When to use:** User wants the auto analysis but has specific roles they know they need (e.g., a Social Media Manager that doesn't show up from codebase analysis alone).

**Dashboard UX:**
```
┌──────────────────────────────────────────────────────┐
│  Generate Agent Workforce                             │
│                                                       │
│  Mode: ○ Auto   ● Auto + Roles   ○ Specific Roles    │
│                                                       │
│  Prep will analyze your codebase AND include        │
│  the roles you specify.                               │
│                                                       │
│  Required roles:                                      │
│  ┌─────────────────────────────────────────────┐      │
│  │ Social Media Manager                     ✕  │      │
│  │ Mobile Engineer                          ✕  │      │
│  └─────────────────────────────────────────────┘      │
│  [+ Add Role]                                         │
│                                                       │
│  Optional context:                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ Debate platform for structured discourse... │      │
│  └─────────────────────────────────────────────┘      │
│                                                       │
│  [Analyze & Generate]                                 │
└──────────────────────────────────────────────────────┘
```

---

## 2. Edge Cases

### 2.1 Insufficient Codebase Data

**Scenario:** User runs HR generation on a project with:
- No pipeline run completed (no epistemic data)
- Very few files (<10)
- No documentation, no README
- No clear architecture (all files in root, random naming)

**Behavior:**

The HR Engine computes an **epistemic readiness score** before generating:

```python
def compute_hr_readiness(project_id: str) -> HRReadiness:
    """Evaluate whether we have enough data to generate meaningful roles."""
    
    checks = {
        "pipeline_complete": has_completed_pipeline(project_id),
        "minimum_files": file_count >= 20,
        "has_modules": module_count >= 2,
        "has_domain_tags": tag_coverage > 0.5,  # >50% of files have tags
        "has_architecture_layers": layer_diversity >= 3,  # At least 3 distinct layers
        "has_documentation": doc_file_count >= 1,
        "has_hub_files": hub_count >= 1,
    }
    
    score = sum(checks.values()) / len(checks)
    
    return HRReadiness(
        score=score,
        checks=checks,
        recommendation=classify_readiness(score),
    )
```

| Readiness Score | Recommendation | Allowed Modes |
|----------------|----------------|---------------|
| **> 0.7** | ✅ "Ready for full analysis" | All modes |
| **0.4 – 0.7** | 🟡 "Partial data — limited accuracy. Consider running the pipeline first." | `list` only; `auto` with warning |
| **< 0.4** | 🔴 "Insufficient codebase data for meaningful role generation." | `list` only (with disclaimer) |

**What the user sees when readiness is low:**

```
┌──────────────────────────────────────────────────────┐
│  ⚠️  Insufficient Codebase Data                      │
│                                                       │
│  Prep doesn't have enough information to            │
│  recommend an agent team for this project.            │
│                                                       │
│  Missing:                                             │
│  ✕ Pipeline not completed (no epistemic analysis)     │
│  ✕ Only 8 files detected                              │
│  ✕ No module clusters available                       │
│  ✓ Documentation found (README.md)                    │
│  ✕ No hub files detected                              │
│                                                       │
│  Recommendations:                                     │
│  1. Run the Prep pipeline first (Build → Fast Sync) │
│  2. Add documentation (README, architecture docs)     │
│  3. Structure your code into directories/modules       │
│                                                       │
│  You can still manually specify roles (List mode),    │
│  but Prep cannot guarantee the generated             │
│  instructions will be well-grounded.                  │
│                                                       │
│  [Run Pipeline First]  [Generate Anyway (List Mode)]  │
└──────────────────────────────────────────────────────┘
```

**Key design decision:** The HR Agent NEVER silently generates bad roles. It explicitly tells the user "I don't have enough to work with" and recommends concrete steps to improve data quality.

---

### 2.2 Single-Domain Codebase

**Scenario:** The codebase is entirely frontend (React components, no backend, no infra).

**Behavior:**
- Auto mode generates fewer roles (maybe just: Lead Engineer, UX Designer, QA)
- Does NOT generate backend/infra roles unless user explicitly requests them
- The org chart is flatter (no need for deep hierarchy on a small surface area)
- LLM reasoning explicitly acknowledges: "This is a frontend-only codebase. Backend and infrastructure roles are not recommended until backend code is added."

---

### 2.3 Massive Monorepo

**Scenario:** 5000+ files, 50+ modules, multi-language, multiple apps.

**Behavior:**
- Auto mode generates more specialized roles (potentially 8-12 agents)
- Suggests domain-specific roles: "Payments Module Owner", "Auth System Lead"
- May recommend a hierarchical structure with middle management (VP Engineering → Lead Engineers)
- Budget estimates scale accordingly
- Warns user about token cost of running many agents

---

### 2.4 Previously Generated Roles (Idempotency)

**Scenario:** User runs "Generate" a second time on the same project.

**Behavior:**
- HR Engine detects existing `agents/` directory or Paperclip agents
- Presents three options:
  1. **Regenerate**: Wipe and start fresh (destructive)
  2. **Merge**: Keep existing roles, add/update based on new analysis (smart)
  3. **Cancel**: Abort

- Merge mode uses the drift detection system:
  - Roles that still align → keep as-is
  - Roles with drift → update AGENTS.md with new priorities/context
  - New roles needed → add to the roster
  - Roles no longer needed → flag for review (never auto-delete)

---

### 2.5 Conflicting Role Titles

**Scenario:** User specifies "Backend Dev" in list mode, but auto analysis would have suggested "Platform Engineer" for the same domain.

**Behavior:**
- In `list` mode: Use user's exact title, no conflict
- In `auto+list` mode: If auto suggests "Platform Engineer" and user specified "Backend Dev":
  - Detect overlap via domain tag comparison
  - Merge into the user's title ("Backend Dev") but incorporate the broader scope the auto analysis detected
  - Note in the role file: "This role was specified by the user. Prep's analysis suggests this domain also covers platform infrastructure."

---

### 2.6 No Business Context Provided

**Scenario:** User runs auto mode without providing any business description.

**Behavior:**
- HR Engine uses ONLY codebase structure to infer the business
- The Atlas and module summaries provide indirect business context
- Generated role descriptions are more technical and less business-oriented
- The system notes: "Business context was not provided. Role descriptions focus on technical responsibilities. Provide a business description for more contextual role definitions."

---

### 2.7 Agent Elimination Proposals

**Scenario:** Drift audit detects a role has become irrelevant (e.g., a "Ruby Engineer" role in a codebase that has migrated entirely to TypeScript).

**Behavior:**
- HR Agent NEVER auto-deletes a role
- Presents an "Elimination Proposal" in the audit report:

```
┌──────────────────────────────────────────────────────┐
│  🔴 Elimination Proposal: Ruby Engineer               │
│                                                       │
│  Fitness Score: 0.12 (Critical Drift)                 │
│                                                       │
│  Reason: No Ruby files remain in the codebase.        │
│  The project has fully migrated to TypeScript.         │
│  0 of 47 recommended files overlap with this role.    │
│                                                       │
│  Recommended Action:                                  │
│  • Reassign responsibilities to "Lead Engineer"        │
│  • Archive this role                                  │
│                                                       │
│  [Archive Role]  [Keep (Override)]  [Dismiss]          │
└──────────────────────────────────────────────────────┘
```

---

### 2.8 Pipeline Rebuild Happens Mid-Audit

**Scenario:** A pipeline rebuild starts while HR audit is running.

**Behavior:**
- HR audit uses a **snapshot** of epistemic data taken at audit start time
- The audit result may become stale immediately, but this is acceptable since audits are low-frequency
- The next scheduled audit will pick up the new pipeline data
- Dashboard shows: "Audit based on pipeline state from [timestamp]. A newer pipeline build has completed."

---

## 3. First-Run Behavior

### 3.1 Decision: Manual Trigger Only

HR generation is NOT automatic on first pipeline build. The user must explicitly choose to generate a workforce.

**Rationale:**
- Building agents is a significant decision (budget, org structure, permissions)
- The user may not want agents at all — Prep is useful without Paperclip
- Auto-generating agents without consent would be surprising and potentially expensive

### 3.2 First-Run Dashboard Flow

When a project has a completed pipeline but no HR workforce configured, the dashboard shows a subtle entry point:

```
┌──────────────────────────────────────────────────────┐
│  ┌─ New Panel: Agent Workforce ──────────────────┐   │
│  │                                                │   │
│  │  🤖 Agent Workforce                            │   │
│  │                                                │   │
│  │  No agents configured for this project.        │   │
│  │                                                │   │
│  │  Prep can analyze your codebase and generate │   │
│  │  a complete AI agent team optimized for your   │   │
│  │  project's architecture.                       │   │
│  │                                                │   │
│  │  [Get Started]                                 │   │
│  │                                                │   │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

Clicking "Get Started" opens the HR Generation wizard (the mode selector shown above).

### 3.3 After First Generation

The panel transforms into the ongoing management view:

```
┌──────────────────────────────────────────────────────┐
│  🤖 Agent Workforce                          [⚙️]    │
│                                                       │
│  6 agents │ Overall Health: 87% │ Last Audit: 2h ago  │
│                                                       │
│  ┌────────┬────────────────────┬───────┬──────────┐  │
│  │ Agent  │ Title              │ Score │ Status   │  │
│  ├────────┼────────────────────┼───────┼──────────┤  │
│  │ CEO    │ Chief Executive    │ 0.91  │ 🟢       │  │
│  │ CTO    │ Chief Technology   │ 0.88  │ 🟢       │  │
│  │ CMO    │ Chief Marketing    │ 0.74  │ 🟡       │  │
│  │ VP Eng │ VP Engineering     │ 0.82  │ 🟢       │  │
│  │ UX     │ Lead Designer      │ 0.45  │ 🟠       │  │
│  │ QA     │ QA & DevOps Lead   │ 0.93  │ 🟢       │  │
│  └────────┴────────────────────┴───────┴──────────┘  │
│                                                       │
│  [Run Audit]  [Sync to Paperclip]  [Add Agent]       │
└──────────────────────────────────────────────────────┘
```

---

## 4. Generation Modes — LLM Prompt Design

### 4.1 Auto Mode System Prompt

```
You are an organizational architect for AI agent workforces. Given a codebase's 
structural analysis, determine the optimal team of autonomous AI agents to 
manage and evolve this codebase.

CODEBASE ANALYSIS:
- Total files: {file_count}
- Modules: {module_count}
- Architecture layers: {layer_distribution}
- Domain tags (top 20): {top_domain_tags}
- Hub files: {hub_files}
- Languages: {language_distribution}
- Atlas summary: {atlas_excerpt}

{business_context if provided}

CONSTRAINTS:
- Each role should have clear, non-overlapping responsibilities
- The org chart should be as flat as practical
- Every role must have a direct connection to the codebase's actual structure
- Include a CEO/lead role only if the team has 3+ members
- Do NOT generate roles that the codebase provides no evidence for

OUTPUT FORMAT:
Return a JSON array of role specifications...
```

### 4.2 List Mode System Prompt

```
You are a role definition specialist for AI agent workforces. Given a codebase's 
structural analysis and a specific role title, generate a detailed role definition 
tailored to THIS codebase.

ROLE TO DEFINE: {role_title}

CODEBASE ANALYSIS:
{same as above}

Generate a role definition that connects the role title to the specific 
modules, files, and domains that this role would own in this codebase.
```

### 4.3 Auto+List Mode Behavior

The auto+list prompt is the same as auto mode, but with an additional constraint:

```
REQUIRED ROLES:
The following roles MUST appear in your output, regardless of whether the 
codebase analysis suggests them:
{user_specified_roles}

If a required role has limited codebase evidence, still include it but note 
the limited evidence in the role description.
```

---

## 5. Dashboard Panel Integration

### 5.1 Where It Lives

The HR panel is a new `ModularDashboard` panel type, registered via `useDashboardPanels`:

```typescript
// In useDashboardPanels hook
{
  id: 'agent-workforce',
  title: 'Agent Workforce',
  icon: Users,  // from lucide-react
  category: 'management',
  minimumPipelineStage: 'atlas',  // Requires at least atlas to be meaningful
  content: <AgentWorkforcePanel {...hrProps} />,
  details: <AgentWorkforceDetails {...hrProps} />,
}
```

### 5.2 Panel States

| State | What Shows |
|-------|-----------|
| No pipeline | Grayed out with "Run pipeline first" message |
| Pipeline complete, no agents | "Get Started" empty state |
| Generating | Animated progress with LLM reasoning steps |
| Agents configured | Roster table with health scores |
| Drift detected | Amber/red indicators with "Run Audit" prompt |
| Audit running | Progress indicator |
| Audit complete | Results inline with action buttons |

### 5.3 Detail Drawer

Clicking a role in the roster opens a detail drawer (same pattern as existing Prep panels):

```
┌──────────────────────────────────────────────────────┐
│  ← CTO — Chief Technology Officer          [Edit ✏️] │
│                                                       │
│  Fitness: 0.88 🟢  │  Last Updated: 2h ago           │
│                                                       │
│  ── AGENTS.md ──────────────────────────────────────  │
│  [rendered markdown preview]                          │
│                                                       │
│  ── SOUL.md ────────────────────────────────────────  │
│  [rendered markdown preview]                          │
│                                                       │
│  ── Knowledge Scope ────────────────────────────────  │
│  12 files selected │ [View/Edit Tree]                 │
│                                                       │
│  ── Role Vector ────────────────────────────────────  │
│  presentation: ██░░░░░░░░ 0.2                         │
│  business_logic: ████████░░ 0.8                       │
│  infrastructure: ██████████ 1.0                       │
│  ...                                                  │
│                                                       │
│  ── Drift History ──────────────────────────────────  │
│  Mar 28: Fitness 0.92 → Apr 1: 0.88 (-0.04)          │
│  Reason: 3 new infrastructure modules added            │
│                                                       │
│  [Sync to Paperclip]  [Re-analyze]  [Archive]         │
└──────────────────────────────────────────────────────┘
```
