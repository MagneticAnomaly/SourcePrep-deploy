# Audit Verification — 2026-07-17

> **What this is:** an independent re-derivation of the load-bearing claims in
> `AUDIT_2026-07-17.md`, performed by a reviewing AI session against the live
> repo at branch `docs/feedback-concept-pipeline-audit-2026-07-11` (HEAD
> `f899539a`). Each claim is marked **CONFIRMED / CORRECTED / NOT-REPRODUCED**
> with file:line evidence. PRIVATE — belongs in the Phase 143 keep-private bucket.

## Summary verdict

All eight load-bearing claims are **substantively confirmed.** Two carry
material corrections that make the underlying risk *worse* or the *mechanism
different* than the audit states, and one entirely new finding surfaced. Nothing
was not-reproduced.

| # | Claim | Verdict |
|---|---|---|
| 1 | Three-way license identity (LICENSE proprietary / pyproject MIT / plan Apache) | **CONFIRMED** |
| 2 | Committed Ed25519 private key + test-vector public key + unsigned-accept + live forgery | **CONFIRMED (mechanism CORRECTED)** |
| 3 | FREE = 3 projects in code vs 2/3/retired in docs | **CONFIRMED** |
| 4 | Pricing disagreement across 3 docs + phantom Founder's/renewal SKUs | **CONFIRMED** |
| 5 | `codrag.key` signing key in git + worktree blocks filter-repo | **CONFIRMED (severity CORRECTED — it is live-tree + on origin, not just history)** |
| 6 | SECURITY.md untracked; no CONTRIBUTING/CLA/DCO/NOTICE | **CONFIRMED** |
| 7 | Lemon Squeezy purchase path not operationally wired | **CONFIRMED** |
| 8 | New issues the audit missed | **1 NEW FINDING (see N1)** |

---

## Claim 1 — Three-way license identity conflict — CONFIRMED

- Root `LICENSE:1-3` = "COMMERCIAL SOFTWARE LICENSE AGREEMENT … Copyright (c)
  2026 Magnetic Anomaly LLC. All Rights Reserved." `LICENSE:10` "NO
  REDISTRIBUTION"; `LICENSE:14` "NO REVERSE ENGINEERING"; `LICENSE:20`
  "INDIVIDUAL USE … purchased a valid license key." → **proprietary commercial.**
- `pyproject.toml:10` `license = "MIT"`; `pyproject.toml:22`
  `License :: OSI Approved :: MIT License`. → **MIT metadata.**
- Planned outbound license is Apache 2.0 (`OPEN_CORE_SPLIT.md:220` "Apache 2.0").
- The three do not reconcile. The authoritative outbound grant today is the
  proprietary `LICENSE` file; the MIT metadata is materially false; Apache 2.0
  exists only in plan docs. **Confirmed as stated.**

## Claim 2 — Void license crypto + committed private key — CONFIRMED, mechanism CORRECTED

Facts confirmed:
- `scripts/generate_license.py:33` commits `DEFAULT_PRIV_KEY_HEX =
  "c6b3c439525def409ea605e0143ba2ab91d933f300c155c42e2e824b057da84f"`
  (git-tracked, commented "DO NOT USE IN PRODUCTION").
- `src/prep/core/licensing.py:22` ships `DEFAULT_PUBLIC_KEY_HEX =
  "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29"`.
- `PREP_LICENSE_PUBLIC_KEY` is **comment-only**: `licensing.py` has no `import
  os` and never reads the env var (the `verify_license_key` `public_key_hex`
  parameter exists but no caller passes an env-sourced value). Confirmed.
- `feature_gate.py:218-224` warn-but-accepts unsigned `license.json` (the `else`
  branch logs a warning, then proceeds to parse and honor `tier`). Confirmed.
- **Live forgery reproduced** in `.venv`: a `{tier:enterprise, seats:999}` token
  signed with the all-zeros seed is accepted by `verify_license_key()` and
  returns the enterprise payload. **Anyone can mint an enterprise license.**

**Mechanism CORRECTION (the audit conflates two independent facts):**
- The shipped public key `3b6a27bc…da29` is the Ed25519 public key of the
  **all-zeros 32-byte seed** (empirically recomputed: `pub(b"\x00"*32)` == the
  shipped key). Its private key is universally known (32 zero bytes) → this is
  what enables forgery, *not* the committed private key.
- The committed private key `c6b3…84f` does **NOT** correspond to the shipped
  public key: `pub(c6b3…84f)` = `928764b66237e489595ac7e7c963bcc7f82c07ff904a790a4aec99f9ecee6dd0`
  ≠ `3b6a27bc…da29`. A token signed with the committed key is **rejected** by
  `verify_license_key()`.
- Attribution nit: the audit calls `3b6a27bc…` the "RFC 8032 §7.1 test vector."
  RFC 8032 §7.1's TEST 1 seed is `9d61b19d…`, not all-zeros. `3b6a27bc…` is the
  famous all-zeros-seed public key — a well-known, trivially-derivable value,
  which is the substantive point. The "§7.1" citation is imprecise; the risk is
  identical.

Net: blocker #4 stands. The forgeable path is the test-vector *public* key, not
the committed *private* key. Both should still be remediated (see N1).

## Claim 3 — FREE project limit contradiction — CONFIRMED

- `feature_gate.py:45-51` `FEATURE_TIERS["projects_max"][Tier.FREE] = 3`.
  `feature_gate.py:4` docstring "free: 3 projects."
- `DISTRIBUTION_AND_REVENUE_PLAN.md:355` Free = 3.
- `PRODUCT_AND_BUSINESS_OVERVIEW.md` Free = "2 active projects" (audit cite :245).
- `OPEN_CORE_SPLIT.md:37` calls the old Free (3-projects) tier retired /
  unlimited under OSS.
- Code enforces 3; one doc says 2; one says 3; the locked plan abolishes it.
  **Confirmed.**

## Claim 4 — Pricing disagreement + phantom SKUs — CONFIRMED

- `OPEN_CORE_SPLIT.md:19-25,222-227` (locked): Pro **$70** perpetual; Teams
  $15/seat/mo or **$144**/seat/yr; Enterprise **$50**/seat/mo (10-seat,
  $6k floor) + $5k setup; Enterprise Plus. `:222` explicitly "Down from $79."
- `PRODUCT_AND_BUSINESS_OVERVIEW.md:250-256`: Pro **$79**; **Founder's Edition
  $49** (first 500 users, :251); **~$30/yr renewal** (:253, contradicts "never
  expires"); Teams **$12/seat/mo** annual-only.
- `DISTRIBUTION_AND_REVENUE_PLAN.md:355-358`: Pro **$79**; Teams $15/seat/mo;
  Enterprise **Custom**; plus an $84.99 App Store variant (:106).
- Pro $70 vs $79; Teams $15 vs $12; Enterprise $50 vs Custom; Founder's +
  renewal SKUs exist in exactly one doc. **Confirmed.**

## Claim 5 — `codrag.key` signing key + blocking worktree — CONFIRMED, severity CORRECTED

- `.claude/worktrees/oss-marketing-copy` exists (`git worktree list` shows it +
  `marketing-oss`), so `git filter-repo` is blocked until removed. Confirmed.
- `src/prep/dashboard/src-tauri/.tauri/codrag.key` blob content =
  `untrusted comment: rsign encrypted secret key …` — a real minisign/rsign
  **encrypted** Tauri-updater secret key. `.key.pub` is the matching minisign
  public key `C43F6BF18AEA1FE0` (public, harmless). Confirmed.

**Severity CORRECTION:** the audit frames `codrag.key` as a *git-history* secret
("the one genuine history secret … at commit `5ba42227`"). In fact it is
**currently tracked in the live tree** — `git ls-files` returns
`src/prep/dashboard/src-tauri/.tauri/codrag.key` on the current branch **and on
`main` and `origin/main`**, and it is present on disk in the main worktree. So:
1. It is a live-tree removal problem first (aligns with audit H8's reclassification), not only a history problem.
2. It is **already on the `origin` remote** — history-only reasoning that assumes "private repo stays private" does not fully neutralize it; the encrypted key already left the machine.
3. Mitigating: the key is passphrase-**encrypted** (rsign/minisign), so exposure alone is not immediate compromise. Correct fix: rotate the Tauri updater keypair, untrack the encrypted private key, never commit the new private half.
   (Exact introducing commit: the audit cites `5ba42227` (a path-rename touch);
   the blob is reachable from `main`, `origin/main`, and both marketing
   worktree branches.)

## Claim 6 — Missing governance files — CONFIRMED

- `SECURITY.md` present on disk but **untracked** (`git status` → `?? SECURITY.md`;
  `git ls-files --error-unmatch` fails).
- `CONTRIBUTING.md`, `NOTICE`, `NOTICE.md`, `CLA.md`, `ICLA.md`, `CCLA.md`,
  `DCO`, `CODE_OF_CONDUCT.md`, `CHARTER.md` — **all absent.** Confirmed.

## Claim 7 — Lemon Squeezy purchase path not wired — CONFIRMED

- `src/prep/core/lemon_squeezy.py` exists (LS REST client, `activate_key`, etc.).
  `PRODUCT_TIER_MAP` (`lemon_squeezy.py:35-40`) is **empty** — every entry
  commented out ("filled in after LS setup").
- `websites/apps/payments/src/app/page.tsx:6-7,28-40`: checkout buttons read
  `NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL` / `_TEAM`, default `''`, and when empty
  render "View Pricing" linking to `sourceprep.io/pricing` — **no live
  checkout** without env config; `.env.example` values are placeholders
  (`perpetual_variant_id`).
- `websites/apps/payments/src/app/api/recover/route.ts:17` is a **mock**
  (`console.log("[Mock] Recovering license…")`) — no real LS call. No LS webhook
  receiver exists in the payments app.
- Conclusion matches the audit: an empty `PRODUCT_TIER_MAP` proves the mapping
  is unwired, **not** that zero purchases occurred. Whether any purchase actually
  happened is unknowable from code — **Eric must confirm the count** (open
  question #1).

## N1 — NEW FINDING (audit missed): the license generator is internally inconsistent with the verifier

Because `pub(c6b3…84f)` = `928764b6…` ≠ the shipped verifier key `3b6a27bc…`,
a license produced by the project's own `scripts/generate_license.py` **using its
default key** would be **rejected** by `verify_license_key()`. The comment at
`generate_license.py:31` ("matches the test public key in prep.core.licensing")
is **false**. The two halves of the offline-licensing system were never
mutually consistent — someone rotated one side without the other. This is a
distinct correctness bug from the forgeability blocker and means the "official"
offline license path is non-functional as shipped. It should be fixed in the
same crypto pass (generate a real keypair; make generator and verifier share it).
