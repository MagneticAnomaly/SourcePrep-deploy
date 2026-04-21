# Headless Serverless Architecture (BYOC)

*Drafted: February 2026*
*Status: Exploratory*

## The "Bring Your Own Compute" (BYOC) Model
To avoid reselling compute or acting as a SaaS host, CoDRAG will provide **infrastructure templates**. Teams deploy these templates to their own accounts on serverless GPU providers. 

The goal: **Zero-maintenance, scale-to-zero, on-demand indexing.**

## Why Serverless GPUs?
You asked if providers have a service where you don't have to "turn it on and off." **Yes, they do.**

1. **RunPod Serverless:** You define a Docker container (our `codrag-headless` image). RunPod gives you an API endpoint. When the endpoint is hit, RunPod wakes up an A4000 GPU in ~2-5 seconds, runs the task, and shuts it down. You only pay for the exact seconds the GPU was running.
2. **Modal (modal.com):** Extremely developer-friendly. You write Python code, and Modal handles containerization and serverless GPU execution automatically. Scales to 0. Boot times are usually sub-second.
3. **Baseten / Replicate:** Similar serverless AI inference platforms, but RunPod and Modal are better suited for long-running batch jobs (like indexing a repo).

## The Proposed Workflow (The "Team" Sync)

Here is how a Team would actually use this in practice:

### 1. The Setup (Done once by the Team Lead)
- The team lead creates a RunPod account and an S3 bucket (e.g., Cloudflare R2, which has zero egress fees).
- They deploy the **CoDRAG RunPod Template** (one click).
- They add a GitHub Action to their repo.
- They commit the S3 endpoint/bucket/prefix to `.prep/team_config.json` (credentials are distributed via env vars or a gitignored `.prep/.secrets` file — **never committed to Git**).

### 2. The Trigger (CI/CD)
- A developer merges a PR into the `main` branch.
- The GitHub Action fires. It sends a webhook to the RunPod Serverless endpoint.

### 3. The Compute (RunPod Serverless)
- RunPod spins up an A4000 GPU.
- The `codrag-headless` container pulls the latest `main` branch.
- It runs the 10-stage Trace Enrichment pipeline (using the built-in ONNX models or Qwen3).
- It generates the dense graph artifacts: `documents.json`, `embeddings.npy`, `trace_manifest.json`, and `atlas_routing.json`.
- It zips these files and uploads them to the team's S3/R2 bucket.
- The GPU shuts down. *Total cost for a full run: ~$0.60. Incremental runs (only changed files): ~$0.05.*

### 4. The Sync (Local Developers)
- The next morning, a developer opens VS Code.
- Their local CoDRAG app sees the `.prep/team_config.json` and checks the S3 bucket.
- It downloads the fresh index zip, extracting it in milliseconds.
- **Result:** The developer has a fully enriched trace graph of the entire repository without their laptop ever spinning up a fan.

## Scaling to Enterprise
When you are ready to sell to Enterprise, the architecture is fundamentally identical, just shifted to corporate boundaries:
- Instead of RunPod, they deploy a container to **AWS SageMaker Serverless** or **AWS ECS**.
- Instead of Cloudflare R2, they use their internal **AWS S3 VPC endpoints**.
- Instead of GitHub Actions, they use **GitLab CI** or **Jenkins**.
- CoDRAG just needs to support standard S3 protocols and provide standard Docker containers.

## Pairing this with Pricing Options

By offering this BYOC architecture, you justify the Team Tier pricing.
- **If you do $15/seat/month:** The pitch is "We provide the sync infrastructure, the CI/CD runners, and the headless daemon to keep your team's laptops fast."
- **If you do $149/seat/year (Anti-SaaS):** The pitch is "Buy the Team software, deploy our RunPod template, and own your infrastructure. No SaaS subscriptions." (This pairs extremely well with the "Own your tools" philosophy).

## Next Development Steps for this Track
1. Build `codrag-headless` Dockerfile.
2. Build a simple `codrag sync --upload s3://...` and `codrag sync --download s3://...` CLI command.
3. Write a Terraform/RunPod template.
