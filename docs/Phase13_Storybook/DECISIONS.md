# Phase 13 Decisions

## Default Theme & Mode
**Decision:** Dark Mode + Theme 'H' (Retro-Futurism).
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
