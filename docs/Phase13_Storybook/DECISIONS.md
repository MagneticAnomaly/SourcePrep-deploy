# Phase 13 Decisions

## Default Theme & Mode
**Decision:** Dark Mode + Theme 'H' (Retro-Futurism).
> **Superseded 2026-05-08 by Phase 131.** The public Storybook now boots in Dark Mode + Theme 'A' (Slate Developer), with the manager chrome restyled in Slate Developer's *light* variant. Retro-Futurism remains an available theme via the toolbar selector but is no longer the default. Rationale: cleaner, IDE-aligned aesthetic for the public design-system showcase. See `docs/Phase131_StorybookCuration/02_visual_design_plan.md`.

**Rationale:**
- "Retro-Futurism" (Theme H) provides a distinctive, high-contrast, developer-centric aesthetic that differentiates Prep.
- Dark mode is the preferred default for developer tools (VS Code, terminal).
- This aligns with the "Deep Focus" and "Operator Console" directions explored.

## Density Toggle
**Decision:** Default to Compact; No toggle for MVP.
**Rationale:**
- Dashboard real estate is valuable.
- The FolderTree and SearchResults lists are information-dense.
- We hardcoded `compact={true}` for the FolderTree.
- A toggle can be added later if user feedback indicates a need for "Comfortable" mode, but for now, "Compact" is the standard for IDE-like tools.
