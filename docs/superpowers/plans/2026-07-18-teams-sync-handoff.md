# SourcePrep Teams Sync - Engineering Handoff

**Date**: July 18, 2026
**Feature**: Teams Sync (Phase 2)
**Objective**: Build a shared index distribution system to prevent redundant local compute for teams.

## 1. Executive Summary

Currently, SourcePrep relies entirely on local compute. Every developer runs the full enrichment pipeline (embeddings, graph analysis, structural paths) on their own machine. This is great for privacy but wastes immense compute when a team of 50 developers all pull `main` and independently re-enrich the exact same commits.

**Teams Sync** solves this by centralizing the heavy lifting: the trace graph and embeddings are built *once* in a headless environment and distributed to the team via S3. Developers then only compute deltas (uncommitted changes) locally.

## 2. Architecture Overview

The Teams Sync feature consists of four major components:

1. **GitHub Webhook Listener**: Triggers the indexing process when code is pushed to a tracked branch (e.g., `main`).
2. **Headless Indexer (Cloud Worker)**: A headless version of the SourcePrep daemon (packaged as a Docker image) that clones the repository, runs the full enrichment pipeline, and outputs metadata artifacts.
3. **Artifact Storage (S3-Compatible)**: The central repository for generated index artifacts. Supports AWS S3, Cloudflare R2 (zero egress), and MinIO.
4. **Local Daemon Sync**: The client-side logic in the developer's local SourcePrep installation that downloads the index, merges it with local uncommitted changes, and serves it to agents.

## 3. Component Details & Requirements

### 3.1. Headless Indexer (CI/CD or Cloud Worker)
We need to provide a Docker image that can be run in GitHub Actions, GitLab CI, or as a standalone cloud worker.
- **Input**: Repository URL, Git Commit Hash, SourcePrep License Key, S3 Credentials.
- **Process**:
  1. Clone the repository at the specific commit hash.
  2. Run the standard SourcePrep enrichment pipeline (parse ASTs, generate embeddings, build graph).
  3. Package the resulting sqlite/vector databases into a compressed tarball or chunked format.
  4. Upload to the S3 bucket using the commit hash as the primary key.
  5. Delete the cloned source code from the worker.
- **Requirements**: Must be able to run without a GUI and without user interaction.

### 3.2. Artifact Storage (S3 Layer)
The storage layer must be dumb and cheap. We don't need a complex backend database; S3 is sufficient.
- **Path Structure**: `s3://[bucket-name]/[project-id]/[branch-name]/[commit-hash].tar.zst`
- **Manifests**: Maintain a `latest.json` pointer at the branch root so clients know what the most recent fully-indexed commit is.
- **Security**: For Teams, we host the worker and bucket. For Enterprise, this bucket lives inside the customer's VPC. 

### 3.3. Local Daemon Sync Logic
This is the most complex piece of the feature. The local daemon must seamlessly merge remote state with local state.
- **Startup / Git Pull**: When the daemon detects a change in the local git HEAD, it checks if it already has the index for that hash.
- **Fetch**: If not, it pings the S3 bucket (or our proxy API) to download the pre-computed index for that commit.
- **Delta Enrichment**: Once the remote index is loaded, the daemon must run a fast `git diff` to see what the developer has changed locally (uncommitted or unpushed commits) and *only* run the enrichment pipeline on those specific files.
- **In-Memory Merging**: The semantic search and graph queries must be able to query the downloaded base index *plus* the local delta index simultaneously.

## 4. Implementation Phasing

**Phase A: The Headless Indexer**
1. Modify the core pipeline to support a `--headless` CLI flag.
2. Build the Docker image containing the necessary ONNX runtime and Python dependencies.
3. Implement the S3 upload utility.

**Phase B: The Local Client Fetcher**
1. Add configuration UI in the dashboard for developers to connect to a Team (authenticating with the Team's API key).
2. Implement the background fetcher that polls/downloads the `[commit-hash].tar.zst` artifact.
3. Build the index swapping logic to replace the local database with the downloaded one safely without locking the UI.

**Phase C: Delta Merging**
1. Refactor the graph database layer to support a "Base Graph" (read-only from remote) and an "Overlay Graph" (read-write for local changes).
2. Ensure search queries transparently search both and deduplicate.

## 5. Security & Enterprise Considerations

- **Code Privacy**: Source code is NEVER uploaded to the S3 bucket. Only embeddings, AST structures, and metadata graphs are uploaded.
- **Enterprise Air-Gap**: The architecture must support the customer swapping out our S3 bucket for their own internal MinIO instance, and running the Headless Indexer on their own internal GitLab CI. This is the primary justification for the $30/seat Enterprise tier.
