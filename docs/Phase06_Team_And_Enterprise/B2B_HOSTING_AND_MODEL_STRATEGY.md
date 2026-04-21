# B2B Hosting and Model Strategy for Prep

*Status: Research & Strategy*
*Target Audience: Teams, SMBs, and Enterprise Customers*

## 1. The Reality of Enterprise AI Adoption

When targeting Teams and Enterprise customers, the strategy must align with how businesses actually procure and manage IT and infrastructure.

### Vendor Consolidation & Compliance
Most established businesses and enterprises have strict compliance requirements (SOC2, HIPAA, GDPR) and existing Data Processing Agreements (DPAs) with major cloud providers (Microsoft, AWS, Google).
- **Azure OpenAI** is the dominant force in enterprise AI because companies already use Azure and Microsoft 365. Adding an Azure OpenAI resource falls under their existing enterprise agreement and billing.
- **AWS Bedrock** (hosting Anthropic's Claude) is similarly popular for AWS-native companies.
- **Data Privacy:** Enterprises are extremely sensitive to sending proprietary source code to third-party APIs. They will only do so if the provider guarantees zero data retention for training. Both Azure and AWS offer these guarantees by default for enterprise customers.

### RunPod & Modal (BYOC) vs. Managed APIs
While **RunPod Serverless** and **Modal** are brilliant for developers and startups, they introduce friction for B2B sales:
- **Procurement Friction:** A mid-market or enterprise company doesn't want to set up a new vendor relationship with RunPod just to run Prep.
- **Maintenance:** Even though Serverless scales to zero and requires no manual "turning on and off," it still requires managing a Docker container registry, handling cold starts, and monitoring a new billing dashboard.
- **The Winner for B2B:** **CPU Runners + Managed APIs**. Most companies would strongly prefer to run a lightweight `prep-headless:cpu` Docker image directly in their existing GitHub Actions or GitLab CI runners, and point it to their corporate Azure OpenAI or Anthropic API key. This requires **zero new infrastructure vendors**.

## 2. Ollama Cloud Viability for Teams

Ollama recently introduced Cloud tiers (Free, Starter ~$3/mo, Pro ~$20/mo).
- **Current State:** Ollama Cloud is currently a B2C / Prosumer offering. It focuses on individual developers needing access to massive models like `kimi-k2.5` or `llama3.1:405b`.
- **B2B / Enterprise Readiness:** As of early 2026, Ollama does not have a mature Enterprise offering (e.g., SSO, invoice billing, strict B2B DPAs guaranteeing zero training retention, dedicated VPC peering).
- **Privacy Concerns:** Community reports indicate Ollama Cloud *may* use data for training on lower tiers. Enterprises will immediately reject sending their source code to a consumer cloud without a strict enterprise DPA.
- **Conclusion:** While Ollama Cloud is incredible for the Pro Desktop tier, it is **not a viable foundation for a B2B Team/Enterprise pitch**. We cannot confidently tell an Enterprise "Just buy our team license and subscribe to Ollama Cloud" because their infosec team will likely block Ollama Cloud.

## 3. Model Selection: Claude 3.5 Sonnet vs. Qwen / Kimi

For the Pro Desktop user, we heavily optimize for open-weight models (`qwen3.5:35b`, `kimi-k2.5` via Ollama) because they are free to run locally or cheap via prosumer clouds.
However, in the Team/Enterprise context, the calculus changes entirely:

### The Problem with 35B Local Models
A 35B parameter model requires 24GB+ of VRAM.
- Most corporate laptops are standard 16GB MacBooks or basic Windows machines.
- Expecting a team of 50 developers to each run a 35B model locally for deep enrichment is unrealistic. Their laptops will freeze, battery life will tank, and productivity will drop.

### The Enterprise Standard: Claude 3.5 Sonnet & GPT-4o
When a team runs Prep in CI/CD, they are willing to pay API costs for accuracy and speed.
- **Claude 3.5 Sonnet** (via Anthropic or AWS Bedrock) is widely considered the best model for coding and reasoning. It is the gold standard for enterprise dev tools (like Cursor, Windsurf, GitHub Copilot).
- **GPT-4o-mini / GPT-4o** (via Azure OpenAI) is the default choice for Microsoft shops.
- These models provide **better reasoning than Qwen 35B**, and because they are hosted on enterprise-grade infrastructure, they process thousands of files rapidly in CI/CD pipelines.

## 4. Proposed B2B Go-To-Market Strategy

To successfully sell Prep to Teams and Enterprises, we must offer a **"Bring Your Own API" (BYOA)** model alongside the "Bring Your Own Compute" (BYOC) model.

1. **The Primary Team Pitch: "Zero-Infra CI/CD Sync"**
   - The team drops the `prep-headless:cpu` action into their GitHub Actions.
   - They provide their corporate Anthropic / Azure OpenAI API key.
   - The CI runner executes the deep enrichment using the API.
   - The output is zipped and stored in their existing AWS S3 bucket.
   - Local developers download the pre-built index and run Prep locally using only a tiny, fast model (like `qwen3.5:9b`) just to handle local uncommitted deltas.

2. **The Secondary Pitch: "Air-Gapped / VPC Serverless"**
   - For defense, healthcare, and finance companies that cannot use APIs.
   - They use `prep-headless:gpu` on AWS ECS/SageMaker or RunPod inside their VPC.
   - They run open-weight models (Qwen 35b) entirely within their network.

### Key Takeaways
- **Pivot the enterprise messaging** away from "Set up RunPod" to "Use your existing Anthropic/OpenAI keys in your existing CI/CD."
- **Embrace Cloud APIs for Teams:** Businesses prefer paying API costs to OpenAI/Anthropic over managing GPU servers.
- **Keep local models small for teams:** The shared index handles the heavy lifting, so the developer's laptop only needs a tiny local model (or a cloud API connection) for daily querying and local delta syncing.
