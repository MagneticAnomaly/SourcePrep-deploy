# 11 — Code Is a Graph, and Retrieval Should Reflect Its Shape

**Status:** ✅ Feasible. All nine sources verified and accessible.
**Type:** Academic synthesis / literature review (Direction 2 from `10_academic_directions.md`).
**Depends on:** Reading nine papers closely enough to represent each fairly. One concrete code-retrieval example (ideally from running an experiment on a test repo) to anchor the opening.
**Does not depend on:** Any half-built CoDRAG feature. The argument stands on published literature.

## Why this is CoDRAG's flagship academic essay

CoDRAG's load-bearing architectural bet is that code retrieval should operate on a graph rather than a flat text corpus. If CoDRAG is wrong about that one thing, most of its design is scaffolding around a wrong premise. Direction 2 is the essay that shows the bet is not improvised — it is the same bet multiple independent research groups have been converging on from 2021 through 2025. The convergence is itself part of the argument.

This essay is the piece that belongs in a CoDRAG whitepaper, in an investor deck, in an academic reading list, or at the top of a "why this tool exists" reference section. It is also the longest and most effortful essay in any of the plans so far. Budget accordingly.

## The argument in one sentence

> Between 2021 and 2025, at least nine independent research efforts arrived at the same finding: retrieval over a graph of symbols outperforms retrieval over flat text for repository-level code understanding, and the reason is that code's meaning is carried by the edges between symbols more than by the text inside any single file.

The essay defends this claim, traces its emergence through the literature, and is honest about where the claim does not hold.

## The nine sources, mapped to sections

| # | Source | Year | Role in the essay |
|---|---|---|---|
| 1 | Guo et al., **GraphCodeBERT** (ICLR 2021) | 2021 | The origin point. A pretraining paper that introduced data-flow signals into code representation learning. Not itself a retrieval paper, but the seed. |
| 2 | **CodeGraph: Code-Centric Knowledge Graphs** (2023, `2308.09687`) | 2023 | First explicit formulation of code as a knowledge graph for LLM consumption. |
| 3 | Wang et al., **GraphCoder: Code Completion via Graph-based Retrieval** (2024, `2406.07003`) | 2024 | Graph-structured retrieval specifically for code completion — the cleanest early demonstration that the approach improves on flat retrieval. |
| 4 | Phan et al., **RepoHyper: Search-Expand-Refine on Semantic Graphs** (2024, `2403.06095`) | 2024 | The three-stage Search → Expand → Refine pipeline, which is almost exactly what `codrag_search` does today. |
| 5 | **STALL+: Boosting LLM-based Repository-level Code Completion with Static Analysis** (2024, `2406.10018`) | 2024 | Static-analysis-at-prompting. Shows that even non-neural graph structure helps. |
| 6 | Edge et al., **GraphRAG: From Local to Global** (2024, `2404.16130`) | 2024 | The general-domain pivot. Not code-specific, but gave the pattern a name and validated it at scale. Bridges the code-retrieval narrative to the broader GraphRAG literature. |
| 7 | Zhang et al., **cAST: Enhancing Code RAG with Structural Awareness** (2025, `2506.15655`) | 2025 | Extends the argument one layer lower: structural awareness matters at chunking time, not just at retrieval time. |
| 8 | **CodeRAG: Supportive Code Retrieval on Bigraph** (2025, `2504.10046`) | 2025 | The maturing design: bigraph structure (two types of nodes + edges between them) as a richer substrate. |
| 9 | Han et al., **RAG vs. GraphRAG: A Systematic Evaluation and Key Insights** (2025, `2502.11371`) | 2025 | The evaluation paper. The essay's empirical backbone. Measures when GraphRAG beats flat RAG and — importantly — when it doesn't. |

Optional supporting cast from the master list if the essay needs more triangulation: *On the Impacts of Contexts on Repository-Level Code Generation* (`2505.09999`), Ferrante et al. 1987 PDG, Khattab & Zaharia ColBERT.

## Essay structure (target: 6000 words, ±500)

### Section 1 — Opening puzzle (~600 words)

Open with one concrete, specific code-retrieval failure: a query where flat-text retrieval returns the wrong files (or returns them in the wrong order) and graph-aware retrieval returns the right ones. Show both outputs. Ask the reader: *why did flat-text retrieval fail on a task a senior engineer would handle in seconds?*

This example needs to be real, not invented. The best candidate is the output of running essay #02 (Hub File Problem) or essay #04 (Aider comparison) on one of the test repos — those experiments will produce exactly the kind of concrete comparison this opening needs. Do not draft section 1 until you have the raw output to draw from. A vague opening sinks the whole essay.

### Section 2 — The 2021 starting point: GraphCodeBERT (~700 words)

Guo et al. showed that pretraining a code model with data-flow information produced better representations for downstream tasks. The paper is about representation learning, not retrieval, but it contains the seed of the graph-retrieval argument: *code has structural information that flat-text models do not capture, and adding that information measurably improves performance.*

Walk through what the paper actually did. Be precise: it added data-flow edges as a pretraining signal, not as a retrieval structure. Note the distinction honestly. End the section by asking what happened when other researchers took this intuition and pushed it into the retrieval layer rather than the pretraining layer.

### Section 3 — The 2023–2024 convergence (~1500 words)

Four papers, one argument. Each subsection 300–400 words.

**CodeGraph (2023).** First explicit formulation of code as a knowledge graph. Introduced the vocabulary ("code-centric knowledge graph") that later papers use. Summarize the construction and the claimed benefits.

**GraphCoder (2024).** Takes graph-structured retrieval and applies it to code completion specifically. Reports improvements over flat-text baselines. Cite the specific numbers — the essay needs measured improvements, not vibes.

**RepoHyper (2024).** Introduces the Search → Expand → Refine pipeline. Explain it carefully; this is the pattern `codrag_search` instantiates almost exactly. Note the parallel plainly, without claiming CoDRAG *implements* RepoHyper.

**STALL+ (2024).** The important counterpoint: graph structure helps *even when* the structure comes from classical static analysis rather than learned representations. This is evidence that the graph itself is doing the work, not a specific flavor of graph encoding.

The synthesis at the end of section 3: four papers from four different research groups, each independently finding that graph structure improves code retrieval. The convergence is the argument.

### Section 4 — The general-domain pivot: Edge et al. (~800 words)

GraphRAG: From Local to Global is not a code paper. It applies the graph-augmented-retrieval idea to general-domain question answering, and — more importantly — it gave the pattern a name that stuck. "GraphRAG" entered the vocabulary after this paper.

Walk through Edge et al.'s community-detection-based summarization strategy. Note that it is *not* a pure graph-retrieval paper — it blends graph structure with multi-level summarization — and that blend is part of why the paper landed. Connect this to the atlas layer in CoDRAG's architecture, which uses a similar multi-level summarization strategy over community-detected modules.

### Section 5 — The 2025 systematic evaluation: Han et al. (~900 words)

This is the section where the essay earns its rigor. Han et al. treat "does GraphRAG beat flat RAG" as a research question and measure it. Walk through what they actually found:

- Where does GraphRAG win decisively?
- Where does GraphRAG lose or tie?
- What properties of the task predict which approach is better?

The essay must report the losses as carefully as the wins. A review that only surfaces confirming evidence is not academic, it is advocacy. If Han et al. found that graph retrieval underperforms on certain task types, say so in the essay and let the reader weigh the trade-off.

### Section 6 — Structural awareness extends to chunking: cAST (~700 words)

Zhang et al.'s cAST paper takes the graph-aware argument one layer deeper: the *chunks* themselves should respect AST boundaries, not just the retrieval topology. Explain why this matters — a chunk that splits a function across two pieces is a chunk that loses the information the retriever would have used — and show the result cAST measured.

Note that this is the same underlying insight at a different granularity. The essay's central thesis compounds as you move down the stack: flat-text handling is the wrong shape for code at the representation layer (GraphCodeBERT), at the retrieval layer (CodeGraph/GraphCoder/RepoHyper/STALL+), and at the chunking layer (cAST).

### Section 7 — The hybrid turn: CodeRAG Bigraph (~500 words)

Short section. CodeRAG introduces a bigraph structure (two node types, edges between them) as a richer substrate than a single-type graph. The point of this section is not to explain every detail but to show that the research is still evolving — the field is moving from "does graph structure help?" to "what kind of graph, with what node types, with what edge semantics?"

This sets up the synthesis by making clear that the argument is not settled forever; it is maturing.

### Section 8 — What this means, and what it does not (~800 words)

The honest section. What has the literature actually established?

**Established.** Graph-aware retrieval measurably improves code understanding tasks in the studies cited. Multiple independent research groups converge on this finding across a four-year span. The improvements are not marginal — they are usually in the 5–20 percentage-point range on standard benchmarks.

**Not established.** That graph retrieval is always better. Han et al.'s losses are real. That any particular graph construction is the right one — the field is still exploring node types, edge semantics, and how to compose graph retrieval with other strategies. That these results transfer cleanly to production systems at scale — most of the evaluations are on curated benchmarks, not live repositories under maintenance pressure.

**Open questions.** How do hybrid systems (graph + flat + reranking) compose? Where is the latency and maintenance cost worth it? Which language families benefit most? The essay leaves these open rather than pretending to answer them.

### Section 9 — Discreet CoDRAG mention (~200 words)

One paragraph. The author has built one such tool because the literature in this essay became compelling enough to act on. It is not the only serious attempt — Aider's repo map is another, and the honest comparison between them lives in [essay #04 in these drafts]. Name, link, move on. No feature list.

### Closing paragraph (~200 words)

One reflective paragraph. The interesting thing about this argument is not that it is new. It is that it is *old* — Ferrante, Ottenstein, and Warren made a version of it in 1987 with their program dependence graph paper. The retrieval story is a rediscovery of an insight classical program analysis already had. That rediscovery is what this essay has been tracing, and the convergence between static analysis and neural retrieval is probably the most important thing happening in the field that nobody is talking about directly.

## Honesty checks — what could go wrong

- **Selection bias in the nine papers.** These nine are papers CoDRAG drew on for its own design. There are papers that argue the opposite — that flat-text retrieval with good chunking is sufficient — and those papers deserve a paragraph. If Han et al.'s evaluation cites a strong baseline that held its own against GraphRAG, that baseline should be named.
- **Author network correlation.** Some of these papers share authors or institutional affiliations. The "independent convergence" framing weakens if four of the nine come from two labs. Map the authors before writing the convergence section and adjust the framing if needed.
- **GraphCodeBERT is a pretraining paper, not a retrieval paper.** Using it as the "starting point" of the graph-retrieval narrative is a slight stretch. Be precise in section 2 about what the paper actually claimed.
- **Reporting other peoples' numbers requires care.** The essay should cite the specific metrics papers reported, the test sets they used, and the baselines they compared against. Vague claims ("GraphRAG performs better") are weaker than specific claims ("GraphRAG improved exact-match on benchmark X by N points against baseline Y"). Do the work to cite specifically.
- **The discreet pitch can still feel like a pitch.** If the reader has been invested in the literature for 5000 words and then CoDRAG shows up in section 9, the transition has to feel earned. One way: frame the CoDRAG mention as "here is one attempt to act on what this essay has argued, and it is neither the only attempt nor obviously the best." Humility sells better than triumphalism.

## Limitations to acknowledge in the essay

- The literature cited is heavily weighted toward Python and Java benchmarks. Evidence on Rust, Go, TypeScript is thinner, and the essay should note this when citing aggregate claims.
- Research results come from controlled benchmarks with frozen data. Production systems face churn, stale indexes, and latency budgets that change the trade-off calculus. The essay should close by noting that *all* the cited evaluations measure what the researchers could measure, not what a production system needs.
- "GraphRAG" vs "flat-text RAG" is a simplification. Every production system is a hybrid. The essay's argument is about the *direction* the evidence points, not about a clean binary.
- Nine papers is still a small slice of a large literature. A reader looking for papers the essay missed will find them; acknowledging this upfront is better than pretending the review is exhaustive.

## Publishing target

- **Venue:** Personal site or Substack with a "Writings" or "Research" section. Not the CoDRAG marketing site (the academic register clashes with product copy). If a whitepaper is planned, this essay is the anchor piece of the whitepaper.
- **Length:** 6000 words ±500. Do not compress it to fit a shorter format — the argument needs room.
- **Format:** Long-form prose with section headings. Footnotes for citations (or inline links; be consistent). Optional: one or two diagrams — a timeline of the nine papers, a simple illustration of flat-text vs graph retrieval. Do not use diagrams as decoration; only if they make the argument clearer.
- **Tonal references:** Adrian Colyer (The Morning Paper) when he ran multi-paper series. Lilian Weng's technical survey posts. Jay Alammar's illustrated transformer essays (for the care he takes to bring the reader along). Gwern Branwen's long-form research essays for the intellectual rigor, minus the idiosyncratic formatting.

## Pre-draft checklist

Before drafting, the following must be in place:

1. **Read the nine papers.** At minimum: abstract, results section, limitations section, and conclusion of each. Take notes on what each paper claims, what it measured, what it concedes. Dispatch research agents to the papers if self-read is not feasible — but the author must *own* the synthesis, not subcontract it.
2. **Map authors across the nine papers.** Identify any institutional or advisor clusters that weaken the "independent convergence" framing.
3. **Run one concrete experiment** to produce the opening example in section 1. Candidate: a single query against one of the test repos, run through Aider's repo map and CoDRAG's atlas, with the outputs saved verbatim.
4. **Identify at least one paper that argues the other side.** Flat-text retrieval advocates exist. Find one strong paper or industry post and cite it in section 8. This single citation will do more for the essay's credibility than any other single move.
5. **Write the section 1 opener first, and stop.** If the opener is vague or forced, the whole essay will be. Iterate the opener to specificity before writing sections 2–9.

## What to link to

- All nine arXiv / venue pages for the primary sources
- CoDRAG source files where the ideas are instantiated (trace graph, `codrag_search`, `codrag_impact`, atlas)
- Aider's `repomap.py` source file (for the cross-reference to the comparison essay #04)
- Ferrante et al. 1987 PDG paper (for the closing paragraph's classical-CS callback)
- The Morning Paper's archive as a tonal reference

## Estimated effort

- **Reading (9 papers, plus one counter-argument paper):** 15–25 hours depending on depth
- **Section 1 opening experiment:** 2–4 hours
- **Drafting:** 15–25 hours
- **Iteration on voice and accuracy:** 8–15 hours
- **Total:** 40–70 hours

This is not a weekend project. It is a two- to four-week undertaking depending on how deep the reading goes. Plan accordingly — and if the time budget is not available, publish Direction 9 first to establish the academic voice with a smaller piece, then come back to this one.

## Next action

Not drafting yet. Two dependencies first:

1. **Run the essay #02 or #04 experiment** to generate the concrete comparison that opens the essay. Without real raw output, the opening is going to be vague or invented, both of which defeat the point.
2. **Confirm the reading plan** — self-read, or dispatch research agents for the nine papers and synthesize the notes before drafting? Either is valid, but the author must own the synthesis step personally. No agent should write the argumentative sections.

Once both are in place, draft section 1 and iterate it to specificity before proceeding to section 2.
