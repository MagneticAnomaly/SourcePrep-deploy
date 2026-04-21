# Content Marketing Strategy

## Purpose
Define a content strategy that:
- attracts the right early adopters (solo devs using Cursor/Windsurf/Copilot)
- builds trust in local-first posture
- supports the A0 journeys (evaluate → install → succeed)

Reference:
- `../WORKFLOW_RESEARCH.md` (A0-J1, A0-J2)

## Positioning backbone (from Phase 10)
- Prep is not “another IDE”.
- Prep is a local-first context/index engine that plugs into existing AI IDE workflows via MCP.

References:
- `../Phase10_Business_And_Competitive_Research/COMPETITOR_LANDSCAPE.md`
- `../Phase10_Business_And_Competitive_Research/ACQUISITION_AND_PARTNERSHIPS.md`

## Target audiences (initial)
- A0/A1: individual devs evaluating AI tooling
- A3: agent users who care about bounded context
- A4: security/ops-conscious users who want local-only assurance

## Content pillars

### Pillar 1: Local-first trust
Goal:
- explain what stays local
- explicitly reject mandatory cloud/telemetry

Artifacts:
- “Local-first by default: what stays on disk”
- “Network mode is optional (and post-MVP): what that means”

### Pillar 2: The core loop (add → build → search → context)
Goal:
- show fast, verifiable outcomes

Artifacts:
- “First 10 minutes with Prep”
- “From search results to bounded context with citations”

### Pillar 3: IDE companion workflows (Cursor/Windsurf/Copilot)
Goal:
- demonstrate that Prep complements existing tools

Artifacts:
- “Using Prep with Cursor via MCP”
- “Using Prep with Windsurf via MCP”

### Pillar 4: Git and real codebase onboarding
Goal:
- show you understand real repo complexity (monorepo/polyrepo)

Artifacts:
- “Standalone vs embedded indexes: choosing the right mode”
- “Team onboarding via embedded mode (and how to avoid Git foot-guns)”

Reference:
- `../Phase10_Business_And_Competitive_Research/GIT_AND_CODEBASE_INTEGRATION.md`

### Pillar 5: Shipping reality (desktop distribution)
Goal:
- reduce friction and increase trust

Artifacts:
- “Why signed installers matter (macOS notarization, Windows SmartScreen)”

Reference:
- `../Phase11_Deployment/README.md`

## Funnel design

### Top-of-funnel (discovery)
Channels:
- GitHub README and release notes
- short posts on X/Bluesky/LinkedIn (developer-centric)
- Hacker News / Reddit (when the product is usable)

Top-of-funnel content:
- 1–2-minute clips/screenshots
- “problem → demo → link to docs”

### Mid-funnel (evaluation)
Channels:
- docs
- 1–3 deeper blog posts that answer trust questions

Mid-funnel content:
- installation + quickstart
- security posture page

### Bottom-of-funnel (activation)
Channels:
- download page
- “troubleshooting” and “known issues” docs

Activation content:
- “If it fails, here’s the recovery path”
- “How to verify you are local-only”

## Launch sequence (suggested)

### Phase 12 v0 (pre-release)
- Publish website placeholder with:
  - home
  - security
  - docs scaffold
  - download placeholder
- Publish 2 anchor pieces:
  - “What is Prep?” (positioning)
  - “Local-first by default” (trust)

### First public alpha
- Publish:
  - “First 10 minutes with Prep”
  - “Using Prep with Cursor/Windsurf via MCP” (even if partial)
- Add:
  - downloads + checksums + upgrade instructions
  - **Founder's Edition** license purchase flow (limited availability messaging)

### First stable release
- Publish:
  - changelog
  - 2 workflow case studies

## SEO target map (initial)
These are not commitments; they are candidate keywords to structure pages.

- “local first code search”
- “local RAG for codebase”
- “Cursor MCP tools”
- “Windsurf MCP server”
- “offline codebase search”
- “codebase context engine”

## Metrics (early, lightweight)
- docs quickstart completion rate (qualitative via feedback)
- download → first-run success rate (bug reports, support issues)
- common onboarding failure clusters

## Risks
- Over-producing content before the product is usable.
- Misrepresenting app-store readiness before sandbox + sidecar constraints are validated.
- Drifting language away from what is actually implemented.
