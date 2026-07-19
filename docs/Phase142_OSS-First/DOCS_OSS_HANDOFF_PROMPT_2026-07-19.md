# Docs OSS-Readiness — Handoff / Starter Prompt (2026-07-19)

> Paste this into the next session after compaction. It is self-contained.

## Starter prompt

Continue the SourcePrep docs-site OSS-readiness work. Two passes are already
committed locally (`a6ad1c7f`, `31e8d210`) — **do not push**; the `[deploy]` gate
is in effect and each push triggers ~4 Netlify builds.

**Your default stance: assume every docs claim is WRONG until proven true.** A
claim counts as "true" only if you can prove it with BOTH (a) code AND
(b) intention/design (a spec, a plan doc, an Eric memory, or an architecture
decision). If you can prove a claim with **intention/design but NOT code** —
do not silently fix it; flag it to me explicitly as "intention says X, code
disagrees" and let me decide. Never edit a docs claim based on a memory note
alone (the first pass got burned by a misread memory note — see "Four corrected
errors" below).

**Keep a running issue tracker** in
`docs/Phase142_OSS-First/DOCS_OSS_RESEARCH_AND_RECOMMENDATIONS_2026-07-18.md`
(the §3 Eric-gated list is the current tracker; add new findings as E14+, and
move items out as they're resolved). Also update
`docs/Phase142_OSS-First/DOCS_OSS_READINESS_AUDIT_2026-07-18.md` if a
first-pass claim is later overturned.

**Correct the site documentation meticulously.** Every edit must be license-neutral
(assert no specific OSS license — the repo root `LICENSE` is still proprietary
commercial; the Apache-2.0+DCO relicense is decided but NOT applied). Docs must
be MORE conservative than marketing on forward-looking claims: marketing has
~14 pages asserting "free and open source under Apache 2.0" in present tense
(see `project_oss_audit_2026-07-19` memory), which is false today. Docs must NOT
mirror that.

## Where things stand

- **Pass 1 (`a6ad1c7f`):** 6 safe fixes — retired 3-project Free tier + Lemon
  Squeezy flow; "Free tier"→"No extra license"; `prep audit`→MCP/REST;
  footer GitHub SourcePrep-MCP→SourcePrep.
- **Pass 2 (`31e8d210`):** 16 safe fixes + 1 revert + this research report. Pass
  2 CORRECTED four pass-1 errors and found 3 false-claim surfaces pass 1 missed.
- **22 fixes total applied across 2 passes.** Docs app `tsc --noEmit` clean.

## Four corrected errors (read before trusting the first-pass audit)

1. **Ollama slug `manutic/nomic-embed-code` is CORRECT** (WebFetch verified,
   6,979 downloads; `nomic-ai/` does not publish it to Ollama). The dashboard
   `AIModelsSettings.tsx:103` is what's wrong (uses namespace-less
   `nomic-embed-code` that 404s) — Eric-gated code fix (E12).
2. **dynamic-model-loading + byok-batching are NOT legacy/hidden.** dynamic-model-loading
   was RESTORED 2026-05-14; byok-batching is actively wired. The "remove from
   nav" option is REJECTED. Both stay (E11).
3. **The phone-home cluster is a REAL falsehood, not "already fine."** Docs
   `enterprise-deploy:247` makes a STRONGER present-tense claim than marketing
   hedges (`lemon_squeezy.py` polls every 7 days). Eric-gated hedge (E5), gated
   on removing the legacy polling code (E13).
4. **Pass-1 M5 was reverted:** restored "Requires a Team or Enterprise license"
   on enterprise-deploy (the gate is real in `feature_gate.py:60`).

## The 13 Eric-gated recommendations (in dependency order — full detail in the research doc)

1. **E1** paperclip final Apache-2.0 wording — *after* relicense + mirror allowlist.
2. **E2** [clean win] populate `SourcePrep-deploy` repo via
   `scripts/publish_deploy_subtree.sh --promote` → all 7 dead links resolve with
   ZERO docs edits (aligns with deploy scripts being Enterprise-only, not in the
   OSS mirror).
3. **E3** team-sync guide → "coming soon" + pull from sidebar (backend not
   shippable at launch: no Docker image, Teams is Phase 2).
4. **E4** compression section final reframe (drop "Pro feature"/BERT; relabel
   Roadmap).
5. **E5** hedge phone-home claim (coordinated with E13).
6. **E6** BYOK privacy wording — scope "No data sent to SourcePrep servers" to
   BYOK code/analysis data.
7. **E7** docs home lede — demote "epistemic graph" jargon.
8. **E8** delete `/guides/model-advisor` orphan route (diff vs `/guides/models`
   first; port any unique content).
9. **E9** dedup the duplicate `/guides/team-sync` sidebar entry (overlaps E3).
10. **E10** footer copyright line — post-relicense, "All rights reserved" →
    Apache copyright + NOTICE.
11. **E11** keep dynamic-model-loading + byok-batching in nav (reject removal).
12. **E12** [code/UX] dashboard recommended-embedding-model slug
    (`AIModelsSettings.tsx:103`) → `manutic/nomic-embed-code`; also mirror
    query/document prefixes in `embedder.py:64`.
13. **E13** [code] remove legacy `lemon_squeezy.py` 7-day polling (unblocks E5).

**Upstream gates:** most of these are blocked on (a) applying the Apache-2.0+DCO
relicense and (b) building `tools/build_public_mirror.py`. A separate 66-agent
audit on 2026-07-19 (`project_oss_audit_2026-07-19` memory) found the same
license-identity inconsistency across the whole repo plus Pro-tier crypto
blockers — coordinate, don't duplicate.

## Hard rules

- **No Co-Authored-By** trailers in commits.
- **Commit per logical unit, locally; never push** without an explicit
  deploy/ship signal.
- **Docs app typecheck must stay clean** (`npm --prefix websites/apps/docs run
  typecheck`) after every edit.
- **Don't trust memory notes for code claims** — verify against the repo. The
  first pass's two biggest errors both came from misread memory notes.
- **SourcePrep = user-facing brand; prep = code-level.** Never `CoDRAG` /
  `RunPrep` / `~/.runprep` in public copy (docs site is currently clean — keep
  it so).
- **No image input** — this model crashes on Read of any PNG; verify text-only.

## First move

Re-read `DOCS_OSS_RESEARCH_AND_RECOMMENDATIONS_2026-07-18.md` §3, then pick the
next item you can prove with code+intention. Start with the ones that don't
need Eric's product decision and aren't blocked on the relicense/mirror tool:
work through any remaining blind spots from the pass-2 panel (the audit-the-audit
lens flagged the phone-home principle; check whether it flagged anything else
that wasn't yet applied), and verify each pass-2 fix actually landed by reading
the current file state. Then surface E1–E13 to me with your recommended option
for each so I can batch the Eric decisions.