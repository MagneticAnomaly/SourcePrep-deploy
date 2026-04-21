# Direction B: Deep Focus

**Personality:** Dark, immersive, code-centric
**Mood:** Professional, focused, "in the zone"
**Best for:** Power users, long coding sessions, IDE integration

---

## Rationale

Deep Focus is a **dark-first** direction that feels native to the developer's workflow. It's designed to minimize eye strain during extended use and to feel at home alongside dark-mode IDEs like VS Code, Cursor, and Windsurf.

This direction prioritizes:
- **Immersion** — the UI recedes, content shines
- **Code readability** — optimized for syntax highlighting
- **IDE kinship** — feels like part of the dev environment
- **Reduced eye strain** — comfortable for long sessions

---

## Color Palette

### Dark Mode (Default)

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 220 13% 10% | `#16181d` | Page background |
| `--surface` | 220 13% 13% | `#1e2028` | Cards, panels |
| `--surface-raised` | 220 13% 16% | `#262932` | Elevated surfaces |
| `--surface-overlay` | 220 13% 8% | `#111318` | Modals backdrop |
| `--border` | 220 10% 22% | `#33363f` | Borders, dividers |
| `--border-subtle` | 220 10% 18% | `#2a2d35` | Subtle separators |
| `--text` | 220 10% 93% | `#ebedf0` | Primary text |
| `--text-muted` | 220 8% 65% | `#9da3ae` | Secondary text |
| `--text-subtle` | 220 6% 45% | `#6b7280` | Tertiary text |

### Light Mode (Optional)

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 220 14% 96% | `#f3f4f6` | Page background |
| `--surface` | 0 0% 100% | `#ffffff` | Cards, panels |
| `--surface-raised` | 220 14% 93% | `#e5e7eb` | Elevated surfaces |
| `--border` | 220 13% 85% | `#d1d5db` | Borders, dividers |
| `--text` | 220 13% 10% | `#16181d` | Primary text |
| `--text-muted` | 220 8% 40% | `#5c6370` | Secondary text |

### Accent Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--primary` | 210 100% 60% | `#3399ff` | Primary actions, links |
| `--primary-hover` | 210 100% 55% | `#1a8cff` | Hover state |
| `--primary-muted` | 210 100% 60% / 12% | — | Backgrounds |
| `--primary-glow` | 210 100% 60% / 25% | — | Focus rings, highlights |

### Semantic Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--success` | 142 70% 50% | `#2dd36f` | Fresh, success states |
| `--success-muted` | 142 70% 50% / 12% | — | Success backgrounds |
| `--warning` | 45 100% 55% | `#ffc409` | Stale, attention states |
| `--warning-muted` | 45 100% 55% / 12% | — | Warning backgrounds |
| `--error` | 0 75% 58% | `#eb445a` | Error, destructive |
| `--error-muted` | 0 75% 58% / 12% | — | Error backgrounds |
| `--info` | 199 90% 55% | `#17a2e8` | Info, building states |
| `--info-muted` | 199 90% 55% / 12% | — | Info backgrounds |

### Syntax Highlighting (Code Chunks)

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--syntax-keyword` | 286 60% 67% | `#c678dd` | Keywords |
| `--syntax-string` | 95 50% 55% | `#98c379` | Strings |
| `--syntax-function` | 207 82% 66% | `#61afef` | Functions |
| `--syntax-variable` | 29 54% 61% | `#d19a66` | Variables |
| `--syntax-comment` | 220 6% 45% | `#5c6370` | Comments |
| `--syntax-number` | 29 54% 61% | `#d19a66` | Numbers |

---

## Typography

### Font Stack

```css
--font-sans: 'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, sans-serif;
--font-mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Code', monospace;
```

**Google Fonts:**
- [IBM Plex Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) — Technical, readable, IBM's open-source typeface
- [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) — Matching monospace for code

**Alternative:**
- [Source Code Pro](https://fonts.google.com/specimen/Source+Code+Pro) — If you want a warmer mono feel

### Type Scale

| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `--text-xs` | 0.75rem (12px) | 400 | 1.6 | Labels, line numbers |
| `--text-sm` | 0.8125rem (13px) | 400 | 1.55 | Code, UI text |
| `--text-base` | 0.9375rem (15px) | 400 | 1.5 | Body text |
| `--text-lg` | 1.0625rem (17px) | 500 | 1.45 | Emphasized text |
| `--text-xl` | 1.25rem (20px) | 600 | 1.35 | Section headings |
| `--text-2xl` | 1.5rem (24px) | 600 | 1.3 | Page headings |
| `--text-3xl` | 1.875rem (30px) | 700 | 1.25 | Hero text |

Note: Slightly smaller base size (15px vs 16px) for denser information display.

---

## Spacing & Layout

### Spacing Scale (4px base)

```css
--space-0: 0;
--space-0.5: 0.125rem;  /* 2px */
--space-1: 0.25rem;     /* 4px */
--space-1.5: 0.375rem;  /* 6px */
--space-2: 0.5rem;      /* 8px */
--space-3: 0.75rem;     /* 12px */
--space-4: 1rem;        /* 16px */
--space-5: 1.25rem;     /* 20px */
--space-6: 1.5rem;      /* 24px */
--space-8: 2rem;        /* 32px */
--space-10: 2.5rem;     /* 40px */
--space-12: 3rem;       /* 48px */
```

### Border Radius

```css
--radius-sm: 0.1875rem;  /* 3px - small elements */
--radius-md: 0.25rem;    /* 4px - default */
--radius-lg: 0.375rem;   /* 6px - cards, panels */
--radius-xl: 0.5rem;     /* 8px - modals */
--radius-full: 9999px;   /* pills, avatars */
```

Note: Tighter radii for a more "technical" feel.

---

## Component Specifications

### Status Badge (Fresh/Stale/Building)

```
┌─────────────────────────────────────────────┐
│  Fresh                                      │
│  ┌──────────┐                               │
│  │ ● Fresh  │  bg: transparent              │
│  └──────────┘  text: success                │
│                border: success/40%          │
│                glow: success/10% (subtle)   │
│                                             │
│  Stale                                      │
│  ┌──────────┐                               │
│  │ ● Stale  │  bg: transparent              │
│  └──────────┘  text: warning                │
│                border: warning/40%          │
│                                             │
│  Building                                   │
│  ┌────────────┐                             │
│  │ ◌ Building │  bg: transparent            │
│  └────────────┘  text: info                 │
│                  border: info/40%           │
│                  icon: animated pulse       │
└─────────────────────────────────────────────┘
```

Badges are **outline-style** with subtle glow on hover — feels more "terminal".

### Search Result Row

```
┌─────────────────────────────────────────────────────────────────┐
│  src/prep/core/index.py                             ▓▓▓▓▓░░  │
│  Lines 42-67                                            87%    │
├─────────────────────────────────────────────────────────────────┤
│  142 │ def build_index(project: Project) -> IndexResult:       │
│  143 │     """Build the embedding index for a project."""      │
│  144 │     chunks = chunker.process(project.files)             │
│  145 │     ...                                                 │
└─────────────────────────────────────────────────────────────────┘

- bg: surface
- border: border-subtle
- hover: border-primary/50%, subtle primary-glow
- file path: text, font-mono, text-sm
- score: displayed as mini bar graph + percentage
- code preview: font-mono, syntax highlighted
- line numbers: text-subtle, border-right
```

### Code Chunk Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│  src/prep/server.py                                          │
│  Lines 142-175                              [Raw] [Copy] [Open] │
├─────────────────────────────────────────────────────────────────┤
│  142 │ @app.post("/projects/{project_id}/build")               │
│  143 │ async def build_project(project_id: str):               │
│  144 │     """Trigger project index build."""                  │
│  145 │     project = registry.get(project_id)                  │
│  146 │     if not project:                                     │
│  147 │         raise HTTPException(404, "Project not found")   │
│  ... │                                                         │
└─────────────────────────────────────────────────────────────────┘

- header bg: surface-raised
- code bg: background (darker than header)
- line numbers: text-subtle, bg: surface, border-right: border-subtle
- code: font-mono, syntax highlighted
- action buttons: ghost, grouped
```

---

## Shadows

Shadows are **subtle** in dark mode — use border glow instead:

```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.3);
--shadow-md: 0 4px 8px -1px rgb(0 0 0 / 0.4);
--shadow-lg: 0 10px 20px -3px rgb(0 0 0 / 0.5);
--shadow-glow-primary: 0 0 12px 2px var(--primary-glow);
--shadow-glow-success: 0 0 8px 1px var(--success-muted);
```

---

## Motion

```css
--duration-instant: 50ms;
--duration-fast: 100ms;
--duration-normal: 150ms;
--duration-slow: 250ms;
--ease-default: cubic-bezier(0.2, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
```

Note: Faster transitions for a snappier, more "responsive" feel.

---

## Pros & Cons

### Pros
- **IDE-native feel** — looks like it belongs in Cursor/Windsurf
- **Power user appeal** — feels like a "pro" tool
- **Code readability** — optimized for syntax highlighting
- **Reduced eye strain** — comfortable for extended sessions
- **Differentiated** — stands out from generic light-mode tools

### Cons
- **Dark-mode-first tradeoff** — light mode may feel like an afterthought
- **Marketing challenge** — dark landing pages can feel "heavy"
- **Accessibility concern** — must be very careful with contrast
- **Limited audience** — some users strongly prefer light mode

---

## Marketing Adaptation

For landing pages:
- Use a **gradient hero** that transitions from deep dark to slightly lighter
- Feature **animated code snippets** showing search in action
- Use **glowing accents** on CTAs for visual pop
- Consider a light-mode landing page even if the app is dark-first
