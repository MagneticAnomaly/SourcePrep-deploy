<p align="center">
  <img src="prep-github-header.png" alt="RunPrep" width="100%">
</p>

# RunPrep Deploy — Headless Team Sync Templates

Deploy RunPrep's headless indexer to your CI/CD pipeline so your team shares a single, pre-built trace graph. Developers download it instantly instead of running LLMs locally.

## Quick Decision Tree

```
Do you want to run LLMs locally/self-hosted (private, cheap)?
├── Yes → Use the GPU image + RunPod or Modal
│         See: runpod/ or modal/
└── No  → Use the CPU image + your OpenAI/Anthropic key
          See: github-actions/ (runs directly in Actions runner)

Is your codebase in a private VPC?
├── Yes → Use the GPU image on AWS ECS or Azure
│         See: aws/
└── No  → Use RunPod or Modal (easiest)
```

## Directory Structure

```
prep-deploy/
├── Dockerfile.cpu          # Slim image: ONNX embeddings + BYOK LLM (~2-3 GB)
├── Dockerfile.gpu          # Fat image: + Ollama + Qwen3:4b baked in (~8-10 GB)
├── github-actions/         # Reusable workflow for CI/CD trigger
│   └── prep-sync.yml
├── modal/                  # Modal.com serverless GPU adapter
│   └── modal_adapter.py
├── runpod/                 # RunPod Serverless adapter
│   ├── Dockerfile.runpod
│   └── runpod_handler.py
└── aws/                    # AWS ECS/Fargate reference
    └── ecs-task-definition.json
```

## How It Works

1. **On push to `main`:** Your CI/CD runs `prep sync-headless` inside the headless Docker image.
2. **The image:** Clones your repo, runs the 10-stage enrichment pipeline, and uploads the index artifacts to your S3-compatible bucket.
3. **Your team:** Each developer's local RunPrep client downloads the index on startup. They only compute deltas for their uncommitted changes.

## Prerequisites

- A **RunPrep Team** or **Enterprise** license.
- An S3-compatible storage bucket (Cloudflare R2, AWS S3, MinIO, Backblaze B2).
- One of:
  - An OpenAI/Anthropic API key (for CPU+BYOK mode), or
  - A RunPod/Modal account (for GPU+local LLM mode).

## Image Tags

| Tag | Size | GPU | Use Case |
|-----|------|-----|----------|
| `ghcr.io/ericbintner/prep-headless:cpu` | ~2-3 GB | No | GitHub Actions + BYOK |
| `ghcr.io/ericbintner/prep-headless:gpu` | ~8-10 GB | Yes | RunPod, Modal, AWS + local Ollama |

## Security

- **Never commit S3 credentials to Git.** Use GitHub Secrets, Modal Secrets, or RunPod environment variables.
- The `.runprep/team_config.json` file (committed to your repo) contains only the bucket endpoint, name, and prefix — no secrets.
- Each developer provides read credentials via environment variables, a gitignored `.runprep/.secrets` file, or OS keychain.

## Links

- [Team Sync Guide](https://docs.runprep.io/guides/team-sync) — Full setup walkthrough
- [Enterprise Deployment Guide](https://docs.runprep.io/guides/enterprise-deploy) — Air-gapped, VPC, serverless GPU
- [RunPrep](https://runprep.io) — Main product page
- [Pricing](https://runprep.io/pricing) — Team & Enterprise plans
