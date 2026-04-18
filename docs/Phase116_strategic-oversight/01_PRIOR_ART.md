# 01 — Prior Art

Consolidated research brief. Sources cited throughout. Sections 1–7 catalog
the literature and production case studies. Section 8 distills design
implications for CoDRAG.

## 1. Hierarchical / multi-tier LLM architectures

- **Orchestrator-Worker (AutoGPT 2023; BabyAGI, Nakajima 2023).** A planner
  LLM decomposes goals into subtasks dispatched to workers. Became the
  default agent skeleton; suffers from unbounded recursion without a gating
  authority.
- **Self-Refine (Madaan et al., NeurIPS 2023).** Same model generates,
  critiques, and revises in a loop. +20% across 7 tasks but plateaus after
  2–3 iterations.
- **Reflexion (Shinn et al., NeurIPS 2023).** Episodic memory of failures
  written in natural language. 91% pass@1 on HumanEval vs 80% GPT-4 base.
- **Chain-of-Verification / CoVe (Dhuliawala et al., Meta 2023).** Model
  drafts, generates verification questions, answers them independently,
  revises. ~30% hallucination reduction on long-form QA.
- **Society of Mind / Multi-Agent Debate (Du et al., ICML 2024).** N agents
  debate R rounds; converges better than self-consistency on MATH and chess
  validity.
- **Mixture-of-Agents (Wang et al., Together AI 2024).** Layered architecture;
  each layer's agents see all prior outputs. Open-source MoA beat GPT-4 Omni
  on AlpacaEval 2.0 (65.1 vs 57.5).
- **MetaGPT / CEO-Worker hierarchy (Hong et al., ICLR 2024).** Explicit role
  ranks (CEO → PM → engineer → QA) with SOP-style handoffs. Strongest public
  evidence that role separation reduces error propagation in code-gen
  pipelines.

## 2. LLM-as-Judge / LLM-as-Verifier

- **Zheng et al., NeurIPS 2023 — "Judging LLM-as-a-Judge with MT-Bench."**
  GPT-4 agrees with human judges ~85% (matches inter-human agreement) but
  has position bias, verbosity bias, and ~10% self-enhancement bias.
- **AlpacaEval 2.0 (Dubois et al. 2024).** Naive LLM-judge scores dominated
  by output length. Introduced length-controlled win rate as correction.
  Relevant to any rubric we design.
- **Constitutional AI (Bai et al., Anthropic 2022).** Judge applies a
  written constitution. Rubric-based judgment outperforms free-form and is
  auditable.
- **Process Reward Models (Lightman et al., OpenAI 2023 — "Let's Verify
  Step by Step").** PRMs scoring each reasoning step beat outcome-only by
  8 points on MATH. Implies overseer should evaluate *intermediate*
  artifacts.
- **Prometheus (Kim et al., ICLR 2024).** Open 13B judge fine-tuned on
  rubric scoring. Pearson 0.897 with GPT-4 judgments. A smaller dedicated
  judge can substitute for a frontier overseer if rubrics are rigid.
- **Panickssery et al. 2024 — "LLM Evaluators Recognize and Favor Their
  Own Generations."** Judges prefer outputs stylistically similar to their
  own. Direct risk if overseer and orchestrator are same-family.

## 3. Weak-to-Strong / draft-then-verify

- **Weak-to-Strong Generalization (Burns et al., OpenAI 2023).** Strong
  student supervised by weak teacher recovers ~80% of the ground-truth gap.
  Overseer's *corrections* matter more than its scoring.
- **Speculative Decoding (Leviathan et al., ICML 2023; Chen et al.,
  DeepMind 2023).** Draft K tokens, target verifies in parallel. Typical
  γ (draft length) = 4–7, yielding 2–3× speedup. Pattern maps cleanly to
  semantic verification.
- **Self-Consistency (Wang et al., ICLR 2023).** Sample N=40 reasoning
  paths, majority vote. Diminishing returns after N≈20 on GSM8K. Multiple
  weak samples often substitute for one strong verifier.
- **Verifier-Generator (Cobbe et al., OpenAI 2021 — GSM8K paper).**
  Best-of-N with verifier beat 30× larger fine-tuned generator. Sweet spot
  N=100; saturation near N=20.
- **Canonical invocation ratio: no consensus.** Speculative decoding uses
  ~1:4–1:7. Cascading systems (§4) route 10–30% to expensive tier.
  **This is the single biggest open design parameter.**

## 4. Selective invocation / escalation policies

- **FrugalGPT (Chen, Zaharia, Zou — Stanford 2023).** LLM cascade with
  learned confidence gate. Achieved GPT-4 quality at 2–4% cost on
  HEADLINES/AGNEWS/COQA. **Most directly applicable to our design.**
- **RouteLLM (Ong et al., LMSYS 2024).** Trained router on Chatbot Arena
  preference data. 85% cost reduction with matched quality on MT-Bench.
  Uses BERT classifier, not the LLM itself.
- **AutoMix (Madaan et al., EMNLP 2024).** Self-verification gates
  escalation from Llama → GPT-4. Adds a meta-verifier that predicts
  whether the small model's self-score is trustworthy.
- **Cascaded Inference / Mixture of Thoughts (Yue et al. 2024).** Answer
  consistency across CoT samples as the gating signal. Cheaper than
  training a router.
- **Entropy / logprob gating (Kadavath et al., Anthropic 2022 — "Language
  Models Mostly Know What They Know").** Token-level confidence is
  calibrated enough to gate well-defined tasks. Less reliable for
  open-ended generation.
- **Tandem Transformers (Google 2024).** Formal analysis: disagreement-
  based triggers are Pareto-optimal over pure uncertainty triggers.

## 5. Consensus-of-peers vs single-authority

- **Self-Consistency (Wang 2023).** 40× same-model sampling beat single
  strong decode on GSM8K (+18%). Peer consensus often sufficient without
  any overseer.
- **Tree-of-Thoughts (Yao et al., NeurIPS 2023).** Structured search +
  self-evaluation beat CoT by 70% on Game of 24. Single model can act as
  both proposer and evaluator.
- **Multi-Agent Debate (Du et al. 2024).** Peer debate > self-consistency
  on factual tasks; < single-strong-judge on subjective tasks.
- **MoA vs single judge (Wang, Together 2024).** Layered MoA beat
  monolithic GPT-4. 3–5 peer samples + aggregator can exceed
  single-overseer review at similar cost.
- **Tradeoff summary:** Peer consensus wins on *factual/reasoning* with
  discrete answers. Single strong authority wins on *subjective/rubric*
  where majority has no signal. CoDRAG's outputs straddle both — concept
  promotion is subjective; edge inference is discrete.

## 6. Failure modes

- **Sycophancy (Sharma et al., Anthropic 2023).** Judges capitulate when
  challenged. If overseer sees "orchestrator says X, is this right?",
  it's biased toward approval. **Present outputs without attribution.**
- **Self-enhancement bias (Zheng 2023).** 10% preference for same-family.
  Avoid Claude-judging-Claude.
- **Cascade error amplification (Dohan et al. 2022 — "Language Model
  Cascades").** Errors compound through stages; overseer can confirm
  upstream hallucinations it cannot independently detect.
- **Ensemble collapse (informal, Arditi et al. 2024).** Shared training
  data → verifier accepts drafter's wrong answers.
- **Cost blowup.** Even 1-in-10 Opus invocation can dominate pipeline
  cost. Flagged by FrugalGPT as the primary reason naive escalation fails
  in production.
- **Latency tail.** Sparse overseer calls become P99 latency spikes.
  Batch or make async.
- **Anchoring (Stureborg et al. 2024).** Judges anchor on first-seen
  output. Randomize order when comparing alternatives.

## 7. Production case studies

- **Cursor Fast Apply / tab-complete (Cursor blog 2024).** Fine-tuned
  Llama-70B for apply; Claude/GPT-4 for chat. Routes by task type, not
  uncertainty. No public overseer loop.
- **Cognition Devin + subsequent "Don't build multi-agents" blog (2025).**
  Argued *against* overseer patterns, citing context fragmentation.
  Architecture is single-agent with tool loops. Worth reading as a
  counter-thesis.
- **Aider "architect mode" (Paul Gauthier, openly documented —
  aider.chat/2024/09/26/architect.html).** Reasoning model (o1 / Opus)
  plans, editor model (Sonnet / Haiku) applies. **Closest public analog
  to Phase 116.** Runs strong model every turn, not selectively.
- **GitHub Copilot Workspace (GitHub Universe 2024 talks).** Spec →
  plan → implement with "checkpoint reviews." No disclosed overseer
  model; same model at different prompts.
- **Sourcegraph Cody "Deep Cody" (blog 2024).** Agentic context with
  internal critique steps. Single model, no tier separation disclosed.
- **Replit Agent (Catasta, 2024).** Multi-agent with "verifier agent"
  — reportedly same Claude model with a verification prompt. Inferred
  not confirmed.
- **Factory.ai "Droids" (Grinberg podcasts 2024).** Tiered agents by
  task type. No public overseer gating.

**Honest assessment: no major shipped coding system publicly documents a
true "sparse frontier overseer" pattern.** Aider's architect mode is the
nearest cousin but it fires every turn, not selectively. **Phase 116 has
room to be genuinely novel in public.**

## 8. Design implications for CoDRAG

1. **Default to 1-in-10 to 1-in-20 invocation**, gated by confidence +
   disagreement. Aligned with FrugalGPT cascade ratios and Cobbe
   verifier-saturation.
2. **Disagreement-based gating beats entropy-based** (Yue 2024). Sample
   3–5 Kimi outputs; if they agree, skip overseer. If they diverge on a
   structural claim (symbol, edge type), escalate.
3. **Score with an explicit rubric, not free-form** (Constitutional AI,
   Prometheus). Per-checkpoint checklist: "Does consolidation preserve
   every cited symbol? Are edge types consistent? Hallucinations
   introduced?" Auditable, less biased.
4. **Hide provenance from the overseer** (Sharma 2023). Do not tell
   Opus "Kimi produced this." Evaluate the artifact on its merits.
   Randomize option order (Stureborg 2024).
5. **Evaluate intermediate artifacts, not final outputs** (Lightman 2023
   PRM). Trace deltas and concept assertions, not persisted JSON.
   Step-level supervision > outcome-level by ~8 points in comparable
   settings.
6. **Avoid same-family judge/generator pairs** (Panickssery 2024).
   Kimi (Moonshot) + Gemini Flash + Opus (Anthropic) is well-diversified.
   Gemini-overseer over Gemini-orchestrator would inherit family bias.
7. **Async for leaves, blocking for hubs.** Use `codrag_impact`: touching
   a hub file → block on overseer; touching a leaf → persist, attach
   findings as deferred antibodies. Maps naturally onto existing immune-
   system concept.
