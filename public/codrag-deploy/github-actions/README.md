# CoDRAG Team Sync — GitHub Actions Template

A reusable GitHub Actions workflow that triggers CoDRAG headless index builds on every push to `main`.

## Setup

1. **Copy the workflow** into your repository:
   ```bash
   mkdir -p .github/workflows
   cp codrag-sync.yml .github/workflows/
   ```

2. **Add secrets** in your repo settings (Settings → Secrets → Actions):

   **Required (S3 storage):**
   - `CODRAG_S3_ENDPOINT` — Your S3-compatible endpoint URL
   - `CODRAG_S3_BUCKET` — Bucket name
   - `CODRAG_S3_ACCESS_KEY` — Write access key
   - `CODRAG_S3_SECRET_KEY` — Write secret key

   **For CPU+BYOK mode (default):**
   - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

   **For GPU webhook mode:**
   - `CODRAG_GPU_WEBHOOK_URL` — Your RunPod/Modal endpoint URL
   - `CODRAG_GPU_WEBHOOK_SECRET` — Auth token for the webhook

3. **Choose mode** via repository variable (Settings → Variables → Actions):
   - `CODRAG_SYNC_MODE` = `cpu` (default) or `gpu`

## How It Works

- **CPU mode:** Runs `codrag sync-headless` directly inside the GitHub Actions runner using the `:cpu` Docker image. Uses your OpenAI/Anthropic key for LLM reasoning. Free CI/CD minutes.
- **GPU mode:** Sends a webhook to your RunPod/Modal endpoint, which runs the build on a rented GPU with local Ollama.

Both modes are incremental by default — only changed files are re-indexed.
