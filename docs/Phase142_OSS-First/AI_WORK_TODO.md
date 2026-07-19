# AI-Executable OSS-Transition Work — TODO

> **Status:** DRAFT 2026-07-19. Derived from the 2026-07-19 deep audit
> (`project_oss_audit_2026-07-19` memory; full report in the workflow transcript).
> PRIVATE — Phase 143 keep-private bucket. This is the *AI-executable* subset of
> the OSS transition. Every item here can be done by an AI agent **without Eric's
> personal decisions**, subject to the guardrails below. Eric-only items (LLC
> status, Lemon Squeezy count, signing the IP Assignment, USPTO filing, patent
> provisional, codrag.key offline rotation, the public push) are listed in §0 but
> NOT worked here.
>
> **Traceability:** IDs match `DECISION_MEMO_2026-07-17.md` Part 2 backlog
> (A/B/C/D) + `IMPLEMENTATION_PLAN.md` Parts A–H + the audit's B1–B18 false-claim
> + C1–C12 contradiction IDs. Read this alongside `LICENSING_RECOMMENDATION.md`,
> `REPO_TOPOLOGY.md`, and `DOCS_OSS_READINESS_AUDIT_2026-07-18.md`.

---

## §0 — Guardrails (read before touching anything)

**Hard rules — violating any one is a bug:**

1. **Commit locally only. Never push.** No `git push`, no `git push --force`, no
   `git filter-repo`. **Deploy gating is already in place** — all 4 Netlify
   configs (`websites/apps/{marketing,docs,payments,support}/netlify.toml`) gate
   on the tip commit's `[deploy]` flag (`ignore = '! git log -1 --pretty=%B |
   grep -qF "[deploy]"'`) and `.github/workflows/deploy-websites.yml:43-56`
   runs a `deploy-gate` job that checks the same flag. **A push does NOT deploy
   unless the tip commit message contains `[deploy]`.** Per
   `feedback_deploy_flag_gating` / `feedback_explicit_push_only`, the push
   itself is still Eric's call — do not push. The local tree is currently **3
   commits ahead** of `origin/main`: `a6ad1c7f` (docs-site pass, deploy-relevant,
   typecheck-verified), `31e8d210` + `f7cf743f` (private Phase142 docs, no deploy
   surface). Leave them ahead.
   - **Pre-push gate-verification checklist (run before ANY push):** (a) all 4
     `netlify.toml` still contain the `ignore = '... [deploy] ...'` line; (b)
     `deploy-websites.yml` still contains the `deploy-gate` job. If either is
     missing/altered, STOP and surface to Eric.
   - **How the gate works:** it reads ONLY the tip commit's message
     (`github.event.head_commit.message`); the deployed tree is the tip's
     checkout; intermediate commits never deploy individually. If pushing N
     commits, put `[deploy]` only on the final tip — and only when that tip is a
     coherent, deployable state. Never put `[deploy]` on a half-done tip.
2. **No Netlify deploy.** Edits to `websites/apps/{marketing,docs,payments,support}/`
   deploy on push. Since we don't push, they don't deploy — but stage them so
   that when Eric does deploy, the changes ship as one coherent batch. Do **not**
   flip `IS_BETA_MODE` to false (`beta.ts:19` defaults true; the post-beta deploy
   must set `NEXT_PUBLIC_BETA_MODE=false` explicitly — that is Eric's deploy-time
   call, not ours).
3. **No git state mutation.** Never `git checkout`, `git stash`, `git stash pop`,
   or `git filter-repo` (a shared stash exists across worktrees and has been
   corrupted by verifier agents before — `feedback_scrutiny_verifiers_read_only`,
   `feedback_scrutiny_worktree_isolation`). Use read-only git commands
   (`git show`, `git log`, `git grep`, `git ls-files`) for inspection only.
4. **No signing, no filing, no irrevocable act.** Do not sign the IP Assignment
   (Eric signs both sides), do not file with USPTO/BIS/court, do not file a
   patent provisional, do not rotate keys on a remote, do not run the public
   mirror push. Drafts only.
5. **No hero edits.** The marketing home-page hero/tagline is off-limits for
   autonomous edits (`feedback_do_not_touch_hero`). Flag suggestions (e.g. B16
   "MAC/WIN/LINUX" Linux overstatement) in this doc; do not edit.
6. **Use the project venv.** `.venv/bin/python` and `.venv/bin/pytest`, never
   system python. `codrag`/`prep` is the project itself, not a pip dependency
   (`feedback_no_pip_install`, `feedback_use_venv`).
7. **Restart the daemon before live validation.** `prep serve` has no
   hot-reload; stale in-memory code silently passes validation against old
   behavior (`feedback_restart_daemon_before_live_validation`). SQLite is
   DELETE-mode on this USB drive (`feedback_sqlite_wal_usb`).
8. **Brand split.** `SourcePrep` = user-facing brand (UI, marketing,
   sourceprep.io, `.sourceprep/`); `prep` = code-level (CLI, imports, MCP tools,
   `@prep/*`, `PREP_*`). "CoDRAG"/"RunPrep" are stale codenames — never
   user-facing; remove from any public-bound surface (`feedback_codrag_is_stale_codename`).
9. **No `Co-Authored-By` trailer** in commits (`feedback_no_coauthored_by`).
10. **Commit per logical unit** as we work (`feedback_commit_as_we_work`); push
    policy is unchanged (no push).

**Eric-only critical path (do NOT work these — surface to Eric):**

| Gate | Why Eric-only |
|---|---|
| A6 LLC status (op agreement, EIN, bank) | Legal entity action |
| A5 Lemon Squeezy customer count | Login + business decision; gates any "now open source" announcement |
| B3 Sign the IP Assignment | Legal signature (both sides = Eric) |
| C5-commit The actual root LICENSE swap commit | Sequenced after B3; AI may **stage** the Apache text but Eric confirms B3 done before commit |
| C6 codrag.key offline rotation | Offline Tauri keygen by Eric; update `tauri.conf.json:66` pubkey |
| A3/D3/D9 Patent prior-art verdict + provisional | Irreversible; Eric's call after AI's prior-art search |
| B1/B2 USPTO federal search + 1(b) filing | External filing |
| B5 Public mirror push | One-shot, irreversible |
| §12 runway / §1 personal brand | Eric's private state + external surfaces |

---

## §1 — Work streams (sequenced; do top-down where dependencies exist)

Dependencies recap (from audit §4): `A6 → D7(draft) → B3(sign) → C5+ C4 + D2 + C8/D8 → C9 → A3/D9 → C6 → C1/C1b/C1c → C2 + D12 → B5`. AI can start on **everything that is not B3/C5-commit/C6/A3/A5/A6/B1/B2/B5** in parallel, with the staging caveats noted per item.

### Stream 1 — Legal drafts (no filing; Eric signs/files)

#### 1.1 — D7 Draft IP Assignment agreement  *(BLOCKING for Stream 2)*
- **Do:** Draft `docs/Phase144_LegalPreLaunch/IP_ASSIGNMENT_DRAFT.md` from the
  Cooley GO / YC CIIAA / Stripe Atlas 9-element checklist in
  `docs/Phase144_LegalPreLaunch/RESEARCH.md` §3.2. Eric individual → Magnetic
  Anomaly LLC, backdated to LLC formation. Mark DRAFT — Eric signs (B3).
  Use `[PLACEHOLDER: Eric to confirm]` for the governing-law state and any
  pre-existing-license/assignment carve-outs.
- **Files:** new `docs/Phase144_LegalPreLaunch/IP_ASSIGNMENT_DRAFT.md`.
- **Acceptance:** 9 elements present; DRAFT watermark; references the checklist
  source; does not assert execution; placeholders for governing-law state +
  carve-outs present (filled by Eric before B3).
- **Deps:** A6 (LLC status) + Eric supplies state-of-residence + carve-outs
  (BOTH — AI drafts the template, Eric fills placeholders). **Eric-gate before
  effect:** B3 sign. **Deploy/push risk:** none (private doc).

#### 1.2 — D8 Draft Phase-1 ToS / Privacy / EULA + governance set
- **Do:** Author `CONTRIBUTING.md` (DCO sign-off section + "single maintainer,
  response times vary, discuss architectural PRs in an issue first" honesty
  block per SCRUTINY §7), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1),
  `CHARTER.md` (anti-rug-pull commitment — **scoped to the engine/OSS surface:
  "the SourcePrep engine's OSS surface stays Apache-2.0 in perpetuity; no
  source-available/BSL/SSPL flip"**; explicitly carve out the hosted
  Teams/Enterprise backend as a separate proprietary codebase NOT bound by this
  commitment — broadening to "SourcePrep stays Apache-2.0" would foreclose
  LICENSING_RECOMMENDATION #2; see §5 Research note on DCO nuance), root
  `SECURITY.md` (security@sourceprep.io, 5-bus-day SLA, GPG fingerprint,
  coordinated disclosure 90-day — **GPG fingerprint uses
  `{{GPG_FINGERPRINT_PLACEHOLDER}}`; the `security@sourceprep.io` inbox +
  fingerprint + SLA are Eric's to provision/confirm, not AI's to author**).
  Draft Phase-1 ToS, Privacy, EULA under `docs/Phase144_LegalPreLaunch/`.
  **Skip ICLA/CCLA — decision is DCO, not CLA** (C3 contradiction). Add a DCO-check
  GitHub Action (`.github/workflows/dco.yml`).
- **Acceptance:** files exist + tracked; SECURITY.md linked from README (when
  README is written); ToS does NOT forbid reverse-engineering/redistribution
  (audit B — terms/page.tsx:85,100,121,127,219 currently asserts Apache in
  present tense; the draft ToS must not repeat a present-tense Apache claim
  before C5).
- **Deps:** none to DRAFT. **Publish requires D8 legal-trigger review** (attorney
  or Eric-as-principal) of ToS/Privacy/EULA before they go live. **Deploy/push
  risk:** none (private/governance files, no deploy).
- **Files:** `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHARTER.md`, `SECURITY.md`
  (root); `docs/Phase144_LegalPreLaunch/{TOS,PRIVACY,EULA}_DRAFT.md`;
  `.github/workflows/dco.yml`.
- **Acceptance:** files exist + tracked; SECURITY.md linked from README (when
  README is written); ToS does NOT forbid reverse-engineering/redistribution
  (audit B — terms/page.tsx:85,100,121,127,219 currently asserts Apache in
  present tense; the draft ToS must not repeat a present-tense Apache claim
  before C5).
- **Deps:** none. **Deploy/push risk:** none (private/governance files, no
  deploy).

#### 1.3 — D3 Export-control self-classification memo
- **Do:** Draft `docs/Phase144_LegalPreLaunch/EXPORT_CLASSIFICATION.md`: Ed25519
  = authentication/digital-signature only → outside ECCN 5D002 (§772.1
  excludes authentication/signature) → EAR99; standard published crypto (RFC
  8032 etc.) → no §742.15(b) notification; §740.13(e) "[Reserved]". One page.
  Add a short EXPORT note to the (future) public README.
- **Files:** new `docs/Phase144_LegalPreLaunch/EXPORT_CLASSIFICATION.md`.
- **Acceptance:** cites §772.1, §742.15(b), §740.13(e)-Reserved; dated.
- **Deps:** none. **Deploy/push risk:** none.

#### 1.4 — D9 Prior-art search for AIMD-for-LLMs (feeds A3, Eric's patent call)
- **Do:** Research whether an AIMD/latency-aware adaptive concurrency limiter
  applied specifically to LLM-API request parallelism is anticipated by prior
  art (TCP AIMD/Vegas literature, existing OSS adaptive-concurrency-limiter
  libs, rate-limiter patents). Note existing
  `docs/Phase116_strategic-oversight/01_PRIOR_ART.md` is LLM-agent architecture
  prior art, NOT the AIMD-for-LLMs search — do not conflate. Report novelty
  verdict to Eric for A3.
- **Files:** new `docs/Phase144_LegalPreLaunch/PRIOR_ART_AIMD_FOR_LLMs.md`.
- **Acceptance:** verdict (novel / anticipated / mixed) + cited sources; no
  legal advice claim.
- **Deps:** none. **Critical:** A3 patent decision is Eric's and must be
  recorded in writing BEFORE B5 (public commit forfeits EU patent rights
  — absolute novelty, zero grace). Add "A3 patent decision recorded" as an
  explicit red/green gate on the B5 checklist (audit OVERLOOKED #1).

### Stream 2 — License application (stage; commit atomically with C5 after B3)

> **Sequencing trap (audit-overlooked, flag for scrutiny):** Flipping metadata
> (C4) to Apache-2.0 **before** swapping the root LICENSE (C5) creates a *new*
> three-way inconsistency in the opposite direction — `pyproject.toml` would
> claim Apache while root LICENSE is still proprietary. The audit said C4 is
> "not B3-gated since MIT is also false against today's proprietary LICENSE" —
> that's about whether you may fix it, not about whether the intermediate state
> is a new false claim. **AI stages C4/C5/D2 now; the commits land together in
> one commit after Eric confirms B3 signed.** Until then, metadata stays MIT
> (also false, but not *newly* false in a worse direction). Draft everything;
> commit nothing in this stream until the B3 gate.

#### 2.1 — C5 Stage root LICENSE swap to verbatim Apache-2.0
- **Do:** Replace `LICENSE` with verbatim Apache-2.0 text, Copyright
  `(c) 2026 Magnetic Anomaly LLC`. **Stage the file content now; do not commit
  until Eric confirms B3 signed.**
- **Files:** `LICENSE`.
- **Acceptance:** verbatim Apache-2.0; correct copyright line; no other edits.
- **Deps:** B3 (Eric sign) before commit. **Deploy/push risk:** committing
  LICENSE alone (without metadata) would leave pyproject=MIT, LICENSE=Apache —
  still inconsistent. Commit with 2.2 + 2.3 atomically.

#### 2.2 — C4 Stage license-metadata flip to Apache-2.0
- **Do:** `pyproject.toml:10` (`license = "Apache-2.0"`) + `:22` classifier;
  `engine/Cargo.toml:16` workspace → Apache-2.0; add `license.workspace = true`
  to `engine/crates/prep-selfheal/Cargo.toml` (audit B3, missing field);
  reconcile the 10 npm `package.json` files lacking a license field (root,
  `packages/vscode/webview-ui`, `src/prep/dashboard`, `src/prep/mcp_local_rag`,
  `websites/apps/{docs,marketing,payments,support}`, `websites/MagneticAnomaly`,
  `docs/Phase13_Storybook/theme-examples/tremor-preview`) to Apache-2.0; flip
  `packages/ui/package.json:95` and `packages/paperclip-plugin-prep/package.json:5`
  from `"MIT"` to Apache-2.0; fix `packages/vscode/package.json`
  `"SEE LICENSE IN LICENSE"` (currently points at proprietary root) to
  Apache-2.0. Fix the stale `@codrag/ui` lockfile reference
  (`packages/ui/package-lock.json` — package.json is `@prep/ui`; re-resolve).
- **Files:** `pyproject.toml`, `engine/Cargo.toml`, 7 `engine/crates/*/Cargo.toml`,
  ~12 `package.json`, `packages/ui/package-lock.json`.
- **Acceptance:** `pip-licenses`, `license-checker` (full monorepo run), and
  `cargo` metadata agree on Apache-2.0; no remaining `MIT` license field on a
  package whose outbound license is the root.
- **Deps:** commit atomically with 2.1 + 2.3 after B3. **Stage now.**

#### 2.3 — D2 Promote NOTICE.draft.md → root NOTICE
- **Do:** Copy `docs/Phase142_OSS-First/NOTICE.draft.md` → root `NOTICE`,
  finalized for Apache-2.0 (§4(d) attribution). Fold in scancode results from
  3.1 when available.
- **Files:** new `NOTICE` (root).
- **Acceptance:** NOTICE lists nomic-embed-text-v1.5 (Apache-2.0), tree-sitter
  grammars (MIT), pathspec (MPL-2.0), Tremor (Apache-2.0), and every other
  third-party component from `LICENSE-AUDIT.md`; copyright line matches LICENSE.
- **Deps:** commit atomically with 2.1 + 2.2 after B3. **Stage now.**

### Stream 3 — License-audit hardening (pre-push gate; do now)

#### 3.1 — C9 Run scancode-toolkit repo-wide source-license scan
- **Do:** `pipx install scancode-toolkit` (~1GB), then
  `scancode -clpeu --json-pp docs/Phase142_OSS-First/scancode-out.json
  src/ packages/ engine/ websites/ scripts/`. Inspect every flagged file for
  GPL/CC-BY-SA copy-paste or LLM-generated matches. Update `LICENSE-AUDIT.md`
  with the result; fold confirmed attributions into NOTICE (2.3). Add a
  CI license-check gate (`.github/workflows/license-check.yml`) running
  `pip-licenses --fail-on=GPL; license-checker --failOn 'GPL'; cargo deny check
  licenses` (install `cargo-deny` if missing) per SCRUTINY §8.
- **Files:** `docs/Phase142_OSS-First/scancode-out.json`,
  `docs/Phase142_OSS-First/LICENSE-AUDIT.md` (update),
  `.github/workflows/license-check.yml`.
- **Acceptance:** scancode run complete (closes LICENSE-AUDIT "open gap"); zero
  GPL/AGPL/LGPL in source; CI gate green on a fresh clone with no secrets.
- **Deps:** none (do now). This is a **hard pre-push blocker** (audit §4 gate 9).
- **Deploy/push risk:** none (private audit output + workflow file).

### Stream 4 — License crypto + secret rotation (AI engineers; C6 keygen is Eric)

#### 4.1 — C1 / C1b / C1c Ed25519 license-crypto fix  *(needs Eric approval of the change plan)*
- **Do:** Execute
  `docs/Phase146_SecurityAudit/CHANGE_PLAN_ed25519_crypto_fix.md` (currently
  PROPOSED — get Eric's approval first): generate a real random keypair,
  replace `DEFAULT_PUBLIC_KEY_HEX` in `src/prep/core/licensing.py:22` (currently
  the all-zeros-seed Ed25519 key — forgeable; audit reproduced a
  `{tier:enterprise, seats:999}` token accepted by `verify_license_key()`),
  remove `DEFAULT_PRIV_KEY_HEX` from `scripts/generate_license.py:33` (which
  derives to a *different* pubkey `928764b6…` ≠ the shipped verifier — the
  generator↔verifier pair is already broken), implement `PREP_LICENSE_PUBLIC_KEY`
  env read (currently comment-only — no `os.environ` anywhere), fail-closed on
  unsigned paid licenses (currently `feature_gate.py:218-224` warns then honors
  the declared tier), add tests with an in-memory dev keypair.
- **Files:** `src/prep/core/licensing.py`, `src/prep/core/feature_gate.py`,
  `scripts/generate_license.py`, tests.
- **Acceptance:** forge attempt rejected; unsigned paid license → FREE or
  rejected (not warn-and-accept); generator and verifier share one keypair;
  `PREP_LICENSE_PUBLIC_KEY` env override works; tests green
  (`.venv/bin/pytest`); restart daemon before live validation.
- **Deps:** Eric approves the change plan. Until applied, **Pro is not
  sellable**. **Deploy/push risk:** none (backend code, no deploy).

#### 4.2 — C6 codrag.key untrack + .gitignore (rotation is Eric)
- **Do:** Untrack `src/prep/dashboard/src-tauri/.tauri/codrag.key` (currently
  tracked + on `origin/main`); add `.tauri/*.key` to `.gitignore`. **Eric's
  offline steps (NOT ours):** generate a new Tauri-updater keypair offline,
  update `tauri.conf.json:66` pubkey (`dW50cnVzdGVk…C43F6BF18AEA1FE0`),
  publish the new public key. Note: the committed key is passphrase-encrypted
  (rsign/minisign), so exposure alone is not immediate compromise — but
  committed signing keys must be rotated regardless.
- **Files:** `.gitignore`, `git rm --cached` the key (local only, no push).
- **Acceptance:** key untracked; `.gitignore` covers `.tauri/*.key`; hand-off
  note to Eric with the exact Tauri keygen command + `tauri.conf.json` update.
- **Deps:** untrack is AI; rotation is Eric. **Push risk:** the key is already
  on origin — untracking locally does not remove it from history; the
  fresh-initial-commit public mirror (Stream 7, C2) is what actually scrubs it.
  Do **not** run `git filter-repo` (guardrail 3).

### Stream 5 — Internal plan reconciliation (docs; do now, private)

> All edits in this stream are to private Phase142 docs (no deploy). Reconcile
> the 12 contradictions (audit §3 C1–C12) so the plan stops arguing with itself.

#### 5.1 — C1 Pro tier: "deferred" → "KEEP $29 one-time (not live at Phase 1)"
- **Edit:** `README.md:5,62-63`; check `:77` "Tier boundaries locked"; annotate
  `DECISION_MEMO Part 1 §D2:40` as SUPERSEDED by Part 0 D2; sweep the 6 other
  docs that carry "deferred" (DECISION_MEMO:75,81,94; STRATEGY:25;
  AUDIT_2026-07-17.md:101; HANDOFF_PROMPT:163).
- **Deps:** none.

#### 5.2 — C2 90-day → 12-month success window
- **Edit:** `README.md:127,134`; `SCRUTINY.md:11`; `IMPLEMENTATION_PLAN.md:362`.
  (Verifier confirmed STRATEGY.md has NO 90-day assertion — do not edit it.)
- **Deps:** none.

#### 5.3 — C3 CLA → DCO across stale docs
- **Edit:** `DECISION_MEMO Part 1 §D1:32,36` + backlog `A1:93` annotate
  SUPERSEDED; `OPEN_CORE_SPLIT.md:10,278,391,436`; `HANDOFF_PROMPT:134`;
  `AUDIT_2026-07-17.md:929` — replace CLA references with DCO. (Verifier
  confirmed OPEN_CORE_SPLIT `:148/187/351` are NOT CLA refs — substring hits
  in "claim"/"SLAs"/"OpenClaw"; leave them.) **All four stale-CLA docs are on
  origin/main** — but we're not pushing; edits land locally.
- **Deps:** none.

#### 5.4 — C4 / OVERLOOKED Reconcile pricing source-of-truth
- **Do:** This is the audit's headline overlooked gap. D10 only says
  "designate OPEN_CORE_SPLIT as SoT, mark the other two SUPERSEDED" — executing
  that as-written would lock the stale $15/$50 as source-of-truth and make the
  marketing/SoT contradiction permanent. **Re-baseline OPEN_CORE_SPLIT.md itself
  to the 2026-07-18 marketing pricing:** Pro $29 one-time perpetual; Teams
  $9/seat/mo + $97/seat/yr; Enterprise $24/seat/mo + 15-seat min + tiered setup
  fee (remote included, on-site from $3,500, air-gapped quoted). Mark
  `PRODUCT_AND_BUSINESS_OVERVIEW.md` and `DISTRIBUTION_AND_REVENUE_PLAN.md`
  pricing sections SUPERSEDED. Delete the phantom $49 Founder's Edition +
  $30/yr renewal (`PRODUCT_AND_BUSINESS_OVERVIEW.md:251,253`).
- **Files:** `docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md`,
  `docs/PRODUCT_AND_BUSINESS_OVERVIEW.md`, `docs/DISTRIBUTION_AND_REVENUE_PLAN.md`.
- **Acceptance:** one canonical price ladder ($0 / $29 / $9 / $24) across all
  three docs; OPEN_CORE_SPLIT marked SoT; phantom SKUs deleted.
- **Deps:** none. **Deploy/push risk:** none (private docs).

#### 5.5 — C6 Copyright holder checkbox (already decided)
- **Edit:** `IMPLEMENTATION_PLAN.md:81` — check the box, replace "Decide:
  Magnetic Anomaly LLC vs personal" with "Apply: Magnetic Anomaly LLC (decided
  Part 0 D8 / LICENSING_RECOMMENDATION.md:53-55 / NOTICE.draft.md:12)".

#### 5.6 — C7 sourceprep org → MagneticAnomaly
- **Edit:** `STRATEGY.md:179-181`; `IMPLEMENTATION_PLAN.md:40,89,90`;
  `SCRUTINY.md:194-196` — repoint to REPO_TOPOLOGY (stay under MagneticAnomaly;
  do not stand up a separate sourceprep org). (Verifier confirmed README scope
  does NOT mention the org — do not edit README for this.)

#### 5.7 — C9 AGPL-fallback → revenue-fallback
- **Edit:** `STRATEGY.md:25,51-53`; `README.md:8,135` — the Path B fallback is
  now "build the hosted Teams/Enterprise backend" (revenue fallback without
  relicense), since the AGPL-flip is foreclosed by the permanent Apache-2.0 +
  DCO decision. Fix `README.md:134` broken cross-ref ("SCRUTINY §'What if no one
  cares'" — no such section exists; repoint to the actual SCRUTINY fallback
  section).

#### 5.8 — C8 Trademark blocker-status reconciliation
- **Edit:** `DECISION_MEMO Part 0 D5:19` — tighten to "not a *decision* blocker;
  the B1/B2 filing actions remain pre-Show-HN execution tasks." Check the
  SCRUTINY §9 decision-made boxes; point them at B1/B2.

#### 5.9 — C10 LICENSING_RECOMMENDATION gap (a) closed
- **Edit:** `DECISION_MEMO Part 0 D1:22` — mark gap (a) CLOSED with commit
  `a92d69e1` (LICENSING_RECOMMENDATION.md IS committed). The
  self-contradiction was introduced in the very commit that authored the file.

#### 5.10 — C11 README index + status block refresh
- **Do:** Refresh `README.md` "Files in this phase" table (currently lists 6
  files; the phase has 14+). Refresh the status checkboxes (currently all
  unchecked despite 5+ hardened decisions + marketing/docs execution in
  flight). Produce a SCRUTINY §1–§20 disposition appendix (act now / defer /
  accept risk per section).

### Stream 6 — Public-surface artifact alignment + remaining-claim sweep (deploy-gated; stage locally)

> **Reframed 2026-07-19 per Eric:** "we are open source now" — the Apache-2.0
> relicense is **effective**, so the present-tense "free and open source under
> Apache 2.0" marketing copy is **correct, not a false claim**. Do NOT reword
> to future tense. The only license-side work is **artifact alignment** in
> Stream 2 (swap root `LICENSE` to Apache-2.0 + flip MIT metadata to Apache),
> which makes the repo artifacts match the already-effective license. The
> items below that remain are **non-license claims** (phone-home posture,
> stale pricing, tier gating, dead repo slugs) — verify each against current
> code, don't blanket-rewrite.

#### 6.1 — B1 Marketing Apache-2.0 claim — NO EDIT (correct as-is)
- **Status:** **VOID 2026-07-19.** The present-tense "open source under
  Apache 2.0" claim on ~14 marketing pages is **correct** — the relicense is
  effective. Leave all pages as-is. The only follow-up is Stream 2 (root
  `LICENSE` swap + metadata flips) so the repo artifacts match. No future-
  tense rewording; no marketing edits. (The earlier "path (a) future tense
  vs path (b) swap LICENSE" framing assumed the claim was false — it isn't.)

#### 6.2 — B6 FAQ "single HTTPS call" → disclose 7-day revalidation
- **Do:** `faq/page.tsx:276` — either make the claim true (depends on Ed25519
  fix 4.1 landing) or correct to disclose 7-day revalidation + 30-day grace
  (`lemon_squeezy.py:43-44`). Align with the security page hedge.

#### 6.3 — B7 Payments page rewrite
- **Do:** `websites/apps/payments/src/app/page.tsx` — rewrite to marketing
  restructure pricing ($29 / $9 / $24), drop "no recurring phone-home" until
  true, gate "Get Pro"/"Start Team" CTAs behind `IS_BETA_MODE` like
  marketing/pricing does (currently ungated — buyable against an unwired
  checkout; `recover/route.ts:14` is a mock).

#### 6.4 — B8 TierComparison component rewrite
- **Do:** `packages/ui/src/components/marketing/TierComparison.tsx` — rewrite to
  OSS-all-capabilities + $29-convenience. Currently: $79/$7-mo Pro, Free=1
  project, "Structural Code Graph free:false", "Real-time file watcher
  free:false", "Get Pro" CTA. Exported via `@prep/ui` (`index.ts:230`) — latent
  landmine for every consumer. Alternatively delete it if no consumer needs
  it (check call sites first).

#### 6.5 — B9 VS Code marketplace README rewrite
- **Do:** `packages/vscode/README.md:20,28,54,55,57` — rewrite License/Tiers
  section to the OSS story; scope "Offline Capable" to the OSS build; drop
  "Free Tier: 3 active projects", "Pro Tier: Unlimited", "Upgrade to Pro to
  unlock advanced features", "## Trace Index (Pro)" (`feature_gate.py:54-55`
  sets trace_index = Tier.FREE, not Pro).

#### 6.6 — B10 Docs enterprise-deploy "Offline licensing Available" → Roadmap
- **Do:** `docs/.../enterprise-deploy/page.tsx:252,275,285,287` — mark
  "Air-gapped deployment" + "Offline licensing" as Roadmap (not Available)
  until Ed25519 offline files ship (4.1). Remove "Ed25519-signed license
  files, no phone-home after activation" present-tense claim.

#### 6.7 — B11 Docs installation page — license-honest line
- **Do:** `getting-started/installation/page.tsx:80-86` (local a6ad1c7f) —
  "free to use… build from source. See the repository LICENSE" points at a
  proprietary LICENSE. Either (with 6.1 path a) reword to "will be free and
  open source under Apache 2.0 at public launch" or (path b) wait for C5.
  Note origin/main variant at :80-83 still says "up to 3 active projects"
  (the retired Free-tier limit) — fix in the same edit.

#### 6.8 — B12 About "no phone-home" + B13 CompetitorMatrix "fully offline"
- **Do:** `about/page.tsx:90`, `security/page.tsx:148` — scope "no phone-home"
  to the OSS build. `packages/ui/src/components/marketing/CompetitorMatrix.tsx:112,550`
  — scope "100% locally… work fully offline… zero data transmission" to the
  OSS build.

#### 6.9 — B14 / B15 Dead repo-slug repoint (partial — needs storefront to exist)
- **Do:** Repoint docs `team-sync:191,278,385` + `enterprise-deploy:125,171,190,446`
  (→ `SourcePrep-deploy` empty subtree) and `payments/ClientLayout.tsx:39` +
  `support/ClientLayout.tsx:35` + `support/.../SupportFeatures.tsx:6` +
  `DiscussionList.tsx:24,38` + `dashboard/.../UpdateBanner.tsx:185` (→
  `SourcePrep-MCP` stub) and the 8+ additional surfaces (GETTING_STARTED.md,
  TROUBLESHOOTING.md, DISTRIBUTION_AND_REVENUE_PLAN.md, MASTER_TODO.md,
  HANDOFF.md, scripts/publish_deploy_subtree.sh) to `MagneticAnomaly/SourcePrep`.
  **CAUTION:** the storefront repo doesn't exist yet (REPO_TOPOLOGY creates it
  at publish time). Until it exists, the links 404 either way. Prefer a neutral
  reword ("see the repository on GitHub at launch") until B5 fires, OR accept
  that the storefront URL is the correct target and repoint now (it will resolve
  once Eric creates the repo). Eric's call; flag in the commit message.
- **Deps:** storefront creation is Eric's (B5 sequence). AI edits can land now
  with the understanding that the URL resolves at publish.

#### 6.10 — B16 Hero "MAC/WIN/LINUX" — FLAG ONLY, do not edit
- **Flag:** `packages/ui/src/components/marketing/heroes/yale.tsx:27` overstates
  Linux availability (`download:106` "macOS & Windows"; `pricing:208` "(Linux
  planned)"; `layout.tsx:24` schema.org = macOS, Windows only). **Hero is
  off-limits (guardrail 5).** Surface to Eric for explicit go-ahead.

#### 6.11 — B17 Integrations "Pro-tier" capability claim
- **Do:** `integrations/page.tsx:153` — drop "some advanced graph views are
  Pro-tier." Contradicts `pricing:29-31` "convenience… never capabilities" and
  `feature_gate.py:54-55` (trace_index = FREE).

#### 6.12 — B5 / L1 Docs paperclip "MIT-licensed" → license-neutral
- **Do:** `docs/.../mcp/paperclip/page.tsx:278` — a local-only commit
  (`31e8d210`) already rewords to "see repository LICENSE." Verify it's staged
  (it's unpushed like a6ad1c7f). At relicense, set to the Apache-2.0 line.
  Also fix `packages/paperclip-plugin-prep/README.md:131` (MIT claim) to match.

### Stream 7 — Public-mirror tooling (AI; do now, no push)

#### 7.1 — C2 Build `tools/build_public_mirror.py`
- **Do:** Allowlist-curation + denylist-regex gate that assembles a curated
  public tree from an explicit allowlist, runs a denylist-regex gate that
  **FAILS on any hit** of: `codrag`, `ACQUIRER`, `SCRUTINY`,
  `DISTRIBUTION_AND_REVENUE_PLAN`, `CLAUDE.md`, `.runprep`, `*.key`,
  private-key markers, `AUDIT_2026-07-17`, `HANDOFF_PROMPT`, `RESEARCH_ROUND_2`,
  `DECISION_MEMO`, `LICENSING_DEEP_RESEARCH`, `MARKETING_OSS_READINESS_BRIEFING`,
  `DOCS_OSS_READINESS_AUDIT`, and the codename-leak sources from audit
  OVERLOOKED #5 (`@codrag/ui` lockfile, paperclip tests asserting
  `manifest.id === 'codrag'`, `docs_grounding.py` RunPrep/CoDRAG markers in
  `PREP_SELF_OUTPUT_MARKERS`). Emit a fresh-initial-commit tree per
  `REPO_TOPOLOGY.md`. Dry-run + manifest of included/excluded files.
- **Files:** new `tools/build_public_mirror.py` + `tools/public_mirror_allowlist.txt`.
- **Acceptance:** dry-run on the current tree fails loudly if any denylist hit;
  manifest shows no private/strategic IP in the output tree; no `codrag`,
  `RunPrep`, `.runprep`, `*.key` in the output.
- **Deps:** pairs with 7.2. **Do not push** the mirror output (B5 is Eric's).

#### 7.2 — D12 File-level triage of 1064 markdown docs
- **Do:** Triage every doc under `docs/` into keep-public / keep-private /
  delete (default keep-private when ambiguous, ~5 min/file). Produces the
  allowlist 7.1 consumes. Include the codename-leak surfaces from OVERLOOKED #5.
- **Files:** `tools/public_mirror_allowlist.txt` (output).
- **Acceptance:** every doc classified; allowlist feeds 7.1 dry-run.

### Stream 8 — Code-level codename + path cleanup (AI; no deploy)

#### 8.1 — B18 license.py `~/.runprep` → `~/.sourceprep` (7 sites) — RE-SCOPED
- **⚠️ SCRUTINY CORRECTION (do NOT commit as-written in the original draft):**
  4 of the 7 cited sites are **reads**, not writes. As originally written
  (hard-code `.sourceprep` on all 7), the 4 read endpoints
  (`validate:221`, `deactivate:318`, `seats:365`, `provision-seat:434`) would
  silently miss a legacy `~/.runprep/license.json` — causing a Pro/Enterprise
  **licensing regression**: deactivate silently no-ops (license persists),
  validate returns "No license file," seats reports free while `feature_gate`
  honors Pro, provision-seat raises NO_LICENSE for a licensed Team/Enterprise
  user.
- **Do:** Only the 3 true WRITE sites hard-code `.sourceprep`
  (`activate:189`, `dev-override:517,518`). The 4 READ endpoints MUST call
  `_resolve_license_path()` (the `feature_gate.py:108-128` contract: reads
  `.sourceprep` first, `.runprep` as legacy fallback). **OR** migrate
  `~/.runprep/license.json` → `~/.sourceprep/license.json` on first write.
  Fix the docstring `:13` + user-facing string `:490` ("RunPrep → Settings" →
  "SourcePrep → Settings").
- **Files:** `src/prep/api/routers/license.py`; tests.
- **Acceptance:** new writes go to `~/.sourceprep/license.json`; reads fall
  back to `~/.runprep/license.json` when `.sourceprep` does not exist; test
  patches `Path.home()` to a dir with only `~/.runprep/license.json` and
  asserts deactivate/validate/seats/provision-seat still find it; dev-override
  restore finds a legacy user's real license. Restart daemon before
  validating.
- **Deps:** none (do now, but re-scoped per above). **Deploy/push risk:** none
  (backend code, no deploy), but a silent licensing regression if committed
  as originally drafted.

#### 8.2 — C7 Brand-hygiene sweep (codename surfaces)
- **Progress 2026-07-19:**
  - ✅ **DONE (commit 3d8ef4a7)** — paperclip plugin tests aligned with the
    already-migrated source. Source had `manifest.id='prep'`, `prep:*` tools,
    `'Prep plugin initializing'` logs, zero codrag in `src/`; tests still
    asserted `manifest.id==='codrag'`, `codrag:*` labels, and `'CoDRAG plugin
    init*'` strings → 21/21 tests were failing. Fixed all assertions; vitest
    21 passed.
  - ✅ **VERIFIED — NOT A BUG** — `docs_grounding.py:92,94,96,98`
    `PREP_SELF_OUTPUT_MARKERS` "RunPrep"/"CoDRAG" entries are a **denylist of
    legacy auto-generated header strings** used to *exclude* self-generated
    files from grounding. Removing them would *degrade* grounding on any repo
    that still has RunPrep/CoDRAG-marked generated files. **Leave them.** The
    only Eric decision is whether to keep (recommend keep) — no edit needed.
  - ⏳ **FLAGGED** — `packages/ui/package-lock.json` still declares
    `"name": "@codrag/ui"` while `packages/ui/package.json` is `@prep/ui`
    (stale lockfile name field, cosmetic). Fix: `cd packages/ui && npm install
    --package-lock-only` regenerates the lockfile to `@prep/ui` without
    touching `node_modules`. Deferred to the Stream 3 npm pass (USB + network
    caution; not run in the 2026-07-19 batch).
  - ⏳ **STILL OPEN** — `lemon_squeezy.py:14` codename reference (minor; review
    during the 8.1 licensing-resolver pass).
- **Do (remaining):** Fix `lemon_squeezy.py:14` codename reference; run the
  scoped `npm install --package-lock-only` in `packages/ui` during the Stream 3
  npm pass. `docs_grounding.py` markers stay as-is (intentional).
- **Acceptance:** grep `codrag`/`RunPrep` in `src/` + `packages/` → only
  intentional legacy-detection patterns (documented) remain.
- **Deps:** 8.2 marker decision is Eric's (keep-as-detection vs rename) —
  recommendation recorded: **keep**.

#### 8.3 — manutic/nomic-embed-code Ollama slug verification
- **Do:** Verify whether `manutic/nomic-embed-code` is an official nomic.ai
  publish on the public Ollama registry, or a private mirror slug that will
  404 for end users. If it 404s, switch all 4 sites
  (`embeddings:48,189`; `guides/models:151`; `embedder.py:64`) + README to ONE
  recommended model (README currently recommends `nomic-embed-text-v2-moe`).
  **Flag:** this is a hard broken-doc bug at launch if the pull command 404s.
- **Acceptance:** `ollama pull <slug>` succeeds on the public registry, or
  all 4 sites use a verified slug.

### Stream 9 — Credibility + content artifacts (AI; draft now)

#### 9.1 — D10 First 8 ADRs + HISTORY.md
- **Do:** Distill ADRs 0001–0008 from the highest-signal phases (113
  daemon-state, 139 embedder memory, 117 scoped rebuild, 82 MCP dogfooding,
  142 OSS path, the Apache-2.0+DCO decision, the REPO_TOPOLOGY decision, the
  Pro-tier reversal). One-page `HISTORY.md` framing the phase arc as deliberate
  engineering evolution. This is the credibility artifact acquirers/hiring
  managers actually read (DECISION_MEMO D10).
- **Files:** `docs/adr/0001-*.md`…`0008-*.md`; `HISTORY.md` (root, public).
- **Deps:** none. Will be in the public mirror allowlist (7.2).

#### 9.2 — D11 Benchmark harness + first vanilla data point (Part E)
- **Do:** Design a reproducible benchmark: SourcePrep-augmented context vs
  grep vs naive RAG vs plain model on real code-retrieval/context tasks, with
  a runnable harness + methodology; produce the first vanilla data point.
  **Hard gate (SCRUTINY §5):** if E.2 shows SourcePrep doesn't materially help,
  pause Parts F–H and diagnose. Define "measurable improvement" BEFORE
  running.
- **Deps:** none. Highest-leverage IC-offer artifact.

#### 9.3 — Part G Blog post drafts (3)
- **Do:** Draft 3 posts (MCP server for codebase intelligence; trace graph
  from a polyglot codebase; concepts + LLM confidence calibration). Note
  `Phase99_Content/blogs/` drafts exist but carry codrag codename — run
  through 7.2 triage.
- **Deps:** none. Codename-free versions go in the public mirror.

#### 9.4 — Part F Show HN draft + Part H.3 outreach-log template
- **Do:** Draft the Show HN post (title + 3 paragraphs + queued first comment;
  link the GitHub repo not the marketing site). Create `OUTREACH_LOG.md`
  template (company, contact, date sent, response, next step, status) —
  gitignore if it will contain private contact info.
- **Deps:** benchmark (9.2) should land first for the HN body, but the draft
  skeleton can start now.

### Stream 10 — Product-hygiene known-limitations (AI; no deploy)

#### 10.1 — README "Known Limitations" section (when README is written)
- **Do:** When authoring the public README (Part C.1, not yet started),
  include a Known Limitations section covering: (1) embedder RSS not reclaimed
  until daemon restart (Phase 139); (2) large-run concept synthesis silent
  fallback (`concepts_synthesis_failed` / `concepts_chunked_meta_failed`
  telemetry with no dashboard surface); (3) deep-enrichment UI can show stale
  "Not run" (Phase 145 FINDING). Be honest — OSS readers find these either
  way (SCRUTINY §2).
- **Deps:** README authoring (Part C.1) — a Stream 9-adjacent task not yet
  started. Note: the public README is itself a major AI-executable artifact
  not yet in this doc — **flag for scrutiny: should README authoring be its
  own stream here?**

#### 10.2 — Pre-launch product-fix triage (SCRUTINY §2)
- **Do:** For each known embarrassment, decide fix-now vs document-as-known
  - limitation: `prep_search` doc-bias (project_search_docs_bias — add a
  `--mode=code` flag or document the workaround); synthesizer silent-fail
  (document); pipeline sequencing bug (project_pipeline_sequencing_bug — fix
  or ship `--no-deep-enrichment` as recommended default); AGENTS.md in graph
  (already resolved per audit §8 — `repo_profile.py:21`); full-reset gaps
  (already resolved per audit §8). This is mostly documentation now.
- **Deps:** none.

---

## §2 — Items NOT in this doc (Eric-only or out of scope)

- **Eric-only legal/business:** A5 (LS count), A6 (LLC status), A7 (runway),
  B3 (sign IP Assignment), B1/B2 (USPTO search + 1(b) filing), A3/D3 (patent
  provisional decision + filing), B5 (public mirror push), C6 rotation
  (offline Tauri keygen), copyright registration ≤3 months.
- **Eric personal:** SCRUTINY §1 (LinkedIn, GitHub profile README,
  sourceprep.io/about, Twitter, resume).
- **Hero edits:** B16 (guardrail 5).
- **Out of scope for Phase 142:** new product features; pricing changes to the
  Pro tier beyond the 2026-07-18 restructure; VC funding; Mac App Store.

---

## §3 — Open questions for Eric (decisions that change the work)

1. **Path (a) vs path (b) for the Apache-2.0 claim (Stream 6).** Reword to
   future-tense now (AI, safe), or wait and execute C5 before the next deploy
   (Eric gate). **Recommendation REVERSED by scrutiny: prefer path (b)** —
   sequence B3 (IP Assignment) before the next deploy so C5 (LICENSE swap)
   lands and the present-tense Apache claims become TRUE. A README "will be
   released under Apache 2.0" note is **legally inert** (GitHub's own guidance:
   "Making your GitHub project public is not the same as licensing your project")
   and reads as hedging to the HN/OSPO audience the launch targets. Use path
   (a) only as a stopgap if B3 slips past the deploy window. If Eric picks (b),
   Stream 6.1 commits 9/10/13 are skipped (the LICENSE swap is the fix). See
   §5 Research note F2 for sources.
2. **docs_grounding.py codename markers (8.2).** ~~Keep as legacy detection
   patterns or rename.~~ **DONE 2026-07-19 (commit 56d496c9):** scrubbed the 4
   dead RunPrep/CoDRAG markers. Eric confirmed those names are dead with no
   users → no legacy output to detect → the markers were dead code, removed.
   Kept the live Prep/SourcePrep/Prep Staffing markers.
3. **Dead repo slugs (6.9).** Repoint to the not-yet-created
   `MagneticAnomaly/SourcePrep` now (URLs resolve at publish), or hold a
   neutral reword until B5. Recommendation: repoint now (the storefront is the
   decided target).
4. **TierComparison (6.4).** Rewrite or delete. Recommendation: rewrite only
   if a consumer uses it; delete if unused (check call sites).
5. **README authoring (10.1).** Should the public README (Part C.1) be its own
   AI stream here? It's the single most-leveraged document per
   IMPLEMENTATION_PLAN. **Recommendation: yes — add as Stream 11.**

---

## §4 — Suggested commit cadence

Commit per logical unit locally (`feedback_commit_as_we_work`); never push.
Suggested grouping (one commit each):

1. `docs(phase142): draft IP assignment + export memo + prior-art search (1.1, 1.3, 1.4)`
2. `docs(phase142): draft ToS/Privacy/EULA + governance set + DCO action (1.2)`
3. `chore(license): stage Apache-2.0 LICENSE + metadata + NOTICE (2.1–2.3)` *(local only; do not push until B3)*
4. `chore(license): scancode scan + CI license gate (3.1)`
5. `fix(license): Ed25519 crypto fail-closed + env key + generator/verifier reconciliation (4.1)` *(after Eric approves change plan)*
6. `chore(tauri): untrack codrag.key + gitignore (4.2)` *(local only)*
7. `docs(phase142): reconcile 12 internal contradictions (5.1–5.10)`
8. `docs(phase142): reconcile pricing SoT to $29/$9/$24 (5.4)`
9. `fix(marketing): reword present-tense Apache claims to future tense (6.1)` *(deploy-gated; stage)*
10. `fix(payments): rewrite to OSS pricing + gate CTAs (6.3)` *(deploy-gated)*
11. `fix(ui): rewrite TierComparison to OSS-all-capabilities (6.4)`
12. `docs(vscode): rewrite marketplace README to OSS story (6.5)`
13. `fix(docs): offline-licensing → Roadmap; installation license-honest (6.6, 6.7)`
14. `fix(brand): dead repo-slug repoint (6.9)`
15. `chore(license): paperclip page license-neutral (6.12)`
16. `feat(tools): build_public_mirror.py + allowlist (7.1, 7.2)`
17. `fix(license): write to .sourceprep not .runprep (8.1)`
18. `fix(brand): codename sweep in code (8.2)` *(after marker decision)*
19. `fix(embedder): verify/fix manutic Ollama slug (8.3)`
20. `docs(adr): first 8 ADRs + HISTORY.md (9.1)`
21. `feat(bench): benchmark harness + vanilla data point (9.2)`
22. `docs(blog): 3 Phase-142 post drafts (9.3)`
23. `docs(launch): Show HN draft + outreach log template (9.4)`
24. `docs(readme): public README + Known Limitations (10.1)` *(if §3 Q5 = yes)*

---

## §5 — Scrutiny amendments (2026-07-19, applied)

> 7-skeptic adversarial pass + synthesis (workflow `wj3hgxx8i`); 71 findings,
> 0 refuted. The critical inline corrections (guardrail 1 deploy-gate reality,
> 8.1 split-brain regression, §3 Q1 path reversal, 1.1 placeholders, 1.2 CHARTER
> scope + GPG placeholder + legal-trigger gate) are applied in place above.
> New streams, new items, research recommendations, the refined Eric-only
> critical path, and top-5-first live here.

### §5.1 — New work streams (were missing entirely)

#### Stream 11 — Public README (Part C.1) — was punted to §3 Q5; now a stream
**11.1 — Author public README.** Lead paragraph ("SourcePrep is the
structural codebase intelligence MCP server…"), one-paragraph what-it-does,
quick-install (`git clone` → `pip install -e .` → `prep serve` → MCP config
snippet), one-glance benchmark snippet (links 9.2 demo), "Works with" badges
(Claude Code, Cursor, Windsurf, Gemini CLI, VS Code, Copilot, **gstack**),
architecture diagram, link to CONTRIBUTING/SECURITY/docs, **no "CoDRAG"
anywhere**, Known Limitations fold-in from 10.1. **The single most-leveraged
document** per `IMPLEMENTATION_PLAN:122` and the literal subject of success
criterion 1. Unblocks 12.3 (gstack section), 6.14 (GETTING_STARTED), 9.7
(canned responses). **Owner: AI.** *(blocker — do early.)*

#### Stream 12 — gstack Integration (Part D) — ZERO mentions of "gstack" above; success criterion 4 silently dropped
**12.1** Build `prep` slash command per gstack format; test against a local
gstack install. **AI.** **12.2** Draft gstack PR/issue body (descriptive, not
prescriptive, per SCRUTINY §4; ship our own gstack-compatible bundle as
primary fallback). **AI drafts; Eric submits.** **12.3** README "Works with
gstack" section (depends 11.1). **AI.**

#### Stream 13 — IC-first reframe (D6 / RESEARCH_ROUND_2) — the C1–C12 reconciliation in Stream 5 does NOT cover this
**13.1** D6 IC-first reframe: flip README/STRATEGY/ACQUIRER_MAP to senior-IC
headline, acqui-hire as lottery-ticket upside. **AI.** **13.2** 90d→12mo
(coordinate with 5.2). **AI.** **13.3** Add SCRUTINY §21 Cursor SDK defensive
plan (§21 was never written — verified). **AI.** **13.4** Reopen license
Decision A (mark PROPOSED until A4 Eric sign-off). **Eric.**

### §5.2 — New items added to existing streams

| Stream | ID | Description | Owner |
|---|---|---|---|
| 1 | 1.2b | Audit `.github/ISSUE_TEMPLATE/` for OSS tone; add `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS` (Eric sole, MagneticAnomaly), `FUNDING.yml`. | AI |
| 1 | 1.2c | Community infra: enable GitHub Discussions, 3–5 `good first issue` starter tasks, `first-time-contributor.yml` auto-comment Action. | BOTH (AI drafts YAML+issue text; Eric clicks enable/label) |
| 1 | 1.5 | Publish/deploy runbook draft — checklist Eric executes at B5/deploy (BETA_MODE=false, 2.1–2.3, 7.1 dry-run, 4.2 rotation, 3.1 gate, A3 patent). | AI drafts; Eric executes |
| 2 | — | 2.3-finalize REQUIRES 3.1 landed; if B3 fires first, commit NOTICE with `<!-- TODO re-finalize after scancode -->` + re-finalize item. | AI |
| 3 | 3.2 | `.github/workflows/oss-ci.yml` — ruff/eslint/cargo fmt/clippy/mypy/tsc/pytest/cargo test/npm test/maturin build/npm build, no secrets, green on fresh clone. | AI |
| 3 | 3.3 | End-to-end fresh-clone smoke: `git clone` mirror + `pip install -e .` + `prep serve` + one `prep_search` query in clean venv; record wall-clock. | AI |
| 3 | — | Add `deny.toml` (cargo-deny config: allow Apache-2.0/MIT/BSD-3/MPL-2.0/ISC/Unicode-DFS-2016; deny GPL/AGPL/LGPL/copyleft). Optional FOSSA CLI cross-check (free for OSS) — do NOT substitute `licensee` for scancode (declared-license-only misses LLM-generated/copyleft-snippets). | AI |
| 4 | 4.3 | Technical data-flow doc substantiating "no phone-home after activation" — OSS build calls (Ollama embed, optional LLM, MCP client) vs Pro/Teams activation (one Ed25519 verify, then offline). Link from README + security page. | AI |
| 5 | 5.11 | Draft D&R_PLAN section 9 (Superseded) + section 2 (Distribution Channels) open-core layering (distinct from 5.4 which only SUPERSEDES the pricing block). | AI drafts; Eric sign-off |
| 6 | 6.13 | CTA-gate sweep across marketing/payments/docs/support — no ungated buyable CTA reachable while BETA=true. **Verified: payments app imports no IS_BETA_MODE — `Get Pro`/`Start Team` render whenever `NEXT_PUBLIC_LS_CHECKOUT_*` envs are set.** | AI |
| 6 | 6.14 | GETTING_STARTED.md rewrite (C.4) — strip internal/Phase/USB refs; 5-min walkthrough ending in working `prep_search` query. Deps: 11.1. | AI |
| 6 | — | 6.1 MUST be one atomic commit covering all 14 pages; never put `[deploy]` on a tip until all 14 are reworded. 6.5/9.1/9.4 ADRs/Show HN inherit the same tense rule as 6.1 until C5 lands. | AI |
| 7 | 7.3 | Public-safe AGENTS.md for the mirror (C8) — stripped variant, no dogfooding/frankness/Phase refs; keep internal AGENTS.md private via 7.2. | AI |

### §5.3 — Other inline corrections (apply when you reach the item)

- **4.1 Ed25519** — match `CHANGE_PLAN_ed25519_crypto_fix.md`: wire
  `PREP_LICENSE_PUBLIC_KEY` env-read + fail-closed on no key; do NOT bake any
  production key into source; generate a throwaway dev keypair at test time
  only (in-memory). Eric supplies the production pubkey via env at deploy.
- **4.2 codrag.key** — split: keygen (offline, Eric) → deliver pubkey string
  to AI → AI edits `tauri.conf.json:66` + commits. Conf edit is AI-gated-on-
  Eric-delivery, not Eric-only.
- **5.4 pricing SoT** — enumerate ALL facts verbatim: Pro $29 one-time +
  ~$15/yr optional updates renewal (license perpetual); Teams $9/seat/mo +
  3-seat min + $97/seat/yr (10% off annual); Enterprise $24/seat/mo + 15-seat
  min + setup (remote included, on-site from $3,500, air-gapped quoted).
  Acceptance: OPEN_CORE_SPLIT matches `pricing/page.tsx` line-for-line.
- **5.7 AGPL→revenue fallback** — keep an explicit "Apache-2.0 is permanent;
  the engine will not be relicensed" sentence alongside the revenue-fallback
  replacement, so the anti-rug-pull signal is restated, not just the AGPL path
  removed. Ensure consistency with CHARTER.md (1.2).
- **6.4 TierComparison** — prefer **delete** (grep confirmed 0 call sites in
  websites/ or dashboard); drop `index.ts:230` export. If a call site appears,
  extract pricing to a shared `packages/ui/src/pricing.ts` consumed by both
  TierComparison + `pricing/page.tsx` (single source) so it can't drift.
- **6.12 paperclip** — split: 6.12a (verify license-neutral wording staged)
  now; 6.12b (set to Apache-2.0 line) bundled with commit 3 (B3-gated).
- **7.1 build_public_mirror.py** — REQUIRES 8.2 (Eric marker decision) + 2.2
  (B3-gated lockfile) first; the `.runprep` deny must be scoped to non-source
  files (feature_gate.py:122-128 KEEPS `.runprep` as fallback, so a blanket
  `.runprep` deny fails the current tree). Split: 7.1a (AI) build tool +
  dry-run + manifest; 7.1b (ERIC) run `--emit` to produce the
  fresh-initial-commit tree, then B5 push.
- **8.2 docs_grounding markers** — Eric's decision (keep-as-detection vs
  rename); unblocks 7.1 denylist clean mirror.
- **8.3 manutic slug** — Eric picks the endorsed slug if manutic 404s (e.g.
  fallback `nomic-embed-text`, the docs' Tier-0 recommendation). Classify
  BOTH. Sequence 8.3 before 9.2 (local-embedder benchmark needs a working
  `ollama pull`).
- **9.2 benchmark** — Eric approves the comparator model + API budget (cloud
  bills his account), OR scope the first data point to local Ollama (no
  account). Classify BOTH.

### §5.4 — Refined Eric-only critical path (after amendments)

Minimal accurate Eric-only sequence to fire the public push:

1. **A4** license Decision A sign-off (reopen per 13.4; PROPOSED until Eric).
2. **A6** LLC confirm + **supply state-of-residence + pre-existing-license
   carve-outs** for 1.1 (hidden inputs the original doc missed).
3. **1.1** Eric fills `[PLACEHOLDER: governing-law + carve-outs]` in the draft.
4. **D8** legal-trigger review (attorney or Eric-as-principal) of ToS/Privacy/EULA before publish.
5. **B3** Eric signs IP Assignment → unlocks C5 + 2.1–2.3 atomic commit.
6. **A3** patent decision recorded in writing (per 1.4 acceptance; EU absolute-novelty forfeit at public commit).
7. **A5** Lemon Squeezy customer count → if >0, customer notice before any "now open source" announcement.
8. **4.2** Eric generates new Ed25519 production keypair offline → delivers pubkey to AI → AI edits `tauri.conf.json:66`.
9. **F1 (hidden gate)** Eric provides GPG fingerprint + provisions/confirms `security@sourceprep.io` inbox + confirms 5-bus-day SLA before SECURITY.md publish.
10. **8.2 (hidden gate)** Eric codename-marker decision → unblocks 7.1 denylist.
11. **B1/B2** USPTO filing — **design mark** (word + standard-character logo) in Class 9+42 per §5.5 F5; budget for 2(e)(1) office action.
12. **§3 Q1** Eric picks path (a)/(b) before commits 9/10/13 execute. Recommended (b).
13. **9.2 (hidden gate)** Eric approves comparator model + API budget.
14. **8.3 (hidden gate)** Eric picks endorsed embedder slug if manutic 404s.
15. **7.1b (hidden gate)** Eric runs `build_public_mirror.py --emit` → fresh-initial-commit tree.
16. **B5** public mirror push — gated on: deploy-gate verified (§0 checklist), C5 committed, 3.1/3.2 CI green on fresh clone, 7.1 denylist clean.
17. **E.4** Eric creates `sourceprep/benchmarks` GitHub repo (after 9.6 skeleton).
18. **E.3** Eric records + hosts demo video (from 9.5 script).
19. **F.1/F.2** Eric posts Show HN + timing (after 9.4 draft AND C5 AND 9.2 first data point).
20. **G.x** Eric publishes ≥2 of 3 blog posts.
21. **H.1** Eric sends ≥5 outreach emails.
22. **H.2** Eric submits ≥5 IC applications.
23. **12.2** Eric submits gstack PR/issue.
24. **Deploy-time flips** Eric executes 1.5 runbook (BETA_MODE=false, etc.).

**Hidden Eric gates the original doc missed:** §3 Q1 path pick, GPG fingerprint
+ security@sourceprep.io inbox + SLA (F1), codename-marker decision (8.2),
benchmark API budget (9.2), embedder slug pick (8.3), mirror --emit step (7.1b),
tauri conf edit split (4.2), 1.1 governing-law/carve-out inputs.

### §5.5 — Research-backed recommendations to Eric (web-verified)

1. **Pro $29 one-time — confirm, but re-anchor.** Aseprite ($19.99) + Krita
   ($9.99) are creative-tool anchors; the dev-tool anchor is **Sublime Text $80**
   (3-yr updates then paid upgrade, license never expires). $29 is defensible
   as a launch price; consider **$39–49** long-term to align with dev-tool
   willingness-to-pay. Keep ~$15/yr renewal (Sublime precedent) but consider
   extending the included-update window 12→24 months (Sublime gives 36). Add
   Sublime to the DECISION_MEMO precedent list.
   (https://www.sublimehq.com/sales_faq, https://krita.org/en/about/license/, https://obsidian.md/pricing)
2. **Apache-2.0 + DCO permanence — confirm, but fix the CHARTER wording.**
   DCO-alone does NOT prevent relicense — it makes a permissive→source-available
   flip require **unanimous contributor consent** (Mozilla 5yr MPL 1.1→2.0;
   OpenSSL 2yr to Apache 2.0). Scope the CHARTER clause to **"no source-available
   flip"**, not "no license change ever" — a permissive→permissive relicense
   (Apache→MIT) remains trivially possible and is fine. The lock does prevent
   the HashiCorp/Elastic/Redis BSL/SSPL pattern (that lever was the CLA
   sublicensing grant we deliberately don't have).
   (https://katedowninglaw.com/2019/02/15/should-i-use-a-developers-certificate-of-origin-or-a-contributor-agreement/, https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA)
3. **12-month window — confirm.** 90 days is fantasy for a no-audience solo
   dev. The Steinberger/OpenClaw "60-day" precedent is confounded (prior $116M
   PSPDFKit exit, $10–20k/mo own spend, 500k systems). Frame 12 months as a
   floor with milestone gates.
   (https://steipete.me/posts/2026/openclaw, https://www.fastcompany.com/91550800/how-peter-steinberger-built-openclaw)
4. **IC-first — confirm, but fix the rationale.** The DECISION_MEMO claim that
   a solo dev has "structurally nothing to acqui-hire" is **empirically
   wrong**: Redpanda acquired Benthos (solo founder, May 2024), Vercel
   acqui-hired Grep (solo founder, Nov 2024), BrowserStack acquired Requestly
   (solo founder, May 2025). The big-name AI acqui-hires were funded startups;
   solo-dev OSS projects DO transact — priced as talent+community, not IP. So
   the likely acquisition is a modest talent hire, not a $2–3B exit — which
   **strengthens** the IC-first thesis.
   (https://techcrunch.com/2024/05/30/redpanda-acquires-benthos-..., https://vercel.com/blog/vercel-acquires-grep)
5. **Trademark — file as a DESIGN mark.** "Source"+"Prep" both describe
   source-code preparation — the compound-mark pattern TTAB rejected in *In re
   OpenAI* (March 2026, CHATGPT) and *In re Fuhu* (2013). Sourcegraph's word
   mark drew an opposition; SourceTree registered as a DESIGN mark (the
   workaround). File SOURCEPREP as a design mark (word + standard-character
   logo) in Class 9+42, OR file the word mark with a §2(f) acquired-
   distinctiveness plan after 3–5 years of use. **Budget for a 2(e)(1) office
   action**; prepare a descriptiveness-overcoming argument.
   (https://ttabvue.uspto.gov/ttabvue/ttabvue-97733261-EXA-14.pdf)
6. **scancode — confirm; add FOSSA cross-check.** scancode-toolkit is the
   right primary deep scan (local, snippet-level, no vendor lock-in). Do NOT
   substitute `licensee` (declared-license-only, misses the LLM-generated/
   copyleft-snippet case). ADD FOSSA CLI (free for OSS, ~99.8% accuracy) as a
   second opinion; reconcile disagreements before B5.
7. **Path (a) vs (b) — REVERSE to (b).** A README "will be Apache 2.0" note is
   legally inert (GitHub: "Making your project public is not the same as
   licensing it") and reads as hedging to the HN/OSPO audience. Sequence B3
   before the next deploy so C5 lands and the present-tense Apache claims
   become TRUE. Use (a) only as a stopgap if B3 slips.
   (https://github.com/github/opensource.guide/blob/main/_articles/legal.md)

### §5.6 — Top 5 things to fix FIRST

1. **(done in this revision)** Fix guardrail 1's wrong deploy-safety model + add the pre-push gate-verification checklist.
2. **(done in this revision)** Re-scope 8.1 — the original draft was a silent Pro/Enterprise licensing regression.
3. **Add Stream 11 — author public README** (§5.1). The single most-leveraged document; currently punted. Unblock it before anything that links to it.
4. **Add Stream 12 — gstack integration** (§5.1). Success criterion 4 had zero mentions; Part D was silently dropped.
5. **(done in this revision)** Reverse §3 Q1 to path (b) — sequence B3 + C5 before the next deploy so the present-tense Apache claims become true instead of hedging.

### §5.7 — §4 commit-cadence fixes

- **Commit 3** — change to "stage (git add) but do NOT commit until B3;
  commit 2.1+2.2+2.3 atomically the moment Eric confirms B3 signed."
- **Commit 7** — "5.1–5.3, 5.5–5.10" (exclude 5.4); keep commit 8 as 5.4 alone.
- **Commit 11** — "chore(ui): **delete** unused TierComparison (6.4)" (verify 0 call sites first, then delete + drop `index.ts:230` export).
- **Commits 9/10/13** — prefix "(conditional on §3 Q1 = path a)"; skip if Eric picks (b) and B3+ C5 land first.
- Add commits for 6.2 (disclose 7-day revalidation), 6.8 (scope no-phone-home to OSS build), 6.11 (drop Pro-tier capability claim), 11.1 (README), 12.1 (gstack slash command), 13.1 (IC-first reframe), 3.2 (oss-ci.yml), 3.3 (fresh-clone smoke).

---

*This doc is a living artifact. The 2026-07-19 scrutiny pass (workflow
`wj3hgxx8i`, 7 skeptics + synthesis, 71 findings) is folded into §5; the
critical corrections are applied inline above. Full per-finding detail is in
the workflow transcript.*