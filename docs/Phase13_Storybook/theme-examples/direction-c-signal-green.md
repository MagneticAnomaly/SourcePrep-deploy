# Direction C: Signal Green

**Personality:** Technical, status-forward, terminal-inspired
**Mood:** Precise, operational, "mission control"
**Best for:** Dev-tool credibility, status clarity, trust signaling

---

## Rationale

Signal Green draws inspiration from terminal interfaces, system monitors, and operational dashboards. The key differentiator is **green as the primary accent** — signaling "systems go", health, and freshness. This direction makes **status the hero** of the UI.

This direction prioritizes:
- **Status clarity** — instant understanding of fresh/stale/building
- **Technical credibility** — feels like infrastructure tooling
- **Trust** — green = healthy, operational, safe
- **Uniqueness** — stands apart from the sea of blue dev tools

---

## Color Palette

### Light Mode

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 150 10% 97% | `#f5f8f6` | Page background |
| `--surface` | 0 0% 100% | `#ffffff` | Cards, panels |
| `--surface-raised` | 150 8% 94% | `#eef2ef` | Elevated surfaces |
| `--border` | 150 8% 85% | `#d4ddd6` | Borders, dividers |
| `--border-subtle` | 150 6% 90% | `#e4ebe6` | Subtle separators |
| `--text` | 160 20% 10% | `#141f18` | Primary text |
| `--text-muted` | 155 10% 40% | `#5c6e62` | Secondary text |
| `--text-subtle` | 155 8% 55% | `#7e8f84` | Tertiary text |

### Dark Mode

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 160 15% 8% | `#111916` | Page background |
| `--surface` | 160 12% 12% | `#1a231f` | Cards, panels |
| `--surface-raised` | 160 10% 16% | `#252f2a` | Elevated surfaces |
| `--border` | 160 8% 22% | `#343f39` | Borders, dividers |
| `--border-subtle` | 160 8% 18% | `#2a352f` | Subtle separators |
| `--text` | 150 10% 92% | `#e8eeea` | Primary text |
| `--text-muted` | 150 6% 60% | `#8fa396` | Secondary text |
| `--text-subtle` | 150 5% 42% | `#66756c` | Tertiary text |

### Accent Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--primary` | 152 70% 45% | `#22b05e` | Primary actions, "go" states |
| `--primary-hover` | 152 70% 40% | `#1d9950` | Hover state |
| `--primary-muted` | 152 70% 45% / 12% | — | Backgrounds |
| `--primary-glow` | 152 70% 45% / 20% | — | Focus rings |

### Semantic Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--success` | 152 70% 45% | `#22b05e` | Fresh (same as primary!) |
| `--success-muted` | 152 70% 45% / 12% | — | Success backgrounds |
| `--warning` | 38 95% 50% | `#f5a623` | Stale, attention states |
| `--warning-muted` | 38 95% 50% / 12% | — | Warning backgrounds |
| `--error` | 0 70% 55% | `#d64545` | Error, destructive |
| `--error-muted` | 0 70% 55% / 12% | — | Error backgrounds |
| `--info` | 200 80% 50% | `#1a9fd9` | Info, building states |
| `--info-muted` | 200 80% 50% / 12% | — | Info backgrounds |
| `--neutral` | 155 8% 50% | `#768a7d` | Disabled, inactive |

### Status-Specific Colors (The Hero)

| State | Color | Hex | Icon |
|-------|-------|-----|------|
| Fresh | `--success` | `#22b05e` | ● filled circle |
| Stale | `--warning` | `#f5a623` | ◐ half circle |
| Building | `--info` | `#1a9fd9` | ◌ animated ring |
| Error | `--error` | `#d64545` | ✕ x mark |
| Pending | `--neutral` | `#768a7d` | ○ empty circle |

---

## Typography

### Font Stack

```css
--font-sans: 'Roboto', ui-sans-serif, system-ui, -apple-system, sans-serif;
--font-mono: 'Roboto Mono', ui-monospace, 'Cascadia Code', monospace;
```

**Google Fonts:**
- [Roboto](https://fonts.google.com/specimen/Roboto) — Clean, technical, widely recognized
- [Roboto Mono](https://fonts.google.com/specimen/Roboto+Mono) — Matching monospace

**Alternative:**
- [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) + [Space Mono](https://fonts.google.com/specimen/Space+Mono) — More unique, "space mission" vibe

### Type Scale

| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `--text-xs` | 0.6875rem (11px) | 500 | 1.5 | Labels, status text |
| `--text-sm` | 0.8125rem (13px) | 400 | 1.5 | UI text, secondary |
| `--text-base` | 0.9375rem (15px) | 400 | 1.5 | Body text |
| `--text-lg` | 1.0625rem (17px) | 500 | 1.45 | Emphasized text |
| `--text-xl` | 1.25rem (20px) | 600 | 1.35 | Section headings |
| `--text-2xl` | 1.5rem (24px) | 700 | 1.3 | Page headings |
| `--text-3xl` | 2rem (32px) | 700 | 1.2 | Hero text |

Note: Slightly bolder weights for "operational" clarity.

---

## Spacing & Layout

### Spacing Scale (4px base)

```css
--space-0: 0;
--space-0.5: 0.125rem;  /* 2px */
--space-1: 0.25rem;     /* 4px */
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
--radius-sm: 0.125rem;   /* 2px - very tight */
--radius-md: 0.25rem;    /* 4px - default */
--radius-lg: 0.375rem;   /* 6px - cards */
--radius-xl: 0.5rem;     /* 8px - modals */
--radius-full: 9999px;   /* pills, status dots */
```

Note: Tighter radii for a more "technical/precise" aesthetic.

---

## Component Specifications

### Status Badge (Fresh/Stale/Building) — THE HERO

```
┌─────────────────────────────────────────────────────────────────┐
│  Status indicators are PROMINENT in this direction              │
│                                                                 │
│  Fresh (large)                                                  │
│  ┌───────────────────────┐                                      │
│  │  ●  Index Fresh       │  bg: success-muted                   │
│  │     Last built 2m ago │  border: success                     │
│  └───────────────────────┘  text: success (strong)              │
│                             subtext: text-muted                 │
│                                                                 │
│  Stale (large)                                                  │
│  ┌───────────────────────┐                                      │
│  │  ◐  Index Stale       │  bg: warning-muted                   │
│  │     3 files changed   │  border: warning                     │
│  └───────────────────────┘  text: warning (strong)              │
│                             subtext: text-muted                 │
│                                                                 │
│  Building (large)                                               │
│  ┌───────────────────────┐                                      │
│  │  ◌  Building...       │  bg: info-muted                      │
│  │     42% complete      │  border: info                        │
│  └───────────────────────┘  text: info (strong)                 │
│                             progress bar below                  │
│                                                                 │
│  Compact badges                                                 │
│  ┌────────┐ ┌────────┐ ┌──────────┐                            │
│  │● Fresh │ │◐ Stale │ │◌ Building│                            │
│  └────────┘ └────────┘ └──────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### Search Result Row

```
┌─────────────────────────────────────────────────────────────────┐
│ ● src/prep/core/index.py                    Score: 87%       │
│   Lines 42-67                                                  │
├─────────────────────────────────────────────────────────────────┤
│  def build_index(project: Project) -> IndexResult:             │
│      """Build the embedding index for a project."""            │
│      chunks = chunker.process(project.files)                   │
└─────────────────────────────────────────────────────────────────┘

- status dot: shows if this file is in a fresh/stale index
- bg: surface
- border-left: 3px solid primary (accent strip)
- hover: bg surface-raised, border-left brightens
- score: monospace, right-aligned
```

### Code Chunk Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│ ● src/prep/server.py:142-175                         [Copy]  │
├─────────────────────────────────────────────────────────────────┤
│ 142 │ @app.post("/projects/{project_id}/build")                │
│ 143 │ async def build_project(project_id: str):                │
│ 144 │     """Trigger project index build."""                   │
│ 145 │     project = registry.get(project_id)                   │
│ 146 │     if not project:                                      │
│ 147 │         raise HTTPException(404, "Project not found")    │
└─────────────────────────────────────────────────────────────────┘

- header: surface-raised, includes status dot
- border-left: 3px solid primary
- line numbers: monospace, right-aligned, text-subtle
- code: monospace, slightly smaller
```

### Project Status Card (Signature Component)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ●  LinuxBrain                                                  │
│     LinuxBrain                                                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Index        ●  Fresh     Last build: 2 min ago        │   │
│  │  Trace        ○  Disabled                               │   │
│  │  Auto-rebuild ●  Enabled   Watching 1,234 files         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  1,234 chunks  •  768 dim  •  nomic-embed-text                 │
│                                                                 │
│                              [Rebuild]  [Settings]  [Search]   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Shadows

```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 2px 4px -1px rgb(0 0 0 / 0.08);
--shadow-lg: 0 4px 8px -2px rgb(0 0 0 / 0.1);
--shadow-status: 0 0 8px 0 var(--primary-glow);
```

Note: Minimal shadows — let color do the work.

---

## Motion

```css
--duration-fast: 100ms;
--duration-normal: 150ms;
--duration-slow: 200ms;
--ease-default: cubic-bezier(0.25, 0.1, 0.25, 1);
--ease-status: cubic-bezier(0.4, 0, 0.2, 1);
```

Status transitions should be **smooth but not slow** — the user needs to see state changes quickly.

---

## Pros & Cons

### Pros
- **Maximum status clarity** — instant understanding of system health
- **Unique identity** — stands out from blue-dominant dev tools
- **Trust signaling** — green = safe, operational, "systems go"
- **Technical credibility** — feels like infrastructure tooling
- **Accessibility win** — green/amber/red is a well-understood pattern

### Cons
- **Green fatigue** — could feel monotonous if overused
- **Color blindness** — must supplement with icons/shapes (●/◐/◌)
- **Marketing challenge** — green can feel "enterprise-y" not "cool"
- **Less personality** — functional over expressive

---

## Marketing Adaptation

For landing pages:
- Use **status as the hero** — show the fresh/stale/building states prominently
- **Gradient hero**: dark to green-tinted dark
- Emphasize **"always know your index is fresh"** messaging
- Use the status card component as a visual centerpiece
