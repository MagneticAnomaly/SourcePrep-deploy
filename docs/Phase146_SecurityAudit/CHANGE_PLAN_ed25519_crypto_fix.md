# Change Plan — Ed25519 License Crypto Fix + Secret Removal (Phase 146 blocker #4)

> **Status:** PROPOSED — awaiting Eric's approval before ANY execution.
> This plan touches security-sensitive code and secret material. Per the handoff,
> no security-sensitive file or git history is touched until this plan is
> confirmed. Nothing here has been executed. No push / force-push / filter-repo.

## Why

Verified 2026-07-17 (`AUDIT_VERIFICATION_2026-07-17.md`):
- The shipped verifier public key `licensing.py:22` is the all-zeros-seed
  Ed25519 public key → **anyone can forge a `{tier:enterprise}` token**
  (reproduced live).
- `PREP_LICENSE_PUBLIC_KEY` override is comment-only (never read).
- Unsigned `license.json` is warn-but-accepted (`feature_gate.py:218-224`).
- A committed private key sits at `generate_license.py:33` (does not even match
  the verifier — finding N1).
- The Tauri updater secret key `codrag.key` is a **live-tree tracked file** on
  `main` / `origin/main` (encrypted, but already off-machine).

## Scope split (what is / isn't in this pass)

**IN (engineering, reversible in the private tree, no history rewrite):**
1. Remove the hardcoded test material from the live tree.
2. Make the verifier read a real production public key from env, and stop
   trusting a baked-in key.
3. Reject unsigned `license.json` for paid tiers.
4. Reconcile generator ↔ verifier so the official offline path works (N1).
5. Rotate the Tauri updater keypair; untrack the encrypted private key.
6. Tests.

**OUT (needs Eric — do NOT do in this pass):**
- Generating the *real production* private key (Eric does this offline/HSM; I
  only wire the code to read the public half and provide a throwaay dev key for
  tests).
- Any `git filter-repo` / history rewrite / squash (blocked by worktrees anyway;
  and per audit H8 the fresh-initial-commit mirror makes history scrub
  unnecessary for the OSS launch).
- Any push or force-push.
- Deciding whether the forgery blocks OSS-FREE publication or only paid tiers
  (open question — my recommendation: it blocks *paid tiers only*, since the OSS
  core does not depend on license validity; but the private key + test key must
  still leave the live tree before any public mirror).

## Files to change

| File | Change |
|---|---|
| `src/prep/core/licensing.py` | Add `import os`; read `PREP_LICENSE_PUBLIC_KEY` (env) as the production key; remove the all-zeros `DEFAULT_PUBLIC_KEY_HEX` baked value (replace with `None` + a clear "no key configured → reject" path, OR a clearly-labeled dev-only key gated behind `PREP_DEV_MODE=1`). When no production key is configured, signature verification returns `None` (fail closed). |
| `src/prep/core/feature_gate.py` | For paid tiers (MONTHLY/PERPETUAL/TEAM/ENTERPRISE), require `signature_verified is True`; unsigned or unverifiable → FREE. Keep FREE working with no license. |
| `scripts/generate_license.py` | Remove `DEFAULT_PRIV_KEY_HEX`. Require `--priv` (no baked default). Update the false comment (N1). Optionally read `PREP_LICENSE_PRIVATE_KEY` env for convenience. |
| `src/prep/dashboard/src-tauri/.tauri/codrag.key` | `git rm --cached` (untrack) + delete from working tree; add `.tauri/*.key` to `.gitignore`. Eric regenerates the updater keypair offline and updates `tauri.conf.json` pubkey. |
| tests | New: forged all-zeros token is **rejected**; unsigned paid license → FREE; a token signed by a configured dev key verifies; generator output verifies against the same dev key (closes N1). Adjust existing licensing tests. |

## Dev-key strategy for tests (no real secret in repo)

- Generate a throwaway Ed25519 keypair **at test time** (in-memory, per session)
  and inject the public half via `PREP_LICENSE_PUBLIC_KEY` / the `public_key_hex`
  param. No key material is committed. This is the "test full import chain"
  pattern — at least one test signs with the private half and verifies through
  the real `verify_license_key()` seam unmocked.

## How the private key leaves history (given the fresh-initial-commit mirror)

- The public mirror is built from a **fresh initial commit** (`OPERATIONS.md:18`),
  so no private-repo history is published → the committed test key never reaches
  the public repo *by construction*, provided the live tree is clean at mirror
  time. **No `filter-repo` needed for the OSS launch.**
- For the private repo's own hygiene, history rewrite is **optional** and
  deferred (blocked by the two live worktrees; low urgency because the test key
  is non-production and the `codrag.key` is encrypted). If ever done, remove the
  worktrees first. This stays OUT of this pass.

## Sequencing & guardrails

1. This pass produces a **local commit only** on the current branch. No push.
2. `codrag.key` rotation requires Eric (offline keygen + `tauri.conf.json`
   update) — I will stage the untrack + gitignore and hand off the regen step.
3. Restart the daemon before any live validation (no hot-reload).
4. Use `.venv/bin/python` / `.venv/bin/pytest`.

## Acceptance

- [ ] Forged all-zeros `{tier:enterprise}` token → `verify_license_key()` returns `None`.
- [ ] Unsigned `license.json` claiming a paid tier → resolves to FREE.
- [ ] With `PREP_LICENSE_PUBLIC_KEY` set to a dev key, a matching-signed token verifies and generator output round-trips (N1 closed).
- [ ] No private key material committed anywhere in the live tree; `.tauri/*.key` gitignored.
- [ ] Tests green: `.venv/bin/pytest tests/ -k licens -v`.
