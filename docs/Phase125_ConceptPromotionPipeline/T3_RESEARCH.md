# Phase 125 T3 — research findings on LLM confidence calibration

> **Revision 2 (authoritative).** Captured 2026-05-02 across two
> sequential research passes. Round 1 established the high-level
> approach (tier rubric, rationale-before-score). Round 2 went deep
> on tier-rubric pitfalls, schema design, and validation — and
> **overturned several round-1 choices**. This doc is the merged
> authoritative reference. The "Round 1 → Round 2 changes" section
> at the bottom records what was wrong about v1.

---

## The diagnosis

Asking an LLM for a continuous 0.0-1.0 confidence float is the
canonical failure mode documented in **Xiong et al. ICLR 2024**
("Can LLMs Express Their Uncertainty?", arXiv:2306.13063). Models
cluster scores at 80-100% in multiples of 5 because they imitate
human conversational confidence registers, not estimate
P(claim is true). SourcePrep's empirical histogram on 1,590 concepts
matches this pathology exactly:

- ≥0.95: 38 (2.4%)
- 0.85-0.95: 577 (36%)
- 0.70-0.85: 898 (57%)
- <0.70: 77 (5%)

The fix is **not tuning the prompt to use the float range better** —
the field needs to be replaced.

---

## Anti-patterns (delete from any prompt)

| Anti-pattern | Why it fails |
|---|---|
| `"Output a confidence between 0.0 and 1.0"` | Continuous self-rating without anchors collapses to social register (~0.8 ± 0.1). **Primary cause of our distribution.** |
| Score-first JSON schemas | Model defends whatever number it emitted first (motivated reasoning). |
| Hint ranges like `"use 0.5-1.0"` | Anchors to the midpoint of the hinted range. |
| `"How confident are you?"` | Invokes politeness register. Ask "what tier does the evidence pass?" instead. |
| Single-pass extraction with confidence | Model has no incentive to discover its own weakness in one shot. |
| **Descriptive tier names** ("AXIOMATIC", "LOAD-BEARING") | Pretraining priors make the model treat these labels as sacred → systematic under-use. Use **neutral labels (T1/T2/T3)** and map to descriptive names at the storage layer. |
| **5-tier rubrics by default** | G-Eval / HELM calibration work shows 3-tier produces lower ECE than 5-tier; 5 is justified only with ≥50 calibration examples per tier. |
| Score-only schemas (no rationale fields) | Without forcing counter-evidence + falsification first, the score is uncalibrated. |

---

## The pattern that works

**Three-tier neutral rubric + adversarial self-critique + pairwise commit.**

### Tier definitions (each a passing test, not a feeling)

```
T1 (lowest): pattern observed in code, no enforcement.
  Anchor example: a comment in one file says "we should always X"
  but no test, lint, or type check ensures it.

T2: documented decision with ≥1 enforcing mechanism (test, lint,
    docstring referenced from a contract, ADR with named anchor).
  Anchor example: "API responses use envelope format" —
  enforced by test_api_envelope.py + a docstring contract.

T3 (highest): codified in CI/types/constraint-concept; violations
    fail the build.
  Anchor example: "All API responses must be Pydantic BaseModels" —
  enforced by mypy strict + test_api_schema.py at PR-time.
```

Map tiers → floats **post-hoc, at storage time**:

| Tier | Stored confidence | Phase 125 Pass 4 status |
|---|---:|---|
| T3 | 0.92 | `active` |
| T2 | 0.65 | `triage_pending` |
| T1 | 0.30 | `archived` |

The LLM **never sees floats or descriptive names**. The mapping
happens server-side after parsing.

### Why 3 tiers, not 5

Round 1 proposed 5 tiers (SPECULATIVE / SUGGESTIVE / SUPPORTED /
LOAD-BEARING / AXIOMATIC). Round 2 research:

- Liu et al. 2023 (G-Eval, arXiv:2303.16634): GPT-4 with discrete
  1-5 rubrics clusters heavily on the modal "3" (mode collapse).
- HELM calibration work: 3-tier produces lower ECE than 5-tier
  unless you have ≥50 calibration examples per tier. We have zero.
- Hashemi et al. 2024 (LLM-Rubric): models match prose vibes 60%
  vs the actual passing test 40%. Fewer tiers = clearer rubric
  boundaries.

Start at 3. Expand to 5 only if calibration data justifies it.

### Why neutral labels (T1/T2/T3)

- Zheng et al. 2023 (MT-Bench, arXiv:2306.05685): loaded labels
  create position-and-prior biases.
- "AXIOMATIC" / "LOAD-BEARING" carry strong philosophical and
  engineering priors → models treat them as sacred → systematic
  under-use.
- Lin et al. 2024 ("Generating with Confidence", arXiv:2305.19187):
  neutral ordinal labels yield better calibration when the output
  is machine-consumed.

### Pairwise-commit anti-mode-collapse trick

Anthropic's Constitutional AI grading and the G-Eval mitigation
both force the model to make a *pairwise* commit before the final
tier:

```
"tier_pairwise": "closer_to_lower" | "closer_to_higher"  // forced
"tier": "T1" | "T2" | "T3"
```

Pairwise resists middle-bias (model can't safely pick T2 just to
hedge — it had to commit "closer_to_T1" or "closer_to_T3" first).
Add this field BETWEEN the rationale fields and the final tier.

### Adversarial self-critique BEFORE the tier

Two-call structure or single-call with ordered fields. Order is:

1. Counter-evidence — what would CONTRADICT this concept?
2. Coincidence hypothesis — could the pattern exist for unrelated reasons?
3. Falsification test — what concrete observation would refute it?
4. Pairwise commit — closer to T-(N-1) or T-(N+1)?
5. **Then** tier classification.

**Critical**: rationale before score, never score before rationale.
When score comes first, subsequent text rationalizes the number
(motivated reasoning). When counter-evidence comes first, low
tiers become reachable because doubt was spoken out loud.

---

## Output schema (final)

```json
{
  "counter_evidence": "...",
  "coincidence": "...",
  "falsification": "...",
  "tier_pairwise": "closer_to_lower" | "closer_to_higher",
  "tier": "T1" | "T2" | "T3",
  "tier_justification": "...",
  "consolidation_action": "keep" | "split" | "merge_with_X" | "drop",
  "refined_title": "...",
  "refined_content": "..."
}
```

Field order rationale (Round 2 Q2):

- Rationale fields (`counter_evidence` → `falsification`) come first
  to force evidence-before-judgment.
- `tier_pairwise` comes BEFORE `tier` to force the anti-middle-bias
  commit.
- `tier_justification` after `tier` — the model justifies its choice,
  not pre-commits.
- `consolidation_action` after tier — "drop" decisions are easier
  once tier is established.
- `refined_title` and `refined_content` LAST because they are the
  longest free-text fields. **Truncation insurance**: if `max_tokens`
  hits, we lose the least critical fields.

---

## System vs user prompt placement

**Anthropic prompt-engineering guide + Liu et al. consensus:**

- Tier definitions + JSON schema → **system prompt** (rules)
- Concept under evaluation, cluster shadows, linked docs →
  **user prompt** (the specific input)
- 2-3 few-shot examples → **user prompt** (before the actual input)
- One-line tier recap at the END of user prompt → anti-recency-bias
  insurance: `// Reminder: T1 = observed-only, T2 = enforced-by-test, T3 = enforced-by-build`

Liu et al. 2023 showed system-prompt rules degrade in adherence as
user-prompt content grows. The recap counteracts this.

**System prompt size cap: ≤2K tokens.** Each worker call processes
N cluster-representatives × ~500 tokens of context each plus the
system prompt; with 1,272 reps fanned to 10 workers that's ~75K
tokens of user content per worker on Kimi-K2.6's ~64K context.
System must stay tight.

---

## Few-shot examples (Q4)

Include **3 worked examples** in the user prompt, ordered ascending
(T1 → T2 → T3):

1. A clear T1 (observed-but-not-enforced)
2. A boundary case: a SUPPORTED-looking concept that is actually
   T2 (because the enforcement isn't in CI/types — it's just in a
   test docstring). **Boundary cases teach more than corners.**
3. A clear T3 (codified in CI/types)

Anti-anchoring rules:

- Order ascending (matches the "earn your way up" framing).
- No two examples share a tier.
- The boundary case has the longest rationale — models imitate
  the form, so the model learns "T2 needs detailed enforcement
  reasoning."

Min et al. 2022 ("Rethinking Demonstrations", arXiv:2202.12837):
format-matching matters more than content correctness for
classification. Examples teach the JSON shape and rationale-first
ordering even if the model knows the task.

---

## Synthesis-layer design

Pass 3 has worker fan-out + synthesizer consolidation (same shape
as Phase 124's swarm). Synthesis-specific design:

1. **Verifier ≠ generator.** Run workers on Qwen3-coder-next, run
   the synthesizer on Kimi-K2.6 (or vice versa). DeepSeek-Math
   (Shao et al. 2024) and Cobbe et al. 2021 show 5-10% accuracy
   gain from independent failure modes.
2. **N=5 self-consistency at synthesis** (Wang 2022, arXiv:2203.11171).
   Run synthesis 5 times, take majority tier per concept. Cost is
   only on synthesis (small input), not workers — affordable.
3. **Disagreement reconciliation:**
   - Tier-distance 1 (e.g., T2 vs T3): **conservative** — pick the
     lower tier (Sparrow / Glaese et al. 2022).
   - Tier-distance ≥2 (e.g., T1 vs T3): re-judge with both
     rationales attached as input.
   - **Don't average tiers.** Averaging discrete ordinal classes
     is meaningless.

---

## Decoding settings

Tuned for hosted Kimi-K2.6 / Qwen3-coder-next 32B-class instruct
models:

| Setting | Value | Rationale |
|---|---|---|
| `temperature` | 0.1 | Classification stability (Round 2 Q6) |
| `top_p` | 0.9 | Standard for structured output |
| `think` | **False** | Kimi's `think=True` degrades JSON-mode reliability — emits thinking trace instead of JSON. Embed CoT as schema fields (counter_evidence etc.) instead. |
| `response_format` | `{"type": "json_object"}` | Explicit JSON mode |
| `max_tokens` | 2× expected | Truncation insurance (Round 2 Q2) |
| Defensive ` ```json ` fence strip | yes | Kimi sometimes wraps JSON in markdown fences even in json_mode |

---

## Invalid-tier handling

Production systems (PrometheusEval, OpenAI Evals) follow the same
recipe:

1. Reject + single retry with the validator error appended to the
   user prompt.
2. If still invalid, force-pick nearest by Levenshtein distance
   ("T_2" → "T2") and **log for human review**.
3. Don't silently coerce arbitrary strings.

---

## Validation methodology

Three measurements, in this order:

### 1. Distribution shape (cheap smoke test)

Bin all concepts under each prompt variant. Target: roughly uniform
or bimodal across T1/T2/T3, **not** a clump in T2. A prompt that
emits "always T2" looks fine on histogram and is useless.

### 2. Hand-labeled calibration sample (the real test)

50-concept calibration set: stratified across tiers, each labeled
TRUE / PARTIALLY-TRUE / FALSE without seeing the model's tier.

- **Per-tier accuracy:** T1 should be ~30% true, T2 ~70% true,
  T3 ~95% true (monotonically increasing).
- **Reliability diagram:** plot predicted-tier on x, empirical
  fraction-correct on y. Look for the S-curve; overconfidence at
  extremes is the typical failure.
- **Ordinal ECE** (Naeini et al. 2015): adjacent-accuracy-weighted
  variant for 3-tier ordinal data. Realistic first-attempt: 0.15-0.25.
  <0.10 is good. <0.05 is suspicious (probably overfit).

### 3. Adversarial trap set

Build by inversion: take 25 clearly-T3 concepts, strip the
CI/types enforcement reference from their anchors, feed to the
model. Should drop to T2. If they stay at T3, the model is matching
prose vibes (Round 2 Q1 finding — Hashemi et al. 2024). PrometheusEval
and HELM both build trap sets this way.

### 4. Cross-LLM agreement (cheap iteration proxy)

Run the same prompt through Kimi-K2.6 AND Qwen3-coder-next on a
200-concept sample. Cohen's κ on tier assignment. κ jumping from
~0.35 (continuous-float prompt) to ~0.65+ (tier prompt) is strong
evidence of evidence-based judgment. Cheaper than (2); use between
hand-label rounds.

### Tooling

- **Promptfoo** is genuinely useful for the iterate-prompt-vs-fixed-evalset
  loop. JSON-schema and tier-distribution assertions are native.
- **DSPy** is overkill until you have ≥100 labeled examples and
  want to optimize the prompt automatically.
- **TextGrad** is research-grade — skip.

Realistic path: **50-concept hand-labeled set + Promptfoo for
regression**. Iterate prompt → check distribution + ECE → repeat.

---

## Recommended implementation

System prompt (≤2K tokens):

```
You evaluate code-intelligence concepts extracted from a codebase.
Each concept is a short rationale claim about a software pattern.

Your job: classify each concept against three tiers. The tier
reflects how well the EVIDENCE supports the concept — not how
plausible-sounding the wording is.

TIER DEFINITIONS (each is a PASSING TEST):

  T1 — pattern observed in code, no enforcement.
       Test: a reader could find counter-examples in the same
       codebase that don't follow the pattern, and nothing prevents
       them.
       Anchor example: "Database access uses connection pools" —
       observed in 3 modules but two other modules use raw connections;
       no test, lint, or type check enforces pooling.

  T2 — documented decision with at least one enforcing mechanism
       (test, lint rule, docstring referenced as a contract, ADR
       with a named anchor).
       Test: a developer who violated this pattern would either
       (a) get a test failure, OR (b) be flagged by a linter, OR
       (c) be pointed at a written decision document by a reviewer.
       Anchor example: "API responses use envelope format" —
       enforced by test_api_envelope.py and documented in API.md.

  T3 — codified in CI/types/constraint-concept; violations fail the
       build.
       Test: a developer who violated this pattern CANNOT merge —
       PR-time mypy strict / build / tests will block it.
       Anchor example: "All API responses must be Pydantic
       BaseModels" — mypy strict catches non-BaseModel returns,
       test_api_schema.py validates structure at every PR.

ADVERSARIAL CRITIQUE FIRST: before you assign a tier, you MUST
think about counter-evidence, coincidence, and falsification.

OUTPUT FORMAT: a single JSON object with these fields IN THIS
ORDER (do not reorder):

  counter_evidence:    What would CONTRADICT this concept? Quote
                       specific files, classes, or patterns if any.
                       If you cannot name counter-evidence, write
                       "none observed" — but that should make the
                       tier lower, not higher.
  coincidence:         Could the pattern exist for an UNRELATED
                       reason (legacy code, copy-paste, framework
                       defaults)?
  falsification:       What CONCRETE observation would refute the
                       concept? If you cannot name a falsification
                       test, the concept is T1.
  tier_pairwise:       Before naming the tier, commit: is this
                       CLOSER TO T(n-1) or T(n+1)? Pick "closer_to_lower"
                       or "closer_to_higher".
  tier:                "T1" | "T2" | "T3"
  tier_justification:  Cite which TIER PASSING TEST is satisfied.
                       Reference specific files/tests if you can.
  consolidation_action: "keep" | "split" | "merge_with_<id>" | "drop"
  refined_title:       Improved title (≤80 chars).
  refined_content:     Improved 2-4 sentence rationale.

Output JSON only. No prose, no markdown fences.

// Reminder: T1 = observed-only, T2 = enforced-by-test, T3 = enforced-by-build.
```

User prompt template (per cluster representative):

```
[3 few-shot examples here, ascending T1 → T2-boundary → T3]

CONCEPT TO EVALUATE:

  Title:   {title}
  Content: {content}
  Anchors: {anchors}

  Cluster shadows (other concepts that grouped with this one — same
  anchor overlap or near-duplicate titles):
  {shadow_summary}

  Linked planning docs (excerpts from atlas_markdown_links.json):
  {relevant_doc_excerpts}

Output the JSON.
```

---

## Round 1 → Round 2 changes (history)

What round 1 said vs what round 2 corrected:

| Choice | Round 1 | Round 2 | Why |
|---|---|---|---|
| Tier count | 5 (SPECULATIVE/SUGGESTIVE/SUPPORTED/LOAD-BEARING/AXIOMATIC) | **3 (T1/T2/T3)** | G-Eval / HELM: 5-tier needs ≥50 calibration examples per tier |
| Tier labels | Descriptive | **Neutral (T1/T2/T3)** | Pretraining priors on "AXIOMATIC" / "LOAD-BEARING" cause systematic under-use |
| Anti-mode-collapse | (none) | **Pairwise commit field** | Constitutional AI / G-Eval standard mitigation |
| Tier order | Implicit | **Ascending (T1→T3)** | Wang 2023: list order biases output; ascending matches "earn your way up" |
| Tier definitions | Prose passing tests | **Prose + concrete code-anchor example each** | Hashemi et al.: prose alone gets matched on vibes 60% of the time |
| Field order in JSON | rationale first, score next | **rationale → pairwise → tier → free-text LAST** | Truncation insurance for hosted-model outputs |
| Few-shot | "consider" | **3 examples, ascending, ONE boundary case** | Min et al. 2022: format > content for classification |
| Synthesis | "elevate cross-segment" | **Different model + N=5 self-consistency + disagreement reconciliation** | DeepSeek-Math + Wang 2022 |
| Validation | ECE + cross-LLM | **+ 25-concept adversarial trap set + Promptfoo regression** | Hashemi et al. + production patterns |

---

## Sources

### Round 1 (high-level)

- [Xiong et al. — Can LLMs Express Their Uncertainty? (ICLR 2024, arXiv:2306.13063)](https://arxiv.org/abs/2306.13063)
- [Madaan et al. — SELF-REFINE (arXiv:2303.17651)](https://arxiv.org/abs/2303.17651)
- [Hamel Husain — LLM-as-a-Judge](https://hamel.dev/blog/posts/llm-judge/) and [evals iteration](https://hamel.dev/blog/posts/evals/)
- [Yang et al. — On Verbalized Confidence Scores (arXiv:2412.14737)](https://arxiv.org/pdf/2412.14737)
- [Lilian Weng — Extrinsic Hallucinations in LLMs](https://lilianweng.github.io/posts/2024-07-07-hallucination/)

### Round 2 (deep dives)

- [Liu et al. — G-Eval (arXiv:2303.16634)](https://arxiv.org/abs/2303.16634) — middle-tier mode collapse + probability-weighted scoring
- [Kim et al. — PrometheusEval (arXiv:2310.08491 + 2405.01535)](https://arxiv.org/abs/2310.08491) — per-tier reference responses
- [Zheng et al. — MT-Bench (arXiv:2306.05685)](https://arxiv.org/abs/2306.05685) — position and prior biases
- [Lin et al. — Generating with Confidence (arXiv:2305.19187)](https://arxiv.org/abs/2305.19187) — neutral ordinal labels
- [Wang et al. — Large Language Models are not Fair Evaluators (arXiv:2305.17926)](https://arxiv.org/abs/2305.17926) — order effects
- [Hashemi et al. — LLM-Rubric (2024)](https://arxiv.org/abs/2401.12174) — rubric adherence
- [Tian et al. — Just Ask for Calibration (arXiv:2305.14975)](https://arxiv.org/abs/2305.14975) — enum vs int vs float
- [Min et al. — Rethinking Demonstrations (arXiv:2202.12837)](https://arxiv.org/abs/2202.12837) — few-shot format
- [Lu et al. — Fantastically Ordered Prompts (arXiv:2104.08786)](https://arxiv.org/abs/2104.08786) — example ordering
- [Wang et al. — Self-Consistency (arXiv:2203.11171)](https://arxiv.org/abs/2203.11171) — N-vote majority
- [Glaese et al. — Sparrow (arXiv:2209.14375)](https://arxiv.org/abs/2209.14375) — conservative epistemics
- [Shao et al. — DeepSeek-Math (arXiv:2402.03300)](https://arxiv.org/abs/2402.03300) — verifier ≠ generator
- [Cobbe et al. — Training Verifiers (arXiv:2110.14168)](https://arxiv.org/abs/2110.14168)
- [Kadavath et al. — Language Models (Mostly) Know What They Know (arXiv:2207.05221)](https://arxiv.org/abs/2207.05221)
- [Willard & Louf — Outlines (arXiv:2307.09702)](https://arxiv.org/abs/2307.09702) — grammar-constrained decoding
- [Reynolds & McDonell — Prompt Programming for LLMs (arXiv:2102.07350)](https://arxiv.org/abs/2102.07350)
- [Naeini et al. — ECE (2015)](https://ojs.aaai.org/index.php/AAAI/article/view/9602)
- Promptfoo: https://www.promptfoo.dev/
