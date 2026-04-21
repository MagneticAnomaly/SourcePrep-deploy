# @prep/ui

Shared UI component library and design system for Prep.

## Overview

This package provides:
- **Design tokens** — CSS custom properties for colors, typography, spacing
- **React components** — Shared components for dashboard and website
- **Storybook** — Component documentation and visual testing

## Usage

This package is consumed by:
- `websites/` — Prep marketing site and documentation
- Dashboard app (when scaffolded)

### Styles

For public-facing docs pages, import the UI stylesheet:

```ts
import '@prep/ui/styles';
```

This currently includes:

- Design tokens (`src/tokens/index.css`)
- `keyboard-css` for `<kbd>` / shortcut rendering

### Install

```bash
cd packages/ui
npm install
```

### Development

```bash
# Run Storybook for component development
npm run storybook

# Build the library
npm run build

# Watch mode for development
npm run dev
```

## Structure

```
packages/ui/
├── .storybook/           # Storybook configuration
│   ├── main.ts
│   └── preview.ts
├── src/
│   ├── components/       # React components (to be added)
│   ├── lib/
│   │   └── utils.ts      # Utility functions (cn, etc.)
│   ├── stories/          # Storybook stories
│   │   └── Introduction.mdx
│   ├── tokens/
│   │   └── index.css     # Design tokens (CSS custom properties)
│   ├── index.ts          # Package entry point
│   └── types.ts          # TypeScript type definitions
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Design Tokens

Design tokens are defined in `src/tokens/index.css` as CSS custom properties.

### Token Categories

- **Colors** — Background, surface, text, semantic (success/warning/error/info)
- **Typography** — Font families (Google Fonts), sizes, weights, line heights
- **Spacing** — 4px-based scale
- **Border radius** — Consistent corner rounding
- **Shadows** — Elevation system
- **Motion** — Duration and easing functions
- **Z-index** — Stacking order

### Theming

The tokens support light and dark modes:

```css
/* Light mode (default) */
:root {
  --background: 210 20% 98%;
  /* ... */
}

/* Dark mode */
.dark, [data-theme="dark"] {
  --background: 222 47% 11%;
  /* ... */
}
```

## Visual Directions

Before finalizing the design tokens, review the visual direction options in:
`docs/Phase13_Storybook/theme-examples/`

| Direction | File | Personality |
|-----------|------|-------------|
| A: Slate Developer | `direction-a-slate-developer.md` | Clean, professional |
| B: Deep Focus | `direction-b-deep-focus.md` | Dark, immersive |
| C: Signal Green | `direction-c-signal-green.md` | Status-forward |
| D: Warm Craft | `direction-d-warm-craft.md` | Approachable, human |

## Tech Stack

- **React 18** — Component framework
- **TypeScript** — Type safety
- **Tailwind CSS** — Utility-first styling
- **Tremor** — Dashboard component library
- **Radix UI** — Accessible primitives
- **Lucide** — Icon library
- **Storybook** — Component documentation
- **Vite** — Build tool

## Next Steps

1. **Select visual direction** — Review options in `docs/Phase13_Storybook/theme-examples/`
2. **Update tokens** — Apply chosen direction's colors/typography to `src/tokens/index.css`
3. **Build components** — Implement core components (StatusBadge, SearchResult, CodeChunk)
4. **Document in Storybook** — Add stories for each component
