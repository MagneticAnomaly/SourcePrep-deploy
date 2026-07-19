# Deep-Research Handoff — Session B: Security engineering (DR-4, DR-5)

> **Self-contained starter prompt** for a dedicated follow-up AI session.
> Part of the 2026-07-19 legal+security+message audit follow-up. Full audit
> context: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`.
>
> You are one of four parallel deep-research sessions (A=legal, B=security
> engineering, C=SBOM scan, D=codrag.key history). You do NOT need to wait on
> the others.

## What this session is

**Security engineering — code mutation.** You WILL edit files in
`websites/apps/support/src/`. This is the ONLY session that mutates code.
You implement the **immediate license-neutral security mitigations** that do
NOT need Eric's sign-off, and you **design + document** (not decide) the
parts that DO need his sign-off. Worktree-isolated; review-gated; no merge,
no push.

## Hard rules

- **Worktree-isolated.** BEFORE any edit, create a worktree with the
  `EnterWorktree` tool (name: `deep-research-security`). Work entirely inside
  it. (If your client has no `EnterWorktree` tool, instead
  `git worktree add ../deep-research-security -b deep-research/security` and
  `cd` there. Equivalent.) This sandboxes your edits from concurrent sessions
  on main.
- **Read-only on git history.** No `git checkout` of files you didn't create,
  no `git stash pop`, no `git reset`. Use the mutate-via-tmp-backup pattern if
  you need to compare. (Prior incidents: verifier subagents clobbered a
  shared stash via `git checkout` — do not repeat.)
- **Commit per logical unit, ON THE WORKTREE BRANCH.** Never push. No
  Co-Authored-By. Never `git commit --amend` (concurrent sessions collide).
- **License-neutral.** No legal act, no privacy-policy publication, no
  assertion of a specific OSS license in new copy.
- **NO attorney budget / Eric-decision boundary:** implement only the
  mitigations explicitly marked "license-neutral, no Eric sign-off" below.
  The auth-provider choice, the Resend subprocessor disclosure TEXT, and any
  privacy-policy notice are **design-only** — present options, don't decide.
- **Don't trust memory/notes for code claims** — verify against the repo.
- **SourcePrep = brand; prep = code.** No CoDRAG/RunPrep in copy.
- **No image input** (model crashes on PNG Read). Verify text-only.
- **prep MCP:** call `prep` (no args) first; project_id is in
  `.sourceprep/AGENT_CONTEXT.md`. Use `prep_impact` BEFORE editing hub files
  to see the blast radius. Use `prep_search` to find every caller of
  `isAuthorized` / `isAuthorizedServer`.
- **Dogfooding:** note unhelpful/wrong prep results as product feedback.

## Items

### DR-4. Support admin auth security hardening

**Context:** `websites/apps/support/src/lib/auth.ts` is the admin gate. The
audit found: raw `ADMIN_TOKEN` stored in a cookie; `?token=` query-param
path (token leaks via Referer to third-party assets); three `===` string
compares (timing-attack); a dev-fallback that authorizes when
`NODE_ENV !== 'production'` AND `ADMIN_TOKEN` is unset. Admin routes expose
PII (emails, license_tier, project_id, logs).

**DO NOW (license-neutral, no Eric sign-off):**
1. **Inventory EVERY caller** of `isAuthorized` / `isAuthorizedServer` across
   `websites/apps/support/src` (use `prep_search` + grep). Produce a table:
   caller → route → what PII it exposes. This is your map.
2. **Remove the `?token=` query-param path** — cookie + Authorization header
   only. (Token in a URL leaks via Referer/logs.)
3. **Swap all three `===` compares to `crypto.timingSafeEqual`** (constant
   time). Watch the Buffer length-equality precondition.
4. **Change the dev-fallback** (`auth.ts:22,43`) to **hard-deny** when
   `NODE_ENV` cannot be confirmed production (do not auto-authorize).
5. **Replace the raw-token cookie** with an **opaque session id** keyed
   server-side to a hash of `ADMIN_TOKEN` (never store the raw token in the
   cookie).
6. **Add an audit-log row** for every `PATCH /api/bug-reports/:id` mutation:
   actor (hashed token), report id, field changes, timestamp.
7. **Remove** `route.ts:229` `console.log` of `reporter.email` (PII to
   function logs). Grep all support routes for `console.log` of email /
   PII and remove.
8. **Confirm** `RESEND_API_KEY` / `BUG_REPORT_EMAIL` / `ADMIN_TOKEN` env vars
   are server-only (no `NEXT_PUBLIC_` prefix; not client-bundled). Report any
   leak.

**DESIGN ONLY (present options, do NOT decide):**
- The auth-provider replacement — evaluate **NextAuth vs Clerk vs rolled-own
  opaque-session** (you're already implementing rolled-own opaque-session in
  step 5; document whether NextAuth/Clerk is worth migrating to and why).
  Surface as ED-adjacent: which provider, and is the support site already
  publicly reachable?

### DR-5. Bug-report endpoint CORS + rate-limit + Resend subprocessor

**Context:** `websites/apps/support/src/app/api/bug-report/route.ts:178-182`
sets `Access-Control-Allow-Origin: '*'` (wildcard) on an unauthenticated PII-
intake endpoint; `rateLimitMap` at `route.ts:40-55` is in-memory (resets on
cold start); the route emails via Resend (a subprocessor not disclosed
anywhere).

**DO NOW (license-neutral, no Eric sign-off):**
1. **Enumerate the full allowed-origin list** (sourceprep.io, www.,
   support., docs., marketing., payments., plus the desktop app's custom
   origin scheme if it POSTs directly — check `tauri.conf.json` CSP + any
   `fetch` calls in `src/prep/dashboard`). **Replace `'*'` with the
   allowlist.**
2. **Wire a persistent serverless store** (Netlify Blobs or Upstash Redis)
   to replace the in-memory `rateLimitMap`. Pick the lighter one that fits
   the existing deploy (check `websites/apps/support/netlify.toml` for
   already-configured integrations). If neither is set up, document the
   choice as ED-adjacent and leave the in-memory map with a clear `TODO`
   comment + a flag in your output doc — do NOT ship a broken persistent
   store.
3. **Audit env vars** (cross-ref DR-4.8).
4. **Harden the PII path:** ensure bug-report fields are validated, the
   email body does not echo arbitrary user input unsanitized into logs.

**DESIGN ONLY (frame for Eric):**
- The **Resend subprocessor disclosure** is a privacy-law compliance item
  (GDPR Art 28 / CCPA). Eric must approve the privacy-policy/notice text
  naming Resend. **Draft** the one-line disclosure text (cross-ref Session
  A's ED-3 work if available; otherwise draft independently) and surface as
  an Eric-decision. Do NOT publish it.

**GATE:** the public mirror (`tools/build_public_mirror.py` allowlist +
denylist) is the gate before this endpoint ships publicly — confirm the
support site's deploy status (`deploy-support` job is commented out in
`deploy-websites.yml:160`; check whether the site is live via manual Netlify
deploy). **If the support site is already publicly reachable, escalate
urgency in your output doc.**

## What to PRODUCE

1. **The code changes** — committed on the worktree branch, per logical unit
   (one commit per DR-4 / DR-5, or finer). Each commit message:
   `fix(support): <what>` — no Co-Authored-By, no push.
2. **A findings doc** at
   **`docs/Phase142_OSS-First/DEEP_RESEARCH_B_SECURITY_FINDINGS.md`** (in the
   worktree, committed):
   - The isAuthorized caller → PII matrix (DR-4.1).
   - What you changed (DR-4.2-7, DR-5.1-2,4) with file:line.
   - What you did NOT change and why (the Eric-decision parts: auth provider,
     Resend disclosure text, persistent-store if not wired).
   - The support-site deploy-status finding + urgency flag.
   - `prep_impact` blast-radius notes for any hub file you touched.
3. **A diff summary** — `git diff main...deep-research/security --stat` +
   the commit list, pasted into the findings doc.

## STOP and surface to Eric when

- All DO-NOW mitigations are committed on the worktree branch + typecheck
  clean (`npm --prefix websites/apps/support run typecheck`).
- The findings doc is written with the framed Eric-decisions (auth provider,
  Resend disclosure, persistent-store, deploy urgency).
- You have NOT merged to main, NOT pushed, NOT exited the worktree (leave it
  for Eric to review: `EnterWorktree` `action: keep`, or just leave the
  `../deep-research-security` worktree on disk). Surface the worktree path +
  branch name + commit list so Eric can review/merge.

## After Eric reviews

Eric will either merge the branch to main himself or request changes. Do
not merge unprompted.