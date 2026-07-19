# Docs OSS-Readiness — Pass 4 Handoff / Starter Prompt (2026-07-19)

> Paste this into the next session after compaction. Self-contained. Supersedes
> the pass-3 handoff (`DOCS_OSS_HANDOFF_PROMPT_2026-07-19.md`) — read this one.

## Starter prompt

Continue the SourcePrep docs-site OSS-readiness work. **A background workflow
is in flight and its results have NOT landed yet** — your first job is to
collect them, not to re-run anything.

**Your default stance (unchanged):** assume every docs claim is WRONG until
proven true with BOTH (a) code AND (b) intention/design. If provable with
intention but NOT code — FLAG it "intention-only," don't silently fix. Never
edit a docs claim based on a memory note alone (pass 1 was burned by this).
Every edit must be license-neutral (root `LICENSE` still proprietary commercial;
Apache-2.0+DCO relicense decided but NOT applied). Docs must be MORE
conservative than marketing on forward-looking claims (marketing has ~14
pages asserting "Apache 2.0" in present tense — false today; docs must NOT
mirror).

**Issue tracker:** `docs/Phase142_OSS-First/DOCS_OSS_RESEARCH_AND_RECOMMENDATIONS_2026-07-18.md`
— §1-4 pass-2, §5 pass-3, §6 (to be written) pass-4. Eric-gated items are
E1–E15 (E14/E15 added in pass 3). Add new ones as E16+. Update
`DOCS_OSS_READINESS_AUDIT_2026-07-18.md` only if a prior claim is overturned.

## Commits so far (all LOCAL, NOT pushed — [deploy] gate)

- `a6ad1c7f` — pass 1 (6 fixes)
- `31e8d210` — pass 2 (16 fixes + 1 revert + research report)
- `f7cf743f` — pass-3 handoff prompt
- `f757168a` — (NOT mine — parallel session; AI-executable OSS-transition TODO + scrutiny amendments. Left untouched.)
- `04e108a0` — pass 3 audit-the-audit (24 safe-now fixes + V2 + research §5)

**46 total fixes applied across 3 passes.** Docs app `tsc --noEmit` clean.

## THE IN-FLIGHT WORKFLOW (collect this first)

A structural-scrutiny workflow was launched in the prior session and is
running in the background. It reverse-engineers docs claims against the real
app via prep MCP (`prep_search`/`prep_impact`) — catching what grep misses
(correct symbol + wrong wiring, re-routed pipelines, buried defaults,
moved tier-gating, "coming soon" features that exist but are stubbed/no-op'd).

- **Workflow tool task ID:** `wja7hmz90`
- **Workflow run ID:** `wf_60bc3c6d-ca8`
- **Output file (when complete):** `/private/tmp/claude-501/-Volumes-4TB-BAD-HumanAI-CoDRAG/3231170c-ee2f-49db-aad0-3c2da574d500/tasks/wja7hmz90.output`
- **Transcript dir:** `/Users/ericbintner/.claude/projects/-Volumes-4TB-BAD-HumanAI-CoDRAG/3231170c-ee2f-49db-aad0-3c2da574d500/subagents/workflows/wf_60bc3c6d-ca8/`
- **Script (to resume/re-run):** `/Users/ericbintner/.claude/projects/-Volumes-4TB-BAD-HumanAI-CoDRAG-websites-apps-docs/3231170c-ee2f-49db-aad0-3c2da574d500/workflows/scripts/docs-structural-scrutiny-wf_60bc3c6d-ca8.js`

9 clusters: embedder, feature-gate/tiers, compression/search, concurrency/AIMD,
CLI, MCP transport, audit pipeline, epistemic score, license/phone-home.
42 agents expected (~9 reverse-engineer → ~N verifiers → 1 synthesizer).

### First move (do this BEFORE anything else)

1. Check whether `wja7hmz90` has completed. Try `TaskOutput` with task_id
   `wja7hmz90`, block=false, timeout 5000. If still running, decide: wait
   (it takes ~15 min total) or read partial journals. If the session truly
   can't see the prior workflow's task, fall back to reading the journal
   files in the transcript dir (`journal.jsonl` has one `{"type":"result"}`
   line per completed agent — `cat` it to recover partial results).
2. If complete, read the output file and extract the `synthesis` field
   (a markdown "Pass 4" addendum). The structured counts
   (`confirmed_false`, `intention_only`, `refuted_true`, `insufficient`)
   tell you what landed.
3. **Reconcile against the actual working tree before applying ANY fix** —
   pass 3 was burned by worktree-base artifacts: the workflow agents run in
   worktrees branched from `origin/main` (`6dc42b85`) which does NOT include
   the local commits `a6ad1c7f`/`31e8d210`/`04e108a0`. So a "CONFIRMED-FALSE"
   finding may describe text the local working tree already fixed. For each
   finding, grep the working tree for the claim's distinctive text; if
   already gone, it's a worktree artifact — skip. If present, it's genuine.
4. Apply the genuine safe-now fixes (license-neutral, no Eric decision),
   file by file. `npm --prefix /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs run typecheck`
   must stay clean.
5. Append the synthesis as "## 6. Pass 4 — Structural scrutiny via prep MCP"
   to `DOCS_OSS_RESEARCH_AND_RECOMMENDATIONS_2026-07-18.md`. If the workflow
   didn't fully complete, hand-write §6 from whatever partial findings you
   recovered and mark it "(partial — workflow did not complete)".
6. Commit locally as `docs(phase142): pass-4 structural scrutiny via prep MCP`.
   No push. No Co-Authored-By.
7. Surface any new E16+ items to Eric with recommended options, alongside
   the still-open E1–E15 (status below).

**Dogfooding note to capture in §6:** call out whether prep MCP surfaced
structural errors grep genuinely missed (strong product signal — semantic >
lexical) or mostly confirmed what pass-3 already found (different signal —
grep was sufficient; prep's marginal value was lower here). Either is
actionable product feedback. Eric cares.

## E1–E15 status (still open — for Eric's batch decision)

All 13 original recommendations were spot-verified against current code in
the prior session — they hold. Full detail in the research doc §3 (E1–E13)
and §5.3 (E14–E15). In dependency order:

**Blocked on the relicense (Apache-2.0+DCO, decided NOT applied):**
- **E1** paperclip final Apache wording — hold for relicense + mirror allowlist.
- **E10** footer copyright line "All rights reserved" → Apache + NOTICE — bundle with relicense.
- **E14** `installation:81` paywall text is code-TRUE today; pass-1 neutral wording is in local commit `a6ad1c7f` (not on origin). Leave as-is; resolves when local commits reach origin alongside relicense.

**Phone-home cluster (code, then docs):**
- **E13** [code] remove `lemon_squeezy.py` 7-day polling + 30-day downgrade (sends machine name to api.lemonsqueezy.com) — part of Phase 146 license-crypto replacement.
- **E5** hedge `enterprise-deploy:247,252` "does not phone home / No internet required after activation" (present-tense, false today) → "Under OSS, no license calls…current crypto being replaced before launch." Coordinate with E13.

**Dead deploy links:**
- **E2** [clean win] `git ls-remote deploy` = zero refs. Run `scripts/publish_deploy_subtree.sh --promote` → 7 dead links resolve with zero docs edits.
- **E15** (new) same pages also reference `ghcr.io/magneticanomaly/prep-headless:{cpu,gpu}` (not published — no `app-v*` tag) + REPO_TOPOLOGY collapses to single storefront. INTENTION-ONLY. Decide: (1) populate + cut tag, or (2) rewrite links to "Enterprise on request."

**Product-positioning rewrites (Eric's call):**
- **E3** `team-sync:20` tier clause code-accurate (`feature_gate.py:60`) but backend not shippable at launch — reframe page as "coming soon," pull from sidebar. (Eric also owns keep-gated-vs-ungate `team_config`.)
- **E9** duplicate `/guides/team-sync` sidebar entry (`config/docs.ts:56` + `:64`) — drop standalone Deployment section. Merges with E3.
- **E4** compression section — body already rewritten pass-3; only heading relabel left (done in 3.3). **Effectively closed** unless Eric wants more voice work.
- **E6** `byok-batching:77` "No data sent to SourcePrep servers" → scope to BYOK code/analysis data + "LLM calls go direct to your provider."
- **E7** docs home lede `app/page.tsx:63` "build your epistemic graph" → lead with outcome, demote jargon. (Not the marketing hero; do-not-touch rule N/A, but high-visibility.)

**Cleanup (quick, Eric confirm):**
- **E8** delete `/guides/model-advisor` orphan (not in sidebar/sitemap, zero links) — diff vs `/guides/models`, port unique content, delete.
- **E11** keep dynamic-model-loading + byok-batching in nav (pass-2 corrected the "legacy" framing). **No action** unless Eric wants reorder.
- **E12** [code/UX] dashboard `AIModelsSettings.tsx:103` lists `nomic-embed-code` (404s; docs use `manutic/nomic-embed-code`); also `embedder.py:64` lacks the query/document prefixes line 59 has. Change slug + mirror prefixes.

**Quick-to-act-on once Eric says go:** E2, E8, E5+E13, E6, E7, E12.
**Relicense/mirror-gated:** E1, E10, E14, E15 (and the docs-vs-marketing license-framing question).

## Cross-cutting follow-ups flagged (out of docs-scope, for a parallel marketing sweep)

- Stale BERT/LLMLingua-2 copy in `packages/ui` (`CompetitorMatrix.tsx`, `TechStackMatrix.tsx:44`, `AIModelsSettings.tsx:1167`, `researchSources.ts`).
- No-suffix `…/SourcePrep` GitHub URL 404s: `mcp/paperclip/page.tsx:275` + marketing `links.ts:3` `GITHUB_REPO_URL` (separate from E15's `…/SourcePrep-deploy` cluster).
- Stale internal docstrings: `mcp_tools.py:633-637` (lingua/auto enum), `audit.py:7-8` (deleted endpoint), `scope_orchestrator.py:13` (stale Pro/Free — `feature_gate.py:65` authoritative: `auto_scope_rebuild` is `Tier.FREE`).

## Hard rules (unchanged)

- **No Co-Authored-By** trailers.
- **Commit per logical unit, locally; never push** without explicit deploy/ship signal (`[deploy]` gate; each push ~4 Netlify builds).
- **Docs typecheck clean** after every edit: `npm --prefix /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/docs run typecheck`.
- **Don't trust memory notes for code claims** — verify against the repo. Pass 1's two biggest errors came from misread memory notes.
- **SourcePrep = user-facing brand; prep = code-level.** Never `CoDRAG`/`RunPrep`/`~/.runprep` in public copy (docs src is clean — keep it so).
- **No image input** — this model crashes on Read of any PNG; verify text-only.
- **Scrutiny verifiers** (if you launch more workflows): read-only on git, `isolation: 'worktree'`. The workflow agents' worktrees branched from origin/main and miss local commits — ALWAYS reconcile findings against the actual working tree before applying.
- **Project prep_id:** `f1636374-abc6-410d-99ee-822120379e79` (pass to every prep MCP call).

## First move, restated (the one thing to do post-compact)

Collect the in-flight workflow `wja7hmz90`'s results → reconcile against the
working tree → apply genuine safe-now fixes → write §6 → commit `pass-4` →
surface E16+ to Eric. Then the remaining work is Eric's E1–E15 batch
decisions (above) + the upstream relicense/mirror tool.