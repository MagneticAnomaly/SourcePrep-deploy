# Prompt Engineering Grounding

A curated research reference for iterators auditing SourcePrep's ~30 LLM prompt sites. Each section maps published research to the prompt **patterns** (P1-P10) we use; the per-site mapping is downstream work for `prompts/<site>.md`.

## Pattern legend (from project brief)

| ID | Pattern | Example sites |
|---|---|---|
| P1 | Plain-text generation with structural constraints | atlas (identity, stack, workspace map, cross-cutting) |
| P2 | Strict JSON output with schema validation | most batched + concept prompts |
| P3 | Named-tier rubrics for evaluation | T1/T2/T3 concept tiers |
| P4 | Few-shot examples (graded) | T3 concept refinement |
| P5 | Adversarial / hostile-reviewer framings | concept-validate |
| P6 | Senior-architect / expert personas | many openers |
| P7 | Multi-pass pipelines (gen → validate → refine → synth) | concept swarm |
| P8 | Batched prompts (multi-item per call) | 8 batched sites |
| P9 | Aggressive instruction tone | AGENTS.md "IMMEDIATELY call" |
| P10 | Inferred / structured graph extraction | cross-file edges, decision chains |

Each entry below names which patterns it speaks to.

---

## 1. Anthropic's official prompt engineering docs

Anthropic restructured the per-technique pages into a single living reference: **"Prompting best practices"** for Claude Opus 4.7, Sonnet 4.6, Haiku 4.5 ([platform.claude.com](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)). The legacy per-technique pages still exist as canonical references: [overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview), [multishot prompting](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting), [chain of thought](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-of-thought), [XML tags](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags), [prefill](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prefill-claudes-response), [prompt chaining](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-prompts), [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [extended thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking).

Headline guidance (current as of 2026-05):
- **Claude 4.7 calibrates response length to task complexity** — if you depend on a fixed style/verbosity, prompt for it explicitly. Affects P1 (atlas plain-text constraints) and P2 (JSON-only sites that should not get prose preludes).
- **XML tags** are the recommended primary structuring device — Claude was trained to parse them. Use `<instructions>`, `<context>`, `<examples>`, `<input>`, `<thinking>`, `<answer>`. Tag names are not canonical; consistency matters more than the specific name. Speaks to P1/P2/P3/P4 — all our heavily-structured prompts.
- **Multi-shot recommendation: 3-5 examples** wrapped in `<example>` tags inside an `<examples>` wrapper, covering edge cases and variations. Maps directly to **P4** (our three graded T1/T2-boundary/T3 examples are inside the recommended range).
- **Prefill** the assistant turn with `{` to skip prose preambles and constrain to JSON. Maps to **P2**. Anthropic now recommends **Structured Outputs** over prefill for guaranteed schema conformance.
- **Chain of thought** has three levels — basic ("think step by step"), guided (named steps), structured (XML `<thinking>` + `<answer>`). Structured is preferred because you can extract the answer programmatically while retaining the reasoning for debugging. Maps to **P3/P5/P7**.
- **Prompt caching** can cut cost up to 90% and latency up to 85% for long prompts. 1-hour cache is recommended for extended-thinking sessions. Relevant to all batched/multi-pass sites (**P7/P8**).

**Evidence quality:** Industry guide from the model vendor. Authoritative for what Claude expects but does not include independent benchmarks of its own claims. Treat as "the right defaults, then measure."

---

## 2. Few-shot / in-context learning

**Brown et al. 2020 — GPT-3 paper** ([arXiv:2005.14165](https://arxiv.org/abs/2005.14165)). Introduced "few-shot" as a setting (10-100 demonstrations fit in context) distinct from one-shot and zero-shot. Established that demonstrations alone — no gradient updates — can elicit large quality gains. Peer-reviewed NeurIPS 2020.

**Min et al. 2022 — "Rethinking the Role of Demonstrations"** ([arXiv:2202.12837](https://arxiv.org/abs/2202.12837)). Counter-intuitive but well-replicated: replacing demonstration *labels* with random labels barely hurts performance. What demonstrations actually teach the model is (a) the label space, (b) the input distribution, (c) the output format. Direct implication for **P4**: our graded T1/T2/T3 examples are doing more to set *format* and *score-range expectations* than to teach the model what makes a T1 vs T3. EMNLP 2022, peer-reviewed.

**Lu et al. 2022 — "Fantastically Ordered Prompts"** (cited in [Order Matters survey, 2025](https://arxiv.org/html/2511.09700v1)). Few-shot performance varies dramatically with example *order*; some orderings are catastrophically worse. Implication for **P4** + **P8**: if we keep our graded examples in fixed order, we may be locked into a suboptimal ordering — worth A/B-testing.

**Many-shot scaling (2024)** — [Agarwal et al., "Many-Shot In-Context Learning"](https://arxiv.org/html/2404.11018v2) — with long-context models (Gemini 1.5 Pro, Claude 3+), 50-1000 examples can outperform fine-tuning on some tasks. Less directly relevant to us (we're not example-starved), but suggests our 3-example T3 prompt could benefit from more graded examples if we have them.

**Caveats:** Min et al.'s "labels don't matter" finding is for classification; less established for generative/structured tasks like ours. Order-sensitivity literature also focused on classification benchmarks.

---

## 3. Chain of Thought (CoT)

**Wei et al. 2022** ([arXiv:2201.11903](https://arxiv.org/abs/2201.11903)). The foundational CoT paper. Adding worked-reasoning exemplars in few-shot prompts boosts arithmetic, commonsense, symbolic reasoning. Emergent ability: only helps at ~100B+ parameters in the original work, though follow-up showed smaller models benefit with task-specific CoT. NeurIPS 2022.

**Kojima et al. 2022 — "Large Language Models are Zero-Shot Reasoners"** ([arXiv:2205.11916](https://arxiv.org/abs/2205.11916)). Just adding "Let's think step by step" — no exemplars — also works (MultiArith 17.7% → 78.7%). NeurIPS 2022.

**Wang et al. 2022 — Self-consistency** ([arXiv:2203.11171](https://arxiv.org/abs/2203.11171)). Sample N CoT traces with temperature > 0, take the majority-vote answer. +17.9% on GSM8K. ICLR 2023.

**Liu et al. 2024 — "Mind Your Step (by Step)"** ([arXiv:2410.21333](https://arxiv.org/abs/2410.21333)). **CoT can hurt** on tasks where deliberation hurts humans (implicit pattern recognition, intuitive judgments). State-of-the-art models showed up to 36.3% absolute accuracy drop with CoT on three of six tested tasks. Also Wharton GAIL technical report ([Decreasing Value of CoT](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)) finds CoT's marginal value is dropping as reasoning models improve.

**Mapped to our patterns:** P3 (named tiers — we *do* ask for rationale-before-score, which is implicit CoT), P5 (hostile-reviewer rationale), P7 (multi-pass). 

**Caveat for us:** Our concept-validate's "quote evidence, search for counter-evidence, attempt falsification" is structured CoT. Worth checking whether models are following the steps or just performing them rhetorically before producing the verdict they wanted anyway — the "Yes Man" / over-abduction failure mode in [the falsification critique](https://mikecaulfield.substack.com/p/is-the-llm-response-wrong-or-have).

---

## 4. Self-Refine / Self-Consistency / Self-Critique

**Madaan et al. 2023 — Self-Refine** ([arXiv:2303.17651](https://arxiv.org/abs/2303.17651)). One LLM generates, critiques, refines, iteratively. ~20% improvement (auto + human metrics) across 7 tasks (dialog, math, code). No training, no RL. NeurIPS 2023.

**Shinn et al. 2023 — Reflexion** ([arXiv:2303.11366](https://arxiv.org/abs/2303.11366)). Agent stores verbal self-reflections in an episodic memory and reuses them across trials. "Verbal RL" — strong gains on coding, language reasoning. NeurIPS 2023.

**Constitutional AI** ([arXiv:2212.08073](https://arxiv.org/abs/2212.08073), Anthropic). Self-critique guided by explicit principles — closest published analogue to our hostile-reviewer pattern, where the critique criteria are made explicit in the prompt.

**Mapped to our patterns:** P5 (adversarial), P7 (multi-pass). Our concept pipeline is structurally close to Self-Refine but with role separation — Generate ≠ Validate ≠ Refine are different prompts, not a loop in the same prompt. That separation is consistent with the Self-Refine ablations (separate critic outperforms unified self-critic in some settings).

**Caveats:** Recent work shows self-critique often fails to find errors the model didn't already know about (similar to self-preference bias in LLM-as-judge — see §8). Worth empirically validating that our `concept-validate` step is actually rejecting bad candidates, not rubber-stamping them.

---

## 5. Structured output / JSON

**OpenAI Structured Outputs (August 2024)** ([introducing post](https://openai.com/index/introducing-structured-outputs-in-the-api/), [API docs](https://platform.openai.com/docs/guides/structured-outputs)). 100% schema conformance via constrained decoding — gpt-4o-2024-08-06 scores 100% on complex schemas vs ~40% for gpt-4-0613 with plain JSON mode. Industry guide; performance numbers are vendor-reported.

**Anthropic Tool Use / Structured Outputs** ([prefill docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prefill-claudes-response), [Spring AI integration writeup](https://spring.io/blog/2025/10/27/spring-ai-anthropic-prompt-caching-blog/)). Tool use has been the recommended path since April 2024; Anthropic added explicit Structured Outputs more recently. Independent comparison ([medium.com/@rosgluk](https://medium.com/@rosgluk/structured-output-comparison-across-popular-llm-providers-openai-gemini-anthropic-mistral-and-1a5d42fa612a)) cites ~<0.2% parse failure for Anthropic tool use vs <0.1% for OpenAI Structured Outputs (vendor-aggregate numbers; treat as order-of-magnitude).

**Outlines / XGrammar / Guidance** — open-source constrained decoders that compile JSON Schema to FSMs. [Outlines repo](https://github.com/dottxt-ai/outlines), [LMSYS compressed FSM post](https://www.lmsys.org/blog/2024-02-05-compressed-fsm/). Cost: <50 microseconds per token of grammar checking vs 10-50ms inference. Relevant if/when we run local models — these would make schema violations impossible at decode time.

**Geng et al. 2025 — "Generating Structured Outputs from Language Models: Benchmark and Studies"** ([arXiv:2501.10868](https://arxiv.org/html/2501.10868v1)). Independent benchmark — confirms constrained decoding ~100% structure conformance but documents **content-quality regression** when the schema is overly restrictive ("schema overhead" — model spends compute satisfying schema instead of solving task).

**Mapped to our patterns:** P2 (strict JSON), P8 (batched JSON — schema overhead compounds). Direct implication: if a SourcePrep prompt is returning malformed JSON, prefer prefill `{` + explicit "valid JSON only" first; only switch to tool-use-mode if the failure persists. Watch for content-quality regression when adding schema fields.

---

## 6. Persona prompting

The literature is **genuinely mixed** and the strongest evidence is on the skeptical side.

**Zheng et al. 2024 — "When 'A Helpful Assistant' Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models"** ([arXiv:2311.10054](https://arxiv.org/html/2311.10054v3)). 2,410 factual questions × 4 LLM families. Adding personas did *not* improve performance on objective tasks; in some cases it hurt. No persona-selection strategy beat random.

**Counter-evidence** comes from role-play research where the persona is task-aligned ([learnprompting.org/docs/advanced/zero_shot/role_prompting](https://learnprompting.org/docs/advanced/zero_shot/role_prompting), [aclanthology.org/2024.findings-emnlp.969](https://aclanthology.org/2024.findings-emnlp.969.pdf)) — modest gains when the persona is thematically tight to the task (e.g., math teacher for math problems).

**PromptHub independent test** ([blog](https://www.prompthub.us/blog/role-prompting-does-adding-personas-to-your-prompts-really-make-a-difference)) — small experimental study finding minimal effect across diverse tasks.

**Mapped to our patterns:** P6 ("You are a senior software architect..."). Honest read: this is one of the highest-suspicion patterns to audit. The opener costs tokens, almost certainly does no harm, but the published evidence does not support that it meaningfully improves output quality on objective tasks like ours (concept extraction, atlas generation). Worth running A/B tests where the persona line is the *only* difference — it's the kind of change that's easy to leave in because "it can't hurt" without verifying.

---

## 7. Confidence calibration

The user's memory record on this is well-supported by the published literature.

**Lin et al. 2022 — "Teaching Models to Express Their Uncertainty in Words"** ([arXiv:2205.14334](https://arxiv.org/abs/2205.14334)). GPT-3 can learn to output well-calibrated *verbal* confidence ("90% confidence", "high confidence") that maps to actual probabilities. First demonstration that LLMs can verbalize calibrated uncertainty.

**Tian et al. 2023 — "Just Ask for Calibration"** ([arXiv:2305.14975](https://arxiv.org/abs/2305.14975), [EMNLP 2023](https://aclanthology.org/2023.emnlp-main.330/)). For RLHF-tuned models (ChatGPT, GPT-4, Claude), **verbalized confidences are better-calibrated than the model's own conditional probabilities** — up to 50% relative reduction in expected calibration error. Critical methodological finding: asking for confidence is *better* than reading log-probs from RLHF models.

**Yang et al. 2024 — "On Verbalized Confidence Scores for LLMs"** ([arXiv:2412.14737](https://arxiv.org/html/2412.14737v2)) and **Calibration survey 2024** ([arXiv:2412.12767](https://arxiv.org/html/2412.12767v1)). Confirm that verbalized confidence works but is **highly prompt-sensitive** — the exact wording of the confidence elicitation moves the distribution. Asking for a 0-1 float gives more clumping than asking for a named tier.

**Social desirability / clumping evidence:** Direct support for "social register clumping" is sparser in academic literature than the user's memory implies. [Social desirability survey work](https://arxiv.org/abs/2405.06058) shows LLMs skew toward socially-desirable responses on personality surveys, which is the same mechanism — RLHF tunes models toward responses humans approve of, and "uncertain but not too uncertain" (~0.7-0.85 floats) is the socially-modulated default. The 2024 verbalized-confidence work shows that **named tiers + rationale-first** mitigates this; the float-on-0-to-1 prompt format is documented as worst-case.

**Mapped to our patterns:** P3 (named tiers), P7 (validate step assigns scores). The user's memory rule — "never ask LLM for 0-1 float; use named-tier rubric with passing tests; rationale before score; map tier→float at storage" — is consistent with the literature. The "rationale before score" ordering is independently supported by CoT research (§3) — having the model reason before committing to a number gives it room to update mid-generation.

---

## 8. Evaluation methodology

**Liang et al. 2022 — HELM** ([arXiv:2211.09110](https://arxiv.org/abs/2211.09110), [Stanford CRFM site](https://crfm.stanford.edu/2022/11/17/helm.html)). Multi-metric (accuracy, calibration, robustness, fairness, bias, toxicity, efficiency) × multi-scenario (42 scenarios) × multi-model (30 models) framework. Authoritative reference for "what 'evaluating an LLM' even means." Less directly applicable to per-prompt iteration but is the textbook on dimensional thinking.

**Liu et al. 2023 — G-Eval** ([arXiv:2303.16634](https://arxiv.org/abs/2303.16634), EMNLP 2023). LLM-as-judge with form-filling and CoT. GPT-4 G-Eval reaches 0.514 Spearman with human judgments on summarization — best published at time of release. **Caveat (in the paper itself):** documented bias toward LLM-generated text.

**Self-Preference Bias in LLM-as-Judge** ([arXiv:2410.21819](https://arxiv.org/abs/2410.21819)). GPT-4 exhibits significant self-preference. Mechanism: lower perplexity for familiar outputs. Implication for us: do not let the same model that produces an artifact judge it; rotate judges or use a human spot-check on a sample.

**LLM-as-Judge survey** ([arXiv:2411.15594](https://arxiv.org/html/2411.15594v6)). Catalogues five major biases: **position** (first/last item bias), **verbosity** (favors longer responses), **self-preference**, **familiarity**, **anchoring**. Position bias mitigation: rearrange comparisons; verbosity bias mitigation: length-normalize.

**Mapped to our patterns:** Cross-cutting — we have no formal eval right now (the Phase 140 snapshot+diff protocol is our eval). When we promote to LLM-as-judge for cross-snapshot comparison, all five biases will apply. **Don't have model A grade model A's output.** Don't rank "A vs B" with both presented in fixed order without controlling for position.

---

## 9. Adversarial / critique prompting

Less mature literature than CoT — most work is in agent/group-decision settings, not single-prompt critique.

**"Devil's Advocate" in LLM-assisted group decision making** ([dl.acm.org/doi/10.1145/3640543.3645199](https://dl.acm.org/doi/fullHtml/10.1145/3640543.3645199), IUI 2024). Groups with a DA LLM that challenged the AI recommendation showed **significantly higher accuracy** than groups with a passive AI. Validates "actively challenge" as a useful framing — but in a group-decision context, not a per-prompt validation context.

**"Devil's Advocate: Anticipatory Reflection for LLM Agents"** ([aclanthology.org/2024.findings-emnlp.53](https://aclanthology.org/2024.findings-emnlp.53.pdf)). Pre-action reflection ("what could go wrong here?") improves agent task completion.

**Falsification framing** — [Mike Caulfield, "Is the LLM response wrong, or have you just failed to iterate it?"](https://mikecaulfield.substack.com/p/is-the-llm-response-wrong-or-have). Folklore-grade but well-argued: instead of "verify the answer," ask "attack the answer." Specifically calls out **over-abduction** (model invents reasons when evidence is weak) and **sycophancy** (model defers to user-implied conclusion) as mechanisms our concept-validate prompt should be designed against.

**Self-reflection in academic critique** ([Nature npj AI 2025](https://www.nature.com/articles/s44387-025-00045-3)). Self-reflection prompts produce more substantive critique than direct critique prompts in academic-review settings.

**Mapped to our patterns:** P5. Honest read: the *direction* of the research is positive (challenging > passive), but published evidence is **thin** for the exact thing we do — single-shot per-candidate hostile review. Worth auto-tracking how often `concept-validate` actually rejects something vs how often it accepts. If reject-rate is <5% it's probably not doing what we think; if it's >40% the criteria are too aggressive.

**Caveat:** The "hostile reviewer" tone may interact badly with self-preference bias (§8) if validate sees the candidate's own LLM-generated text.

---

## 10. Batched prompts

**Cheng et al. 2023 — Batch Prompting (BatchPrompt is the Lin et al. follow-up).** Original batch prompting paper showed near-inverse-linear cost reduction with batch size, but documented **quality degradation as batch size grows**, with degradation correlated with **position and order** within the batch.

**Lin et al. 2023 — BatchPrompt** ([arXiv:2309.00384](https://arxiv.org/abs/2309.00384), ICLR 2024). Combats degradation with **batch permutation + ensembling** (run the same batch in multiple orders, ensemble). Recovers much of the lost quality but at the cost of multiple calls — partially defeats the throughput gain.

**Recent (2024-2025):** With long-context models (Gemini 1.5 Pro, Claude 3+), [many-shot/batched experiments](https://arxiv.org/html/2404.11018v2) show **minimal degradation** at much larger batch sizes than 2023 work — model capability has caught up.

**[Reasoning Under Constraint, 2025](https://arxiv.org/html/2511.04108)** finds batch prompting can actually *help* on reasoning models by suppressing overthinking.

**Mapped to our patterns:** P8 (8 batched sites). Implications:
- Batch position effects are real — items at the start/end of a batch may be treated differently from items in the middle. Worth shuffling within a batch as a robustness check.
- The 2023 degradation results were on smaller models / shorter contexts than what we use today. Don't over-correct; just measure.
- For consequential outputs, batch-of-1 with caching is a viable alternative — prompt caching (§1) makes the cost gap smaller than it used to be.

---

## 11. Aggressive vs neutral instruction tone

This is the area where **published evidence is weakest and most contradictory**.

**Yin et al. 2024 — "Should We Respect LLMs? A Cross-Lingual Study on the Influence of Prompt Politeness on LLM Performance"** ([arXiv:2402.14531](https://arxiv.org/abs/2402.14531), SICon 2024). Impolite prompts often perform worse; overly polite prompts don't help; **optimal politeness level is language-dependent**. English, Chinese, Japanese tested.

**Dobariya & Kumar 2025 — "Mind Your Tone"** ([arXiv:2510.04950](https://arxiv.org/abs/2510.04950)) and a follow-up [arXiv:2512.12812](https://arxiv.org/html/2512.12812v1). **Opposite finding on newer models:** GPT-4o accuracy went up with impolite prompts (80.8% → 84.8%). Suggests RLHF tuning has changed the picture since 2024.

**Mapped to our patterns:** P9 (our aggressive "IMMEDIATELY call X", "No announcements" in AGENTS.md). Honest read: **the published evidence doesn't say one way or the other** for our case. The AGENTS.md aggressive tone is targeting agent compliance (will the agent call the tool?), not output-quality — that's a different question than the politeness studies address. Independent evidence that aggressive instructions in *agent* harnesses produce more compliance would need to come from agent-eval work (SWE-bench, AgentBench), not the politeness papers. Worth flagging as a low-confidence pattern in our audit.

---

## 12. Prompt versioning + A/B testing

**Industry guides, no peer-reviewed canonical source.** Convergent best practice across vendor docs:

- **Immutability** — prompt versions are never modified in place; new version = new ID. ([Maxim AI guide](https://www.getmaxim.ai/articles/prompt-versioning-best-practices-for-ai-engineering-teams/))
- **Separate prompts from code** — prompts are loaded dynamically so wording changes don't require code redeploys. ([Reintech guide](https://reintech.io/blog/implement-prompt-versioning-management-production), [Braintrust guide](https://www.braintrust.dev/articles/ab-testing-llm-prompts))
- **Canary rollout** — new prompt sees ~10% of traffic; statistical-significance test before promotion. ([Traceloop guide](https://www.traceloop.com/blog/the-definitive-guide-to-a-b-testing-llm-models-in-production))
- **Regression test suites** — every prompt version is run against the same input set; outputs compared. ([Langfuse A/B docs](https://langfuse.com/docs/prompt-management/features/a-b-testing))
- **CI/CD integration** — prompts are first-class assets in the pipeline. ([Dextra Labs guide](https://dextralabs.com/blog/prompt-engineering-for-llm/))

**Mapped to our patterns:** Cross-cutting / methodology. Our Phase 140 protocol (snapshot before mutate, one site at a time, multi-repo, verdict gate) is essentially a hand-rolled version of the above, optimized for offline iteration rather than online traffic. The piece we're missing is a *statistical* gate — we currently do qualitative diff. If we promote to ≥10 test repos, we should add a quantitative pass/fail criterion (e.g., "wins on 7/10 repos under blind LLM-as-judge with position-shuffled comparison").

**Evidence quality:** Industry-folklore consensus. No academic studies of "how to A/B test prompts" — the engineering practices are converging without a published canonical reference.

---

## Cross-cutting research gaps and honest caveats

- **Hallucination in structured graph extraction (P10)** is documented but mitigations are immature. [LLMs Prompted for Graphs (arXiv:2409.00159)](https://arxiv.org/html/2409.00159v3) shows LLMs hallucinate even on well-known graphs (Karate club, Les Mis). For SourcePrep's cross-file edge / decision-chain extraction, we should expect hallucinations and design verification (intersection with the actual graph) into the pipeline rather than trusting outputs.
- **None of the cited research** evaluates on a codebase-intelligence task that resembles SourcePrep's atlas generation or concept extraction. Benchmarks are typically QA, summarization, math, code-gen. Take all of the "+X%" numbers as suggestive, not predictive.
- **Self-preference bias** (§8) is the single highest-risk research finding for our pipeline — multi-pass (P7) means a model's output gets evaluated by the same model later. Worth tracking whether we can use a smaller/different model for validate vs generate.
- **"Aggressive tone" research is in its infancy** — current evidence is too contradictory to draw conclusions, especially for agent-compliance scenarios different from the politeness benchmarks.

## How to use this doc

When writing an iteration block in `prompts/<site>.md`:

1. Note which patterns (P1-P10) the site falls under.
2. Look up the relevant sections above for *currently understood* best practice + caveats.
3. State the hypothesis in research-grounded terms when possible ("Min et al. 2022 suggests our T3 examples are teaching format more than content — try keeping format but rotating labels as an ablation").
4. Cite the specific source you're relying on in the iteration block. Future iterators should be able to follow your reasoning back to the literature, not just to vibes.

The downstream job (not this doc) is to write per-site recommendations that combine this research with our actual outputs. That work belongs in `prompts/<site>.md` and, when a pattern emerges across ≥3 sites, in `findings/`.
