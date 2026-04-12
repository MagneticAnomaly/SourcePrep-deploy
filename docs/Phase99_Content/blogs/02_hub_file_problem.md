# 02 — The Hub File Problem

**Status:** ✅ Feasible. Requires live Claude Code session for comparison.
**Depends on:** `codrag_impact` MCP tool (transitive, max_hops configurable), hub detection via `codrag_audit`, a Claude Code session without CoDRAG attached, and a Claude Code session *with* CoDRAG attached.
**Does not depend on:** concepts, antibodies, or scale-sensitive features.

## The premise

Every codebase has a handful of files where a wrong edit cascades silently. Senior developers learn which ones by scar tissue: "don't touch that without running the full suite." AI coding assistants have no equivalent intuition. They treat every file as approximately equal until proven otherwise, and "proven otherwise" usually means *after the bug report comes in*.

This essay is the specific version of that observation, run as an experiment.

## The scenario to run

1. **Pick the repo.** A medium-size test repo where you can credibly pretend to be an outsider. Recommended: `gin-go` or `click-python` from `tests/eval/real_repos/`. Both are real libraries, both have clear hub files, both are small enough that Claude Code can read them in a few turns.
2. **Find the hub.** Run `codrag_audit` and extract the top hub file (highest in-degree, or highest z-score on the hub bottleneck check). For `gin-go` this is likely `context.go`; for `click-python` it's likely `core.py`. Verify by hand — if CoDRAG's hub detection picks something trivially utility-ish (constants, logging helpers), pick the second or third result instead.
3. **Identify a candidate edit.** Pick one function or method in the hub file. Choose something that has real callers — not a private helper, but a public entry point. Record the function name and signature.
4. **Trial A — Claude Code alone.** Start a fresh Claude Code session with *no* CoDRAG MCP server attached. Open the repo. Ask: *"I'm considering renaming `<function_name>` in `<file>` to `<new_name>`. What do I need to check before making this change?"* Let it work. Log every file it reads (Claude Code shows its tool calls). Save its full answer.
5. **Trial B — Claude Code + CoDRAG.** Fresh session. Same repo. CoDRAG MCP server attached. Same question. Log tool calls and the answer.
6. **Ground truth.** Run `codrag_impact` directly on the function with `max_hops=3` or higher. Also run a simple grep for the function name as a sanity check. These two together are your ground truth for "what depends on this function."

## What to record

- Raw `codrag_audit` output showing hub detection
- The chosen function and its signature
- Full transcript of Trial A (files read, answer given)
- Full transcript of Trial B (files read, `codrag_impact` output if called, answer given)
- The ground-truth dependent list from direct `codrag_impact` + grep
- Delta: what Trial A missed vs ground truth; what Trial B missed vs ground truth

Save to `02_hub_raw_output.md` before drafting prose.

## What the essay argues

The argument is not "Claude Code is bad." It's more precise: **without structural priors, a tool's blast-radius estimate is a guess wearing a confident voice.** Claude Code may read several files and form a reasonable answer, but it has no systematic way to know when it's done. CoDRAG's contribution is not intelligence — it's *completeness*. A graph-backed impact query is either correct or wrong; it doesn't trail off.

The essay shows the comparison on one concrete function in one concrete file. No extrapolation to "this is how AI coding tools work in general." Just the one case.

## Honesty checks — what could go wrong

- **Claude Code might get it right.** It is pretty good. If its answer covers the full dependent set, write that: "Claude Code got this case right. Here's the specific reason it was tractable — the function name was distinctive enough to grep, the callers were in obvious locations, and the harness had enough file-read budget to cover them. Now here's a case that's harder." Then pick a harder case and run it.
- **CoDRAG might get it wrong.** If `codrag_impact` misses a caller that grep finds, that's an honest limitation to report. It probably means the parser missed a dynamic import or a reflection-based call. This is information and belongs in the essay.
- **The comparison might be confounded.** Claude Code with web access or advanced tool use might read the same files CoDRAG identified by a different route. If so, the essay shifts: "Claude Code arrived at the same answer by reading 14 files; CoDRAG arrived at it by running one query. The cost difference is the story, not the correctness difference."
- **The hub might not be interesting.** If the hub file is a trivial utility, the consequence of a wrong edit is small and the essay has no stakes. Pick a different hub.

## Limitations to acknowledge in the essay

- `codrag_impact` traverses the static import/call graph. It cannot see dynamic dispatch, reflection, late binding, plugin systems, or anything that hides edges at runtime. A plugin-heavy codebase would weaken the argument.
- CoDRAG's hub detection uses z-score on in-degree (see `00_feasibility_audit.md`). This is simpler than Aider's personalized PageRank. For some repos, CoDRAG might pick a hub that PageRank would deprioritize. Note this up front.
- The experiment is a sample size of one. The essay should not generalize to "AI coding tools can't do blast radius." It should say "here is one case where the difference was visible."

## Publishing target

Personal blog post, 1500–2500 words. Two-column comparison format for the tool outputs. Screenshots of both Claude Code sessions are fine — they're self-documenting and more credible than prose.

## What to link to

- The repo being tested (so readers can reproduce)
- The specific commit SHA used (to pin the state of the codebase)
- CoDRAG's hub detection source (`src/codrag/core/audit/analyzers/hub_bottlenecks.py`)
- Aider's repo map (for readers who want to see a different serious attempt)

## Next action

Run this only after essay 01 has confirmed the experimental format works. Needs Claude Code + CoDRAG wired up together, which adds one more failure mode to manage.
