# Phase 142 — Implementation Plan

> Ordered, scoped work to ship SourcePrep as Apache 2.0 OSS and execute
> the distribution motion that follows. Eight parts (A–H), each with
> deliverables and acceptance criteria. Estimated calendar: 8–12 weeks
> at solo-developer pace.

**Each part has acceptance criteria.** Do not mark a part complete
until criteria are met — this plan exists to prevent the "shipped
something close to it" trap.

---

## Part A — Pre-OSS Hygiene (Week 1)

**Goal:** Make the repo safe and respectable to publish. Find secrets,
strip internal-only docs, audit attribution.

### A.1 — Secret audit

- [ ] Run `git log --all -p | grep -iE "api[_-]?key|secret|token|password|bearer|sk-[a-zA-Z0-9]" | head -200` and review hits.
- [ ] Run `trufflehog git file:///Volumes/4TB-BAD/HumanAI/CoDRAG --max-depth 500` (install if missing).
- [ ] Audit `.env*`, `.npmrc`, `*.local.json`, `*.local.toml` are gitignored.
- [ ] Audit `~/.local/share/sourceprep/` references in tests — replace any real project paths with fixture paths.
- [ ] Search for personal email / Slack / Linear references in commit messages and docs (`git log --all | grep -iE "@gmail|@anthropic|slack.com|linear.app"`).

**Acceptance:** zero secrets in history. If any found, decide squash-vs-redact (see SCRUTINY.md §"History rewrite").

### A.2 — Internal docs scrub / move

Many files in `docs/` are internal phase-baseball (incident reports,
write-guard recovery details, etc.) that are noise to outsiders.

- [ ] Inventory `docs/` and classify each top-level entry as:
  - **Public** (keeps in public repo: ARCHITECTURE.md, API.md, GETTING_STARTED.md, AGENTIC_INTEGRATION_GUIDE.md, etc.)
  - **Internal** (moves to `docs/internal/` and gets gitignored from public mirror, OR stays in monorepo with a `.docignore` strategy)
  - **Mixed** (needs editing — e.g., strip Phase NN references from CLAUDE.md before publishing)
- [ ] Decide between two strategies:
  - **Option 1:** Single repo, with `docs/internal/` gitignored from public mirror via a separate orphan branch.
  - **Option 2:** Two repos — `MagneticAnomaly/SourcePrep` (public storefront, curated fresh-initial-commit mirror) and `MagneticAnomaly/SourcePrep-Private` (workshop; full history, never published).
- [ ] Strip "Phase NN" leak language from any file going public (CLAUDE.md, AGENTS.md, READMEs). Same antibody as Phase 131.

**Acceptance:** a clean `docs/` tree for public consumption with no
internal incident reports, no "Phase NN" jargon in user-facing pages,
no Eric-specific paths or USB-drive references.

### A.3 — Attribution audit

- [ ] Inspect `src/prep/core/atlas/` for any `role` taxonomy code potentially adapted from gstack.
- [ ] Inspect any `.claude/` or `~/.claude/skills/` patterns in this repo that mirror gstack's structure.
- [ ] Review imports / vendored code for any non-Apache/MIT licenses we may have pulled in (especially Rust crate deps; check `engine/Cargo.lock`).
- [ ] Draft `NOTICE` file with required attributions.

**Acceptance:** every license-bearing dependency accounted for in
`NOTICE`. Any gstack-derived patterns explicitly credited in code
comments + `NOTICE`.

### A.4 — Dashboard scrub

The dashboard contains internal Phase references and devOnly panels.

- [ ] Re-verify Phase 131 storybook hide-devOnly work covers the public dashboard build.
- [ ] Strip any "Phase NN" labels visible in the user-facing dashboard UI.
- [ ] Confirm `packages/ui/src/components/llm/index.ts` doesn't export devOnly components by default in the public bundle.

**Acceptance:** running the dashboard against a fresh project shows
no internal phase references in any tab, tooltip, or settings panel.

---

## Part B — License & Repo Restructuring (Week 1–2)

**Goal:** Apply Apache 2.0 across the OSS surface, restructure for
public consumption, prepare the GitHub org.

### B.1 — Apache 2.0 application

- [ ] Add `LICENSE` (Apache 2.0 text, unmodified, top of repo).
- [ ] Add SPDX headers to *new* source files going forward. Do **not** mass-rewrite existing files (cosmetic-only diffs are noise).
- [ ] Add `NOTICE` file with copyright holder, year, and third-party attributions (from A.3).
- [x] ~~Decide copyright holder~~ → **Apply: Magnetic Anomaly LLC** (decided Part 0 D8 / `LICENSING_RECOMMENDATION.md` / `NOTICE`). Copyright holder is Magnetic Anomaly LLC; formalized by the IP Assignment (Stream 1.1) for diligence chain-of-title.
- [ ] Update `pyproject.toml`, `Cargo.toml`, and `package.json` files with `"license": "Apache-2.0"`.

**Acceptance:** `pip-licenses`, `cargo deny`, and `license-checker`
all pass with no incompatible-license warnings.

### B.2 — GitHub org / repo setup

- [x] ~~Reserve GitHub org~~ → **stay under existing `MagneticAnomaly`** org (decided 2026-07-18; do NOT stand up a separate `sourceprep` org).
- [x] ~~Create main repo~~ → **`MagneticAnomaly/SourcePrep`** (public storefront, monorepo, fresh-initial-commit mirror built by `tools/build_public_mirror.py`). Workshop repo `MagneticAnomaly/SourcePrep-Private` keeps full history and is never published.
- [x] ~~Decide on history strategy~~ → **DECIDED D8 (2026-07-18):** fresh-initial-commit public mirror (Option 3 in SCRUTINY.md §6); no history rewrite of the workshop repo. See `PRE_LAUNCH_BLOCKERS.md` §2 (live-tree secrets removal, not history scrub).
- [ ] Set up `.github/` — issue templates, PR template, CODEOWNERS, FUNDING.yml (optional).

**Acceptance:** public repo URL is decided and reserved; redirect plan
documented if private dev repo continues elsewhere.

### B.3 — Public CI

The current CI is built for internal development and likely contains
secrets / private S3 access / Lemon Squeezy API keys.

- [ ] Audit `.github/workflows/` and `scripts/` for any CI step that uses a private secret.
- [ ] Create a `.github/workflows/oss-ci.yml` that runs on public infrastructure with **no secrets**:
  - lint (`ruff`, `eslint`, `cargo fmt`, `cargo clippy`)
  - typecheck (`mypy`, `tsc --noEmit`)
  - test (`pytest tests/`, `cargo test`, `npm test`)
  - build smoke (`maturin build`, `npm run build`)
- [ ] Disable / scope any internal-only workflow to private repo only.

**Acceptance:** public CI is green on a fresh clone with no secrets
configured.

---

## Part C — Public-Facing Surface (Week 2–3)

**Goal:** README, CONTRIBUTING, SECURITY, GETTING_STARTED that a
first-time visitor can act on in 30 seconds.

### C.1 — README rewrite

The README is the single most-leveraged document in Phase 142.

- [ ] Lead paragraph: **"SourcePrep is the structural codebase intelligence MCP server. Works standalone. Supercharges gstack."** (one line, no jargon)
- [ ] One-paragraph "what it does" with concrete benefit (per `feedback_marketing_voice.md`: lead plain-language/outcome, jargon as supporting detail).
- [ ] Quick-install: `git clone` → `pip install -e .` → `prep serve` → MCP config snippet.
- [ ] One-glance benchmark snippet (links to demo video — Part E).
- [ ] "Works with" badges: Claude Code, Cursor, Windsurf, Gemini CLI, VS Code, Copilot, **gstack**.
- [ ] Architecture diagram (single PNG/SVG, not interactive).
- [ ] Link to CONTRIBUTING, SECURITY, full docs.
- [ ] No mention of "CoDRAG" anywhere.

**Acceptance:** a developer reading the README in 30 seconds can
(a) explain what it does to a coworker, (b) start installing.

### C.2 — CONTRIBUTING.md

- [ ] Outline how to set up dev environment (Python venv, Rust toolchain, Node 20, npm).
- [ ] Outline test commands and the bar for PRs.
- [ ] Outline issue templates (bug, feature, question).
- [ ] **Honesty section:** "This is currently maintained by a single developer. Response times may vary. Major architectural PRs should be discussed in an issue first."

**Acceptance:** a new contributor can run the test suite in <15 min
from a fresh clone on a typical dev machine.

### C.3 — SECURITY.md

- [ ] Reporting contact (email; consider `security@sourceprep.io` alias).
- [ ] Supported versions table.
- [ ] Note that SourcePrep reads local source code; users should review the integration before running on sensitive repos.
- [ ] Coordinated disclosure policy (90-day default).

**Acceptance:** the file exists, is linked from README, and matches
GitHub's security policy detection.

### C.4 — GETTING_STARTED rewrite

- [ ] Strip any internal references from existing `docs/GETTING_STARTED.md`.
- [ ] Update to point at the public repo install flow rather than internal Tauri builds.
- [ ] Include a "first 5 minutes" walkthrough that ends with a successful `prep_search` query.

**Acceptance:** a fresh user can index this very repo (or any small
public repo) and get a useful search result within 5 minutes.

---

## Part D — gstack Integration (Week 2–4)

**Goal:** Land SourcePrep in front of gstack's audience.

### D.1 — Build a `prep` slash command in gstack's format

- [ ] Read the gstack repo's skill / slash-command structure.
- [ ] Create a `prep` command that runs the SourcePrep MCP install + basic onboarding ("`prep init`" → "`prep status`" → first search).
- [ ] Test against a local gstack install.

**Acceptance:** running `./setup prep` inside a gstack-installed project leaves the user with a working SourcePrep MCP server registered to Claude Code.

### D.2 — Open a PR or issue to gstack

- [ ] Draft a short issue: "Recommend SourcePrep as the codebase-intelligence MCP server for gstack roles."
- [ ] Include a one-paragraph benefit statement, a screenshot/video of a gstack role using `prep` tools, and link to the slash command from D.1.
- [ ] Submit as an issue first (lower friction); offer to send a PR if maintainers agree.

**Acceptance:** issue is open and visible. PR is open if maintainers
nod. (If maintainers ignore — still acceptable; we keep the slash
command published in our own repo as an integration.)

### D.3 — README "Works with gstack" section

- [ ] Add a clearly labeled section to our own README with a one-command install for gstack users.
- [ ] Link the demo video (Part E) that explicitly shows gstack + SourcePrep working together.

**Acceptance:** any gstack user landing on our README can install
SourcePrep in one command and see why they'd want to.

---

## Part E — Killer Demo + Benchmark (Week 3–5)

**Goal:** A single reproducible benchmark that proves SourcePrep
improves an AI agent on a hard codebase task, with a recorded video.

This is the most-leveraged Part. **Spend disproportionate time here.**

### E.1 — Choose the benchmark task

Pick a task that is (a) hard for a vanilla AI agent, (b) easy with
codebase intelligence, (c) reproducible by anyone.

Candidates (pick one for the headline demo, others can be follow-ups):

- "Add a new MCP tool to a 100k LOC AI agent project" (real architectural task; hits ranking, impact, concepts)
- "Refactor a hub file in a popular OSS repo without breaking dependents" (showcases `prep_impact`)
- "Implement a bug fix where the failing test is in a sibling module" (showcases `prep_search` + trace expansion)

- [ ] Pick the task. Document the exact prompt, the exact target repo at a pinned SHA, and the exact pass/fail criteria.

**Acceptance:** the task spec fits on one screen and is unambiguous.

### E.2 — Run the benchmark two ways

- [ ] Run the task with Claude Code (no SourcePrep) — record output, time, success/failure.
- [ ] Run the task with Claude Code + SourcePrep MCP — record output, time, success/failure.
- [ ] Run the same task with gstack alone, then gstack + SourcePrep, for the gstack-comparison row.

**Acceptance:** four data points (vanilla, +SourcePrep, +gstack, +both) with reproducible commands.

### E.3 — Record the demo video

- [ ] 90–180 seconds, screen-recorded, voice-over.
- [ ] Structure: problem (5s) → vanilla attempt fails (30s) → +SourcePrep succeeds (60s) → quick how-to (30s) → call to action.
- [ ] Host on YouTube + embed in README + standalone landing page on sourceprep.io.
- [ ] Honesty: if SourcePrep fails or partially succeeds, **say so** — this is a dogfooding product, and credibility comes from honest reporting. Per `project_dogfooding.md`.

**Acceptance:** video published, embedded in README, linked from
sourceprep.io homepage.

### E.4 — Publish the benchmark as a public repo

- [ ] Create `sourceprep/benchmarks` repo with the exact reproduction recipe (target repo SHA, prompts, commands, expected output).
- [ ] Link from main README.

**Acceptance:** any developer can clone the benchmarks repo and
reproduce the four data points.

---

## Part F — Show HN Launch (Week 5–6)

**Goal:** Front page of Hacker News. Distribution multiplier.

### F.1 — Show HN post draft

- [ ] Title: "Show HN: SourcePrep — open-source codebase intelligence MCP server"
- [ ] Body: 3 short paragraphs — what it does, why it exists, the benchmark video.
- [ ] First comment (queued, post 30 seconds after submission): technical details, architecture link, "happy to answer questions about MCP integration / trace graph / why Apache 2.0."
- [ ] Don't link the marketing site as primary URL — link the GitHub repo. HN crowd trusts repos more than marketing pages.

**Acceptance:** draft is reviewed by Eric and ready to post.

### F.2 — Timing

- [ ] Post Tuesday or Wednesday, 9–10 AM Eastern (highest HN engagement windows).
- [ ] Do NOT post the same week as a major Anthropic / OpenAI release (would get drowned out).
- [ ] Have 2–3 honest peers (not employees, not paid) ready to comment substantively in first 30 minutes — not vote brigade, just genuine engagement that anchors the conversation technically.

**Acceptance:** posted at the chosen window with prep complete.

### F.3 — Follow-up posts

- [ ] r/LocalLLaMA — different angle ("local-first" framing)
- [ ] r/ClaudeAI — gstack + SourcePrep integration framing
- [ ] r/cursor — "make Cursor's codebase indexing actually understand your repo" framing
- [ ] Twitter/X thread with the demo video clip — tag Anthropic / Garry Tan if natural (don't beg)

**Acceptance:** at least 3 of the above posted within 7 days of HN launch.

---

## Part G — Technical Blog Posts (Week 5–7)

**Goal:** 2–3 deep technical posts that double as job-application
evidence.

### G.1 — Post 1: "Designing an MCP server for codebase intelligence"

- [ ] Topic: the architecture of `src/prep/mcp/` — how we map MCP tool calls to bounded structural retrieval, why direct-mode vs server-mode exists, the auto-classification of search intent.
- [ ] Length: 1500–3000 words.
- [ ] Audience: AI infra engineers at Anthropic / OpenAI / Cursor / Sourcegraph.
- [ ] Cross-post: own blog → HN → dev.to → Twitter thread.

**Acceptance:** published, ≥1000 views in first week.

### G.2 — Post 2: "Building a trace graph from a polyglot codebase"

- [ ] Topic: how the Rust engine + Python enrichment combine into the trace graph (`src/prep/core/trace/`), what we learned about cross-language symbol resolution, what we got wrong (be honest).
- [ ] Length: 2000–4000 words with diagrams.
- [ ] Audience: code-intelligence engineers (Sourcegraph, JetBrains, GitHub).

**Acceptance:** published, ≥1000 views in first week.

### G.3 — Post 3 (stretch): "Concepts: extracting business rationale from code"

- [ ] Topic: the concept system — LLM confidence calibration, T1/T2/T3 tiering, why we don't just embed everything. Reference `project_llm_confidence_calibration.md` lessons.
- [ ] Length: 1500–2500 words.
- [ ] Audience: AI infra + applied research crowd.

**Acceptance:** published. (Optional — if Parts G.1 and G.2 ate the
week, this can defer.)

---

## Part H — Direct Outreach + Applications (Week 6–12)

**Goal:** Activate the targets in ACQUIRER_MAP.md. Land conversations.

### H.1 — Outreach (5+ named contacts)

See [ACQUIRER_MAP.md](./ACQUIRER_MAP.md) for the specific list. The
pattern for each:

- [ ] Short email (≤150 words) — what you built, why they might care (specific integration with their product), a link to the demo video and one technical blog post.
- [ ] Not a sales pitch. "Built this, thought it might be relevant to [Codex / Claude Code / Cody / Devin]. Happy to chat if useful."
- [ ] Send 1–2 per week, not all at once. Personalize each.

**Acceptance:** ≥5 named contacts emailed across ≥3 named companies
by end of Phase 142.

### H.2 — Senior IC role applications

- [ ] Apply to a handful of specific roles at the same companies.
  - Anthropic — Claude Code infra, AI engineer (applied), MCP team if listed
  - OpenAI — Codex team, dev tools
  - Cognition — software engineer / AI engineer
  - Cursor / Anysphere — code intelligence
  - Sourcegraph — Cody / code intel
- [ ] Use the OSS repo + blog posts as the cover letter — link prominently.
- [ ] Customize one paragraph per application.

**Acceptance:** ≥5 applications submitted across ≥3 named companies
by end of Phase 142.

### H.3 — Track every conversation

- [ ] Create `docs/Phase142_OSS-First/OUTREACH_LOG.md` (not committed if it contains private info — gitignore).
- [ ] Log: company, contact, date sent, response, next step, status.

**Acceptance:** every conversation is recorded; nothing falls through.

---

## Post-Phase: Retro + Authoritative Doc Update

Once Parts A–H are complete (whether or not outcomes have materialized):

- [ ] Write `RESULTS.md` — what landed, what surprised, what to do differently.
- [ ] Update `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` section 9 ("Superseded Documents") and section 2 ("Distribution Channels") to reflect the OSS + Pro layering.
- [ ] Update `docs/PRODUCT_AND_BUSINESS_OVERVIEW.md` to mention OSS availability.
- [ ] Save a `project_oss_pivot` memory note recording the decision and date.
- [ ] If outcomes landed: write `OUTCOMES.md` (acquirer conversations, offers, traction metrics).
- [ ] If no outcomes within 90 days: trigger Path B fallback decision per SCRUTINY.md.

---

## Dependencies between Parts

```
A ──► B ──► C
            │
            ├──► D ──► F
            │         │
            └──► E ───┤
                      ├──► G ──► H
                      │
                      └──► H (can run in parallel with G)
```

- A blocks B (can't license what isn't audited)
- B blocks C (can't write public README until license is in place)
- C blocks D, E, F (public README anchors all distribution)
- E blocks F (Show HN needs the benchmark)
- G can run parallel to E once C is done
- H can start as soon as one of E/G has shipping artifacts

## Time budget warning

Solo developer + 8 parts = realistic 8–12 weeks elapsed time *if*
Eric protects 60%+ focus time. If pulled into product-engineering
work (Phase 143+, ongoing pipeline reliability, etc.), this stretches
to 16+ weeks. **Recommendation:** treat Phase 142 as a foreground
phase for ~10 weeks; defer non-blocking product work.
