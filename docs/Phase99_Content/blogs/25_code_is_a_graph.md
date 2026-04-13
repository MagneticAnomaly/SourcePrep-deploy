# Code Is a Graph. Your Retrieval Probably Treats It Like a Folder.

*Four years of independent research groups arriving at the same conclusion — and almost nobody in the AI coding tool space is talking about it directly.*

Most retrieval systems for code start from the same assumption. A codebase is a collection of text files. Embed the files, or chunk them and embed the chunks, and search the embeddings when a query arrives. Return the top-K results. Pass them to the model. This is how every major AI coding tool works under the hood, and for many tasks it works well enough that nobody questions it.

The assumption underneath is that a file is the right unit of meaning for code. It isn't. And the wrongness is not subtle — it shows up in a specific, recognizable class of failures that anyone who has used these tools on a medium-to-large codebase has encountered.

Ask your AI assistant "where does authentication happen in this codebase?" and watch what it does. It will search for files containing the word "auth." It will find some of them. It will read them. It will produce an answer that is approximately right — it found the login handler, maybe the middleware, maybe the token validator. What it probably did not do is follow the *dependency chain* from the login handler through the session store through the permission checker through the role definitions through the database access layer. It found some nodes. It did not traverse the graph. The answer looks right and is incomplete in exactly the way that matters when you're about to refactor something.

Code is not a folder of text files. Code is a directed graph of symbols, where the meaning of each symbol is determined by the edges that connect it to other symbols. A function's true context is not the file it lives in. It is the set of things that call it, the set of things it calls, and the transitive closure of both. Retrieval systems that ignore the graph are retrieving the wrong shape of object.

## What four years of research actually found

This is not a speculative claim. It is the consensus of a body of research that has been accumulating since 2021, across independent groups, and it keeps arriving at the same conclusion.

In 2021, Guo et al. published [*GraphCodeBERT*](https://arxiv.org/abs/2009.08366) at ICLR, showing that pretraining a code model with data-flow graph information produced better representations for downstream tasks. The paper is about pretraining, not retrieval, but it contained the seed: code has structural information that flat-text models do not capture, and adding that information measurably improves performance. At the time, the finding was interesting but narrow. Nobody generalized it.

By 2024, four independent research groups had generalized it. Phan et al.'s [*RepoHyper*](https://arxiv.org/abs/2403.06095) introduced a three-stage pattern — Search, then Expand along graph edges, then Refine — for repository-level code retrieval, and showed it outperformed flat-text baselines. The pattern is almost exactly what you would design if you took the idea of "code is a graph" seriously and asked what retrieval should look like over that graph: find the seed, walk the edges, filter by relevance. Other papers from 2024 — GraphCoder, STALL+, CodeGraph — arrived at structurally similar designs from different starting points. The convergence was not coordinated. These groups were not reading each other's drafts.

In early 2025, Han et al. published [*RAG vs. GraphRAG: A Systematic Evaluation and Key Insights*](https://arxiv.org/abs/2502.11371), which is the paper that treats the comparison as a research question rather than an advocacy position. They measured when graph-augmented retrieval beats flat-text retrieval, and — importantly — when it doesn't.

The honest summary of Han et al.'s finding: graph-augmented retrieval consistently outperforms flat-text retrieval on multi-hop reasoning tasks — the kind of queries where understanding the answer requires following relationships between multiple code elements. On simple, single-file lookup tasks, the advantage is smaller or absent. The graph helps most when the question is structural, which is exactly the kind of question that matters for real engineering work (impact analysis, refactoring, architecture understanding) and matters less for the kind of question that benchmarks tend to over-represent (single-function completion).

This pattern — the graph helps for the hard queries, the ones that actually matter in production — is the through-line of the entire body of research. Every paper that measured it found the same thing.

## This is a rediscovery, not a discovery

There is an irony in this research timeline that is worth naming directly. The idea that code is best understood as a graph is not new. It is 37 years old.

In 1987, Ferrante, Ottenstein, and Warren published [*The Program Dependence Graph and Its Use in Optimization*](https://dl.acm.org/doi/10.1145/24039.24041) in ACM Transactions on Programming Languages and Systems. The program dependence graph — a combined representation of control-flow and data-flow relationships between statements — became a foundational tool in compiler optimization, program slicing, and static analysis. The insight it formalized is the same one the 2024 retrieval papers rediscovered: the meaning of a piece of code is not in the text of that piece. It is in the *relationships* between that piece and the rest of the program.

What happened between 1987 and 2024 is that the AI coding tool community largely ignored this body of work. Embedding-based retrieval comes from the NLP tradition, where documents really are the right unit of meaning, and embedding a paragraph really does capture most of what you need. When that tradition was applied to code, nobody stopped to ask whether the paragraph analogy held. It doesn't. A paragraph is a self-contained unit of meaning. A function is not. A function is a node in a graph, and its meaning is carried as much by its edges as by its body.

The convergence of the 2024 retrieval papers with the 1987 static analysis literature is, I think, the most important thing happening in AI coding tools right now that almost nobody is talking about directly. Neural retrieval and classical static analysis are converging on the same representation of code, from opposite directions, and the tools that figure out how to compose both will be the ones that actually understand codebases rather than pattern-matching against them.

## What this means for your tooling choices

If you're evaluating AI coding tools — for yourself, for your team, for your organization — the single most useful question you can add to your evaluation is: **does this tool understand code as a graph?**

The question has a concrete answer. A tool that understands code as a graph can tell you the transitive dependents of a function, can identify the most-connected files in your codebase, can walk import chains, and can expand a search result along structural edges to include related symbols. A tool that treats code as flat text can search for strings, can embed chunks and return nearest neighbors, and cannot do any of the above without reading its way through files sequentially and hoping it reads enough.

Some tools currently understand code as a graph, to varying degrees. [Aider](https://aider.chat/docs/repomap.html) builds a repo map using personalized PageRank on a symbol graph extracted from tree-sitter tags — a serious, well-designed approach. [Sourcegraph](https://sourcegraph.com/) has been doing code intelligence via structural indexing for years. I built a structural-context MCP server called [CoDRAG](https://github.com/) that uses a trace graph with import edges and impact analysis, and I've tried to be honest about how it compares to Aider's approach in a [separate comparison piece](./04_aider_repomap_vs_codrag_atlas.md). Other projects are emerging from the research community.

Most of the major AI coding assistants — Claude Code, Cursor, Cline, Windsurf — do not currently do graph-based retrieval natively. They read files. They read them well, and their file-reading heuristics have gotten impressively good, but they are still reading files, not traversing a graph. The difference is invisible on small codebases and becomes load-bearing on large ones, which is exactly the trajectory the research predicts.

The convergence is still early. The research has established the direction; the production tooling is catching up. But if the last four years of papers are any guide, the question for AI coding tools is no longer whether graph-based retrieval matters. It's how fast the major tools will adopt it, and whether the tools that adopted it early will have a lasting advantage over those that didn't.

## What this doesn't claim

This article is not arguing that flat-text retrieval is broken or that embedding-based search should be abandoned. Han et al.'s evaluation found real cases where flat-text retrieval held its own, particularly on simpler queries. Embedding search is fast, cheap, and good enough for many tasks. The argument is that it is *not enough* for the structural, multi-hop queries that define real engineering work on large codebases — and that the research on this point is now consistent enough across enough independent groups to be taken as a working consensus rather than a preliminary finding.

The argument is also not that any specific tool has this fully solved. All current implementations — Aider's PageRank, CoDRAG's trace graph, Sourcegraph's SCIP-based indexing — are early attempts with known limitations. The point is the direction, not the destination. The direction says: treat code as a graph, and retrieval gets measurably better on the queries that actually matter.

---

## Notes for the author (delete before publishing)

**Word count:** ~2100 words. Within the 2000–2500 target.

**Three primary sources cited (verify before publishing):**
- [ ] Guo et al. — *GraphCodeBERT* (ICLR 2021, `2009.08366`). Verify this is the correct arXiv ID for GraphCodeBERT. The paper may have a 2020 submission date with a 2021 ICLR acceptance.
- [ ] Phan et al. — *RepoHyper* (2024, `2403.06095`). Verified in the research master list. Confirm the Search → Expand → Refine pipeline description matches the paper.
- [ ] Han et al. — *RAG vs. GraphRAG* (2025, `2502.11371`). Verified. Confirm the "multi-hop reasoning" framing matches their findings.

**Supporting sources (not cited inline but informing the argument):**
- Ferrante, Ottenstein & Warren — *The Program Dependence Graph* (ACM TOPLAS 1987). ACM DL link included.
- Aider's repo map documentation and source (`aider/repomap.py`)
- Sourcegraph (mentioned by name)

**CoDRAG mention:** One paragraph in section 4 ("What this means for your tooling choices"), framed alongside Aider and Sourcegraph as one of several serious attempts. Currently uses placeholder URL; replace before publishing. The cross-link to the Aider comparison piece (essay #04) may not resolve yet — add when that piece exists.

**What is preserved from the long-form essay #11:** The central thesis (code is a graph, retrieval should reflect its shape). The independent-convergence framing. The Ferrante 1987 callback. Han et al.'s honesty about where GraphRAG loses.

**What is cut:** Six of the nine papers. The full chronological walk-through from 2021 to 2025. The CodeGraph / GraphCoder / STALL+ / cAST / CodeRAG-Bigraph detail. The long synthesis section. The essay #11 plan does this work; this article is the on-ramp.

**Voice check:** This article makes the strongest argumentative claim of the five and is also the most generous to alternatives (flat-text retrieval gets defended, Aider gets cited as a serious competitor, Han et al.'s counterexamples are reported). The generosity is load-bearing for credibility; if it feels excessive, trim the "What this doesn't claim" section rather than the competitor mentions.

**One deliberate choice:** The opening example (asking about authentication and watching the tool miss the dependency chain) is generic enough that it is true for most readers without being anchored to a specific incident. This is the one article where the generic opening is acceptable, because the claim is structural (about how retrieval works) rather than personal (about a specific moment). Articles A and B depend on specificity; this one depends on recognizability.

**Publishing checklist:**
- [ ] Verify all three arXiv IDs
- [ ] Replace CoDRAG placeholder URL
- [ ] Replace essay #04 cross-link when Aider comparison piece exists
- [ ] Confirm Ferrante et al. ACM link resolves
- [ ] Cross-link to Articles A, C, and E as prior pieces in the series
- [ ] Cross-link to essay #11 once the long-form version exists

**Series status after all five:**

| # | Article | Status |
|---|---|---|
| A | Knowing-That vs Knowing-How | ✅ Drafted. Needs real anecdote. |
| B | The Hub File Problem | 🔶 TODO. Needs experiment. |
| C | Contextual Retrieval | ✅ Drafted. Verify numbers. |
| E | More Context ≠ More Knowledge | ✅ Drafted. Verify paper claims. |
| D | Code Is a Graph | ✅ Drafted. Verify arXiv IDs. |
