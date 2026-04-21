# Research: Team LLM Preferences (GPU vs CPU+BYOK)

*Drafted: February 2026*
*Status: Exploratory Research*

When planning the Prep headless indexing architecture for teams, we must anticipate how businesses prefer to spend their compute and LLM budgets. Do they want to rent GPUs and run open-source models (Qwen3), or do they want to run cheap CPU servers and pay OpenAI/Anthropic per token?

## 1. The Two Buyer Profiles

### Profile A: The "Speed & Simplicity" Team (CPU + BYOK)
**Who they are:** Small teams, startups, web agencies.
**Their mindset:** "We already pay $2,000/mo to OpenAI. We don't want to manage GPU infrastructure. Just use our API key."
**What they will do:** 
- They will run the `prep-headless` container directly inside a standard GitHub Action or GitLab CI runner (which are CPU-only and essentially free).
- They will configure Prep to use their existing Anthropic/OpenAI API keys (`gpt-4.1-mini` or `claude-3.5-haiku`) for the 10-stage enrichment pipeline.
- **Pros for them:** Zero new infrastructure to learn. Runs directly in existing CI/CD.
- **Cons for them:** High per-token cost for massive repositories. Code is sent to a third-party API.

### Profile B: The "Privacy & Scale" Team (GPU + Local LLM)
**Who they are:** Mid-sized tech companies, enterprise teams, fintech/healthcare, or teams with massive monolithic repositories.
**Their mindset:** "We cannot send our proprietary backend to OpenAI. We want a fixed cost and total privacy."
**What they will do:**
- They will deploy the `prep-headless` template to RunPod, Modal, or AWS SageMaker, renting an Ada 5000, A4000, or A10G GPU.
- They will configure Prep to use the embedded Ollama engine with `qwen3:8b` or `deepseek-coder-v2`.
- **Pros for them:** 100% private. Fixed infrastructure cost (~$0.50 per run) regardless of codebase size.
- **Cons for them:** Requires setting up a RunPod/Modal account and managing an S3 bucket.

---

## 2. Strategic Implications for Prep

Because both profiles exist in large numbers, the `prep-headless` build must seamlessly support both paradigms without requiring different Docker images.

**The Implementation Plan:**
The headless CLI must accept explicit LLM overrides so the CI/CD pipeline can dictate the compute strategy.

*Example A (CPU + BYOK):*
```bash
# Runs on a standard GitHub Action (CPU only)
prep sync-headless \
  --repo-url "..." \
  --embedder native \
  --model-provider openai \
  --model-name gpt-4.1-mini \
  --api-key $OPENAI_API_KEY
```
*(Note: Prep's native ONNX embedder runs flawlessly on CPU, so semantic search generation doesn't require a GPU, only the LLM reasoning stages do).*

*Example B (GPU + Local):*
```bash
# Runs on RunPod / Modal Serverless GPU
prep sync-headless \
  --repo-url "..." \
  --embedder native \
  --model-provider local \
  --model-name qwen3:8b
```

## 3. Cost Analysis (Why Teams will choose GPU eventually)

If a codebase has 5,000 files:
- **BYOK (GPT-4.1-mini):** ~10M tokens processed. At $0.40/1M input and $1.60/1M output, a full indexing run costs roughly **$8.00**. If they merge to `main` 5 times a day, that's **$40/day ($1,200/mo)** in API costs.
- **RunPod GPU (A4000):** An A4000 costs ~$0.30/hour. Indexing 5,000 files takes ~2 hours. A full run costs **$0.60**. 5 times a day is **$3/day ($90/mo)**.

**Conclusion:** 
Teams will start with the CPU + BYOK approach because it requires zero infrastructure setup. As their codebase grows and their OpenAI bill spikes, they will migrate to the RunPod/Modal GPU approach. Prep must provide the templates to make that transition painless.
