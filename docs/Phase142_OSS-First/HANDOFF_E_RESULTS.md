# Handoff — Session E: Results

> Follow-up to `HANDOFF_E_DESKTOP_BUGREPORT_INTEGRATION.md`. Closes the
> cross-cutting loose ends Session B found but was scoped out of, plus the one
> approved build task (Netlify Blobs rate-limit) Session B deliberately did not
> ship. **Code mutation, worktree-isolated, review-gated, NOT merged, NOT
> pushed.**
>
> **Status: E-1, E-2, E-3, E-4 implemented + committed on branch
> `session-e-bugreport`. E-5 deferred (gated, AND already done on main — see
> §E-5). Typecheck + build clean; CAS algorithm verified by a 21-assertion
> harness; adversarial 5-lens review run, 2 confirmed defects fixed.**

---

## 0. TL;DR for Eric

- **Four license-neutral items done** (E-1 Tauri CSP, E-2 endpoint prop,
  E-3 security headers, E-4 Netlify Blobs rate-limit) in 4 commits, plus 2
  follow-up commits for defects the adversarial review caught. **6 commits
  total** on `session-e-bugreport` (based on `deep-research/security` @
  `ee12dcbd`). Typecheck + `next build` clean; CAS logic covered by a standalone
  harness (21/21).
- **E-5 (Resend disclosure) is deferred — and already done on main.** Session A's
  commit `78dd6b3b` (on main, 2026-07-20) already added the Resend sub-processor
  disclosure to the marketing `/security` page with DPA/SCC language. The
  handoff E-5 was written from Session B's branch, which predates `78dd6b3b` and
  never saw it. Do NOT re-apply E-5 on this branch — it would duplicate and
  conflict on merge. The only remaining E-5 gate is your offline acceptance of
  Resend's DPA (a legal act, not code).
- **Two review fixes worth your attention:** (a) I dropped HSTS `preload` — the
  spec demanded it but it's premature while `support.sourceprep.io` isn't live
  (serves Storybook; `/admin` + `/api/bug-report` 404); preload is a multi-year
  commitment. Re-add it post-deploy. (b) The Blobs CAS loop would have silently
  degraded to unconditional writes if a `getWithMetadata` ever returned no ETag —
  guarded now (§E-4).
- **Concurrent-session hazard encountered (no damage):** during this session,
  main advanced with the dead-codename scrub (tip `da235073`→`1a354b43`) and an
  uncommitted footer/`ClientLayout` WIP. My worktree is based on
  `deep-research/security` (itself based on old main `5bad7d9a`), so **merging
  `session-e-bugreport` to current main will need a rebase** — but the root
  `package-lock.json` and `websites/apps/support/package.json` were NOT touched
  by main's scrub, so there are no textual lockfile conflicts (the E-4
  license-field refresh MIT→Apache-2.0 flows in the correct direction). A
  post-merge `npm install` is reasonable hygiene, not required to resolve
  conflicts.
- **Ops dependency (not code):** E-1 + E-2 unblock the desktop submit path in
  code, but `support.sourceprep.io` currently serves **Storybook** (custom
  domain on the wrong Netlify site) and `/api/bug-report` 404s. Submission only
  goes live once you move the custom domain to the deployed support site.

---

## 1. What changed (with file:line + commit)

### E-1. Unblock desktop bug submission (Tauri CSP) — `2a212df3`

`src/prep/dashboard/src-tauri/tauri.conf.json` → `app.tauri.security.csp` →
`connect-src`: added `https://support.sourceprep.io` (specific host, not a
wildcard) right after `'self'`. The bug-report modal uses browser `fetch`
(governed by `connect-src`, not the Tauri `http.scope` allowlist), so this is
the right lever. Session B's support-side CORS allowlist already accepts the
Tauri webview origins, so once the host is provisioned the cross-origin POST is
accepted both ways.

### E-2. De-hardcode the bug-report endpoint — `43d2ce96`

`packages/ui/src/components/console/BugReportModal.tsx`: added optional
`BugReportModalProps.endpoint?: string` (default `= BUG_REPORT_ENDPOINT`); the
modal's `fetch` now uses the resolved `endpoint`, and `endpoint` is in the
`handleSubmit` `useCallback` deps (no stale closure). Existing caller
(`LogConsole.tsx`) passes no `endpoint` → identical behavior. Download-fallback
unchanged. `prep_impact` first: real TS dependents are `LogConsole.tsx` + the
storybook story + barrel — an optional prop breaks none. Typecheck (@prep/ui)
adds **zero** new errors (374 before = 374 after; the pre-existing Button
union errors are environmental — also present in untouched `LogConsole.tsx`).

### E-3. HTTP security headers — `3de0208b` + review fix `4636f015`

`websites/apps/support/next.config.js`: added `async headers()` on
`source: '/:path*'` (covers `/`, `/admin`, `/api/*` — `:path*` matches
zero-or-more segments). Headers: HSTS, `X-Frame-Options: DENY`, `X-Content-Type-
Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy: camera=(), microphone=(), geolocation=()`. **No CSP**
intentionally (Next.js inline scripts need nonces; add only after verifying the
admin UI renders). Review fix: dropped HSTS `preload` (premature — see §0) and
added a trailing newline.

### E-4. Persistent rate-limit store (Netlify Blobs) — `63157241` + review fix `60b40069`

`websites/apps/support/src/app/api/bug-report/route.ts`: replaced the
per-instance in-memory `rateLimitMap` (which reset on every serverless cold
start, so the 10/hr limit was effectively unenforced across the fleet) with a
shared **Netlify Blobs** store at strong consistency + an **ETag compare-and-
swap retry loop** (Blobs has no native atomic INCR). Keys on client IP — Blobs
keeps it inside our existing host, adding **no new subprocessor** (the deciding
factor vs Upstash). Falls back to the in-memory map if Blobs is unavailable
(local dev / missing context) and degrades to in-memory on a runtime failure —
never a broken store. Also switched the client-IP source from the spoofable
leftmost `x-forwarded-for` to Netlify's trusted `x-nf-client-connection-ip`
(graceful fallback). Review fix: guard the CAS against a missing ETag (§E-4
review).

Added `@netlify/blobs@^10.7.9` to the support app's deps. The lockfile also
refreshes 4 workspace license fields (MIT→Apache-2.0) and drops `dev:true`
from `semver`/`tmp` (now runtime deps of the Blobs transitive tree) — benign
and in the correct direction (main's lockfile had stale MIT entries).

---

## 2. E-5 — Resend sub-processor disclosure: DEFERRED (already done on main)

The handoff E-5 says to add Resend as an email-delivery sub-processor to the
marketing `/security` page's Privacy Policy, gated on (a) your approval of the
wording AND (b) your acceptance of Resend's DPA.

**Finding: the wording is already published on main.** Session A's commit
`78dd6b3b` ("fix(phase142): apply DR-A legal fix-now items", 2026-07-20, on
main) added exactly this disclosure to
`websites/apps/marketing/src/app/security/page.tsx` lines 273–280 (inside the
`#data-collection` Privacy Policy section, right after the "open-source
collects nothing" paragraph):

> …nothing unless you choose to send a bug report or support request. Bug
> reports and support emails you submit are delivered through **Resend**, a
> US-based email subprocessor, under a data-processing agreement with Standard
> Contractual Clauses. Resend receives your message and reply-to email plus
> the diagnostics report attached to your submission.

This is essentially the text Session B §6 drafted. The handoff E-5 was written
from Session B's branch (`deep-research/security`), which split from main at
`5bad7d9a` **before** `78dd6b3b` landed — so it never saw the disclosure and
flagged a gap that no longer exists.

**Action: NONE on this branch.** Do not re-apply E-5 — it would duplicate and
conflict on merge (main already has it). The only remaining E-5 gate is your
**offline acceptance of Resend's DPA** ([resend.com/legal/dpa](https://resend.com/legal/dpa))
— a legal act, not code. Confirm that's done; the published wording already
references "a data-processing agreement with Standard Contractual Clauses."

---

## 3. Adversarial verification (5-lens review)

A 5-agent read-only review ran across the diff (CSP, BugReportModal compat,
security headers, Blobs CAS, lockfile hygiene). **2 confirmed defects, both
fixed;** the rest sound or refuted-as-acceptable.

| Lens | Verdict | Outcome |
|---|---|---|
| E-1 Tauri CSP | **sound** | Host added to `connect-src`, specific (no wildcard), CSP well-formed, JSON parses, no other directive altered. |
| E-2 BugReportModal | **sound** | Optional prop defaults to constant, `fetch` uses resolved `endpoint`, deps updated, download-fallback intact, no caller broken. |
| E-3 security headers | needs-fix → **fixed** | `preload` premature (dropped, `4636f015`); `/:path*` covers all routes (confirmed); `X-Frame-Options: DENY` appropriate (PII dashboard, no legit embeds); no CSP intentional/safe; trailing-newline nit (added). |
| E-4 Blobs CAS | needs-fix → **fixed** | **CAS voided on missing ETag** (medium) — fixed in `60b40069`; IP-source spoofing on non-Netlify proxy accepted/documented; fail-open-on-exhaustion safe (no over-increment); blobsStore/blobsDisabled state consistent; strong consistency + lazy init + rate-limit-before-parse all clean. |
| E-4 lockfile/pkg | **sound** | Dep version reasonable; no new subprocessor (all added packages are local libs); commit-message "purely additive" claim was slightly inaccurate (benign license refresh — noted here, not amended); merge onto main is textually clean for the root lockfile (main's scrub didn't touch it). |

### The E-4 defect in detail (the valuable one)

`Store.getWithMetadata` returns `etag?: string` — optional; the Blobs runtime
computes it from the response ETag header, which can be absent. The CAS loop
passed `{ onlyIfMatch: entry.etag }` to `Store.set`; when `etag` is `undefined`,
Blobs' `getConditions` does a **truthiness** check (`"onlyIfMatch" in options &&
options.onlyIfMatch`), so `{ onlyIfMatch: undefined }` becomes **no condition** →
an **unconditional write** that always returns `modified: true`. Every
concurrent writer would "win", each reading the same `count` and writing
`count+1` → lost update / under-counting (fail-open direction), and the retry
loop never detects the race. Fix (`60b40069`): if an existing entry has no
ETag, **fail open for that request without writing** (return `true`) — skip
counting one request rather than clobber a concurrent writer. New harness case
T10 proves: no-etag → allow + count unchanged (no unconditional clobber).

---

## 4. Verification evidence

- **E-1**: `python3 -c "json.load(...)"` — JSON parses, CSP `connect-src`
  contains `https://support.sourceprep.io`, well-formed.
- **E-2**: `@prep/ui` `tsc --noEmit` — 374 errors before == 374 after (my edit
  adds zero new errors; pre-existing Button union errors are environmental,
  also in untouched `LogConsole.tsx`). No errors at my edited lines.
- **E-3**: support `tsc --noEmit` clean (exit 0); `next build` —
  `✓ Compiled successfully`, 14 routes incl. `/api/bug-report`, exit 0.
- **E-4**: support `tsc --noEmit` clean (exit 0); `next build` —
  `✓ Compiled successfully`, `/api/bug-report` present, exit 0. Standalone CAS
  harness (`/tmp/e4-cas-harness.mjs`, 21 assertions, not committed) — exact
  limit + count cap, per-IP isolation, window-expiry reset, concurrent-first no
  lost/double count, persistent contention → fail open + no over-increment,
  corrupt/malformed overwrite, no off-by-one, **no-etag → fail open no-write
  (T10)**. All 21 pass.
- **Lockfile**: diff is additive in the new `@netlify/*` + `@opentelemetry/*`
  tree; no existing package's `version`/`integrity` changed (only 4 workspace
  `license` fields refreshed and `dev:true` dropped from `semver`/`tmp`).

> The `⨯ Failed to patch lockfile` / `TypeError: ... reading 'os'` lines during
> `next build` are a cosmetic Next.js telemetry/lockfile-patch warning in the
> shared-node_modules worktree setup — they print after `Compiled successfully`
> and do not fail the build (exit 0).

---

## 5. For Eric — review & merge

- **Worktree:** `/Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/session-e-bugreport`
- **Branch:** `session-e-bugreport` (based on `deep-research/security` @ `ee12dcbd`)
- **Commits (6):**
  - `2a212df3` fix(dashboard): allow support.sourceprep.io in Tauri CSP connect-src (E-1)
  - `43d2ce96` feat(ui): make BugReportModal endpoint overridable via prop (E-2)
  - `3de0208b` fix(support): add HTTP security headers to all routes (E-3)
  - `63157241` feat(support): persistent rate-limit via Netlify Blobs + trusted client IP (E-4)
  - `60b40069` fix(support): guard CAS against missing ETag in Netlify Blobs (E-4 review fix)
  - `4636f015` fix(support): drop premature HSTS preload + add trailing newline (E-3 review fix)
- **Review with:** `git -C .claude/worktrees/session-e-bugreport diff ee12dcbd..HEAD`
- **Merge note:** this branch is based on `deep-research/security` (based on
  old main `5bad7d9a`). Main has since advanced with the dead-codename scrub.
  The root `package-lock.json` and support `package.json` are textually
  conflict-free vs main (main's scrub touched `packages/ui/package-lock.json`,
  not these). Expect to **rebase `session-e-bugreport` (and
  `deep-research/security`) onto current main**; a post-merge `npm install` is
  reasonable hygiene. Nothing was merged or pushed.

### Diff summary (excl. lockfile)

```
 packages/ui/src/components/console/BugReportModal.tsx  |   9 +-
 src/prep/dashboard/src-tauri/tauri.conf.json           |   2 +-
 websites/apps/support/next.config.js                   |  31 +++++
 websites/apps/support/package.json                     |   1 +
 websites/apps/support/src/app/api/bug-report/route.ts  | 122 ++++++++++++++++++---
 5 files changed, 147 insertions(+), 18 deletions(-)
```

### Open follow-ups (Eric's call, not code)

1. **Ops/DNS:** move `support.sourceprep.io` off the Storybook Netlify site onto
   the deployed support site (currently `/admin` + `/api/bug-report` 404). E-1
   + E-2 only go live once this is fixed.
2. **HSTS preload:** re-add `; preload` to the HSTS value (E-3) AFTER the support
   app is deployed, the custom domain is moved, and the cert is stable.
3. **Resend DPA:** confirm you've accepted Resend's DPA — the published
   disclosure (main `78dd6b3b`) already references it; this is the last E-5 gate.
4. **Persistent store for the report store** (`lib/reports.ts`, in-memory, no
   size bound) — same durability question as the rate-limit; out of Session E
   scope (Session B §8 flagged it for the same follow-up).