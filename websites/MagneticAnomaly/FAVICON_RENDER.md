# Magnetic Anomaly — Logo & Favicon Render Pages

This directory contains two related render pages that share the same tiny-moon + rainbow-polar-arc particle scene.

## Public page: `/logo-generator`

`logo-generator/index.html` is the source for the **live, public page** at `https://magneticanomaly.llc/logo-generator`. It renders the same stripped-down scene and is meant to be screenshotted or linked as a brand asset.

- Indexed by search engines.
- Includes Open Graph / Twitter Card meta tags.
- Built and deployed with the rest of the site.

Open it locally while developing:

```bash
npm run dev
open http://localhost:5175/logo-generator
```

## Local-only page: `/favicon.html`

`favicon.html` is a stripped-down, **no-index render page** used to generate the site's favicon and touch-icon assets.

The main Magnetic Anomaly site renders a full-screen WebGL scene with multiple planets, scroll-driven camera motion, and heavy post-processing. That composition is far too busy to read at favicon size (16×16–180×180 px).

`favicon.html` renders **one tiny moon with a handful of colorful polar-arc particles** using the same shader code as the main site. It exists only so we can:

1. Open it locally in a browser.
2. Screenshot the canvas at a high resolution.
3. Crop and scale the screenshot into favicon / Apple touch icon / PWA icon assets.

It is intentionally **not linked from the public site** and is blocked from search indexing.

## Files

| File | Purpose |
|------|---------|
| `logo-generator/index.html` | Public HTML shell with social/meta tags |
| `src/logo-generator.jsx` | React entry point for the public page |
| `favicon.html` | Minimal HTML shell with `noindex,nofollow,noarchive` robots meta |
| `src/favicon.jsx` | React entry point that mounts only `<FaviconScene />` |
| `src/FaviconScene.jsx` | Scene setup: tiny moon, camera, no post-process bloom |
| `src/FaviconParticles.jsx` | Favicon-tuned particle shader (big heads, dramatic tail shrink, polar arcs, rainbow colors) |

## How to use the local favicon render

```bash
npm run dev   # serves the whole site, including /favicon.html
open http://localhost:5175/favicon.html
```

Then use your OS screenshot tool or the browser dev tools to capture the canvas. The page auto-animates; pick a frame where the arcs are nicely distributed. Crop to a square and scale to the target icon sizes.

## Building and previewing

```bash
npm run build
npm run preview
```

The build emits both the main site (`/`) and the public logo generator (`/logo-generator`). The local favicon render (`/favicon.html`) is available in dev but is **not** included in the production build.

## Do not deploy the favicon render page

`/favicon.html` is for local asset generation only. It is not part of the public navigation and is excluded from crawlers via the robots meta tag.
