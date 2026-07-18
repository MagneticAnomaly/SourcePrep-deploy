# Handoff Prompt — OSS-Conversion Audit Review & Continuation

> **What this is:** a self-contained prompt to hand the 2026-07-17 OSS-conversion
> audit to another AI for review and continuation. Copy everything inside the
> `=== CUT HERE ===` block below into a fresh AI session (same repo, same
> working directory) and paste as the first message.
>
> **Repo:** `/Volumes/4TB-BAD/HumanAI/CoDRAG` (the SourcePrep repo; "CoDRAG" is a
> stale codename for the directory only — the project is **SourcePrep** / `prep`).
> **Branch at audit time:** `docs/feedback-concept-pipeline-audit-2026-07-11`.
> **Audit doc:** `docs/Phase142_OSS-First/AUDIT_2026-07-17.md` (private — strategic IP).

=== CUT HERE ===

You are picking up an in-progress open-source conversion for the **SourcePrep**
repository (local-first codebase intelligence MCP server; `prep` is the code/CLI
name, `SourcePrep` is the brand). The working directory is the repo root. A
prior AI session just completed a 16-agent research + adversarial-scrutiny
audit of the OSS-conversion state and wrote the findings to
`docs/Phase142_OSS-First/AUDIT_2026-07-17.md`. Your job is to (1) review that
audit for correctness, (2) verify its load-bearing claims against the live repo,
and (3) begin executing the recommended sequence — but ONLY the parts that are
safe, reversible, and do not require Eric's personal decisions.

## Read these first (in order)

1. `docs/Phase142_OSS-First/AUDIT_2026-07-17.md` — the audit you are reviewing.
   Read it fully. It is the authoritative summary of state.
2. `docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md` — the locked open-core tier
   plan (the monetization thesis: OSS the engine, sell the signed/notarized
   Mac/Win installer; anyone may compile from source unsigned for free).
3. `docs/Phase142_OSS-First/STRATEGY.md` and `RESEARCH_ROUND_2.md` — Path D
   strategy and the later research round that revises it (note: ROUND_2's
   prescribed 6-file revision was NEVER applied — the plan docs argue with
   themselves).
4. `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md` — the live blocker
   checklist.
5. `docs/Phase146_SecurityAudit/STATUS.md` + `PHASE2_LICENSE.md` — source of
   the hidden 4th blocker (committed Ed25519 private key + void license crypto).

## The state in one paragraph

The repo is **not shippable as OSS today.** Its actual legal state is
**proprietary commercial** (root `LICENSE` = "COMMERCIAL SOFTWARE LICENSE
AGREEMENT … NO REDISTRIBUTION"), while `pyproject.toml`/Cargo/3 npm packages
say MIT and the plan says Apache 2.0 — a three-way inconsistency no doc
reconciles. Phase 142 (strategy) is well-researched but internally
contradictory; Phase 143 (docs cleanup) is scaffolded with zero ADRs and no
curation tooling; Phase 144 (legal) has 2 open blockers (history scrub, IP
assignment) + a hidden 4th (committed private key + void license crypto) + an
untracked LICENSE-file swap. The Pro tier is not sellable (crypto void, backend
all stubs). The real bottleneck is ~6–9 weeks of strictly-serial solo work, NOT
the attorney (the 2026-06-15 reframe removed the attorney from the critical
path). The 90-day success window is mis-framed — prerequisites consume ~3–4.5
months before that clock starts.

## Your tasks

### Task A — Verify the audit's load-bearing claims against the live repo
Re-derive these independently (do not trust the audit blindly); confirm or
correct each, with file:line evidence:
- Root `LICENSE` is commercial proprietary; `pyproject.toml:10` says MIT; the
  planned outbound license is Apache 2.0.
- `scripts/generate_license.py:33` commits an Ed25519 private key
  (`DEFAULT_PRIV_KEY_HEX`); `src/prep/core/licensing.py:22` ships the RFC 8032
  §7.1 test vector as the public key; `PREP_LICENSE_PUBLIC_KEY` is comment-only;
  `src/prep/core/feature_gate.py` warn-but-accepts unsigned `license.json`.
  (Try to forge a `{tier:enterprise}` token against `verify_license_key()` —
  the audit claims this succeeds in a live venv. Use the project venv
  `.venv/bin/python`, never system python.)
- `src/prep/core/feature_gate.py` enforces FREE = 3 projects while docs say 2,
  3, and "retired."
- Pricing disagrees across `OPEN_CORE_SPLIT.md`, `PRODUCT_AND_BUSINESS_OVERVIEW.md`,
  and `DISTRIBUTION_AND_REVENUE_PLAN.md` (Pro $70 vs $79; Teams $15 vs $12;
  Enterprise $50 vs Custom; phantom $49 Founder's Edition + $30/yr renewal).
- The Tauri signing key `codrag.key` is reachable in git history (commit
  `5ba42227`); a worktree exists under `.claude/worktrees/` that would block
  any `git filter-repo`.
- `SECURITY.md` is untracked; `CONTRIBUTING.md` / CLA / DCO do not exist; no
  `NOTICE` file.
- The Lemon Squeezy customer-count question is unanswered — search
  `websites/apps/payments/`, `src/prep/core/lemon_squeezy.py`, and
  `PRODUCT_TIER_MAP` to confirm whether any purchase path is wired (wired ≠
  purchases occurred; the count itself is something only Eric can confirm).

Report any claim in the audit that you cannot reproduce, and any new issue you
find that the audit missed.

### Task B — Begin executing the "DO NOW, no attorney, no personal-decision"
items from the audit's §8 recommended sequence
Specifically, the items that are safe + reversible and do not require Eric's
decisions (do NOT touch the items in §9 open-questions — those are Eric's call):

1. **IP Assignment** — this is DIY but involves Eric signing a legal document;
   do NOT execute it, but you MAY draft the agreement from the Cooley GO / YC
   CIIAA / Stripe Atlas templates referenced in `docs/Phase144_LegalPreLaunch/RESEARCH.md`
   §3.2 and present it for Eric's signature. Mark it DRAFT.
2. **Ed25519 private key removal + key regen + license crypto fix** — this is
   engineering work and IS in your scope, but it is security-sensitive and
   touches the live tree + git history. Before doing it: confirm the plan with
   a written change plan (which files, which commits, how the private key leaves
   history given the fresh-initial-commit public-mirror decision). Do NOT push
   or force-push anything. Generate the new keypair with the private half
   offline; ship only the public half. Implement `PREP_LICENSE_PUBLIC_KEY` read;
   reject unsigned `license.json` for paid tiers. Add/adjust tests.
3. **LICENSE + metadata flip** — swap root `LICENSE` to verbatim Apache 2.0
   (Copyright (c) 2026 Magnetic Anomaly LLC), flip `pyproject.toml` to
   Apache-2.0, add license to `engine/crates/prep-selfheal/Cargo.toml`,
   reconcile the 9 npm `package.json` files, fix the stale `@codrag/ui`
   lockfile, fix paperclip-plugin tests asserting `manifest.id==='codrag'`,
   fix `docs_grounding.py` "RunPrep" attribution, fix `license.py`'s 7
   hardcoded `~/.runprep` sites to use the Phase 128 `.sourceprep` resolver.
   **Sequence this AFTER the IP Assignment is executed** so the LLC owns what
   Apache grants — i.e., draft it now but do not commit the LICENSE swap until
   Eric confirms the assignment is signed. The metadata flips (pyproject/Cargo/npm)
   can land now.
4. **USPTO TESS search** — you cannot run this (it needs Eric's browser + a
   filing decision); just remind Eric it is 30 min, free, and pending 6 weeks.
5. **Lemon Squeezy customer-count audit** — Eric's to answer, but you can
   inspect the code to confirm whether a purchase path is even wired and
   report that.
6. **Export-control self-classification (EAR §740.17(e) TSU)** — draft the
   classification memo + the ENC/LICENSE-EXPORT notice text; do not file
   anything.
7. **`scancode-toolkit` / `licensee detect` repo-wide license audit + draft
   `NOTICE` + `LICENSE-AUDIT.md` (private) + CI license-check gate** — in scope.
   Run the scans; draft NOTICE with attributions (networkx BSD-3, ONNX
   nomic-embed, tree-sitter grammars, Tremor, Radix, etc.).
8. **Reclassify Phase 144 blocker #2** — edit
   `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md` to drop the
   filter-repo/squash requirement for the OSS launch (per `OPERATIONS.md:18`'s
   fresh-initial-commit design) and split it into "remove live-tree secrets"
   + "verify no real secrets in private-repo history (informational)."
9. **Draft Phase 1 ToS/Privacy/EULA + CHARTER.md + ICLA.md + CCLA.md +
   CONTRIBUTING.md + CODE_OF_CONDUCT.md; git-track SECURITY.md** — in scope;
   draft from templates.
10. **Start the benchmark** (Phase 142 Part E.1 task selection + E.2 first
    vanilla data point) — in scope; this is the highest-leverage content work
    and does not depend on the public README/ADRs.
11. **Apply the RESEARCH_ROUND_2 six-file revision** to
    README/STRATEGY/ACQUIRER_MAP (lead with "senior IC role at frontier lab,"
    reframe acqui-hire as lottery-ticket bonus, 90d→12mo, applications Week 2,
    add SCRUTINY §21 for Cursor SDK). This edits strategy docs — do it, but
    flag clearly that it reverses the prior headline and that Eric should
    confirm he accepts the flip (it is his call per open-question #6; if he has
    not answered, make the edits reversible/mark them PROPOSED).
12. **Re-baseline the timeline** to prerequisite sprint ~6–9 weeks + launch
    sprint ~8–12 weeks; rewrite the Phase 142 dependency graph to show
    Phase 143+144 prerequisite gates explicitly.
13–19. **Phase 143 doc-cleanup work** (file-level triage, first 8 ADRs,
    `HISTORY.md`, `tools/build_public_mirror.py` with denylist-regex gate,
    CLAUDE.md frankness scrub, pricing reconciliation, Free-tier limit
    reconciliation, Phase 144 budget reconciliation) — in scope; these are
    substantial, prioritize the ADRs + HISTORY.md + the allowlist script
    (the credibility artifact + the leak-prevention tool).

### Task C — Do NOT do these without explicit Eric sign-off
- Filing anything with USPTO, BIS, or a court.
- Signing the IP Assignment (Eric signs both sides).
- Pushing to any remote, force-pushing, or running `git filter-repo` (remember:
  a live worktree under `.claude/worktrees/` blocks filter-repo anyway).
- Deciding Apache vs AGPL (open-question #4).
- Deciding whether to ship Pro at Phase 1 or defer (open-question #3).
- Deciding whether to file an AIMD-for-LLMs provisional (open-question #5).
- The actual public mirror push (§8 EXECUTE AT PUBLISH) — that is irrevocable
  and is Eric's one-shot event.
- Any change to the marketing home-page hero (off-limits per Eric's standing
  preference).

## Working rules (Eric's standing preferences — follow exactly)
- Use the project venv: `.venv/bin/python` and `.venv/bin/pytest`, never system
  python. `codrag`/`prep` is the project itself, not a pip dependency.
- Commit locally only; never push to `origin/main` (or any remote) without an
  explicit "push/deploy/ship" signal from Eric. Each push triggers 4 Netlify
  builds.
- No `Co-Authored-By` trailer in commits.
- Brand: **SourcePrep** = user-facing brand (UI, marketing, sourceprep.io,
  `.sourceprep/`); **prep** = code-level (CLI, imports, MCP tools, `@prep/*`,
  `PREP_*`). "CoDRAG" is a stale codename — never user-facing; remove it from
  any public-bound surface.
- SQLite WAL is unreliable on this USB drive; DELETE mode works.
- Restart the daemon before live validation (`prep serve` has no hot-reload;
  stale in-memory code silently passes validation against old behavior).
- Use the SourcePrep MCP tools available to you (`prep`, `prep_search`,
  `prep_impact`, `prep_audit`) — and critically evaluate their results as
  product feedback (this repo dogfoods its own product).

## How to start
Begin with Task A: read the audit, then independently verify the 8 load-bearing
claims listed above, reporting confirmed / corrected / not-reproduced for each
with file:line evidence. Then move to Task B item 7 (the license audit + NOTICE)
and item 2 (the Ed25519/crypto fix plan) as the first concrete execution work —
but present a written change plan for item 2 before touching security-sensitive
files or history. Surface open-question items to Eric as you reach them rather
than guessing.

=== CUT HERE ===

## Notes for Eric about this handoff prompt

- The prompt is scoped so the reviewing AI can **verify the audit and execute
  the safe, reversible, no-decision work** (license audit + NOTICE, Ed25519
  crypto fix, metadata flips, ADR/HISTORY authorship, the allowlist script,
  doc reconciliation, ToS/CLA drafts) while **deferring every decision that is
  yours** (Apache vs AGPL, Pro-at-launch vs defer, patent provisional,
  IP-assignment signature, the public push, USPTO/BIS filings).
- Before the AI runs the public-mirror push or signs the IP Assignment, it will
  come back to you — those are flagged as irrevocable / your-signature.
- The audit doc and this prompt are both **private strategic IP** — they must
  be in the Phase 143 "keep private" bucket and excluded from the public mirror
  by the `tools/build_public_mirror.py` denylist (codrag, ACQUIRER, SCRUTINY,
  DISTRIBUTION_AND_REVENUE_PLAN, CLAUDE.md, AUDIT_2026-07-17,
  HANDOFF_PROMPT_2026-07-17, RESEARCH_ROUND_2).