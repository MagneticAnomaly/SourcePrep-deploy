# Legal + Security + Message-Clarity Audit — Handoff / Starter Prompt (2026-07-19)

> Paste into the next session after compaction. Self-contained.
> Supersedes nothing (this is a NEW audit track, orthogonal to the 4 code-accuracy
> passes). Read alongside `DOCS_OSS_HANDOFF_PROMPT_2026-07-19-PASS4.md`.

## What this is (and is NOT)

Passes 1–4 were **code-accuracy** audits (does the docs claim match the code).
This is a **different, orthogonal lens**: a cross-surface **legal + security +
message-clarity** audit of all public sites + repo metadata. It catches what the
code-graph cannot — e.g., "marketing says Apache 2.0 present-tense while root
LICENSE says COMMERCIAL; package.json says Apache-2.0; docs stays conservative" —
a contradiction no per-file code check surfaces.

## The workflow is WRITTEN but NOT YET RUN

- **Script:** `docs/Phase142_OSS-First/legal-security-message-audit.workflow.js`
  (240 lines). Run it with:
  ```
  Workflow({ scriptPath: '/Volumes/4TB-BAD/HumanAI/CoDRAG/docs/Phase142_OSS-First/legal-security-message-audit.workflow.js' })
  ```
- **Structure:** 4 phases — Discovery (6 agents: docs/marketing/support/payments/repo-metadata + 1 code-posture ground-truth) → Find (3 lens agents: legal/security/message, consuming all discovery) → Verify (adversarial, per-finding, read-only, NO worktree) → Classify (synthesize). Expect ~40–80 agents depending on finding count.
- **NO worktree isolation** in this workflow (read-only audit reads the actual
  working tree directly) → avoids the pass-4 worktree-base artifact problem
  entirely. Verifiers are read-only on git (no `git` ops in prompts).

## Eric's scoping decisions (recorded from AskUserQuestion, 2026-07-19)

- **Surfaces:** ALL public sites + repo metadata — `websites/apps/{docs,marketing,support,payments}` + root `LICENSE/NOTICE/README.md/SECURITY.md/CONTRIBUTING.md/package.json/pyproject.toml/engine/Cargo.toml` + workspace `package.json` license fields.
- **Legal depth — NO ATTORNEY BUDGET.** So:
  - **Do/decide anything straightforward** ourselves (license-neutral edits, no legal act).
  - **Flag** anything needing deeper review for **a later AI deep-research pass** (the workflow emits a `FLAG-FOR-AI-DEEP-REVIEW` docket with research briefs).
  - **Eric-decision** items get a precise question + options.
- **Tooling:** no paid tools. `gitleaks`/`trufflehog` NOT installed (checked) — the code-posture agent does a **grep-based secret scan** and the follow-up docket flags "install gitleaks/trufflehog for a proper scan." Do **NOT** install `scancode-toolkit` (~1GB) yourself — the vendored-GPL source scan is a `flag-deep-review` item (DR-N), not a do-it-now.

## ⚠️ RELICENSE LANDED mid-session (re-verify before trusting the workflow's RULES)

While this handoff was being written, parallel commit **`99315988 license: swap
root LICENSE commercial-proprietary -> verbatim Apache-2.0`** landed. **Root
`LICENSE` is now Apache-2.0** (verified: first line "Apache License, Version 2.0").
This flips the audit's central premise:

- The "metadata=Apache, LICENSE=commercial" contradiction is **RESOLVED** — do not
  re-flag it as a defect. The audit should instead VERIFY the relicense is complete
  and consistent (LICENSE text correct/complete? DCO/NOTICE/CONTRIBUTING aligned?
  copyright-holder line correct? year range? `NOTICE` no longer says "All Rights
  Reserved"?).
- Marketing's present-tense "Apache 2.0" claims are now **TRUE** (no longer false).
  Docs' conservatism (not asserting Apache) is now UNDER-stating but still SAFE
  (more conservative than reality is fine; less conservative is not).
- **Pass-4 Eric-gated items now potentially actionable** (re-verify each against
  the new LICENSE before acting): E1 (paperclip Apache wording — unblocked), E10
  (footer copyright → Apache + NOTICE — unblocked), E14 (installation paywall —
  the LICENSE it deferred to is now Apache), E19 (installation:81 "build from
  source" is now TRUE, not a falsehood — the forward-looking-conservatism concern
  flips). E18 (Ed25519 placeholder key — UNCHANGED, still forgeable). S22/E5
  (phone-home — UNCHANGED).

**BEFORE running the workflow:** update its RULES block (see "First move" step 0
below) — the script still says "root LICENSE is still COMMERCIAL… All Rights
Reserved… Apache-2.0+DCO decided but NOT applied," which is now FALSE. Run an
Edit on `legal-security-message-audit.workflow.js` to fix those lines first, or
the audit will flag non-defects.

## Known/decided — do NOT re-flag (the workflow's RULES block lists these; verify still true)

- License crypto forgeable: `licensing.py:22 DEFAULT_PUBLIC_KEY_HEX` = RFC 8032 test vector; Phase 146 `CHANGE_PLAN_ed25519_crypto_fix.md` has the fix plan. Flag public copy claiming "Ed25519 secure license" present-tense (enterprise-deploy — already pass-4 E18).
- GPL deps resolved (igraph/leidenalg → networkx). Open legal gap = source-vendored-GPL/LLM-generated scan (scancode not installed) → `flag-deep-review`.
- `codrag.key` on origin; public mirror (`tools/build_public_mirror.py`) not built → flag the mirror build, do not history-scan.
- Pricing ladder (2026-07-18, PUSHED `0f1a66c2`, NOT deployed): OSS $0 / Pro $29 one-time / Teams $9/seat/mo / Enterprise $24/seat/mo (15-seat min). Check ALL surfaces match.
- Pass-4 (`e5d74fb7`) already fixed the docs-side cluster (ONNX-GPU, audit-logging-Available, LOD 2.5, compression dropdown, codebase-audit pipeline-connection, Anthropic-structured-output, byok subdivision, mcpSetup Windsurf path, AIModelsSettings LLMLingua-2, Roo/CodeGPT). Do not re-report.

## First move (post-compact)

0. **Re-verify the relicense state** (it landed mid-session at `99315988`):
   `head -3 LICENSE` → should be "Apache License, Version 2.0". Then **Edit
   `legal-security-message-audit.workflow.js`'s RULES block** to reflect it:
   replace "root LICENSE is still COMMERCIAL… All Rights Reserved… Apache-2.0+DCO
   decided but NOT applied" with "root LICENSE is now Apache-2.0 (commit 99315988);
   verify the relicense is complete/consistent rather than flag it as a
   contradiction." Commit that script fix before running. (See the ⚠️ section above
   for the full list of now-actionable pass-4 items.)
1. **Run the workflow** via the `Workflow` tool with the `scriptPath` above (it's a substantive multi-agent audit — ultracode is on, user explicitly asked for this methodology).
2. When it completes, read the `synthesis` field (the markdown addendum) + counts (`fix_now`, `flag_deep_review`, `eric_decision`, `refuted_true`).
3. **Apply the `fix-now` set** — license-neutral, no Eric/legal-act. File by file. The synthesis gives exact edits. Reconcile each against the working tree first (the workflow read the real tree, so artifacts are unlikely, but confirm before editing). Keep `npm --prefix /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs run typecheck` + `packages/ui` typecheck clean if those surfaces are touched.
4. **Write the audit doc** `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md` from the synthesis (all 7 sections: summary / fix-now / flag-deep-review / eric-decision / refuted / cross-surface claim matrix / dogfooding).
5. **Commit per logical unit, locally** (NO push — [deploy] gate; NO Co-Authored-By). Suggested message: `docs(phase142): legal+security+message audit — N fix-now + docket for AI deep-review`.
6. **Surface to Eric:** the fix-now count applied, the FLAG-FOR-AI-DEEP-REVIEW docket (DR-1…DR-N), and the new ERIC-DECISION items (ED-1…). Note which DR items Eric wants the follow-up AI to take first.
7. **Commit often** per the user's standing instruction (commit per task/logical unit).

## Hard rules (unchanged, carry from prior passes)

- **No Co-Authored-By** trailers. **Never `git commit --amend` on `main`** — concurrent sessions collide (pass-4 lesson; see `feedback_amend_collides_concurrent_sessions`). Verify `git log -1` is YOUR commit before any history op.
- **Commit per logical unit, locally; never push** without explicit deploy signal ([deploy] gate; each push ~4 Netlify builds).
- **License-neutral edits only.** Root LICENSE still proprietary; Apache-2.0+DCO decided not applied. No edit asserts a specific current OSS license.
- **Docs ≥ marketing conservative** on forward-looking claims.
- **Don't trust memory notes for code claims** — verify against the repo.
- **SourcePrep = brand; prep = code.** Never CoDRAG/RunPrep/~/.runprep in public copy.
- **No image input** (model crashes on PNG Read). **Scrutiny verifiers read-only on git.**
- **prep project_id:** `f1636374-abc6-410d-99ee-822120379e79`.

## Commits so far (all LOCAL, NOT pushed — [deploy] gate)

- `a6ad1c7f` pass 1 · `31e8d210` pass 2 · `04e108a0` pass 3 · `e5d74fb7` pass 4 (24 fixes).
- Plus parallel-session commits on main: `93f9c38d` (metadata MIT→Apache-2.0), `476e345d`, `56d496c9` (codename scrub), `328fe9ae` (README bet line) — NOT mine, leave untouched.
- **~70 docs/UI fixes across 4 passes. tsc clean.**

## After this audit lands

The flagged DR-N docket is the input for a **follow-up AI deep-research pass** (the
"let another AI research and deeply review the remaining and flagged items" Eric
named). That pass closes: vendored-GPL scan (scancode), full SBOM compatibility
matrix, trademark clearance, privacy-law compliance, patent preflight, and the
gitleaks/trufflehog secret scan over the emitted public mirror tree. It does NOT
need an attorney for the research; the final sign-off on trademark/patent/privacy
may, but that's downstream of the research.