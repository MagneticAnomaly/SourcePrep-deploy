# Priority Channels — Business-Aligned Distribution Plan

## How this doc relates to the others
- **RESEARCH_FRAMEWORK.md** — the generic repeatable system (taxonomy, rubric, workflow)
- **This doc** — the prioritized, business-aligned application of that framework to CoDRAG specifically
- **Phase10 docs** — business goals, ICP, pricing, competitive positioning (source of truth)
- **COPY_DECK.md** — approved messaging pillars and copy variants

This doc answers: **Where should we focus first, what should we say there, and why?**

---

## Business objectives driving channel selection

From Phase 10 + Pricing Strategy:

| # | Objective | Metric |
|---|-----------|--------|
| B1 | Drive Free-tier downloads (top of funnel) | Install count |
| B2 | Convert Free → Starter → Pro (revenue) | Conversion rate, LTV |
| B3 | Establish "local-first context engine" positioning | Share of voice in relevant communities |
| B4 | Build trust credibility (privacy, no cloud, BYOK) | Sentiment, repeat engagement |
| B5 | Attract enterprise/team inbound leads | Demo requests, contact form fills |
| B6 | SEO for long-tail "code search", "MCP tools", "local RAG" queries | Organic traffic |

**Primary ICP** (Phase 10): Solo developers using Cursor / Windsurf / Claude Code / Copilot.
**Secondary ICP**: Privacy-conscious devs, LLM infra builders, team leads evaluating dev tooling.

---

## CoDRAG's 5 messaging pillars (from COPY_DECK + Phase 10)

These are the core claims. Every channel placement should use 1–2 of these as the "hook."

| ID | Pillar | One-liner |
|----|--------|-----------|
| M1 | **No LLM required** | The structural trace index works standalone — no Ollama, no cloud API needed for core value |
| M2 | **Local-first trust** | Your code stays on your machine. No upload, no telemetry, no mandatory cloud |
| M3 | **AI sees files, not structure** | CoDRAG is the mediation layer — it gives AI tools the *right* code, not just *more* code |
| M4 | **MCP companion, not another IDE** | Works with Cursor, Windsurf, VS Code, Claude Desktop — plugs into your existing workflow |
| M5 | **Pay once, own forever ($79)** | Perpetual license disrupts subscription fatigue. No token markup. BYOK at cost |

---

## Tier 0: "Must activate" channels (highest business impact)

These channels have the strongest overlap with our primary ICP and the highest leverage per post.

### 0A. r/LocalLLaMA
- **Why #1**: This is the single highest-concentration community of developers running local AI tooling. Perfect ICP overlap (A1+A2+A4). Posts about local-first tools routinely get 200–1000+ upvotes.
- **Size**: ~750K+ members (as of early 2026)
- **Self-promo tolerance**: HIGH — "I built this" posts are celebrated when they show technical depth
- **Hook pillars**: M1 (no LLM required) + M2 (local-first) + M3 (structural trace vs naive RAG)
- **Angle**: "I built a local code context engine that works without any LLM — here's how the structural trace index works" (technical, show architecture, invite feedback)
- **What works here**: Technical deep-dives, architecture diagrams, benchmark comparisons, "how it works under the hood" posts. Screenshots of dashboards. Performance numbers.
- **What to avoid**: Marketing-speak, vague claims, anything that looks like an ad
- **Business objective**: B1 (downloads) + B3 (positioning)
- **Format**: F1 (text-native discussion)
- **Trust ramp**: 1 week commenting on local model threads → first post

### 0B. Hacker News (Show HN)
- **Why**: The canonical launch surface for developer tools. One front-page hit can drive thousands of installs and set the narrative for how the product is perceived industry-wide.
- **Size**: ~10M monthly uniques
- **Self-promo tolerance**: Show HN is explicitly for this purpose
- **Hook pillars**: M3 (AI sees files, not structure) + M4 (MCP companion) + M1 (no LLM required)
- **Angle**: "Show HN: CoDRAG — local-first structural code context for AI coding tools (no LLM required)" — lead with the surprising technical claim, link to docs/GitHub
- **What works here**: Concise, honest, technically interesting. Respond to every comment in the first 3 hours. Show working demo or screenshots.
- **What to avoid**: Hype, unsubstantiated claims, ignoring comments
- **Business objective**: B1 (downloads) + B3 (positioning) + B5 (enterprise inbound)
- **Format**: F3 (launch post) with F2 (companion blog post linked)
- **Trust ramp**: None needed; Show HN is the format. But have a strong companion article ready.

### 0C. r/cursor + r/windsurf (IDE-specific subreddits)
- **Why**: These are literally our ICP's home communities. Every member is an AI-assisted developer.
- **Size**: r/cursor ~50K+, r/windsurf smaller but growing
- **Self-promo tolerance**: MODERATE — need to frame as "useful tool for Cursor users" not "buy my product"
- **Hook pillars**: M4 (MCP companion) + M3 (AI sees files, not structure)
- **Angle**: "I built an MCP server that gives Cursor structural context about your codebase — not just file chunks" (position as a Cursor enhancement, not a competitor)
- **What works here**: "How I improved my Cursor workflow" framing, before/after examples, MCP setup guides
- **What to avoid**: Positioning as a Cursor replacement, pure link drops
- **Business objective**: B1 (downloads) + B2 (conversion — these users already pay for tools)
- **Format**: F1 (discussion) or F4 (guide)
- **Trust ramp**: 1–2 weeks of helpful commenting on "Cursor tips" threads

### 0D. codrag.io/blog → syndicated to dev.to + Medium
- **Why**: Canonical long-form content you fully control. SEO anchor. Syndication target for all discussion posts.
- **Hook pillars**: All (M1–M5), varies per article
- **Angle**: Technical deep-dives, architecture posts, "how we built X" series, comparison posts
- **Business objective**: B6 (SEO) + B1 (downloads via organic) + B3 (positioning)
- **Format**: F2 (technical deep dive) + F4 (guides)
- **Trust ramp**: N/A (your own property)
- **Syndication flow**: Publish on codrag.io/blog first (canonical URL) → cross-post to dev.to (supports canonical URL) → adapt for Medium

---

## Tier 1: "High value, activate in month 1–2"

### 1A. r/programming
- **Size**: ~6M+ members
- **Self-promo tolerance**: LOW — strictly no "here's my tool" posts. But "interesting technical discussion" posts that happen to reference your tool can work.
- **Hook pillars**: M3 (AI sees files, not structure — framed as a CS/architecture discussion)
- **Angle**: "Why vector search alone fails for code retrieval — and what structural trace graphs add" (educational, not promotional)
- **Business objective**: B3 (positioning) + B6 (SEO via discussion links)
- **Format**: F1 (text-native, no self-promo links in body)
- **Trust ramp**: 2+ weeks of commenting. This community is hostile to drive-by posters.

### 1B. r/selfhosted
- **Size**: ~400K+
- **Self-promo tolerance**: MODERATE — "I made this self-hosted tool" posts are common
- **Hook pillars**: M2 (local-first, no cloud) + M1 (no LLM required)
- **Angle**: "I built a self-hosted code context engine — no cloud, no API keys needed for core features"
- **Business objective**: B1 (downloads) + B4 (trust credibility)
- **Format**: F1 (discussion)

### 1C. r/MachineLearning
- **Size**: ~3M+
- **Self-promo tolerance**: MODERATE — [Project] flair exists for tool posts
- **Hook pillars**: M3 (structural trace vs naive RAG) + M1 (no LLM required for core)
- **Angle**: "[P] Structural trace graphs for code retrieval — beyond vector similarity" (research-adjacent framing)
- **Business objective**: B3 (positioning among ML practitioners)
- **Format**: F1 (discussion with [Project] flair)

### 1D. dev.to (primary long-form platform)
- **Why**: Better than Medium for devtools. Supports canonical URLs. Built-in dev audience. Tags drive discovery.
- **Self-promo tolerance**: HIGH — "here's what I built" is the culture
- **Hook pillars**: All (M1–M5), article-dependent
- **Angle**: Series: "Building a local-first code context engine" (build-in-public style)
- **Business objective**: B6 (SEO) + B1 (downloads) + B3 (positioning)
- **Format**: F2 (deep dive) + F4 (guides)
- **Key tags to target**: #ai, #devtools, #opensource, #productivity, #mcp, #rag, #vscode, #coding

### 1E. Product Hunt
- **Why**: One-time launch event. High visibility if executed well. Drives press/newsletter coverage.
- **Self-promo tolerance**: This IS the purpose
- **Hook pillars**: M4 (MCP companion) + M5 (pay once $79) + M2 (local-first)
- **Angle**: "CoDRAG — Local-first structural code context for AI coding tools"
- **Business objective**: B1 (downloads) + B3 (positioning) + B5 (enterprise inbound)
- **Format**: F3 (launch)
- **Timing**: Coordinate with v1.0 release. Tuesday–Thursday launch. Have HN Show post same week.

---

## Tier 2: "Valuable, activate in month 2–3"

### 2A. r/neovim + r/vscode
- **Hook**: MCP integration / "make your editor's AI smarter"
- **Pillar**: M4
- **Business objective**: B1

### 2B. r/devops + r/kubernetes
- **Hook**: "Local code context for platform teams" / no cloud dependency
- **Pillar**: M2 + M4
- **Business objective**: B5 (team/enterprise leads)

### 2C. r/ClaudeAI + r/OpenAI
- **Hook**: "Better context for Claude/ChatGPT code tasks" / MCP integration
- **Pillar**: M4 + M3
- **Business objective**: B1
- **Risk**: These communities shift fast; check current rules before posting

### 2D. r/rust + r/Python
- **Hook**: "We built the indexer in Rust with PyO3" (r/rust) / "Python devtools" (r/Python)
- **Pillar**: Technical interest, not product marketing
- **Business objective**: B3 + B1
- **Caveat**: Only post when you have a genuinely interesting technical story about the Rust engine or Python integration

### 2E. Lobsters
- **Why**: High-signal, small community of senior engineers. One post can set narrative.
- **Self-promo tolerance**: Moderate (invite-only, so you need an invite first)
- **Hook pillar**: M3 (structural trace — technical depth appreciated here)
- **Business objective**: B3 + B5
- **Action needed**: Get an invite. Research who can invite you.

### 2F. Indie Hackers
- **Hook**: Build-in-public narrative, pricing strategy discussion, solo founder story
- **Pillar**: M5 (perpetual license model) + founder journey
- **Business objective**: B3 + B2 (pricing validation)

### 2G. LinkedIn
- **Hook**: "Why we chose perpetual licensing for a dev tool in 2026" / enterprise-facing thought leadership
- **Pillar**: M2 + M5
- **Business objective**: B5 (enterprise/team inbound)
- **Format**: F5 (short posts) + link to blog

### 2H. X / Bluesky
- **Hook**: Short demos, GIFs, release announcements, amplify blog posts
- **Pillar**: All (varies)
- **Business objective**: B1 + B3 (amplification)
- **Format**: F5 (short demo clips)

---

## Tier 3: "Long-tail discovery surfaces"

### 3A. GitHub Awesome Lists (submit PRs)
Targets to research and submit to:
- `awesome-mcp-servers` — CoDRAG ships an MCP server
- `awesome-rag` / `awesome-retrieval-augmented-generation`
- `awesome-developer-tools`
- `awesome-local-first`
- `awesome-rust` (if Rust engine is noteworthy)
- `awesome-vscode` (VS Code extension)

### 3B. Newsletters that accept submissions
Research and pitch to:
- **TLDR** (tldr.tech) — dev section
- **Console.dev** — curates new dev tools weekly
- **Changelog** (changelog.com) — dev tools news
- **Ben's Bites** / **The Rundown AI** — AI tools
- **DevOps Weekly** / **SRE Weekly** — if platform angle resonates
- **Hacker Newsletter** — curates top HN posts (get on HN first)
- **This Week in Rust** — if Rust engine story is strong

### 3C. Podcasts + YouTube channels to pitch
Research and track:
- **Changelog Podcast** (The Changelog)
- **Syntax.fm** (devtools focus)
- **devtools.fm**
- **Lex Fridman** (aspirational, long-shot)
- **Fireship** (YouTube — devtools explainers)
- **Theo / t3.gg** (YouTube — devtools opinions)
- **ThePrimeagen** (YouTube/Twitch — tooling nerd audience)
- **ArjanCodes** (YouTube — Python devtools)

### 3D. Discord / Slack communities
Research membership + posting rules:
- **Cursor Discord** (official)
- **Windsurf Discord** (official)
- **Claude Discord** (Anthropic)
- **LocalLLaMA Discord**
- **MLOps Community Slack**
- **Rands Leadership Slack** (for team/enterprise angle)

### 3E. Medium Publications to research
- **Towards Data Science** (ML/AI angle)
- **Better Programming** (devtools)
- **Level Up Coding**
- **The Startup** (founder story)
- **Towards AI**

For each: check submission guidelines, editor contact, topic fit.

---

## Message–Channel Matrix

This matrix maps which messaging pillar to lead with for each channel type.

| Channel Type | Lead Pillar | Secondary | Angle |
|-------------|-------------|-----------|-------|
| Local AI communities (r/LocalLLaMA) | M1 (No LLM required) | M2 (Local-first) | "Works without Ollama — structural trace is standalone" |
| IDE communities (r/cursor, r/windsurf, r/vscode) | M4 (MCP companion) | M3 (Structure > files) | "Make your AI IDE smarter with structural context" |
| Privacy/self-hosted (r/selfhosted, r/privacy) | M2 (Local-first trust) | M1 (No LLM required) | "Zero cloud, zero telemetry, zero API keys for core" |
| Programming general (r/programming, HN) | M3 (AI sees files, not structure) | M1 (No LLM required) | Educational/technical framing, not promotional |
| ML/AI (r/MachineLearning) | M3 (Structural trace) | M1 | Research-adjacent: "Beyond vector RAG for code" |
| Long-form (dev.to, Medium, blog) | M3 + M1 | All | Technical depth, architecture, benchmarks |
| Launch surfaces (Product Hunt, Show HN) | M4 (MCP companion) | M5 ($79 perpetual) | Product launch framing |
| Enterprise-adjacent (LinkedIn, newsletters) | M2 (Local-first) + M5 (Pricing) | M4 | "Why we built a perpetual-license local dev tool" |
| Directories (Awesome lists) | M4 (MCP) | M2 | Categorize correctly, minimal description |
| Social amplifiers (X, Bluesky) | F5 (demos/GIFs) | All | Short, visual, link to blog |

---

## Content types to prepare BEFORE activating channels

You should not post anywhere until these artifacts exist:

### Must-have (before any channel activation)
1. **codrag.io landing page** — live, with download CTA (or waitlist)
2. **GitHub repo or public demo** — something to link to that proves the product is real
3. **"Architecture overview" blog post** — the canonical "how CoDRAG works" article (syndicate everywhere)
4. **30-second screen recording / GIF** — shows: add repo → build → search → context via MCP
5. **README with clear "Getting Started"** — anyone who clicks through must be able to try it in <5 minutes

### Should-have (before Tier 0 activation)
6. **"Why structural trace beats vector search for code" article** — the technical thought-leadership piece
7. **"No LLM required" explainer** — addresses the surprising claim head-on
8. **Benchmark or comparison** — CoDRAG trace context vs naive RAG context (before/after example)
9. **Pricing page live** — so "pay once $79" pillar is verifiable

### Nice-to-have (before Tier 1 activation)
10. **"Build in public" series outline** — 5-part dev.to series plan
11. **Product Hunt assets** — tagline, screenshots, maker story
12. **Short video (2 min)** — more polished than the GIF, suitable for YouTube/social

---

## Phased rollout plan

### Phase A: Foundation (weeks 1–2)
- Prepare artifacts 1–5 above
- Create accounts on: Reddit (if not existing), dev.to, Product Hunt, HN
- Begin "trust ramp" commenting on r/LocalLLaMA, r/cursor, r/windsurf (helpful comments, no CoDRAG mentions yet)
- Research and document subreddit rules for all Tier 0 channels

### Phase B: Launch wave (weeks 3–4)
- Publish "Architecture overview" on codrag.io/blog
- Cross-post to dev.to
- Post Show HN
- Post to r/LocalLLaMA (same day or next day, different angle)
- Post to r/cursor + r/windsurf (MCP companion angle)
- Respond to ALL comments within 3 hours of each post

### Phase C: Amplification (weeks 5–8)
- Publish "Why structural trace beats vector search" article
- Activate Tier 1 channels (r/programming educational post, r/selfhosted, r/MachineLearning)
- Submit to awesome lists
- Pitch to 2–3 newsletters (Console.dev, TLDR, Changelog)
- Launch on Product Hunt (coordinate with a blog post + HN if timing works)
- Begin LinkedIn thought leadership posts

### Phase D: Sustained cadence (month 3+)
- 1 blog post every 2 weeks (codrag.io → syndicate)
- 1 Reddit post per week (rotate channels)
- Activate Tier 2 channels as content library grows
- Pitch podcasts
- Monitor and refresh channel database monthly

---

## Anti-patterns to avoid

- **"Spray and pray"**: Don't post the same text to 10 subreddits. Each community needs a tailored angle.
- **Link-first posts**: Lead with discussion/insight, not a URL.
- **Ignoring comments**: A post with zero author replies looks like spam.
- **Claiming what isn't shipped**: Don't market enterprise features that don't exist yet.
- **Over-indexing on reach**: A thoughtful post in r/LocalLLaMA (750K) is worth more than a post in r/technology (15M) where nobody cares about dev tools.
- **Forgetting the funnel**: Every post should have a clear next step for the reader (try it / read the docs / join the waitlist). Don't just "raise awareness."

---

## Success metrics (per phase)

| Phase | Primary metric | Target |
|-------|---------------|--------|
| A (Foundation) | Artifacts ready, accounts active, trust ramp started | Checklist complete |
| B (Launch) | HN upvotes, Reddit engagement, first-week installs | 100+ HN points, 50+ Reddit comments, 500+ installs |
| C (Amplification) | Newsletter features, awesome-list PRs merged, PH ranking | 2+ newsletter features, 3+ awesome-list merges, PH top 10 |
| D (Sustained) | Weekly active installs, Starter/Pro conversions | Steady install growth, first 50 paid conversions |

---

## Next steps
1. Research and document the specific rules for each Tier 0 subreddit (r/LocalLLaMA, r/cursor, r/windsurf)
2. Draft the "Architecture overview" blog post outline
3. Create the 30-second GIF/screen recording
4. Begin trust ramp commenting
