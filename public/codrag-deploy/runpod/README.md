# CoDRAG Team Sync — RunPod Serverless Adapter

Deploy the CoDRAG headless indexer as a serverless endpoint on [RunPod](https://runpod.io). The GPU spins up only when triggered, and shuts down automatically after the job completes.

## Setup

1. **Build and push the image:**
   ```bash
   cd codrag-deploy/
   docker build -f runpod/Dockerfile.runpod -t my-org/codrag-runpod .
   docker push my-org/codrag-runpod
   ```

2. **Create a RunPod Serverless Endpoint:**
   - Go to [RunPod Console → Serverless](https://www.runpod.io/console/serverless)
   - Click "New Endpoint"
   - Select your pushed image (`my-org/codrag-runpod`)
   - Choose a GPU type (A4000 recommended for most repos)
   - Set Max Workers to 1 (unless you need parallel builds)

3. **Set environment variables** in the endpoint settings:
   - `CODRAG_S3_ENDPOINT` — Your S3-compatible endpoint URL
   - `CODRAG_S3_BUCKET` — Bucket name
   - `CODRAG_S3_ACCESS_KEY` — Write access key
   - `CODRAG_S3_SECRET_KEY` — Write secret key

4. **Copy the Endpoint ID** and use it in your GitHub Action (see `../github-actions/`).

## Trigger

```bash
curl -X POST "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "repo_url": "https://github.com/org/repo",
      "branch": "main"
    }
  }'
```

## Job Input

| Field | Default | Description |
|-------|---------|-------------|
| `repo_url` | (required) | HTTPS URL of your repository |
| `branch` | `main` | Branch to index |
| `model_provider` | `local` | `local` (Ollama) or `openai`/`anthropic` |
| `model_name` | `qwen3:4b` | Model to use for enrichment |
| `full` | `false` | Force full rebuild (skip incremental) |

## GPU Selection

Choose based on repo size:
- **RTX A4000 (16 GB)** — Most repos. ~$0.30/hr.
- **RTX A5000 (24 GB)** — Large monorepos or bigger models. ~$0.40/hr.
- **A100 (80 GB)** — Massive repos + large models. ~$1.10/hr.
