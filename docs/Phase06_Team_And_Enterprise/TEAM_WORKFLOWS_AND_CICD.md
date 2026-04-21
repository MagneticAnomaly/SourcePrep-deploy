# Team Workflows, CI/CD, and Local Constraints

*Status: Architecture & Workflow Design*
*Focus: How CoDRAG fits into a multi-developer team environment.*

## 1. The "Heavy Cloud, Light Local" Workflow

The fundamental problem CoDRAG Teams solves is the compute burden. A high-quality trace graph requires deep epistemic enrichment (Stage 5) and group reasoning (Stage 6), which demand large models (35B+ parameters or Claude-tier reasoning). 
**Most developers do not have 32GB+ RAM laptops.**

Therefore, the team workflow must shift the heavy lifting to the cloud/CI, leaving only lightweight tasks for the local machine.

### The Pipeline Split

CoDRAG's 8-stage pipeline naturally splits between CI/CD and Local Developer environments:

**Executed in CI/CD (The "Heavy" Sync):**
1. **Structural Graph:** Parsed from AST.
2. **Fast Catalogue:** Initial indexing.
3. **Relationship Validation:** Edge validation.
4. **Knowledge Embedding:** Vectorizing the codebase.
5. **Epistemic Enrichment:** (Heavy LLM) - Generates documentation, tech debt analysis.
6. **Cluster Synthesis:** (Heavy LLM) - Group reasoning and module identification.
7. **Continuous Deepening:** Iterative graph refinement.
8. **Deep Knowledge Embedding:** Vectorizing the enriched data.

**Executed Locally (The "Light" Delta):**
- **Download:** The developer's desktop app downloads the pre-built artifacts (SQLite, JSONL, embeddings) from S3/R2 on startup.
- **Delta Watcher:** As the developer edits files, the local CoDRAG daemon only processes the *changed* files.
- **Local Model Usage:** Because it's only processing 1-5 files at a time, the local machine can use a small, fast model (e.g., `qwen3.5:9b`, or `qwen-coder-next`) or simply route to a cloud API for those few files. The heavy batch processing of 1,000+ files was already done in CI.

## 2. Who Picks the Model? (Configuration Governance)

In a Team or Enterprise setting, configuration cannot be an anarchic free-for-all.

### The Team Lead (Admin)
The Team Lead configures the `.prep/team_config.json` file, which is committed to the repository. This file dictates:
- The S3 bucket for downloading the shared index.
- **CI/CD Model Mandates:** Which model is used for the heavy CI build (e.g., `claude-3-5-sonnet-20241022`).
- **Prompt Standards:** Custom instructions or specific context rules for the team's codebase.

### The Local Developer (User)
The developer's local CoDRAG app respects the team configuration but retains flexibility for their local environment:
- **Local API Key / Local Hardware:** The developer configures their own local `ComputeNode`. If they have a Mac Studio, they might map their local delta processing to a local 35B model. If they have a basic MacBook Air, they might map it to an Anthropic API key provided by the company.
- **Restriction:** They cannot change the architecture of the shared remote index; they only control how their local app calculates deltas and handles search queries.

## 3. Implementing the CI/CD Sync Strategy

How does a startup or mid-market software company actually implement this?

### Scenario A: The Modern Startup (Vercel/Next.js/GitHub)
- **Code Host:** GitHub
- **Compute:** GitHub Actions (Ubuntu runners, CPU only).
- **AI Provider:** Anthropic API (Claude 3.5 Sonnet).
- **Storage:** Cloudflare R2 (S3 compatible, zero egress fees).
- **Workflow:** 
  1. PR merged to `main`.
  2. GitHub Action runs `ghcr.io/ericbintner/codrag-headless:cpu`.
  3. Action passes `ANTHROPIC_API_KEY` via GitHub Secrets.
  4. CoDRAG processes the diff, updates the graph using Claude, and pushes to R2.
  5. Devs pull from R2 automatically via the CoDRAG desktop app.

### Scenario B: The Regulated Enterprise (On-Prem / VPC)
- **Code Host:** GitLab Self-Managed.
- **Compute:** AWS ECS (with GPU instances) or internal Kubernetes cluster.
- **AI Provider:** Local Open-Weight (Qwen 35b) or AWS Bedrock (Claude 3.5 Sonnet).
- **Storage:** Internal AWS S3 Bucket.
- **Workflow:** 
  1. Merge to `develop`.
  2. GitLab CI triggers an ECS task running `codrag-headless:gpu`.
  3. Task runs local Ollama or calls Bedrock entirely within the VPC.
  4. Pushes artifacts to S3.
  5. Developers' laptops (on corporate VPN) pull the index from S3.

## 4. Re-evaluating RunPod / Modal for Teams

**RunPod Serverless & Modal are still highly relevant, but as niche solutions:**
- They are perfect for **AI-native startups** who already use Modal/RunPod for their own products and prefer to keep all compute there.
- They are great for companies that want the privacy of open-weight models but don't want to manage persistent GPU VMs on AWS.
- However, they should **not** be the *default* recommendation for standard web/software businesses. The default path of least resistance for a SaaS business is using a CPU CI runner + an Anthropic/OpenAI API key.

## 5. Conclusion & Actionable Next Steps

To properly support B2B teams:
1. **Promote the CPU + API Workflow:** Update deployment documentation to feature the GitHub Actions + Claude/OpenAI workflow as the "Golden Path" for Teams.
2. **De-emphasize local 35B requirements:** Explicitly market that CoDRAG Team Sync means developers can use CoDRAG on 16GB laptops because the CI server does the 35B/Claude heavy lifting.
3. **API Key Management:** Ensure the AI Gateway in the CoDRAG UI easily allows Team users to input a corporate API key just for their local delta computations, bypassing local VRAM limits entirely.
