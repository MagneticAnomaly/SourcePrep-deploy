"""
CoDRAG Team Sync — Modal.com Adapter

Deploys the CoDRAG headless indexer as a serverless GPU function on Modal.
Scales to zero when idle (costs $0.00). Wakes up in <1 second when triggered.

Setup:
  1. pip install modal
  2. modal setup
  3. Create a Modal Secret named "codrag-s3-creds" with your S3 credentials:
       CODRAG_S3_ENDPOINT, CODRAG_S3_BUCKET, CODRAG_S3_ACCESS_KEY, CODRAG_S3_SECRET_KEY
  4. modal deploy modal/modal_adapter.py
  5. Copy the webhook URL into your GitHub Action.

Trigger (from GitHub Actions or curl):
  curl -X POST https://your-modal-url.modal.run \
    -H "Content-Type: application/json" \
    -d '{"repo_url": "https://github.com/org/repo", "branch": "main"}'
"""

import modal

# ── Image: pull the pre-built CoDRAG GPU image from GHCR ─────
codrag_image = modal.Image.from_registry(
    "ghcr.io/ericbintner/codrag-headless:gpu",
    add_python="3.11",
)

app = modal.App("codrag-team-sync")


@app.function(
    image=codrag_image,
    gpu="A10G",  # Change to "A100" for larger repos, or "T4" for budget
    timeout=7200,  # 2 hour max (adjust for repo size)
    secrets=[modal.Secret.from_name("codrag-s3-creds")],
)
@modal.web_endpoint(method="POST")
def trigger_sync(payload: dict):
    """Webhook endpoint: triggers a headless index build."""
    import subprocess
    import os

    repo_url = payload.get("repo_url", "")
    branch = payload.get("branch", "main")
    model_provider = payload.get("model_provider", "local")
    model_name = payload.get("model_name", "qwen3:4b")
    full = payload.get("full", False)

    if not repo_url:
        return {"status": "error", "message": "repo_url is required"}

    cmd = [
        "codrag", "sync-headless",
        "--repo-url", repo_url,
        "--branch", branch,
        "--model-provider", model_provider,
        "--model-name", model_name,
        "--embedder", "native",
    ]

    if full:
        cmd.append("--full")

    # S3 credentials are injected via Modal Secrets as env vars
    print(f"[codrag-modal] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

    if result.returncode != 0:
        return {
            "status": "error",
            "returncode": result.returncode,
            "stderr": result.stderr[-2000:],
        }

    return {
        "status": "success",
        "repo": repo_url,
        "branch": branch,
        "stdout_tail": result.stdout[-500:],
    }
