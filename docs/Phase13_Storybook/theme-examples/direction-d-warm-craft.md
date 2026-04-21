# Direction D: Warm Craft

**Personality:** Approachable, human, indie-dev feel
**Mood:** Friendly, crafted, "made by developers for developers"
**Best for:** Marketing appeal, onboarding, community building

---

## Rationale

Warm Craft takes a different approach: instead of feeling like infrastructure tooling, it feels like a **thoughtfully crafted product** made by people who care. It uses warm neutrals, subtle texture, and a more expressive accent color to create a sense of **quality and care**.

This direction prioritizes:
- **Approachability** — welcoming to newcomers
- **Craft** — feels hand-made, not corporate
- **Marketing punch** — stands out in screenshots and demos
- **Human touch** — the opposite of cold/sterile enterprise software

---

## Color Palette

### Light Mode (Default)

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 40 20% 97% | `#faf9f7` | Page background (warm white) |
| `--surface` | 0 0% 100% | `#ffffff` | Cards, panels |
| `--surface-raised` | 40 15% 94% | `#f3f1ed` | Elevated surfaces |
| `--surface-warm` | 35 25% 92% | `#efe9df` | Accent backgrounds |
| `--border` | 35 12% 82% | `#d6d0c4` | Borders, dividers |
| `--border-subtle` | 35 10% 88% | `#e4e0d8` | Subtle separators |
| `--text` | 30 15% 15% | `#2a2520` | Primary text (warm black) |
| `--text-muted` | 30 8% 40% | `#6b6460` | Secondary text |
| `--text-subtle` | 30 6% 55% | `#918a85` | Tertiary text |

### Dark Mode

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--background` | 30 12% 10% | `#1c1917` | Page background |
| `--surface` | 30 10% 14% | `#262220` | Cards, panels |
| `--surface-raised` | 30 8% 18% | `#302c29` | Elevated surfaces |
| `--surface-warm` | 30 12% 16% | `#2d2824` | Accent backgrounds |
| `--border` | 30 8% 24% | `#403b36` | Borders, dividers |
| `--border-subtle` | 30 6% 20% | `#35312e` | Subtle separators |
| `--text` | 40 15% 92% | `#f5f3f0` | Primary text |
| `--text-muted` | 35 8% 60% | `#9e9690` | Secondary text |
| `--text-subtle` | 35 6% 45% | `#78716c` | Tertiary text |

### Accent Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--primary` | 24 95% 53% | `#f97316` | Primary actions (warm orange) |
| `--primary-hover` | 24 95% 46% | `#ea580c` | Hover state |
| `--primary-muted` | 24 95% 53% / 12% | — | Backgrounds |
| `--primary-light` | 33 100% 60% | `#fbbf24` | Highlights |

**Alternative primary colors to consider:**
- Coral: `hsl(12 90% 58%)` — `#f06449` — warmer, more unique
- Amber: `hsl(38 92% 50%)` — `#f59e0b` — more golden
- Terracotta: `hsl(18 80% 50%)` — `#d95a2b` — earthier

### Semantic Colors

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `--success` | 142 65% 40% | `#22a55b` | Fresh, success states |
| `--success-muted` | 142 65% 40% / 12% | — | Success backgrounds |
| `--warning` | 38 92% 50% | `#f59e0b` | Stale, attention states |
| `--warning-muted` | 38 92% 50% / 12% | — | Warning backgrounds |
| `--error` | 0 72% 51% | `#dc2626` | Error, destructive |
| `--error-muted` | 0 72% 51% / 12% | — | Error backgrounds |
| `--info` | 199 85% 45% | `#0891b2` | Info, building states |
| `--info-muted` | 199 85% 45% / 12% | — | Info backgrounds |

---

## Typography

### Font Stack

```css
--font-sans: 'DM Sans', ui-sans-serif, system-ui, -apple-system, sans-serif;
--font-mono: 'DM Mono', ui-monospace, 'Fira Code', monospace;
--font-display: 'Fraunces', Georgia, serif;  /* Optional: for marketing headlines */
```

**Google Fonts:**
- [DM Sans](https://fonts.google.com/specimen/DM+Sans) — Friendly, geometric, excellent readability
- [DM Mono](https://fonts.google.com/specimen/DM+Mono) — Matching monospace, slightly quirky
- [Fraunces](https://fonts.google.com/specimen/Fraunces) (optional) — Variable serif for expressive headlines

**Why DM Sans:**
- More personality than Inter/Roboto
- Geometric but warm
- Excellent at small sizes
- Variable font support

### Type Scale

| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `--text-xs` | 0.75rem (12px) | 400 | 1.6 | Labels, captions |
| `--text-sm` | 0.875rem (14px) | 400 | 1.55 | UI text, secondary |
| `--text-base` | 1rem (16px) | 400 | 1.6 | Body text |
| `--text-lg` | 1.125rem (18px) | 500 | 1.5 | Emphasized text |
| `--text-xl` | 1.25rem (20px) | 600 | 1.4 | Section headings |
| `--text-2xl` | 1.5rem (24px) | 600 | 1.35 | Page headings |
| `--text-3xl` | 1.875rem (30px) | 700 | 1.25 | Hero text |
| `--text-4xl` | 2.25rem (36px) | 700 | 1.2 | Marketing headlines |

Note: Slightly looser line heights for a more "breathing" feel.

---

## Spacing & Layout

### Spacing Scale (4px base)

```css
--space-0: 0;
--space-1: 0.25rem;     /* 4px */
--space-2: 0.5rem;      /* 8px */
--space-3: 0.75rem;     /* 12px */
--space-4: 1rem;        /* 16px */
--space-5: 1.25rem;     /* 20px */
--space-6: 1.5rem;      /* 24px */
--space-8: 2rem;        /* 32px */
--space-10: 2.5rem;     /* 40px */
--space-12: 3rem;       /* 48px */
--space-16: 4rem;       /* 64px */
--space-20: 5rem;       /* 80px */
```

### Border Radius

```css
--radius-sm: 0.375rem;   /* 6px - more rounded */
--radius-md: 0.5rem;     /* 8px - default */
--radius-lg: 0.75rem;    /* 12px - cards */
--radius-xl: 1rem;       /* 16px - modals */
--radius-2xl: 1.5rem;    /* 24px - large elements */
--radius-full: 9999px;   /* pills, avatars */
```

Note: Larger radii for a softer, more approachable feel.

---

## Component Specifications

### Status Badge (Fresh/Stale/Building)

```
┌─────────────────────────────────────────────────────────────────┐
│  Status badges are SOFTER and more VISUAL                       │
│                                                                 │
│  Fresh                                                          │
│  ┌─────────────┐                                                │
│  │  ✓  Fresh   │  bg: success-muted                             │
│  └─────────────┘  text: success                                 │
│                   border-radius: radius-full (pill)             │
│                   icon: checkmark (not dot)                     │
│                                                                 │
│  Stale                                                          │
│  ┌──────────────────┐                                           │
│  │  ↻  Needs update │  bg: warning-muted                        │
│  └──────────────────┘  text: warning                            │
│                        icon: refresh arrow                      │
│                                                                 │
│  Building                                                       │
│  ┌─────────────────┐                                            │
│  │  ◌  Building... │  bg: info-muted                            │
│  └─────────────────┘  text: info                                │
│                       icon: animated spinner                    │
└─────────────────────────────────────────────────────────────────┘
```

Note: Uses **descriptive labels** ("Needs update" vs "Stale") for approachability.

### Search Result Row

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  📄  src/prep/core/index.py                                   │
│      Lines 42-67  •  87% match                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  def build_index(project: Project) -> IndexResult:      │   │
│  │      """Build the embedding index for a project."""     │   │
│  │      chunks = chunker.process(project.files)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

- bg: surface
- border: border (visible, warm)
- border-radius: radius-lg
- shadow: shadow-sm (subtle lift)
- hover: shadow-md, border-primary/30%
- file icon: emoji or Lucide icon
- code block: bg surface-raised, radius-md
```

### Code Chunk Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  📄  src/prep/server.py                                       │
│      Lines 142-175                                              │
│                                                       [Copy ✓]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   142   @app.post("/projects/{project_id}/build")              │
│   143   async def build_project(project_id: str):              │
│   144       """Trigger project index build."""                 │
│   145       project = registry.get(project_id)                 │
│   146       if not project:                                    │
│   147           raise HTTPException(404, "Project not found")  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

- border-radius: radius-lg (soft corners)
- header: warm background, friendly file icon
- copy button: shows "Copied!" feedback with checkmark
- line numbers: right-aligned, text-subtle, no separator
- generous padding throughout
```

### Welcome/Empty State

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                         🔍                                      │
│                                                                 │
│              No projects yet                                    │
│                                                                 │
│      Add your first project to start searching                  │
│                                                                 │
│              ┌─────────────────────┐                            │
│              │   + Add Project     │   (primary button)         │
│              └─────────────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

- centered, friendly illustration or emoji
- warm, encouraging copy
- prominent CTA
```

---

## Shadows

```css
--shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.03);
--shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.06);
--shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.08), 0 8px 10px -6px rgb(0 0 0 / 0.06);
```

Note: Softer shadows (lower opacity) for a gentler feel.

---

## Motion

```css
--duration-fast: 150ms;
--duration-normal: 250ms;
--duration-slow: 350ms;
--duration-slower: 500ms;
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-smooth: cubic-bezier(0.25, 0.1, 0.25, 1);
```

Note: Slightly slower, more "considered" animations.

---

## Texture & Visual Interest (Optional)

To add "craft" feel:
- **Subtle noise texture** on backgrounds (very low opacity)
- **Soft gradients** on hero sections
- **Hand-drawn style icons** for empty states
- **Micro-interactions** on buttons (slight bounce)

---

## Pros & Cons

### Pros
- **Maximum approachability** — welcoming to all skill levels
- **Marketing strength** — screenshots look inviting
- **Memorable** — warm palette stands out
- **Onboarding-friendly** — less intimidating for new users
- **Community appeal** — feels "indie" and human

### Cons
- **Less "serious" feel** — enterprise buyers might want more gravitas
- **Warm tones can clash** — with code syntax highlighting
- **Harder to execute** — requires more design polish to avoid "toy" feel
- **Dark mode challenge** — warm colors are harder to balance in dark

---

## Marketing Adaptation

For landing pages, this direction **IS the marketing direction**:
- Generous whitespace
- Friendly illustrations
- Warm gradients
- Testimonials with human photos
- "Made with care" messaging

---

## When to Choose Warm Craft

Choose this direction if:
- You want to **maximize approachability**
- You're targeting **individual developers** first
- You want **strong marketing visuals**
- You value **personality over corporate trust**
- You want to **stand out** from sterile dev tools
