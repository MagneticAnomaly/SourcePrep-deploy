# Magnetic Anomaly — Favicon Render Page

This directory contains a local-only, no-index render page used to generate the site's favicon and touch-icon assets.

## Why this page exists

The main Magnetic Anomaly site renders a full-screen WebGL scene with multiple planets, scroll-driven camera motion, and heavy post-processing. That composition is far too busy to read at favicon size (16×16–180×180 px).

`favicon.html` is a stripped-down version that renders **one tiny moon with a handful of colorful polar-arc particles** using the same shader code as the main site. It exists only so we can:

1. Open it locally in a browser.
2. Screenshot the canvas at a high resolution.
3. Crop and scale the screenshot into favicon / Apple touch icon / PWA icon assets.

It is intentionally **not linked from the public site** and is blocked from search indexing.

## Files

| File | Purpose |
|------|---------|
| `favicon.html` | Minimal HTML shell with `noindex,nofollow,noarchive` robots meta |
| `src/favicon.jsx` | React entry point that mounts only `<FaviconScene />` |
| `src/FaviconScene.jsx` | Scene setup: tiny moon, camera, no post-process bloom |
| `src/FaviconParticles.jsx` | Favicon-tuned particle shader (big heads, dramatic tail shrink, polar arcs, rainbow colors) |

## How to use

```bash
npm run dev   # serves the whole site, including /favicon.html
open http://localhost:5176/favicon.html
```

Then use your OS screenshot tool or the browser dev tools to capture the canvas. The page auto-animates; pick a frame where the arcs are nicely distributed. Crop to a square and scale to the target icon sizes.

## Do not deploy

This page is for local asset generation only. It is not part of the public navigation and is excluded from crawlers via the robots meta tag.
