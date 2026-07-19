# Deep-Research Handoff — Session C: SBOM / vendored-copyleft scan (DR-1)

> **Self-contained starter prompt** for a dedicated follow-up AI session.
> Part of the 2026-07-19 legal+security+message audit follow-up. Full audit
> context: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-18.md`
> (read for background; everything you must DO is inline below).
>
> You are one of four parallel deep-research sessions (A=legal, B=security
> engineering, C=SBOM scan, D=codrag.key history). You do NOT need to wait on
> the others. **You run first / in parallel — you are the gate before the
> public-mirror push.**

## What this session is

**Tool-heavy filesystem scan** to close the SBOM / source-vendored-GPL /
LLM-generated-copyleft gap. Read-only on git. You install + run license
scanners, reconcile hits against `NOTICE`, and produce a per-component
verdict table. No code mutation (you may write a `deny.toml` for cargo if
absent — that's a config file, not source). This is the gate: **do NOT push
the public mirror until this closes.**

## Authorization note (read first)

The prior audit was told "do NOT install scancode-toolkit (~1GB)." **That
restriction is lifted for THIS session** — Eric approved the follow-up
deep-research dispatch that includes this scan. If the install environment
is constrained (disk, no network, sandbox), fall back to the **lighter
toolchain** described in step 1b below; flag the fallback in your output so
Eric knows the scan was partial.

## Hard rules

- **Read-only on git** (no `git` mutation; no worktree). You may create
  config files (`engine/deny.toml`, a `license-checker` config) and your
  output doc — those are plain file writes, not git ops. Commit them locally.
- **License-neutral.** The relicense to Apache-2.0 is DECIDED + APPLIED
  (`99315988`). Do NOT assert a new license; do NOT rewrite or remove any
  third-party code (that's an Eric/attorney decision per hit). You SCAN and
  REPORT; the reconciliation decisions are Eric's.
- **NO attorney budget.** For each non-permissive hit, present replace /
  attribute / rewrite as **options with a recommended default** — do not
  decide.
- **Do NOT push the public mirror** until the scan closes and Eric signs off.
- **Don't trust memory/notes for license claims** — read the actual license
  text of each dependency you flag.
- **prep MCP:** call `prep` (no args) first; project_id in
  `.sourceprep/AGENT_CONTEXT.md`. `prep_search` can help locate vendored
  code blobs (e.g. `docs/Phase13_Storybook`, `docs/Phase14_MCP-CLI
  codrag-mcp-template`, `packages/vscode`) — but license text has no graph,
  so the scanners + Read are your primary instruments.
- **Dogfooding:** note unhelpful/wrong prep results as product feedback.

## Item

### DR-1. SBOM / source-vendored-GPL / LLM-generated-CC-BY-SA scan

**Step 1a — scancode (full scan):** `pipx install scancode-toolkit` (~1GB),
then `scancode -clpeu --json-pp docs/Phase142_OSS-First/sbom_scan.json .` from
the repo root (or scope to the hotspots first if a full-tree scan is too
slow). **Hotspots** flagged by `docs/Phase142_OSS-First/LICENSE-AUDIT.md:80`:
`docs/Phase13_Storybook`, `docs/Phase14_MCP-CLI codrag-mcp-template`,
`packages/vscode`.

**Step 1b — lighter parallel toolchain (run these regardless, they're fast
and cross-check scancode):**
- `npm ls --json --workspaces` + a license-checker
  (`npx license-checker --json > docs/Phase142_OSS-First/npm_licenses.json`)
  on every npm workspace: `packages/ui`, `packages/vscode`,
  `packages/vscode/webview-ui`, `packages/paperclip-plugin-prep`,
  `src/prep/dashboard`, `websites/apps/{docs,marketing,support,payments}`.
- `cargo deny check licenses` on `engine/` — **add `engine/deny.toml`** if
  absent (config: allow = ["Apache-2.0","MIT","BSD-3-Clause","ISC","MPL-2.0",
  "Unicode-DFS-2016"]; flag everything else). Run `cargo deny check licenses`.
- `pip-licenses --from=mixed --format=markdown >
  docs/Phase142_OSS-First/pip_licenses.md` on `src/prep/` (via `.venv/bin/pip-
  licenses` if present).

**Step 2 — reconcile:** every GPL / AGPL / LGPL / CC-BY-SA / MPL hit against
`NOTICE:30-58`. For each, decide (as a *recommendation*, not a decision):
- Is it a **direct** dependency, **transitive**, or **vendored source**?
- **MPL-2.0** is weak-copyleft file-level: confirm the source-disclosure
  obligation for pathspec-covered files distributed in binary form
  (`pathspec` is the known MPL-2.0 dep — verify it's still the only
  weak-copyleft).
- For **vendored** or **LLM-generated** copyleft snippets in
  `docs/Phase13_Storybook` / `docs/Phase14_MCP-CLI codrag-mcp-template` /
  `packages/vscode`: read the actual content, classify the license, and
  recommend replace / attribute / rewrite.

**Step 3 — NOTICE reconciliation:** only AFTER the scan + reconciliation,
recommend removing the `NOTICE:22` DRAFT banner (Eric signs off). Also fix
the `NOTICE:27` stale pointer ("AI_WORK_TODO.md Stream 3" → point to
`docs/Phase142_OSS-First/README.md` or remove) — that's a safe fix-now you can
apply + commit.

**Step 4 — the open question:** is any vendored or model-generated copyleft
snippet hiding in the source tree? State a definitive yes/no with evidence.

## What to PRODUCE

Write your findings to:
**`docs/Phase142_OSS-First/DEEP_RESEARCH_C_SBOM_FINDINGS.md`**

Structure:
1. **Method** — which scanners ran (scancode full vs. lighter fallback),
   scope, any limitations.
2. **Per-component license table** — component / version / license /
  direct|transitive|vendored / NOTICE-listed? / verdict (ok | replace |
  attribute | rewrite | escalate).
3. **Non-permissive hits** — each with the replace/attribute/rewrite
  recommendation + the framed Eric/attorney decision.
4. **Vendored / LLM-generated scan** — the hotspot findings + the definitive
  yes/no on hidden copyleft.
5. **MPL-2.0 file-level obligation** — the pathspec analysis.
6. **NOTICE recommendations** — the DRAFT-banner removal recommendation +
  the `NOTICE:27` stale-pointer fix (applied + committed).
7. **Gate verdict** — "public mirror push: CLEAR / BLOCKED on N items" with
  the blocking list.

## STOP and surface to Eric when

- The scan + reconciliation is complete and the findings doc is written.
- Every non-permissive hit is a framed decision (replace / attribute /
  rewrite / escalate) with a recommended default.
- The gate verdict is stated (CLEAR or BLOCKED + list).
- You have NOT removed the NOTICE DRAFT banner (recommend only), NOT pushed
  the public mirror, NOT rewritten any third-party code.

## Commit

Commit your output docs + any config files (`engine/deny.toml`, the
`npm_licenses.json` / `pip_licenses.md` / `sbom_scan.json` if small enough —
otherwise add them to a scan-output dir and commit) locally, per logical
unit. Suggested:
`docs(phase142): deep-research C — SBOM scan: <clear|N hits>`.
**NEVER push** (no `[deploy]` signal). **No Co-Authored-By.** **Never `git
commit --amend` on main** (concurrent sessions collide — verify `git log -1`
is yours before any history op).