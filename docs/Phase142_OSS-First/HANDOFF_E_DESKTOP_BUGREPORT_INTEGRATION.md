# Handoff — Session E: Desktop bug-report integration, security headers, rate-limit store

> **Self-contained starter prompt** for a dedicated follow-up session.
> Follows Session B (support-portal security hardening, DR-4/DR-5), whose
> findings are in `docs/Phase142_OSS-First/DEEP_RESEARCH_B_SECURITY_FINDINGS.md`.
> Session B is on branch `deep-research/security` (may or may not be merged to
> main by the time you run this — the items below are written to stand alone).

## What this session is

Engineering follow-up to close the cross-cutting loose ends Session B found but
was scoped out of (they live outside `websites/apps/support/src/`), plus the one
approved build task Session B deliberately did not ship. **Code mutation**,
worktree-isolated, review-gated, no push.

## Hard rules

- **Worktree-isolated.** Before any edit, create a worktree (`EnterWorktree`
  tool, name `session-e-bugreport`; or `git worktree add` under
  `.claude/worktrees/` so `node_modules` resolves upward to the repo root).
- **Read-only on git history.** No `git checkout` of files you didn't create,
  no `git stash pop`, no `git reset`. Other sessions share this repo.
- **Commit per logical unit** on the worktree branch. **No push. No
  Co-Authored-By. Never `git commit --amend`** (concurrent sessions collide).
- **License-neutral** for the code items. Item 5 (privacy text) is a legal
  publication — **do NOT apply it unless Eric has approved the wording AND
  accepted Resend's DPA**, and never push/deploy it without that.
- **SourcePrep = brand; prep = code.** No CoDRAG/RunPrep in copy or new code.
- **prep MCP:** call `prep` (no args) first (project_id in
  `.sourceprep/AGENT_CONTEXT.md`). Run **`prep_impact` before editing
  `packages/ui/src/components/console/BugReportModal.tsx`** — it's in the shared
  `@prep/ui` package. Note unhelpful/wrong prep results as product feedback.
- **Verify before claiming done.** Typecheck what you touch (see each item). If
  your model cannot read images, verify UI via text (getComputedStyle /
  DOM / snapshot), not screenshots.

## Context you need (verified 2026-07-19/20)

- The bug-report flow: `BugReportModal.tsx` (in `@prep/ui`, rendered by
  `LogConsole.tsx`, shown in the desktop app's console) does a **browser
  `fetch`** to a hardcoded `https://support.sourceprep.io/api/bug-report`, which
  the support-site backend receives and emails via Resend.
- **`support.sourceprep.io` is misconfigured (as of 2026-07-20):** it resolves
  (Cloudflare → Netlify) but currently **serves Storybook**, not the support app —
  the custom-domain alias is on the wrong Netlify site. `/admin` and
  `/api/bug-report` both **404**. The `deploy-support` CI job is also commented
  out. So the desktop path (items 1–2) only fully works once the support app is
  actually deployed AND the `support.sourceprep.io` custom domain is moved off the
  Storybook site onto it. Flag this ops/DNS step to Eric — code alone won't fix it.
- Session B's support-side **CORS allowlist already includes the Tauri webview
  origins** (`tauri://localhost`, `https://tauri.localhost`, `http://tauri.localhost`),
  so once the desktop CSP is fixed the cross-origin POST will be accepted.

## Items

### E-1. Unblock desktop bug submission (Tauri CSP)

`src/prep/dashboard/src-tauri/tauri.conf.json` → `tauri.security.csp` →
`connect-src` currently lists `'self' http://127.0.0.1:8400 ws://127.0.0.1:8400
ws://localhost:* http://localhost:* https://api.lemonsqueezy.com https://github.com
https://objects.githubusercontent.com` — **no sourceprep.io host**, so the
in-webview `fetch` to the support endpoint is CSP-blocked and silently falls
back to file download.
- **Add exactly `https://support.sourceprep.io`** to `connect-src` (the specific
  host, NOT a wildcard). The modal uses browser `fetch`, governed by
  `connect-src` — not the Tauri `http.scope` allowlist, so that stays as-is.
- Verify the JSON parses and the CSP string is well-formed.

### E-2. De-hardcode / align the bug-report endpoint

`packages/ui/src/components/console/BugReportModal.tsx` hardcodes
`BUG_REPORT_ENDPOINT = 'https://support.sourceprep.io/api/bug-report'` with an
"update when cloud endpoint is deployed" comment, pointing at a host that
currently NXDOMAINs.
- Decide with Eric whether `support.sourceprep.io` is the real production host.
  If yes: the constant is fine but the host must be provisioned + deployed
  (separate ops step). If the endpoint will live elsewhere, update the constant.
- Consider making it overridable (a `BugReportModalProps.endpoint?: string`
  prop, defaulting to the constant) so it isn't purely hardcoded and can be
  pointed at a staging host in tests. Keep the existing download-fallback.
- `prep_impact` this file first (shared package). Typecheck: `cd packages/ui &&
  npm run typecheck` (and a build if the type surface changes).

### E-3. HTTP security headers on the support site

`websites/apps/support/next.config.js` sets **no** `headers()`. Add an
`async headers()` applying to all routes:
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `X-Frame-Options: DENY` (admin dashboard should not be framed)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` locking down unused features (camera/mic/geo=()).
- A page `Content-Security-Policy` is a **stretch goal** — Next.js injects inline
  scripts, so a strict CSP needs nonces and careful testing; do the safe headers
  above first and only attempt CSP if you can verify the admin UI still renders.
- Typecheck/build the support app: `npm --prefix websites/apps/support run typecheck`
  then `npm --prefix websites/apps/support run build`.

### E-4. Persistent rate-limit store (Netlify Blobs) — Eric-approved direction

Replace the in-memory `rateLimitMap` in
`websites/apps/support/src/app/api/bug-report/route.ts` (marked `TODO(DR-5.2)`)
with **Netlify Blobs**, strong consistency + an **ETag compare-and-swap** loop
for the counter (Blobs has no atomic INCR — rationale + citations in the
Session B findings doc §6). Also:
- Switch the client-IP source from the **spoofable** leftmost `x-forwarded-for`
  to Netlify's trusted `x-nf-client-connection-ip` (fall back gracefully).
- Add the `@netlify/blobs` dependency. On Netlify the store is provisioned
  automatically (no dashboard config). **If Blobs is unavailable in the deploy,
  keep the in-memory fallback with the TODO — do NOT ship a broken store.**
- Typecheck + build the support app.

### E-5. Resend sub-processor disclosure — GATED on Eric approval + DPA

The product privacy policy is the marketing `/security` page:
`websites/apps/marketing/src/app/security/page.tsx` ("Privacy Policy" section,
`#data-collection` anchor). It has a **Bug Reports** section and names one
sub-processor (**Lemon Squeezy**, payments) but **not Resend**. Add Resend as an
email-delivery sub-processor beside that content, using the drafted text in the
Session B findings doc §6.
- **DO NOT apply unless Eric has approved the exact wording AND accepted
  Resend's DPA.** This is a legal publication — if either is missing, leave it
  and surface to Eric. Never push/deploy it without both.

## Ordering

E-1 + E-2 are the desktop-submit path (do together). E-3 and E-4 are independent
(support app). E-5 is gated/optional. Any order; one commit per item is fine.

## What to PRODUCE

- Code changes committed on the worktree branch (`fix(...)` / `feat(...)` per
  logical unit; no Co-Authored-By; no push).
- A short findings note (append to the Session B findings doc or a new
  `HANDOFF_E_RESULTS.md`): what changed with file:line, what was deferred and
  why (esp. anything gated on ops/DNS/DPA), typecheck/build evidence, and the
  diff summary + commit list.

## STOP and surface to Eric when

- The license-neutral items (E-1, E-3, E-4; E-2 code portion) are committed and
  typecheck/build clean.
- E-5 is either applied (only with Eric's approval + DPA) or clearly deferred.
- The desktop-submit path's remaining ops dependency (provision + deploy
  `support.sourceprep.io`) is called out — code alone won't make it live.
- Nothing merged, nothing pushed. Surface the worktree path + branch + commits.
