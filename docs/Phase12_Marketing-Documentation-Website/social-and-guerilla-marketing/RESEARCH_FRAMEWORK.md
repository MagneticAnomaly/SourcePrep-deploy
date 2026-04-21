# Social + Guerrilla Marketing Research Framework (Reddit-First)

## Purpose of this doc
This is a **research framework** for identifying **where** Prep content can be posted/distributed (and how to evaluate those options).

This pass explicitly does **not** write post copy.

## North-star objective
Build a repeatable system to:
- discover communities/publications/distribution surfaces
- quickly determine whether Prep can post there (and in what format)
- prioritize the highest-ROI channels
- maintain a “channel database” you can return to for each future content campaign

## Target audiences (so we can score channels)
- **A1: AI-assisted developers** (Cursor/Windsurf/Claude Code/Gemini CLI users)
- **A2: privacy/local-first developers** (skeptical of cloud upload)
- **A3: productivity/tooling nerds** (editors, CLIs, workflows)
- **A4: LLM infra builders** (RAG, embeddings, evals, MCP)
- **A5: teams/leads** (developer experience, guardrails, adoption)

## Content formats we should plan to place
- **F1: “Text-native discussion” posts** (best for Reddit, HN, Lobsters)
- **F2: “Technical deep dive”** (best for Medium/Substack/dev.to)
- **F3: “Launch/Update”** (Product Hunt, release posts, changelog amplification)
- **F4: “Guide”** (docs pages, canonical references, SEO)
- **F5: “Short demo”** (clips, GIFs, screenshots for X/LinkedIn/Bluesky)

## Channel taxonomy (the universe of places to research)
### Tier 1: High-signal dev discussion surfaces
- Reddit (subreddits)
- Hacker News (Show HN, Ask HN)
- Lobsters
- Indie Hackers
- Dev community forums (language-specific)

### Tier 2: Long-form publishing surfaces
- Medium (your profile + Medium Publications)
- dev.to
- Hashnode
- Substack
- Personal blog (runprep.io/blog) with syndication

### Tier 3: Social feeds (amplifiers, not primary)
- X
- LinkedIn
- Bluesky
- Mastodon

### Tier 4: Communities you can “join”, not just post
- Discord/Slack communities (AI dev, editor communities)
- GitHub Discussions (your own + allied projects)

### Tier 5: Directories + launch platforms
- Product Hunt
- Awesome lists (GitHub)
- “Tools” directories / newsletters

## Research workflow (repeatable)
### Step 0 — Define the campaign slice
For each campaign, pick:
- **Audience** (A1–A5)
- **Format** (F1–F5)
- **Core claim** (1-liner, not copy)
- **Proof artifact** (repo, demo video, docs page, benchmark, screenshots)

### Step 1 — Discover candidate channels
Use these discovery methods (do not guess; verify policies):
- Search queries:
  - `site:reddit.com "MCP" tool` / `site:reddit.com "RAG" local` / `site:reddit.com "code search" embeddings` / `site:reddit.com "developer tool" launch`
  - `"Show HN" code search tool` / `"Ask HN" local-first` / `"Lobsters" code graph`
  - `Medium publication developer tools` / `dev.to code search` / `hashnode RAG`
- “Adjacent product” and "Competitor" reconnaissance:
  - Find where similar tools get traction (e.g., local RAG tools, code search CLIs, AI IDE extensions, AST-based context engines, LSP wrappers, Sourcegraph, Continue.dev, Aider, OpenHands)
  - Track which communities allow “here’s what I built” posts and monitor competitor launch threads for feature gaps you can fill.
- Community directory scanning:
  - Reddit: related subreddits sidebar, mod lists, weekly promo threads
  - Medium: browse Publications by tag; check submission guidelines

### Step 2 — Evaluate each channel with a rubric
Score each candidate channel using the rubric below (0–5 each). Record evidence.

### Step 3 — Decide the allowed posting style
For each channel, choose one:
- **S1: Text-first discussion (no links in body)**
- **S2: Link-post allowed (docs/blog/GitHub)**
- **S3: Comment-link only** (post is discussion; link only when asked)
- **S4: Only in weekly promo thread**
- **S5: Not allowed** (rules too strict / audience mismatch)

### Step 4 — Placement plan
For the top channels:
- define the posting cadence (1x/week, 2x/month, etc.)
- define the “trust ramp” (commenting for 2 weeks before first post)
- define your success metric per channel (comments, signups, stars, demo requests)

## Evaluation rubric (0–5 each)
- **Audience fit**: does the community align with A1–A5?
- **Self-promo tolerance**: are “I built this” posts allowed?
- **Text-native friendliness**: can we post without external links?
- **Reach**: size/traffic (approx)
- **Engagement quality**: do threads get thoughtful replies?
- **Moderation clarity**: rules explicit + consistently enforced?
- **Effort**: time to craft a compliant post + respond
- **Risk**: chance of backlash, bans, reputation damage

Suggested total score: /40.

## Tracking template (recommended spreadsheet columns)
- Channel Name
- URL
- Type (Reddit / HN / Medium Pub / etc.)
- Audience tags (A1–A5)
- Allowed formats (F1–F5)
- Posting style (S1–S5)
- Self-promo rule excerpt (quote + link)
- Restrictions (account age, karma, flair requirements, link limits)
- Best-performing post patterns (3 example links)
- Common hooks/topics (observed)
- What NOT to do (observed removals)
- Recommended first interaction (commenting topics)
- Score breakdown (audience fit, tolerance, reach, etc.)
- Owner (you)
- Status (to research / researched / active / paused)
- Notes

## Reddit-first strategy
### Reddit operating principles
- Prefer **discussion posts** (S1/S3) over link drops.
- Build credibility first:
  - spend 1–2 weeks commenting helpfully
  - avoid posting only about Prep
- Always comply with subreddit rules; if unclear, message mods.
- Respond fast to comments (first 2 hours matters).

### Reddit channel discovery: categories to research
#### AI dev tooling / RAG / local models
- r/LocalLLaMA
- r/MachineLearning
- r/LLMDev (if present / or similar)
- r/ArtificialInteligence / r/Artificial
- r/OpenAI / r/ClaudeAI (policy-dependent)

#### Programming (broad)
- r/programming
- r/learnprogramming
- r/cscareerquestions (usually strict; research)
- r/ExperiencedDevs (often strict; research)

#### Editors / workflows
- r/vscode
- r/neovim
- r/emacs
- r/commandline
- r/linux

#### Infra + self-hosting + privacy
- r/selfhosted
- r/homelab
- r/devops
- r/kubernetes
- r/privacy

#### Language-specific (only if you have relevant demos)
- r/rust
- r/golang
- r/Python
- r/typescript

### What to research per subreddit
- Rules about:
  - self-promo
  - linking to your own site
  - posting frequency
  - “tool” posts vs “discussion” posts
- Whether they have:
  - weekly showoff/promote threads
  - mandatory flair
  - minimum karma/account age
- Identify:
  - top 20 posts in last 6 months that match your format
  - common title patterns
  - comment sentiment around “AI coding tools” and privacy claims

## Long-form strategy (Medium + alternatives)
### Why long-form exists in this system
Long-form is your **canonical proof artifact** for linkable detail, while Reddit/HN/Lobsters are **distribution surfaces**.

### Medium placements to research
- Your own Medium profile (easy baseline)
- Medium Publications (harder but higher distribution)

For each publication, track:
- topic fit (devtools/AI/productivity)
- submission requirements
- editor contact route
- whether they accept “tool walkthrough” style

### Alternatives (often better than Medium)
- dev.to (great for devtools)
- Hashnode
- Substack (for recurring “build in public”)
- runprep.io/blog (for SEO + full control; syndicate outward)

## “Blast every direction” distribution map (research targets)
### High-leverage posts (non-Reddit)
- Hacker News:
  - Show HN (launch/update)
  - Ask HN (questions that invite discussion)
- Lobsters (invite-only posting; research invite path)
- Indie Hackers (build in public / devtool launch)

### Directories + launch surfaces
- Product Hunt
- GitHub “Awesome” lists (submit PRs)
- Newsletters that accept submissions (research by niche)

### Community partnerships
- Discords/Slacks: partner posts, demo nights, office hours
- Podcasts/YouTube channels that cover devtools (research and track)

## Research output checklist (definition of done)
- 50+ channels discovered
- 25 channels fully researched + scored
- Top 10 “active targets” selected with:
  - posting style
  - cadence
  - trust ramp
  - success metric

## Next step
Create a `CHANNEL_DATABASE.md` (or CSV) alongside this doc to track channel research scores and status across campaigns. Use the "Tracking template" column list above as the schema.
