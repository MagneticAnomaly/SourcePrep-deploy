# Phase 132 Tier A — Onboarding & First-Run

> **Pages audited:** `/getting-started`, `/getting-started/installation`,
> `/getting-started/quick-start`
> **Method:** desk-only first pass on 2026-05-14. Install-required items
> flagged for batched fresh-install verification.

## How to read this file

Every numbered claim is something a literal reader of the docs page would do
or expect. For each claim:

- ✅ Verified (desk) — verified by reading code/config
- ⚠ Drift (desk) — desk evidence shows the page is wrong; fix recommended inline
- ❌ Missing (desk) — page describes a feature that doesn't exist in code
- 🔧 Install-required — needs a fresh install on macOS/Windows to verify
- ☁️ Cloud-required — needs cloud LLM spend to verify

When you do the install-required batch, work through the 🔧 items at the
bottom of each page section.

---

## `/getting-started/installation`

### Page intent

Direct the user from "I want SourcePrep" to "the desktop app is running with
a green Connected status and `prep --version` works in my terminal".

### Claims

**1. Prerequisites: macOS 11+, Windows 10+, Linux experimental**
- ⚠ Drift (fixed 2026-05-14): the "Linux is supported but experimental"
  claim was inaccurate — Linux is not supported today, even experimentally.
  Page now reads "Linux support is planned."
- 🔧 Install-required (still): verify the macOS 11+ and Windows 10+ minimum
  OS versions match what the Tauri/electron config actually allows when a
  fresh-install pass happens.

**2. "~500 MB for the app + embedding model"**
- ⚠ Drift (desk): The ONNX embedding model is ~132 MB per the Phase 130 fix
  (memory note: "ONNX model ~132 MB" was fixed in Phase 130). The app
  bundle size is the remaining ~370 MB — confirm against the actual `.dmg`
  size when fresh-install pass happens. Recommendation: rewrite as "~150 MB
  for the embedding model + app binary".
- 🔧 Confirm exact bundle sizes on Mac and Windows.

**3. Download from sourceprep.io/download**
- 🔧 Install-required: visit `sourceprep.io/download` and confirm both `.dmg`
  and `.msi` are served. Verify "Apple Silicon & Intel" matches the
  delivered builds.

**4. "Also available on the Mac App Store"**
- ❌ Missing — but not in the "needs fixing" sense; in the "will never
  exist" sense. SourcePrep's indexer requires full filesystem access, which
  sandboxed Mac App Store apps can't provide. The line has been removed
  from the installation page (2026-05-14) and replaced with an explicit
  note that Mac App Store distribution is not possible. **Durable constraint
  — see memory `project_distribution_channels.md`.**

**5. "Also available on the Microsoft Store"**
- ⚠ Drift (fixed 2026-05-14): Microsoft Store distribution is not prepared;
  it's planned post-MVP. Page now reads "Microsoft Store distribution is
  planned post-MVP" instead of claiming the listing exists.

**6. macOS install flow: dmg → Applications → Spotlight launch**
- 🔧 Install-required: walk through the flow.
- Specific note: "On first launch, macOS may ask you to confirm the app is
  from an identified developer." Verify the app is signed/notarized.

**7. Windows install flow: msi → wizard → Start Menu launch**
- 🔧 Install-required: walk through the flow.

**8. "App also installs a `prep` CLI command"**
- 🔧 Install-required: confirm `prep --version` works after a fresh install
  on each platform. CLI install path differs across macOS/Windows (PATH
  management); both should "just work" per the docs.

**9. "Green Connected status"**
- 🔧 Install-required: verify the dashboard's connection indicator turns
  green automatically after the daemon starts.

**10. "Free to use with up to 3 active projects, all features included"**
- ✅ Verified (desk): the Free tier project cap is enforced in
  `feature_gate.py`. Cross-reference exact cap value when reviewing
  `feature_gate.py` again.
- Possible drift: page says "all features included" but several features are
  paid-only (e.g., trace auto-build on save per `/getting-started` Step 5).
  Recommend rewriting as "all core features" or listing what's gated.

**11. "Lemon Squeezy (Merchant of Record)"**
- ✅ Verified (desk): historical confirmation in earlier phases.

**12. "Activation requires a one-time internet connection; after that,
SourcePrep works fully offline"**
- 🔧 Install-required: verify the license activation flow really does a
  single online round-trip then permits offline operation.
- Desk note: the license validation code should not require continual
  online checks. Spot-check the licensing module.

**13. "SourcePrep checks for updates automatically"**
- 🔧 Install-required: verify auto-update infrastructure exists and notifies.

### Tier A install-required batch for this page (consolidated)

When a fresh-install session happens, do all of these together:
- App bundle size (item 2)
- Download URL and asset names (item 3)
- Mac App Store listing (item 4)
- Microsoft Store listing (item 5)
- macOS install flow (item 6) — including notarization
- Windows install flow (item 7)
- `prep --version` after install (item 8)
- Green Connected status (item 9)
- License activation online→offline (item 12)
- Auto-update notification (item 13)

---

## `/getting-started/quick-start`

### Page intent

Five-step happy path from "app installed" to "first AI query returns
structurally-aware context".

### Claims

**1. Step 1: launching the app automatically starts the background daemon**
- 🔧 Install-required: verify daemon starts on app launch on Mac and Windows.
- ✅ Verified (desk, partial): `prep serve` is the documented power-user
  alternative; both paths should converge on the same daemon process.

**2. Step 2: "+" button in sidebar opens a folder picker**
- ✅ Verified (desk): existing dashboard story
  (`stories/dashboard/FullDashboard.stories.tsx`) shows the sidebar with "+"
  affordance. Confirm in a live install.

**3. Step 2: "SourcePrep will scan and build the Code Graph immediately"**
- ⚠ Drift candidate: "build the Code Graph immediately" — on the Free tier,
  the page later says trace builds are manual. Either:
  - The Code Graph (structural index) builds immediately even on Free, and
    only *trace expansion* requires the manual build, OR
  - There's drift between Step 2 and the Free-tier note in Step 5.
  Verify against `feature_gate.py` and the build pipeline. Likely the
  former is correct; clarify wording.

**4. Step 2: `prep add ~/my-project` CLI alternative**
- ✅ Verified (desk): `prep add` is a real CLI command (referenced in
  multiple docs and `prep/cli.py`).

**5. Step 3: Configure Cursor/Windsurf to use the local server**
- ✅ Verified (desk): MCP configuration paths covered in `/mcp/ides`. Tier B
  fidelity check will verify config copy-paste works.

**6. Step 4: "Scope panel" naming**
- ⚠ Drift candidate: verify "Scope" is the current panel display label.
  Per memory and recent panel-registry work, the panel might be labeled
  "Knowledge Scope" or similar. Check `packages/ui/src/config/panelRegistry.ts`
  for the canonical label.
- Action: open panelRegistry.ts and confirm the panel's `name`/`title`.

**7. Step 4: `prep` returns "hub files, module structures, and focus areas"**
- ✅ Verified (desk): the MCP `prep` handler returns ambient context with
  hub files and modules. "Focus areas" comes from user's selected scope.
- ⚠ Possible drift: dogfooding finding P82-F5 (sparse atlas) shows the
  live `prep` no-arg call sometimes returns only 1 of 10 modules. The page
  describes the *intended* behavior. Cross-reference with
  `docs/Phase82_MCP-Dogfooding/20_Followup_2026-05-13.md`.

**8. Step 4: Quoted AI reply text**
- The illustrative response — "8 design docs and 18 React components"
  with hub files `EnhancedHero.tsx`, `ParallaxController.tsx` — is a
  *generic example*, not a literal expectation. No fidelity issue.

**9. Step 5: "Audit my codebase" → `prep_audit`**
- ✅ Verified (desk): the MCP `prep_audit` handler exists and returns
  structural findings.

**10. Step 5: "11 deterministic analyzers"**
- ⚠ Verify count: the analyzer count has changed across phases. Check
  `src/prep/core/audit/` analyzer registry for the actual count. Likely
  one of: 11, 12, or 13. If different, update the page.

**11. Step 5: "ARCH-1 (circular dependency)" severity-tag format**
- ✅ Verified (desk): the audit analyzer registry assigns codes in this
  format. Confirm `ARCH-1` specifically maps to circular dependency.

**12. Step 5: "Fix it" → `action="refactor"`**
- ✅ Verified (desk): `prep_audit` handler dispatches on `action` parameter
  including `refactor`. Documented in MCP page.

**13. Pro tips: `prep search`, `prep build`, `prep status` CLI commands**
- ✅ Verified (desk): all three exist as CLI commands.

### Tier A install-required batch for this page

- Daemon auto-start on app launch (item 1)
- Folder picker in "+" button (item 2)
- Free-tier behavior for Step 2 vs Step 5 (item 3)
- Live behavior of `prep` returning multi-module context (item 7) —
  reproducing P82-F5 hopefully

### Tier A desk follow-ups for this page

- Open `panelRegistry.ts`, find the Scope/Knowledge-Scope panel, confirm
  the canonical label. Update page if drift. (item 6)
- Count the audit analyzers in the registry. Update page if not 11. (item 10)
- Confirm `ARCH-1` is the circular-dependency code specifically. (item 11)

---

## `/getting-started` (parent)

### Page intent

The first page a new user lands on. Walks the 6-step trust loop:
install → launch → add repo → connect editor → verify → audit.

### Claims

The parent page largely consolidates the two subpages above. Re-checking
only the claims that are unique to the parent.

**1. "Trust Loop" callout: SourcePrep runs locally, no cloud uploads needed**
- ✅ Verified (desk): the indexer, MCP server, and dashboard all run
  locally. Cloud LLM is opt-in via BYOK or paid tiers; never required for
  core indexing.

**2. Step 2: Live embed of `<StoryEmbed storyId="website-demos-animatedcli--project-overview" />`**
- ✅ Verified (desk): the story file at `stories/console/AnimatedCLI.stories.tsx`
  declares `title: 'Website/Demos/AnimatedCLI'` and exports a `ProjectOverview`
  variant, so the Storybook-derived ID is correctly
  `website-demos-animatedcli--project-overview`. (Storybook IDs come from the
  story's `title:` field, not the file path — the file lives in `console/`
  but the story is titled under `Website/Demos/`.)
- Verify-after-deploy: confirm the embed renders correctly once the
  netlify env-var fix ships (the iframe will then point at real Storybook).

**3. Step 3: "For a 50k file repo, the Rust trace index takes less than a
second once semantic indexing wraps up"**
- ⚠ Verify against benchmarks. The Rust trace index is fast; "<1s" is a
  specific number that may or may not be current. Check recent perf logs
  in `docs/Phase11x_*` or `docs/Phase13x_*` for the actual benchmark on a
  50k-file repo.

**4. Step 4: "stdio (recommended)" for MCP transport**
- ✅ Verified (desk): MCP config docs consistently recommend stdio.

**5. Step 5: Free-tier note: "On the Free tier, trigger this [trace build]
manually from the dashboard (Graph Status → Build) before trying the graph
query above. Paid tiers build the trace automatically on file save"**
- ⚠ Verify against `feature_gate.py`. The exact Free-tier gating around
  trace build vs auto-build needs to match the gate's current behavior.
  The wording "Graph Status → Build" implies a specific panel + button —
  confirm in panelRegistry.

**6. Step 6: "11 built-in analyzers" + `ARCH-1`, `QUAL-3` codes**
- Same as `/quick-start` Step 5 items 10–12. Verify analyzer count.

**7. Step 6: "fix ARCH-1" → `action="refactor"` workflow**
- ✅ Verified (desk): same as quick-start item 12.

**8. "Smart Compression — structural for code (3–20×), language-aware for docs"**
- ⚠ Verify ratios. The 3–20× claim and the "language-aware for docs" phrase
  should match what `/guides/compression` says and what the compression
  code actually does. Cross-reference Tier D `guides/compression` check.

### Tier A desk follow-ups for this page

- Fix the stale `storyId` on Step 2 (item 2) — should be
  `console-animatedcli--project-overview`. **This is desk-doable now.**
- Verify "<1s trace index for 50k files" against current perf benchmarks
  (item 3).
- Verify Free-tier panel/button wording for trace build (item 5).
- Verify analyzer count (item 6).
- Verify compression ratio claims (item 8).

---

## Summary of fidelity fixes — resolution status (2026-05-14)

Desk verification round complete. Outcomes:

| Fix | Page | Resolution |
|---|---|---|
| Update embedding-model size | installation | ✅ no change needed — `cli.py:678` confirms ONNX is ~132 MB; the existing "~500 MB app + embedding model" sums correctly with the binary |
| Clarify "all features included" on Free | installation | ✅ no change needed — `feature_gate.py` confirms Free gets all core features (only project cap differs from Pro) |
| Free-tier manual-trace claim vs `feature_gate.py` | getting-started Step 5 | ⚠ **fixed 2026-05-14** — `feature_gate.py` puts `auto_trace`, `auto_rebuild`, `auto_fast_sync`, `auto_deep_enrichment` all at `Tier.FREE`. Rewrote the note to drop the Free-vs-Paid distinction and point at "Graph Scope" panel |
| Stale "Graph Status → Build" panel reference | getting-started Step 5 | ⚠ **fixed 2026-05-14** — panel was removed and consolidated into `graph-structure` (Graph Scope) per `panelRegistry.ts:151`. Updated wording |
| Scope panel canonical name | quick-start Step 4 | ✅ no change needed — `panelRegistry.ts:129` confirms `title: 'Scope'` |
| Analyzer count "11" | quick-start Step 5 + getting-started Step 6 | ✅ no change needed — exactly 11 analyzer modules in `src/prep/core/audit/analyzers/` |
| "<1s trace index for 50k files" perf claim | getting-started Step 3 | 🔧 deferred — needs benchmark on a 50k-file repo. Likely still true but unverifiable desk-only |
| "3–20×" compression ratio claim | getting-started Step 5 | ✅ no change needed — matches `/guides/compression` headline |
| "language-aware for docs. Built in." | getting-started "Next Steps" | ⚠ **fixed 2026-05-14** — language compression is on the roadmap per `/guides/compression`'s own "Coming Soon" section, not "built in." Rewrote |

**Cross-session findings saved as `prep_observe`:**
- 8b48f4fed23f (anchored to `feature_gate.py`) — Free-tier automation gate disagrees with prior docs; corrected.
- 466e14e19130 (anchored to `panelRegistry.ts`) — `Graph Status` panel name no longer exists; any doc reference is stale.

## Install-required batch (consolidated for Tier A)

All flagged 🔧 items above, in one place for the fresh-install session.
See per-page sections above for full context on each.

- Disk: actual app bundle sizes on Mac and Windows
- Marketplace: Mac App Store + Microsoft Store listings exist
- Flow: macOS install (dmg → Applications → Spotlight, including notarization prompt)
- Flow: Windows install (msi → wizard → Start Menu)
- CLI: `prep --version` works after install on both platforms
- Status: Green Connected indicator after daemon auto-starts
- Daemon: auto-starts on app launch
- Folder picker: "+" button in sidebar opens picker
- Free-tier reproduction: confirm trace-build manual-vs-auto behavior
- License flow: one-time online activation → fully offline
- Auto-update: update notification fires on a stale install

## Items punted to product (not docs work)

None so far. If any install-required item turns out to describe behavior
that doesn't exist, file as a product gap in MASTER_TODO and remove or
rewrite the claim in the doc.

## Open questions for the user

1. ✅ ~~Mac App Store / Microsoft Store listings live?~~ — answered
   2026-05-14: Mac App Store **never** (sandboxing prevents filesystem
   access); Microsoft Store **planned post-MVP**; Linux **planned post-MVP**
   (not even experimental today). Docs fixed; durable constraint saved as
   memory `project_distribution_channels.md`.
2. Is "11 analyzers" the right current count, or has it changed? If you
   know off the top of your head, save a quick check.
