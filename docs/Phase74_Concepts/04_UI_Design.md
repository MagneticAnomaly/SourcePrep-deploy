# Phase 74 — UI Design: Concepts Dashboard Panel

> **Research Document 4 of 5** | Phase 74: Concept Cluster Methodology  
> Date: 2026-04-04

---

## 1. Design Philosophy

The Concepts panel follows two key principles from Phase 71's Architecture Diagram:

1. **Generated + Editable** — LLM generates seeds, user curates to ground truth
2. **Progressive Disclosure** — Dashboard card → Overlay detail → Individual concept editor

### Structural Parallel to Architecture Diagram

| Architecture Diagram | Concepts Panel |
|:---|:---|
| Auto-generated module graph | Auto-generated concept seeds |
| User drags/renames nodes | User edits/approves concept cards |
| ADR sticky notes on nodes | Clarifying questions → concept creation |
| Node overlay badges | Cluster cards with concept counts |
| Sidebar inspector | Concept editor sidebar |
| ELK auto-layout | Leiden auto-clustering |
| Coverage via linked issues | Coverage via module concept-attachment |

---

## 2. Panel Card (Dashboard Grid)

The panel card on the dashboard grid shows a compact summary:

```
┌─────────────────────────────────────────┐
│  💡  Concepts                   [•••]   │
│                                          │
│  19 concepts · 4 clusters                │
│  68% module coverage                     │
│                                          │
│  ██████████████░░░░░░░  68%             │
│                                          │
│  3 pending questions                     │
│  Last updated: 2 hours ago               │
│                                          │
│  Pipeline Architecture (5)               │
│  Brand & Positioning (3)                 │
│  Domain Model (4)                        │
│  API Design Patterns (4)                 │
│  Process & Conventions (3)               │
│                                          │
└─────────────────────────────────────────┘
```

**Before initialization:**
```
┌─────────────────────────────────────────┐
│  💡  Concepts                   [•••]   │
│                                          │
│  Capture conceptual understanding —      │
│  the "why" behind your code.             │
│                                          │
│           ┌─────────────────┐            │
│           │  ✨ Initialize   │            │
│           └─────────────────┘            │
│                                          │
│  CoDRAG will analyze your atlas,         │
│  modules, and audit data to generate     │
│  concept seeds you can curate.           │
│                                          │
│  ~2 minutes · uses deep model            │
│                                          │
└─────────────────────────────────────────┘
```

---

## 3. Detail View (Full-Screen Overlay)

When the panel card is clicked, the full-screen overlay opens with three sections:

### 3.1 Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard        CONCEPTS        [+ Quick Add] [⟳ Regen] │
│  ═══════════════════════════════════════════════════════════════════  │
│                                                                       │
│  ┌──── CLUSTER MAP ────────────────────────────────────────────────┐ │
│  │                                                                  │ │
│  │   ┌────────────────┐    ┌────────────────┐                      │ │
│  │   │ 🏗 Pipeline    │    │ 🎨 Brand &     │                      │ │
│  │   │ Architecture   │    │ Positioning    │                      │ │
│  │   │                │    │                │                      │ │
│  │   │ ■ ■ ■ ■ ■      │    │ ■ ■ ■          │                      │ │
│  │   │ 5 concepts     │    │ 3 concepts     │                      │ │
│  │   │ 🟢 all active  │    │ 🟡 1 seed      │                      │ │
│  │   └────────────────┘    └────────────────┘                      │ │
│  │                                                                  │ │
│  │   ┌────────────────┐    ┌────────────────┐    ┌───────────────┐ │ │
│  │   │ 🗂 Domain      │    │ 🔌 API Design  │    │ 📋 Process &  │ │ │
│  │   │ Model          │    │ Patterns       │    │ Conventions   │ │ │
│  │   │                │    │                │    │               │ │ │
│  │   │ ■ ■ ■ ■        │    │ ■ ■ ■ ■        │    │ ■ ■ ■         │ │ │
│  │   │ 4 concepts     │    │ 4 concepts     │    │ 3 concepts    │ │ │
│  │   │ 🟢 all active  │    │ 🟢 all active  │    │ 🟢 all active │ │ │
│  │   └────────────────┘    └────────────────┘    └───────────────┘ │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════════  │
│                                                                       │
│  ┌──── CONCEPT LIST (filtered by selected cluster) ────────────────┐ │
│  │                                                                  │ │
│  │  🏗 Pipeline Architecture                    [Expand All]       │ │
│  │  ─────────────────────────────────────────────────────────────  │ │
│  │                                                                  │ │
│  │  ┌─ CONCEPT ────────────────────────────────────────────────┐   │ │
│  │  │ 🟢 11-Stage Pipeline Design                     [Edit ✏️]│   │ │
│  │  │                                                           │   │ │
│  │  │ The pipeline uses 11 stages because stages 1-5 are      │   │ │
│  │  │ structural (fast, no LLM) while stages 6-10 are         │   │ │
│  │  │ epistemic (deep, LLM-required). This split enables      │   │ │
│  │  │ "Fast Sync" (stages 1-5 only) for quick updates.        │   │ │
│  │  │                                                           │   │ │
│  │  │ 📎 orchestrator.py, scheduler.py                         │   │ │
│  │  │ 🏷 technical · architecture_rationale                    │   │ │
│  │  │ 📊 Confidence: 0.85 (user-validated)                    │   │ │
│  │  └──────────────────────────────────────────────────────────┘   │ │
│  │                                                                  │ │
│  │  ┌─ CONCEPT (SEED) ────────────────────────────────────────┐    │ │
│  │  │ 🟡 Concurrency Model                                    │    │ │
│  │  │                                                          │    │ │
│  │  │ Pipeline uses 3 model slots (fast, code, deep) to...    │    │ │
│  │  │                                                          │    │ │
│  │  │ [✅ Approve] [✏️ Edit & Approve] [❌ Reject]             │    │ │
│  │  └──────────────────────────────────────────────────────────┘    │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════════  │
│                                                                       │
│  ┌──── CLARIFYING QUESTIONS (3 pending) ───────────────────────────┐ │
│  │                                                                  │ │
│  │  ❓ Why does the pipeline use 11 stages instead of fewer?       │ │
│  │     Context: Most analysis tools use 3-4 stages. CoDRAG's      │ │
│  │     11-stage pipeline is unusually granular.                     │ │
│  │     Suggested category: Technical > Architecture Rationale      │ │
│  │     [💬 Answer] [🚫 Dismiss]                                    │ │
│  │                                                                  │ │
│  │  ❓ What makes orchestrator.py the most important file?         │ │
│  │     Context: This file has 2,643 lines and is the hub of the   │ │
│  │     pipeline — but no concept explains its architectural role.  │ │
│  │     [💬 Answer] [🚫 Dismiss]                                    │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ─── COVERAGE ────────────────────────────────────────────────────── │
│  █████████████░░░░░░ 68% concept coverage                            │
│  7 of 23 significant modules have no concepts attached               │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Interaction Patterns

| Action | Trigger | Result |
|:---|:---|:---|
| **Click cluster** | Click a cluster card in the cluster map | Filters concept list to that cluster |
| **Click concept** | Click a concept card | Opens concept in sidebar editor |
| **Approve seed** | Click ✅ on a seed concept | Status changes to "active", confidence → 1.0 |
| **Edit concept** | Click ✏️ | Opens markdown editor with title, content, anchors, category |
| **Answer question** | Click 💬 | Expands inline editor, answer auto-becomes a new concept |
| **Quick Add** | Click [+ Quick Add] | Opens minimal concept creation form (title + content) |
| **Regenerate** | Click [⟳ Regen] | Runs seeder again, adds NEW seeds (doesn't overwrite existing) |
| **Dismiss question** | Click 🚫 | Question hidden (can be restored from settings) |

### 3.3 Concept Editor Sidebar

When editing a concept, a sidebar slides in (like the Architecture Diagram's inspector):

```
┌────────────────────────────────────┐
│  ✏️  Edit Concept                   │
│  ─────────────────────────────────  │
│                                     │
│  Title:                             │
│  ┌───────────────────────────────┐  │
│  │ 11-Stage Pipeline Design      │  │
│  └───────────────────────────────┘  │
│                                     │
│  Category:                          │
│  ┌───────────────────────────────┐  │
│  │ Technical > Architecture ▼    │  │
│  └───────────────────────────────┘  │
│                                     │
│  Content (Markdown):                │
│  ┌───────────────────────────────┐  │
│  │ The pipeline uses 11 stages   │  │
│  │ because stages 1-5 are       │  │
│  │ structural (fast, no LLM)     │  │
│  │ while stages 6-10 are        │  │
│  │ epistemic (deep, LLM-        │  │
│  │ required). This split         │  │
│  │ enables "Fast Sync"...       │  │
│  └───────────────────────────────┘  │
│                                     │
│  Anchors:                           │
│  📎 orchestrator.py         [✕]     │
│  📎 scheduler.py            [✕]     │
│  [+ Add anchor]                     │
│                                     │
│  Tags:                              │
│  🏷 pipeline  🏷 architecture       │
│  [+ Add tag]                        │
│                                     │
│  Status: 🟢 Active                  │
│  Confidence: 0.85                   │
│  Source: user-validated              │
│                                     │
│  [💾 Save] [🗑 Delete] [📤 Export]  │
│                                     │
│  ── Related Concepts ──────────── │
│  • Concurrency Model               │
│  • Fast Sync vs Deep Enrichment     │
│                                     │
│  ── Source Evidence ──────────── │
│  "The atlas mentions 11 stages      │
│   with a 'Fast Sync boundary'       │
│   at stage 5..."                    │
│                                     │
└────────────────────────────────────┘
```

---

## 4. Answer Flow for Clarifying Questions

When user clicks "Answer" on a clarifying question:

```
Step 1: Question expands inline with a text area

  ❓ Why does the pipeline use 11 stages instead of fewer?
     Context: Most analysis tools use 3-4 stages. CoDRAG's 
     11-stage pipeline is unusually granular.
     
     Your answer:
     ┌─────────────────────────────────────────────────────┐
     │ The stages are split into "structural" (1-5) and    │
     │ "epistemic" (6-10) because they use different       │
     │ computational resources. Stages 1-5 can run         │
     │ without any LLM at all (pure Rust parsing and       │
     │ embedding). This lets us do "Fast Sync" — a quick   │
     │ update after small code changes — in < 30 seconds.  │
     │ The deep stages need LLM access and can take         │
     │ 30-120 minutes, so users only run them when they    │
     │ need deep analysis.                                  │
     └─────────────────────────────────────────────────────┘
     
     [Create Concept] [Save as Draft] [Cancel]

Step 2: On "Create Concept", the system:
  - Creates a new Concept with:
    - title: "11-Stage Pipeline Split" (auto-suggested, editable)
    - content: User's answer (formatted as concept body)
    - category: "Technical > Architecture Rationale" (from question)
    - anchors: From question's target_anchors
    - source: "question_answer"
    - confidence: 1.0 (user-created → ground truth)
  - Marks the question as "answered"
  - Links the question to the new concept
  - Recalculates coverage score

Step 3: Concept appears in the concept list with a ✨ "New" badge
```

---

## 5. Design System Integration

### Color Palette (extends existing CoDRAG dashboard theme)

| Element | Color | Meaning |
|:---|:---|:---|
| Active concept | `var(--success-green)` | Validated, ground truth |
| Seed concept | `var(--warning-amber)` | LLM-generated, needs validation |
| Deprecated concept | `var(--muted-gray)` | Outdated, kept for history |
| Cluster cards | `var(--surface-elevated)` | Slightly elevated surface |
| Question badge | `var(--accent-purple)` | CoDRAG brand purple |
| Coverage bar | Green → Amber → Red | Based on % coverage |

### Typography

- **Concept titles:** `font-weight: 600`, `font-size: 1rem`
- **Concept bodies:** `font-size: 0.875rem`, standard markdown rendering
- **Cluster labels:** `font-weight: 700`, `font-size: 1.125rem`, uppercase tracking
- **Question text:** `font-style: italic` for the question, normal for context

### Animations

- **Cluster card hover:** Subtle elevation + border glow
- **Seed → Active transition:** Card smoothly transitions from amber to green border
- **Question answer → Concept creation:** Collapse question, expand into concept card (smooth)
- **Coverage bar:** Animated fill on update

---

## 6. Mobile / Compact Considerations

The panel card and detail view should work at the existing dashboard's responsive breakpoints:

- **≥1200px:** Full layout as described above
- **900-1199px:** Cluster map becomes 2-column, sidebar overlays instead of side-by-side
- **<900px:** Cluster map stacks vertically, concept list becomes full-width

---

*Next: [05_Implementation_Roadmap.md](./05_Implementation_Roadmap.md) — Phased implementation plan with effort estimates*
