# Prep Design System

## Overview

This design system defines the visual language for Prep across marketing, documentation, and the application dashboard. It's built on **Tremor React** components with **TailwindCSS** and **CSS custom properties** for dynamic theming.

---

## Design Principles

### 1. Developer-First Aesthetic
- Clean, functional interfaces over flashy effects
- High information density with clear hierarchy
- Monospace fonts for code, readable sans-serif for content

### 2. Local-First Trust
- Dark mode as default (matches developer environments)
- Terminal-inspired color accents
- Privacy-conscious messaging

### 3. Progressive Complexity
- Simple entry points, powerful details on demand
- Layered information architecture
- Smart defaults with customization options

---

## Color System

### Semantic Color Tokens

```css
/* Core */
--background       /* Page background */
--foreground       /* Primary text */
--surface          /* Card/panel background */
--surface-raised   /* Elevated surface (dropdowns, modals) */

/* Brand */
--primary          /* Primary actions, links, accents */
--primary-hover    /* Primary hover state */
--primary-muted    /* Subtle brand accents */

/* Text */
--text             /* Primary text */
--text-muted       /* Secondary text */
--text-subtle      /* Tertiary/disabled text */

/* Borders */
--border           /* Standard borders */
--border-subtle    /* Subtle dividers */

/* Status */
--success          /* Positive states (fresh, connected) */
--success-muted    /* Subtle success backgrounds */
--warning          /* Caution states (stale, pending) */
--warning-muted    /* Subtle warning backgrounds */
--error            /* Error states */
--error-muted      /* Subtle error backgrounds */
--info             /* Informational states */
--info-muted       /* Subtle info backgrounds */

/* Syntax Highlighting */
--syntax-comment   /* Code comments */
--syntax-keyword   /* Keywords (def, async, etc.) */
--syntax-function  /* Function names */
--syntax-string    /* String literals */
```

### Theme Directions

| Theme | Character | Primary Hue | Best For |
|-------|-----------|-------------|----------|
| **A: Slate Developer** | Neutral, professional | Gray-blue | Enterprise, docs |
| **B: Deep Focus** | High contrast, immersive | Deep blue | Dashboard, focus |
| **C: Signal Green** | Terminal-inspired | Green | Developer tools, CLI |
| **D: Warm Craft** | Approachable, warm | Amber/orange | Marketing, onboarding |

---

## Typography

### Font Stack

```css
--font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
--font-mono: 'JetBrains Mono', ui-monospace, monospace;
```

### Scale (Tremor)

| Token | Size | Line Height | Use Case |
|-------|------|-------------|----------|
| `tremor-label` | 0.75rem | 1rem | Labels, captions |
| `tremor-default` | 0.875rem | 1.25rem | Body text |
| `tremor-title` | 1.125rem | 1.5rem | Section titles |
| `tremor-metric` | 1.875rem | 2.25rem | Large numbers |

### Heading Hierarchy (Marketing)

- **H1**: 3rem–3.75rem (48–60px), bold, tight leading
- **H2**: 1.5rem–2rem (24–32px), semibold
- **H3**: 1.125rem–1.25rem (18–20px), medium

---

## Spacing & Layout

### Spacing Scale

```
4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px, 96px
```

### Container Widths

| Context | Max Width | Padding |
|---------|-----------|---------|
| Marketing | 1280px (max-w-7xl) | 24px (px-6) |
| Dashboard | 1280px (max-w-7xl) | 24px (px-6) |
| Docs | 896px (max-w-4xl) | 24px (px-6) |

### Grid System

- **Marketing**: 1 col (mobile) → 2 col (lg)
- **Dashboard**: 1 col → 2 col (md) → 3 col (lg)
- **Cards**: 16–24px gap

---

## Border Radius

```css
--radius-sm: 0.375rem;  /* 6px - small elements */
--radius-md: 0.5rem;    /* 8px - default */
--radius-lg: 0.75rem;   /* 12px - cards */
--radius-xl: 1rem;      /* 16px - large cards */
--radius-2xl: 1.5rem;   /* 24px - hero sections */
```

---

## Shadows

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.15);
```

---

## Components

### Buttons

| Variant | Use Case | Style |
|---------|----------|-------|
| **Primary** | Main CTAs | `bg-primary text-white` |
| **Secondary** | Secondary actions | `border border-border bg-transparent` |
| **Ghost** | Tertiary actions | `bg-transparent hover:bg-surface-raised` |

### Badges

| Color | Use Case |
|-------|----------|
| `green` | Success, fresh, connected |
| `yellow` | Warning, stale, pending |
| `red` | Error, disconnected |
| `blue` | Info, building, new features |
| `gray` | Neutral, disabled |
| `purple` | Pro/premium features |

### Cards

```tsx
// Default card
<Card className="border border-border bg-surface shadow-sm">

// Raised card
<Card className="border border-border bg-surface-raised shadow-md">

// Highlighted card (primary accent)
<Card className="border-2 border-primary/50 bg-primary/5">
```

### Data Visualization Elements

#### Index Stats
- Grid of 2–4 stat boxes
- Large metric number + label + trend indicator
- Subtle background with border

#### Folder Tree
- Collapsible nodes with status indicators
- Status dots: indexed (green), pending (yellow), ignored (gray), error (red)
- Chunk count on hover

#### Trace Graph
- Node cards with kind badges (file, symbol, endpoint)
- In/out degree indicators
- Mini SVG visualization for overview

#### Search Results
- File path with icon
- Line range + relevance score
- Code preview with syntax highlighting
- Hover state with primary border accent

---

## Motion

### Transitions

```css
/* Default transition */
transition: all 150ms ease;

/* Hover lift */
hover:-translate-y-1

/* Status pulse */
animate-pulse (for connection indicators)
```

### Principles
- Subtle, functional motion only
- No gratuitous animations
- Instant feedback for interactions

---

## Responsive Breakpoints

| Breakpoint | Width | Use |
|------------|-------|-----|
| `sm` | 640px | Small tablets |
| `md` | 768px | Tablets |
| `lg` | 1024px | Laptops |
| `xl` | 1280px | Desktops |
| `2xl` | 1536px | Large screens |

---

## Accessibility

- Minimum contrast ratio: 4.5:1 (AA)
- Focus states visible on all interactive elements
- Keyboard navigation supported
- Screen reader labels on icons

---

## File Structure (Storybook-Ready)

```
src/
├── components/
│   ├── index.ts              # Barrel exports
│   ├── FolderTree.tsx        # File tree with status
│   ├── IndexStats.tsx        # Stats grid
│   ├── TraceGraph.tsx        # Symbol graph
│   ├── MarketingHero.tsx     # Hero variants
│   └── FeatureBlocks.tsx     # Feature layouts
├── styles/
│   ├── tokens.css            # Global CSS variables
│   ├── index.css             # Tailwind + base styles
│   └── themes/
│       ├── direction-a.css   # Slate Developer
│       ├── direction-b.css   # Deep Focus
│       ├── direction-c.css   # Signal Green
│       └── direction-d.css   # Warm Craft
```

---

## Usage Notes

### Theme Switching
```tsx
// Set theme via data attribute
document.documentElement.setAttribute('data-prep-theme', 'c');

// Toggle dark mode via class
document.documentElement.classList.toggle('dark', isDark);
```

### Component Variants
- Hero: `centered` | `split`
- Features: `cards` | `list` | `bento`
- Stats: `default` | `compact` | `large`

---

## Next Steps

1. **Storybook Integration**: Create stories for each component
2. **Design Tokens Export**: Generate JSON tokens for Figma sync
3. **Component Testing**: Add visual regression tests
4. **Animation Library**: Consider Framer Motion for complex transitions
