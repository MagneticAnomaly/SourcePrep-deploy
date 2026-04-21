# Team & Enterprise Strategy: Shared Indexing & Pricing Exploration

*Drafted: February 2026*
*Status: Exploratory Phase*

## 1. The Core Dilemma & The "Killer Feature"
If Prep is a local-first application, charging $15/seat/month simply for centralized billing feels like a "SaaS tax." To justify a monthly recurring subscription, the Team tier must solve a painful, expensive problem for engineering teams.

**The Problem:** The 10-stage trace enrichment pipeline is computationally heavy. If a 10-person team is working on the same repository, having 10 developers locally run the LLM pipeline over the same `main` branch is a massive waste of local GPU time and battery life.

**The Solution (The Killer Feature):** **Shared Remote Indexing.** 
Compute the index once centrally, store the artifacts, and let the developers' local Prep clients download the pre-computed index. Their local machines only compute the *deltas* (their uncommitted branch changes).

This transforms the Team tier from "administrative convenience" into **"Zero-overhead AI context for the whole team."** This justifies $15/seat/mo easily.

---

## 2. Infrastructure: "Bring Your Own Compute" (BYOC)
*Constraint: Prep does not want to resell or host servers. We want to provide the software, and the customer pays their own infra bill.*

How do we give teams a "headless, on-demand" server that doesn't need to be manually turned on and off? 

### The Answer: Serverless GPU Platforms
Services like **Modal (modal.com)**, **RunPod Serverless**, and **Baseten** provide exactly this. 
- You write a Python script/Docker container.
- They host it. It scales to zero when not in use (costing $0.00).
- When a web request hits the endpoint, it spins up an A4000/A100 GPU in milliseconds, runs the workload, and shuts down.
- The customer pays per second of compute directly to RunPod/Modal.

### The Team Architecture (Small to Mid-Sized Teams)
1. **The Trigger:** A GitHub Action triggers on merges to the `main` branch.
2. **The Compute:** The Action hits the team's RunPod Serverless or Modal endpoint running the **Prep Headless Image**.
3. **The Work:** The Serverless GPU pulls the repo, runs the 10-stage Ollama/Qwen pipeline, and generates the index artifacts (`documents.json`, `embeddings.npy`, `trace_manifest.json`).
4. **The Storage:** The Serverless script uploads the artifacts to a cheap storage bucket (Amazon S3, Cloudflare R2, or GitHub Packages).
5. **The Client:** The developers' local Prep apps ping the S3 bucket every morning. If a new index exists, it downloads it instantly. The developer gets a fully enriched codebase without their laptop fans spinning up.

*Prep provides the RunPod Template and the GitHub Action. The team just deploys it.*

---

## 3. Scaling to Enterprise
Enterprises have strict data privacy constraints. They will not send their proprietary source code to RunPod or Modal. They want to run everything inside their own Virtual Private Cloud (VPC).

### The Enterprise Architecture (AWS / Azure)
The architecture remains identical, but the hosting providers change to enterprise-approved equivalents:
- **AWS:** Prep Headless runs on **AWS SageMaker** (Serverless Inference) or **AWS Batch**. Storage is an internal private S3 bucket.
- **Azure:** Prep Headless runs on **Azure Container Apps** (with GPU profiles) or **Azure Machine Learning**. Storage is Azure Blob.
- **Authentication:** Local clients authenticate with the internal bucket using SSO / AWS IAM credentials rather than simple API keys.

By building the feature to use generic object storage (S3 protocol) and containerized compute, the transition from "Team (RunPod + Cloudflare R2)" to "Enterprise (AWS EC2 + Private S3)" is just a matter of changing environment variables.

---

## 4. Revised Pricing Strategy Options

With this killer feature in mind, here are two viable ways to price the Team tier:

### Option A: The "Compute Savior" Subscription (SaaS)
- **Individual Pro:** $79 one-time (or $7/mo).
- **Team Tier:** $15 / seat / month.
- **Why it works:** You are selling massive time savings and battery life. "Don't run local LLMs for the whole repo. Sync from your team's CI/CD." At $15/mo, a manager will gladly pay to keep their developers' laptops fast and unburdened.
- **Deliverables needed:** Serverless GPU templates, GitHub Actions, S3 sync logic in the desktop client.

### Option B: The "Anti-SaaS" Annual License
- **Individual Pro:** $79 one-time.
- **Team Tier:** $149 / seat / year (or $149 perpetual with 1 year of updates).
- **Why it works:** Fits perfectly with the "Own your tools" ethos. Eliminates the SaaS feeling entirely while still commanding a B2B premium.
- **Deliverables needed:** Same as above, but marketed as an infrastructure toolkit they buy from you and run themselves.

---

## 5. Next Steps for Exploration

1. **Investigate Modal vs RunPod Serverless:** Build a quick proof-of-concept Docker container that runs the Prep Python pipeline + Ollama headless, and see how fast it boots on Modal or RunPod Serverless.
2. **Design the S3 Sync Protocol:** Outline how the local client merges a downloaded `trace_manifest.json` with local uncommitted file changes. (How does it know what to trust?)
3. **Draft the "Team Onboarding" UX:** How does an engineering manager distribute the S3 read credentials to their team securely? (e.g., via the `.runprep/team_config.json` file we planned).
