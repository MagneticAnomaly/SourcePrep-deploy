# Netlify Deployment Troubleshooting

> **Status: RESOLVED (2026-05-06).** `@prep/marketing` and `@prep/docs` deploy successfully via the `Deploy Websites to Netlify` workflow. Production URLs: https://sourceprep.io, https://docs.sourceprep.io. The remainder of this document is retained as a historical reference for the issues that were fixed and as a deployment runbook for adding new sites.
>
> **Update (2026-05-07): Storybook deploy job added.** `@prep/ui` builds via `build-storybook` turbo task and deploys `packages/ui/storybook-static/` to `storybook.sourceprep.io`. Pending one-time setup: create the Netlify site, add `NETLIFY_STORYBOOK_SITE_ID` GitHub secret, point DNS, and set `NEXT_PUBLIC_STORYBOOK_URL=https://storybook.sourceprep.io` on the docs Netlify site to activate the 12 existing `<StoryEmbed>` calls.

This document summarizes the issues encountered and solutions applied to successfully deploy the monorepo (marketing and docs apps) to Netlify via GitHub Actions.

## Initial Problem

The GitHub Actions workflow for deploying websites to Netlify was failing with various errors related to monorepo configuration, build failures, and Next.js static generation issues.

## Issues and Solutions

### 1. Netlify CLI Interactive Prompt

**Error**: `We've detected multiple sites inside your repository ? Select the site you want to work with`

**Cause**: Netlify CLI was prompting for interactive site selection in the CI environment, which is not supported.

**Solution**: Added `--filter` flag to `netlify-cli deploy` commands in `.github/workflows/deploy-websites.yml`:
```yaml
- name: Deploy to Netlify
  env:
    NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
    NETLIFY_SITE_ID: ${{ secrets.NETLIFY_MARKETING_SITE_ID }}
  run: npx netlify-cli deploy --prod --dir=websites/apps/marketing/.next --filter=@prep/marketing
```

### 2. Netlify Publish Directory Not Found

**Error**: `Error: Your publish directory was not found at: /home/runner/work/SourcePrep/SourcePrep/.next`

**Cause**: The `publish` path in `netlify.toml` was relative to the base directory, but Netlify expected an absolute path from the repo root.

**Solution**: Updated `publish` paths in both `netlify.toml` files to be absolute:
```toml
# websites/apps/marketing/netlify.toml
[build]
  base    = "websites/apps/marketing"
  command = "cd ../../.. && npx turbo run build --filter=@prep/marketing"
  publish = "websites/apps/marketing/.next"  # Changed from ".next"

# websites/apps/docs/netlify.toml
[build]
  base    = "websites/apps/docs"
  command = "cd ../../.. && npx turbo run build --filter=@prep/docs"
  publish = "websites/apps/docs/.next"  # Changed from ".next"
```

### 3. GitHub Actions Billing Block

**Error**: `The job was not started because recent account payments have failed or your spending limit needs to be increased`

**Cause**: GitHub Organization had no payment method and spending limit was set too low.

**Solution**: User added a payment method and increased the spending limit in GitHub Organization settings.

### 4. Next.js Server/Client Component Boundary Issues

**Error**: `You're importing a component that needs createContext. It only works in a Client Component but none of its parents are marked with "use client"`

**Cause**: Components using React hooks (like `createContext`) were imported in Server Components.

**Solution for Marketing App**:
- Split `websites/apps/marketing/src/app/setup/page.tsx` into:
  - `page.tsx` (Server Component) - handles metadata export
  - `ClientPage.tsx` (Client Component) - handles UI logic and data imports with `'use client'` directive

**Solution for Docs App**:
- Created `websites/apps/docs/src/config/mcp-setup.ts` as a re-export shim
- Initially tried deep imports from `@prep/ui/src/config/mcpSetup.ts`
- Finally copied the full content of `packages/ui/src/config/mcpSetup.ts` directly into the docs app to completely decouple from the bundled `@prep/ui` entry point

### 5. notFound() Crash During Static Generation

**Error**: `Error: Failed to collect page data for /dev/cli-demos` and `Error occurred prerendering page "/dev/cli-demos2"`

**Cause**: The `dev/layout.tsx` was calling `notFound()` during production static generation, which crashes the build.

**Solution**: Modified `websites/apps/marketing/src/app/dev/layout.tsx` to return a simple 404 UI in production instead of throwing:
```tsx
export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === 'production') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-text">
        <h1 className="text-2xl font-bold">404 - Not Found</h1>
      </div>
    );
  }
  return <>{children}</>;
}
```

### 6. Module Resolution with Deep Imports

**Error**: `Module not found: Package path ./src/config/mcpSetup.ts is not exported from package`

**Cause**: The `exports` field in `packages/ui/package.json` did not explicitly allow deep imports with the `.ts` extension.

**Attempted Solution 1**: Added explicit export to `packages/ui/package.json`:
```json
"exports": {
  ".": {
    "import": "./dist/index.js",
    "types": "./dist/index.d.ts"
  },
  "./src/config/mcpSetup": "./src/config/mcpSetup.ts",
  "./src/config/mcpSetup.ts": "./src/config/mcpSetup.ts",
  ...
}
```

**Attempted Solution 2**: Changed docs import to use the explicit export path
**Final Solution**: Copied the full content of `packages/ui/src/config/mcpSetup.ts` directly into `websites/apps/docs/src/config/mcp-setup.ts` to completely bypass module resolution issues.

### 7. Static Files Treated as Routes

**Error**: Build output showed routes like `/opengraph-image.png` and `/icon.png` with 0 B size, and warnings about "Failed to collect page data"

**Cause**: Static PNG files (`opengraph-image.png` and `icon.png`) were placed in `src/app/` directories. Next.js App Router treats all files in `app/` as routes, even non-JS/TS files.

**Solution**: Moved static files from `src/app/` to `public/` directories:
- `websites/apps/marketing/src/app/opengraph-image.png` → `websites/apps/marketing/public/images/opengraph-image.png`
- `websites/apps/marketing/src/app/icon.png` → `websites/apps/marketing/public/icon.png`
- `websites/apps/docs/src/app/opengraph-image.png` → `websites/apps/docs/public/opengraph-image.png`
- `websites/apps/docs/src/app/icon.png` → `websites/apps/docs/public/icon.png`

## Benign Warnings

The following warnings appear during builds but do not cause failures:

### patch-incorrect-lockfile.js Warning

**Warning**: `TypeError: Cannot read properties of undefined (reading 'os')` from `patch-incorrect-lockfile.js`

**Cause**: Next.js tries to patch the lockfile for SWC dependencies in monorepo setups, but this sometimes fails due to the package structure.

**Impact**: This is a warning only. The build continues and succeeds (exit code 0).

### Critical Dependency Warning

**Warning**: `Critical dependency: the request of a dependency is an expression`

**Cause**: Dynamic imports in the bundled `@prep/ui` package.

**Impact**: This is a warning only. The build continues and succeeds.

## Key Lessons

1. **Static assets belong in `public/`**: Never place static files (images, fonts, etc.) in the Next.js `app/` directory - they will be treated as routes.

2. **Server/Client Component boundaries**: Be explicit about which components need `'use client'` and structure pages accordingly (Server Component for metadata, Client Component for interactive UI).

3. **Monorepo path resolution**: In CI environments, use absolute paths for Netlify publish directories relative to the repo root.

4. **Netlify CLI flags**: Use `--filter` in monorepo deployments to bypass interactive prompts.

5. **Module exports**: Deep imports from packages require explicit configuration in the `exports` field of `package.json`. When in doubt, copy the data locally.

## Current Status

Both `@prep/marketing` and `@prep/docs` build successfully locally and deploy to Netlify via GitHub Actions. The workflow file is at `.github/workflows/deploy-websites.yml`.

## Related Files

- `.github/workflows/deploy-websites.yml` - GitHub Actions workflow
- `websites/apps/marketing/netlify.toml` - Marketing Netlify config
- `websites/apps/docs/netlify.toml` - Docs Netlify config
- `websites/apps/support/netlify.toml` - Support Netlify config
- `websites/apps/payments/netlify.toml` - Payments Netlify config
- `packages/ui/netlify.toml` - Storybook Netlify config
- `websites/apps/marketing/src/app/setup/page.tsx` - Server Component example
- `websites/apps/marketing/src/app/setup/ClientPage.tsx` - Client Component example
- `websites/apps/marketing/src/app/dev/layout.tsx` - Dev-only layout with production fallback
- `packages/ui/package.json` - Package exports configuration

## Deployment Process for Additional Sites

The same workflow pattern is used for every site. Each site is its own Netlify project; GitHub Actions builds via Turbo, then `netlify-cli deploy` pushes the build artifacts to the corresponding project. Adding a new site is a four-step process.

### One-time setup per site

1. **Create the Netlify project** (in the Netlify dashboard) and copy its Site ID.
2. **Add GitHub secrets**:
   - `NETLIFY_AUTH_TOKEN` (already exists; shared across all sites)
   - `NETLIFY_<SITE>_SITE_ID` (e.g. `NETLIFY_STORYBOOK_SITE_ID`, `NETLIFY_SUPPORT_SITE_ID`, `NETLIFY_PAYMENTS_SITE_ID`)
3. **Set per-site environment variables in the Netlify dashboard** (see each `netlify.toml` for the required list — `support` needs GitHub/Resend keys, `payments` needs Lemon Squeezy keys, `storybook` needs none).
4. **Add a job to `.github/workflows/deploy-websites.yml`** mirroring the existing `deploy-marketing` job — only the `--filter`, `--dir`, and site-id env var change.

### Per-site specifics

| Site | Domain | Build filter | Publish dir (CLI `--dir`) | Notes |
|------|--------|--------------|---------------------------|-------|
| Storybook | storybook.sourceprep.io | `@prep/ui` (build target: `build-storybook`) | `packages/ui/storybook-static` | Static Vite build; no Next.js plugin. Docs site reads it via `NEXT_PUBLIC_STORYBOOK_URL`. |
| Support | support.sourceprep.io | `@prep/support` | `websites/apps/support/.next` | Next.js + `@netlify/plugin-nextjs`. Requires `GITHUB_TOKEN`, `RESEND_API_KEY`, `BUG_REPORT_EMAIL`, `NEXT_PUBLIC_SITE_URL` in Netlify env. |
| Payments | payments.sourceprep.io | `@prep/payments` | `websites/apps/payments/.next` | Next.js + `@netlify/plugin-nextjs`. Requires `LEMONSQUEEZY_API_KEY`, `LEMONSQUEEZY_STORE_ID`, `NEXT_PUBLIC_LS_CHECKOUT_*`, `NEXT_PUBLIC_SITE_URL` in Netlify env. |

### Pre-flight check before activating each site

Before un-commenting a deploy job, verify the `netlify.toml` `publish` path is **absolute from the repo root** (e.g. `websites/apps/support/.next`, not `.next`) — see Issue 2 above. The `ui` config was fixed on 2026-05-07. The current `support` and `payments` configs still use relative paths and will need to be updated when activated.
