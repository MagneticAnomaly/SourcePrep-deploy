# Deep Dive: Augment Code & Sourcegraph Cody vs Prep

## Purpose

This document provides a detailed technical and strategic comparison of Prep against its two closest cloud-based competitors: **Augment Code** and **Sourcegraph Cody**. The goal is to solidify Prep's market position by understanding exactly how these competitors work and where Prep's local-first + BYOK architecture provides genuine advantages.

## Executive Summary

| Dimension | Prep | Augment Code | Sourcegraph Cody |
|-----------|--------|--------------|------------------|
| **Architecture** | Local-first, on-device | Cloud-hosted, code uploaded | Cloud-hosted, code indexed remotely |
| **Code residency** | Stays on device | Uploaded to Augment cloud | Indexed on Sourcegraph instance |
| **Embeddings** | Local (nomic-embed-text) | Cloud (custom models) | Deprecated embeddings → keyword search |
| **LLM** | BYOK (any provider) | Augment's models (cloud) | Multiple providers (cloud) |
| **Vector DB** | Local (on-device) | Cloud (Google Cloud) | Removed in favor of BM25 search |
| **Latency** | Sub-10ms local queries | Network-bound (50-200ms+) | Network-bound |
| **Privacy** | Complete (no upload) | Code uploaded, "proof of possession" | Code indexed remotely |
| **Pricing** | **Free (1-repo) / Starter ($29/4mo) / Pro ($79 life)** | $20-$200/mo + Enterprise | $49/user/mo Enterprise only (Free/Pro discontinued) |

**Key insight**: Both Augment and Sourcegraph are cloud-first by design. Prep's local-first architecture is a genuine moat, not just a positioning choice.

---

## Augment Code: Deep Dive

### How it works

#### Code upload and indexing
When a developer enables Augment:
1. **Code is uploaded to Augment's cloud** (Google Cloud infrastructure)
2. Files are filtered via `.gitignore` and `.augmentignore`
3. Embeddings are generated using **custom-trained models** (not generic OpenAI embeddings)
4. A **per-user, per-branch index** is maintained in real-time

Source: https://www.augmentcode.com/blog/a-real-time-index-for-your-codebase-secure-personal-scalable

#### Key architectural claims

**Real-time indexing**:
> "Our goal is to update your personal search index within a few seconds of any change to your files."

They process "many thousands of files per second" using Google Cloud PubSub, BigTable, and AI Hypercomputer.

**Per-user, per-branch indexes**:
> "AI that does not respect the exact version of the code you are working on can easily cost you and your team more time than what it saves you."

This is sophisticated—they maintain separate indexes per developer per branch, not just per repo.

**Custom embedding models**:
> "Generic embedding models are good at identifying which text pieces are similar. However, embedding from generic models can easily miss a lot of relevant context that is not similar on a textual level."

They've trained models specifically for code context retrieval, claiming generic models "quickly degrade for larger codebases."

#### Security claims

- **"Proof of Possession"**: IDE must cryptographically prove it has access to a file before the backend returns content
- **Non-extractable API**: Claims to prevent data exfiltration
- **No training on customer code**: Stated in terms
- **SOC 2 Type II, ISO 42001 certified**

Source: https://www.augmentcode.com/security

#### Pricing (as of research date)

| Tier | Price | Credits |
|------|-------|---------|
| Indie | $20/mo | 40,000 credits |
| Standard | $60/mo | 130,000 credits |
| Max | $200/mo | 450,000 credits |
| Enterprise | Custom | Custom + SSO/SCIM/CMEK |

Credit-based pricing: A "small task" (~10 tool calls) costs ~300 credits; complex task (~60 tool calls) costs ~4,300 credits.

Source: https://www.augmentcode.com/pricing

### Augment's strengths

1. **Real-time branch-aware indexing** — sophisticated per-user state management
2. **Custom-trained context models** — not relying on generic embeddings
3. **Enterprise-grade security** — SOC 2, ISO 42001, customer-managed encryption keys
4. **Commit history indexing** — tracks codebase evolution, not just current state

### Augment's weaknesses (from Prep's perspective)

1. **Requires code upload** — code leaves the developer's machine
2. **Cloud-dependent** — no offline capability
3. **Network latency** — every query hits cloud infrastructure
4. **Cost scales with usage** — credit-based model can get expensive
5. **No self-host option** — enterprise still uses Augment's cloud

---

## Sourcegraph Cody: Deep Dive

### How it works

#### Architecture evolution

Sourcegraph Cody has gone through a significant architectural shift:

**Old approach (deprecated)**:
- Used OpenAI `text-embedding-ada-002` for embeddings
- Stored embeddings in a vector database
- Ran vector similarity search for context retrieval

**Current approach**:
- **Keyword search (BM25-based)** using Sourcegraph's Code Search engine
- No embeddings, no vector database
- Pre-processes queries into tokens, ranks file snippets by relevance

Source: https://sourcegraph.com/blog/how-cody-understands-your-codebase

#### Why they abandoned embeddings

From their blog:
> "While embeddings worked for retrieving context, they had some drawbacks:
> - Your code has to be sent to a 3rd party (OpenAI) for processing
> - The process of creating embeddings and keeping them up-to-date introduces complexity
> - Searching vector databases for codebases with >100,000 repositories is complex and resource-intensive"

They replaced embeddings with their native Code Search platform, which uses **BM25 ranking** plus learned signals.

#### Context retrieval flow

For **chat/commands**:
1. User selects repositories (up to 10)
2. Query is tokenized and cleaned
3. Sourcegraph search engine scans repos, ranks snippets using adapted BM25
4. Local context (open files, tabs) is also pulled
5. Global ranking combines remote + local snippets
6. Top N snippets packaged into prompt context

For **autocomplete**:
- Uses **local context only** for speed
- Tree-sitter for intent classification
- Searches open files, tabs, recently closed tabs
- Different (faster) LLMs tuned for completion

#### Major recent change: Free/Pro tiers discontinued

As of July 23, 2025:
- **Cody Free**: Discontinued
- **Cody Pro**: Discontinued
- **Enterprise Starter**: No longer includes Cody
- **Cody Enterprise**: Still available ($49/user/mo for Code Search; Cody pricing separate)

Sourcegraph is pivoting to **Amp** (ampcode.com) for consumer/prosumer AI coding.

Source: https://sourcegraph.com/blog/changes-to-cody-free-pro-and-enterprise-starter-plans

### Sourcegraph's strengths

1. **Proven at massive scale** — 300k+ repos, 90GB+ monorepos
2. **Multi-repo context** — can search across up to 10 repos at once
3. **Code Search integration** — leverages battle-tested search infrastructure
4. **No embeddings to manage** — simplified architecture (for admins)

### Sourcegraph's weaknesses (from Prep's perspective)

1. **No free/pro tier** — Enterprise-only for Cody
2. **Keyword search limitations** — BM25 misses semantic similarity
3. **Code must be indexed on Sourcegraph instance** — not local
4. **Network latency for all queries** — remote search required
5. **Complexity** — requires running/managing a Sourcegraph instance

---

## Local vs Cloud Vector DB: Performance Analysis

### Latency characteristics

| Deployment | Typical p50 latency | Typical p99 latency | Notes |
|------------|---------------------|---------------------|-------|
| **Local in-memory (FAISS)** | <1ms | <5ms | No network, RAM-bound |
| **Local on-disk (Qdrant/Chroma)** | 5-20ms | 50ms | SSD I/O bound |
| **Cloud managed (Pinecone)** | 20-50ms | 100-200ms | Network + compute |
| **Self-hosted cloud** | 30-100ms | 200-500ms | Network + instance variability |

Source: https://www.firecrawl.dev/blog/best-vector-databases-2025, community benchmarks

### Why local is faster

1. **No network round-trip** — cloud queries add 20-100ms minimum just for network
2. **No queueing** — local queries don't compete with other users
3. **Memory locality** — hot data stays in RAM/cache
4. **No serialization overhead** — no JSON/HTTP encoding/decoding

### Prep's advantage

With nomic-embed-text running locally + a local vector store:
- **Embedding generation**: ~10-50ms on CPU, faster on GPU
- **Vector search**: <10ms for typical codebase sizes (<1M vectors)
- **Total query latency**: <100ms end-to-end

Compare to Augment/Sourcegraph:
- Network latency alone: 50-200ms
- Plus server-side processing: 100-500ms total

**For interactive use (MCP tool calls, IDE integration), this 5-10x latency advantage is significant.**

### Scale considerations

Local vector DBs have limits:
- FAISS can handle billions of vectors but needs RAM
- Qdrant performs well under 50M vectors, degrades beyond
- For typical codebase sizes (10k-1M files), local is comfortably viable

---

## How Cloud Services Access Local Codebases

### The fundamental approaches

| Approach | How it works | Used by |
|----------|--------------|---------|
| **Code upload** | IDE extension uploads code to cloud | Augment Code |
| **Git host integration** | Service clones from GitHub/GitLab | Sourcegraph, Greptile |
| **Agent sync** | Background agent watches filesystem | Some enterprise tools |
| **Hybrid** | Local index + cloud augmentation | GitHub Copilot (partial) |

### Augment Code: Upload model

```
Developer machine → IDE extension → Augment Cloud
                                        ↓
                                   Index + embed
                                        ↓
                                   Query at runtime
```

- Code physically leaves the machine
- "Proof of possession" verifies access rights
- Real-time sync on file changes

### Sourcegraph Cody: Git host model

```
GitHub/GitLab/etc → Sourcegraph instance → Index
                                              ↓
                          IDE extension → Query via API
```

- Code cloned from git host to Sourcegraph
- Indexed on Sourcegraph infrastructure
- IDE queries remote index

### Neither operates on the local git repo directly

Both Augment and Sourcegraph:
- Require code to leave the developer's machine (or be accessible via git host)
- Maintain their own indexes in their infrastructure
- Cannot work fully offline

**This is Prep's key differentiator: it operates directly on the local codebase without uploading anything.**

---

## Prep's Differentiated Position

### Architecture comparison

```
Prep (local-first):
Local codebase → Local embeddings (nomic-embed-text) → Local vector DB
                           ↓
                    MCP tools → IDE/Agent
                           ↓
                    BYOK LLM (optional cloud)

Augment Code (cloud-first):
Local codebase → Upload to cloud → Cloud embeddings → Cloud vector DB
                                           ↓
                                    IDE extension → Cloud query → Response

Sourcegraph Cody (cloud-first):
Git host → Sourcegraph instance → Code Search index
                                         ↓
                             IDE extension → Cloud query → Response
```

### Prep's unique combination

| Feature | Prep | Augment | Sourcegraph |
|---------|--------|---------|-------------|
| Code never leaves device | ✅ | ❌ | ❌ |
| Works offline | ✅ | ❌ | ❌ |
| Sub-10ms query latency | ✅ | ❌ | ❌ |
| Multi-codebase registry | ✅ | ❌ | ✅ (multi-repo) |
| Granular scoping (include/exclude) | ✅ | Partial (.augmentignore) | Partial |
| MCP integration | ✅ | ❌ | ✅ (recently added) |
| BYOK for LLM | ✅ | ❌ | ✅ |
| Local embeddings | ✅ (nomic-embed-text) | ❌ (cloud) | ❌ (deprecated) |
| Desktop app | ✅ (Tauri) | ❌ (IDE plugin only) | ❌ (IDE plugin + web) |

### Where competitors have advantages

Be honest about where they're stronger:

**Augment Code**:
- More sophisticated context models (custom-trained vs. generic)
- Real-time branch-aware indexing (Prep doesn't track branches yet)
- Commit history integration
- Enterprise security certifications (SOC 2, ISO 42001)

**Sourcegraph**:
- Proven at massive scale (300k+ repos)
- Code Search is battle-tested infrastructure
- Multi-repo context (up to 10 repos in one query)
- Enterprise customer base and support

### Prep's strategic response

1. **Don't compete on cloud scale** — own the local-first niche
2. **Emphasize latency** — local queries are 5-10x faster
3. **Emphasize privacy** — code never leaves the device
4. **Emphasize offline** — works without internet
5. **Emphasize cost** — no per-query cloud costs
6. **MCP as the integration surface** — be the context engine for IDEs, not a replacement

---

## Market Position Recommendations

### Positioning statement

> **Prep is the local-first codebase context engine for developers who need fast, private, offline-capable RAG without uploading their code to the cloud.**

### Target segments (where Prep wins)

1. **Privacy-conscious developers** — code never leaves machine
2. **Air-gapped/regulated environments** — can run fully offline
3. **Latency-sensitive workflows** — MCP tool calls need <100ms
4. **Cost-conscious teams** — no per-query cloud costs
5. **Multi-project freelancers** — registry of client codebases

### Anti-segments (where competitors win)

1. **Massive monorepos (>50M files)** — Sourcegraph is proven at this scale
2. **Teams wanting managed infrastructure** — Augment handles everything
3. **Enterprise needing SOC 2 today** — Augment has certifications now

### Feature roadmap implications

Based on this analysis, Prep should prioritize:

1. **Local embedding quality** — consider fine-tuning nomic-embed-text for code
2. **Branch awareness** — Augment's per-branch indexing is sophisticated
3. **Commit history indexing** — Augment tracks codebase evolution
4. **Enterprise security posture** — SOC 2 path for enterprise tier

### What NOT to build

1. **Cloud-hosted version** — don't dilute the local-first moat
2. **Generic IDE replacement** — stay focused on context engine
3. **Multi-repo remote search** — that's Sourcegraph's territory

---

## Conclusion

Prep occupies a **genuinely differentiated position** in the market:

- **Augment Code** and **Sourcegraph Cody** are cloud-first by design
- Neither can offer true local-first operation
- Prep's latency, privacy, and offline advantages are structural, not just marketing

The local vector DB is **faster** than cloud-based (5-10x lower latency). Cloud services must upload or clone code—they cannot operate directly on the local git repo.

**Prep should lean into this differentiation**, not try to match cloud competitors feature-for-feature. The goal is to be the **best local-first context engine**, not a worse cloud service.

---

## Sources

- Augment Code blog: https://www.augmentcode.com/blog/a-real-time-index-for-your-codebase-secure-personal-scalable
- Augment Code security: https://www.augmentcode.com/security
- Augment Code pricing: https://www.augmentcode.com/pricing
- Sourcegraph Cody architecture: https://sourcegraph.com/blog/how-cody-understands-your-codebase
- Sourcegraph plan changes: https://sourcegraph.com/blog/changes-to-cody-free-pro-and-enterprise-starter-plans
- Vector DB comparison: https://www.firecrawl.dev/blog/best-vector-databases-2025
