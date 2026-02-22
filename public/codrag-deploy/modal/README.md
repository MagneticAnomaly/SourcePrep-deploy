# CoDRAG Team Sync — Modal Adapter

Deploy the CoDRAG headless indexer as a serverless GPU function on [Modal](https://modal.com). Scales to zero when idle. Wakes up in under a second when triggered.

## Setup

1. **Install Modal CLI:**
   ```bash
   pip install modal
   modal setup
   ```

2. **Create a Modal Secret** named `codrag-s3-creds` with your S3 credentials:
   - `CODRAG_S3_ENDPOINT` — Your S3-compatible endpoint URL
   - `CODRAG_S3_BUCKET` — Bucket name
   - `CODRAG_S3_ACCESS_KEY` — Write access key
   - `CODRAG_S3_SECRET_KEY` — Write secret key

3. **Deploy:**
   ```bash
   modal deploy modal/modal_adapter.py
   ```

4. **Copy the webhook URL** into your GitHub Action (see `../github-actions/`).

## Trigger

```bash
curl -X POST https://your-app--codrag-team-sync-trigger-sync.modal.run \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo", "branch": "main"}'
```

## Configuration

You can override defaults in the webhook payload:

| Field | Default | Description |
|-------|---------|-------------|
| `repo_url` | (required) | HTTPS URL of your repository |
| `branch` | `main` | Branch to index |
| `model_provider` | `local` | `local` (Ollama) or `openai`/`anthropic` |
| `model_name` | `qwen3:4b` | Model to use for enrichment |
| `full` | `false` | Force full rebuild (skip incremental) |

## GPU Selection

Edit `modal_adapter.py` to change the GPU type:
- `"T4"` — Budget ($0.10/hr)
- `"A10G"` — Default, good balance ($0.30/hr)
- `"A100"` — Large repos ($1.10/hr)
