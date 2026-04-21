# Copy Deck

## Purpose
Centralize copy and messaging variants for:
- website
- docs landing pages
- release notes

This copy is grounded in:
- Phase 10: positioning, competitor expectations, enterprise posture
- Phase 11: desktop distribution constraints and trust-building requirements

## One-sentence value prop (variants)
- Prep is a local-first context engine for your codebase that plugs into Cursor/Windsurf/Copilot workflows.
- Prep indexes your repo locally so you can search and generate bounded, cited context for AI coding assistants.
- Prep is your on-device companion for faster code understanding: search, context, and trace-assisted retrieval.
- Prep is a trust-first local indexing layer: freshness signals, inspectable citations, and bounded context outputs for agent workflows.
- Prep is designed for reliable agent loops: conservative output budgets, actionable errors, and local diagnostics.

## Hero headline (variants)
- Local-first codebase context for AI IDE workflows.
- Your codebase, searchable and citeable — without sending it to the cloud.
- Faster answers from your repo. Local-first. Bounded context.
- Trustworthy repo context: fresh, inspectable, and bounded.
- Inspectable local context for AI assistants — with citations and budgets.

## Hero subhead (variants)
- Add a repo, build an index, and generate context with citations — ready for Cursor/Windsurf via MCP.
- Designed to be trustworthy: right project, fresh index, verifiable sources.
- Desktop-first (macOS/Windows) with a local daemon and an inspectable UI.
- Built for reliability: freshness signals, storm-resistant auto-rebuild, and actionable diagnostics when something breaks.
- Bounded outputs by default: control context size, see sources, and keep agent loops stable.

## Primary CTA (variants)
Pre-release:
- Get updates
- Read the docs

Post-release:
- Download for macOS
- Download for Windows

## Homepage “How it works” block
- Add your repo
- Build the local index
- Stay fresh automatically (watch + debounce + storm control)
- Search and inspect results
- Generate bounded context with citations
- (Optional) Expand context using trace signals

## “Local-first” trust block
Copy:
- Prep is local-first by default. Your codebase and indexes stay on your machine.
- Shareable configs are secret-free by design; provider keys stay local.
- No mandatory telemetry; diagnostics are local unless you explicitly share them.
- Network mode (team server) is a roadmap item and will be explicit and opt-in.

## “Why not just use Cursor/Windsurf/Copilot?” block
Copy:
- Prep complements your AI IDE. It focuses on local indexing, inspectable retrieval, and bounded context assembly.
- It adds trust controls: freshness signals, citations, and diagnostics to answer “why is this result wrong?”.
- Use it as a reliable context source inside agent loops via MCP.

## Differentiation bullets (vs CLI-first local indexers)
- Prep is a desktop app with an inspectable UI: search results, citations, and project status are visible and debuggable.
- Freshness is first-class: clear stale/pending/building/throttled states and a storm-resistant auto-rebuild loop (debounce + dedupe + fallback polling).
- Curate what gets retrieved: control scoping and context assembly so assistants receive bounded, relevant context.
- Bounded outputs by default: conservative budgets and hard caps to keep agent loops stable.
- Actionable diagnostics: error codes + hints, provider health checks, and per-project logs when things go wrong.
- Config safety: shareable configs are secret-free by design; provider keys stay local.
- MCP that doesn't break: protect stdio JSON-RPC by keeping stdout clean; debug logs go to file when enabled.

## “Built for robustness” block
Copy:
- Prep is designed for the messy real world: watcher edge cases, large repos, flaky providers, and continuous changes.
- Freshness and recovery are explicit: you can see pending changes, build state, and what to do when a build fails.
- Index updates are atomic by design so search can rely on a last known-good snapshot.
- Diagnostics are first-class: error codes + hints, per-project logs, and copyable support bundles.

## Security & Privacy page copy

### Short statement
- Prep is designed to work without mandatory cloud services or telemetry.

### What stays local (draft list)
- Project settings
- Provider API keys/secrets (per-user)
- Index artifacts
- Search results and context outputs (where applicable)
- Build logs and diagnostics bundles (when enabled)

### What is opt-in
- Any network mode features
- Any future cloud add-ons
- Any optional telemetry or crash reports (if ever added)

## Download page copy

### Pre-release
- Prep is not publicly downloadable yet.
- When installers are available, they will be published with checksums and signed binaries.

### Release
- Signed installers for macOS and Windows.
- Upgrade-safe: your projects persist across updates.
- If an index becomes incompatible after an upgrade, Prep will prompt you to rebuild.

## Pricing page copy (placeholder)
- **Free Tier:** 1 active repo. Essential search. $0 forever.
- **Starter Pass:** 3 active repos. Real-time watchers. $29 / 4-months.
- **Pro License:** Unlimited repos. Trace Index. Full MCP.
  - **Founder's Edition:** $49 (Limited time). Yours forever.
  - **Standard:** $79.
- **Team:** Shared configuration. Centralized policy. $12/seat/mo.
- **Enterprise:** Air-gapped builds. Audit logs. Custom pricing.

**Key Message:** "Prep does not charge for tokens. You pay your provider directly at cost. No markup. No middleman."

## Docs landing page copy
- Start here if you want the fastest path to “search → cite → context”.
- The first 10 minutes: install → add a repo → build → search → context.
- When results look off: use freshness + citations + logs to debug “why is it wrong?” and recover quickly.

## Positioning footnotes (internal)
These messages align with research:
- Avoid competing as “another IDE” (Phase 10 competitor landscape).
- Emphasize enterprise expectations as roadmap (SSO/SCIM/audit), without claiming availability.
- Highlight distribution realities (signed installers, notarization/SmartScreen) to build trust.

References:
- `../Phase10_Business_And_Competitive_Research/COMPETITOR_LANDSCAPE.md`
- `../Phase10_Business_And_Competitive_Research/LOCAL_FIRST_ENTERPRISE_ECOSYSTEM.md`
- `../Phase11_Deployment/README.md`
