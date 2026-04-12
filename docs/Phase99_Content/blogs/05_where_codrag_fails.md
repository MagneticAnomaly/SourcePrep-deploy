# 05 — Where CoDRAG Fails

**Status:** ✅ Feasible. This essay's raw material is the feasibility audit itself plus any real failures observed during essays 01–04.
**Depends on:** nothing that isn't already there. The essay is built from honest observation, not a new experiment.
**Does not depend on:** anything working better than it currently does.

## The premise

Every serious developer tool has a list of things it doesn't do well yet. Most tools hide that list. The ones that publish it tend to get more credibility, not less, because the gap between "what the marketing says" and "what the code does" is the thing experienced readers are scanning for anyway. If you close that gap yourself, you remove the suspicion.

This essay is CoDRAG's public gap list, written by the person who built it.

## What it catalogs

The audit in `00_feasibility_audit.md` plus anything observed during essays 01–04. The cataloged failures fall into three honest categories:

### 1. Framework-without-runtime

- **Concepts + antibodies.** The data model is real. `codrag_audit(action="antibodies")` lists what was derived from concept assertions. But there is no runtime monitoring loop that evaluates antibodies against code changes and emits alerts. CoDRAG's CLAUDE.md describes "immune system alerts in ambient context" as if they work. They are not currently firing. This is a gap between the writing and the code, which is the worst kind of gap and the most important to acknowledge.

### 2. Simpler-than-it-could-be

- **Hub ranking is z-score, not PageRank.** For small and medium codebases this is usually fine. For large codebases it diverges from true centrality. Aider's repo map uses personalized PageRank via `networkx.pagerank` and is objectively more sophisticated at this specific task. CoDRAG's advantage is in the surrounding atlas (module clusters, entry points, cross-cutting concerns), not in the ranking algorithm itself. Pretending otherwise is dishonest.
- **Atlas narrative summaries depend on LLM quality.** When CoDRAG generates module summaries, the quality is a function of whichever LLM is configured. The summaries can drift, repeat, or hallucinate connections that aren't in the graph. CoDRAG does not currently have a robust check for summary-vs-graph consistency.

### 3. Scale-unproven

- **Nothing published larger than ~2k files.** 17 real test repos live in `tests/eval/real_repos/`. None are larger than a few thousand files. Claims about how CoDRAG performs on a 50k-file monorepo are claims without evidence. The honest answer to "can CoDRAG index Linux" is "I don't know yet."
- **External repo initialization UX is under-documented.** The backend supports it. The user-facing flow isn't obvious and probably has rough edges.
- **Pipeline sequencing bug.** The project memory notes a real issue with deep enrichment stages not advancing on certain inputs (state machine regressions from Phase 76/89/91/92). This affects any essay that assumes the deep-enrichment layer is reliable.

### 4. Parser-layer honesty

- Static graphs miss dynamic dispatch, reflection, runtime plugin systems, monkey-patching, and anything that rebinds names at runtime. Python and Ruby codebases with heavy metaprogramming are the hardest case. CoDRAG's impact analysis has the same blind spots as every static analyzer — it only sees edges that exist at parse time.

## What the essay argues

One claim, patiently: **tools that describe themselves accurately are more useful than tools that describe themselves aspirationally**, because the second kind waste their users' time on things that don't work.

The essay then walks each gap, explains what the current state actually is, and — where possible — names the fix that would close it. For some gaps (PageRank adoption) the fix is small and concrete. For others (antibody runtime monitoring, scale testing on large repos) the fix is real work and honest to mark as such.

## Honesty checks — what could go wrong

- **The essay might read as a laundry list of regrets.** Tone matters. The goal is "here is a tool I built, here is what I know about its limits, here is how I plan to address them." Not "I am sorry, here is my apology." Armin Ronacher's writing is the model — opinionated, clear-eyed, no self-flagellation.
- **The essay might be used against CoDRAG by competitors.** It might. It might also be used *for* CoDRAG by evaluators who appreciate seeing a founder who is honest about their own tool. The second effect is usually larger in the audience that matters (senior developers evaluating dev tools). Competitors trash-talking an honest post-mortem look worse, not better.
- **The gaps might be fixed before publication.** Good problem. If the antibody runtime monitor lands between now and publish date, remove that item and add it to a "what changed" note. The essay is always a snapshot of a specific moment in the tool's development.

## Limitations to acknowledge in the essay

- The list is not exhaustive. It's what was surfaced by one feasibility audit on one date. Users will find more.
- Some items are judgment calls (e.g., is z-score "simpler than it should be" or "fit-for-purpose at this scale"?). The essay should not pretend every item is equally urgent.

## Publishing target

Medium-length post, 2000–3000 words. Personal tone. Possible title: "The Gap List: What CoDRAG Doesn't Do Yet." Reference posts to study for voice: Armin Ronacher's retrospective posts on his own tools, any of Thorsten Ball's "notes from building" posts, Paul Gauthier's occasional honesty posts on Aider's limitations.

## What to link to

- `00_feasibility_audit.md` (if published publicly — or a sanitized version of it)
- The specific CoDRAG source files where each gap lives
- Aider's `repomap.py` for the PageRank reference
- Any linked roadmap / issues where the gaps are tracked

## Next action

This essay does not need a new experiment — it needs essays 01–04 to have been run, so that real-world observations can be folded in alongside the static audit findings. Publish last. Reread before publishing to check the tone is clear-eyed rather than apologetic.
