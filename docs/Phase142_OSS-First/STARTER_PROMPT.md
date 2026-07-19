# Starter Prompt — OSS-First execution continuation (2026-07-19)

> Paste this into a fresh Claude Code session to continue the OSS-transition
> execution. Live working doc — updated as work lands.

## One-line state
Phase142 OSS-First transition is ~55% executed. The relicense to Apache-2.0
is **effective** (Eric: "we are open source now"); artifact alignment + plan-
doc reconciliation are in flight. All work committed locally, NOT pushed.

## Critical context from Eric (this session)
1. **Dead codenames have NO users** — `.runprep`/`codrag`/`RunPrep` are old
   dead names. Scrub them from code; do NOT preserve as "legacy fallback."
   (memory: `feedback_no_dead_codename_legacy.md`)
2. **The OSS relicense is EFFECTIVE now** — marketing "free and open source
   under Apache 2.0" copy is CORRECT, not a false claim. Do not soften to
   future tense. The root LICENSE swap + metadata flips are **artifact
   alignment**, not false-claim corrections.

## What's done (committed locally)
| Commit | What |
|---|---|
| `ab70186c` | OPEN_CORE_SPLIT reconciled to hardened decisions (Pro $29 one-time, Teams $9/$97, Ent $24/15-seat, DCO, stay MagneticAnomaly, Phase 1 OSS-only); marked pricing SoT |
| `5c70d33c` | Governance DRAFTs: NOTICE, CONTRIBUTING (DCO 1.1), CHARTER (permanent Apache, no source-available flip), CODE_OF_CONDUCT, SECURITY |
| `3d8ef4a7` | paperclip-plugin tests aligned to migrated source (codrag→prep); 21/21 green |
| `56d496c9` | Dead-codename scrub: removed .runprep fallback from license path (feature_gate + license.py 7 sites + lemon_squeezy + docs_grounding markers); 36+27 tests green |
| `476e345d` | Stream 6 reframed — Apache claim is CORRECT; 6.1 voided |
| `93f9c38d` | Metadata flip: all package metadata MIT→Apache-2.0 (pyproject+classifier, Cargo workspace+prep-selfheal, 13 npm package.json); cargo metadata + JSON validated; EXCLUDED websites/MagneticAnomaly (Eric's separate brand site) |
| `40749ea6` | README bet line + 90-day→12-month (D2/D11) |
| (earlier) | `d0ea35d3` LICENSING fix, `6d193a1f` 8.2 progress — superseded by later commits |

## ⚠️ Anomaly to investigate
Commit `e5d74fb7` ("pass-4 structural scrutiny via prep MCP — 24 code-verified
fixes") landed between `93f9c38d` and `40749ea6`. **I did not make this
commit.** Check `git show e5d74fb7 --stat` + reflog for origin (hook? leftover
agent/worktree?) before building on it.

## Next work (in priority order)
1. **Stream 5 remainder (in-flight):** DECISION_MEMO Part 1 D1 stale "CLA"
   text → add superseded marker (Part 0 = DCO); PRE_LAUNCH_BLOCKERS #2
   "git filter-repo/squash" → reclassify to live-tree secrets (D8 fresh-
   initial-commit); SCRUTINY §6 history options → mark D8 decided.
2. **Stream 2.1 root LICENSE swap → ASK ERIC:** swap root LICENSE to verbatim
   Apache-2.0 now (backdate IP Assignment to LLC formation) or sequence after
   the IP Assignment per LICENSING_RECOMMENDATION? Metadata flip is done; the
   file grant is the one remaining license artifact.
3. **Migration-chain scrub → surface to Eric:** the codrag→prep→runprep→
   sourceprep rename infra (`data_dir_migration.py`, `paths.py`, daemon/cli
   startup calls, ignore-globs in `roadmap_miner.py`/`repo_profile.py`/
   `projects/crud.py`, `audit_log.py:145`, `watcher.py:99`) — harmless no-ops,
   but the names are dead. Gut it or leave the safety net? Don't rip out
   unilaterally.
4. **`@codrag/ui` lockfile:** stale name field; `cd packages/ui && npm install
   --package-lock-only` (USB/network caution — flagged, not run).
5. **`feature_gate.py` module docstring** stale tier pricing ($7/month, $79,
   free=3 projects) — tied to MONTHLY tier still in code; needs tier-enum +
   pricing-SoT reconciliation (C3/D10), not a standalone edit.
6. **Stream 11 — public README** (repo root `README.md` is 20KB old internal
   content) — biggest remaining AI-runnable item; unblocks mirror push +
   fresh-clone smoke.
7. **Stream 3 — scancode + `oss-ci.yml` + fresh-clone smoke** — dependency-
   license audit (metadata flip is done; dep audit is separate).

## Live Eric-gated decisions still open
- **B2 LLC status** (operating agreement/EIN/bank) — gates IP Assignment → gates root LICENSE swap.
- **A5 Lemon Squeezy customer count** — "codrag never shipped to paying users" implies 0; confirm → write the all-clear.
- **A3 patent provisional on AIMD-for-LLMs** — decide BEFORE the public mirror push (EU absolute-novelty forfeiture at the public commit). No patent preflight gate exists yet.
- **B5 trademark** — run free USPTO search; file 1(b) before Show HN.

## Constraints (persist verbatim)
- Never push without explicit "push/deploy/ship" from Eric; [deploy]-flag gate verified in place.
- No Co-Authored-By trailer.
- Use `.venv/bin/python` + `.venv/bin/pytest`; prep is the project itself, not a pip dep.
- SQLite WAL unreliable on this USB drive; DELETE mode works.
- Restart daemon before live validation (no hot-reload).
- Don't touch the marketing home hero/tagline.
- Scrutiny verifiers: read-only on git + worktree isolation.
- Brand: SourcePrep=user-facing, prep=code-level, CoDRAG/RunPrep=dead.
- Commit per logical unit locally; push policy unchanged.
- glm-5.2:cloud crashes on Read of PNG — verify text-only.
- prep `project_id: f1636374-abc6-410d-99ee-822120379e79`.

## Entry point
Read this file + `docs/Phase142_OSS-First/AI_WORK_TODO.md` (the master TODO,
§5 has the scrutiny amendments) + the memory note `project_oss_audit_2026-07-19`.
Then pick up at "Next work" item 1 above.