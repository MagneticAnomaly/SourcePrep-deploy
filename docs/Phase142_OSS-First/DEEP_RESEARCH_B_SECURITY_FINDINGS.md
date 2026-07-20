# Deep-Research Session B — Security engineering findings (DR-4, DR-5)

> Produced by the follow-up security-engineering session for the 2026-07-19
> legal+security+message audit. Scope: **code mutation** in
> `websites/apps/support/src/`, worktree-isolated, review-gated.
> Parent audit: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`.
> Handoff: `docs/Phase142_OSS-First/DEEP_RESEARCH_HANDOFF_B_SECURITY.md`.
>
> **Status: DO-NOW mitigations implemented + committed on branch
> `deep-research/security`. Typecheck clean. NOT merged, NOT pushed.**
> Eric-decision items are framed below (design only — nothing decided/published).

---

## 0. TL;DR for Eric

- **All license-neutral DO-NOW mitigations are done** across DR-4 (admin auth)
  and DR-5 (bug-report intake), in two commits on the worktree branch. The app
  **typechecks clean** (`tsc --noEmit`).
- **Urgency is MODERATE, not an emergency.** The support site is **not
  currently reachable**: `support.sourceprep.io` returns **NXDOMAIN**, and the
  `deploy-support` CI job is commented out. This is *pre-ship* hardening — the
  fixes are the gate before the endpoint goes public, but there is no active
  exposure at the canonical host today.
- **Env-var audit is clean** — no secret is exposed to the client bundle
  (no `NEXT_PUBLIC_` on `ADMIN_TOKEN` / `RESEND_API_KEY` / `BUG_REPORT_EMAIL` /
  `GITHUB_TOKEN`).
- **Four items need YOUR decision** (framed in §6, none acted on): auth-provider
  choice, the Resend sub-processor disclosure *text*, the persistent rate-limit
  store, and one cross-cutting desktop-app CSP fix that is out of this session's
  edit scope.
- Review the branch and merge it yourself (§9). Do not expect me to have merged.

---

## 1. Deploy status & urgency (the GATE)

The handoff asked to confirm whether the endpoint is publicly reachable and to
escalate if live. Findings (verified against the repo + DNS on 2026-07-19):

| Signal | Result |
|---|---|
| `deploy-support` job in `.github/workflows/deploy-websites.yml` | **Commented out** (lines ~160–181). Not deployed via CI. |
| `websites/apps/support/netlify.toml` | Exists; `base = websites/apps/support`; **`[deploy]`-gated** `ignore` rule (only builds when the tip commit message contains `[deploy]`). A Netlify git-integration deploy path *could* exist if the Netlify site is connected. |
| DNS `support.sourceprep.io` | **NXDOMAIN** (system resolver). Apex `sourceprep.io` resolves (Cloudflare) — so DNS works; the `support` subdomain is simply **not provisioned**. |
| Public OSS mirror (`tools/build_public_mirror.py`) | **Includes** `websites/apps/support` (allowlist line 72). Committed hardening becomes public OSS code — fine (secrets are env-only). |
| Desktop client target | `packages/ui/.../BugReportModal.tsx` hardcodes `https://support.sourceprep.io/api/bug-report` — a host that currently does not resolve, so **submission is non-functional in production today** (falls back to local download). |

**Conclusion:** the support site / bug-report endpoint is **not publicly
reachable at its canonical host** as of 2026-07-19. Harden now (it's the
pre-ship gate) but there is **no live-exposure emergency**. If you provision
`support.sourceprep.io` and land a `[deploy]` commit, these mitigations must be
in place first.

> **Update (2026-07-20):** `support.sourceprep.io` now **resolves** (Cloudflare
> → Netlify, `x-nf-request-id` present) but is **serving Storybook** (page title
> `@storybook/cli - Storybook`), not the support app — the custom-domain alias is
> attached to the wrong Netlify site. Both `/admin` and `/api/bug-report` return
> **404**. So: (a) still **no live exposure** of the admin/PII dashboard — the
> conclusion holds; (b) there's a **DNS/Netlify misconfiguration** to fix before
> ship — the `support.sourceprep.io` custom domain must be moved off the
> Storybook site and onto the deployed support site; (c) the desktop modal's POST
> to `.../api/bug-report` 404s today (fails to download-fallback). Folded into the
> Session E handoff ops step.

---

## 2. DR-4.1 — `isAuthorized` / `isAuthorizedServer` caller → PII matrix

Every consumer of the admin gate (`websites/apps/support/src/lib/auth.ts`),
confirmed via `prep_impact` (5 dependents) + grep:

| Caller | Auth fn used | Route / purpose | PII / sensitive data behind the gate |
|---|---|---|---|
| `app/admin/auth/route.ts` | `COOKIE_NAME`, `deriveSessionId`, `safeEqual` | `POST /admin/auth` — validate token, set session cookie | Sets the auth cookie. Returns nothing. |
| `app/admin/layout.tsx` | `isAuthorizedServer` | Server-component gate wrapping **all** `/admin/*` pages | Gates the entire admin UI (report list + full detail). |
| `app/api/bug-reports/route.ts` | `isAuthorized` | `GET /api/bug-reports` — list | Per report: reporter **email**, description, `project_id`, `license_tier`, `platform`, status. |
| `app/api/bug-reports/[id]/route.ts` | `isAuthorized` | `GET` detail + `PATCH` mutate `/api/bug-reports/:id` | GET: reporter **email** + full diagnostic **payload** (logs, platform, diagnostics), `project_id`, `license_tier`. PATCH: status/assignee mutation. |
| `app/api/bug-reports/metrics/route.ts` | `isAuthorized` | `GET /api/bug-reports/metrics` | Aggregate counts only (low sensitivity). |

The list and detail endpoints are the real PII surface (reporter emails +
diagnostic payloads); the auth gate hardening below protects all of them.

---

## 3. What changed — DR-4 (admin auth hardening)

Commit **`c5fd9ac8`** — `fix(support): harden admin auth gate (DR-4.2–4.5)`.
Files: `lib/auth.ts`, `lib/audit.ts` (new), `app/admin/auth/route.ts`,
`app/admin/layout.tsx`.

| # | Was | Now |
|---|---|---|
| DR-4.2 | `?token=<secret>` query-param accepted in `isAuthorized` | **Removed.** Cookie + `Authorization: Bearer` only. (A secret in a URL leaks via `Referer` and access logs.) |
| DR-4.3 | 3× raw `===` token compares (`auth.ts`, plus login route) | **Constant-time** `safeEqual` — SHA-256 each side then `timingSafeEqual`. Fixed-length digests, so it never throws on length mismatch and leaks no length via timing. |
| DR-4.4 | `NODE_ENV !== 'production'` auto-authorizes the no-token path (an unset NODE_ENV opens admin) | **Hard-deny** via `isConfirmedDevelopment()` — the no-token path opens ONLY for `NODE_ENV === 'development' \| 'test'`. Anything ambiguous denies. Applied in `isAuthorized`, `isAuthorizedServer`, and `admin/layout.tsx`. |
| DR-4.5 | Cookie stored the **raw ADMIN_TOKEN** | Cookie stores an **opaque session id** = `HMAC-SHA256(key=ADMIN_TOKEN, "prep-admin-session:v1")` via `deriveSessionId`. Never the raw token; can't be reversed to it; can't be replayed as the Bearer API key. Rotating ADMIN_TOKEN invalidates all sessions. |
| — | Login cookie `Secure` only when `NODE_ENV==='production'` | `Secure` everywhere except confirmed dev (`!isConfirmedDevelopment()`). |
| DR-4.6 (infra) | No audit trail | New `lib/audit.ts`: PII-free structured audit log (`logAdminAudit`), actor = `hashActor` (non-reversible 12-hex of the credential). Admin **login success/failure** is now audited. |

**Note — session cookie format change:** any admin currently holding the old
raw-token cookie will be logged out and must re-authenticate (their cookie no
longer matches the derived id). Acceptable — the site isn't live, so there are
no live sessions.

## 3b. What changed — DR-5 + DR-4.6/4.7 (bug-report API hardening)

Commit **`855e2b6b`** — `fix(support): harden bug-report API — CORS,
rate-limit, PII, audit (DR-4.6–4.7, DR-5.1–5.4)`. Files: `lib/cors.ts` (new),
`app/api/bug-report/route.ts`, `app/api/bug-reports/route.ts`,
`app/api/bug-reports/[id]/route.ts`, `app/api/bug-reports/metrics/route.ts`.

| # | Was | Now |
|---|---|---|
| DR-5.1 | `Access-Control-Allow-Origin: '*'` on **all four** support API routes | New `lib/cors.ts`: reflects the request `Origin` **only if allowlisted** (sourceprep.io web family + Tauri webview origins `tauri://localhost` / `https://tauri.localhost` / `http://tauri.localhost` + localhost dev). `Vary: Origin` set. **No** `Allow-Credentials`, so allowlisting never exposes cookies. **Native clients send no `Origin` and are unaffected** — the server still processes them, so desktop/CLI submission is preserved. |
| DR-5.4 | Reporter email + `platform` + `project` + `license_tier` + log `level`/`time`/`logger` interpolated **raw** into the Resend notification HTML | **All attacker-controllable values HTML-escaped** — closes a stored/blind-XSS vector in the recipient's mail client. |
| DR-5.4 | Email validated only by `.includes('@')` | **Strict** validation: single-line one-`@` regex, length ≤254, explicit CR/LF reject → blocks header injection into the Resend `reply_to`. |
| DR-5.4 | No input size bounds | Caps: description ≤20 000, free-text fields ≤5 000, logs ≤1 000 entries. Prevents oversized-payload / log-flood abuse of the unauthenticated endpoint. `logs` normalized to `[]` when omitted (also fixes a latent crash). |
| DR-4.7 | `console.log(... email=${report.reporter.email} ...)` wrote PII to function logs | **Email removed** from the log line (report id + severity + log count only). |
| DR-5.2 | In-memory `rateLimitMap` grows unbounded across distinct IPs | Prunes expired entries past a 10 000-IP watermark (memory-exhaustion DoS bound). Carries a `TODO(DR-5.2)` documenting the cold-start reset + the recommended persistent store. **Not** replaced (no store configured — see §6). |
| DR-4.6 | No mutation audit | `PATCH /api/bug-reports/:id` now emits a PII-free audit event (actor = hashed credential, report id, field changes). |

---

## 4. Env-var audit (DR-4.8 / DR-5.3) — PASS

- No `NEXT_PUBLIC_` prefix on any secret anywhere in `websites/apps/support/src`.
- `ADMIN_TOKEN`, `RESEND_API_KEY`, `BUG_REPORT_EMAIL`, `GITHUB_TOKEN` are read
  only in server route handlers / server components → never client-bundled.
- The only `NEXT_PUBLIC_*` referenced is `NEXT_PUBLIC_SITE_URL` (a public URL,
  in `netlify.toml` comments). No leak.

Minor (not fixed — out of `src/` scope, license-neutral): `.env.local.example`
still documents the stale default `bugs@prep.io`, while `route.ts` defaults to
`bugs@sourceprep.io`. Cosmetic brand drift; flag for a later cleanup.

---

## 5. Cross-cutting findings (out of this session's edit scope)

These are real, but touch files **outside** `websites/apps/support/src/`, so —
per the handoff — I did **not** edit them. Surfacing for follow-up:

1. **Desktop bug-report submission is CSP-blocked today (HIGH, latent).**
   `packages/ui/src/components/console/BugReportModal.tsx` `fetch`es
   `https://support.sourceprep.io/api/bug-report`, but the Tauri
   `connect-src` CSP (`src/prep/dashboard/src-tauri/tauri.conf.json`) does
   **not** list any `sourceprep.io` host. So the in-webview submit is blocked
   regardless of CORS. **Fix (separate change):** add
   `https://support.sourceprep.io` to `connect-src`. My CORS allowlist already
   includes the Tauri origins, so once the CSP is fixed the submit will work.
2. **Hardcoded, unreachable endpoint.** Same file hardcodes the support host
   (`BUG_REPORT_ENDPOINT`) with a "update when cloud endpoint is deployed"
   comment. It points at a host that currently NXDOMAINs. Consider making it
   configurable and gating the "Send" path on the host being live.
3. **No HTTP security headers.** `websites/apps/support/next.config.js` sets no
   `headers()` (no CSP, `X-Frame-Options`, `X-Content-Type-Options`,
   `Referrer-Policy`, HSTS). Adding a headers block is license-neutral and worth
   doing before ship — but it edits the app-root config, not `src/`, so it's
   flagged rather than applied here.

---

## 6. Eric-decision items (DESIGN ONLY — nothing decided or published)

The following need your sign-off. Independent web-sourced analysis (a 3-agent
research pass) is included verbatim below.

> **Decisions (Eric, 2026-07-20):**
> 1. **Auth provider — KEEP the hardened rolled-own gate.** Approved; no further
>    code needed (already built). `ADMIN_TOKEN` is set via env var only (never in
>    source); documented in `netlify.toml`. Login page at `/admin`.
> 2. **Rate-limit store — Netlify Blobs (strong-consistency + ETag CAS).**
>    Approved as the direction. **Still a follow-up build task** — not yet wired.
> 3. **Resend disclosure — approved to proceed.** Eric's action, not code: accept
>    Resend's DPA + add the drafted disclosure to the existing privacy policy.
>    **Location (corrected):** the product privacy policy lives in the marketing
>    `/security` page — `websites/apps/marketing/src/app/security/page.tsx`, the
>    "Privacy Policy" section at the `#data-collection` anchor (footer/terms link
>    there). It already has a **Bug Reports** section and names **one**
>    sub-processor (**Lemon Squeezy**, payments) but **not Resend**. Add Resend
>    as an email-delivery sub-processor beside the Bug Reports / Lemon Squeezy
>    content using the drafted text below. Small, concrete edit — no new policy
>    needed. (Publishing legal text is Eric's call + gated on the signed Resend
>    DPA, so it's not done in this session.)

### Auth-provider evaluation (DESIGN ONLY)

Comparison for a **single-admin** PII dashboard on Next.js 14 (App Router) / Netlify, where adding a data subprocessor is a real cost to the OSS/privacy posture.

| Criterion | Hardened rolled-own (opaque session) | NextAuth / Auth.js v5 (Credentials) | Clerk (hosted) |
|---|---|---|---|
| Setup / migration | Already in progress; minimal | Days: adapter, `auth.ts`, middleware, callbacks | Hours to wire, but re-architects the gate |
| Cost (2026) | $0 | $0 (MIT, self-hosted) | Free ≤50K MRU; Pro $25/mo — free tier covers one admin ([Clerk pricing](https://clerk.com/pricing)) |
| Self-hosted vs hosted | Fully self-hosted | Self-hosted | Hosted only |
| **New data subprocessor?** | **No** | **No** (Credentials provider needs no third party) | **Yes** — Clerk stores/processes the identity; a subprocessor disclosure obligation |
| MFA | Not built-in (add TOTP later) | Not built-in; DIY via Credentials + a TOTP lib | Built-in (TOTP, passkeys, SMS) |
| Session revocation | Trivial — rotate the derived secret / clear server session | Supported with a DB session strategy (JWT strategy is harder to revoke) | Built-in, per-session dashboard revocation |
| Overkill for one admin? | No — right-sized | **Yes** — its value is OAuth/multi-provider/DB sessions you don't have | **Yes** — a full identity platform for one login |

**Status (2026):** Auth.js v5 is stable for App Router and its Credentials provider is fully supported ([Auth.js docs](https://authjs.dev/getting-started/providers/credentials)), but its maintainers now steer *new* projects toward Better Auth rather than NextAuth ([LogRocket, 2026](https://blog.logrocket.com/best-auth-library-nextjs-2026/)) — i.e. NextAuth is a migration tool, not a greenfield default. Clerk's free tier fits a solo founder ([saasprices](https://saasprices.net/blog/clerk-free-plan-changes)); cost is not the objection — the subprocessor is.

**Recommendation: KEEP the hardened rolled-own opaque-session gate.** For exactly one admin, both alternatives add a moving part without buying anything you need: NextAuth's value is OAuth providers and DB-backed sessions (you have neither), and Clerk's value is hosted identity at the price of a **new PII subprocessor** — directly counter to the OSS/privacy stance for a dashboard that already exposes reporter PII. The hardened gate already covers the actual threat model: protect one credential, allow instant revocation (rotate `ADMIN_TOKEN`). Add app-level TOTP if you want MFA — stays self-hosted, no third party.

**Switch conditions:**
- **Adopt NextAuth/Auth.js (or Better Auth)** once there is **more than one admin**, you need **role/permission separation**, OAuth/SSO, or DB-backed multi-session management — i.e. when you're managing *users*, not a *secret*.
- **Adopt Clerk** only if you additionally want **managed MFA/passkeys, SSO/SAML, and a session/audit UI without building them** — and the subprocessor disclosure becomes acceptable (team/enterprise scale, not solo-founder).
- **Keep rolled-own** as long as it's one admin and MFA can be met with self-hosted TOTP.

### Persistent rate-limit store (DESIGN ONLY / ED-adjacent)

The current in-memory `Map` is not viable on Netlify's serverless runtime: each function instance has its own memory, counters reset on cold start, and nothing is shared across instances, so the 10 req/hr limit is effectively unenforced. A shared persistent store is required. Two realistic options:

**Atomic increment (the decisive axis).** A rate limiter needs an atomic `INCR`-with-expiry to avoid two concurrent requests both reading `9` and both writing `10`.
- **Upstash Redis** provides native atomic `INCR` and ships [`@upstash/ratelimit`](https://www.npmjs.com/package/@upstash/ratelimit) — a turnkey library (sliding/fixed-window, token-bucket) whose increment+expire is atomic server-side ([overview](https://upstash.com/docs/redis/sdks/ratelimit-ts/overview)). Effectively a drop-in replacement for the `Map`.
- **Netlify Blobs** has **no native atomic increment** — only optimistic-concurrency conditional writes via `onlyIfMatch`/`onlyIfNew` (ETag compare-and-swap), so you hand-roll a read-modify-write **retry loop** ([docs](https://docs.netlify.com/build/data-and-storage/netlify-blobs/)).

**Consistency.** Blobs default to eventual consistency (up to 60s edge propagation) and require explicit **strong-consistency** opt-in for a limiter to be correct; strong reads add latency. Upstash Redis is strongly consistent within a region by default.

**Free tier (2026).** Upstash: **500K commands/month** free, then $0.20/100K ([pricing](https://upstash.com/pricing/redis)) — far more than a low-volume intake needs. Netlify Blobs is included in the Netlify plan you already pay for.

**Setup.** Blobs is zero-integration — already available via `@netlify/plugin-nextjs`, no new account/secret. Upstash needs a database + `UPSTASH_REDIS_REST_URL` / `_TOKEN` env vars.

**Subprocessor / privacy (material here).** The store keys on **client IP, which is PII under GDPR**. Netlify Blobs keeps that inside your **existing** host — **no new subprocessor**. Upstash is a **new third-party subprocessor** that must be added to the subprocessor list + DPA.

**Recommendation:** Use **Netlify Blobs with a strong-consistency store + an ETag compare-and-swap retry loop.** At ~10 req/hr/IP, contention is negligible, so the lack of native `INCR` is a non-issue, and it **adds no subprocessor** for IP-derived PII — the right call for this privacy posture. **Tradeoff:** you write/test the CAS/retry increment yourself instead of getting Upstash's audited atomic limiter for free. **Choose Upstash only if** volume grows enough that CAS contention becomes real — then `@upstash/ratelimit` is the correct tool, at the cost of a new subprocessor + DPA entry.

### Resend sub-processor disclosure (DESIGN ONLY — Eric must approve)

> **DRAFT — NOT legal advice, NOT reviewed by counsel, NOT published.** Proposed privacy-notice text only. Eric (founder, not a lawyer) must review and approve before any of it goes live.

**1. One-line sub-processor disclosure**

> We use **Resend** ([resend.com](https://resend.com)) as our email-delivery sub-processor to send bug-report notifications to our team.

**2. Proposed "Sub-processors" / "How we handle your data" paragraph**

> When you submit a bug report, we send that report to our team via **Resend**, a transactional email provider acting as our sub-processor. Resend receives the email address you provide and the diagnostic report attached to your submission, solely so the notification can be delivered to us. Resend processes this data on our behalf under a data processing agreement and does not use it for its own purposes. Our current sub-processors are listed at [resend.com/legal/subprocessors](https://resend.com/legal/subprocessors) and summarized in our sub-processor list linked below.

**3. What the founder (Eric) still must do — legal basis**

- **Sign / accept Resend's DPA.** Confirmed: Resend publishes a DPA ([resend.com/legal/dpa](https://resend.com/legal/dpa)) naming it as an Art. 28 processor, with Standard Contractual Clauses and EU–US Data Privacy Framework coverage. Verify which acceptance path applies and retain the signed copy.
- **Publish a sub-processor list + link it from the privacy policy.** GDPR Art. 28 expects controllers to disclose sub-processors (name, purpose, data categories) and notify on changes; add an entry — *Resend · email delivery · reporter email + diagnostic report* — and link it.
- **Record the legal basis.** Under **GDPR Art. 28** Resend is engaged under general written authorization; under **CCPA/CPRA** it should be contracted as a *service provider* (processing limited to the business purpose, no sale/sharing). Have counsel confirm the DPA satisfies both before publishing.

Sources: [Resend DPA](https://resend.com/legal/dpa) · [Resend GDPR](https://resend.com/security/gdpr) · [Resend sub-processors](https://resend.com/legal/subprocessors) · [Subprocessors under GDPR (Art. 28)](https://complydog.com/blog/subprocessors)

---

## 7. `prep_impact` blast-radius notes

- `prep_impact(auth.ts)` returned **5 dependents** (the four route files +
  `admin/layout.tsx`) — matches the caller matrix in §2 exactly. The auth
  contract is small and fully enumerated; the hardening preserved every export
  the dependents use (`isAuthorized`, `isAuthorizedServer`, `COOKIE_NAME`) and
  only **added** exports (`deriveSessionId`, `safeEqual`, `isConfirmedDevelopment`,
  `getRequestActor`), so no dependent broke. Typecheck confirms.
- New `lib/audit.ts` and `lib/cors.ts` are leaf modules (imported by auth/routes,
  import nothing back) — no cycles introduced.

### Dogfooding notes on prep (product feedback)

- `prep_impact(file_path="…/lib/auth.ts")` worked well and was **more accurate
  than grep would have been quickly** — it enumerated exactly the 5 importers.
  It did print `node not found in trace graph` yet still returned correct
  dependents, which is confusing UX (says "not found" then lists 5 results).
  Worth reconciling that message.
- `prep_search("who imports isAuthorized isAuthorizedServer from support lib
  auth")` **errored** `NODE_NOT_FOUND` — it tried to treat the whole natural-
  language question as a symbol id instead of routing to a TRACE/semantic
  search. A "who imports X" query should not hard-error; it should fall back to
  trace/semantic. This matches the known "search bias / classifier" gap.
- `prep(task=…, role security)` gave a useful Security-Engineer atlas but keyed
  onto pipeline/docs modules rather than the support app — the support portal
  wasn't surfaced as a security-relevant module despite being the actual admin/
  PII surface. The corpus's doc-heavy bias again outranked the code that
  mattered for the task.

---

## 8. Adversarial review verification

The diff was put through a 4-lens adversarial review (auth/crypto, CORS-bypass,
PII/injection, regression/runtime) plus a senior adjudicator that verified each
finding against the real code and hunted for misses. The security-critical
crypto/validation logic was also verified with a standalone Node harness
(29 assertions, all pass): constant-time compare edge cases, session-id
determinism + non-reversibility + rotation-invalidation, login roundtrip, old
raw-token-cookie rejection, Bearer-vs-cookie separation, dev-fallback hard-deny,
and email CR/LF-injection rejection.

**One real defect found and fixed** (commit `af09b050`):

- **Malformed log entry → anonymous HTTP 500** (severity low, fixed). `validate()`
  bounded the `logs` array but not entry *shape*, so `logs:[null]` passed and
  `l.level` in the email render threw a `TypeError` outside `sendNotification`'s
  try/catch → a trivially, anonymously triggerable 500 that defeated this
  change's own "prevents a latent crash" claim. Fix: reject non-object log
  entries in `validate()`, null-guard the log filters, and wrap the email call
  so a render/delivery failure degrades to `email_sent=false`. Verified: `tsc`
  clean + a 7-case validate check (`logs:[null]` rejected, valid entries pass).

**One accepted-tradeoff observation** (info, no code change): the session cookie
is a static, non-rotating, non-revocable bearer value (a pure function of
`ADMIN_TOKEN` with a 7-day `maxAge`). The adjudicator confirmed this is **not** a
forge/replay break — the cryptographic separation is sound — but an inherent
shared-secret MVP limitation. The fix (per-login nonce / signed issued-at +
expiry for individual revocation) is the migration path documented in the
auth-provider section of §6. No change now.

**Verified SOUND by the adjudicator** (no fix needed): Bearer-vs-cookie
credential separation (a stolen cookie cannot be replayed as the Bearer key);
constant-time comparison (fixed 32-byte digests, no length leak, no throw); CORS
/ CSRF posture (`Allow-Credentials` deliberately never set, so credentialed
cross-origin preflights fail and no admin data is exposed; `SameSite=lax` blocks
cross-site cookie'd PATCH; `Vary: Origin` correct; native no-Origin clients
intentionally unaffected); HTML-email XSS (every attacker-controlled field
escaped; the two unescaped interpolations — emoji constant and whitelist-
validated `severity` — are safe); email header injection blocked by
`EMAIL_RE` + the explicit CR/LF check; `isConfirmedDevelopment` hard-denies on
unset/unknown `NODE_ENV`.

**Noted but out of scope** (pre-existing, unchanged by this diff — fold into the
DR-5.2 rate-limit redesign):

- The rate-limit IP is taken from the leftmost, client-**spoofable**
  `x-forwarded-for` value. An attacker can rotate the spoofed IP to bypass the
  limit. When wiring the persistent store, also switch to the platform's trusted
  client-IP header (e.g. Netlify's `x-nf-client-connection-ip`).
- The in-memory report store (`lib/reports.ts`) has no size bound. Bounded/
  persisted storage belongs with the same durability decision as rate-limiting.

---

## 9. For Eric — review & merge

- **Worktree:** `/Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/deep-research-security`
- **Branch:** `deep-research/security` (based on local `5bad7d9a`)
- **Commits:**
  - `c5fd9ac8` fix(support): harden admin auth gate (DR-4.2–4.5)
  - `855e2b6b` fix(support): harden bug-report API — CORS, rate-limit, PII, audit
  - `af09b050` fix(support): reject malformed log entries in bug-report intake (adversarial-review fix)
  - _(+ the commit adding this findings doc)_
- Nothing was merged or pushed. Review with
  `git -C .claude/worktrees/deep-research-security diff 5bad7d9a..HEAD`, then
  merge to your local `main` yourself. The worktree is left on disk for review.

### Diff summary

Commits on `deep-research/security` (base `5bad7d9a`):

```
af09b050 fix(support): reject malformed log entries in bug-report intake
855e2b6b fix(support): harden bug-report API — CORS, rate-limit, PII, audit (DR-4.6–4.7, DR-5.1–5.4)
c5fd9ac8 fix(support): harden admin auth gate (DR-4.2–4.5)
```

`git diff 5bad7d9a..HEAD --stat -- websites/apps/support`:

```
 websites/apps/support/src/app/admin/auth/route.ts  |  20 ++--
 websites/apps/support/src/app/admin/layout.tsx     |  26 ++---
 .../apps/support/src/app/api/bug-report/route.ts   | 117 ++++++++++++++++-----
 .../support/src/app/api/bug-reports/[id]/route.ts  |  39 ++++---
 .../src/app/api/bug-reports/metrics/route.ts       |  13 +--
 .../apps/support/src/app/api/bug-reports/route.ts  |  13 +--
 websites/apps/support/src/lib/audit.ts             |  46 ++++++++
 websites/apps/support/src/lib/auth.ts              | 102 ++++++++++++++----
 websites/apps/support/src/lib/cors.ts              |  60 +++++++++++
 9 files changed, 336 insertions(+), 100 deletions(-)
```

_(This findings doc is added in a separate commit on the same branch.)_
