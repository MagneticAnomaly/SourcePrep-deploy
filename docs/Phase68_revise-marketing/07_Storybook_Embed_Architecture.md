# Storybook Embed Architecture — Option B: Sandboxed Iframes

## Overview

Embed live, interactive Storybook dashboard panels directly into the public documentation site using sandboxed iframes. The Storybook static build is hosted at a separate origin and rendered via a `<StoryEmbed>` wrapper component.

## Security Model

| Layer | Mechanism | What It Prevents |
|-------|-----------|-----------------|
| **Origin isolation** | Storybook on `storybook.codrag.io` | No shared cookies, localStorage, DOM access |
| **Iframe sandbox** | `sandbox="allow-scripts"` | No navigation, forms, popups, top-frame access |
| **Referrer policy** | `no-referrer` | No URL leakage from docs → storybook |
| **CSP headers** | `default-src 'self'; script-src 'self' 'unsafe-inline'` | No external script injection |
| **Mock data only** | Stories use hardcoded fixtures | No real API calls, no `localhost:8400` |
| **Minified bundle** | Vite production build | Source not human-readable |

## Component: `<StoryEmbed>`

```tsx
interface StoryEmbedProps {
  storyId: string;            // "dashboard-widgets-searchpanel--default"
  height?: number | string;   // default 400
  title?: string;             // accessible label
  theme?: 'light' | 'dark';  // sync with docs theme
  className?: string;
}
```

### URL Construction
```
{STORYBOOK_BASE}/iframe.html?id={storyId}&viewMode=story&globals=theme:{theme};codragTheme:h
```

### Sandbox Attributes
```html
<iframe
  sandbox="allow-scripts allow-same-origin"
  referrerPolicy="no-referrer"
  loading="lazy"
  allow=""
/>
```

> **Note:** `allow-same-origin` is required so the iframe can load its own Vite-bundled JS chunks. Without it, the browser treats the iframe as an opaque origin and blocks sub-resource loading. Security is maintained because in production the Storybook is hosted on a **separate subdomain** (different origin), so `allow-same-origin` merely restores the iframe's ability to access its own assets — not the parent's.

## Story-to-Page Mapping

| Docs Page | Story ID | Shows |
|-----------|----------|-------|
| `/dashboard` | `dashboard-layouts-fulldashboard--full-dashboard` | Full modular dashboard |
| `/mcp` | `dashboard-widgets-searchpanel--default` | Search panel |
| `/mcp` | `dashboard-widgets-indexstatuscard--loaded` | Index status |
| `/concepts/trace-graph` | `dashboard-widgets-trace-graph--default` | Trace graph |
| `/concepts/trace-graph` | `dashboard-widgets-trace-coveragepanel--default` | Coverage stats |
| `/guides/codebase-audit` | `dashboard-widgets-trace-graphenrichmentpipeline--full-pipeline-running` | Pipeline viz |
| `/getting-started` | `dashboard-widgets-buildcard--default` | Build card |
| `/getting-started` | `dashboard-widgets-usageguidepanel--default` | Usage guide |
| `/search` | `dashboard-widgets-searchpanel--full-search-demo` | Full search |
| `/search` | `dashboard-widgets-search-components--search-results` | Results list |

## Hosting Options

| Option | URL | Pros | Cons |
|--------|-----|------|------|
| **Vercel subdomain** | `storybook.codrag.io` | Clean separation, easy deploy | Extra Vercel project |
| GitHub Pages | `magneticanomaly.github.io/codrag-storybook/` | Free, separate origin | Slower updates |
| Docs subpath | `docs.codrag.io/_storybook/` | Single deploy | Shares origin (weaker isolation) |

**Development**: Points to `http://localhost:6006` for hot-reload iteration.

## Hardening Checklist

- [ ] Separate origin deployment
- [ ] CSP headers on Storybook host
- [ ] `sandbox="allow-scripts"` on all iframes
- [ ] Stories use mock data only
- [ ] No `localhost:8400` references in stories
- [ ] `X-Frame-Options: ALLOW-FROM docs.codrag.io` on Storybook
- [ ] `referrerPolicy="no-referrer"` on all iframes
- [ ] Lazy loading for performance
