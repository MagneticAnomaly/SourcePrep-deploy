# Deep-Research Handoff — Session D: codrag.key history scan + rotation plan (DR-6 + ED-6 prefix)

> **Self-contained starter prompt** for a dedicated follow-up AI session.
> Part of the 2026-07-19 legal+security+message audit follow-up. Full audit
> context: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`.
>
> You are one of four parallel deep-research sessions (A=legal, B=security
> engineering, C=SBOM scan, D=codrag.key history). You do NOT need to wait on
> the others.

## What this session is

**Read-only git history scan + rotation plan.** No code mutation, no key
rotation (rotation is Eric's decision). You confirm what's in origin history,
verify the public-mirror gate is sound, and produce a rotation plan Eric can
approve. The lightest of the four sessions.

## Hard rules

- **Read-only on git AND the filesystem.** No `git` mutation, no file edits
  except your output doc, NO key generation, NO key rotation (that's an
  Eric-decision + a release-engineering act). You SCAN and REPORT.
- **License-neutral.** No legal act, no assertion of a specific OSS license.
- **NO attorney budget.** The rotation EXECUTION is Eric's; you produce the
  PLAN + the framed decision.
- **Don't trust memory/notes for claims** — verify against the repo + git
  history.
- **SourcePrep = brand; prep = code.** No CoDRAG/RunPrep in copy. (Yes,
  `codrag.key` the FILE still carries the dead codename — that's a known
  artifact; flag it but do NOT rename the file, renaming is a release-
  engineering act Eric must sequence with the rotation.)
- **No image input** (model crashes on PNG Read). Verify text-only.
- **prep MCP:** call `prep` (no args) first; project_id in
  `.sourceprep/AGENT_CONTEXT.md`. `prep_search` can locate references to
  `codrag.key` / `codrag.key.pub` / the Tauri signing config, but git history
  is outside prep's graph — use `git log -p` + grep.
- **Dogfooding:** note unhelpful/wrong prep results as product feedback.

## Items

### DR-6. codrag.key history scan + rotation plan

**Context (verified by the audit):**
- `codrag.key` is still tracked on `origin/main` at
  `src/prep/dashboard/src-tauri/.tauri/codrag.key` — an **rsign/minisign-
  format encrypted Ed25519 secret key** for signing **Tauri app-update
  bundles** (macOS/Windows). It is **NOT the license-signing key** — license
  forgery risk lives separately in `src/prep/core/licensing.py:22`
  (`DEFAULT_PUBLIC_KEY_HEX` = RFC 8032 §7.1 Test 1 public key, forgeable; Phase
  146 `CHANGE_PLAN_ed25519_crypto_fix.md` has that fix plan — OUT OF SCOPE
  here, note it only).
- The public-mirror gate IS built and fails-closed
  (`tools/build_public_mirror.py:412-416`); the mirror design is a
  **fresh-initial-commit** (no history copy), so origin history is **never**
  published by the mirror.

**DO:**
1. **History scan.** Run:
   ```
   git log --all -p | grep -iE 'BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY|codrag\.key|sk-[A-Za-z0-9]{20}|gh[pousr]_|AKIA[0-9A-Z]{16}|-----BEGIN.*PRIVATE KEY-----'
   ```
   (extend the pattern as you see fit). **Confirm `codrag.key` is the ONLY
   private-key/secret commit in history.** List every hit with
   `commit:file:line`. If other secrets appear, enumerate them.
2. **Verify the gate is CI-wired.** Grep `.github/workflows/` + `scripts/`
   for invocations of `build_public_mirror.py`. Is the gate a MANDATORY
   pre-push CI check, or a MANUAL script (operator discipline only)? If
   manual, flag to Eric (this folds into ED-6) to add a pre-push hook /
   required CI job. Report the exact wiring state.
3. **Confirm the fresh-initial-commit property.** Read
   `tools/build_public_mirror.py` around the mirror-creation logic and
   confirm it does NOT copy `.git` / history (so leaked history on origin is
   never published). Cite the lines.
4. **Distinguish the two keys.** Restate clearly for Eric: `codrag.key` =
   Tauri updater signing key (this session); `licensing.py:22` placeholder =
   license verification key (separate, Phase 146, out of scope). Make sure
   the rotation plan addresses ONLY the Tauri key.

### ED-6 research prefix — rotation + CI-gate plan (research only; do NOT execute)
Produce a **rotation plan** Eric can approve:
- **Step 1:** generate a NEW Tauri updater Ed25519 keypair (the command, where
  the new key lives, how it's encrypted at rest).
- **Step 2:** update `codrag.key.pub` in the repo (the public verification
  half — safe to commit).
- **Step 3:** sign the next app-release bundles with the NEW key.
- **Step 4:** deprecate the OLD key — keep it valid for one release cycle so
  already-installed apps can still update, then remove. State the
  deprecation window.
- **Step 5:** scrub the OLD `codrag.key` from origin history (filter-repo /
  BFG) — note this rewrites history and requires coordinated force-push +
  re-clone by all clones; flag as the heaviest step.
- **CI gate plan:** the exact `.github/workflows/*.yml` addition (or
  `scripts/` pre-push hook) to make `build_public_mirror.py` mandatory before
  any push that would publish.
Frame the ED-6 decision: (a) rotate keypair + wire CI gate (both),
(b) wire CI gate only, defer rotation, (c) status quo. Recommended default:
(a).

## What to PRODUCE

Write your findings to:
**`docs/Phase142_OSS-First/DEEP_RESEARCH_D_CODRAG_KEY_FINDINGS.md`**

Structure:
1. **History scan results** — every secret/private-key hit with
   `commit:file:line`; the definitive "codrag.key is the only one" (or not)
   statement.
2. **Public-mirror gate state** — CI-wired (yes/no) with evidence; the
   fresh-initial-commit confirmation with `build_public_mirror.py` line
   cites.
3. **The two-keys distinction** — Tauri updater key vs license verification
   key, so Eric doesn't conflate them.
4. **Rotation plan** — steps 1-5 above, actionable, with commands.
5. **CI-gate plan** — the exact workflow/hook addition.
6. **Framed ED-6 decision** — options + recommended default.

## STOP and surface to Eric when

- The history scan is complete + the gate-wiring state is confirmed.
- The rotation + CI-gate plan is written.
- You have NOT generated any key, NOT rotated anything, NOT force-pushed,
  NOT rewrote history, NOT modified `.github/workflows/` (the CI-gate plan
  is a PROPOSAL in your doc, not an applied change).

## Commit

Commit your findings doc locally (one commit):
`docs(phase142): deep-research D — codrag.key history scan + rotation plan`.
**NEVER push** (no `[deploy]` signal). **No Co-Authored-By.** **Never `git
commit --amend` on main** — verify `git log -1` is yours before any history
op (concurrent sessions collide).