# Syncing Team Context (BYOC)

If you are on the **Team** or **Enterprise** tier, you can set up a headless indexing server so your developers never have to run local LLMs or burn CPU cycles to build the trace graph.

Your CI/CD pipeline builds the index once on every push to `main`. Every developer on your team downloads the pre-computed graph instantly. Their local CoDRAG only computes deltas for their uncommitted changes.

---

## How it works

1. **Build once:** A CI/CD job runs the CoDRAG headless image after every merge to `main`. It produces the full 10-stage enriched trace graph.
2. **Store centrally:** The index artifacts are uploaded to an S3-compatible bucket (Cloudflare R2, AWS S3, MinIO, etc.).
3. **Sync locally:** Each developer's CoDRAG client checks the bucket on startup and downloads the latest index in seconds.
4. **Delta only:** When a developer edits files locally, CoDRAG enriches only those files using their local LLM or BYOK API key. The rest of the graph comes from the shared index.

Two Docker image variants are available:

| Image | Size | GPU | Use case |
|-------|------|-----|----------|
| `codrag/headless:cpu` | ~2-3 GB | No | GitHub Actions + BYOK (OpenAI/Anthropic) |
| `codrag/headless:gpu` | ~8-10 GB | Yes | RunPod, Modal, AWS SageMaker + local Ollama |

---

## Quick Start: CPU + BYOK (Zero Infrastructure)

The fastest way to get started. Runs directly inside a free GitHub Actions runner using your existing OpenAI or Anthropic API key. No GPU rental, no RunPod, no Modal.

### 1. Create a Storage Bucket

We recommend [Cloudflare R2](https://developers.cloudflare.com/r2/) (zero egress fees). AWS S3 or MinIO also work.

Create a bucket (e.g., `codrag-team-indexes`) and generate an Access Key pair with read/write permissions.

### 2. Add the GitHub Action

Copy the workflow template into your repository:

```yaml
# .github/workflows/codrag-sync.yml
name: "CoDRAG Team Sync"
on:
  push:
    branches: ["main"]  # Add other branches as needed

jobs:
  index:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/ericbintner/codrag-headless:cpu
    steps:
      - uses: actions/checkout@v4
      - name: Build & Upload Index
        env:
          CODRAG_S3_ENDPOINT: ${{ secrets.CODRAG_S3_ENDPOINT }}
          CODRAG_S3_BUCKET: ${{ secrets.CODRAG_S3_BUCKET }}
          CODRAG_S3_ACCESS_KEY: ${{ secrets.CODRAG_S3_ACCESS_KEY }}
          CODRAG_S3_SECRET_KEY: ${{ secrets.CODRAG_S3_SECRET_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          codrag sync-headless \
            --repo-path . \
            --branch "${{ github.ref_name }}" \
            --model-provider openai \
            --model-name gpt-4.1-mini \
            --embedder native
```

That's it. Every push to `main` will rebuild the index (incrementally — only changed files are re-processed) and upload it to your bucket.

### 3. Connect Your Team

Commit the sync configuration to your repository (credentials are **never** committed):

```json
// .codrag/team_config.json
{
  "sync": {
    "enabled": true,
    "s3_endpoint": "https://<account-id>.r2.cloudflarestorage.com",
    "s3_bucket": "codrag-team-indexes",
    "s3_prefix": "my-repo-name",
    "poll_interval_minutes": 30
  }
}
```

Each developer provides their S3 read credentials via one of:
- Environment variables: `CODRAG_S3_ACCESS_KEY` / `CODRAG_S3_SECRET_KEY`
- A gitignored file: `.codrag/.secrets`
- The OS keychain (prompted on first run)

When a developer opens the project, CoDRAG downloads the latest shared index automatically.

---

## Advanced: GPU + Local LLM (RunPod / Modal)

For teams with large codebases or strict privacy requirements. Runs the enrichment pipeline on a rented GPU using open-source models (Qwen3, DeepSeek). No code leaves your infrastructure.

### Option A: Modal (Easiest)

[Modal](https://modal.com) provides serverless GPU execution that scales to zero.

1. Install the Modal CLI: `pip install modal && modal setup`
2. Save your S3 credentials as a Modal Secret named `codrag-s3-creds`.
3. Deploy the adapter:
```bash
modal deploy deploy/modal/modal_adapter.py
```
4. Copy the webhook URL into your GitHub Action (replace the `run` step above with a `curl` call to the webhook).

### Option B: RunPod Serverless

[RunPod](https://runpod.io) provides cheap A4000/A100 GPUs on demand.

1. Build and push the RunPod image:
```bash
docker build -f deploy/runpod/Dockerfile.runpod -t my-org/codrag-runpod .
docker push my-org/codrag-runpod
```
2. Create a Serverless Endpoint in the RunPod dashboard using your image.
3. Set your S3 credentials as endpoint environment variables.
4. Add a webhook trigger in your GitHub Action.

### Cost comparison

For a 5,000-file codebase with 5 merges/day:

| Method | Per run | Monthly |
|--------|---------|---------|
| CPU + OpenAI (gpt-4.1-mini) | ~$8.00 | ~$1,200 |
| GPU + Qwen3 (RunPod A4000) | ~$0.60 | ~$90 |
| GPU incremental (typical PR) | ~$0.05 | ~$8 |

Most teams start with CPU + BYOK for simplicity, then migrate to GPU as their codebase grows and API costs spike.

---

## Enterprise: AWS / Azure (VPC)

For organizations that require air-gapped deployment inside their own cloud infrastructure.

The `codrag/headless:gpu` image runs on any container orchestrator with GPU support:

```bash
# AWS ECS / Fargate
docker run --gpus all \
  codrag/headless:gpu \
  sync-headless \
    --repo-path /mnt/repo \
    --model-provider local \
    --model-name qwen3:8b
```

- **AWS:** Use ECS with GPU task definitions or SageMaker Processing Jobs. Storage: internal S3 with IAM role auth (no static keys).
- **Azure:** Use Azure Container Apps with GPU profiles or Azure ML. Storage: Azure Blob.
- **GitLab / Jenkins:** Use the same Docker image in your existing CI/CD pipelines.

A reference AWS ECS task definition is provided at `deploy/aws/ecs-task-definition.json`.

---

## How local deltas work

When a developer edits a file that exists in the shared index, CoDRAG automatically:

1. Detects the change via the local file watcher.
2. Enriches only that file using the developer's local LLM or BYOK key.
3. At query time, the local delta takes priority over the shared version (the stale remote entry is masked).
4. When the developer's changes are merged into `main` and the shared index is rebuilt, the local delta is automatically discarded.

This means every developer always has the most up-to-date context: the team's shared graph plus their own uncommitted work.

---

## FAQ

**How often does the local client check for updates?**
On daemon startup, on manual "Sync Now" button press, and on a configurable polling interval (default: every 30 minutes).

**Does every push trigger a full rebuild?**
No. By default, `sync-headless` runs in incremental mode. It compares the existing index manifest against the current repo state and only re-processes changed, added, or deleted files. Pass `--full` to force a complete rebuild.

**Which branches can I sync?**
Any branch. Configure the `branches` list in your GitHub Action. Each branch gets its own S3 prefix automatically.

**What if my repo is private?**
The headless container supports Git clone via `$GIT_TOKEN` (HTTPS) or `$SSH_KEY` (SSH). In GitHub Actions, the `actions/checkout` step handles this automatically.

**Do I need a GPU?**
No. The `:cpu` image uses CoDRAG's built-in ONNX embedder (runs on CPU) and sends LLM reasoning to a cloud API (OpenAI, Anthropic, etc.). A GPU is only needed if you want to run models locally for privacy or cost reasons.
