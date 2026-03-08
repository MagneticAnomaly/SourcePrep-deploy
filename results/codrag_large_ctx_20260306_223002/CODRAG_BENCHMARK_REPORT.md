# CoDRAG Large-Context Benchmark Report
*Tested on CoDRAG monorepo: 1,341 files, 4,927 nodes, 19,690 edges, 3,328 modules*
*6 model configurations × 4 tasks, completed in 69.6 minutes*

## Speed Summary

| Config | Atlas 50 | Atlas 100 | Group Reasoning (5) | Audit | Total |
|---|---|---|---|---|---|
| **35b-a3b Q4 no-think** | 104s | 110s | 104s | 43s | **6.1 min** |
| 35b-a3b Q4 think | 295s | 301s | 468s | 109s | 19.6 min |
| **35b-a3b Q8 no-think** | **69s** | 113s | 107s | 49s | **5.6 min** |
| 27b Q4 no-think | 217s | 181s | 228s | 99s | 12.1 min |
| 27b Q8 no-think | 180s | 240s | 279s | 97s | 13.3 min |
| **122b-a10b no-think** | 133s | 202s | 170s | 66s | **9.5 min** |

### Speed Analysis
- **35b-a3b Q8 is the fastest** at 69s for Atlas 50 — faster than Q4 (104s). This is surprising and suggests the Q8 model was already loaded in memory while Q4 had to swap in.
- **122b-a10b** (81GB, 10B active) is ~1.6× slower than the 35b-a3b but ~1.5× faster than the 27b dense. A good middle ground.
- **27b dense** is consistently the slowest for no-think configs (2-3× slower than MoE models).
- **35b-a3b think** mode is 3-4× slower than no-think — Group Reasoning jumped from 104s to 468s.

---

## Atlas Quality (50 modules, ~10K tokens input)

| Config | Chars | IDENTITY Quality | Key Differentiators |
|---|---|---|---|
| **35b-a3b Q4 no-think** | 11,202 | Good — mentions SQLModel, FastAPI, React | Most comprehensive, lists all languages |
| 35b-a3b Q4 think | 1,358 | **BROKEN** — thinking leaked into output | Thinking process dumped as plain text |
| **35b-a3b Q8 no-think** | 7,142 | Good — mentions CoDRAG and Jezebel platforms | Clean, well-structured |
| 27b Q4 no-think | 8,428 | Good — "multi-platform codebase" | Names CoDRAG system specifically |
| 27b Q8 no-think | 6,478 | Good — similar to Q4 | Slightly shorter |
| **122b-a10b no-think** | 7,459 | **Best** — "comprehensive ecosystem...RAG" | Most accurate IDENTITY, mentions RAG explicitly |

### Atlas 50 vs 100 Comparison

| Config | 50 mods | 100 mods | Change | Notes |
|---|---|---|---|---|
| 35b-a3b Q4 no-think | 11,202 | 14,036 | **+25%** | More context → more content |
| 35b-a3b Q8 no-think | 7,142 | 12,514 | **+75%** | Dramatic improvement with more input |
| 27b Q4 no-think | 8,428 | 6,739 | **-20%** | DEGRADED — model struggled with larger input |
| 27b Q8 no-think | 6,478 | 9,285 | **+43%** | Better than Q4 at handling more context |
| 122b-a10b no-think | 7,459 | 11,790 | **+58%** | Strong improvement with more context |

**Critical finding:** The 27b Q4 model actually produced LESS content with 100 modules than 50. The denser Q4 quantization may degrade the 27b's ability to handle larger context windows effectively. The Q8 version of the same model handled it fine (+43%), confirming that **quantization quality matters for large-context tasks**.

---

## Group Reasoning Quality (5 representative groups from CoDRAG)

All 6 configs achieved 5/5 parse success. Quality comparison by pattern specificity:

### Group 1 (4 files: config-driven hook composition)
| Config | Pattern Name |
|---|---|
| 35b-a3b Q4 no-think | "Configuration-Driven Service Orchestration" |
| **35b-a3b Q4 think** | **"Facade Pattern (via Hook Composition)"** ← most precise |
| 35b-a3b Q8 no-think | "Controlled Composition with Configuration-Driven Behavior" |
| 27b Q4 no-think | "Configuration-Driven Presentation Layer" |
| 27b Q8 no-think | "Composite State Hook with Configuration-Driven Orchestration" |
| 122b-a10b no-think | "Feature-Specific Hook Composition with External Configuration Binding" |

### Group 5 (15 files: test fixture artifacts)
This group is a known artifact — files from test repos that got linked. Let's see which models detected this:

| Config | Pattern Name | Correctly Identified as Artifact? |
|---|---|---|
| 35b-a3b Q4 no-think | "Fragmented Artifact Repository" | ✅ Yes |
| **35b-a3b Q4 think** | **"Test Evaluation Framework with Multi-Repository Aggregation"** | ✅ Yes + specific |
| 35b-a3b Q8 no-think | "Fragmented Evaluation Harness with Spurious Documentation Coupling" | ✅ Yes + insightful |
| 27b Q4 no-think | "Synthetic Documentation Dependency (Artifact Aggregation)" | ✅ Yes |
| 27b Q8 no-think | "Synthetic Dependency Graph (False Positive)" | ✅ Yes, most direct |
| 122b-a10b no-think | "Artificial Dependency Graph / Test Fixture Aggregation" | ✅ Yes |

**All models correctly identified Group 5 as an artifact/synthetic dependency.** The 35b-a3b Q8 had the most insightful take: "a static analysis or dependency mapping tool has hallucinated connections between unrelated files."

### Architectural Insight Quality

The **35b-a3b Q4 think** mode consistently produced the deepest insights:
- Group 1: "The reliance on Markdown for critical configuration creates a silent failure mode" 
- Group 5: "This group exhibits severe data collection artifacts where external repository test files are incorrectly marked as dependencies"

The **35b-a3b Q8 no-think** was the quality runner-up without the speed penalty of thinking.

---

## Audit Summary Quality

| Config | Chars | Grade | Key Observation |
|---|---|---|---|
| **35b-a3b Q4 no-think** | **4,917** | C | Most detailed, longest output |
| 35b-a3b Q8 no-think | 5,095 | C | Slightly longer, mentions compliance |
| 27b Q4 no-think | 3,697 | **B-** | Only model to give a higher grade |
| 27b Q8 no-think | 3,703 | C | Mentions deferred security/ML logic |
| 122b-a10b no-think | 3,845 | C | Balanced, mentions cross-platform integration |
| 35b-a3b Q4 think | 2,780 | C | Shorter due to thinking overhead |

All audits correctly identified 180 warnings, 0 critical findings, and provided actionable recommendations. The 35b-a3b models (both Q4 and Q8) produced the longest, most detailed reports.

---

## Key Findings

### 1. Think mode breaks prose output on the 35b-a3b MoE
The Atlas 100 with think=True produced 37K chars of leaked thinking process instead of a proper atlas. The `_postprocess` stripping failed because the model emitted "Thinking Process:" as plain text, not in `<think>` tags. **Think mode should NOT be used for prose/non-JSON output tasks.**

### 2. Q8 quantization helps large-context quality
The 27b Q4 model DEGRADED when given 100 modules (produced less content than with 50), while the Q8 version improved by 43%. For large-context tasks, **higher quantization preserves the model's ability to utilize more input context**.

### 3. The 122b-a10b (10B active) is a viable "scope" model
At 133-202s per Atlas call, it's between the MoE (69-110s) and dense 27b (180-240s) in speed, but produces accurate, well-structured output. Its IDENTITY section was the most accurate ("comprehensive ecosystem...retrieval-augmented generation"). For users with 128GB Macs, this is the best scope model.

### 4. Module cap of 50 vs 100 matters differently per model
- MoE models (35b-a3b, 122b-a10b): More context → proportionally more output (25-75% improvement)
- Dense 27b Q4: More context → DEGRADATION
- Dense 27b Q8: More context → improvement (43%), but not as dramatic as MoE

### 5. All models handle CoDRAG's real complexity
Every model correctly identified the multi-language, multi-platform nature of CoDRAG. Every model correctly identified the test fixture group as an artifact. The quality floor is high — the differentiation is in specificity and depth.

---

## Final Three-Tier Model Recommendations

### Tier 1: Fast (Iterative Per-File Tasks)
**Model: `qwen3.5:35b-a3b` (Q4 or Q8)**
- Tasks: Augmentation (Pass 1), Epistemic per-file (Pass 2)
- Think: OFF
- num_predict: 2048
- Speed: ~14s/file
- Notes: Q8 may be slightly faster due to memory layout; quality is equivalent

### Tier 2: Deep (Cross-File Reasoning)  
**Model: `qwen3.5:35b-a3b` (Q4) with think=ON**
- Tasks: Group Reasoning (Stage 6b), Cluster Synthesis (Pass 3)
- Think: ON (produces genuinely better architectural patterns)
- num_predict: 8192 (to accommodate thinking tokens)
- Speed: ~43s/group (small repo), ~94s/group (large repo)
- ⚠️ ONLY for JSON output tasks — think mode breaks prose output

### Tier 3: Scope (Whole-Repo Synthesis)
**Model: `qwen3.5:35b-a3b` (Q8) for most users, `qwen3.5:122b-a10b` for 128GB Macs**
- Tasks: Atlas, Segmented Atlas, Audit Reports
- Think: OFF (critical — think leaks into prose)
- num_predict: 4096-6000
- Module cap: Top 100 modules by file count (prevents context overflow)
- Speed: 69-133s per Atlas call

### Context Window Configuration

| Project Size | Module Cap | num_predict | Estimated Atlas Prompt |
|---|---|---|---|
| < 50 files | All modules | 4096 | < 10K tokens |
| 50-200 files | Top 100 | 4096 | 10-20K tokens |
| 200-500 files | Top 100 | 6000 | 15-25K tokens |
| 500+ files | Top 50 | 4096 | 10-15K tokens + Segmented Atlas |

### User-Configurable Settings
1. **Model per tier** — advanced users can override (e.g., use 122b-a10b for scope tier)
2. **Think toggle** — default ON for Tier 2, OFF for Tier 1 and 3
3. **Module cap** — auto-scaled by project size, user-overridable
4. **Quantization preference** — Q8 recommended for scope tasks if VRAM allows
