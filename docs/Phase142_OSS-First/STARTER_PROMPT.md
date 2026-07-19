# Starter Prompt — OSS-First execution continuation (2026-07-19)

> Paste this into a fresh Claude Code session to continue the OSS-transition
> execution. Live working doc — updated as work lands.

## One-line state
Phase142 OSS-First transition is ~70% executed. The relicense to Apache-2.0
is **effective** (Eric: "we are open source now"); artifact alignment is
DONE (root LICENSE + metadata + README + governance DRAFTs), Stream 5
plan-doc reconciliation is DONE, Stream 3 dep-license audit gate is DONE,
the C2 public-mirror builder is DONE and has surfaced a 76-file scrub
worklist (the new front line). All work committed locally, NOT pushed.

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
| `27891ccb` | Stream 5 remainder: DECISION_MEMO Part 1 D1 CLA→DCO superseded banner; PRE_LAUNCH_BLOCKERS §2 history-scrub → live-tree-secrets (D8); SCRUTINY §6 marked DECIDED + exit-checklist [x] |
| `7bf962fb` | Public README: Apache-2.0 license badge (header) + License section (tail, links LICENSE/NOTICE/CONTRIBUTING/SECURITY + DCO `git commit -s`) |
| `703cd5d1` | TODO + starter-prompt progress — recorded Stream 5 status, resolved the `e5d74fb7` anomaly (author = Eric Bintner, his own parallel prep-MCP scrutiny pass) |
| `99315988` | Root LICENSE swap — commercial-proprietary → verbatim 201-line Apache-2.0 (the last license artifact; Eric: "yes update now", path A) |
| `b1fcbac1` | Stream 5 sub-items 5.5–5.10 closed — copyright holder, sourceprep org→MagneticAnomaly, AGPL-fallback→revenue-fallback + broken cross-ref fix, trademark blocker-status, Phase142 README status+files-table refresh. **Stream 5 fully closed.** |
| `c1456fbd` | **Stream 3 license-audit gate** — `engine/deny.toml` (cargo-deny) + `tools/check_python_licenses.py` + `tools/check_npm_licenses.mjs` (lockfile-based) + `.github/workflows/license-audit.yml`. All 3 gates pass live (107 py / 1097 npm / engine); 4 documented exceptions (PyInstaller, busboy, streamsearch, format). |
| `f3fef6ac` | **C2 `tools/build_public_mirror.py`** — allowlist + path denylist + content denylist-regex gate + dry-run + manifest. First dry-run: 1662 included, 6 path-excluded, 76 content-FLAGGED. **CAUGHT a live-tree `codrag.key`** at `src/prep/dashboard/src-tauri/.tauri/`. Manifest saved to `docs/Phase142_OSS-First/PUBLIC_MIRROR_MANIFEST_2026-07-19.json`. Mirror not emittable yet (76 hits = scrub worklist). |
| (earlier) | `d0ea35d3` LICENSING fix, `6d193a1f` 8.2 progress — superseded by later commits |

## ⚠️ Anomaly — RESOLVED 2026-07-19
Commit `e5d74fb7` ("pass-4 structural scrutiny via prep MCP — 24 code-verified
fixes") landed between `93f9c38d` and `40749ea6`. **Resolved:** `git show
e5d74fb7 --format="%an %ad"` shows author **Eric Bintner** (2026-07-19) — it
was Eric's own parallel prep-MCP scrutiny pass (OSS research doc + docs-site
pages), not a rogue hook or leftover agent. Tree is safe to build on.

## Next work (in priority order)
1. **Migration-chain / dead-codename scrub (76-file worklist)** —
   `tools/build_public_mirror.py` (f3fef6ac) flagged 76 files carrying
   `codrag`/`RunPrep`/`.runprep` or internal-doc markers. Full list in
   `docs/Phase142_OSS-First/PUBLIC_MIRROR_MANIFEST_2026-07-19.json` under
   `flagged`. This is now a concrete worklist, not a vague "surface to Eric":
   - **Live-tree secret (highest priority):** `src/prep/dashboard/src-tauri/.tauri/codrag.key`
     — a real codrag.key file in the tree (path-denylist excluded it from the
     mirror, but it's live in the workshop + already on origin). ROTATE the key
     + remove the file. Confirms PRE_LAUNCH_BLOCKERS §2.
   - **Core code dead-name leftovers (~30 files in src/prep/):** cli.py, server.py,
     paths.py, data_dir_migration.py, feature_gate.py, atlas/generator.py,
     repo_profile.py, watcher.py, lemon_squeezy.py, docs_grounding.py, etc.
     Some are the rename infra (harmless no-ops Eric was asked about) — DECIDE:
     gut the rename infra, or keep the safety net and add path-denylist entries
     so they don't block the mirror. The starter-prompt item "migration-chain
     scrub → surface to Eric" IS this decision.
   - **Tests (~40 files):** many intentionally assert `.codrag`/`.runprep` glob
     handling (test_walker_parity, test_data_dir_migration, test_phase128_*).
     These must STAY (they pin the rename behavior) but reference dead names —
     the content gate will keep flagging them. Resolution: add these test
     files to a `content_scan_allowlist` in build_public_mirror.py (they're
     legitimate), OR accept they're flagged and the mirror emit excludes
     flagged files.
   - **Public-facing:** `websites/apps/marketing/src/app/faq/page.tsx:143`
     references "CLAUDE.md or rules file" — scrub the CLAUDE.md mention.
2. **`@codrag/ui` lockfile:** stale name field; `cd packages/ui && npm install
   --package-lock-only` (USB/network caution — flagged, not run).
3. **`feature_gate.py` module docstring** stale tier pricing ($7/month, $79,
   free=3 projects) — tied to MONTHLY tier still in code; needs tier-enum +
   pricing-SoT reconciliation (C3/D10), not a standalone edit. The public
   README `PREP_TIER` env-var line lists a `starter` tier not in the hardened
   ladder ($0/$29/$9/$24) — same root cause.
4. **SCRUTINY §1–§20 disposition appendix** — the one deferred Stream 5 piece;
   a standalone deliverable (act-now / defer / accept-risk per section).
5. **Stream 1.1 — D7 IP Assignment draft** — formalizes LLC ownership of the
   copyright (Eric signs/files). Not strictly blocking since the root LICENSE
   swap already landed, but needed for diligence chain-of-title.
6. **Fresh-clone smoke test** — deferred to after the 76-file scrub; once the
   mirror is emittable (`build_public_mirror.py --emit` returns 0), clone it +
   run `pip install -e . && pytest` + `npm ci && npm run build` to verify the
   public tree builds clean. SCRUTINY §8 sub-item.

## Live Eric-gated decisions still open
- **B2 LLC status** (operating agreement/EIN/bank) — gates the IP Assignment execution (Stream 1.1). The root LICENSE swap already landed (99315988); the LLC copyright holder is named in NOTICE, formalized when the IP Assignment executes.
- **A5 Lemon Squeezy customer count** — "codrag never shipped to paying users" implies 0; confirm → write the all-clear.
- **A3 patent provisional on AIMD-for-LLMs** — decide BEFORE the public mirror push (EU absolute-novelty forfeiture at the public commit). No patent preflight gate exists yet.
- **B5 trademark** — run free USPTO search (B1); file 1(b) (B2) before Show HN.

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