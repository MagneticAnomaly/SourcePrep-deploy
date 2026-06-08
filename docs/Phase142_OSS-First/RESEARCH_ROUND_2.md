# Phase 142 — Research Round 2 (Explained Plainly)

> **What this document is:** the second round of research for Phase 142,
> written for a reader who hasn't been steeped in startup-finance or
> labor-economics jargon. Every term gets defined the first time it
> appears. Every conclusion gets shown, not just stated.
>
> **Why it exists:** the first research round (`RESEARCH.md`) collected
> evidence about Warp, OpenClaw, Bun, Astral, and gstack. The plan
> got written, then scrutinized. The scrutiny exposed assumptions
> that needed harder data — not vibes. This round dispatched four
> parallel research agents to find that data in academic papers,
> industry analyst reports, and public datasets.
>
> **What changed because of this round:** quite a lot. The original plan
> over-weighted the "acqui-hire" outcome (very unlikely) and
> under-weighted the "get hired as an IC engineer" outcome (much more
> likely). The license recommendation may flip. The timeline is too
> aggressive by 3–6×. The competitive threat is different than we
> thought. Read on.

---

## Part 1 — What we did and why

### The four questions we asked

After the first research round and the scrutiny pass, I had a list of
open questions where I had used "vibes" instead of evidence. So I
sent four research agents — each working in parallel — to dig into
the literature on different angles. Each agent has access to Google
Scholar, arXiv (a free academic paper archive), SSRN (another paper
archive), and the web more broadly. Each one wrote a detailed
synthesis with citations.

The four questions were:

1. **Does the academic literature actually support "OSS as a signal
   for getting hired"?** (Or is that just blog-post folklore?)
2. **What's the current market structure for AI dev tools?**
   Specifically: what's *commoditizing* (becoming a free undifferentiated
   feature anyone can build) versus what's *defensible* (a real moat)?
3. **What's the realistic probability of a solo developer getting
   acqui-hired by a frontier AI lab — based on actual data, not
   famous-name stories?**
4. **What's the realistic income/outcome distribution for solo
   developer tool projects?** What do indie founders *actually* earn?

The agents came back with the actual research — papers, datasets,
analyst reports. The findings are striking enough that we should
reconsider some core plan decisions.

---

## Part 2 — Core concepts you need first

Before getting into the findings, here are the concepts that show
up repeatedly. Skip ahead to Part 3 if you already know these.

### "Signal" / "Signaling theory"

When two parties don't have the same information about each other
(e.g., an employer trying to evaluate a candidate, or an investor
trying to evaluate a startup), the less-informed party looks for
**signals** — visible actions that are costly to fake. A college
degree is a signal: it's expensive in time and money, so someone
willing to invest in one is *probably* serious. An open-source
project is a signal: it takes months of unpaid work, so someone with
a maintained OSS project is *probably* competent and motivated.

The original theory (Michael Spence, 1973) said signals only work if
they're costly enough that incompetent people can't fake them. This
is the "**costly signaling**" idea.

**Why this matters for SourcePrep:** open-sourcing SourcePrep is a
signal of competence to potential employers. A working, well-architected
OSS project that you maintain says "I can build this kind of thing"
in a way that no résumé bullet can.

### "Survivorship bias"

The mental trap of looking at successful cases and assuming they're
the rule, when actually most attempts failed and you're only seeing
the ones that worked.

**Example:** "Peter Steinberger went from solo developer to OpenAI
acqui-hire in 60 days, so I can too." But Steinberger had already
sold his previous company (PSPDFKit) for $116 million in 2021. The
60-day timeline is the *outcome*; the prior reputation is the
*reason*. Looking only at the 60 days is survivorship bias.

### "Base rate"

The proportion of all attempts that end in a given outcome — not
just the famous ones. Base rates are usually much lower than people's
intuitions suggest, because the famous cases dominate attention.

**Example:** "What's the base rate of an OSS project getting its
maintainer acqui-hired by a frontier AI lab?" Empirically, in 2024–2026
across the entire AI dev tool ecosystem, the number of documented
no-prior-exit solo developers acqui-hired by a frontier lab is **zero**.
The base rate isn't 60 days; it's effectively unmeasurable because
the population of successes is too small.

### "Expected value" (EV)

A way of comparing options when each outcome has a probability. You
multiply the value of each outcome by its probability and add them
up. It's how to think clearly about risky choices.

**Example:** Option A is "guaranteed $50k." Option B is "10% chance
of $1M, 90% chance of $0." Option B has an expected value of $100k
(0.10 × $1,000,000), so it's "worth more" on paper — but if you only
get one shot, A might still be the right choice depending on whether
you can afford a 90% chance of nothing.

For SourcePrep: closed-source indie SaaS vs. OSS-first have different
expected values, and we have to compare them honestly even though
both involve uncertainty.

### "MRR" / "ARR"

**Monthly Recurring Revenue.** The amount of money a subscription
business is earning every month, totaled across all customers. "$10k
MRR" means $10,000/month coming in from paying customers. **ARR** is
**Annual Recurring Revenue** (just MRR × 12). These are the standard
metrics for SaaS businesses.

### "Acqui-hire"

A company "acqui-hires" another company when they buy the company
primarily to get the *people*, not the product. The product is often
shut down or absorbed. The founders/engineers get hired with signing
bonuses and 4-year retention packages.

This is different from a real acquisition where the buyer keeps the
product running and the customers/revenue matter. Acqui-hires are
fundamentally **hiring deals dressed up as M&A.**

**For SourcePrep:** if Anthropic "acqui-hired" you, they'd hire you as
an engineer, probably with a $300k–$1M signing bonus, and SourcePrep
either gets shut down or absorbed into Claude Code internals. You'd
become an Anthropic employee for 4 years (the cliff/vesting period).

### "Conversion rate" (free → paid)

If you have a freemium product (free tier + paid tier), the
**conversion rate** is the percentage of free users who upgrade to
paid. For developer tools specifically, this is **1–3%** on average.
Most freemium developer tool users never pay. This is critical for
sizing how big a free user base needs to be before paid revenue is
meaningful.

**Example:** if SourcePrep has 10,000 free OSS users and a 2%
conversion rate, that's 200 paying customers. At $20/month each,
that's $4,000 MRR — not "rent money" in most cities.

### "Network effects"

A product has network effects when each new user makes the product
*more valuable to other users*. Facebook has network effects — more
users = more reasons to be on it. A code editor like VS Code does
not — your VS Code experience doesn't change based on how many other
people use VS Code.

**Why this matters for SourcePrep:** code intelligence tools have
*no* network effects. A solo developer using SourcePrep doesn't make
SourcePrep more valuable to another developer. This is good news
because it means **scale isn't a moat** — a well-funded competitor
can't lock you out via network effects the way Facebook locks out
new social networks.

### "Christensen's disruption theory"

Clayton Christensen's *Innovator's Dilemma* (1997) described how
incumbents — big established companies — lose markets to smaller
upstarts. Two patterns matter:

- **Low-end disruption:** the upstart sells a cheaper, worse version
  to customers the incumbent overserves.
- **New-market disruption:** the upstart sells to customers the
  incumbent ignores — non-consumers, people priced out of the market.

The incumbent ignores the upstart because the upstart's customers
aren't profitable for the incumbent — until eventually the upstart
moves upmarket and eats the incumbent's customers.

**Why this matters for SourcePrep:** Sourcegraph is the incumbent for
code intelligence. In July 2025 they killed their free/individual
plan and went to $59/seat enterprise-only. They *vacated* the
solo-developer market because it wasn't profitable for them. SourcePrep
sits in that vacated market — which is exactly the new-market
disruption pattern.

### "Commoditization"

When something becomes a generic, undifferentiated feature that
anyone can build, it's been commoditized. Once commoditized, it's
hard to charge money for it because customers can get it for free
from many sources.

**For SourcePrep:** semantic search over codebases (RAG) is
commoditizing — every tool ships some version of it. Structural code
intelligence with concept extraction and trace graphs is *not* yet
commoditized. The defensible part of SourcePrep is the structural
stuff, not the RAG.

### "Rug pull" (in OSS context)

When a company releases their product as open source, builds a user
community, then later changes the license to make it proprietary or
restricted. Users feel cheated because they invested time and money
based on the OSS promise.

**Famous examples:** MongoDB (2018), Elastic (2021), HashiCorp Terraform
(2023), Redis (2024). After each rug pull, the community typically
forks the last open version and keeps developing it — Valkey (forked
from Redis), OpenTofu (forked from Terraform), OpenSearch (forked from
Elasticsearch).

**Why this matters for SourcePrep:** users are now suspicious of
single-vendor OSS projects. They're scared of investing in something
that'll get rug-pulled. The license you choose is partly a signal
about whether you might rug-pull.

### "Permissive" vs "copyleft" licenses

The two main families of OSS licenses:

- **Permissive** (MIT, Apache 2.0, BSD) — you can do almost anything
  with the code, including using it in a closed-source commercial
  product. Most enterprise-friendly.
- **Copyleft** (GPL, AGPL, LGPL) — if you build on this code, your
  derivative work must also be released under the same license. **AGPL**
  is the strictest: if you use AGPL code to power a *service* (not just
  ship software), you must also open-source the service.

**Why this matters for SourcePrep:** Apache 2.0 lets anyone (including
Anthropic) integrate SourcePrep into their commercial closed-source
products freely. AGPL would force them to open-source whatever they
built on top — which they generally won't accept. So Apache is more
"acqui-hire friendly" and AGPL is more "we mean it" / anti-rug-pull
because hyperscalers can't fork-and-host you.

---

## Part 3 — What the research actually found

Now we get to the findings. Each one ends with a section called
"**What this means for SourcePrep**" that translates the academic
finding into concrete strategic implications.

### Finding 1 — OSS-as-signal works, but rank matters more than commits

**The research:**

A 2002 economics paper by Lerner & Tirole proposed that programmers
contribute to OSS partly as a signal to future employers (and the
labor market values that signal). A 2005 follow-up by Hann, Roberts
& Slaughter tested this empirically on the Apache web server project
— they tracked contributors' careers and wages.

What they found:
- Just *contributing* to OSS doesn't measurably raise your wages.
- But *achieving a high rank* in the project (becoming a committer
  with merge access, then a PMC member, then a chair) raises wages
  by up to **18%**.

A 2025 follow-up by Goldbeck & Abou El-Komboz tracked ~22,900 GitHub
developers across job-search events. They found OSS activity spikes
~16% during job-search windows. Critically: developers shift toward
visibility-maximizing projects (popular repos, in-demand languages)
during job search, even when those projects have lower community
value. This means the labor market *literally reads* OSS-as-signal
in 2024–2026. It's not folklore; it's measurable behavior.

A 2025 paper by Galdin & Silbert tested what happens when LLMs make
text cheap. They found that *written* signals (cover letters,
résumés) lost their value — employers stopped paying attention
because LLMs could generate them. But *non-text* signals (working
code, project artifacts) became *more* valuable in relative terms.

**What this means for SourcePrep:**

Your OSS project is a strong signal — *if* you are unambiguously
the architect/maintainer/lead. As a solo developer, you'd be in
the maximum-rank position by definition (it's all you). That's
structurally similar to being an Apache PMC chair.

Critically, the *coherence* of the project matters more than the
*size*. A well-architected SourcePrep that visibly works and has a
clear technical story is a better signal than a sprawling project
with broken parts. This is why fixing the known product bugs
*before* launch is now critical — broken pipeline stages or visible
known-bad behavior turns the signal from "this person can build
hard things" into "this person ships unfinished work."

The 2025 LLM finding is *especially* good news. Cover letters and
résumés are being commoditized away. A working codebase — which
LLMs cannot fake, because faking would require the code to actually
work — is now *more* valuable as a hiring signal than it was 5 years
ago.

### Finding 2 — Anthropic publicly bet AGAINST native code indexing

**The research:**

Claude Code's architecture is documented (in Anthropic's own
materials and Pragmatic Engineer's March 2026 industry survey) as
*deliberately index-free*. Instead of pre-computing embeddings and
storing them in a vector database, Claude Code does live filesystem
traversal and targeted grep at query time. Anthropic explicitly
markets this as a design principle: "no staleness, no re-embedding
pipeline."

By contrast, Cursor uses RAG + Turbopuffer vector DB + custom
embeddings — the opposite architectural bet.

Anthropic's recent acquisitions tell a story:
- **Bun (Dec 2025):** JavaScript runtime. Used by OpenAI, Google,
  Cloudflare. Acquired partly to deny competitors access.
- **Humanloop (Aug 2025):** AI evaluation platform.
- **Stainless (May 2026):** SDK generation tooling, ~$300M reported.
  Used by OpenAI, Google, Cloudflare — same denial logic.

Pattern: Anthropic buys teams whose work either (a) plugs a
capability gap in Claude Code, or (b) is infrastructure competitors
also depend on.

**What this means for SourcePrep:**

The thing I worried about most in the scrutiny — "what if Anthropic
just builds native codebase indexing into Claude Code and makes
SourcePrep irrelevant?" — is *less* likely than feared. Anthropic
has publicly committed to the *opposite* architecture and they keep
doubling down on it.

This is good news *and* a strategic clue: Anthropic sees indexing
as a third-party concern. They want partners (like SourcePrep) to
fill that role via MCP, not to build it internally. That's the
acqui-hire thesis in a nutshell — they don't want to build it, so
they'd rather buy the team that did.

**But:** the real competitive threat is now **Cursor SDK** (released
April 29, 2026). Cursor's hosted indexing-as-a-service can be called
from any agent. If Cursor SDK becomes the default code-intel layer
for the long tail of AI agents, SourcePrep gets routed around. This
threat replaces "Anthropic native indexing" as the principal worry.

### Finding 3 — The 60-day acqui-hire timeline is a mirage

**The research:**

Every named acqui-hire I cited as a template had massive prior
reputation:

| Founder | Project | Prior background |
|---|---|---|
| Peter Steinberger | OpenClaw → OpenAI | Founded PSPDFKit, $116M Insight Partners exit 2021 |
| Jarred Sumner | Bun → Anthropic | Thiel Fellow, Stripe alum, $26M Kleiner/Khosla funding |
| Charlie Marsh | Astral → OpenAI | Princeton CS, Khan Academy senior eng, VC-backed |

Sumner's Bun took **3.5 years** from first release to acquisition.
Marsh's Ruff/uv took **3.5 years**. Steinberger's OpenClaw took 60
days *because Steinberger already had a $116M exit and Satya Nadella
called him personally.*

**For a solo developer with no prior exit**, there are zero
documented cases in the 2024–2026 AI tooling cycle of going from
public OSS launch to frontier-lab acqui-hire.

Strategic Management Journal research (Boyacıoğlu 2024, Pierri et al.
2025) on acqui-hire outcomes confirms: solo founders without
venture-backed prior exits are *systematically* less likely to be
acqui-hired and *less* retained when they are.

A calibrated probability estimate, based on the comparable cases:

- **Probability of acqui-hire within 12 months: ~1–3%**
- **Probability of senior IC role offer within 6 months: ~8–15%**
  (could reach 25% with active outreach)

**What this means for SourcePrep:**

The 90-day-to-acqui-hire framing in the original plan was wrong.
The base rate is somewhere between 1 and 3 in 100. That's worth
buying as a lottery ticket — but you cannot plan around it as the
*primary* outcome without being delusional.

The *primary* outcome to plan around is **landing a senior IC role
at one of the named target companies via OSS visibility + direct
outreach + applications.** The probability is 5–15× higher and
totally within reach for a competent solo developer with a
well-executed OSS launch.

The compensation comparison is also worth knowing:

- Anthropic senior engineer median total compensation (per Levels.fyi):
  ~$710k/year
- Top of band: $1M+
- An acqui-hire signing bonus for a solo founder, conditional on it
  happening at all, is probably $300k–$1M one-time plus a 4-year
  retention package roughly equal to senior comp

So an IC offer at Anthropic and a successful acqui-hire are
**roughly the same financial outcome over 4 years.** The acqui-hire
has a slightly higher upfront component; the IC role has no
"shutdown your product" downside. Both pay you to work on AI infra
at a frontier lab.

### Finding 4 — Solo dev-tool revenue is brutally low

**The research:**

Cross-validated across three datasets (RockingWeb's 1,000-product
analysis, Freemius platform data, MicroConf annual survey):

- **Median solo dev-tool MRR: ~$500/month**
- **~70% of projects never cross $1k MRR**
- **Only ~4% ever reach $10k MRR**
- **<1% ever reach $50k MRR**

These are *lifetime* numbers (not year-1) — most projects die long
before reaching their lifetime cap.

The gold-standard OSS-first solo dev tool benchmark is **Plausible
Analytics** (a privacy-focused Google Analytics alternative). Their
timeline:
- Month 14: $400 MRR
- Month 23: $10k MRR
- Month 36: ~$1M ARR

Plausible was 2 co-founders working full-time. They had a clear
ICP (privacy-conscious analytics buyers, a real underserved niche)
and Twitter/content distribution. They are roughly the **best case**
for OSS-first solo-ish dev tools, and they needed nearly 2 years
to reach "rent money" levels of revenue.

Developer tool free-to-paid conversion rates are **1–3%** — half
the rate of non-developer SaaS. Open-core specifically converts at
**well under 1%** of free downloaders. GitHub stars are essentially
*uncorrelated* with revenue at a measurable level.

Tidelift's 2024 maintainer survey (N>400): **47% of OSS maintainers
get paid $0.** Of the 32% who get paid anything, the median income
is under $100/month. Less than 5% of OSS maintainers earn a livable
income from their projects.

**What this means for SourcePrep:**

The "instant cash flow from a free + Pro tier" thesis is essentially
hopeless on a 12-month timeline for a solo dev with no prior audience.
The realistic numbers:

- If you went closed-source SaaS today, expected year-1 revenue is
  probably **$3k–$15k total** (not per month). The chance of crossing
  $10k MRR within 12 months is **3–6%**.
- If you went OSS-first, expected direct revenue is **near zero** for
  the first 12+ months. The Pro tier conversion happens, if at all,
  in year 2 or 3.

This isn't a moral failure or an Eric-specific problem — it's the
distribution of outcomes across the entire solo dev tool market.
Almost everyone earns very little.

**The opportunity cost is significant:** a senior AI infra engineer
role at a frontier lab pays $400k–$700k+ per year in total
compensation. Spending 12 months solo to earn $5,000 in dev-tool
revenue *while passing up* on applying for $500k IC roles is, on the
expected-value math, a clear mistake.

**The corollary:** OSS-first isn't a sacrifice of "instant cash flow."
There was no instant cash flow available. OSS-first is choosing the
higher-EV path (land an IC role) over the lower-EV path (build a
closed-source product hoping to hit the 4% who reach $10k MRR).

### Finding 5 — License choice is genuinely contested now

**The research:**

After the 2018–2024 rug-pull cycle (MongoDB, Elastic, HashiCorp,
Redis), users have learned to distrust permissively-licensed
single-vendor projects. The market reaction to a rug pull is
*reflexive forking* — Valkey (Redis fork), OpenTofu (Terraform fork),
OpenSearch (Elasticsearch fork) — all created within months of the
license changes.

Elastic *partially reversed* in 2024 by adding AGPLv3 as an option,
explicitly to recover trust. This signals that AGPL is the
license-as-credibility-device — it's hard to rug-pull AGPL because
the strict copyleft means any forked version is also free, so the
threat that keeps users "trapped" doesn't exist.

But: AGPL is acquisition-hostile. Acquirers' legal teams flag it as
a risk. Permissive licenses (Apache 2.0, MIT) clear those legal
hurdles cleanly.

The trade-off:

| | Apache 2.0 | AGPL |
|---|---|---|
| Friendly to acqui-hire (1–3% scenario) | Yes | No |
| Trust signal in 2026 (95%+ scenarios) | Neutral | Strong |
| Hyperscaler can clone-and-host you | Yes | No |
| Adoption ceiling | Higher | Slightly lower (enterprise allergy) |
| Anti-rug-pull credibility | Requires extra commitment | Built in |

**What this means for SourcePrep:**

The original recommendation in STRATEGY.md was Apache 2.0 on the
logic that "we want to be acqui-hireable." Given the calibrated
probabilities (1–3% acqui-hire), optimizing the license for the rare
case is questionable.

**The realistic argument for AGPL:** it builds in the anti-rug-pull
signal that the market increasingly demands. It protects against
hyperscaler clone-and-host. It signals "we mean it" to skeptical
adopters.

**The realistic argument for Apache 2.0:** it maintains acqui-hire
optionality. It's the license Anthropic, Bun, and Astral all use
(or used). It's the simplest legal story.

This is now a genuine call where the right answer depends on Eric's
priorities. I leaned Apache 2.0 originally; the data suggests AGPL
deserves serious reconsideration.

---

## Part 4 — What this means for the plan we wrote

The plan in `IMPLEMENTATION_PLAN.md` was built around assumptions
that this research now updates. Concretely:

### What needs to change

**1. Lead with "IC role at frontier lab" not "acqui-hire."**

The README's success criteria, the STRATEGY's narrative, and the
ACQUIRER_MAP's framing all need to invert. The headline outcome is
landing a senior engineering role. Acqui-hire is the lottery-ticket
bonus.

This is more honest *and* more actionable, because applying for jobs
is a real, tractable process. Hoping someone calls about acqui-hire
is not.

**2. Extend the timeline from 90 days to 12 months.**

The data says:
- IC offer pipeline: 6–12 months from start to signed offer
- OSS revenue traction: 18+ months in the best case
- Acqui-hire conversations: no median exists

A 90-day success window was too aggressive by 3–6×. Phase 142 should
have a 12-month success horizon with milestones at 90 days (Show HN
shipped), 180 days (job applications submitted), 270 days (interviews
in progress), and 365 days (offer or fallback).

**3. Bring job applications forward to Week 2.**

The original plan put applications in Week 6+. Interview cycles take
6–10 weeks. If applications go out Week 6, offers don't materialize
until Week 12–18. If applications go out Week 2, offers can land by
Week 8–12 — well within a 12-month plan.

OSS visibility and direct outreach (from Show HN, blog posts, etc.)
*supplements* applications — they don't replace applications.
Applications are the actual pipeline; everything else is the warming.

**4. Make product fixes blocking, not optional.**

The signaling research is clear: *coherence* of the project matters.
Bugs visible to a Show HN audience or a recruiter who clones the
repo damage the signal. Known issues from Eric's memory (search-doc
bias, synthesizer silent fails, pipeline sequencing) need to either
(a) be fixed before launch, or (b) be visibly disabled with clear
documentation explaining the choice.

This is a new `Part A.5` in `IMPLEMENTATION_PLAN.md`.

**5. Replace "Anthropic native indexing" worry with "Cursor SDK adoption" worry.**

The original SCRUTINY §14 (what if Anthropic ships native indexing?)
is now downgraded — they've publicly bet against it. A new
SCRUTINY §21 should be added: "What if Cursor SDK becomes the
default code-intel layer for the long tail of AI agents?" Defense
remains the same (MCP-native, IDE-agnostic, Apache or AGPL), but
the strategic framing reorients.

**6. Reopen the license decision (Apache 2.0 vs AGPL).**

The original recommendation was Apache 2.0 optimized for acqui-hire.
Given acqui-hire is 1–3%, the AGPL trade-off becomes more attractive.
This is Eric's call — but it shouldn't be a default; it should be a
considered choice.

### What stays the same

- The overall Path D strategy (OSS-first, with Pro tier as fallback) is *validated* by the research, not undermined. The case for OSS over closed-source is stronger after this round.
- The gstack positioning (complementary, not competitive) is still right.
- The structure of the plan (Parts A through H) is sound.
- The Acquirer Map's specific named targets are still the right targets.

---

## Part 5 — The five decisions left for Eric

After all this research, only five questions remain that genuinely
need your input. Everything else is a downstream consequence of
these.

### Decision A — License: Apache 2.0 or AGPL?

**Apache 2.0** keeps acqui-hire optionality (1–3% scenario) and aligns
with Anthropic's MCP ecosystem. Cleaner legal story. Hyperscalers can
clone-and-host you, but at your scale that's an unlikely near-term
threat.

**AGPL** signals strong commitment to OSS, prevents hyperscaler
cloning, addresses post-rug-pull market suspicion, but creates legal
friction with potential acqui-hirers and may slow enterprise adoption.

**What I recommend:** Apache 2.0 *if* the acqui-hire optionality
genuinely matters to you. AGPL *if* the trust signal and anti-clone
protection matter more. **Lean Apache 2.0** given Anthropic
ecosystem alignment, but it's a real choice.

### Decision B — Timeline: 90 days or 12 months for Phase 142 success?

12 months is realistic. 90 days is fantasy. The hard question is
whether your runway supports a 12-month horizon.

**What I recommend:** 12 months with milestone gates (described above
in section 2).

### Decision C — Headline outcome: IC role or acqui-hire?

Math says IC role is 5–15× more probable. Plan currently leads with
acqui-hire.

**What I recommend:** flip. Lead with IC role; treat acqui-hire as a
bonus.

### Decision D — Product fixes: defer or block?

Bugs visible to launch audience damage the signal. Either fix or
visibly disable known issues before launch.

**What I recommend:** block. Add `Part A.5 — Demo-Blocking Fixes` to
the implementation plan. If a known issue can't be fixed in one
week, document it as a known limitation in the README. Don't ship
with broken-by-default behavior.

### Decision E — Runway (private question, just to me)

How many months of personal runway do you have?

- <6 months: only IC role pathway is viable. Cut Pro tier development entirely. Start applications Week 1, not Week 2.
- 6–12 months: balanced plan as revised here works.
- 12+ months: full optionality preserved.

I don't need a number in a document; just your honest answer in the
chat so I can calibrate.

---

## Part 6 — What we still don't know

Even after this round, here's what the research did *not* settle:

- **Whether SourcePrep is actually load-bearing for any frontier
  lab's product.** The acqui-hire data says load-bearing is the
  acquisition criterion. We don't yet know if Anthropic considers
  code intelligence load-bearing for Claude Code, or if they
  consider it an interesting but optional partner play.

- **The realistic minimum audience size where OSS signaling kicks
  in.** Goldbeck's data was a 22,900-developer panel. We don't know
  if the signaling effect works at 100 stars vs. 1,000 stars vs.
  10,000 stars. Common sense says more = better, but the curve
  shape is unknown.

- **Whether the "Pro tier exists in the future" framing damages OSS
  adoption.** Some communities are allergic to anything with a
  hint of commercial intent. Others welcome it. Empirical evidence
  is anecdotal and contradictory.

- **The specific person at each acquirer/employer who is the right
  contact.** The ACQUIRER_MAP names teams but not individuals. This
  requires real outreach research before Part H of the plan starts.

- **Whether Eric's prior career/work would change the acqui-hire
  probability.** Steinberger's $116M exit was the dominant factor
  in his 60-day timeline. Eric's actual professional history is
  not documented in the research (and shouldn't be in this
  document) — but it affects the calibration. A "prior senior IC
  at FAANG" history shifts the IC-offer probability up. A "prior
  exit" shifts the acqui-hire probability up. A "no prior
  industry presence" keeps the calibration as-stated.

These are flagged so they're not forgotten if we want to do a
third round of research later.

---

## Part 7 — What happens next

Once Eric makes the five decisions (A through E above), I will do
one consolidated revision of all six Phase 142 plan files:

- `README.md` — update success criteria, status, scope wording
- `STRATEGY.md` — flip outcome ordering, lock license choice
- `IMPLEMENTATION_PLAN.md` — add Part A.5, reorder H.2, extend timeline
- `SCRUTINY.md` — downgrade §14, add new §21 (Cursor SDK), lock decisions
- `ACQUIRER_MAP.md` — reframe IC role first
- `RESEARCH.md` — point at this document for the second-round findings

After that, I create the `TaskCreate` TODO list against the *revised*
plan. The user (Eric) executes from the TODO list.

This research round is not a blocker — it's a sharpener. The
original plan was directionally right (OSS-first); this round
corrects the calibration so the execution doesn't fail for
predictable reasons.

---

## Source citations

The full citations from the four research agents are preserved in
the conversation transcript. The most consequential papers and
reports for future reference:

**OSS economics & signaling:**
- Lerner & Tirole, "Some Simple Economics of Open Source" (2002)
- Hann, Roberts & Slaughter, "Delayed Returns to OSS Participation: Apache" (2002–2006)
- Goldbeck & Abou El-Komboz, "Career Concerns as a Public Good: The Role of Signaling for OSS" (*Labour Economics*, 2025)
- Galdin & Silbert, "Making Talk Cheap: Generative AI and Labor Market Signaling" (arXiv 2511.08785, Nov 2025)
- Marlow & Dabbish, "Activity Traces and Signals in Software Developer Recruitment" (CSCW 2013)

**AI dev tools market structure:**
- a16z, "Notes on AI Apps in 2026" (Jan 2026)
- Pragmatic Engineer, "AI Tooling for Software Engineers in 2026" (Mar 2026)
- Gartner Magic Quadrant for AI Code Assistants (Sept 2025, May 2026 update)
- "Old Moats for New Models" — NBER Working Paper w32474

**Acqui-hire economics:**
- Boyacıoğlu, "Acqui-hires: Redeployment and retention" (*Strategic Management Journal* 2024)
- Pierri et al., "Does acqui-hiring pay off?" (*Small Business Economics* 2025)
- Zhang, "Advantage of Experienced Start-Up Founders" (*Small Business Economics* 2011)
- MIT Sloan / Kim, ~4,000-acquisition study on acquired-employee retention
- CB Insights, "Acqui-hire Report"
- Levels.fyi compensation data (May 2026)

**Solo dev-tool revenue:**
- MicroConf, "State of Independent SaaS" (annual survey)
- RockingWeb / SaaSRanger, 1,000-product micro-SaaS analysis
- Freemius, "State of Micro-SaaS 2025"
- Tidelift, 2024 Maintainer Survey
- Open Core Ventures Handbook
- Plausible Analytics, public revenue disclosures
