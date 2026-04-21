# Research: Architecture of Shared Trace vs Local Knowledge Base

*Drafted: February 2026*
*Status: Exploratory Research*

If a team uses a headless server to build the index centrally, we must cleanly separate what is "team-owned" (the shared repository state) from what is "user-owned" (local branches, personal notes, external URLs).

This document outlines how the CoDRAG architecture handles the synchronization of shared remote state with highly specific local developer context.

---

## 1. The Core Problem: The Three Context Layers

A developer working on a CoDRAG-enabled project actually relies on three distinct layers of context:

1. **The Main Branch (Shared):** The massive, 10-stage enriched trace graph of the repository's `main` branch. This takes hours to build.
2. **The Local Delta (Personal):** The uncommitted files or feature-branch changes the developer is actively editing.
3. **The Knowledge Base (Personal):** External context the user has specifically selected in their CoDRAG dashboard tree (e.g., a Jira ticket URL, a PDF spec, a Slack thread, or a local `scratchpad.md` outside the repo).

If the headless server builds the index, how do we merge these layers without the server needing to manage multi-user states?

---

## 2. The Solution: Local Merge Architecture

The headless server **does not** manage multi-user versions of the RAG. The headless server is entirely "dumb" — it only knows about the Git repository `main` branch. 

All merging and scoping happen **locally on the user's computer.**

### Layer 1: The Headless Sync (The Heavy Lift)
- The headless CI/CD server runs on push to `main`.
- It builds the complete Trace Graph and Atlas Routing for `main`.
- It uploads `trace_manifest.json`, `documents.json`, and `embeddings.npy` to the team's S3 bucket.
- **The developer's local CoDRAG daemon downloads this zip and places it in `.prep/index/remote/`.**

### Layer 2: The Local Watcher (The Delta)
- The developer opens their IDE and starts editing `src/auth.ts`.
- The local CoDRAG file watcher detects the change.
- It compares the file against the remote `trace_manifest.json`.
- The local CoDRAG daemon uses the developer's *local* LLM (or BYOK API key) to run the enrichment pipeline **only on `src/auth.ts`**.
- It saves this delta to `.prep/index/local_deltas/`.
- *Compute cost: ~2 seconds of local GPU/API time, rather than 2 hours.*

### Layer 3: The Knowledge Base (The Personal Scope) *(Future Enhancement — not part of Phase 06 MVP)*
- The user selects "Add URL" in their CoDRAG tree and adds a Jira ticket.
- This is processed 100% locally and saved to `.prep/index/knowledge/`.
- The headless server is completely unaware of this.

> **Note:** Layer 3 is a future roadmap feature. Phase 06 MVP ships with Layers 1 and 2 only. The Knowledge Base layer is documented here for architectural completeness.

---

## 3. Query Time (How the AI searches)

When the user asks a question in Cursor/Windsurf (via MCP):

1. The query hits the local CoDRAG search engine.
2. **Knowledge Scope Filter:** CoDRAG checks which folders/URLs the user has currently checked/selected in the Dashboard UI.
3. **Vector Search:** It runs a parallel semantic search across:
   - The remote `main` embeddings (ignoring files that have local deltas).
   - The local delta embeddings.
   - The local knowledge base embeddings.
4. **Context Assembly:** It merges the top results, applies the user's selected Path Weights, and returns the unified context string to the IDE.

### Delta Staleness Detection
When the remote index is updated (because the developer's PR was merged into `main`), local deltas for those files become stale. The sync process must:
1. Compare each local delta's `content_hash` against the new remote `trace_manifest.json`.
2. If the remote manifest now contains the same or newer hash for a file, **discard the local delta** — the remote index already has the enriched version.
3. If the delta file has *further* local edits beyond what was merged, keep the delta.

### Sync Trigger Timing
The local client checks for remote index updates:
- **On daemon startup** (when the IDE opens or CoDRAG starts).
- **On manual "Sync" button press** in the Dashboard.
- **On a configurable polling interval** (default: every 30 minutes while the daemon is running).
- **Not** on every MCP tool call (too frequent, would add latency).

---

## 4. Why this Architecture Wins

1. **Privacy & Simplicity:** The central server never needs to handle user authentication, multi-tenant database row-level security, or personal Jira/Confluence API keys. It just statically serves a zip file of the public `main` branch.
2. **Zero Watcher Loops:** The central sync only happens when `main` changes. The live-sync (watcher) only runs locally for the specific files the user is touching.
3. **Offline Capability:** If the developer goes offline on an airplane, they still have the last-synced remote index, their local knowledge base, and their local deltas. Everything still works.

---

## 5. Implementation Requirements for Phase 06

To make this work, the Phase 06 implementation must add support for **layered index reading**.
Currently, `get_context()` reads a single `documents.json` and `embeddings.npy`.

We must update `src/codrag/core/index.py` to:
1. Load the Remote Trace Index.
2. Load the Local Delta Index.
3. Load the Local Knowledge Index.
4. Mask (tombstone) any document IDs in the Remote index that exist in the Delta index (so the AI doesn't see both the old `main` version and the new local version of the same file).
