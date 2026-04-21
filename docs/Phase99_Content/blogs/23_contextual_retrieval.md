# Why One Sentence of Context Cuts Retrieval Failures by Half

*Anthropic published a small indexing trick in September 2024. It's one of the few research results from that year that quietly changed how production retrieval should be built.*

Every month or two, a research result comes through that makes a modest claim backed by specific numbers. Most of them are fine. A few of them matter. Anthropic's [Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) post from September 2024 was one of the ones that mattered, and it did something unusual for research in this space: it made a concrete engineering claim with a concrete engineering number. Prepend a one- or two-sentence contextual prefix to each chunk before you embed it, they said, and your retrieval failure rate drops by 35% on its own — or by 49% if you also stack it with BM25, or by 67% if you add reranking on top.

Anyone who has been in the retrieval trenches for a year or two should feel a small suspicion when they see numbers that big. Most improvements in retrieval work in the single digits. Reducing failures by a third or a half or two thirds is the kind of lift that usually comes from changing models, not from changing indexing. And so the right thing to do when a post like this lands is not to post an enthusiastic tweet and move on. It is to sit with the result for an hour, figure out what the technique actually does, what the numbers actually measure, and whether it's the kind of thing you should be building into your own systems.

I've spent that hour, more than once, and I've now integrated the technique into a retrieval pipeline I maintain. Here is what the post actually says, what I think is going on under the hood, what the numbers do and do not mean, and why the technique turned out to be durable for reasons that are different from the reasons the headline suggests.

## The technique

Contextual Retrieval has three moving parts, and it is mechanically very simple.

First, you chunk your documents normally. Whatever strategy you already use — fixed-window, recursive, semantic, AST-aware — keeps working. Anthropic is not replacing your chunker. They are changing what happens to the chunks before they get embedded.

Second, for each chunk, you generate a short contextualizing prefix — Anthropic's prompt asks for 50 to 100 tokens — that situates the chunk inside its parent document. The prompt they recommend is roughly: *"Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk."* You send this prompt to Claude along with the full document and the target chunk. Claude produces a sentence or two that describes what the chunk is about, relative to the document. Anthropic uses prompt caching on the document so the per-chunk cost stays low — around one dollar per million tokens of source material, which is cheap enough that it doesn't meaningfully change the economics of even a large corpus.

Third, you prepend the generated prefix to the chunk and embed the combined text. The embedding is computed over prefix-plus-chunk as a single unit. There is no second embedding. The prefix is not stored separately. At retrieval time, the system does not know the prefix is there — it just sees a chunk whose embedding is different from, and apparently better than, what the bare chunk would have produced.

That is the whole technique.

It is worth pausing on how small the move is. This is not a new embedding model. It is not a new retrieval algorithm. It is not a different chunking strategy. It is, at the level of code, a function that takes a chunk and returns a slightly longer chunk, plus one extra LLM call per chunk at index time. I integrated it into a structural-context tool I maintain called [Prep](https://github.com/), and the code change was a few hours; the interesting part was deciding what counts as the "document" that the prefix should describe (turns out, for code, it's usually the file plus a one-line summary of its role in the module).

The cost is not zero. One LLM call per chunk at indexing time adds up quickly on large corpora — a 50,000-chunk corpus is 50,000 calls, which takes real wall-clock time even with parallelism. But retrieval-time latency is unchanged, because all the extra work happens at index time and never again.

## Why it works — three hypotheses

Anthropic's post does not deeply explain why this works. They run the experiments, they report the numbers, they show you where the improvements are concentrated. They do not spend a lot of time on the mechanism. When a result is this surprising and the mechanism is this underspecified, it's worth being explicit about the fact that we are *hypothesizing*, not reporting, when we talk about why.

Three hypotheses seem plausible, and all three probably contribute.

The first is **disambiguation**. A chunk with the word "parse" in it could be about a billing module, a log formatter, or a configuration loader. Those three things share a verb and almost nothing else. A contextualizing prefix that says "This chunk is from the billing reconciliation service, specifically the function that parses batch settlement files" pulls the chunk's embedding toward the billing neighborhood and away from the other two. A query about billing retrieves the right parse function now; a query about logs doesn't get confused.

The second is **document identity as a retrieval signal**. Chunks live inside documents, and documents have their own coherence. When you encode a chunk with a prefix that references its parent document, you're implicitly encoding "this chunk belongs to document X" into the vector. Queries biased toward a specific document's terminology end up nearer to chunks from that document, and the retrieval distribution gets smarter about provenance almost as a side effect.

The third is the one I find most interesting and see discussed least: **brittleness repair**. Embedding models are trained on text that is on average longer than the chunks we usually feed them. When you embed a 200-token chunk of code in isolation, you're at the short tail of the model's training distribution, and the resulting vector is noisier than an embedding of longer text would be. Prepending 50 to 100 tokens of natural language pushes the input toward the center of the distribution the model learned on, which probably stabilizes the embedding geometry in ways that are hard to articulate but show up as measured retrieval improvements. The prefix isn't just disambiguating. It's also making the embedding less noisy in the first place.

These are hypotheses, and they are compatible with each other. Anthropic's post gives us strong evidence that *something* is going on; it doesn't tell us which mechanism is dominant. For a working engineer evaluating whether to adopt the technique, the mechanism question is interesting but not blocking. The number is the number, and the number is large enough to matter regardless of which story is true.

## What the 49% does and doesn't mean

The headline numbers have two important qualifications most readers miss on the first pass.

First, they describe different stacks, and mixing them up is the most common mistake I see when people cite this post. Contextual Embeddings *alone* reduces failures by 35%. Contextual Embeddings plus Contextual BM25 reduces failures by 49%. Adding reranking on top brings the total reduction to 67%. These are not separate measurements of the same thing; they are cumulative layers. If you are comparing Contextual Retrieval to "embeddings only" as your baseline, the relevant number is 35%. If you are comparing it to "embeddings plus BM25 without contextual prefixes," the relevant number is the delta between those two — which is smaller than either headline. The 49% is real, and it is genuinely impressive, but it is the contribution of the whole stack, not of the embedding change in isolation.

Second, the evaluation measures retrieval failure rate, not end-to-end task quality. A better-retrieved chunk is not the same thing as a better answer. Retrieval improvements sometimes propagate to downstream generation and sometimes don't, and Anthropic's post is measuring the easier-to-measure thing. In production, the chunk you retrieve has to actually help the generator, and there are plenty of cases where a marginal retrieval improvement produces no observable end-to-end difference because the generator was already making it work from partial information. Retrieval is necessary but not sufficient.

A third qualification isn't a flaw but is worth noticing: the technique assumes the concept of "document" is meaningful for your corpus. A contextualizing prefix that says "this chunk is from the billing reconciliation service" requires there to be a billing reconciliation service — that is, a coherent parent document whose identity the prefix can reference. For corpora that are grab-bags of heterogeneous snippets (a pile of gist-sized notes, a directory of unrelated scripts, a search index over every Slack message in your workspace), the prefix has less to anchor against, and the improvement is probably smaller. Code repositories work well for this technique specifically because they are more document-like than they usually get credit for: files have purposes, modules have cohesion, and the prefix has something coherent to describe.

None of these qualifications make the result less interesting. They make it a result you can adopt with your eyes open instead of adopting the headline.

## The composability is the durable part

Here is the thing about Contextual Retrieval that turned out to matter more than the number.

When a new retrieval technique arrives, the question I find myself asking is not "how big is the improvement?" but "does it compose with the other things I'm already doing?" A clever new embedding model that replaces everything else is hard to adopt; you have to rip something out. A clever new retrieval algorithm that wants to own the whole pipeline is a commitment. But a technique that happens at indexing time, modifies a string, and leaves every other part of the stack alone — that is a technique you can adopt in an afternoon without coordinating with anyone else on your team, and leave in place for years because nothing else has to move around it.

That is what Contextual Retrieval is. It stacks cleanly with BM25 hybrid retrieval, which is itself a well-established composition pattern — [Cormack, Clarke, and Buettcher's 2009 paper on reciprocal rank fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) is the standard reference for how to combine two rankers without tuning weights. It stacks cleanly with reranking. It stacks cleanly with whatever chunking strategy you already have, including the AST-aware structural chunking that code benefits from. It doesn't fight with different embedding models. It is the kind of primitive you add to your system and forget about, which is the highest form of compliment you can pay a piece of retrieval infrastructure.

The 49% is not the important part of this result. The composability is. A year from now, when the next clever retrieval idea arrives, the thing we'll look back on from Contextual Retrieval isn't the headline number. It's that this was one of a handful of techniques from 2024 that quietly became part of everyone's production stack without anyone having to rebuild their systems to make room for it, and it did that because the cost of adoption was an afternoon and the cost of regret was nearly zero.

The practical lesson isn't "adopt this technique" — though you probably should, if you run a retrieval pipeline over code or any document-like corpus. The practical lesson is this: when you evaluate new retrieval research, the first question to ask isn't how big the improvement is. It's whether you can take the technique on board without rebuilding your stack to accommodate it. The techniques you actually end up using, the ones that survive the first three months of production, are the ones that don't demand anything of the system around them. Contextual Retrieval passes that test, which is why it's still in my pipeline eighteen months later, and why I would pay the one-dollar-per-million-tokens indexing cost even if the headline number turned out, on closer inspection, to be smaller than it looked.

---

## Notes for the author (delete before publishing)

**Word count:** ~2000 words. Within the 1800–2200 target.

**Numbers to verify before publishing:** The 35% / 49% / 67% decomposition is from Anthropic's September 2024 post. I'm confident these are the right numbers but the article's credibility depends on them being exact. Re-read the post and confirm before publishing. If any of the three figures is off, the fix is mechanical — update the three places they appear (opening, section 4, closing). Specifically verify:
- Contextual Embeddings alone reduces retrieval failures by 35%
- Contextual Embeddings + Contextual BM25 reduces by 49%
- Adding reranking brings the total to 67%
- Cost is ~$1.02 per million tokens of source material with prompt caching

**Prep mention:** One paragraph in section 2, framed as "a structural-context tool I maintain called Prep." Currently uses a placeholder URL; replace with the actual repo link before publishing. The framing is deliberately modest — it says "I integrated it" not "Prep uses this technique as a competitive advantage."

**Citations included:**
- Anthropic's Contextual Retrieval post (primary source, linked in opening)
- Cormack, Clarke & Buettcher 2009 RRF paper (secondary, linked in closing)

No other citations. This is deliberate; the article is a single-result deep dive and additional citations would dilute the focus. If the publication venue requires more formal citation (e.g., academic Substack), add a one-line "Further reading" footer linking to Liu et al. *Lost in the Middle* and Jina AI's Late Chunking post.

**Voice check:** Slightly more first-person than Article A because this article is explicitly a working-engineer's report on adopting a specific technique. The "I've spent that hour" and "I would pay the indexing cost" moves are load-bearing for credibility — they signal that the author has actually done the work rather than reporting on a post they read.

**What's preserved from the long-form plan (essay #12):** The three-hypothesis section on why it works. The scope-qualification section on what the numbers mean. The composability framing at the end. The worked-example structure is condensed to a single paragraph about billing reconciliation rather than a full section.

**What's cut:** The worked example with real chunk output. The full composition walkthrough of BM25 + reranking. Detailed discussion of Jina's Late Chunking as an alternative approach. These all belong in the longer essay #12 when it gets drafted.

**Publishing checklist:**
- [ ] Verify the 35% / 49% / 67% figures against Anthropic's post
- [ ] Replace placeholder Prep link
- [ ] Confirm Cormack et al. 2009 link still resolves
- [ ] Decide on citation style for target venue (Medium, Substack, personal site)
- [ ] Optional: add a "Further reading" footer with Liu et al. and Late Chunking
- [ ] Cross-link to Article A (Knowing-That vs Knowing-How) as prior piece in the series
- [ ] Cross-link to essay #12 once the long version exists

**Next article in the series:** Article B was skipped and marked TODO (requires experiment from essay #02 to be run first). Next up per the planned order (A → B → E → C → D) with B deferred is Article E (*More Context Is Not More Knowledge*).
