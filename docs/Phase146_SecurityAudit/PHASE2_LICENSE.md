# Phase 2 — License & Feature-Gate — Findings

**Date:** 2026-06-22
**Method:** orchestrated workflow (Map → 5 Probes → 2-lens adversarial Refute panel, 46 agents) + **independent re-verification of the linchpin claim by the lead** (live forgery run in the project venv). prep daemon down → grep/read.
**Verification level:** the headline is *proven* (working forgery). Everything else is code-confirmed and run through an adversarial refute panel; verdicts below reflect what survived.

## The most important outcome of the refute panel: a category correction

The adversarial pass established a distinction the earlier scaffold (and the Phase 06 audit's "CRIT" labels) blurred: **almost every license finding is a local user bypassing their *own* license gate.** That is a **revenue / license-integrity** problem, not a CIA-triad **security** vulnerability — no one else's data or machine is compromised. Both matter, but they belong in different buckets and get different severities. Findings below are split accordingly. This is exactly the kind of correction the refute step exists to produce.

---

## 🔴 HEADLINE — License system is cryptographically void (LAUNCH-BLOCKER for paid tiers)

**Category:** license/revenue integrity · **Severity:** CRITICAL (business) · **Verdict:** PROVEN
**Consolidates:** CRIT-1, C-7, verify-LIC-1, storage-LIC-2, LS-4.

Three independent, confirmed forgery paths mean any user can self-grant Enterprise:

1. **The signing key's private half is public.** `licensing.py:22` `DEFAULT_PUBLIC_KEY_HEX = "3b6a27bc…da29"` is the **RFC 8032 §7.1 test-vector** public key — i.e. the Ed25519 key for the **all-zeros 32-byte seed**. Independently reproduced by the lead: `Ed25519PrivateKey.from_private_bytes(b"\x00"*32).public_key()` == the shipped key (MATCH), and a forged `{tier:enterprise,seats:999,valid:true}` token **passed `verify_license_key()`**.
2. **There is no production override.** The `PREP_LICENSE_PUBLIC_KEY` env var is a **comment only** (`licensing.py:21`); `licensing.py` imports no `os` and never reads it. `verify_license_key` is always called with one arg (`feature_gate.py:202`, `license.py:139`), so the test key is *always* used. No build path injects a real key (exhaustive search of pyproject, scripts, all 7 CI workflows, deploy Dockerfiles, Tauri config — `set_anywhere=false`).
3. **Unsigned licenses are accepted anyway.** Even without touching crypto, `feature_gate.get_license()` **warns-but-allows** a hand-written `~/.sourceprep/license.json` with no `key` field — it logs a SECURITY warning then parses `tier/valid` from the plaintext (`feature_gate.py:218-224`, `:226-254`). Second forgery path, zero crypto needed.

**Fix (launch blocker):** generate a real keypair, keep the private half offline/HSM, ship only the public half (and actually *implement* the `PREP_LICENSE_PUBLIC_KEY` read or a build constant); make `valid` imply a verified signature — reject unsigned key-bearing and keyless licenses for paid tiers. Matches the original Phase 06 CRIT-1 "ship blocker" call — now with proof.

> Note: `scripts/generate_license.py:33` commits a *real* Ed25519 private key (`c6b3c4…84f`), but it derives a *different* public key (`928764b6…`) — it does **not** match the shipped key, so it is a secret-hygiene smell, **not** the forgery vector (refuted as such, LIC-8). The forgeable key is the all-zeros seed.

---

## Genuine security findings (cross-trust-boundary / affect others)

| ID | Finding | Evidence | Severity | Refute outcome |
|----|---------|----------|----------|----------------|
| P2-SEC-1 | License file written world/group-readable (no `chmod 0600`) → local info-disclosure on multi-user hosts | storage-probe LIC-6; router write paths | LOW–MED (local multi-user) | **2/2 survived** — no mitigation found. Pairs with prior HIGH-2 (.secrets perms). |
| P2-SEC-2 | `/license/dev-override` endpoint has no server-side gate; reachable via CSRF/drive-by on the **token-less** daemon (ties to Phase 1 C-1) | `license.py:502-584` | MED (bounded: loopback + token-when-set) | C-2.1 **1/2 survived**; the panel bounds it to a local/CSRF frontier, not a broad auth bypass |
| P2-SEC-3 | MCP transport `is_local` Origin check prefix-bypassable (`http://localhost.evil.com`) | `mcp/transport.py:136` | LOW (http transport opt-in) | F1-NEW-1 **0/2 "exploitable" but both confirm the bug is real** — fix cheap + add regression test; mitigations are incidental |

## License/revenue-integrity defects (real, fix before monetizing — not CIA-security)

| ID | Finding | Evidence | Refute outcome |
|----|---------|----------|----------------|
| P2-LIC-1 | No machine binding — `license.json` freely copyable between machines | storage-LIC-1 (`feature_gate.get_license`) | **2/2 survived** (as revenue/DRM) |
| P2-LIC-2 | LemonSqueezy activation trusted purely on JSON `activated/valid` — no signed entitlement | `lemon_squeezy.py:88-129`, `license.py:116` | refuted-as-security, **survives as revenue** |
| P2-LIC-3 | No store_id/product pinning; `PRODUCT_TIER_MAP` empty → unmapped product falls back to `meta.tier` (claims its own tier) | `lemon_squeezy.py:35-40` | refuted-as-security, survives as anti-piracy |
| P2-LIC-4 | No replay/rollback protection — cancelled/refunded/expired LS license kept by editing the file | storage-LIC-5 | **1/2 survived** for the production LS path |
| P2-LIC-5 | Signature silently skipped if `cryptography` lib unavailable (`except ImportError` has no return → reads unverified tier) | `feature_gate.py:213-217` | contested headline; **survives as defense-in-depth** (hard-dep makes it rare) |

## Correctness / hygiene (non-security, but real)

- **P2-FIX-1** — Read/write path mismatch: reads prefer `~/.sourceprep` then `~/.runprep` (`feature_gate.py:114-128`); **all 6 router writes hardcode `~/.runprep`** (`license.py:189,221,318,365,434,517`). Activate/deactivate may operate on a different file than the gate reads. (LIC-7, refuted-as-security, real correctness bug.)
- **P2-FIX-2** — Committed Ed25519 private key in `scripts/generate_license.py:33` (non-matching, but poor hygiene). (LIC-8.)
- **P2-FIX-3** — Signing input lacks domain separation / algorithm pinning (`licensing.py:40-72`); moot while the key is public, matters after the key fix. (verify-LIC-2.)
- **P2-FIX-4** — Unparseable `expires_at` defaults to never-expires rather than failing closed (`feature_gate._parse_expires_at`). (verify-LIC-4.)

## Refuted / subsumed (kept for the record so the next pass doesn't re-chase)

- **C-2 (Phase 1)** — *as a broad unauthenticated bypass*: **refuted 0/2**. The endpoint is real & ungated, but reachability is bounded by the IPC token (when set) + loopback; and the **dashboard tier-dropdown IS dev-build-gated** (C-2.2, `useLicenseSystem.ts` nav-hide + overlay redirect), so a production end-user can't reach it through the shipped UI. Reframed → P2-SEC-2 (server-side gate still needed).
- **LS-3** — TLS verification is ON (no `verify=False`); no MITM vuln. Positive finding.
- **LS-4 forgery claim** — refuted: the offline fallback still checks a signature; it's only forgeable *because of the public key* → subsumed into the HEADLINE.
- **verify-LIC-3** ("fails open when crypto missing") — headline contested; the real concern is the unsigned-accept path (HEADLINE #3) + P2-LIC-5.

---

## Open question carried forward (the one thing this phase could NOT verify)
Is the packaged desktop daemon's HTTP API bound localhost-only / token-required, or can a non-loopback deployment expose `/license/dev-override` and friends? The Map agent flagged this as out-of-files-scope. It's the Phase 1 D-3 footgun (C-1) — already logged; revisit if scope expands to packaging/runtime config.

## Verdict roll-up vs. prior ledger
- **CRIT-1 / C-7 → 🔴 CONFIRMED, CRITICAL (launch-blocker).** Was 🟡 "Ed25519 wired & fails closed." Reality: the key is public and unsigned licenses are accepted. The "fails closed" was true *only* for a present-but-invalid signature against a key anyone can sign with.
- **C-2 → reframed** to P2-SEC-2 (bounded) + confirmed the UI is dev-gated.
- **New:** P2-SEC-1 (perms), P2-LIC-1..5, P2-FIX-1..4.

## Next: Phase 3 — Outbound / SSRF / Team-Sync (C-3 `is_safe_url` gaps, MED-3 integrity-warn-not-abort, `team_config.py` validation completeness, HIGH-2 secrets perms — which P2-SEC-1 now reinforces).
