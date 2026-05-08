# Storybook Visual Design Plan

**Status**: Draft (2026-05-08)
**Decision owner**: Eric
**Companions**: `00_curation_plan.md`, `01_taxonomy_research_and_proposal.md`

---

## 1. Decision

Two visual surfaces, two postures:

| Surface | Posture | Theme |
|---|---|---|
| **Story content** (the rendered component inside the iframe) | Dark mode | `prepTheme='a'` — **Slate Developer**, dark variant |
| **Storybook chrome** (sidebar, toolbar, manager UI) | Light mode | Custom manager theme derived from `prepTheme='a'` light variant |

The result: visitors land on a clean, light Slate-Developer-style chrome — sidebar, toolbar, addon panels. The story preview area renders the component in dark Slate Developer. Two postures of the same visual language sit side-by-side. The contrast reinforces that the components are made for IDE-like dark UIs while the design-system documentation itself reads like a polished developer doc site.

This **supersedes Phase 13's earlier decision** (`docs/Phase13_Storybook/DECISIONS.md`) of dark mode + theme 'h' (Retro-Futurism) as the default. Retro-Futurism remains available via the toolbar selector — it's just no longer the boot default.

---

## 2. Why Slate Developer for both

Theme 'a' was already described in `Foundations/Visual Directions` as:

> *"A clean, neutral theme inspired by modern developer tools (Vercel, Linear). Low saturation, high legibility."*

It's the most professionally legible of the 14 themes. For a public design-system showcase aimed at *other design engineers*, low-noise + high-legibility wins over distinctive-and-dramatic. Retro-Futurism is a stronger personality, but it asks the visitor to accept a strong stylistic frame before evaluating the components themselves.

For the chrome specifically, Storybook's manager UI was designed against light backgrounds first (the default Storybook theme is light). Mapping Slate Developer to light-mode chrome respects that contract while still putting the SourcePrep visual language in front of the user from the first paint.

---

## 3. Token mapping — Slate Developer → Storybook ThemeVars

Source: `packages/ui/src/styles/themes/direction-a.css`. Both light and dark variants are defined there in HSL.

### 3.1 Light-mode tokens (used for the manager chrome)

| CSS token | HSL | Hex equivalent | Role |
|---|---|---|---|
| `--background` | `210 20% 98%` | `#F8FAFC` | App background (sidebar, top bar) |
| `--surface` | `0 0% 100%` | `#FFFFFF` | Story preview area, addon panel |
| `--surface-raised` | `210 15% 96%` | `#F1F4F8` | Toolbar, hovered rows |
| `--border` | `214 20% 88%` | `#D9DFE6` | App + content borders |
| `--border-subtle` | `214 15% 93%` | `#E8ECF1` | Subtle dividers |
| `--text` | `222 47% 11%` | `#0F172A` | Primary text |
| `--text-muted` | `215 16% 45%` | `#64748B` | Bar text, muted labels |
| `--primary` | `221 83% 53%` | `#2563EB` | Selected sidebar row, links |

### 3.2 Storybook ThemeVars assignments

Storybook 7's manager API takes a `ThemeVars` object via `addons.setConfig({ theme })`. Mapping:

```ts
import { create } from '@storybook/theming';

export const slateDeveloperLight = create({
  base: 'light',

  // Brand
  brandTitle: 'SourcePrep · Design System',
  brandUrl: 'https://sourceprep.io',
  brandTarget: '_blank',

  // App canvas
  appBg: '#F8FAFC',           // --background
  appContentBg: '#FFFFFF',    // --surface
  appBorderColor: '#D9DFE6',  // --border
  appBorderRadius: 6,

  // Top toolbar / footer bar
  barBg: '#F1F4F8',           // --surface-raised
  barTextColor: '#64748B',    // --text-muted
  barSelectedColor: '#2563EB',// --primary
  barHoverColor: '#0F172A',   // --text

  // Text
  textColor: '#0F172A',       // --text
  textInverseColor: '#FFFFFF',
  textMutedColor: '#64748B',  // --text-muted

  // Form inputs (search box, controls)
  inputBg: '#FFFFFF',
  inputBorder: '#D9DFE6',
  inputTextColor: '#0F172A',
  inputBorderRadius: 4,

  // Brand color
  colorPrimary: '#2563EB',    // --primary
  colorSecondary: '#2563EB',

  // Typography
  fontBase: '"Inter", ui-sans-serif, system-ui, sans-serif',
  fontCode: '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace',
});
```

### 3.3 Story-content defaults (the iframe)

The iframe defaults are set via `globalTypes` in `.storybook/preview.tsx`. Change:

```ts
// preview.tsx — change defaults
globalTypes: {
  theme: { defaultValue: 'dark', /* unchanged */ },
  prepTheme: {
    defaultValue: 'a',  // was 'h' (Retro-Futurism); now Slate Developer
    /* toolbar items unchanged — visitors can still flip to any theme */
  },
}
```

Both toolbars stay visible so visitors can switch themes from the manager UI; we're only changing the boot-time default.

---

## 4. Implementation steps

1. **Create `packages/ui/.storybook/manager.ts`**: declares the Slate Developer light theme via `create({ base: 'light', … })` and registers it with `addons.setConfig({ theme })`.
2. **Edit `packages/ui/.storybook/preview.tsx`**: change `globalTypes.prepTheme.defaultValue` from `'h'` to `'a'`. (`theme.defaultValue` stays `'dark'`.)
3. **Build verification**: `STORYBOOK_PUBLIC=true npm run build-storybook:public`. Visit `localhost:6007` — confirm:
   - Sidebar/top bar render with light Slate Developer palette
   - Story preview area renders dark by default, with the dark Slate Developer token set
   - Toolbar selectors still function (can flip to other themes)
4. **Update `docs/Phase13_Storybook/DECISIONS.md`**: add a note that the public Storybook now defaults to Slate Developer; Retro-Futurism remains an available theme but is no longer the default. Tag the note with this Phase 131 reference.
5. **No change to `StoryEmbed.tsx`** — it already hardcodes `theme:dark;prepTheme:m;docsMode:true` for embedded use. Whether to switch the embed default to `'a'` is a separate decision (the current `'m'` Retro Aurora was chosen for the docs-site embeds specifically; updating it would shift the docs site's visual posture too).

---

## 5. What this changes vs. doesn't

**Changes:**
- Default boot theme of the public storybook (sidebar + first story load).
- `npm run storybook` (private) inherits the same default unless we further differentiate.

**Does not change:**
- Component implementations.
- The list of available themes (still 14).
- The iframe embed posture used by `docs.sourceprep.io` — those still render in Retro Aurora (`m`).
- The `docsMode` global behavior.

---

## 6. Open questions

1. **Brand image**: should `brandImage` show a SourcePrep wordmark/logo? If yes, drop a hashed asset under `.storybook/static/` and point `brandImage` at it. Skipped for v1.
2. **Should the *private* (`STORYBOOK_PUBLIC` unset) build also default to Slate Developer**, or keep developer-preferred Retro-Futurism for in-house work? Recommendation: same default for consistency; toolbar still allows flipping.
3. **Font hosting**: Storybook's manager renders chrome in its own iframe sandbox; web-fonts referenced via `fontBase` need to be loaded somewhere reachable by the manager. If we want Inter, we either ship it via `manager-head.html` or accept the system fallback. Skipped for v1 — system stack is fine.
