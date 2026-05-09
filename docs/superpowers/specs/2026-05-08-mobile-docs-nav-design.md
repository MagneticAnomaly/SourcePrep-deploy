# Mobile Docs Navigation Design

**Date:** 2026-05-08
**Scope:** `packages/ui` + `websites/apps/docs` (no config-side changes required)
**Problem:** On the public-facing docs site (`docs.sourceprep.io`), the left sidebar is hidden on screens below 1024px with no mobile fallback. Users on phones and tablets cannot navigate the docs tree from the docs site itself.

## Diagnosis

Two existing layout decisions combine into a complete mobile nav blackout on docs pages:

- **`packages/ui/src/components/docs/DocsLayout.tsx:33`** — sidebar is `hidden lg:block`, removing it entirely below the `lg` breakpoint (1024px) with no replacement.
- **`packages/ui/src/components/docs/DocsLayout.tsx:46`** — right-rail TOC is `hidden xl:block`, removing it below 1280px.
- **`packages/ui/src/components/site/SiteHeader.tsx`** has its own mobile hamburger drawer, but it only renders the four site-level links (Home / Pricing / Download / FAQ) configured by `ClientLayout.tsx`. It does **not** include the docs sidebar tree (8 sections, ~30 links).

Net effect: on mobile, the docs site has no path from any docs page to any other docs page except by typing URLs.

## Goals

1. Restore full docs sidebar navigation on mobile and tablet without a desktop-class viewport.
2. Keep marketing/site links (Home / Pricing / Download / FAQ) reachable but secondary, since the primary intent on a docs page is reaching another docs page.
3. Match the mobile-nav patterns users expect from major dev-docs sites (Stripe, Vercel, Next.js, Tailwind, shadcn, Mintlify) — off-canvas left drawer with full sidebar tree.
4. Re-use existing components (`DocsSidebarNav`, the existing hamburger button, body-scroll-lock logic) rather than introducing parallel implementations.
5. Keep `SiteHeader` reusable by non-docs apps (marketing, payments, support) — no breaking changes.

## Non-Goals

- Redesigning the desktop sidebar.
- Touching the marketing site, pricing site, payments, or support apps.
- Adding new content to the docs sidebar — `websites/apps/docs/src/config/docs.ts` is unchanged.
- A search/command palette UX upgrade. The existing search input is reused as-is in the drawer header.

## Design

### 1. Component boundaries

Three files change in `@prep/ui`, plus `currentPath` is plumbed in via `websites/apps/docs/src/app/ClientLayout.tsx`.

**`packages/ui/src/components/site/SiteHeader.tsx`** gains two optional props and an `Esc` handler:

```ts
export interface SiteHeaderProps {
  // ... existing props ...
  /**
   * Optional content to render in place of the default mobile menu when the
   * hamburger is open. Replaces both the chrome and the content — the
   * content is responsible for its own positioning, scrim, and animation.
   * SiteHeader continues to own the toggle button, open/close state,
   * body-scroll-lock, and Esc-to-close handling.
   */
  mobileMenuContent?: React.ReactNode;

  /**
   * Breakpoint at which the mobile hamburger gives way to the inline
   * desktop nav. Defaults to 'md' (768px) for backwards compat. Docs pages
   * pass 'lg' (1024px) so the hamburger remains visible at tablet widths
   * where the desktop sidebar is still hidden.
   */
  mobileBreakpoint?: 'md' | 'lg';
}
```

Concretely: when `mobileMenuContent` is provided, the existing mobile-menu render branch (`SiteHeader.tsx:121-154`) is bypassed entirely and `{mobileMenuContent}` is rendered as-is — `MobileDocsDrawer` brings its own off-canvas chrome. The hamburger button visibility class flips from `md:hidden` to `lg:hidden` when `mobileBreakpoint='lg'`, and the inline desktop nav class flips from `md:flex` to `lg:flex`. A new `useEffect` adds a `keydown` listener for `Escape` that closes the menu.

**`packages/ui/src/components/docs/DocsLayout.tsx`** gains a `currentPath?: string` prop, computes active flags on each `DocNode`, and passes the result to both desktop and mobile sidebars:

```tsx
const flagged = useMemo(() => withActive(sidebarItems, currentPath), [sidebarItems, currentPath]);

<SiteHeader
  {...headerProps}
  mobileBreakpoint="lg"
  mobileMenuContent={
    <MobileDocsDrawer
      items={flagged}
      siteLinks={headerProps.links}
      onSearch={headerProps.onSearch}
      onClose={...}  // wired through SiteHeader via context or a callback prop
    />
  }
/>
```

Where `withActive` is a small pure helper in the same file that returns a new tree with `active: item.href === currentPath` set on each leaf. This is a **scope-adjacent fix**: the docs site has never highlighted the current page in the sidebar (latent bug — `docs.ts` never set `active`, and `DocsSidebarNav` is purely prop-driven with no pathname access). Adding `currentPath` plumbing fixes desktop and mobile in one pass at trivial cost.

**`packages/ui/src/components/docs/MobileDocsDrawer.tsx`** is new. It renders its own off-canvas chrome (fixed left, full-height, slide-in transform, scrim sibling) and reuses `DocsSidebarNav` for the tree so desktop and mobile share one source of truth for rendering logic.

**`websites/apps/docs/src/app/ClientLayout.tsx`** passes `currentPath={usePathname() ?? undefined}` into `DocsLayout`. (`ClientLayout` is already a `"use client"` component, so `usePathname` is already available.)

**Why this shape:** keeps `@prep/ui` Next.js-agnostic (it's also consumed by Vite apps — `DocsSidebarNav` and `DocsLayout` stay pure, no `next/navigation` imports). Keeps the off-canvas chrome co-located with the docs-specific drawer (where it belongs) instead of forcing `SiteHeader` to grow a new layout mode that no other app needs. And the `mobileMenuContent === undefined` path is byte-identical to today's behavior, so marketing/payments/support sites are unaffected.

### 2. Drawer anatomy

When the header hamburger is tapped on a docs page, an off-canvas panel slides in from the left covering ~85% of the viewport width (`w-[85%] max-w-[320px]`, falls back to `w-full` below 360px). A scrim (`bg-black/40 backdrop-blur-sm`) covers the rest of the viewport; tap-outside closes the drawer.

Top to bottom, the drawer contains:

1. **Search input (sticky, top of drawer)** — full-width search field identical in styling to the desktop header search. Autofocus on open. Uses the same `onSearch` handler passed from `ClientLayout`. `Esc` key closes the drawer.

2. **Docs sidebar tree (scrollable, fills remaining space)** — the existing `DocsSidebarNav` rendered with the active-flagged items produced by `DocsLayout`'s `withActive(items, currentPath)` helper. The component as it stands today handles:
   - Active-link highlighting from `DocNode.active` (data-driven; we feed it from `currentPath`).
   - Section headers with no `href` rendered as non-clickable headings (e.g., "Core Concepts", "Guides") — confirmed at `DocsSidebarNav.tsx:25-34`.

   The tree is always fully expanded by design (no expand/collapse logic exists today and none is added). On a drawer with vertical scroll that's the right behavior — a scan of all sections is one swipe.

   One trivial override: `DocsSidebarNav` hardcodes `nav className="w-4/5"`. Inside the desktop sidebar's `w-64` container that's fine, but inside the drawer it would leave 20% empty on the right. We pass `className="w-full"` from `MobileDocsDrawer`; `cn` (a tailwind-merge wrapper at `packages/ui/src/lib/utils.ts`) resolves the conflict in favor of the later class.

3. **Site-link strip (sticky, bottom of drawer)** — a single-row footer with the four site links (Home / Pricing / Download / FAQ) rendered as small text links, separated by `·` dividers or thin borders. `border-t border-border bg-surface-raised`. Pinned at the bottom regardless of how far the tree is scrolled, so marketing nav is always one thumb-reach away without dominating the drawer.

### 3. Drawer behavior

| Trigger / event | Behavior | Owner |
|---|---|---|
| Hamburger tap | Drawer slides in from left, 200ms ease-out. Scrim fades in. Body scroll locks. Search field autofocuses. | SiteHeader toggles state; MobileDocsDrawer renders chrome |
| Scrim tap | Drawer slides out, scrim fades, body scroll unlocks. | MobileDocsDrawer calls `onClose` → SiteHeader |
| `Esc` key | Same as scrim tap. | SiteHeader (new `useEffect` adds keydown listener) |
| Tap any link inside drawer (docs tree or site strip) | Navigate to that URL **and** close the drawer. | `DocsSidebarNav` gains an `onLinkClick?` prop; MobileDocsDrawer wires it to `onClose` |
| Submit search | Triggers `onSearch(query)`, drawer closes. | MobileDocsDrawer |
| Window resize past `lg` (1024px+) | Hamburger button hides via `lg:hidden` on the toggle. If the drawer was open at the time of resize, the hidden class on the chrome wrapper still hides it visually; an additional `useEffect` watching a `matchMedia('(min-width: 1024px)')` listener force-closes the menu state to keep body-scroll-lock from sticking. | SiteHeader |

### 4. Right-rail TOC on mobile

Currently `tocItems` is hidden below `xl` (1280px). For mobile and tablet, we add an inline "On this page" disclosure at the top of `<article>` when `tocItems` is non-empty:

- Renders inside `DocsLayout`'s `<main>` block, immediately above `<article>`, with class `xl:hidden` so it disappears once the right rail appears.
- Collapsed by default. Tap to expand a flat list of section anchors (one level deep — h2 headings only, matching `TableOfContents` desktop behavior).
- Tapping any anchor closes the disclosure (since you're navigating within-page).
- Reuses the same `tocItems` data structure already plumbed through `DocsLayout`.

Rationale for keeping TOC out of the drawer: the left sidebar answers "where am I in the docs?" and the TOC answers "where am I in this page?". Tabbing them together (Tailwind v4's pattern) is heavier UX for the small win of one fewer affordance. The inline disclosure is discoverable exactly when relevant (long articles with multiple headings) and invisible when not (short pages, no `tocItems` passed in).

### 5. Concept-page exception

`ClientLayout.tsx` already routes `/concepts/*` paths through a full-width layout that bypasses `DocsLayout` entirely. Concept pages have their own internal section nav via `ConceptPageShell`. The mobile drawer work does not affect concept pages — they continue to use `SiteHeader` with its default mobile menu (site links only), which is correct because concept pages have no docs sidebar to surface.

### 6. Drawer markup sketch

```tsx
// packages/ui/src/components/docs/MobileDocsDrawer.tsx
"use client";

interface MobileDocsDrawerProps {
  items: DocNode[];           // already flagged by DocsLayout's withActive
  siteLinks: NavLink[];
  onSearch?: (q: string) => void;
  onClose: () => void;        // called on scrim tap, Esc (via SiteHeader), and link clicks
  searchPlaceholder?: string;
}

export function MobileDocsDrawer({ items, siteLinks, onSearch, onClose, searchPlaceholder }: MobileDocsDrawerProps) {
  return (
    <>
      {/* Scrim */}
      <div
        className="fixed inset-0 top-14 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
        onClick={onClose}
        aria-hidden
      />

      {/* Drawer panel */}
      <div
        className="fixed top-14 left-0 z-50 flex flex-col w-[85%] max-w-[320px] h-[calc(100vh-3.5rem)] bg-background border-r border-border shadow-xl lg:hidden animate-in slide-in-from-left duration-200"
        role="dialog"
        aria-label="Documentation navigation"
      >
        {/* Sticky search */}
        <div className="border-b border-border bg-background p-4">
          <SearchInput onSubmit={(q) => { onSearch?.(q); onClose(); }} autoFocus placeholder={searchPlaceholder} />
        </div>

        {/* Scrollable tree (fills remaining space, sits above the sticky footer) */}
        <nav className="flex-1 overflow-y-auto p-4">
          <DocsSidebarNav items={items} className="w-full" onLinkClick={onClose} />
        </nav>

        {/* Sticky site-link strip */}
        <div className="border-t border-border bg-surface-raised px-4 py-3">
          <ul className="flex items-center justify-between gap-2 text-xs text-text-muted">
            {siteLinks.map((link) => (
              <li key={link.href}>
                <a href={link.href} onClick={onClose} className="hover:text-primary transition-colors">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
```

Notes:
- The scrim and panel are siblings inside a fragment. Both use `fixed top-14` so they sit just below the 3.5rem-tall header, and both gate on `lg:hidden`.
- `SiteHeader` does not wrap `mobileMenuContent`. It renders it as a sibling of the header content when `mobileMenuOpen` is true, with no positioning of its own. All chrome lives inside `MobileDocsDrawer`.
- `slide-in-from-left` is from `tailwindcss-animate` — verify it's already in `packages/ui`'s plugin list during implementation; if not, drop in a one-line `@keyframes` in `globals.css` instead.

### 7. Auto-close-on-navigate

The existing `SiteHeader` mobile drawer does **not** auto-close on link click — links are plain `<a>` tags and the drawer stays open until the destination loads. Acceptable for a 4-link site nav, jarring with a 30-link docs tree.

`DocsSidebarNav` currently has no link-click hook (verified: `DocsSidebarNav.tsx:39-49` renders plain anchors). We add an optional `onLinkClick?: () => void` prop and call it from each anchor's `onClick`. Backward-compatible — desktop usage in `DocsLayout` doesn't pass the prop and behaves as today. `MobileDocsDrawer` passes `onClose`. Same hook is also called from the site-link strip anchors.

`SiteHeader` exposes `onClose` to `mobileMenuContent` either via a child-via-context pattern (small `MobileMenuContext` providing `close()`) or by accepting `mobileMenuContent` as a render-prop `(close: () => void) => ReactNode`. Render-prop is simpler and avoids context; recommended.

## Testing

- Visual: open the docs site dev server (`scripts/dev.sh`), narrow to 375px / 768px / 1023px / 1024px / 1280px viewports. Confirm:
  - At <1024px: hamburger present, opens drawer, drawer contains tree + sticky bottom site links.
  - At ≥1024px: drawer hidden, desktop sidebar visible.
  - At 1024–1279px: desktop sidebar visible, "On this page" disclosure visible above article when `tocItems` exists.
  - At ≥1280px: desktop sidebar visible, right-rail TOC visible, "On this page" disclosure hidden.
- Behavior: tap-outside closes drawer, `Esc` closes drawer, link tap closes drawer, body scroll locks while drawer is open.
- Active state: navigate to `/guides/smart-search`, open drawer, confirm "Smart Search" link is highlighted (background and text color from `DocsSidebarNav.tsx:43-46`'s active branch). Then on desktop, confirm the same highlight appears in the static sidebar — this verifies the `currentPath` plumbing fixed the latent active-state bug in both surfaces.
- Cross-app sanity: open `websites/apps/marketing` and `websites/apps/support` in dev — confirm their `SiteHeader` mobile menu still renders the default site-link list (no regression for non-docs apps).

## Files Changed

| File | Change |
|---|---|
| `packages/ui/src/components/site/SiteHeader.tsx` | Add `mobileMenuContent?: ReactNode \| ((close: () => void) => ReactNode)` and `mobileBreakpoint?: 'md' \| 'lg'` props. When `mobileMenuContent` is provided and the menu is open, render it as a sibling of the header content (no chrome wrapper). Toggle button visibility class flips to `lg:hidden` when `mobileBreakpoint='lg'`; inline desktop nav class flips to `lg:flex`. New `useEffect` adds a `keydown` listener for `Escape` to close the menu. New `useEffect` watching `matchMedia('(min-width: 1024px)')` force-closes the menu when the viewport crosses the breakpoint while the drawer is open (prevents body-scroll-lock from sticking). |
| `packages/ui/src/components/docs/DocsLayout.tsx` | Add `currentPath?: string` prop. Compute `withActive(sidebarItems, currentPath)` once via `useMemo`. Pass flagged items to both desktop sidebar and `MobileDocsDrawer`. Pass `mobileBreakpoint="lg"` and `mobileMenuContent={(close) => <MobileDocsDrawer ... onClose={close} />}` to `SiteHeader`. Add inline "On this page" disclosure above `<article>` when `tocItems` is non-empty (with `xl:hidden`). Desktop sidebar continues to be `hidden lg:block` (unchanged). |
| `packages/ui/src/components/docs/MobileDocsDrawer.tsx` | **New.** Renders its own off-canvas chrome (scrim + fixed left panel + slide-in animation), with sticky search at top, scrollable `DocsSidebarNav` in the middle, and sticky site-link strip at bottom. |
| `packages/ui/src/components/docs/DocsSidebarNav.tsx` | Add optional `onLinkClick?: () => void` prop, called on each anchor's `onClick`. No change to existing call sites. |
| `packages/ui/src/components/docs/index.ts` | Export `MobileDocsDrawer`. |
| `websites/apps/docs/src/app/ClientLayout.tsx` | Read `usePathname()` (already available — file is `"use client"`) and pass `currentPath={pathname ?? undefined}` into `DocsLayout`. One-line change. |
| `packages/ui/src/stories/docs/*` | Optional Storybook story for `MobileDocsDrawer` (visual review). |

No changes to:

- `websites/apps/docs/src/config/docs.ts` — sidebar tree definition is unchanged; `active` flags are now computed at render time instead of being absent in config.
- `websites/apps/marketing/src/app/ClientLayout.tsx`, `websites/apps/payments/src/app/ClientLayout.tsx`, `websites/apps/support/src/app/ClientLayout.tsx` — none of these pass `mobileMenuContent` or `mobileBreakpoint`, so `SiteHeader` falls back to its current `md:hidden` hamburger + default site-link dropdown. Behavior is byte-identical to today.

## Open Questions

None blocking. Two minor decisions deferred to implementation:

- Whether `slide-in-from-left` is already available via `tailwindcss-animate` in `packages/ui`'s plugin list. If not, add a one-shot `@keyframes` block in `globals.css` instead of pulling in a plugin.
- Whether the bottom site-link strip uses `·` text dividers or thin border separators. Visual call during implementation.

## Out of Scope (explicitly)

- Replacing the search input with a command palette.
- Adding a "Sections" tab inside the drawer (Tailwind v4 pattern). Deferred unless TOC handling proves insufficient in practice.
- Changing the desktop sidebar layout, breakpoint, or content.
- Restyling the docs typography or article layout.
