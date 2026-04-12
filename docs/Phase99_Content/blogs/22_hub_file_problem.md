# Article B — The Hub File Problem

**Status:** 🔶 TODO. Blocked on experiment data.

This article is planned in detail in [`20_medium_articles.md`](./20_medium_articles.md) and the long-form version is planned in [`02_hub_file_problem.md`](./02_hub_file_problem.md). It cannot be drafted honestly until the experiment from essay #02 has been run on a real test repo and the raw outputs captured.

## What needs to happen first

1. Pick a real hub file in a medium test repo. Recommended starting point: `gin-go` from `tests/eval/real_repos/`, hub candidate `context.go`.
2. In a clean Claude Code session *without* CoDRAG attached, ask Claude Code: *"I'm considering renaming `<function>` in `context.go` to `<new_name>`. What do I need to check before making this change?"* Log every file it reads and save the full answer.
3. In a second Claude Code session *with* CoDRAG attached, ask the same question. Log tool calls and save the answer.
4. Run `codrag_impact` directly on the function with `max_hops=3`. Save the output. Run a quick grep as a ground-truth sanity check.
5. Drop everything into `02_hub_raw_output.md` in this folder.

Once the raw outputs exist, the article draft is ~1–2 days of work. The delta between Claude Code's answer and CoDRAG's impact query is the story. If there is no delta, the article changes shape (it becomes "here is the case where the tools converged and here is why") rather than getting killed — but that determination has to come from the real data, not from a guess about it.

## Why this is blocked

The honest reason: inventing a blast-radius comparison would defeat the entire point of the experimental-essay format we committed to in earlier sessions. The article's credibility comes from showing real tool output on a real codebase. Substituting plausible-but-invented examples is the exact failure mode we agreed to avoid.

## Unblocking it

Run the experiment when there is time. The experiment itself is 1–2 hours, not days. I can help structure the scenario (what to capture, what to compare) but cannot run Claude Code sessions against external test repos from here.

When the raw output lands in `02_hub_raw_output.md`, ping me and I will draft Article B from the data.
