# Canonical Site Header Nav Order

> Last updated: 2026-05-07

The four public Next.js sites (`marketing`, `docs`, `payments`, `support`) must
present **the same nav items in the same order** so that users moving between
them never have to re-learn the layout.

## The canonical order (left → right)

```
Home · Docs · Pricing · Download · FAQ
```

Each site **omits the entry that points to itself**.

## Per-site result

| Site                 | Header nav (in order)                  |
|----------------------|----------------------------------------|
| `sourceprep.io`      | Docs · Pricing · Download · FAQ        |
| `docs.sourceprep.io` | Home · Pricing · Download · FAQ        |
| `payments.sourceprep.io` | Home · Docs · Pricing · Download · FAQ |
| `support.sourceprep.io` | Home · Docs · Pricing · Download · FAQ *(deferred — site on backburner; current copy retained until launch)* |

## What goes in the header vs the footer

**Header — primary cross-site nav (max 5 entries).** Items the user is
likely to want from anywhere on the property: identity, docs, money, software,
help. Keep this list short and stable.

**Footer — everything else.** Per-site curated. Examples:
- marketing: Changelog, Research, Compare, Community, Careers, Blog, Privacy, Terms, Status
- docs: Components/Storybook, Troubleshooting, FAQ, Support
- payments: Recover license, Status, Support
- support: Status, Bug reports

**Storybook (`storybook.sourceprep.io`)** does not use the SourcePrep site
header at all — it ships with the standard Storybook chrome and is consumed
mostly by developers who arrive via direct link. If we ever want a "back to
docs" rail on Storybook, do it via Storybook's own toolbar / navbar
configuration, not by injecting our `SiteHeader`.

## Why this order

- **Home** first when present — front door, identity. Always leftmost.
- **Docs** before commerce — the most-used cross-site link from people who are
  already users (not buyers).
- **Pricing** before **Download** — sales funnel order: see what it costs,
  then get it.
- **FAQ** last — overflow / catch-all.
- **Support** is intentionally NOT in the header. It's reachable from the
  footer on every site. Promoting it to the header would imply something is
  wrong; we'd rather lead with the docs/FAQ cycle and keep Support in arm's
  reach without front-loading it.

## When to change this list

Editing this list is a deliberate choice that affects every site. If you
think a sixth header item is warranted (or one of the five should go), do
the following:

1. Update this document **first** with the new order and rationale.
2. Update each site's `ClientLayout.tsx` to match.
3. Verify all four sites build cleanly (`npm run build` per app).
4. Note the change in the closest available phase / changelog file.

Specifically — do **not** edit one site's nav in isolation. The whole point
of this document is that drift between sites is a UX bug. If you find a site
that doesn't match this list, fix the site, not the list.

## Implementation pointers

- Each site's nav lives in its `src/app/ClientLayout.tsx` `navLinks` array.
- Cross-site URLs use environment-aware constants (`HOME_URL`, `DOCS_URL`,
  etc.) so dev mode hits localhost dev servers and prod hits the real
  subdomains.
- The `SiteHeader` and `SiteFooter` components themselves live in
  `@prep/ui` (`packages/ui/src/components/site/`) and are shared across all
  four apps.
