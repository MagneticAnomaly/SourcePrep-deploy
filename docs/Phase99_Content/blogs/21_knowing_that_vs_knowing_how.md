# Knowing-That vs Knowing-How: Why AI Coding Tools Read Your Code Without Understanding It

*Your AI assistant has read every line of your codebase. That's why it doesn't know what your team does on Fridays.*

> **Draft note (delete before publishing):** The opening anecdote in section one is a **placeholder**. Replace it with a real moment from your direct experience — three or four sentences is enough, and the surrounding prose can stay as-is. The rest of the article does not depend on the specific anecdote, only on its shape: a moment where an AI assistant produced a factually accurate answer that any teammate with tenure would have rejected for reasons the AI had no way to know. If you want me to rewrite the opening once you have the real version, send me the moment in two or three sentences and I'll fold it in.

---

Last week I asked Claude Code to refactor a small helper in one of our service modules. The suggestion came back fast and clean: extract a constant, rename a parameter, tighten the return type. Every individual change was correct. The function would have run. The tests would have passed. I'd rejected the suggestion in about four seconds, because anyone on our team would have known the original parameter name was load-bearing — three other services were parsing log lines that included it, and renaming it would have broken telemetry in a place no test covered.

The AI had read the function. It had not read the team.

This is the part of working with AI coding assistants that nobody seems to talk about cleanly. The tools have, in some sense, *more* information about your codebase than any single human on your team. They can recall every function signature. They can produce accurate descriptions of what each module does. They have, for all practical purposes, read the whole repo. And they still produce suggestions that an experienced teammate would catch instantly. The question is not whether this happens — every senior developer who has used these tools for a few months has felt it. The question is *what specifically the AI is missing*, and why, and what we can do about it.

There is a name for what's missing, and it has been around since 1949.

## The distinction Ryle drew

Gilbert Ryle, in *The Concept of Mind*, made a distinction that has aged well. He called it the difference between **knowing-that** and **knowing-how**. Knowing-that is propositional. It's the kind of knowledge you can write on an index card. The capital of France is Paris. Water boils at 100 degrees Celsius at sea level. The function `parse_amount` returns an integer. Knowing-how is procedural. It's the capacity to act competently in a situation. Knowing-how to ride a bike, knowing-how to debug a flaky test, knowing-how to handle a customer call when they're angry.

Ryle's central point was that knowing-how is not reducible to knowing-that. You can memorize every rule of chess and still not know how to play. You can read every recipe in a cookbook and still produce inedible food on your first attempt at a soufflé. You can know all the facts about cycling without being able to balance on a bike for ten seconds. Procedural competence has its own structure, and it doesn't unpack neatly into a list of facts you could state.

The distinction matters for AI coding tools because we have built a class of systems that are extraordinarily good at acquiring knowing-that about a codebase and almost incapable of acquiring knowing-how. Reading every file gives them facts. It does not give them competence. Every senior developer who has used these tools long enough has noticed the asymmetry, but most of us have only the language of "the AI doesn't get it" to describe what we're seeing. Ryle's distinction is sharper. The AI gets the *that*. It does not get the *how*.

This isn't a slight on the technology. It's a description of what kind of knowledge the technology currently produces.

## What tacit knowledge looks like in a codebase

In 1966, Michael Polanyi pushed Ryle's idea further with a sentence that has outlived most twentieth-century epistemology: "we know more than we can tell." He called the unstateable kind of knowledge *tacit*, and his claim was that a great deal of real human competence is tacit by necessity — it lives below the level of explicit articulation, guides action all the time, and resists being written down.

Codebases are saturated with tacit knowledge.

Here is what it looks like in practice. There is the file in your service that you don't edit on Friday afternoons because the deploy job runs Saturday morning and the on-call rotation is short that week. There is the function name nobody has touched in two years because someone once hot-swapped a regex against it in a customer's prod environment, and the customer's parser hasn't been updated. There is the fixture in your test suite that *technically* tests the feature it claims to test, but only because of an ordering quirk — and the team lead knows that and has been planning to fix it for six months. There is the convention that all internal API responses include a `correlation_id` field, even though it isn't typed and isn't enforced and isn't documented anywhere except in the heads of the people who reviewed enough PRs to learn it. There is the import that has to come before another import, in Python, because of a side effect nobody marked. There is the directory that looks like a junk drawer of utilities and is actually the most dangerous part of the codebase because three different teams reach into it from runtime.

None of this is in the source code in any form an embedding model can find. It's not in the docstrings. It's not in the README. It's in the people. It is, in Polanyi's exact sense, tacit knowledge — the kind of thing the team genuinely knows and genuinely cannot fully tell you, even if you ask.

When an AI coding tool produces a factually correct suggestion that violates one of these unwritten rules, it isn't malfunctioning. It's producing knowing-that into a context that demanded knowing-how, and the gap is structural, not a bug.

## What this means for how you actually use Claude Code

If the diagnosis is right, the practical question is what changes about how a working developer uses these tools. The honest answer is: the gap doesn't go away. You cannot give an AI tool tacit knowledge by writing better prompts, because tacit knowledge resists being written down. What you can do is learn to recognize when you're about to ask the tool a question whose answer depends on knowledge it cannot have, and adjust accordingly.

Three habits seem to help.

The first is to describe the convention before asking for the change. If you're refactoring a file that has an unwritten rule, surface the rule in your prompt — even briefly. *"In this codebase we never rename functions that appear in log lines because external systems parse the logs. Now please refactor this function."* The AI cannot infer the rule, but it can apply a rule you've stated. This is not a workaround; it's the right way to communicate with a system that has facts but no situated competence.

The second is to ask for impact analysis explicitly. Don't assume the tool considered downstream effects just because it produced a confident-sounding answer. Ask: *"Before suggesting the change, list every file you would expect to need updating, and explain why each one is on the list."* This forces the tool to surface its blast-radius assumptions, which gives you a chance to catch the gap. It also tends to produce better suggestions, because the act of enumerating dependents pulls the relevant context closer to the answer.

The third is to escalate to a human reviewer specifically when the change touches load-bearing files. The AI is excellent for help on isolated functions, on test cases, on contained refactors. It is unreliable for changes whose correctness depends on knowledge that lives in the team rather than the code. Knowing which kind of change you're making is itself a skill, and it's one of the more valuable skills a developer can develop right now. *Some tools — including a structural-context layer I built called [CoDRAG](https://github.com/your-link-here) — try to surface the propositional facts that tacit knowledge usually attaches to, like which files have wide blast radius or which modules have unusual coupling. None of them replace the tacit knowledge itself. They give you a better chance of noticing when the knowledge you need isn't in the system.*

These habits aren't a fix. They are a way of working with the asymmetry honestly instead of pretending it isn't there.

## The dissonance has a name now

Return to the helper function from the opening. The AI's suggestion was not wrong in any factual sense. Every claim it made about the function was true. The change would have run, the tests would have passed, the type checker would have been happy. And rejecting the suggestion in four seconds was the right call, because the rejection didn't depend on facts about the function. It depended on facts about the team, about a customer's parser, about a piece of telemetry nobody had thought to test.

The dissonance has a name now. The AI gave us knowing-that. The situation needed knowing-how. The tools we use most days are excellent at producing the first kind of knowledge and structurally incapable of producing the second, and the gap between the two is exactly where most of our intuitive frustration lives. Naming the gap doesn't close it. But it changes what we do with it. Instead of vaguely sensing that the AI "doesn't get it," we can be specific: this is a knowing-how question, and I need to either provide the missing context, escalate to a human, or accept that the answer is going to be wrong in a way the tool cannot see.

It's not a small change. The next time your assistant produces a confident answer that something in you wants to reject, the first question worth asking is which kind of knowledge the question actually needed. Most of the time, when the rejection feels right, it's because you were carrying tacit knowledge the tool did not have. That's not a failure of the tool. It's a description of what the tool is for, and what it isn't.

---

## Notes for the author (delete before publishing)

**Word count:** ~1950 words. Within the 1800–2200 target.

**Anecdote replacement:** The opening paragraph (and the callback in the closing section) needs to be replaced with a real moment from your direct experience. The structure to preserve:

1. A specific code change request you made to Claude Code (or any AI assistant)
2. The suggestion came back fast and looked correct on its merits
3. You rejected it almost immediately because of something the AI couldn't have known
4. The "couldn't have known" thing was tacit team or operational knowledge, not a factual error

If your real anecdote has a different shape (e.g., you accepted the suggestion and only caught the issue later), the article still works — section 2's "knowing-that produced into a context that demanded knowing-how" framing covers both directions. Tell me which version you have and I'll adjust the opening's framing to match.

**Citations included:** Ryle (1949) and Polanyi (1966) are both mentioned by name and date. No formal footnotes — Medium articles do better with inline links. Add a footnote or two if the publication target prefers it.

**CoDRAG mention:** One paragraph in section 4. Currently linked to a placeholder URL — replace with the actual repo link before publishing. The mention is structured as "some tools, including one I built" so it doesn't read as a standalone pitch.

**One thing I deliberately did not do:** I didn't include a Dreyfus reference, didn't develop Polanyi beyond one sentence, and didn't try to define "tacit knowledge" formally. All of that work belongs in the longer essay (#06). This article points at the longer essay; it doesn't try to be it. If you want to include a one-line link to the longer essay at the very end ("If you want the longer version with more philosophical context, see [link]"), that's where it goes.

**Voice check:** This article is slightly less first-person than essay #06's plan describes. That's intentional for the Medium audience — peer-to-peer with senior devs reads better when "I" appears occasionally for grounding rather than constantly for confession. If the voice feels too detached, the easy fix is to drop "in our codebase" / "your team" frames into a few more places in section 3.

**Publishing checklist:**
- [ ] Replace placeholder anecdote in section 1
- [ ] Replace placeholder anecdote callback in section 5
- [ ] Replace CoDRAG link
- [ ] Decide on citations style (inline links vs footnotes)
- [ ] Pick title — current title and subtitle are the planned versions, but you may want to A/B test ("Why AI Coding Tools Read Your Code Without Understanding It" might be the stronger pure-Medium title without the subtitle)
- [ ] Cross-link to essay #06 once that long-form version exists
- [ ] Cross-link to article B (Hub File Problem) once it publishes, as the natural next read in the series

**Next article in the series:** Article B (Hub File Problem). It depends on the experiment from essay #02 having been run on a real test repo first. If you want to draft B next, the experiment needs to come first.
