# Direction A: Slate Developer

**Personality:** Clean, professional, neutral
**Mood:** Trustworthy, mature, enterprise-ready
**Best for:** Wide appeal, works for both indie devs and enterprise teams

---

## Rationale

Slate Developer is the "safe" choice that maximizes trust and minimizes friction. It uses neutral grays with a subtle cool tint, paired with a restrained accent color. The result feels like a serious developer tool without being cold or sterile.

This direction prioritizes:
- **Professionalism** over personality
- **Clarity** over visual interest
- **Broad appeal** over niche aesthetic

---

## Color Palette

### Light Mode (Default)

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 210 20% 98% | `#f8fafc` | Page background |
| `--surface` | 210 20% 100% | `#ffffff` | Cards, panels |
| `--surface-raised` | 210 15% 96% | `#f1f5f9` | Elevated surfaces |
| `--border` | 214 20% 88% | `#e2e8f0` | Borders, dividers |
| `--border-subtle` | 214 15% 93% | `#eef2f6` | Subtle separators |
| `--text` | 222 47% 11% | `#0f172a` | Primary text |
| `--text-muted` | 215 16% 47% | `#64748b` | Secondary text |
| `--text-subtle` | 215 14% 63% | `#94a3b8` | Tertiary text |

### Dark Mode

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 222 47% 11% | `#0f172a` | Page background |
| `--surface` | 217 33% 17% | `#1e293b` | Cards, panels |
| `--surface-raised` | 215 28% 22% | `#334155` | Elevated surfaces |
| `--border` | 217 19% 27% | `#3b4861` | Borders, dividers |
| `--border-subtle` | 217 19% 22% | `#2d3a4d` | Subtle separators |
| `--text` | 210 40% 98% | `#f8fafc` | Primary text |
| `--text-muted` | 215 20% 65% | `#94a3b8` | Secondary text |
| `--text-subtle` | 215 16% 47% | `#64748b` | Tertiary text |

### Accent Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--primary` | 221 83% 53% | `#3b82f6` | Primary actions, links |
| `--primary-hover` | 221 83% 46% | `#2563eb` | Hover state |
| `--primary-muted` | 221 83% 53% / 15% | `#3b82f6/15` | Backgrounds |

### Semantic Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--success` | 142 71% 45% | `#22c55e` | Fresh, success states |
| `--success-muted` | 142 71% 45% / 15% | — | Success backgrounds |
| `--warning` | 38 92% 50% | `#f59e0b` | Stale, attention states |
| `--warning-muted` | 38 92% 50% / 15% | — | Warning backgrounds |
| `--error` | 0 84% 60% | `#ef4444` | Error, destructive |
| `--error-muted` | 0 84% 60% / 15% | — | Error backgrounds |
| `--info` | 199 89% 48% | `#0ea5e9` | Info, building states |
| `--info-muted` | 199 89% 48% / 15% | — | Info backgrounds |

---

## Typography

### Font Stack

```css
--font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
```

**Google Fonts:**
- [Inter](https://fonts.google.com/specimen/Inter) — Clean, highly legible sans-serif
- [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) — Developer-focused monospace

### Type Scale

| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `--text-xs` | 0.75rem (12px) | 400 | 1.5 | Labels, captions |
| `--text-sm` | 0.875rem (14px) | 400 | 1.5 | UI text, secondary |
| `--text-base` | 1rem (16px) | 400 | 1.5 | Body text |
| `--text-lg` | 1.125rem (18px) | 500 | 1.4 | Emphasized text |
| `--text-xl` | 1.25rem (20px) | 600 | 1.3 | Section headings |
| `--text-2xl` | 1.5rem (24px) | 600 | 1.25 | Page headings |
| `--text-3xl` | 1.875rem (30px) | 700 | 1.2 | Hero text |

---

## Spacing & Layout

### Spacing Scale (4px base)

```css
--space-0: 0;
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.25rem;   /* 20px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
--space-10: 2.5rem;   /* 40px */
--space-12: 3rem;     /* 48px */
--space-16: 4rem;     /* 64px */
```

### Border Radius

```css
--radius-sm: 0.25rem;   /* 4px - small elements */
--radius-md: 0.375rem;  /* 6px - default */
--radius-lg: 0.5rem;    /* 8px - cards, panels */
--radius-xl: 0.75rem;   /* 12px - modals */
--radius-full: 9999px;  /* pills, avatars */
```

---

## Component Specifications

### Status Badge (Fresh/Stale/Building)

```
┌─────────────────────────────────────────────┐
│  Fresh                                      │
│  ┌──────────┐                               │
│  │ ● Fresh  │  bg: success-muted            │
│  └──────────┘  text: success                │
│                border: success/30%          │
│                                             │
│  Stale                                      │
│  ┌──────────┐                               │
│  │ ● Stale  │  bg: warning-muted            │
│  └──────────┘  text: warning                │
│                border: warning/30%          │
│                                             │
│  Building                                   │
│  ┌────────────┐                             │
│  │ ◌ Building │  bg: info-muted             │
│  └────────────┘  text: info                 │
│                  border: info/30%           │
│                  icon: animated spinner     │
└─────────────────────────────────────────────┘
```

### Search Result Row

```
┌─────────────────────────────────────────────────────────────────┐
│  src/prep/core/index.py                          0.87 ●      │
│  ──────────────────────────────────────────────────────────────│
│  def build_index(project: Project) -> IndexResult:             │
│      """Build the embedding index for a project."""            │
│      chunks = chunker.process(project.files)                   │
│      ...                                                       │
│                                                    Lines 42-67 │
└─────────────────────────────────────────────────────────────────┘

- bg: surface
- border: border-subtle
- hover: border-primary/30%, surface-raised
- file path: text-muted, font-mono, text-sm
- score: primary, font-mono
- code preview: font-mono, text-sm
- line numbers: text-subtle
```

### Code Chunk Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│  📄 src/prep/server.py:142-175                    [Copy]     │
├─────────────────────────────────────────────────────────────────┤
│  142 │ @app.post("/projects/{project_id}/build")               │
│  143 │ async def build_project(project_id: str):               │
│  144 │     """Trigger project index build."""                  │
│  145 │     project = registry.get(project_id)                  │
│  146 │     if not project:                                     │
│  147 │         raise HTTPException(404, "Project not found")   │
│  ...                                                           │
└─────────────────────────────────────────────────────────────────┘

- header bg: surface-raised
- header border-bottom: border
- line numbers: text-subtle, bg: surface-raised
- code: font-mono, text-sm
- copy button: ghost variant, icon-only
```

---

## Shadows

```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
--shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
```

---

## Motion

```css
--duration-fast: 150ms;
--duration-normal: 200ms;
--duration-slow: 300ms;
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
```

---

## Pros & Cons

### Pros
- **Maximum trust signaling** — feels like serious software
- **Enterprise-friendly** — no bold colors that feel "startup-y"
- **High accessibility** — neutral palette is easy to tune for contrast
- **Works in both light and dark** — no personality loss in either mode
- **Tremor-compatible** — aligns with Tremor's default aesthetic

### Cons
- **Less memorable** — doesn't stand out visually
- **Could feel generic** — needs strong typography and spacing to feel crafted
- **May lack marketing punch** — needs accent use on landing pages

---

## Marketing Adaptation

For landing pages and docs, this direction can be "warmed up" with:
- Larger type scale for hero sections
- Gradient backgrounds (subtle blue → slate)
- Accent color used more liberally in CTAs
- Illustration style: clean line art with blue accent
