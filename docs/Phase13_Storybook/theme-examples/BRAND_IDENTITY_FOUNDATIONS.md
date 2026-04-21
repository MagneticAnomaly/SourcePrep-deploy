# Prep Brand Identity Foundations

This document defines the **shared brand foundations** that apply across all visual directions. These are the constants—the elements that make Prep recognizable regardless of which color palette or visual style is chosen.

---

## Brand Essence

### Tagline Options
- "Local-first code intelligence"
- "Your codebase, understood"
- "Semantic search for developers"

### Brand Attributes
| Attribute | Description | Visual Expression |
|-----------|-------------|-------------------|
| **Trustworthy** | Local-first, your data stays yours | Solid foundations, clear status |
| **Intelligent** | AI-assisted, not AI-dependent | Clean, not flashy |
| **Developer-native** | Built for developers, by developers | Code-centric UI, monospace |
| **Precise** | Accurate retrieval, clear citations | Tight spacing, aligned grids |

### Brand Voice
- **Confident but not arrogant** — "Prep indexes your code" not "Prep is the best"
- **Technical but accessible** — Explain concepts, don't assume knowledge
- **Honest** — Clear about what it does and doesn't do
- **Helpful** — Error messages guide users to solutions

---

## Logo Concept (Placeholder)

The Prep logo should incorporate:
- **"Co"** — collaboration, code, connection
- **"D"** — documentation, data, discovery
- **"RAG"** — retrieval, the technical core

Visual directions to explore:
- Stylized magnifying glass over code brackets `</ >`
- Abstract graph/network nodes (representing RAG retrieval)
- Minimalist wordmark with distinctive letter treatment

**Note:** Final logo design is out of scope for Phase 13. This is a placeholder for future brand work.

---

## Typography System

### Primary Font: Sans-Serif (UI + Body)

**Recommended options (all Google Fonts, free):**

| Font | Personality | Best For Direction |
|------|-------------|-------------------|
| [Inter](https://fonts.google.com/specimen/Inter) | Neutral, highly legible | A: Slate Developer |
| [IBM Plex Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) | Technical, trustworthy | B: Deep Focus |
| [Roboto](https://fonts.google.com/specimen/Roboto) | Clean, familiar | C: Signal Green |
| [DM Sans](https://fonts.google.com/specimen/DM+Sans) | Friendly, geometric | D: Warm Craft |
| [Source Sans 3](https://fonts.google.com/specimen/Source+Sans+3) | Adobe-quality, open | Any |

**Selection criteria:**
- Must have good weight range (400, 500, 600, 700)
- Must be highly legible at small sizes (13-14px)
- Must have matching monospace variant (or good pairing)
- Must be free and self-hostable

### Monospace Font: Code Display

**Recommended options:**

| Font | Personality | Ligatures |
|------|-------------|-----------|
| [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) | Developer-focused, distinctive | Yes |
| [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) | Matches Plex Sans | No |
| [Roboto Mono](https://fonts.google.com/specimen/Roboto+Mono) | Matches Roboto | No |
| [DM Mono](https://fonts.google.com/specimen/DM+Mono) | Matches DM Sans, quirky | No |
| [Fira Code](https://fonts.google.com/specimen/Fira+Code) | Popular, ligatures | Yes |
| [Source Code Pro](https://fonts.google.com/specimen/Source+Code+Pro) | Adobe-quality | No |

**Selection criteria:**
- Must pair well with chosen sans-serif
- Must be highly legible for code (distinguish 0/O, 1/l/I)
- Ligatures optional (some developers love them, some hate them)

### Display Font (Optional, Marketing Only)

For hero headlines on landing pages:

| Font | Personality | Usage |
|------|-------------|-------|
| [Fraunces](https://fonts.google.com/specimen/Fraunces) | Expressive serif | D: Warm Craft |
| [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) | Technical, distinctive | B: Deep Focus, C: Signal Green |
| [Outfit](https://fonts.google.com/specimen/Outfit) | Modern geometric | A: Slate Developer |

**Note:** Display fonts are optional and only for marketing pages. The app UI should use the primary sans-serif.

---

## Type Scale (Shared Across Directions)

Based on a **1.125 (Major Second)** ratio with **16px** base:

| Token | Size | Rem | Typical Usage |
|-------|------|-----|---------------|
| `--text-xs` | 12px | 0.75rem | Labels, captions, badges |
| `--text-sm` | 14px | 0.875rem | UI text, secondary content |
| `--text-base` | 16px | 1rem | Body text, default |
| `--text-lg` | 18px | 1.125rem | Emphasized body, lead text |
| `--text-xl` | 20px | 1.25rem | Section headings |
| `--text-2xl` | 24px | 1.5rem | Page headings |
| `--text-3xl` | 30px | 1.875rem | Large headings |
| `--text-4xl` | 36px | 2.25rem | Hero text (marketing) |
| `--text-5xl` | 48px | 3rem | Display (marketing) |

### Line Heights

| Token | Value | Usage |
|-------|-------|-------|
| `--leading-none` | 1 | Single-line display text |
| `--leading-tight` | 1.25 | Headings |
| `--leading-snug` | 1.375 | Subheadings |
| `--leading-normal` | 1.5 | Body text |
| `--leading-relaxed` | 1.625 | Long-form content |
| `--leading-loose` | 2 | Captions, labels |

### Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `--font-normal` | 400 | Body text |
| `--font-medium` | 500 | Emphasized text, labels |
| `--font-semibold` | 600 | Headings, buttons |
| `--font-bold` | 700 | Strong emphasis, display |

---

## Spacing System (Shared)

Based on **4px** base unit:

| Token | Value | Px | Common Usage |
|-------|-------|-----|--------------|
| `--space-0` | 0 | 0 | Reset |
| `--space-0.5` | 0.125rem | 2px | Micro spacing |
| `--space-1` | 0.25rem | 4px | Tight padding |
| `--space-1.5` | 0.375rem | 6px | Icon gaps |
| `--space-2` | 0.5rem | 8px | Default gap |
| `--space-2.5` | 0.625rem | 10px | — |
| `--space-3` | 0.75rem | 12px | Small padding |
| `--space-3.5` | 0.875rem | 14px | — |
| `--space-4` | 1rem | 16px | Default padding |
| `--space-5` | 1.25rem | 20px | Medium padding |
| `--space-6` | 1.5rem | 24px | Section gaps |
| `--space-8` | 2rem | 32px | Large gaps |
| `--space-10` | 2.5rem | 40px | — |
| `--space-12` | 3rem | 48px | Section spacing |
| `--space-16` | 4rem | 64px | Page sections |
| `--space-20` | 5rem | 80px | Hero spacing |
| `--space-24` | 6rem | 96px | Large sections |

---

## Semantic Status Colors (Shared Meaning)

Regardless of visual direction, these meanings are constant:

| State | Meaning | Icon Shape |
|-------|---------|------------|
| **Success / Fresh** | Index is up-to-date, operation succeeded | ● filled circle or ✓ |
| **Warning / Stale** | Attention needed, changes detected | ◐ half-fill or ↻ |
| **Error** | Operation failed, critical issue | ✕ or ! |
| **Info / Building** | In progress, informational | ◌ ring or spinner |
| **Neutral / Disabled** | Inactive, unavailable | ○ empty or — |

**Accessibility requirement:** Never rely on color alone. Always pair with:
- Icon shape
- Text label
- Position/context

---

## Iconography

### Icon Library: Lucide React

[Lucide](https://lucide.dev/) is the recommended icon library:
- Open source, MIT licensed
- Consistent 24x24 grid
- Over 1,000 icons
- React components available
- Matches Tremor's default icons

### Icon Sizing

| Size | Px | Usage |
|------|-----|-------|
| `--icon-xs` | 12px | Inline with small text |
| `--icon-sm` | 16px | Inline with body text, badges |
| `--icon-md` | 20px | Buttons, list items |
| `--icon-lg` | 24px | Section headers, emphasis |
| `--icon-xl` | 32px | Empty states, features |

### Key Icons (Prep-Specific)

| Concept | Icon Name | Lucide |
|---------|-----------|--------|
| Search | `Search` | ✓ |
| Project | `FolderCode` or `FolderGit` | ✓ |
| Build/Index | `Database` or `HardDrive` | ✓ |
| Fresh | `CheckCircle` | ✓ |
| Stale | `RefreshCw` | ✓ |
| Building | `Loader2` (animated) | ✓ |
| Code chunk | `FileCode` | ✓ |
| Copy | `Copy` / `Check` | ✓ |
| Settings | `Settings` | ✓ |
| Trace | `GitBranch` or `Network` | ✓ |

---

## Border Radius Scale (Shared)

The radius values differ per direction, but the semantic scale is shared:

| Token | Usage |
|-------|-------|
| `--radius-none` | No rounding (0) |
| `--radius-sm` | Small elements (inputs, badges) |
| `--radius-md` | Default (buttons, cards) |
| `--radius-lg` | Larger cards, panels |
| `--radius-xl` | Modals, popovers |
| `--radius-2xl` | Large feature cards |
| `--radius-full` | Pills, avatars, circular buttons |

---

## Z-Index Scale (Shared)

| Token | Value | Usage |
|-------|-------|-------|
| `--z-base` | 0 | Default stacking |
| `--z-dropdown` | 50 | Dropdowns, selects |
| `--z-sticky` | 60 | Sticky headers |
| `--z-modal-backdrop` | 70 | Modal overlay |
| `--z-modal` | 80 | Modal content |
| `--z-popover` | 90 | Popovers, tooltips |
| `--z-toast` | 100 | Toast notifications |
| `--z-tooltip` | 110 | Tooltips (highest) |

---

## Breakpoints (Shared)

| Token | Width | Target |
|-------|-------|--------|
| `--screen-sm` | 640px | Mobile landscape |
| `--screen-md` | 768px | Tablet |
| `--screen-lg` | 1024px | Small desktop |
| `--screen-xl` | 1280px | Desktop |
| `--screen-2xl` | 1536px | Large desktop |

**Note:** Prep is primarily a desktop application, but the marketing site and docs must be mobile-friendly.

---

## Motion Principles (Shared)

### Principles
1. **Purposeful** — Animation conveys meaning, not decoration
2. **Quick** — Respect user's time (prefer 150-250ms)
3. **Subtle** — Don't distract from content
4. **Consistent** — Same patterns throughout

### Duration Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-instant` | 0ms | Immediate (disabled state) |
| `--duration-fast` | 100-150ms | Micro-interactions, hovers |
| `--duration-normal` | 200-250ms | Standard transitions |
| `--duration-slow` | 300-350ms | Complex animations |
| `--duration-slower` | 500ms | Elaborate sequences |

### Easing Functions

| Token | Curve | Usage |
|-------|-------|-------|
| `--ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General purpose |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exit animations |
| `--ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Enter animations |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Symmetric |
| `--ease-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful feedback |

---

## Accessibility Requirements (Non-Negotiable)

### Color Contrast
- **Normal text:** 4.5:1 minimum (WCAG AA)
- **Large text (18px+):** 3:1 minimum
- **UI components:** 3:1 minimum against adjacent colors

### Focus States
- All interactive elements must have visible focus indicators
- Focus ring should be high contrast (typically primary color)
- Focus must work for both mouse and keyboard navigation

### Motion
- Respect `prefers-reduced-motion` media query
- Provide instant alternatives for all animations
- No flashing content (3 flashes/second max)

### Semantic HTML
- Use proper heading hierarchy (h1 → h2 → h3)
- Use buttons for actions, links for navigation
- Provide alt text for meaningful images
- Use ARIA labels where needed

---

## Next Steps

1. **Choose a visual direction** — Review the 4 directions and select one
2. **Finalize typography pairing** — Pick sans + mono fonts
3. **Define color palette** — Lock in the specific hex/HSL values
4. **Build Storybook foundation** — Implement tokens in code
5. **Create core components** — Status badge, search result, code chunk
