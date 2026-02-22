"""
CoDRAG Team Sync — RunPod Serverless Handler

Listens to the RunPod job queue and triggers headless index builds.
The handler parses job input and calls `codrag sync-headless`.

Environment variables (set in RunPod Endpoint settings):
  CODRAG_S3_ENDPOINT, CODRAG_S3_BUCKET, CODRAG_S3_ACCESS_KEY, CODRAG_S3_SECRET_KEY
"""

import subprocess
import runpod


def handler(job):
    """RunPod serverless handler — called for each job in the queue."""
    job_input = job.get("input", {})

    repo_url = job_input.get("repo_url", "")
    branch = job_input.get("branch", "main")
    model_provider = job_input.get("model_provider", "local")
    model_name = job_input.get("model_name", "qwen3:4b")
    full = job_input.get("full", False)

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

    print(f"[codrag-runpod] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=7200,  # 2 hour max
    )

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


runpod.serverless.start({"handler": handler})
