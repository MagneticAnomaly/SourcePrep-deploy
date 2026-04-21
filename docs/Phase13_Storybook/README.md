# Phase 13 — Design System + Storybook (App + Website)

## Problem statement
Prep needs a coherent UI/UX across:

- the dashboard (app UI)
- the marketing website
- the public documentation site

If we build UI surfaces independently, we’ll accumulate:

- inconsistent interaction patterns
- duplicated components
- ad-hoc styling decisions that are hard to maintain

At the same time, a “design system” is premature until we have explored multiple viable visual directions.

## Goal
Define a Tremor-based UI foundation and a workflow to:

- prototype multiple visual design directions quickly
- select a single direction with explicit rationale
- formalize it into a shared design system (tokens + components)
- document it in Storybook for consistent implementation across app + website

## Scope

### In scope
- A visual prototyping plan with multiple design options (before standardization)
- A design system plan (tokens, typography, theming, component inventory)
- Storybook scope and usage (docs, examples, accessibility expectations)
- Alignment rules for Tremor + Tailwind usage

### Out of scope
- Full brand identity work (logo system, full illustration system)
- Pixel-perfect final UI for every dashboard page
- Rewriting the dashboard IA (Phase 02 defines that)

## Deliverables
- Visual direction prototypes plan (at least 3 distinct directions)
- Decision rubric for selecting the direction
- Design tokens strategy (how we represent theme, spacing, type, color)
- Component inventory (what we standardize first)
- Storybook baseline plan (structure, naming, documentation expectations)

## Functional specification

### Foundation constraints

- The dashboard UI stack explicitly uses:
  - React
  - TailwindCSS
  - Tremor

This phase must align with those constraints (do not introduce a second competing component system).

### Tremor as the component baseline

Tremor should be treated as:

- the primary source of primitives for layout, data display, and dashboard patterns
- the “default look” we can theme and extend, rather than replacing

Rules:
- Prefer Tremor primitives for tables, cards, charts, tabs, badges, layouts.
- Introduce custom components only when:
  - the pattern is not available in Tremor
  - or it is core to Prep (e.g., code chunk viewer, citation blocks)

### Visual prototyping: multiple directions (pre-design-system)

Before writing a style guide, we prototype multiple UI directions.

#### Output expectation
Create **3–4** visual directions, each expressed through:

- a small set of representative screens/components:
  - App shell layout (sidebar + tabs)
  - Status page card layout
  - Search results list + chunk viewer
  - Context output viewer (citations)
  - Settings form surface
- a small set of token-level decisions:
  - light vs dark baseline
  - typography choice
  - density (compact vs spacious)
  - emphasis style (borders vs elevation)

#### Suggested directions (initial set)
These are intentionally distinct; we pick one later.

1) **Clean Technical Light**
- light default, subtle neutrals, crisp borders
- optimistic, product-led
- good for docs/marketing consistency

2) **Dark Operator Console**
- dark default, higher contrast, “tooling” vibe
- fits developer tools, great for code viewing

3) **Muted Enterprise Neutral**
- conservative neutrals, low-saturation accents
- “security-first”/enterprise trust

4) **High-Contrast Accent**
- stronger brand accent color (still accessible)
- bolder CTAs and highlights

#### Selection rubric
Pick the direction that best supports:

- clarity of status/freshness indicators (trust-first UX)
- readability for code chunks and citations
- accessibility (contrast, focus states)
- long-term maintainability (tokens map cleanly to Tailwind)
- ability to translate into both app UI and marketing/docs

### Design tokens strategy

Define tokens so they are:

- stable across app and website
- implementable in Tailwind
- compatible with Tremor theming

Minimum token categories:
- Color
  - background/surface/border/text
  - semantic status (success/warn/error/info)
  - accents (primary/secondary)
- Typography
  - font families
  - sizes and line heights
  - code font
- Spacing + radii
- Shadows/elevation (if used)
- Motion
  - durations
  - easing

### Component inventory (what to standardize first)

Start with the components that appear in both app + docs:

- App shell
  - sidebar
  - top/breadcrumb area
  - tabs
- Status primitives
  - badges (Fresh/Stale/Building/Pending)
  - status cards
- Search primitives
  - query input
  - results list row
  - empty states
- Code/content primitives
  - code chunk viewer
  - citation blocks
  - copy-to-clipboard button
- Forms
  - toggles
  - input validation messaging

### Storybook expectations

Storybook should:

- be the source of truth for component behavior
- document props and states (loading, empty, error)
- include accessibility considerations and keyboard behavior

Story organization (recommended):
- Foundations
  - Colors
  - Typography
  - Spacing
- Components
  - Navigation
  - Status
  - Search
  - Code/Docs
  - Forms
- Patterns
  - “Trust console” states
  - Empty state patterns
  - Error state patterns

## Success criteria
- We can show 3–4 coherent UI directions to choose from.
- One direction is selected with explicit rationale.
- A token strategy exists that can be implemented in Tailwind and used across surfaces.
- A Storybook plan exists that enumerates initial components and states.

## Dependencies
- Phase 02 (Dashboard) — defines the UI surfaces we need to support
- Phase 12 (Website/Docs) — ensures tokens/components work for marketing/docs pages
- `../WORKFLOW_RESEARCH.md` — trust invariants and UX states

## Open questions
- Should the default experience be light or dark?
- Do we want a “density toggle” (compact vs comfortable) in the app?
- Do we publish Storybook publicly or keep it internal until the UI stabilizes?

## Risks
- Over-designing before the product surfaces exist.
- Creating a design system that fights Tremor instead of leveraging it.
- Token churn causes rework across app + website.

## Testing / evaluation plan
- Accessibility checks for each direction (contrast + focus states)
- Representative user tasks:
  - identify whether a project is fresh/stale
  - copy context output
  - inspect a chunk’s source/span

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 13 gates)
