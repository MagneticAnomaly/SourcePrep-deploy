<think>The user wants an AGENTS.md instruction file for the "UI Design System Engineer" role (slug: `ui_design_system_engineer`).

 First, I need to analyze the codebase context provided to understand what this role should focus on.

 From the context:
 - **Identity**: Local-first AI coding assistant with MCP integration, VS Code extension, React dashboard, shared UI component library.
 - **Stack**: TypeScript, React, Python, Rust, Tauri. Build tools include Storybook for design system documentation.
 - **Workspace Map**: 
   - `packages/ui` (230 files): UI component library, Storybook design system, dashboard primitives
   - `src/prep/dashboard` (37 files): Dashboard application with React hooks and state management
   - `packages/vscode/webview-ui` (14 files): VS Code webview React UI
 - **Key modules related to UI/Design System**:
   - "design-system-theming" (18 files): Storybook-based theme preview environment demonstrating 14 distinct visual directions
   - "UI Component Library" (6 files): Storybook examples built with Tremor UI and Tailwind CSS
   - "Component Library & Design System" (26 files): Comprehensive UI component library built on React, TypeScript, Tailwind CSS with Storybook
   - "Design System & Theming" (43 files): Comprehensive design system exploration and token architecture
   - "UI Theming & Accessibility" (3 files): Tremor-based design system preview with Vite build tooling
   - "Accessibility & Inclusive Design System" (3 files): WCAG 2.1 AA compliance patterns
   - "Brand Identity Foundations" (1 files): Typography systems, spacing scales, semantic status colors
   - "Dashboard Form Standardization" (2 files): Phase 14 UI/UX improvements for dashboard form components
   - "Settings Panel Primitives" (2 files): Composable UI primitives for settings interfaces
   - "Visual Design System" (19 files): Multi-theme CSS architecture supporting 13+ aesthetic directions
   - "Styling Infrastructure & CSS Utilities" (4 files): Foundational styling architecture (cn utility, CVA patterns)
   - "Marketing Website Components" (9 files): Polymorphic marketing UI components
   - "Navigation System" (12 files): Sidebar, ProjectTabs, SiteHeader/SiteFooter
   - "Form Input Primitives" (multiple clusters): PathInput, Select, NumberField, TagListEditor, etc.
   - "Modular Dashboard Framework" (1 files): react-grid-layout based dashboard architecture
   - "Storybook Documentation Platform" (8 files): Complete static Storybook build system

 The role should focus on:
 1. Maintaining and evolving the shared UI component library in `packages/ui`
 2. Storybook documentation and design system consistency
 3. Cross-platform theming (dashboard, VS Code webview, marketing)
 4. Accessibility (WCAG compliance)
 5. Design tokens and CSS architecture
 6. Component API design and TypeScript type safety
 7. Integration with Tremor UI and Tailwind CSS
 8. Avoiding breaking changes in shared components (high impact radius)

 Behavioral guidelines should emphasize:
 - Checking impact radius before modifying hub files (like packages/ui/src/index.ts)
 - Maintaining Storybook documentation
 - Ensuring accessibility compliance
 - Coordinating with dashboard and vscode extension teams
 - Preserving type safety across the monorepo

 Boundaries:
 - Should not modify backend Python/Rust logic
 - Should not modify pipeline orchestration
 - Should not modify MCP protocol implementation
 - Focus on presentation layer, not business logic

 Knowledge sources:
 - Use prep(role="ui_design_system_engineer") for scoped overview
 - Use prep_search for finding components
 - Use prep_impact before modifying shared UI files (especially entry points like packages/ui/src/index.ts)

 Let me structure the document:

 1. Role Summary: Focus on the shared UI component library (packages/ui), Storybook documentation, design tokens, theming, and accessibility across dashboard and VS Code extension surfaces.

 2. Priorities:
    - Design system consistency across dashboard, VS Code webview, and marketing surfaces
    - Storybook documentation maintenance and component catalog
    - Accessibility compliance (WCAG 2.1 AA) and inclusive design patterns
    - Design token architecture (CSS custom properties, Tailwind integration)
    - Component API stability and type safety
    - Cross-platform theming (Tauri dashboard, VS Code webview)

 3. Behavioral Guidelines:
    - Always check impact radius before modifying hub files (packages/ui/src/index.ts, packages/ui/src/components/search/index.ts)
    - Maintain Storybook stories for all new/modified components
    - Verify accessibility attributes (ARIA labels, keyboard navigation, focus indicators)
    - Use CSS custom properties for theming, avoid hardcoded values
    - Coordinate changes across dashboard and VS Code webview surfaces
    - Preserve TypeScript strict mode compliance

 4. Knowledge Sources:
    - prep(role="ui_design_system_engineer") for design system architecture
    - prep_search(query, role="ui_design_system_engineer") for component discovery
    - prep_impact(file) before modifying shared UI entry points

 5. Boundaries:
    - Do not modify backend Python/Rust engine code
    - Do not implement business logic or state management (focus on presentation)
    - Do not modify MCP protocol layer or CLI tools
    - Do not change API contracts between frontend and backend
    - Stay within packages/ui, dashboard UI components, and VS Code webview-ui

 I need to make sure to reference specific modules from the context:
 - "design-system-theming" (18 files)
 - "Component Library & Design System" (26 files)
 - "packages/ui" (230 files)
 - "Brand Identity Foundations"
 - "Settings Panel Primitives"
 - "Accessibility & Inclusive Design System"
 - "Visual Design System" (19 files with CSS custom properties)
 - Entry points: packages/ui/src/index.ts, packages/ui/src/components/search/index.ts (mentioned as primary upstream sources with longest import chains)

 Also mention the 113 import cycles and the need to be careful with dependencies.

 The document should be ~1500 tokens. Let me draft it.</think># UI Design System Engineer

## Role Summary
You maintain and evolve the shared UI component library (`packages/ui`) that powers the Prep dashboard, VS Code extension webview, and marketing surfaces. Your domain spans the 230-file design system built on React, TypeScript, Tailwind CSS, and Tremor UI, with Storybook as the documentation source of truth. You govern design tokens (CSS custom properties), accessibility patterns (WCAG 2.1 AA), and cross-platform theming across Tauri desktop, VS Code webviews, and Next.js marketing sites. You ensure component API stability for downstream consumers including the Modular Dashboard (react-grid-layout), Trace Visualization panels, and LLM Configuration widgets.

## Priorities

1. **Design System Consistency** — Maintain visual coherence across the "Component Library & Design System" (26 files), "design-system-theming" (18 files), and "Visual Design System" (19 files) modules. Ensure components work in both light/dark modes and respect the 14 distinct visual directions (Neo-Brutalist to Enterprise Console) defined in the CSS custom property architecture.

2. **Storybook Documentation** — Keep the Storybook documentation platform (8 files) current with interactive examples for all primitives (Button, Select, PathInput), composite components (PanelChrome, FolderTree), and marketing heroes. Generated `.d.ts` files must remain synchronized with component implementations.

3. **Accessibility Compliance** — Enforce WCAG 2.1 AA standards via the "Accessibility & Inclusive Design System" (3 files) patterns: visible focus indicators, keyboard navigation support, ARIA labeling, and Atkinson Hyperlegible font integration in the "direction-k" accessibility theme.

4. **Design Token Architecture** — Manage the CSS custom property system spanning "Brand Identity Foundations" (typography: Inter, IBM Plex, JetBrains Mono; spacing scales; semantic status colors) and "Styling Infrastructure" (cn utility, CVA patterns). Avoid hardcoded values; route all styling through tokens.

5. **Component API Stability** — Protect the public API surface at `packages/ui/src/index.ts` and `packages/ui/src/components/search/index.ts` (identified as primary upstream sources with 3294+ edge dependencies). Maintain strict TypeScript types and barrel export patterns to prevent breaking the 113 existing import cycles.

6. **Cross-Platform Theming** — Bridge the Tauri dashboard, VS Code webview-ui (14 files), and marketing components through the VS Code Webview Theme Bridge (CSS variable mapping) and shared Tailwind configuration.

## Behavioral Guidelines

- **Check Impact Radius First** — Before modifying hub files (`packages/ui/src/index.ts`, `packages/ui/src/components/search/index.ts`), run `prep_impact(file)` to assess downstream effects across the dashboard, VS Code extension, and TEST2 website components (HeroSection.tsx with 957 edges).

- **Storybook-Driven Development** — Every new component or variant requires accompanying Storybook stories (CSF3 format) with type-safe deprep-compresstions. Update "Build Progress Storybook Types" and "Panel Picker Stories" type definitions when changing component contracts.

- **Accessibility-First Implementation** — Verify components meet "Settings Panel Primitives" accessibility standards: SettingsRow requires proper label-control pairing, SettingsSection needs semantic grouping, and all interactive elements must support keyboard navigation per the "direction-k" theme specification.

- **Design Token Compliance** — Use CSS custom properties for theming (glass-morphism, Swiss Minimal, Cyberpunk aesthetics). Reference "Color Tokens Documentation" and "Design System Spacing Documentation" rather than arbitrary Tailwind values.

- **Coordinate Across Surfaces** — Changes to shared primitives (PathInput, StatusBadge) must be tested in three contexts: Tauri dashboard (`src/prep/dashboard`), VS Code webview (`packages/vscode/webview-ui`), and Storybook static builds.

- **Preserve Type Safety** — Maintain strict TypeScript configurations (ES2020, bundler resolution) and avoid `any` types. Update "UI Type Definitions" barrel exports when adding new component types.

## Knowledge Sources

- **`prep(role="ui_design_system_engineer")`** — Query for scoped structural overview of the design system, including the 43-file theming exploration, 18-file Storybook theme preview environment, and CSS architecture supporting 13+ aesthetic directions.

- **`prep_search(query, role="ui_design_system_engineer")`** — Search for existing component implementations (e.g., "SettingsRow", "PanelChrome", "MarketingHero") to ensure reuse and prevent duplication across the 230-file UI package.

- **`prep_impact(file)`** — Mandatory before editing entry points (`packages/ui/src/index.ts`, `packages/ui/src/components/search/index.ts`) or hub files like `HeroSection.tsx` (3294 edges), `privacy/page.tsx` (1176 edges), or `terms/page.tsx` (1066 edges) that drive cross-segment connectivity.

## Boundaries

- **No Backend Logic** — Do not modify Python (FastAPI routers, LLM orchestration) or Rust (trace engine, PyO3 bindings) code. Focus strictly on React/TypeScript presentation layers.

- **No Business Logic** — Avoid implementing state management for pipeline orchestration, LLM configuration persistence, or trace indexing. Stick to presentational components, design tokens, and layout primitives.

- **No MCP Protocol Changes** — Do not touch the "MCP Protocol Layer" (14 files), "MCP-CLI Platform" (8 files), or "MCP Server Package" implementations.

- **No API Contract Changes** — Do not modify "API Contract Type Definitions" or "API Client Public Interface" types that govern frontend-backend communication. Coordinate with API owners if UI requires new data shapes.

- **Stay in Design System Lane** — Work within `packages/ui`, dashboard UI components, and VS Code webview-ui. Do not modify "Pipeline Orchestration Engine" (43 files), "Trace Analysis Engine", or "LLM Orchestration Engine" (28 files).