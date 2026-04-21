# 20 — Medium-Sized Articles for Professional AI Tool Users

**Status:** Planning stage. Source material already exists in essays 01–12; this file boils each down to a Medium-sized article suitable for senior developers who use Claude Code, Cursor, Cline, Windsurf, or Aider in production.
**Audience:** Working engineers who already pay for AI coding tools, hit context limits weekly, and read dev blogs to sharpen their workflow. Not researchers. Not beginners. Not the audience for the academic literature reviews in #11–#12.

## Format spec

- **Length:** 1500–2500 words. Medium's reader-attention curve drops fast after ten minutes.
- **Voice:** Direct. Slightly less first-person than the personal essays. No academic register. The reader is a peer.
- **Structure:** Strong opening, thesis in the first 200 words, three or four sections, concrete takeaway in the last 200 words. One bold callout per article maximum.
- **Citations:** Inline links, not footnotes. Cite where it matters; do not over-cite.
- **Prep mention:** One paragraph near the end, sometimes one line plus a footnote. Same discipline as essays #06 and #11–#12.
- **Tonal references:** Vicki Boykis on ML in production, Hamel Husain on evals, Eugene Yan on building search systems, Birgitta Böckeler on AI-assisted development at Thoughtworks. Engineering writers who treat working programmers as the audience and don't condescend in either direction.

## Why this set exists alongside the longer plans

The long-form plans (01–12) are the deep work. They are also a lot of essays to write. Medium-sized pieces serve three different needs the longer essays don't:

1. **Faster publication cadence.** Each is 1–2 weeks of work, not 4–6.
2. **Wider distribution surface.** Medium, dev.to, Substack short posts, Hashnode, personal blogs all live in this size class. Long essays mostly live in one place.
3. **Lower commitment per piece.** A reader who picks up a 2000-word post is making a smaller bet than one who opens a 6000-word literature review. The shorter pieces convert more readers into "I should look at the longer one."

The relationship: medium articles are the **on-ramps** to the deep work. Someone reads "The Hub File Problem" in eight minutes, finds it useful, and now they're the kind of reader who clicks through to the 6000-word literature review when it lands.

## The five articles

Each article below is derived from an existing long-form plan but reorganized for the Medium format and audience. None of them duplicate the long-form piece — they cover the same idea at different depth, with different framing, for different readers.

---

### Article A — Knowing-That vs Knowing-How: Why AI Coding Tools Read Your Code Without Understanding It

**Source:** Essay #06 (`06_knowing_a_codebase.md`).
**Word target:** 1800–2200.
**Type:** Conceptual / philosophical, with concrete examples.

**Hook (first 150 words).** A specific dissonance the reader has felt: an AI assistant that produced a factually correct answer about a function, then suggested a modification that any team member with a month of tenure would have rejected. Frame it as a puzzle worth a name.

**Thesis (one sentence).** Current AI coding tools have an unusual amount of *knowing-that* about your codebase and almost no *knowing-how*, and the gap explains a specific class of mistakes you have probably learned to silently work around.

**Structure.**

1. *The dissonance* (~300 words). The opening anecdote, told in detail. End with the philosophical question.
2. *Ryle, briefly* (~400 words). Knowing-how vs knowing-that. Use Ryle's chess example or a non-code analogy first; then map to code. One footnote to *The Concept of Mind* (1949).
3. *What tacit knowledge looks like in a codebase* (~500 words). Concrete examples: the file you "never edit on a Friday," the convention nobody documented, the function name you would never reuse because of a bug from two years ago. Cite Polanyi's "we know more than we can tell" (1966) in one sentence — no need to develop him fully here, that work happens in the long essay.
4. *Why this matters for how you use Claude Code* (~400 words). The practical move. The reader cannot give an AI tool tacit knowledge, but they can learn to recognize when they are about to ask the tool a question that requires it. Prompt-level discipline: describe the convention before asking for the change. Pair the AI with a senior reviewer for changes in load-bearing files. Ask for impact analysis explicitly rather than assuming the tool did one.
5. *Closing* (~200 words). Return to the opening anecdote. The dissonance has a name now. Knowing the name does not solve the problem, but it changes how you work around it.

**Discreet Prep mention.** One sentence plus a footnote in section 4: *"Some tools — including a structural-context layer I built called Prep — try to provide the propositional facts that tacit knowledge usually attaches to, but no tool replaces the knowledge itself."*

**Why it works for Claude Code professionals.** It gives them vocabulary for a frustration they already have. Vocabulary travels — readers cite the article when explaining the failure mode to colleagues. Highest "shared on Twitter with 'this'" potential of the five.

**What is preserved from the long version.** The Ryle / Polanyi frame, the central thesis, the dissonance opening.
**What is cut.** Dreyfus entirely. Schön entirely. The full philosophical lineage. The four-section structural-scaffolding argument. The longer essay does this work; the Medium article points at it.

---

### Article B — The Hub File Problem

**Source:** Essay #02 (`02_hub_file_problem.md`).
**Word target:** 1500–2000.
**Type:** Practical / technical with one concrete experiment.

**Hook (first 150 words).** Every codebase has a handful of files where a wrong edit cascades silently. Senior developers learn which ones by scar tissue. AI coding assistants have no equivalent intuition, and the result is that "blast radius estimate" from your AI tool is a guess wearing a confident voice.

**Thesis.** The hub file problem is not "some files matter more than others." It is that without a graph, any blast-radius estimate from an AI tool is a guess, and the guess gets worse as the codebase gets larger.

**Structure.**

1. *The scar tissue most senior devs share* (~300 words). The opening anecdote. The "don't touch that on a Friday" instinct. Frame it as practical, not philosophical.
2. *What an AI tool actually sees* (~400 words). When you ask Claude Code "what should I check before changing function X?", it reads files. It reads them sequentially. It stops when it thinks it has enough. None of those steps is wrong. All of them are blind to which files are *load-bearing*.
3. *The experiment* (~600 words). The condensed version of essay #02's experiment: pick one hub file in a real repo, ask Claude Code to estimate the blast radius of a rename, then run a graph-based impact query for ground truth. Show the delta. (This section *requires* the experiment to have been run — do not draft this article on imagined results.)
4. *What you can do today* (~300 words). The practical takeaway. Specific prompt patterns that force the tool to broaden its file-read pass before answering. When to escalate to a graph-aware tool. When to escalate to a human reviewer.
5. *Closing* (~200 words). The hub file problem won't disappear by writing better prompts, but knowing it exists changes which suggestions you accept on autopilot.

**Discreet Prep mention.** One paragraph in section 3 — "I ran the impact query through Prep, the structural-context tool I built" — with a footnote.

**Why it works for Claude Code professionals.** Practical, immediately applicable, ends with prompt patterns the reader can use today. Highest "I'll use this tomorrow" rating of the five.

**What is preserved.** The experiment, the comparison delta, the honest framing about what the AI tool *can* and *can't* see.
**What is cut.** The full multi-tool comparison. The detailed scenario steps. The six-section structure. This is the focused version of one slice of essay #02.

---

### Article C — Why One Sentence of Context Cuts Retrieval Failures by Half

**Source:** Essay #12 (`12_anthropic_contextual_retrieval.md`).
**Word target:** 1800–2200.
**Type:** Single-result deep dive.

**Hook (first 150 words).** A short engineering post from Anthropic in September 2024 reported that prepending a one-sentence context prefix to each chunk before embedding reduced retrieval failures by 49%. For a field that celebrates single-digit improvements, that number is unusual enough to deserve a careful look.

**Thesis.** Anthropic's Contextual Retrieval is not a new model. It is a one-line indexing change that exploits a brittleness in how short text chunks get embedded, and it is one of the few research results from the last eighteen months that meaningfully changes how production retrieval systems should be designed.

**Structure.**

1. *The 49% number, and the immediate suspicion* (~300 words). Put the number on the table. Note the suspicion any experienced engineer should feel about a number that big and immediately frame the article as a careful walkthrough rather than a hype piece.
2. *The technique, in three sentences* (~400 words). Chunk normally. Generate a 50–100 token prefix per chunk that situates it inside the document. Embed prefix-plus-chunk together. Note the cost: one LLM call per chunk at index time, indexing cost grows, retrieval cost is unchanged.
3. *Why it works (probably)* (~400 words). Three plausible mechanisms — disambiguation, document identity, embedding brittleness repair. Be explicit that these are hypotheses, not Anthropic's stated findings.
4. *What the 49% does and does not mean* (~400 words). The number is the full stack (Contextual Retrieval + BM25 + reranking). Contextual Retrieval alone is smaller. The evaluation is retrieval failure rate, not end-to-end task quality. Indexing cost is real and worth budgeting.
5. *Closing — the technique that quietly changed things* (~300 words). Return to the headline. The 49% is not the important part. The technique's *composability* — it stacks cleanly with BM25 and reranking — is what makes it durable.

**Discreet Prep mention.** One sentence in section 2: *"I integrated this technique into a tool I work on; the indexing-time cost was real but the retrieval improvement was visible enough on dogfooded queries that I would not turn it off."*

**Why it works for Claude Code professionals.** Many of them are building their own RAG systems on the side or evaluating MCP servers. Contextual Retrieval is one of the few cheap, practical primitives they can adopt this week. Highest "useful at work tomorrow" rating for engineers who build retrieval infra.

**What is preserved.** The technique walkthrough, the three-mechanism hypothesis section, the honest scope qualifications.
**What is cut.** The detailed worked example. The composition section's full reciprocal-rank-fusion explanation. The Prep-Phase-93 integration paragraph. The longer essay covers all three.

---

### Article D — Code Is a Graph. Your Retrieval Probably Treats It Like a Folder.

**Source:** Essay #11 (`11_code_is_a_graph.md`), heavily condensed.
**Word target:** 2000–2500.
**Type:** Argumentative / framing piece, with three citations doing the work that nine do in the long version.

**Hook (first 150 words).** Most retrieval systems for code start from the same assumption: a codebase is a folder of text files, embed them, search the embeddings, return the top-K. The assumption is wrong, and the wrongness is visible in the kinds of mistakes the resulting tools make. Code is not a folder. It is a graph.

**Thesis.** The meaning of code lives in the edges between symbols, not the text inside any single file. Retrieval systems that ignore the graph are retrieving the wrong shape of object, and four years of research from independent groups now consistently shows it.

**Structure.**

1. *The folder assumption* (~400 words). The hidden premise behind every flat-text retrieval system. Show what it means in practice: a query for "where does authentication happen here?" returns the file with the most lexical matches for "auth," not the file the actual auth flow runs through.
2. *What the research actually shows* (~700 words). Three papers, in chronological order, doing the heavy lifting that nine do in the long version: GraphCodeBERT (2021) for the seed insight, RepoHyper (2024) for the Search → Expand → Refine pattern, Han et al. (2025) for the systematic evaluation that measured the trade-offs honestly. Cite each carefully. Note where Han et al. found GraphRAG *losing* — that single move buys most of the article's credibility.
3. *Why this is a conceptual rediscovery* (~400 words). The connection to Ferrante, Ottenstein, and Warren's 1987 program dependence graph paper. Static program analysis already knew code was a graph. The retrieval story is a rediscovery, not a discovery, and that is part of what makes it convincing.
4. *What this means for your tooling choices* (~400 words). Practical: which AI coding tools currently understand code as a graph (Aider's repo map, Prep, code-graph-rag, Sourcegraph), which don't, and how to tell the difference at evaluation time. The reader should be able to ask better questions of any new MCP server they evaluate.
5. *Closing* (~200 words). One sentence on the shape of the rediscovery: "The most useful thing happening in AI coding tools right now is that classical static analysis and neural retrieval are converging, and almost nobody is talking about it directly."

**Discreet Prep mention.** One paragraph in section 4 — "I built Prep because the literature in this article became compelling enough to act on, and I tried to be honest about how it compares to Aider in [link to essay #04]."

**Why it works for Claude Code professionals.** Tool evaluators read this article and walk away with a vocabulary for distinguishing serious tools from shallow ones. The "ask whether it understands code as a graph" heuristic is portable to any future tool they evaluate.

**What is preserved.** The central thesis. The independent convergence framing. The Ferrante callback. The Han et al. honesty move (reporting losses).
**What is cut.** Six of the nine papers. The four-paper convergence section. The general-domain GraphRAG pivot. The long synthesis section. Essay #11 does all this work; this article is the doorway.

---

### Article E — More Context Is Not More Knowledge

**Source:** Direction 1 from `10_academic_directions.md` (no long-form plan exists yet).
**Word target:** 1800–2200.
**Type:** Counterintuitive empirical piece.

**Hook (first 150 words).** Every model release announcement now includes a context window number. 100K. 200K. 1M. 2M. The implied promise is that bigger windows mean smarter use of more code. The research consistently says they don't, and the failure mode is more specific than the usual "attention dilutes" hand-wave.

**Thesis.** Model reasoning degrades with long context *even when the retrieval is perfect*, and the right discipline is not to fit more in the window but to retrieve less of the right thing.

**Structure.**

1. *The window size arms race* (~300 words). The practical observation. Every reader has felt this: long-context Claude or Gemini sessions get worse, not just slower, as the context fills.
2. *What "Lost in the Middle" actually showed* (~500 words). Walk through Liu et al. (TACL 2024). The U-shaped attention curve. The specific finding that information in the middle of the context degrades more than information at the edges. Note the precise scope: the paper did not say "long context is broken," it said "model attention is uneven across position."
3. *The 2025 follow-ups* (~500 words). Chen et al. (EMNLP 2025) found degradation persists even when retrieval is *perfect* — that is, even when the relevant information is in the context, the model gets worse at using it as the surrounding context grows. Chroma's 2025 *Context Rot* report extended this to eighteen production LLMs. The effect is not a quirk of one model. It is structural.
4. *What this means for your prompts* (~400 words). The practical move. Stop pasting the whole file. Stop attaching whole directories. Do not assume that a bigger window justifies a lazier prompt. Pre-filter ruthlessly. The two heuristics: *"the right hundred lines beats the wrong ten thousand,"* and *"if your prompt is bigger than your answer, you are probably wasting the model's attention."*
5. *Closing* (~200 words). The provider companies have a commercial reason to keep growing context windows, and they are not wrong to do so — long context has real applications. But the application that matters most for code work is selective retrieval, not context inflation.

**Discreet Prep mention.** One sentence in section 4: *"This is also why the structural-context tool I built defaults to small char budgets per query — the research is consistent enough that it would feel dishonest to do otherwise."*

**Why it works for Claude Code professionals.** Most senior devs already feel this but do not have research backing for it. Giving them three citations they can drop into a Slack thread when their team argues for "just paste more files" is the high-utility move.

**What is preserved.** The three-paper spine (Liu, Chen, Chroma), the practical "stop pasting everything" advice, the U-shaped attention finding.
**What is cut.** The full Direction 1 source list. The Databricks long-context numbers. The context engineering survey. The longer Direction 1 essay (when it gets written) does this work.

---

## How the five fit together

These five are designed to work as a sequence and as standalones.

| Order | Article | Role |
|---|---|---|
| 1 | A — Knowing-That vs Knowing-How | Mental model. Gives the reader vocabulary for a frustration they already feel. |
| 2 | B — The Hub File Problem | Concrete failure mode. Practical, technical, immediately actionable. |
| 3 | E — More Context Is Not More Knowledge | The "what to do differently" piece. Research-backed prompt discipline. |
| 4 | C — Why One Sentence of Context Cuts Retrieval Failures by Half | The specific high-leverage technique. For readers building their own retrieval. |
| 5 | D — Code Is a Graph | The framing piece. The intellectual move that makes the rest cohere. |

Published in this order, each piece sets up the next. Article A gives the language for the gap. Article B shows the gap in one specific case. Article E gives a research-backed practice change. Article C gives a research-backed technique. Article D gives the underlying conceptual frame that the whole sequence has been pointing at.

A reader who finishes all five has moved from "I have a vague feeling my AI assistant is missing something" to "I have a working mental model, three practice changes, and one technique I can adopt this week." That is the conversion funnel for the longer essays — anyone who finishes the five and wants more goes to #06, #02, #11, #12, and the eventual full Direction 1 piece.

## Recommended publication cadence

- **One article per week for five weeks.** Tight enough to feel like a series, loose enough to iterate on voice.
- **Cross-link each article to its long-form sibling.** When essay #11 publishes later, article D becomes the on-ramp; the Medium piece's footer links to the long version. Same for the others.
- **Publish article A first.** It is the most distinctive frame and the one most likely to be shared. The shares earn attention for articles 2–5.
- **Article B requires the experiment from essay #02 to have been run.** Sequence the work accordingly: run the hub-file experiment, then write article B as the writeup. The article is shorter than the long-form essay #02, so the same raw output supplies both.

## Honesty checks across the set

These are tighter pieces, so the honesty checks from the long-form plans get distilled too.

- **No invented anecdotes.** If article A's opening dissonance is not from direct experience, write a different opening. Inventing anecdotes for credibility damages credibility.
- **No 49% without the qualifications.** Article C's headline number must travel with its scope qualifier in section 4. Otherwise the article reads as marketing.
- **No "X is bad" framings.** Article D could easily slide into "flat-text retrieval is bad." It is not. Articles must always concede where the alternative wins.
- **One Prep mention per article, maximum.** The discipline holds at this length too. A mention in section 2 *and* section 5 reads like a pitch even if neither sentence is.
- **No pretending Medium articles are research.** They are not. They cite research; they do not produce it. The voice should be confident but not authoritative in the way essays #11–#12 are.

## What I need before drafting any of them

For each article, the same three things:

1. **The opening hook material.** Real, specific, not invented. Article A needs the dissonance anecdote. Article B needs the experiment output from essay #02. Article C needs a careful re-read of Anthropic's post. Article D needs the three primary papers. Article E needs the three primary papers.
2. **The Prep sentence.** One sentence per article, drafted in advance, so the discreet mention does not get over-written into a pitch when the rest of the article is in flow.
3. **A target publication.** Personal Substack? Medium? Hashnode? The target affects formatting (Medium loves big quote blocks; Substack doesn't), and the formatting affects how the article is structured.

## Next action

Pick one of the five to draft first. My recommendation: **Article A (Knowing-That vs Knowing-How)**, because:

- It does not depend on running an experiment first (unlike B, which needs essay #02's output).
- It does not depend on careful paper re-reading (unlike C, D, E).
- It is the most distinctive voice piece in the set and the one most likely to be shared.
- It establishes the mental model the other four articles rely on.

If you would rather start with the practical / technical piece, **Article B** is the best second choice — but it must wait for the experiment in essay #02 to have been run on a real test repo.

When you pick, I will draft the article in the same folder, numbered `21_<slug>.md`, with the actual prose rather than a plan. Or if you prefer, I can draft a plan-then-prose split: a tight one-page plan first, then the full article after you approve it.
