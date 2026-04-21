# Prep Visual Design Directions

This folder contains **distinct visual design directions** for Prep's brand identity and UI system.

## Purpose

Before locking in a design system, we prototype multiple directions to:

1. Explore the visual design space
2. Get stakeholder/user feedback on tone and personality
3. Make an informed choice with explicit rationale
4. Avoid premature standardization

## Prep Brand Context

Prep is a **local-first developer tool** for semantic code search and understanding. The visual identity must communicate:

- **Trust** — local-first, no cloud dependency, your data stays yours
- **Developer credibility** — this is a serious tool, not a toy
- **Intelligence** — AI-assisted, but not "AI hype"
- **Clarity** — search results, status, and citations must be instantly readable

Target audiences:
1. **Cursor/Windsurf power users** — expect polished dev tooling
2. **Enterprise teams** (later) — need professional, trustworthy aesthetics

## Visual Directions

| Direction | File | Personality | Best For |
|-----------|------|-------------|----------|
| **A: Slate Developer** | [direction-a-slate-developer.md](./direction-a-slate-developer.md) | Clean, professional, neutral | Wide appeal, enterprise-friendly |
| **B: Deep Focus** | [direction-b-deep-focus.md](./direction-b-deep-focus.md) | Dark, immersive, code-centric | Power users, long sessions |
| **C: Signal Green** | [direction-c-signal-green.md](./direction-c-signal-green.md) | Technical, status-forward, terminal-inspired | Dev-tool credibility, status clarity |
| **D: Warm Craft** | [direction-d-warm-craft.md](./direction-d-warm-craft.md) | Approachable, human, indie-dev feel | Marketing appeal, onboarding |

## Selection Rubric

When choosing a direction, evaluate against:

1. **Trust signaling** — Does it feel secure and local-first?
2. **Code readability** — Are chunks/citations easy to scan?
3. **Status clarity** — Can users instantly see fresh/stale/building?
4. **Marketing fit** — Does it work on a landing page?
5. **Accessibility** — Does it meet WCAG AA contrast?
6. **Tremor compatibility** — Does it extend (not fight) Tremor's patterns?

## Shared UI Package Location

The chosen direction will be implemented in:

```
packages/ui/
├── src/
│   ├── tokens/           # Design tokens (CSS custom properties)
│   ├── components/       # Shared React components (Tremor-based)
│   └── styles/           # Base styles and theme CSS
├── .storybook/           # Storybook configuration
├── package.json
└── tsconfig.json
```

This package will be consumed by:
- `website/` — marketing site + docs
- Dashboard app (when scaffolded)

## How to Use These Directions

1. **Review each direction** — Read the rationale, color palette, typography, and sample component specs.
2. **Compare side-by-side** — Use the selection rubric.
3. **Prototype key components** — Build 2-3 components (status badge, search result, code chunk) in the top candidates.
4. **Decide** — Document the choice and rationale in an ADR.

## Legacy Research Reference

See `../previous-app-legacy-research/` for patterns from a different product (Halley). That product had a very different personality (intimate, personal AI). Prep needs a distinct identity focused on developer trust and tooling credibility.
