# Phase 142 — Scrutiny

> Adversarial review of the plan. Each section asks "what kills this?"
> and lists what to do *before* shipping if that risk is real.
>
> This document is the most important pre-flight check. Run it cold —
> look for the things the plan author (Claude) is too close to see.

## Reverse-engineering: working backwards from the goal

**Goal:** Within 90 days of Show HN, ≥1 of:
(a) inbound from a named acquirer, (b) IC offer from a named employer,
(c) ≥500 stars + clear flywheel.

**For (a) or (b) to happen, someone at a target company must:**

1. *Know about Eric and SourcePrep.* → distribution (Show HN, gstack, blog), or direct outreach.
2. *Believe Eric built it.* → clean Apache-licensed commits with Eric's name, public technical story (blog posts, demo, Twitter presence).
3. *Believe Eric+SourcePrep is worth integrating or hiring.* → working code, credible benchmark, alignment with their roadmap.

**Plan coverage check:**

| Sub-step | Plan covers? | Gap |
|---|---|---|
| Distribution via OSS launch | ✅ Parts D, F | Solid |
| Distribution via gstack | ✅ Part D | Reciprocity gap — see §"gstack PR presumption" |
| Direct outreach | ✅ Part H | List exists; quality of cold email matters |
| Clean public commits | ✅ Part B | History strategy still TBD |
| Eric as a credible person | ❌ **MISSING** | No personal-brand work (Twitter, LinkedIn, personal site, GitHub profile README) |
| Working code first impression | ⚠️ Partial — Part A scrubs, but doesn't fix known product bugs | See §"Known product embarrassments" |
| Credible benchmark | ✅ Part E | Heavy bet — see §"What if benchmark fails?" |
| Alignment with each acquirer's roadmap | ⚠️ ACQUIRER_MAP.md exists | Generic vs specific pitch — see §"Pitch specificity" |

**Three missing pieces flagged.** Each gets a section below.

## §1 — Eric as a person is missing from the plan

Acqui-hires happen to **people**, not repositories. The plan
optimizes the artifact (SourcePrep) but says nothing about Eric's
professional surface area.

**Adversarial question:** if an Anthropic recruiter reads the Show HN
post, googles "Eric Bintner," and finds nothing — no Twitter, stale
LinkedIn, no personal site, no GitHub profile README, no other public
work — how confident are they to reach out vs assume "anonymous solo
dev, might be hard to onboard"?

**Pre-launch additions to the plan:**

- [ ] Update LinkedIn — current role, SourcePrep listed as a project, link to the repo
- [ ] Write GitHub profile README at `github.com/<eric-handle>/<eric-handle>` — what Eric works on, link to SourcePrep + blog posts
- [ ] Optional: refresh Twitter/X with technical posts (3–5 before Show HN so the profile isn't empty)
- [ ] Decide if `sourceprep.io/about` page should name Eric publicly (recommend yes — anonymous founders are a red flag for acquirers)
- [ ] Resume up-to-date and ready to send within 24 hours of any inbound

**Cost:** half a day to a day. Cheap. Plan was failing to include this.

## §2 — Known product embarrassments not addressed pre-launch

Per Eric's memory:

- `project_search_docs_bias.md` — `prep_search` keys on roadmap/planning MD files instead of UI code. A Show HN reader trying it on a real repo will hit this in 5 minutes.
- `project_synthesizer_wall_time_regression.md` — concept synthesis silently fails; concepts lost. Reader runs full enrichment, gets empty concepts panel, files an issue.
- `project_pipeline_sequencing_bug.md` — deep enrichment stages don't advance. Same.
- `feedback_agents_md_in_graph.md` — auto-generated AGENTS.md ends up in the index as noise.
- `project_full_reset_gaps.md` — F-78 incomplete reset leaves stale state.
- Phase 139 embedder memory growth (now hardened but the daemon still won't release RAM until restart on long runs).

**Adversarial question:** what happens when 500 simultaneous Show HN
readers index their own large repos on Day 1 and hit any of these?

**Pre-launch additions:**

- [ ] Fix or visibly disable the doc-bias issue in `prep_search` (at minimum: add a `--mode=code` flag or surface the issue in README with a workaround)
- [ ] Fix synthesizer silent-fail OR explicitly document the known limitation with a workaround
- [ ] Resolve pipeline sequencing bug OR ship Phase 142 with `--no-deep-enrichment` as the recommended default
- [ ] Add AGENTS.md to default ignore patterns (the gitignore-style filters)
- [ ] Document the embedder restart-to-reclaim limitation in README "Known Limitations" — be honest, it's better than getting caught

**The principle:** ship with honest known-limitation documentation
rather than pretend issues don't exist. The OSS reader will find them
either way — getting ahead of it earns credibility, hiding loses it.

## §3 — Pitch specificity for each acquirer

Plan H.1 says "≥5 named contacts across ≥3 named companies." But a
generic "I built an MCP server for code intel" email to all of them
produces a 0% response rate.

**Adversarial question:** can Eric (a) name the specific person at
each company, (b) name the specific integration or product team that
benefits, and (c) name what changes at their company *because* of
SourcePrep?

**Pre-outreach additions:**

- [ ] For each company in ACQUIRER_MAP.md, name the exact team that should care (Claude Code team at Anthropic, Codex infra at OpenAI, etc.)
- [ ] For each company, name 1 specific integration angle ("Claude Code's `/sourcetree` could call `prep_impact` to expand blast-radius reasoning before edits")
- [ ] For each company, identify a person via their public engineering blog, conference talks, or GitHub (not LinkedIn cold-spray — that gets ignored)

## §4 — gstack PR presumption

Plan D.2 says "open a PR or issue to gstack." This presumes a
project with 104k stars and 33 contributors will welcome a "use our
tool" PR from a stranger.

**Adversarial question:** what if Garry's team ignores or rejects the
PR? What's our fallback?

**Reality:** gstack maintainers receive a flood of "add my tool" PRs.
The acceptance rate is low without prior relationship or genuine
upstream contribution.

**Better approach:**

- [ ] Before any "use SourcePrep" outreach: contribute one genuinely useful thing to gstack (a bug fix, a test, a doc improvement). Build maintainer goodwill.
- [ ] Ship our own gstack-compatible bundle in *our* repo as the primary integration ("install gstack, then install our gstack-compatible bundle") — don't depend on upstream merge.
- [ ] Frame outreach as "we built a gstack-compatible MCP server; here's how it works alongside gstack" — descriptive, not prescriptive.
- [ ] Garry Tan personally interacts with quality PRs and tools on Twitter — a public thread tagging him *after* the PR is open is better than a cold DM.

## §5 — What if the benchmark fails?

Plan E says "if SourcePrep fails or partially succeeds, say so."
But what if the benchmark *consistently* shows SourcePrep doesn't
materially help — i.e., a vanilla Claude Code agent matches or beats
the +SourcePrep run on most realistic tasks?

**This is the killer scenario.** If the benchmark is honest and the
benchmark looks bad, the whole distribution motion (Parts F–H) makes
the product *less* attractive, not more.

**Pre-Part-F gate:**

- [ ] **Hard gate:** if E.2 produces a benchmark where SourcePrep doesn't show measurable improvement on the chosen task, **pause Parts F–H.** Diagnose the product issue. Do not launch into a bad demo.
- [ ] Define "measurable improvement" before running: time-to-correct, pass/fail, or quality metric. Don't move the goalposts after seeing results.
- [ ] If multiple tasks show no improvement: we have a product problem (probably the search-bias / concept-failure issues from §2). Fix first; ship after.

This is a Phase-142-killer if not addressed up front. Better to know.

## §6 — History rewrite tradeoff

The current repo history reveals a lot: Phase 139's 100 GB memory
incident, Phase 141's silent shrink, Phase 134 migration cases,
Phase 78 reset gaps. Every "fix(phaseNN)" commit is a public
admission of a past bug.

**Three options:**

| Option | Pros | Cons |
|---|---|---|
| Ship history as-is | Authentic; preserves attribution; shows transparency | Reveals rough development; some readers may judge harshly |
| Squash to clean initial commit | Polished first impression; standard for new OSS projects | Loses attribution; reads as "hiding something" if discovered |
| Two-repo strategy: public mirror with curated commits, private dev repo with full history | Best of both — clean public face, full private record | Highest setup cost; sync overhead |

**Recommendation:** **Option 3 — two-repo strategy.** Squash the
public-facing initial commit to something clean ("Initial public
release"); keep `/Volumes/4TB-BAD/HumanAI/CoDRAG/` as the private
dev repo with full history. Ongoing development happens privately;
public mirror gets curated commits.

> **✅ DECIDED 2026-07-18 (D8):** Option 3 is adopted — the public surface
> is a **fresh-initial-commit mirror** assembled by
> `tools/build_public_mirror.py` from an explicit file allowlist + a
> denylist-regex gate (see `DECISION_MEMO_2026-07-17.md` C2/D1 and
> `PRE_LAUNCH_BLOCKERS.md` §2). The private dev repo keeps full history and
> is never published. "Squash the existing history" is reframed as
> "start the public repo from a clean curated initial commit" — there is
> no history rewrite of the dev repo. The §6 tradeoff is settled; see also
> the exit-checklist item below.

**But Eric's call.** Some OSS founders (e.g., Bun's creator) shipped
warts-and-all and were celebrated for the honesty. The choice depends
on Eric's stomach for public scrutiny of past mistakes.

## §7 — Maintenance overhead reality

Show HN launches that hit the front page typically generate
**50–300 GitHub issues within the first week** and dozens of DMs.
A solo dev gets crushed.

**Pre-launch additions:**

- [ ] Pre-write canned responses for the top 10 anticipated questions ("How does this compare to Cody?", "Why not just use grep?", "Does it work offline?", "What about Cursor's built-in indexing?", "Why MCP?", "Is the dashboard required?").
- [ ] Set up GitHub Discussions to triage questions vs bugs.
- [ ] Set expectations in CONTRIBUTING + README: "Maintained by one developer. Response times may vary. Major architectural PRs should be discussed in an issue first."
- [ ] Pin a "Roadmap and limitations" issue.
- [ ] Plan: spend 50% of the week post-launch on community management, not coding. Don't promise features in DMs.

## §8 — Dependency license audit

Plan A.3 audits source files for attribution but does not run a
proper dependency license audit. A single GPL Rust crate buried in
`engine/Cargo.lock` would make our Apache 2.0 grant invalid.

**Pre-launch additions:**

- [ ] `cargo deny check licenses` — fail on any GPL/AGPL/proprietary crate
- [ ] `pip-licenses --fail-on=GPL` for Python deps
- [ ] `license-checker --excludePackages '...' --failOn 'GPL'` for npm deps
- [ ] Run all three in CI as a blocking step

## §9 — Naming + trademark check

> **2026-07-18 update:** the org-name sub-question is **DECIDED** — stay under
> the existing `MagneticAnomaly` org (do NOT reserve a separate `sourceprep`
> org); see `STRATEGY.md` "What is intentionally not decided yet" +
> `IMPLEMENTATION_PLAN.md` B.2. The trademark sub-question is **DECIDED** per
> `DECISION_MEMO` Part 0 D5 — not a decision blocker; B1 (free USPTO clearance
> search) and B2 (file 1(b)) are pre-Show-HN execution tasks. The checkboxes
> below that remain open are the B1/B2 execution items.

Plan B.2 says "reserve GitHub org `sourceprep`." But have we checked:

- [x] ~~Is `sourceprep` the GitHub org available?~~ → DECIDED: stay under `MagneticAnomaly`; no separate org to reserve.
- [ ] Is `sourceprep` on PyPI? Crates.io? npm? *(execution check before public publish)*
- [ ] **B1:** Is "SourcePrep" trademarked by someone else? (free USPTO search via tmsearch.uspto.gov — 30 min; see `DECISION_MEMO` D5)
- [ ] **B2:** File trademark 1(b) on the Principal Register once B1 clears (before Show HN).
- [ ] Is `sourceprep.io` already owned by Eric? (Memory suggests yes, but confirm.)

A name conflict after the public launch is a brutal rebranding cost.

## §10 — Anti-rug-pull commitment

Elastic / HashiCorp / Redis all flipped licenses mid-stream and burned
their communities. The OSS reader who *cares* about the license cares
about whether it'll change.

**Pre-launch additions:**

- [ ] Write a `CHARTER.md` (or section in README) committing the OSS surface to Apache 2.0 in perpetuity — and specifying that the Pro tier is the only proprietary surface, with no plans to flip OSS components proprietary.
- [ ] Be honest about the open-core boundary so users aren't surprised when Pro features ship.

This costs nothing and dramatically increases trust.

## §11 — Existing customers of the current closed product

Per `DISTRIBUTION_AND_REVENUE_PLAN.md`: there is already a path for
paid Tauri desktop users via Lemon Squeezy.

**Adversarial question:** if anyone has already paid for Pro, what
happens when we open-source the core?

- Do they get a discount? A grandfathered tier?
- Do we owe them a notice ("hey, the engine you paid to use is now free, but the Pro app remains paid")?
- Is there a refund-request risk?

**Pre-launch additions:**

- [ ] Audit Lemon Squeezy / Magnetic Anomaly LLC for existing customer count.
- [ ] If non-zero: write a customer notice explaining the OSS pivot and what stays paid.
- [ ] If zero: no action needed; document the all-clear.

## §12 — Money runway during the 8–12 weeks

Plan estimates 8–12 weeks of focused solo-dev work. No mention of
how Eric is paying rent during that time.

**Adversarial question:** is there a money clock that ends Phase 142
before Phase 142 ends? If the answer is "I have 3 months of runway,"
the plan should explicitly hold Parts F–H to weeks 5–8 to leave a
buffer for outcomes to materialize before the runway hits zero.

**Pre-plan additions:**

- [ ] Document Eric's actual runway in months (private; not in repo).
- [ ] If <4 months: tighten the timeline. Move H.2 (job applications) to Week 2, not Week 6 — applications take 4–8 weeks to convert to offers; can't wait until Show HN to start.
- [ ] If 4+ months: plan timeline is OK; keep H.1 + H.2 in weeks 6–12.

## §13 — Conflict with existing AUTHORITATIVE doc

`docs/DISTRIBUTION_AND_REVENUE_PLAN.md` is marked AUTHORITATIVE and
specifies closed-source distribution. Phase 142 pivots from this.

**Risk:** if Eric (or a future Claude session) reads the authoritative
doc without finding Phase 142, they'll execute against an obsolete
strategy.

**Pre-launch additions:**

- [ ] On the day Phase 142 ships Parts B–C: add a banner at the top of `DISTRIBUTION_AND_REVENUE_PLAN.md` pointing to Phase 142 and noting the open-core layering.
- [ ] Do **not** delete the authoritative doc — the Pro-tier mechanics (Lemon Squeezy, Tauri installer, Microsoft Store) remain valid.
- [ ] Plan retro updates section 9 ("Superseded Documents") with the OSS layering decision.

## §14 — What if Anthropic ships native codebase intel into Claude Code?

Anthropic owns Claude Code. They could (and arguably should) build
codebase intelligence natively into the product. If they ship that
in Q3/Q4 2026, SourcePrep's value prop evaporates.

**Adversarial question:** does Phase 142 ship *before* Anthropic
internalizes this functionality?

**Reality:** Anthropic has already shipped *some* codebase context in
Claude Code (file references, `@file` mentions, automatic exploration).
But the structural graph + concepts + trace expansion that SourcePrep
provides is non-trivial to build and not the kind of thing a
research-org first-parties quickly.

**Risk mitigation:**

- [ ] Treat Phase 142 as time-sensitive. The longer we wait, the higher the chance Anthropic ships the in-house version.
- [ ] The acqui-hire pitch becomes *stronger*, not weaker, in this scenario: "you're about to build this; hire the person who already built it."
- [ ] If Anthropic ships native code intel during Phase 142: pivot the pitch from "MCP server that adds capability" to "code intel team you can hire to make the in-house version better."

## §15 — What if Sourcegraph beats us to MCP-native code intel?

Sourcegraph already has the best code intelligence engine in the
industry. They've open-sourced Cody. They could ship a Cody MCP
server tomorrow and crush our category.

**Adversarial question:** what's our defense?

**Reality check:**

- Sourcegraph is enterprise-focused; per their own framing, they don't optimize for individual developers.
- SourcePrep's local-first posture is a real differentiator vs Sourcegraph's hosted indexing.
- MCP-native + local-first + Apache 2.0 + works-with-gstack is a thinner but defensible niche.

**Risk mitigation:**

- [ ] Lean into local-first in messaging — "your code never leaves your machine" is a real differentiator vs Sourcegraph.
- [ ] If Sourcegraph ships a Cody MCP server during Phase 142: reframe SourcePrep as the local-first / individual-developer alternative. Don't try to outdo them on enterprise.

## §16 — What if a third party finds our pre-Apache code that's GPL-derived?

If A.3 (attribution audit) misses something — e.g., a vendored
algorithm from a GPL project, an LLM-generated function that happened
to match GPL code, a copy-paste from Stack Overflow under CC-BY-SA —
and it's discovered post-launch, we get a public license-violation
incident.

**Pre-launch additions:**

- [ ] Run `licensee detect` or `scancode-toolkit` on the entire repo.
- [ ] Manually inspect any flagged files.
- [ ] Document the audit and date in `LICENSE-AUDIT.md` (kept private; serves as legal defense if anyone challenges later).

## §17 — Show HN timing competition

Plan F.2 says "don't post the same week as a major Anthropic /
OpenAI release." But the AI dev tool space ships 5+ notable products
*per week.* Avoiding all of them is impossible.

**Better approach:**

- [ ] Pick a Tuesday/Wednesday with no *scheduled* Anthropic or OpenAI event (DevDay, Claude release, etc.).
- [ ] Accept that some surprise launch will happen; don't try to perfectly time.
- [ ] Have a launch checklist for the morning-of so we don't fumble execution under time pressure.

## §18 — The "Pro tier exists" awkwardness

When we go OSS, the OSS reader assumes everything is free. When they
discover there's a Pro tier later, some will feel surprised /
bait-and-switched.

**Pre-launch additions:**

- [ ] On the README, in the same screen as the install instructions, include a small "Pro tier" link that explains what's free vs paid (per the open-core split in STRATEGY.md).
- [ ] No bait. No "free now, $99/mo later." If anything is paid, say so on the README from day one.

## §19 — Subagent / community contribution friction

The plan assumes community contributions will help. But Phase 142
is a solo-dev show until that flywheel actually starts spinning. The
first 10–20 PRs are usually low-quality "fix typo" / "add lint rule"
work that costs maintainer time without adding value.

**Pre-launch additions:**

- [ ] Set up a GitHub Action that auto-comments on first-time-contributor PRs with the CONTRIBUTING.md link + the "discuss-first for architectural changes" rule.
- [ ] Mark a `good first issue` label with 3–5 actually-useful starter tasks (small bugs, docs improvements).
- [ ] Reject "fix typo" PRs gracefully but firmly if they're noise; merge real ones.

## §20 — One more reverse-engineering check: the timing dependency

The plan has Parts E (benchmark), F (Show HN), G (blog posts), H
(outreach) ordered in calendar weeks 3–12.

**Adversarial check:** is there an ordering where the *acquirer
conversation* happens *before* Show HN? E.g., direct outreach to
Anthropic / Cognition with the demo video, then their reaction
informs whether/how we ship the public launch?

**Argument for going direct first:**

- A warm intro is worth 100x a cold Show HN
- An acquirer's feedback before launch can reshape the messaging
- If they say "we'd want to talk before you go public," that's information

**Argument against:**

- Direct outreach without traction is easier to ignore
- Show HN provides traction signal that warms outreach
- "We open-sourced this thing that's hitting #1 on HN" is a stronger opener than "we built a thing"

**Recommendation:** ship E (benchmark + demo video) → 1 week of
direct outreach to 2–3 closest contacts → if no traction, proceed
to F (Show HN); if traction, slow down F until conversations clarify.

---

## Scrutiny exit checklist

Before Eric approves Phase 142 to begin:

- [ ] Each of §1–§20 has been read and a decision made (act now, defer, or accept the risk)
- [ ] The runway question (§12) has an honest answer
- [ ] The pre-launch product fixes from §2 are scoped (which fix, which defer-with-doc, which ship as known limitation)
- [x] The history-rewrite question (§6) is decided — D8 2026-07-18: fresh-initial-commit mirror (Option 3)
- [ ] The launch-order question (§20) is decided
- [ ] The personal-brand work (§1) is added to Part A or B
