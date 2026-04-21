# Institutional Model Assignment Plans & Cost Estimation

*Status: Reference & Go-To-Market Strategy (Updated Mar 2026)*
*Focus: Mapped model assignments for various enterprise and team environments based on existing vendor contracts. Provides two tiers (Premium and Standard) per profile.*

## Baseline Assumptions for Cost Estimation
To estimate the monthly AI cost per active full-time developer, we assume the following pipeline volume (handling daily deltas and occasional full rebuilds):

**Fast / Code Operations Volume (per month):**
- **Input Tokens:** ~2.5 Million (processing ~1,000 files/deltas for augmentation, cataloging, search prep, edge discovery)
- **Output Tokens:** ~250,000

**Deep Reasoning Operations Volume (per month):**
- **Input Tokens:** ~2.2 Million (processing ~500 files for epistemic enrichment, 20 atlas/module runs, 10 audits)
- **Output Tokens:** ~320,000

---

## 1. The Microsoft / Azure Enterprise
*Typical Profile: Fortune 500, healthcare, or established enterprises with existing Microsoft Enterprise Agreements and Azure OpenAI commitments.*

### Premium Tier (Maximum Accuracy & Deep Reasoning)
For teams where codebase complexity is extremely high and cost is secondary to developer productivity.
- **Reasoning Stages (Epistemic, Group Reasoning, Atlas, Audit):** `gpt-4.5-preview` or `o1`
  - *Why:* Unmatched agentic planning and logic for identifying deep architectural tech debt.
- **Fast / Code Stages (Augmentation, Cataloging, Search Prep):** `o3-mini`
  - *Why:* Incredibly capable reasoning at lower costs compared to full o1.

**Estimated Cost (Premium):**
- **Fast Tier (`o3-mini`):** $2.00/1M Input, $8.00/1M Output → ~$7.00 / mo
- **Reasoning Tier (`gpt-4.5-preview`):** ~$5.00/1M Input, ~$15.00/1M Output → ~$15.80 / mo
- **Total Estimated Cost:** **~$22.80 / developer / month**

### Standard Tier (Cost-Optimized Scale)
For large teams looking for the best balance of speed, cost, and quality.
- **Reasoning Stages:** `gpt-4o`
  - *Why:* Still an exceptional model for standard enterprise web apps and services.
- **Fast / Code Stages:** `o4-mini` or `gpt-4o-mini`
  - *Why:* Extremely cost-efficient ($1.10/$4.40 or cheaper) while maintaining high reliability for JSON structured extraction.

**Estimated Cost (Standard):**
- **Fast Tier (`o4-mini`):** $1.10/1M Input, $4.40/1M Output → ~$3.85 / mo
- **Reasoning Tier (`gpt-4o`):** $2.50/1M Input, $10.00/1M Output → ~$8.70 / mo
- **Total Estimated Cost:** **~$12.55 / developer / month**

---

## 2. The Modern Tech / AWS Startup
*Typical Profile: Y-Combinator startups, Vercel shops, SaaS companies using AWS Bedrock or Anthropic direct APIs.*

### Premium Tier (State-of-the-Art Coding Logic)
- **Reasoning Stages:** `claude-4.6-sonnet` (or `claude-3.7-sonnet` depending on regional rollout)
  - *Why:* Anthropic's Sonnet line consistently beats competitors in coding benchmarks. 4.6 brings agentic team capabilities that excel at whole-repo context.
- **Fast / Code Stages:** `claude-4.5-haiku`
  - *Why:* 4.5 Haiku is the new blazing-fast standard for extraction and edge discovery.

**Estimated Cost (Premium):**
- **Fast Tier (`claude-4.5-haiku`):** $0.50/1M Input, $2.50/1M Output → ~$1.87 / mo
- **Reasoning Tier (`claude-4.6-sonnet`):** $5.00/1M Input, $25.00/1M Output (est) → ~$19.00 / mo
- **Total Estimated Cost:** **~$20.87 / developer / month**

### Standard Tier (Proven Efficiency)
- **Reasoning Stages:** `claude-3.5-sonnet`
  - *Why:* Still highly respected, widely available, and incredibly reliable for complex JSON synthesis.
- **Fast / Code Stages:** `claude-4.5-haiku` (or `claude-3-haiku` legacy)

**Estimated Cost (Standard):**
- **Fast Tier (`claude-4.5-haiku`):** ~$1.87 / mo
- **Reasoning Tier (`claude-3.5-sonnet`):** $3.00/1M Input, $15.00/1M Output → ~$11.40 / mo
- **Total Estimated Cost:** **~$13.27 / developer / month**

---

## 3. The Google Cloud (GCP) Shop
*Typical Profile: AI startups, Android-heavy shops, or teams heavily invested in GCP Vertex AI. Excellent for massive mono-repos due to massive context windows.*

### Premium Tier
- **Reasoning Stages:** `gemini-2.5-pro`
  - *Why:* Capable of digesting up to 2M tokens. Ideal for module synthesis across massive directories in a single shot.
- **Fast / Code Stages:** `gemini-2.5-flash`
  - *Why:* Blazing fast, multimodal capable, and highly reliable for edge tracking.

**Estimated Cost (Premium):**
- **Fast Tier (`gemini-2.5-flash`):** $0.075/1M Input, $0.30/1M Output → ~$0.26 / mo
- **Reasoning Tier (`gemini-2.5-pro`):** $1.25/1M Input, $5.00/1M Output → ~$4.35 / mo
- **Total Estimated Cost:** **~$4.61 / developer / month**

### Standard Tier
- **Reasoning Stages:** `gemini-2.0-flash-thinking`
  - *Why:* Google's reasoning-focused Flash model. Cheaper than Pro but with chain-of-thought capabilities built in.
- **Fast / Code Stages:** `gemini-2.0-flash`
  - *Why:* The standard workhorse for vertex pipelines.

**Estimated Cost (Standard):**
- **Fast Tier (`gemini-2.0-flash`):** ~$0.26 / mo
- **Reasoning Tier (`gemini-2.0-flash-thinking`):** Highly subsidized/free on some tiers, assume ~$2.00 / mo.
- **Total Estimated Cost:** **~$2.26 / developer / month**
- *Takeaway:* GCP is aggressively pricing Vertex AI. This is the cheapest cloud API option by a wide margin.

---

## 4. The Air-Gapped / Defense / Finance Shop
*Typical Profile: Regulated industries that cannot send source code to external APIs. Must run entirely on VPC or internal hardware.*

### Premium Tier (Workstation / Server Rack)
- **Hardware:** 4x RTX 6000 Ada (192GB VRAM total) or 2x H100 (160GB VRAM) running via serverless container (e.g. `prep-headless:gpu`) or persistent K8s.
- **Reasoning Stages:** `qwen3.5:122b-a10b` (Q8 Quantized)
  - *Why:* The highest quality open-weight model currently available. Requires massive VRAM, but produces results rivaling GPT-4o.
- **Fast / Code Stages:** `qwen3.5:35b-a3b Q4` or `qwen3-coder-next`
  - *Why:* Fits perfectly alongside the 122b model on a multi-GPU setup. 

**Estimated Cost (Premium):**
- **API Cost:** $0
- **Compute Cost:** Amortized hardware (e.g., ~$25k for 4x Ada 6000 workstation) OR Cloud VPC instances. 
- *Cloud equivalent (e.g., AWS p4d.24xlarge / RunPod 4x A100):* ~$12.00/hr.
- Assuming 10 hours of batch indexing per dev per month: **~$120.00 / developer / month** (if using on-demand cloud).
- *Takeaway:* Expensive in pure cloud compute, but often a sunk cost if the enterprise already owns the hardware.

### Standard Tier (Single High-End GPU)
- **Hardware:** 1x RTX 6000 Ada (48GB), 1x A6000, or 2x RTX 4090.
- **Reasoning Stages:** `qwen3.5:35b-a3b Q8`
  - *Why:* Fits comfortably in 48GB of VRAM with room for a 32K context window.
- **Fast / Code Stages:** `qwen3.5:9b` or `qwen3-coder`

**Estimated Cost (Standard):**
- **API Cost:** $0
- **Compute Cost:** 1x A6000 on RunPod is ~$0.80/hr.
- Assuming 15 hours of batch indexing per dev per month (slower processing than multi-GPU): **~$12.00 / developer / month**.

---

## 5. The Prosumer / Solo Developer (Hybrid Cloud)
*Typical Profile: Individual Pro users optimizing for quality without massive API bills, utilizing local hardware for fast tasks and Ollama Cloud for reasoning.*

### Premium Tier (Mac Studio + Cloud)
- **Reasoning Stages:** `kimi-k2.5:cloud` (via Ollama Cloud Pro)
  - *Why:* 1T parameter logic offloaded to the cloud, preserving local resources.
- **Fast / Code Stages:** `qwen3.5:35b-a3b Q8` (Local on Mac Studio 64GB/128GB)
  - *Why:* Runs locally at 20+ tok/s, completely free.

**Estimated Cost:**
- **Local Compute:** $0 (sunk cost of hardware)
- **Ollama Cloud Pro:** **$20.00 / month flat**

### Standard Tier (MacBook Pro 16GB-32GB)
- **Reasoning Stages:** `kimi-k2.5:cloud` (via Ollama Cloud Free Tier - rate limited)
  - *Why:* Sufficient for daily delta reasoning and occasional module re-synthesis.
- **Fast / Code Stages:** `qwen3.5:9b` or `qwen3-coder` (Local)
  - *Why:* The only viable local option that fits in 16GB RAM while leaving room for the IDE and OS.

**Estimated Cost:**
- **Total Estimated Cost:** **$0.00 / month** (Utilizing free tiers and local compute, but requires patience with rate limits).
