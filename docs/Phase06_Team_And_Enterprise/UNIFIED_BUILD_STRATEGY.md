# Unified Headless Build Strategy: Core + Adapters

*Status: Exploratory & Planned for Phase 06*

To support RunPod, Modal, and custom Enterprise environments (AWS/Azure) without maintaining completely separate codebases, CoDRAG will use a **"Core + Adapter"** architecture. 

We will build **one single base Docker image**. The different deployment targets simply provide a tiny wrapper (an "adapter") that tells the provider how to trigger the image.

## 1. The Single Base Build: `codrag/headless:latest`
This is a standard, heavyweight Docker container that contains everything needed to index a repository offline.

**Contents of the Base Image:**
- Ubuntu 22.04 base (Alpine is incompatible with numpy/onnxruntime due to musl libc).
- Python 3.11+ and the `codrag` Python package.
- Compiled Rust binaries (`codrag-engine`, `codrag-parser`).
- Pre-downloaded ONNX embedding models (e.g., `nomic-embed-text-v1.5`).
- S3 synchronization utilities (via `boto3` or `minio` Python SDK).
- Git CLI (for cloning private repos via token or SSH key injection).

**Image Size Tiers:**
The base image will be large. Two tags are planned:
- `codrag/headless:cpu` (~2–3 GB) — ONNX embeddings + BYOK LLM support only. No Ollama, no GPU libs. Runs on free CI/CD runners.
- `codrag/headless:gpu` (~8–10 GB) — Everything in `cpu`, plus Ollama runtime + pre-baked Qwen3:4b model weights. For RunPod/Modal/SageMaker GPU deployments.

Baking the model into the image avoids a 5GB download on every serverless cold start.

**The Core CLI Command:**
The container exposes a primary command designed for batch processing:
```bash
codrag sync-headless \
  --repo-url "https://github.com/org/repo" \
  --branch "main" \
  --s3-bucket "s3://my-team-bucket" \
  --s3-prefix "indexes/repo-name" \
  --s3-endpoint "https://..." \
  --s3-access-key "$AWS_ACCESS_KEY_ID" \
  --s3-secret-key "$AWS_SECRET_ACCESS_KEY"
```
This command clones the repo (using `$GIT_TOKEN` or `$SSH_KEY` for private repos), runs the 10-stage pipeline, zips the artifacts (`documents.json`, `embeddings.npy`, `trace_manifest.json`), and uploads them.

**Incremental mode (default):** If a previous index exists in the S3 bucket, the CLI downloads it first, compares the `trace_manifest.json` against the current repo state, and only re-indexes changed/added files. This reduces a 2-hour full build to ~5 minutes for typical PRs.

**Full rebuild:** Pass `--full` to force a complete re-index from scratch.

---

## 2. The Platform Adapters

Because the entire logic is self-contained in the Base Image and CLI, the platform-specific code is reduced to fewer than 50 lines per provider.

### Adapter A: Modal (`modal.com`)
Modal can import custom Docker registries directly. We don't even need to publish a separate Modal app package. The customer runs a simple Python script using the Modal client.

```python
# modal_adapter.py
import modal

# 1. Use the unified base build
image = modal.Image.from_registry("codrag/headless:latest")
app = modal.App("codrag-team-sync")

# 2. Define the webhook trigger
@app.function(image=image, gpu="A10G", secrets=[modal.Secret.from_name("codrag-s3-creds")])
@modal.web_endpoint(method="POST")
def trigger_index(payload: dict):
    import subprocess
    # 3. Call the core CLI
    subprocess.run([
        "codrag", "sync-headless", 
        "--repo-url", payload["repo_url"],
        "--s3-bucket", "codrag-indexes"
    ], check=True)
    return {"status": "success"}
```

### Adapter B: RunPod Serverless
RunPod requires the Docker container to run a specific Python handler that listens to their internal job queue. We simply `COPY` a tiny handler script into the base image to create a RunPod-specific tag.

```dockerfile
# Dockerfile.runpod
FROM codrag/headless:latest
RUN pip install runpod
COPY runpod_handler.py /handler.py
CMD ["python", "-u", "/handler.py"]
```
The `runpod_handler.py` simply parses the job input and calls the same `subprocess.run(["codrag", "sync-headless", ...])` command.

### Adapter C: Enterprise (AWS / Azure)
Enterprises don't need an adapter script. They have their own orchestration tools (AWS ECS, Kubernetes Jobs, GitLab CI runners).
They simply pull `codrag/headless:latest`, inject their IAM roles or environment variables, and run the `codrag sync-headless` command directly as a batch job.

---

## 3. The Implementation Plan (Phase 06)

**Step 1: The Headless CLI**
- Add the `sync-headless` command to `src/codrag/cli.py`.
- Implement `S3StorageProvider` for uploading/downloading zipped indexes.

**Step 2: The Base Image CI/CD**
- Add a GitHub Action to the CoDRAG repo that builds `codrag/headless:latest`.
- Push it to a public registry (Docker Hub or GitHub Container Registry).

**Step 3: The Adapters & Templates**
- Create a `deploy/` directory in the CoDRAG repository.
- Add `deploy/modal/modal_adapter.py`.
- Add `deploy/runpod/Dockerfile.runpod` and `runpod_handler.py`.
- Add `deploy/aws/ecs-task-definition.json`.

**Step 4: The Local Client Sync**
- Update the local CoDRAG daemon to check `.codrag/team_config.json` for an S3 endpoint.
- If present, on startup, hit S3. If a newer index exists, download, unzip, and replace `.codrag/index/`.
