# Model Comparison Findings — 3-Model Benchmark (Mar 8, 2026)

*Status: Research findings from automated eval runs*
*Data: `tests/eval/model_snapshots/` (12 snapshot files)*
*Tool: `tests/eval/model_comparison.py`*

---

## 1. Models Tested

| Model | Provider | Type | Cost |
|---|---|---|---|
| `lmstudio-community/qwen3-coder-next-mlx` | LM Studio (local, port 1234) | Code-specialized MoE ~80B | $0 (local hardware) |
| `qwen3-coder-next:cloud` | Ollama Cloud (port 11434) | Same architecture, cloud-hosted | Ollama Cloud credits |
| `kimi-k2.5:cloud` | Ollama Cloud (port 11434) | General reasoning, 1T params | Ollama Cloud credits |

---

## 2. Repo 1: mini-redis-rust (29 file nodes, real repo)

Tokio-based educational Redis implementation in Rust.

### Metrics

| Metric | 🏠 coder-next MLX (local) | ☁️ coder-next:cloud | ☁️ kimi-k2.5:cloud |
|---|---|---|---|
| **Epistemic files** | 29 | 29 | 29 |
| **Avg confidence** | 0.875 | 0.880 | **0.923** |
| **Avg cross_refs** | 1.4 | **2.6** | 1.1 |
| **Avg patterns** | 1.5 | 1.6 | **2.3** |
| **Avg summary chars** | 611 | **632** | 533 |
| **Group count** | 4 | 3 | 4 |
| **Module count** | 15 | 20 | 23 |
| **Atlas chars** | 1,540 | 1,527 | **1,554** |

### Timing

| Stage | 🏠 Local MLX | ☁️ Cloud coder | ☁️ Kimi |
|---|---|---|---|
| **Epistemic** | 258s (8.9s/file) | 371s (12.8s/file) | **155s (5.3s/file)** |
| **Group Reasoning** | 61.6s | **28.7s** | 131.6s |
| **Module Synthesis** | **110.7s** | 111.2s | 118.6s |
| **Atlas** | 19.2s | 14.2s | **10.4s** |
| **Total** | **450s** | 525s | 416s |

### Pattern Names

- **Local MLX**: "Redis Protocol Command Dispatch Pipeline", "Graceful Redis Lifecycle Manager with TTL-Aware Pub/Sub", "Async Redis Protocol Command Router with Client Abstraction Layer", "Redis Pub/Sub Message Exchange with Async I/O"
- **Cloud coder**: "Graceful-Shutdown-Aware Shared State Manager", "Async-Blocking Interop Redis Protocol Stack with Command-Driven Pub/Sub", "Redis Command Fallback & I/O Encapsulation Layer"
- **Kimi**: "Redis Protocol Frame Transport Kernel with Client-Server Symmetry", "Redis Core with Graceful Shutdown Observability", "Multi-Runtime Redis Client-Server with Command Dispatch", "Redis Async Pub/Sub Example Pair"

### Atlas Identity (first line)

- **Local MLX**: "A minimal, educational Redis-compatible server and client implementation in Rust using Tokio for async I/O, supporting core commands (PING, GET, SET, PUBLISH, SUBSCRIBE), pub/sub messaging..."
- **Cloud coder**: "A minimal, educational Redis-compatible server and client implementation in Rust using Tokio, designed to demonstrate async programming patterns and protocol compliance."
- **Kimi**: "mini-redis is an educational Redis client/server implementation built with Tokio, demonstrating async Rust patterns through a minimal but functional Redis-compatible protocol stack."

---

## 3. Repo 2: TEST/DebateHaus (44 file nodes, real repo)

Next.js marketing site with GSAP scroll-driven animations, TypeScript/React.

### Metrics

| Metric | 🏠 coder-next MLX (local) | ☁️ coder-next:cloud | ☁️ kimi-k2.5:cloud |
|---|---|---|---|
| **Epistemic files** | 44 | 44 | 44 |
| **Avg confidence** | 0.874 | 0.881 | **0.899** |
| **Avg cross_refs** | 2.0 | **2.2** | 1.9 |
| **Avg patterns** | 1.0 | 1.0 | **1.7** |
| **Avg summary chars** | **686** | 641 | 568 |
| **Groups** | 2 | 2 | 2 |
| **Modules** | 33 | 29 | **15** |
| **Atlas chars** | 1,535 | 1,511 | **1,555** |

### Timing

| Stage | 🏠 Local MLX | ☁️ Cloud coder | ☁️ Kimi |
|---|---|---|---|
| **Epistemic** | 488s (11.1s/file) | **203s (4.6s/file)** | 352s (8.0s/file) |
| **Group Reasoning** | 50.9s | **36.7s** | 122.4s |
| **Module Synthesis** | 247.0s | **114.6s** | 111.3s |
| **Atlas** | 26.8s | **6.8s** | 10.8s |
| **Total** | 813s (13.5m) | **361s (6.0m)** | 597s (9.9m) |

### Module Quality (Critical Finding)

For a 44-file repo, Kimi produced **15 clean, distinct modules** while the coder models produced 29-33 with significant overlap/fragmentation:

- **Local MLX (33)**: "Parallax Animation Subsystem", "Scroll-Driven Hero UI", "Roadmap Visualization Subsystem", "Ui" (generic!)
- **Cloud coder (29)**: "Scroll-Driven UI Orchestration", "Scroll-Driven Interactive UI", "Scroll-Driven UI Enhancements" (hard to distinguish)
- **Kimi (15)**: "Animation Subsystem", "Content Management", "Marketing Site Landing Pages", "GSAP Animation Infrastructure" (each distinct)

### Atlas Identity

- **Local MLX**: "...accessibility-first marketing site for a video debate platform that orchestrates immersive UI experiences using GSAP and React, focusing on governance visualization"
- **Cloud coder**: "...scroll-driven, accessible, narrative-rich user experiences centered on governance, trust, and civic discourse"
- **Kimi**: "...immersive scroll-driven landing experiences through a Next.js React frontend with GSAP-powered animations for user acquisition and beta program signup"

Kimi is the most **actionable** — mentions business purpose (user acquisition, beta signup). Coder models describe technical UX but miss business context.

---

## 4. Earlier Findings: HomeColab + TEST (Kimi vs qwen3.5:35b-a3b)

From `.prep/backups/` A/B comparison on HomeColab (665 files) and TEST (44 files).

### HomeColab Epistemic (599 files)

| Metric | qwen3.5:35b-a3b | kimi-k2.5:cloud |
|---|---|---|
| Avg confidence | **0.933** | 0.895 (calibration issue on docs) |
| Avg cross_refs | 2.6 | **2.9** |
| Avg patterns | 1.0 | **1.2** |
| Avg summary chars | **581** | 558 |

**Confidence calibration issue**: Kimi reports 0.50 on markdown/docs files where Qwen reports 0.95. Actual content quality is comparable.

### HomeColab Modules

- Qwen: 232 modules, descriptive unique names
- Kimi: 254 modules, shorter names but fragmentation ("Design System (Homecolabapp)" appears 3 times)
- Only **6 of ~240 module names overlap** — models cluster very differently

### HomeColab Pipeline Speed (kimi-k2.5:cloud)

| Stage | Time |
|---|---|
| Epistemic (599 files) | 74.6 min (7.6s/file avg) |
| Group Reasoning (31 groups) | 22.9 min |
| Module Synthesis (254 modules) | 19.1 min |
| Atlas | 1.0 min |
| Deepening | 1.1 min |
| Deep Knowledge Embedding (1,499 chunks) | 6.3 min |
| **Total** | **124.8 min** |

Kimi epistemic: 5.3s/file (free tier). Local qwen3.5:35b: ~13.5s/file. **Kimi 1.8× faster.**

---

## 5. Kimi-k2.5:cloud Pricing & Rate Limits

| Tier | Price | Rate Limit |
|---|---|---|
| **Free** | $0 | Rate-limited (unclear exact cap) |
| **Starter** | ~$3/mo | ~300 req/day (community reports) |
| **Pro** | $20/mo | Higher limits (unspecified) |

**Volume estimates for CoDRAG pipeline:**

| Repo Size | Total Requests |
|---|---|
| Small (50 files) | ~60 |
| Medium (200 files) | ~250 |
| Large (665 files) | ~635 |
| XL (5000+ files) | ~5,100 |

**⚠️ Privacy**: Ollama cloud may use prompts for training. For proprietary codebases, local models recommended.

**⚠️ Rate limit detection**: Ollama returns HTTP 429 when limits exceeded. No API to check remaining quota proactively.

---

## 6. Cross-References Explained

The `cross_references` field is from **epistemic enrichment (Deep Reasoning)**. When a model analyzes `src/components/EnhancedHero.tsx`, it identifies other files that component connects to — e.g., `src/hooks/useGSAP.ts`, `src/styles/globals.css`. These cross-refs directly feed the knowledge graph powering CoDRAG's `/context` search. **More accurate cross-refs = better search results.**

This is the Deep Reasoning task (Reasoning slot in the UI), NOT assigned to a coder model. It's separate from **Inferred Edge Discovery** (Code slot), which finds cross-language/dynamic edges that static parsing misses. Edge Discovery has NOT been benchmarked in this comparison — that's a gap to fill.

---

## 7. Task-to-Model Recommendations (Based on Both Repos)

| Task | Best Quality | Best Speed | Best Value |
|---|---|---|---|
| **Epistemic (Deep Reasoning)** | Kimi (highest conf, most patterns) | Cloud coder (4.6s/file) | Cloud coder (close quality, 2.4× faster) |
| **Group Reasoning** | Kimi (richer architectural insight) | Cloud coder (37s vs 122s) | Cloud coder for speed, Kimi for quality |
| **Module Synthesis** | **Kimi** (15 clean modules vs 29-33 fragmented) | Cloud coder (115s vs 111s — tie) | **Kimi** — quality difference is decisive |
| **Atlas** | **Kimi** (business-aware, most specific) | Cloud coder (7s vs 11s) | **Kimi** — 4s doesn't matter |
| **Inferred Edge Discovery** | Unknown (not benchmarked) | Unknown | coder-next (local) — code-specific, no credits |
| **Augmentation/Catalogue** | Not tested | Not tested | Local model — high volume, simple JSON |

### Mapped to Pipeline UI Slots

| Stage | UI Category | Recommended Model |
|---|---|---|
| Inferred Edge Discovery | Code | qwen3-coder-next (local) |
| Catalogue Summarization | Fast | qwen3.5:35b-a3b Q8 (local) |
| Deep Reasoning | Reasoning | kimi-k2.5:cloud OR cloud coder |
| Group Reasoning | Reasoning | kimi-k2.5:cloud |
| Module Synthesis | Reasoning | kimi-k2.5:cloud |
| Atlas Generation | Reasoning | kimi-k2.5:cloud |
| Deepening Loop | Reasoning | Same as Deep Reasoning |
| Search Preprocessing | Fast | qwen3.5:35b-a3b Q8 (local) |
| Automated Audits | Reasoning | kimi-k2.5:cloud |
| Trace Augmentation | Fast | qwen3.5:35b-a3b Q8 (local) |

---

## 8. Open Questions

- [ ] Benchmark Inferred Edge Discovery (code-specific task) across models
- [ ] Kimi rate limits on free tier — how many files/hour before throttling?
- [ ] Kimi confidence calibration — should we normalize scores by model?
- [ ] Kimi module fragmentation — prompt engineering to reduce duplicates
- [ ] qwen3-coder-next vs kimi for Edge Discovery
- [ ] Compare kimi think mode ON vs OFF per task
- [ ] Test qwen3.5:35b-a3b (general model) as a fourth comparison point

---

## 9. Reproducibility

All snapshots in `tests/eval/model_snapshots/`:
```
mini-redis-rust__lmstudio-community_qwen3-coder-next-mlx__20260308_221612.json
mini-redis-rust__qwen3-coder-next_cloud__20260308_223808.json
mini-redis-rust__kimi-k2.5_cloud__20260308_222308.json
TEST__lmstudio-community_qwen3-coder-next-mlx__20260308_231700.json
TEST__qwen3-coder-next_cloud__20260308_232301.json
TEST__kimi-k2.5_cloud__20260308_233257.json
```

Eval harness: `tests/eval/model_comparison.py`

Example command:
```bash
.venv/bin/python -m tests.eval.model_comparison \
  --repo mini-redis-rust \
  --models "lmstudio-community/qwen3-coder-next-mlx,qwen3-coder-next:cloud,kimi-k2.5:cloud" \
  --endpoint-map "lmstudio-community/qwen3-coder-next-mlx=http://localhost:1234|openai-compatible" \
  --snapshot
```
