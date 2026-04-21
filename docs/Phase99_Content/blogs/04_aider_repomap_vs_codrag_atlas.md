# 04 — Aider's Repo Map vs Prep's Atlas

**Status:** ✅ Feasible. Requires Aider installed + Prep + a shared test repo.
**Depends on:** Aider CLI, Prep atlas, and honest willingness to publish findings even if Aider wins on some axis.
**Does not depend on:** concepts, antibodies, or any half-built Prep feature.

## The premise

Aider has done the best public thinking of any AI coding tool about how to give a model a map of a codebase *before* it starts answering. Paul Gauthier and contributors built a system that ranks files by personalized PageRank on a symbol graph extracted from tree-sitter tags. Prep is a different serious attempt at the same problem with a different design. Both exist. Both are open. They should be compared honestly.

This essay is not "Prep beats Aider." It cannot be. Prep's hub ranking is z-score on in-degree; Aider's is PageRank with personalization. On raw ranking sophistication, Aider is ahead. The essay is more useful than a competitive writeup: *what does each system actually see, and what do the design tradeoffs look like in practice?*

## Verified facts about Aider's repo map

From `https://github.com/Aider-AI/aider/blob/main/aider/repomap.py`:

- Uses `networkx` (`import networkx as nx`, line 368)
- Builds a `nx.MultiDiGraph` where nodes are files and edges are weighted by symbol references (line 470)
- Calls `nx.pagerank(G, weight="weight", **pers_args)` with optional personalization (lines 518–525)
- Personalization biases rank toward files relevant to the current chat context
- Symbol extraction is via tree-sitter tags (Aider uses `tree-sitter-language-pack`)

Aider's public docs at https://aider.chat/docs/repomap.html only call this "a graph ranking algorithm." The specificity comes from the source file.

## Known facts about Prep's atlas + hub detection

From Prep source, verified 2026-04-11:

- Hub detection: `src/prep/core/audit/analyzers/hub_bottlenecks.py`, z-score on in-degree, threshold z > 2.0 and min in-degree 8
- Atlas generation: `src/prep/core/atlas/generator.py`, produces workspace map, module clusters, entry points, cross-cutting concerns
- Symbol extraction is via Prep's Rust engine (tree-sitter under the hood, different integration path than Aider's)
- Prep optionally includes LLM-generated narrative summaries in the atlas; the underlying ranking does not use an LLM

## The scenario to run

1. **Pick the shared repo.** Must work with both tools. Recommended: **`gin-go`** — medium-size, well-known, Go, exercises the Go side of both tools' tree-sitter integration. Run against the same git SHA for both tools.
2. **Aider side.** Install Aider. Point it at the repo. Trigger repo map generation (ask a benign question that forces the map to be built). Capture the full repo map output — file list with scores if Aider surfaces them, or the ranked order if not.
3. **Prep side.** Run the full Prep indexing + atlas generation on the same commit. Capture the atlas document: hub files, entry points, module clusters, whatever the atlas produces.
4. **Compare at three levels.**
   - **Top-N file overlap.** Take the top 20 from each and measure intersection. Which files does Aider surface that Prep doesn't? Which does Prep surface that Aider doesn't?
   - **Architectural coverage.** Each tool tries to tell you "what this codebase is about." Do they cover the same architectural sections? Does one miss a whole subsystem?
   - **Cost.** Rough token cost and wall-clock time for each tool to produce its map. Aider's is fast and cheap; Prep's full atlas generation can be slower and may involve LLM calls depending on mode.
5. **Read-through sanity check.** For the top-20 files of each tool, read them (or at least skim) and ask: *does the ranking match my own intuition after reading?* This is the only way to judge whether the ranking is telling you something true or merely telling you something consistent.

## What to record

- Raw Aider repo map output, pinned to SHA
- Raw Prep atlas output, pinned to same SHA
- Top-20 file lists side by side
- Overlap counts and the symmetric differences
- Wall-clock time and approximate token cost per tool
- Your honest read-through verdict on each ranking: which file listings feel right, which feel off

Save to `04_aider_comparison_raw.md`.

## What the essay argues

Honest design taxonomy, not a competition.

- **Personalized PageRank (Aider):** classic centrality, edge-weighted by symbol references, biased toward the current chat. Fast to compute. Produces a single ranked list. Best when you want "the files most relevant to what you're doing right now" as a retrieval-layer prior.
- **Z-score on in-degree + multi-layer atlas (Prep):** outlier detection on structural fan-in, paired with module clustering, entry point detection, cross-cutting concern identification, and optional LLM summaries. Produces a *document* rather than a list. Slower. Best when you want "a map of the whole codebase" rather than "the N files most relevant to this turn."

These are different things. Both are valid. The essay argues that the choice reflects a deeper split: Aider is optimizing for the chat, Prep is optimizing for the atlas. A harness can have both.

If the experiment reveals that Prep's ranking is meaningfully worse than Aider's on the top-N file test, the essay says so plainly. Credibility requires it. The useful framing: **"Aider's PageRank is better at ranking; Prep's atlas is doing a different thing. Here is what I plan to fix in Prep as a result of this comparison."**

## Honesty checks — what could go wrong

- **Prep's ranking loses on the top-N test.** Plausible. If so, publish it and commit to adopting PageRank (or a centrality algorithm) in Prep. The essay becomes a public learning moment, which is a stronger piece than a shallow win.
- **The two tools produce lists so different they can't be compared.** If Aider returns 20 files and Prep returns an atlas document that doesn't cleanly enumerate files, normalize by extracting Prep's top-20 hub files for the comparison. Note the normalization in the essay.
- **Aider's ranking is chat-dependent.** Personalized PageRank uses the chat context as a seed. For a fair comparison, run Aider with an empty or neutral chat so the ranking is *unpersonalized*. Otherwise you're comparing Prep's static rank to Aider's query-biased rank, which is apples to oranges.
- **Aider and Prep parse different symbols.** Aider uses `tree-sitter-language-pack`; Prep uses its own Rust parser crate. The underlying graphs may not be identical even for the same codebase. Note this limitation; don't pretend the inputs are apples-to-apples.

## Limitations to acknowledge in the essay

- Single-repo comparison. Not a benchmark. One datapoint.
- Prep's LLM-augmented atlas includes generated summaries that Aider's repo map does not. Comparing them as if they were the same artifact is unfair to Aider. The essay should separate "structural ranking" from "narrative atlas."
- Both tools are moving targets. The comparison is pinned to specific commits. Anyone reading the essay six months later should assume the numbers have shifted.

## Publishing target

Technical comparison post, 2000–3500 words. Aider's community will actually read this if it's honest. The title should not be a cheap win; something like "Aider's Repo Map and Prep's Atlas Are Solving Different Problems" is closer to what the essay will actually say.

## What to link to

- Aider's `repomap.py` source (cite the specific lines for PageRank)
- Aider's docs page on repo map (even though it's vaguer than the source)
- Prep's hub bottleneck source and atlas generator source
- `networkx.pagerank` documentation (intellectual honesty about the algorithm)
- Any papers on graph centrality for code (if relevant)

## Next action

Run this *after* essay 01 proves the experimental format works. Needs both tools installed and a shared pinned SHA. Budget a day for the run plus a day for the honest read-through.
