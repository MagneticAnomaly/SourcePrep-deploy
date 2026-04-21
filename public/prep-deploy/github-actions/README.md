# Prep Team Sync — GitHub Actions Template

A reusable GitHub Actions workflow that triggers Prep headless index builds on every push to `main`.

## Setup

1. **Copy the workflow** into your repository:
   ```bash
   mkdir -p .github/workflows
   cp prep-sync.yml .github/workflows/
   ```

2. **Add secrets** in your repo settings (Settings → Secrets → Actions):

   **Required (S3 storage):**
   - `PREP_S3_ENDPOINT` — Your S3-compatible endpoint URL
   - `PREP_S3_BUCKET` — Bucket name
   - `PREP_S3_ACCESS_KEY` — Write access key
   - `PREP_S3_SECRET_KEY` — Write secret key

   **For CPU+BYOK mode (default):**
   - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

   **For GPU webhook mode:**
   - `PREP_GPU_WEBHOOK_URL` — Your RunPod/Modal endpoint URL
   - `PREP_GPU_WEBHOOK_SECRET` — Auth token for the webhook

3. **Choose mode** via repository variable (Settings → Variables → Actions):
   - `PREP_SYNC_MODE` = `cpu` (default) or `gpu`

## How It Works

- **CPU mode:** Runs `prep sync-headless` directly inside the GitHub Actions runner using the `:cpu` Docker image. Uses your OpenAI/Anthropic key for LLM reasoning. Free CI/CD minutes.
- **GPU mode:** Sends a webhook to your RunPod/Modal endpoint, which runs the build on a rented GPU with local Ollama.

Both modes are incremental by default — only changed files are re-indexed.
