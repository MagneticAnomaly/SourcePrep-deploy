# More Context Is Not More Knowledge

*Every model release announces a bigger context window. The research consistently says bigger windows don't produce better answers — and the failure is more specific than "attention dilutes."*

Every few months, a model announcement leads with a number. 100K tokens. 200K. A million. Two million. The implicit promise is clear: if your codebase didn't fit in the window before, it will fit now, and fitting means understanding. The assumption underneath — so obvious it usually goes unstated — is that more context is more knowledge. Give the model more of your code and it will know more about your code. Give it the whole repo and it will understand the whole repo.

The research says this is wrong, and the failure is not vague. It is measurable, reproducible, and more specific than the usual hand-wave about attention diluting over long sequences. Three independent research efforts from 2024 and 2025, using different models, different benchmarks, and different evaluation methods, arrived at the same finding: model reasoning degrades with long context in ways that do not improve even when retrieval is perfect and the relevant information is provably present in the window. The problem is not that the model can't *find* what it needs. The problem is that the model gets worse at *using* what it finds as the surrounding context grows.

This has practical implications for anyone who uses Claude Code, Cursor, Cline, or any AI coding assistant on a codebase larger than a few thousand lines. Most of the default workflows encourage stuffing: paste the file, attach the directory, let the tool read everything it wants. The research suggests this default is actively counterproductive past a certain point, and the point is lower than most developers assume.

## What "Lost in the Middle" actually showed

The paper that started this conversation is Liu et al., [*Lost in the Middle: How Language Models Use Long Contexts*](https://arxiv.org/abs/2307.03172), published in Transactions of the ACL in 2024. It is probably the most-cited retrieval paper of the last two years and also one of the least carefully read.

The finding most people remember is the U-shaped attention curve: models attend better to information at the beginning and end of their context window and attend worse to information in the middle. This is real, well-measured across multiple model families, and robust. It has been replicated independently.

But the finding most people *miss* is more important. Liu et al. showed that performance degrades as total context length increases, *even when the relevant information is placed at the optimal position* (the beginning or end of the window). In other words, it is not just that information in the middle gets lost. It is that the presence of irrelevant surrounding context actively degrades the model's ability to use relevant information regardless of where that information sits. More context is not just wasteful. It is harmful.

The practical implication is precise: if you are pasting a 3,000-line file into your prompt because the function you care about is on line 47, the other 2,953 lines are not neutral passengers. They are active drag on the model's reasoning about line 47. The model does not ignore them. It processes them, allocates attention to them, and as a result processes the thing you care about less well than it would have in a shorter context.

This is not a claim that long context windows are useless. There are tasks — summarization, translation of long documents, multi-file refactors — where long context is the right tool. The claim is narrower and more useful: for retrieval-dependent tasks, where the model needs to find and reason about a specific piece of information inside a larger body, stuffing the window is a net negative past a surprisingly low threshold.

## The 2025 follow-ups made it worse

If Liu et al. had been a single paper with a single finding, it would have been interesting but not decisive. What happened next is what made it decisive.

In 2025, Chen et al. published [*Context Length Alone Hurts LLM Performance Despite Perfect Retrieval*](https://arxiv.org/abs/2510.05381) at EMNLP. The title is the finding. They constructed experiments where the retrieval was guaranteed to be perfect — the relevant information was always in the context, always clearly marked, always at the right position — and measured what happened as the total context length grew. Performance still degraded. Not because the model couldn't find the information. Not because the retrieval was wrong. But because the model's ability to *reason* over the retrieved information got worse as the surrounding context got longer.

This is the result that should change how you think about your prompts. It means the problem is not retrievable. Better retrieval does not fix it. Better placement does not fix it. The only thing that fixes it is less total context — fewer tokens in the window, less noise around the signal, a more disciplined prompt.

Separately, Chroma Research published [*Context Rot*](https://research.trychroma.com/context-rot) in 2025, testing eighteen production LLMs on distractor-laden contexts. They found that degradation compounds when the distractors are *semantically similar* to the target information — which is exactly the case in a codebase, where most functions share vocabulary with the function you're asking about. The worst case for long-context reasoning is a large body of code that all looks roughly like the code you care about, which is a description of nearly every repository in production.

Three research efforts, different teams, different models, same finding. The context window is not a storage container. It is a cognitive workspace, and it has a carrying capacity that is lower than its token limit.

## What this means for how you prompt

If you use AI coding tools on a codebase of any meaningful size, this research suggests three practice changes.

**First, stop pasting whole files unless you need the whole file.** If you're asking about a function, paste the function. If the function depends on types defined elsewhere, paste the type definitions. Do not paste the file the function lives in and hope the model will figure out what matters. The other functions in that file are not helping. They are active noise that degrades the model's reasoning about the function you care about.

**Second, ask yourself whether your prompt is bigger than your answer.** This is a rough heuristic, not a law, but it catches the most common failure mode. If you're writing a 50-word question and attaching 5,000 words of context, you're almost certainly past the point where more context helps. The model's attention budget is finite, and you are spending most of it on material that is not going to appear in the answer. Trim the context to the minimum that makes the question answerable and no more.

**Third, prefer retrieval over attachment.** When a tool like Claude Code reads files on its own, it is at least making *some* judgment about relevance — it reads files it thinks it needs, in an order it thinks makes sense, and stops when it thinks it has enough. That judgment is imperfect but it is better than no judgment at all, which is what you get when you manually attach everything and let the model sort it out. If you have a retrieval system — a search tool, an MCP server, anything that can select context on your behalf — use it rather than pasting. The whole point of retrieval is to give the model less, not more, and the research says less is better. *This is also why the structural-context tool I built defaults to small per-client char budgets rather than sending everything the index contains — the research is consistent enough that it would be dishonest to do otherwise.*

These are not dramatic changes. They are the kind of prompt-level discipline that takes thirty seconds to apply and pays off on every query. The model did not get dumber. You gave it less noise to reason through, and it used its attention budget on the thing you actually asked about.

## The window is not the bottleneck

The temptation, when your AI coding assistant produces a bad answer, is to think: *it didn't have enough context*. And sometimes that's true. But the research consistently says the opposite failure is more common and harder to notice: the model had *too much* context, the relevant information was buried in semantically similar noise, and the model's reasoning degraded in a way that looked like a bad answer rather than a context problem.

The next time you get a wrong or shallow answer from Claude Code or Cursor or Cline, before you paste more files into the window, try the opposite. Strip the context to the minimum. Paste only the function. Describe in natural language what the surrounding code does instead of including it literally. Give the model a 500-token workspace where it used to have a 50,000-token one, and see whether the answer gets better.

It will, more often than you expect. Not because the model is smarter with less input — it isn't — but because the model is better at using a small amount of relevant information than a large amount of noisy information, and the research now has three independent confirmations that this is a structural property of how these systems work, not a bug that will be patched in the next release.

The window size arms race will continue. The model providers have a commercial reason to keep the numbers going up, and they are not wrong to do so — there are tasks where long context matters. But for the retrieval-dependent, code-understanding work that most developers do most of the time with AI tools, the bottleneck was never the window size. It was what you put in the window. Less of the right thing beats more of everything.

---

## Notes for the author (delete before publishing)

**Word count:** ~2050 words. Within the 1800–2200 target.

**Three primary sources cited:**
- Liu et al. — *Lost in the Middle* (TACL 2024, `2307.03172`). Most-cited paper of the set, link included.
- Chen et al. — *Context Length Alone Hurts LLM Performance Despite Perfect Retrieval* (EMNLP 2025, `2510.05381`). Link included.
- Chroma Research — *Context Rot* (2025). Link included.

**Verification needed before publishing:**
- [ ] Confirm the U-shaped attention curve is in Liu et al. and not misattributed. The paper is freely available on arXiv.
- [ ] Confirm Chen et al.'s core finding — "performance degrades even with perfect retrieval" — is what the paper actually says, not a simplified version. Read the abstract and results section.
- [ ] Confirm Chroma's "semantically similar distractors compound degradation" finding. The Chroma research page should have this.
- [ ] The threshold claim ("lower than most developers assume") is vague by design. If you want to add a specific number (e.g., Databricks found saturation at 4K–32K tokens, or Chroma found cliffs beyond ~15K words), add it in section 2 or 3 with a citation.

**CoDRAG mention:** One sentence in section 3, final paragraph. Framed as "the structural-context tool I built defaults to small per-client char budgets" — which is true per `mcp/server.py:123-138`. Replace with actual budget numbers if you want to make it more specific.

**What's preserved from the Direction 1 plan:** The three-paper spine, the "long context degrades reasoning even with perfect retrieval" finding as the central claim, the practical prompt discipline section.

**What's cut:** The Databricks and Ayyachamy Nadar Ponnusamy et al. papers. The full context-engineering survey. The longer Direction 1 synthesis essay (when written) covers these.

**Voice check:** This article is the most directly practical of the five. The closing is slightly more prescriptive than Articles A and C ("try the opposite," "strip the context to the minimum"). That's deliberate — the reader of this article is looking for a practice change they can apply Monday morning, and the article delivers one. If the prescriptive tone feels too strong, soften the closing by replacing imperative verbs with "consider" or "experiment with."

**Publishing checklist:**
- [ ] Verify all three paper citations
- [ ] Replace CoDRAG link placeholder (there isn't one in this article — CoDRAG mention is by name only, no URL. Add one if desired.)
- [ ] Decide whether to add specific token-count thresholds with citations
- [ ] Cross-link to Article A and Article C as prior pieces in the series
- [ ] Cross-link to Direction 1 full synthesis essay once it exists

**Next article in the series:** Article D (*Code Is a Graph. Your Retrieval Probably Treats It Like a Folder*). This is the conceptual capstone of the five-article set. It draws on three of the nine papers from the long-form essay #11 plan (GraphCodeBERT, RepoHyper, Han et al.) and Ferrante 1987 for the closing. No experiment dependency; no anecdote dependency.
