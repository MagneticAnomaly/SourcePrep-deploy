# 06 — Knowing a Codebase (A Philosophical Essay)

**Status:** ✅ Feasible. Philosophical frame is settled; technical examples still need to be gathered.
**Depends on:** no CoDRAG features. The essay's ground material is 2–3 observed incidents from real use (yours or others'), plus three real philosophical sources that already exist in print.
**Does not depend on:** concepts, antibodies, scale, or any live harness experiment.

## The premise

There is a distinction in philosophy, usually traced to Gilbert Ryle in *The Concept of Mind* (1949), between **knowing-that** and **knowing-how**. Knowing-that is propositional: facts you can state. Knowing-how is procedural: the capacity to act competently in a situation. Ryle's point was that knowing-how is not reducible to knowing-that — you can memorize every rule of chess and still not know how to play, and you can play beautifully without being able to articulate what you're doing.

Michael Polanyi pushed this further in *The Tacit Dimension* (1966) with the sentence that has outlived most of twentieth-century epistemology: **"we know more than we can tell."** His claim was that a great deal of real human competence is tacit — it lives below the surface of what can be explicitly described. A skilled machinist can feel when a cut is wrong. A doctor can see that a patient is off before any test confirms it. The tacit knowledge is real, acts on the world, and cannot be fully written down.

Hubert Dreyfus, in *What Computers Can't Do* (1972), took these ideas and aimed them at artificial intelligence. His argument was that computers cannot have the kind of situated, embodied, tacit expertise that humans have, and therefore any AI built purely on explicit rules would fail at exactly the tasks where tacit knowledge matters. Dreyfus was wrong about many specifics. Large language models now do things he said machines would never do. But there is one domain where his critique has aged uncomfortably well, and that is the domain of knowing a codebase.

This essay is about what it means to know a codebase, why current AI coding tools usually don't, and what it would take to give them even a rough approximation of the propositional scaffolding that senior developers build up through years of exposure.

## Who the essay is for

Senior developers who have felt the strange dissonance between "this AI tool obviously has more facts about my codebase than any single human could hold in their head" and "this AI tool just suggested something that anyone who has worked here for a month would know is a bad idea." The essay names that dissonance philosophically so that readers have vocabulary for it.

## The philosophical spine (what I'm actually citing)

Three real sources, all in print, all citable.

- **Gilbert Ryle, *The Concept of Mind*, University of Chicago Press, 1949.** The knowing-how / knowing-that distinction. Chapter II ("Knowing How and Knowing That"). Still taught in philosophy of mind.
- **Michael Polanyi, *The Tacit Dimension*, University of Chicago Press, 1966.** The tacit knowledge thesis. "We know more than we can tell" is the opening move.
- **Hubert L. Dreyfus, *What Computers Can't Do: A Critique of Artificial Reason*, Harper & Row, 1972.** (Updated as *What Computers Still Can't Do*, MIT Press, 1992.) The critique-from-Heidegger applied to classical AI. Uneven, often wrong, but the tacit-expertise argument has held up specifically in domains that resist full formalization.

Optional fourth source if it fits the essay's rhythm:

- **Donald Schön, *The Reflective Practitioner*, Basic Books, 1983.** "Knowing-in-action" and "reflection-in-action" for skilled professionals. Maps well onto how a senior developer navigates an unfamiliar part of their own codebase.

I am citing these because they are canonical, not because they are fashionable. Canonical philosophy ages well and lends credibility. Made-up frameworks do not.

## What the essay argues

One claim, developed carefully:

> Current AI coding tools have an unusual amount of *knowing-that* about a codebase and almost no *knowing-how*. They can produce accurate facts — what a function does, what it imports, what it returns — and still fail at tasks that any senior developer would handle competently, because the task required tacit knowledge the codebase never wrote down. A tool that wanted to do better at this couldn't replicate the tacit knowledge directly, because by definition tacit knowledge resists articulation. But it could do the next-best thing: surface the **structural scaffolding** that tacit knowledge usually attaches to — the graph, the hubs, the blast radius, the cycles, the architectural layers — so that an AI tool at least has something to hang its reasoning on besides file contents.

The essay is not "AI can never understand code." The essay is more careful: *the kind of understanding that helps most in a real codebase is largely tacit, and current tools are trying to substitute propositional facts for tacit competence, and the substitution is visible in the failure modes.*

## Structure

Six sections, roughly 4000–5000 words total.

### 1. The strange dissonance (opening, ~600 words)
One concrete anecdote. An AI tool that correctly described a function and then suggested a modification that violated an unwritten convention any team member would have caught. Frame it as a puzzle: the tool *knew more facts* about the code than the human reviewer, and still produced a worse answer. Something is going on.

### 2. Ryle's distinction (~800 words)
Introduce knowing-that vs knowing-how. Use a non-code example first to make the distinction clear (Ryle's own chess example, or cooking, or playing an instrument). Then map it onto code. Knowing-that a function exists and returns an integer is not the same as knowing-how to use it correctly in the codebase's idiom.

### 3. Polanyi and the tacit dimension (~900 words)
The upgrade. Knowing-how itself often rests on knowledge that cannot be stated. A senior developer's sense that "you never edit `billing.py` on a Friday" or "the auth middleware has an ordering dependency nobody documented" is tacit knowledge in Polanyi's exact sense — it guides action, it is real, and it is mostly below the level of articulation. Introduce the idea of tacit codebase knowledge and give two more concrete examples from real engineering experience.

### 4. Dreyfus, the old critique, and the part that survived LLMs (~800 words)
Dreyfus is an awkward citation because most of his predictions were falsified. Handle this directly: "Dreyfus was wrong about many things. Here is the part that wasn't." The part that wasn't: in domains where expertise is largely tacit and situated, classical AI systems substitute explicit rule-following and fail in exactly the ways Dreyfus predicted. LLMs changed the game by learning statistical regularities that look tacit from the outside, but when it comes to a specific codebase — a single working context the LLM was not trained on — the old Dreyfus critique comes back into force. The LLM's training data did not include your team's scar tissue.

### 5. Structural scaffolding as a partial answer (~1000 words)
The constructive move. A tool cannot extract tacit knowledge from a codebase because tacit knowledge is not in the codebase — it is in the developers. But a tool can surface the **structural facts that tacit knowledge is usually about**: which files are load-bearing, which functions have wide blast radius, which modules have cyclic dependencies, which entry points define the architecture. These are still propositional facts (knowing-that), but they are the *right* propositional facts — the ones a senior developer would have internalized through exposure. They don't replace tacit knowledge. They give an AI tool a chance to behave as if it had any.

Here the essay mentions CoDRAG, briefly, as the thing the author built because this argument bothered them enough to act on. No feature list. No pitch. One sentence and a link.

### 6. What this implies and what it doesn't (~600 words)
Closing. What this argument does *not* claim: it does not claim that any tool will ever fully substitute for tacit codebase knowledge, or that structural context will eliminate AI coding mistakes, or that the right tool makes humans unnecessary. What it does claim: the dissonance readers started the essay feeling has a real name in philosophy, and there is at least one honest way to narrow the gap. Leave the reader thinking about their own codebase and what its tacit knowledge looks like.

## The technical examples — what I need before drafting

The essay stands or falls on three or four concrete incidents where the knowing-that / knowing-how gap is visible in real coding work. These cannot be invented. Before drafting, I need material from one of these sources:

1. **Direct experience.** Moments where you (or someone you work with) watched an AI tool produce a factually correct but practically wrong answer about a codebase, and a human caught it because they "just knew" something the tool didn't. Write them down even if they feel obvious — the obvious ones are the best.
2. **Public incidents.** Bug reports, blog posts, or GitHub issues where an AI coding tool suggested something that violated an unwritten rule. Simon Willison has written about several; so has Armin Ronacher. A sourced public example carries more weight in print than a personal anecdote.
3. **Dogfooded examples from CoDRAG itself.** If running essays 01–05 surfaces any cases where Claude Code (or another harness) missed something structural that CoDRAG caught, those are gold. They are the essay's bridge from philosophy to product without the product pitch being the point.

Ideally: one example per category. Drop them into `06_knowing_raw_material.md` before drafting.

## The discreet product pitch

This essay has to sell without selling. The model is Geoffrey Litt writing about personal software, or Maggie Appleton writing about annotation — you feel the author has built something, the something is implied by the argument, and by the end you want to try it. The explicit mention lives in one sentence in section 5:

> *"I built a tool called CoDRAG because this gap bothered me enough to act on it — it doesn't solve the tacit knowledge problem, nothing does, but it does try to surface the structural facts that tacit knowledge usually attaches to."*

And a footnote or closing link. That's the whole pitch. The rest of the essay has to earn enough attention that the one sentence feels like a payoff rather than an interruption.

Anti-patterns for this particular essay:
- No feature lists
- No screenshots of CoDRAG output mid-essay (breaks the register)
- No "CoDRAG solves this" language — the essay's argument explicitly rejects that kind of claim
- No comparison tables
- No MCP explainer

If the reader learns the philosophy and never clicks through, the essay still did its job. The pitch is a byproduct, not the purpose.

## Honesty checks — what could go wrong

- **The philosophical frame might feel pretentious.** Ryle and Polanyi in a dev blog is a register risk. The way out is concreteness: every philosophical move is immediately grounded in a coding example. If the prose drifts into abstract philosophizing for more than two paragraphs at a stretch, bring it back down.
- **Dreyfus is a disputed figure.** Citing him risks attracting "Dreyfus was wrong about AI" comments. Preempt this by explicitly acknowledging what he got wrong in section 4 and isolating the narrow claim that survives.
- **The tacit knowledge argument proves too much.** If taken to its logical end, it suggests no tool can help, which defeats the discreet pitch. The essay has to distinguish clearly between *replacing* tacit knowledge (impossible) and *providing the structural scaffolding tacit knowledge attaches to* (modest but tractable). That distinction is load-bearing; get it wrong and the essay collapses.
- **The product pitch might drown the philosophy, or vice versa.** Keep the CoDRAG mention to one sentence plus a closing link. If the draft needs more pitch, the pitch belongs in a different essay.

## Limitations to acknowledge in the essay

- The tacit knowledge argument is a claim from philosophy, not a claim from empirical cognitive science. Readers from ML or cognitive science may push back. The essay should note it is reasoning within an epistemological tradition, not reporting a result.
- The "structural scaffolding" move is modest on purpose. It does not promise that graph-backed tools will dramatically change AI coding outcomes. It claims only that they replace a categorically wrong substitute (file contents as a proxy for context) with a categorically less wrong one (graph structure as a proxy for context).
- The essay's examples are anecdotal. That is unavoidable when writing about tacit knowledge — the whole point is that it resists formalization, so all evidence is going to be stories. Acknowledge this up front.

## Publishing target

Long-form essay, 4000–5000 words. Personal blog or Substack. Tonal references: Hillel Wayne's philosophical pieces ("Are We Really Engineers?"), Robin Sloan's tech essays, Maggie Appleton's annotation and tools-for-thought writing, Ted Chiang's AI essays for the *New Yorker*. All four write philosophy-adjacent essays for technical audiences without condescension in either direction.

## What to link to

- Ryle, *The Concept of Mind* (any reprint; Chapter II if citing a specific passage)
- Polanyi, *The Tacit Dimension* (University of Chicago Press edition is standard)
- Dreyfus, *What Computers Still Can't Do* (MIT Press, 1992 edition preferred — the revised version handles the Heidegger material better)
- Optionally: Schön, *The Reflective Practitioner*
- Hillel Wayne's "Are We Really Engineers?" as a tonal reference
- Geoffrey Litt's "Code Like a Surgeon" as the closest recent model for this kind of piece
- CoDRAG (once, at the discreet mention)

## Next action

Two things, in this order:

1. **Gather 3–4 real incidents** in `06_knowing_raw_material.md`. Not invented, not generic. Specific moments where the knowing-that / knowing-how gap was visible. Personal, public, and dogfooded if possible.
2. **Only after that, draft section 1 (the opening anecdote)**. The rest of the essay follows from whether the opening has real weight. If the opening is vague, the philosophy will feel tacked on. If the opening is concrete, the philosophy will feel inevitable.

This is the essay where voice matters most. Budget iteration on the draft. A single well-written version of this essay is worth more to CoDRAG than all five technical posts combined — because it is the only piece in the set that plausibly lives on a senior developer's "essays I liked this year" list, and that is the readership that actually evaluates dev tools on taste.
