# Phase 99 — Blog Content Plan

Experimental-essay content plan for CoDRAG. Each essay is an experiment you actually run; the essay is the writeup. No predictions, no HN-front-page claims, no made-up taxonomies. Scenarios are scoped against CoDRAG's *real* capabilities as audited on 2026-04-11 (see [`00_feasibility_audit.md`](./00_feasibility_audit.md)).

## What this folder contains

- [`00_feasibility_audit.md`](./00_feasibility_audit.md) — what CoDRAG actually does today, what's half-built, what's killed. Read this first.
- [`01_cycles_as_diagnosis.md`](./01_cycles_as_diagnosis.md) — run cycle detection on real OSS, read the results as archaeology. Lowest-risk first experiment.
- [`02_hub_file_problem.md`](./02_hub_file_problem.md) — compare Claude Code's blast-radius answers to CoDRAG's impact analysis on a real hub file.
- [`03_day_zero_onboarding.md`](./03_day_zero_onboarding.md) — "I just cloned this repo. What should I read first?" across three harnesses + CoDRAG's atlas.
- [`04_aider_repomap_vs_codrag_atlas.md`](./04_aider_repomap_vs_codrag_atlas.md) — honest technical comparison between Aider's personalized PageRank repo map and CoDRAG's atlas.
- [`05_where_codrag_fails.md`](./05_where_codrag_fails.md) — the honest dogfooding essay. Cataloged failures of CoDRAG on a real repo. Credibility piece.
- [`06_knowing_a_codebase.md`](./06_knowing_a_codebase.md) — philosophical essay on knowing-that vs knowing-how (Ryle, Polanyi, Dreyfus) applied to AI coding tools. Product pitch is one sentence in section 5.
- [`10_academic_directions.md`](./10_academic_directions.md) — ten candidate academic-leaning essays grounded in the research master list. Synthesis reviews + Morning-Paper-style deep dives. Source verification complete (2026-04-11).
- [`11_code_is_a_graph.md`](./11_code_is_a_graph.md) — **flagship academic essay.** Nine-paper literature review defending CoDRAG's core architectural bet: code retrieval should operate on a graph, not flat text. 6000-word target, 40–70 hours effort.
- [`12_anthropic_contextual_retrieval.md`](./12_anthropic_contextual_retrieval.md) — Morning-Paper-style deep dive on Anthropic's September 2024 Contextual Retrieval post. 2800-word target, 16–26 hours effort. Recommended as academic-voice warm-up before essay #11.
- [`20_medium_articles.md`](./20_medium_articles.md) — five Medium-sized (1500–2500 word) articles for senior developers using Claude Code, Cursor, Cline, etc. Boil-downs of #06, #02, #12, #11, and Direction 1. On-ramps to the long-form essays. Recommended publication order: A → B → E → C → D.
- [`21_knowing_that_vs_knowing_how.md`](./21_knowing_that_vs_knowing_how.md) — **Article A drafted** (~1950 words). Knowing-that vs knowing-how for AI coding tools. Opening anecdote is a placeholder; needs real moment from your direct experience before publishing.
- [`22_hub_file_problem.md`](./22_hub_file_problem.md) — **Article B: TODO stub.** Blocked on running the essay #02 hub-file experiment on a real test repo. Draft when `02_hub_raw_output.md` lands.
- [`23_contextual_retrieval.md`](./23_contextual_retrieval.md) — **Article C drafted** (~2000 words). Close read of Anthropic's September 2024 Contextual Retrieval post. Self-contained; verify the 35/49/67% figures against the post before publishing.
- [`24_more_context_not_more_knowledge.md`](./24_more_context_not_more_knowledge.md) — **Article E drafted** (~2050 words). Three-paper research spine (Liu, Chen, Chroma) on why long context degrades reasoning. Three practical prompt habits.
- [`25_code_is_a_graph.md`](./25_code_is_a_graph.md) — **Article D drafted** (~2100 words). Capstone piece: four years of convergent research on graph-based code retrieval. Ferrante 1987 callback. Aider and Sourcegraph cited alongside CoDRAG.

## Voice guide

- **Essayistic, not tutorial.** Long paragraphs. Arguments, not bullet lists. Short sentence for rhythm.
- **First-person, rooted, non-bombastic.** "I built this, I ran this, here's what I saw." Not "the industry has the wrong mental model."
- **Concrete before general.** Every claim grounded in a specific file, commit, command output, or observed result.
- **No product pitch until the last 15%.** Earn attention with the experiment. Mention CoDRAG as the tool that enabled the observation.
- **Tonal references.** Geoffrey Litt (metaphor, brevity), Armin Ronacher (experiential authority), Drew Breunig (taxonomy, visuals), Simon Willison ("working notes" energy), Thorsten Ball (code-first). Mix, don't impersonate.

## Anti-patterns (things that killed the first draft)

- Predicting what will rank or go viral. We don't know and shouldn't pretend.
- Inventing taxonomies on the spot and selling them as shared vocabulary.
- Claiming CoDRAG beats alternatives without measurement.
- Picking fights with named writers (Willison, etc.) to borrow audience.
- Scale claims CoDRAG can't back up (e.g. "500-line implementation" when CoDRAG is a three-language monorepo).
- Slogan sentences that don't say anything ("the harness is the craft").

## How to proceed

1. **Pick one essay to run first.** Recommended order: 01 → 02 → 03 → 04 → 05. Rationale: 01 has the lowest operational risk and tells us whether the experimental format works before we commit to bigger scenarios.
2. **Run the scenario from the essay's plan file.** Record raw outputs as-is.
3. **Drop the raw outputs back into this folder** (e.g. `01_cycles_raw_output.md`) before any prose is written. Evidence before writing.
4. **Draft the essay from the raw outputs.** First draft gets iterated on voice, not on facts.
5. **Publish or kill.** If the experiment is boring, the essay is boring. Better to kill it than fake interest.

## What changed from the first proposal (2026-04-11)

The initial brainstorm had eight essays. Feasibility audit cut or changed:

- **Killed:** "The architecture antibody" essay. CoDRAG's concepts/antibodies framework exists as a data structure but the trigger/firing pipeline is not wired into runtime monitoring. Cannot honestly demo end-to-end today. Revisit if/when triggers fire reliably.
- **Killed:** "500 lines of Python" implementation essay. CoDRAG is not a 500-line thing. Format collision with reality.
- **Killed:** "Skills aren't a bigger deal than MCP" rebuttal. No genuine disagreement with Willison's piece; borrow-audience play.
- **Killed:** "Four ways an AI agent fails to understand your codebase" taxonomy. Invented on the spot; no evidence behind the categories.
- **Added:** "Where CoDRAG fails" — the honest failure catalog, which turns the audit's findings into content rather than hiding them.
- **Corrected:** The Aider comparison essay now knows that Aider uses personalized PageRank via `networkx.pagerank` on a tree-sitter symbol graph, while CoDRAG's hub ranking is z-score on in-degree. CoDRAG does not automatically win that comparison.

## Target repos (audit-approved)

Use one of CoDRAG's existing test repos in `tests/eval/real_repos/` for the first experiments. All have been indexed before; scale risk is minimal.

| Repo | Language | Why |
|---|---|---|
| `gin-go` | Go | Medium-size web framework, clean import graph |
| `cobra-go` | Go | CLI library, lots of command tree structure |
| `ripgrep-rust` | Rust | Well-known Rust tool, exercises Rust parser |
| `bat-rust` | Rust | Smaller Rust tool, good for first Rust test |
| `click-python` | Python | Small, canonical Python CLI library |
| `sqlmodel-python` | Python | Type-heavy Python, interesting hubs |

Larger targets (Zulip ~5k files, Django ~3k files) remain aspirational until a scale test succeeds on one of the above.
