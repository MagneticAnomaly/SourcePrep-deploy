# Phase 137 — Tech Fix: NEXT_PUBLIC_STORYBOOK_URL

> **Status:** Edit landed locally in `websites/apps/docs/netlify.toml`.
> **Not yet pushed** — do not push without explicit user signal per memory
> `feedback_explicit_push_only.md`.

## Symptom (the screenshot)

On production `docs.sourceprep.io/dashboard`, the live `<StoryEmbed>` block
under "Overview" rendered:

- "SourcePrep Docs" header
- A giant "404"
- "Doc not found" + "Docs Home" / "Search Docs" buttons
- Caption beneath: "A populated dashboard — drag, resize, and close panels…"

All of those UI elements are docs-site components (`SourcePrep Docs` header
is the docs `ClientLayout.tsx`; the 404 body is `not-found.tsx`). They were
rendering *inside* the iframe — meaning the iframe `src` was resolving to a
docs-site URL, not to Storybook.

## Root cause

`websites/apps/docs/src/components/StoryEmbed.tsx:17`:

```ts
const STORYBOOK_BASE_URL = process.env.NEXT_PUBLIC_STORYBOOK_URL || '/storybook';
```

`NEXT_PUBLIC_*` env vars in Next.js are inlined at *build time*, not runtime.
The docs Netlify environment did not have `NEXT_PUBLIC_STORYBOOK_URL` set,
so the build emitted `'/storybook'` as the base URL.

In production, the iframe `src` therefore became:

```
/storybook/iframe.html?id=demos-fulldashboard--default&viewMode=story&...
```

A relative path on the docs origin. Next.js's catch-all routing sent that
through `not-found.tsx`, which rendered inside the iframe.

## The fix

Added to `websites/apps/docs/netlify.toml` under `[build.environment]`:

```toml
NEXT_PUBLIC_STORYBOOK_URL = "https://storybook.sourceprep.io"
```

Why this works:

- **Build-time inlining.** Netlify exports the `[build.environment]` table
  as env vars during `next build`. The Next compiler inlines
  `process.env.NEXT_PUBLIC_STORYBOOK_URL` into the client bundle at that
  point — so the value ships in the JS that runs in the browser.
- **Origin exists.** Storybook deploys to `storybook.sourceprep.io` via
  `packages/ui/netlify.toml`.
- **CSP allows the embed.** The Storybook host's response headers include:
  ```
  Content-Security-Policy: ...frame-ancestors 'self' https://sourceprep.io https://*.sourceprep.io;
  ```
  `docs.sourceprep.io` matches the wildcard. Modern browsers honor
  `frame-ancestors` over the deprecated `X-Frame-Options: ALLOW-FROM`.

## Security audit — current iframe strategy

The design of record is
`docs/Phase68_revise-marketing/07_Storybook_Embed_Architecture.md`. Re-checked
against current code on 2026-05-13:

| Defense | Status | Evidence |
|---|---|---|
| `sandbox="allow-scripts allow-same-origin"` | ✅ matches spec | `StoryEmbed.tsx:101` |
| `allow-same-origin` justified | ✅ safe | Iframe loads from a different origin (`storybook.sourceprep.io`) than parent (`docs.sourceprep.io`); attribute restores iframe's own asset loading without granting parent-origin access. Per `07_Storybook_Embed_Architecture.md:45`. |
| CSP `frame-ancestors` on Storybook host | ✅ in place | `packages/ui/netlify.toml:14` |
| `referrerPolicy="no-referrer"` | ✅ in place | `StoryEmbed.tsx:102` |
| `allow=""` (no camera/mic/geo) | ✅ in place | `StoryEmbed.tsx:104` |
| `loading="lazy"` | ✅ in place | `StoryEmbed.tsx:103` |
| Stories use only mock fixtures | ✅ confirmed | Phase 131 `02_visual_design_plan.md` |

**No newer vulnerability patches require changes.** Phase 131 (Storybook
curation) did not modify the embed model. The strategy is current.

### Latent risk that this fix closes

Before the fix, when `NEXT_PUBLIC_STORYBOOK_URL` was unset, the iframe loaded
`/storybook` on the *same origin* as the docs site. Combined with
`allow-same-origin`, that would normally permit iframe→parent access to
localStorage, cookies, etc. Real-world impact was nil because:

- Docs has no auth state, no cookies of interest, no localStorage with sensitive data
- The 404 page inside the iframe didn't ship any malicious script

But it was an unintended same-origin posture. Setting the env var moves the
iframe back to a cross-origin host, restoring the intended isolation.

## Verification checklist

Run after the netlify.toml change is pushed and Netlify rebuilds the docs site:

- [ ] Visit `https://docs.sourceprep.io/dashboard` — the embed under
  "Overview" should render the modular dashboard story (panels visible),
  not a 404.
- [ ] Visit `https://docs.sourceprep.io/mcp` — embeds in the tools section
  should render.
- [ ] Visit `https://docs.sourceprep.io/cli` — `<AnimatedCLI>` should render
  in addition to any `<StoryEmbed>`.
- [ ] DevTools → Network: iframe `src` attribute should start with
  `https://storybook.sourceprep.io/iframe.html?id=...` and the response
  should be 200, not a redirect to the docs origin.
- [ ] DevTools → Console: no CSP violation errors. (If you see a CSP error
  about `frame-ancestors`, check that the Storybook deploy is using the
  current `packages/ui/netlify.toml` and not a stale build.)
- [ ] DevTools → Elements: the iframe's `sandbox` attribute should still be
  `"allow-scripts allow-same-origin"`.

## Local-dev parity

For local dev, `NEXT_PUBLIC_STORYBOOK_URL` is unset, so the fallback
`/storybook` kicks in. The docs dev server doesn't serve Storybook at that
path, so embeds will 404 locally just like prod did before this fix.

Two options for local dev parity:

1. **Run Storybook locally** at `:6006` (`cd packages/ui && npm run storybook`)
   and set `NEXT_PUBLIC_STORYBOOK_URL=http://localhost:6006` in
   `websites/apps/docs/.env.local`. This is the proper local-dev posture.
2. **Point local dev at the production Storybook** by setting
   `NEXT_PUBLIC_STORYBOOK_URL=https://storybook.sourceprep.io` in
   `.env.local`. Faster, but you're testing against the deployed Storybook.

Neither option is committed — `.env.local` is gitignored. A follow-up could
add a `.env.example` documenting this if it's a friction point.

## Anchors

- `websites/apps/docs/netlify.toml` — the env-var change (this fix)
- `websites/apps/docs/src/components/StoryEmbed.tsx:17` — the fallback that
  masked the bug
- `packages/ui/netlify.toml` — Storybook CSP and deploy config
- `docs/Phase68_revise-marketing/07_Storybook_Embed_Architecture.md` —
  security design of record
- `docs/Phase131_StorybookCuration/02_visual_design_plan.md` — current
  Storybook theming for docs embeds (`prepTheme='m'` Retro Aurora,
  `docsMode:true`)
