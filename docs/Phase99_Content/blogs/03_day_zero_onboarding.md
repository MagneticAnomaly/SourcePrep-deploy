# 03 — Day Zero in an Unfamiliar Codebase

**Status:** ✅ Feasible, scale-bounded. Requires at least two AI harnesses for comparison.
**Depends on:** Prep atlas generation (`src/prep/core/atlas/generator.py`), a harness without Prep attached, and the same harness with Prep attached. Second (and ideally third) harness for triangulation.
**Does not depend on:** concepts, antibodies, or large-scale indexing (stays within test-repo bounds).

## The premise

The first question a developer asks when they clone a repo they've never seen is some version of "where do I start reading?" AI coding assistants answer this question constantly, usually by reading file names and top-level directory structure and guessing. Sometimes the guess is fine. Sometimes it puts the developer in the wrong part of the codebase for an hour.

This essay tests what several harnesses actually know about a codebase *before they read anything*.

## The scenario to run

1. **Pick the repo.** Medium-size test repo from `tests/eval/real_repos/`. Recommended: **`gin-go`** (well-known, non-trivial, has clear architectural layers). Alternative: `sqlmodel-python` for a Python-first run.
2. **Pick the harnesses.** Minimum: Claude Code (terminal) and Cursor. Ideal: add Cline or Windsurf as a third point. You already have Claude Code set up; the test repo size keeps the others cheap to run.
3. **The cold question.** In each harness, with a fresh session and no Prep attached, open the repo and ask: *"I just cloned this repo. Tell me the 15 files I should read first to understand the architecture, and why."* Record each answer in full — file list, reasoning, order.
4. **The Prep answer.** Run Prep's atlas on the same repo. Extract the hub files and entry points it surfaces. Compare that list to each harness's answer.
5. **Ground-truth read-through.** This is the part nobody skips: actually read the files on each list. Mark which files genuinely belong on a "15 most important" list for someone new, which are utility noise, and which are surprising-but-valid.

## What to record

- Raw transcripts per harness: file list, reasoning, order
- Prep atlas output: hub files, entry points, module clusters
- A comparison matrix: rows = files, columns = (harness A picked? harness B picked? Prep picked? your ground-truth verdict)
- A tally of overlap and disagreement
- The files everyone missed (if any) — the "shadow" set

Save to `03_day_zero_raw_output.md`.

## What the essay argues

Two honest claims. First: **"what the harness knows before reading anything" is the quiet axis nobody measures.** The answer a harness gives in its first turn is a function of its priors about codebase structure, and those priors are almost entirely absent today. Prep's atlas is one attempt to install priors.

Second: **the atlas is not automatically better than what a harness reads its way into.** For small or tidy repos, a harness with a good file-read strategy might arrive at the right files without any structural knowledge. The experiment is the place to find out.

The essay becomes interesting specifically where Prep picks a file no harness mentions, or vice versa. Boring agreement is not an essay. Disagreement is.

## Honesty checks — what could go wrong

- **All three harnesses might converge.** If Claude Code, Cursor, and Cline all name the same 10 files and Prep names 9 of those plus one more, the essay shrinks to "they all mostly agree; here's the one file that's interesting." That's still honest and still worth publishing if the one file matters.
- **The harnesses might outperform Prep.** Prep's hub detection is z-score on in-degree, which can overrate utility files (constants, logging helpers). If a harness picks the *right* files and Prep picks `utils.go`, the essay writes itself as a critique of Prep's current ranking — which is also honest and is the kind of piece that builds credibility.
- **The repo might be too tidy for meaningful differences.** `gin-go` is well-engineered; the "right" 15 files may be obvious. Consider running a second round on a messier repo (`sqlmodel-python`, or an older Python library) for contrast.
- **You might be wrong about ground truth.** Your read-through of the files is a judgment call. Acknowledge that explicitly in the essay — don't present your verdict as objective.

## Limitations to acknowledge in the essay

- Scale-bounded. The atlas has not been tested on codebases much larger than ~3k files. The essay can only claim what the experiment showed on a medium repo. A reader asking "does this hold on Linux, Chromium, Kubernetes?" gets the honest answer: "unknown, didn't test, here's why."
- Sample size is three harnesses. Not a survey. One datapoint per harness.
- The question is asked cold, once, with no conversation. Real onboarding is iterative — the harnesses might do much better on turn 3 or turn 10. Say so.
- Prep's atlas includes LLM-generated narrative summaries in some modes. If those summaries are part of the experiment, the comparison is partly measuring the summary-generation LLM, not just the structural layer. Separate the two if possible.

## Publishing target

Long essay, 2500–4000 words. Comparison matrix as a key visual. Section per harness, then a synthesis section, then a "what this implies" section. Geoffrey Litt's "Code Like a Surgeon" is the closest tonal reference for this kind of multi-harness exploration piece.

## What to link to

- The test repo and the commit SHA
- Each harness's documentation (Claude Code, Cursor, Cline/Windsurf)
- Aider's repo map for readers who want to see the "other" serious structural approach
- Prep atlas generator source

## Next action

Run this *after* essays 01 and 02. It's the most operationally complex — three live sessions, manual read-through, a comparison matrix — and benefits from knowing the experimental format works first.
