# Large-Context Benchmark Report: Atlas, Group Reasoning, Audit
*Tested on TEST repo (DebateHaus Next.js marketing site): 97 nodes, 44 files, 127 edges*

## Speed Results

| Config | Atlas | Group Reasoning (3 groups) | Audit Summary | Total |
|---|---|---|---|---|
| **35b-a3b no-think** | **23s** | **72s** (24s/group) | **24s** | **~2 min** |
| **35b-a3b think** | 260s | 129s (43s/group) | 108s | **~8 min** |
| **27b no-think** | 78s | 204s (68s/group) | 60s | **~6 min** |
| **27b think** | 595s | 1220s (407s/group) | 371s | **~36 min** |

### Speed takeaway
The 35b-a3b MoE is **3× faster** than the 27b dense for no-think tasks, and **11× faster** when thinking is enabled. The 27b-think config takes 407s per group reasoning call — that's nearly 7 minutes per group, which is impractical for production use.

---

## Quality Analysis: Atlas Generation

**Prompt size:** 21,093 chars (~5K tokens) — all module summaries + graph stats + hub files.

All 4 models produced valid, well-structured Atlas documents following the IDENTITY/STACK/ARCHITECTURE/SUBSYSTEMS/FLOW/PATTERNS/RISKS format. Key quality differences:

| Aspect | 35b no-think | 35b think | 27b no-think | 27b think |
|---|---|---|---|---|
| **Output chars** | 2,192 | 2,214 | 2,316 | 1,795 |
| **IDENTITY precision** | Good | Better — adds "beta acquisition" | Good | Good |
| **SUBSYSTEMS detail** | Lists 9 subsystems with files | Lists 10 subsystems with files | Lists 4 broader categories | Lists 7 subsystems |
| **FLOW specificity** | Names 4 concrete files | Names 4 files + build pipeline | Names 5 files + good narrative | Names 4 files |
| **RISKS specificity** | 6 concrete risks with file paths | 9 risks with file paths, most detailed | 8 risks with file paths, very specific | 9 risks but less file-specific |

**Winner: 35b-a3b think** — Produced the most balanced Atlas with the best RISKS section (identified race condition risks, !important overrides, console.log in production) while staying within budget. The 27b-think produced shorter output (1795 chars) despite having 10K thinking tokens — the thinking budget consumed tokens that could have gone to content.

---

## Quality Analysis: Group Reasoning

**Prompt sizes:** 4,628–9,186 chars per group (2-15 files each).

| Aspect | 35b no-think | 35b think | 27b no-think | 27b think |
|---|---|---|---|---|
| **Parse success** | 3/3 | 3/3 | 3/3 | 3/3 |
| **Pattern names** | Descriptive but generic | **Most specific** | Descriptive | Overly broad |
| **Coupling risks** | 5, 5, 4 risks | 5, 6, 5 risks | 4, 4, 5 risks | 3, 5, 4 risks |
| **Insight quality** | Good — "leaky abstraction" | **Best** — "content-injection pattern" | Good — "Command Pattern variation" | OK — less specific |

### Pattern name comparison (Group 2: 15 scroll-animation files)

- **35b no-think:** "Orchestrated Scroll-Driven Visualization with Centralized State"
- **35b think:** "Scroll-Driven Parallax Architecture with Content Injection Hooks" ← most precise
- **27b no-think:** "Centralized State with Event-Driven Animation Orchestration"
- **27b think:** "Component Composition with Shared Services" ← too generic, lost the scroll/animation domain

### Architectural insight comparison (Group 2)

- **35b no-think:** "relies heavily on a global imperative state machine (GSAP singleton) to drive declarative React components, creating a 'leaky abstraction'" — excellent specific insight
- **35b think:** "demonstrates a content-injection pattern where marketing content is decoupled from presentation logic through hook-based dependency" — deeper abstraction
- **27b no-think:** "exhibits a 'Command Pattern' variation where the GSAP hook acts as the central command executor" — good pattern recognition
- **27b think:** "suffers from 'feature branching' debt, evidenced by multiple versions of the same logical sections" — different but valid observation about the _OLD/_BAD files

**Winner: 35b-a3b think** — Most specific pattern names, highest coupling risk count, best architectural insights. The 27b-think was surprisingly weaker despite 6× more thinking time — it produced more generic pattern names and fewer coupling risks.

---

## Quality Analysis: Audit Summary

**Prompt size:** 4,624 chars.

All models produced well-structured markdown audit reports with Health Score, Critical Findings, Top Recommendations, Module Status, and Next Steps.

| Aspect | 35b no-think | 35b think | 27b no-think | 27b think |
|---|---|---|---|---|
| **Output chars** | 2,864 | 2,114 | 2,600 | 2,029 |
| **Health grade** | C | C | C | C |
| **Recommendations** | 5, actionable | 5, concise + specific | 5, detailed + specific | 5, actionable |
| **Module breakdown** | 5 modules | 5 modules | 5 modules | 5 modules |
| **File path citations** | Frequent | Frequent | Frequent | Frequent |

The Audit Summary quality was surprisingly uniform across all 4 models. The 27b-nothink actually produced the most detailed Next Steps section with specific file paths and refactoring suggestions. The think modes produced shorter output — thinking tokens consumed budget.

---

## Key Findings

### 1. Thinking mode hurts output length for prose tasks
Both Atlas and Audit produce **shorter content** with thinking enabled because the thinking tokens consume the `num_predict` budget. The 27b-think Atlas was only 1,795 chars (vs 2,316 without thinking) despite using 10,292 total tokens — most were thinking tokens that get stripped.

**Recommendation:** For prose output tasks (Atlas, Audit), either:
- Use `think=False` and allocate full `num_predict` to content
- OR use `think=True` but increase `num_predict` to 12K+ to compensate for thinking overhead

### 2. Thinking mode genuinely helps JSON reasoning tasks
Group Reasoning with `think=True` on the 35b-a3b produced measurably better pattern names, more coupling risks, and deeper architectural insights. The MoE architecture is efficient enough that the thinking overhead is only ~1.8× (43s vs 24s per group).

### 3. The 27b dense model's thinking mode is impractical
At 407s per group reasoning call (vs 43s for 35b-think), the 27b-think is **9.5× slower** than the 35b-think with **no measurable quality improvement**. In fact, it produced more generic pattern names and fewer coupling risks.

### 4. Context window is not the bottleneck (yet)
The TEST repo's Atlas prompt was only ~5K tokens. Both models support 256K. The real context window challenge will emerge on 300+ file repos where:
- Atlas input could be 50K+ tokens of module summaries
- Group Reasoning groups could have 15 files × 200-char summaries + edges = 10K+ tokens
- Audit could ingest 100+ findings + full Atlas = 30K+ tokens

**We need to test on the CoDRAG repo itself (300+ files) to stress the context window.**

### 5. Ollama's default `num_ctx` may silently truncate
Ollama defaults to 2048-8192 context tokens. We should explicitly pass `num_ctx` in the options dict for large-context tasks. Both models support 262,144 tokens.

---

## Three-Tier Model Recommendations (Final)

| Tier | Task Examples | Recommended Model | Think | Time/Call | Quality |
|---|---|---|---|---|---|
| **Fast (iterative)** | Augmentation, Epistemic per-file | `qwen3.5:35b-a3b` | OFF | ~14s/file | ★★★★ |
| **Deep (group)** | Group Reasoning, Cluster Synthesis | `qwen3.5:35b-a3b` | **ON** | ~43s/group | ★★★★★ |
| **Scope (whole-repo)** | Atlas, Audit Reports | `qwen3.5:35b-a3b` | OFF | ~23s/call | ★★★★ |

### Why the 35b-a3b wins all three tiers

The MoE architecture (3B active parameters out of 35B total) gives us the best of both worlds:
- **Speed:** 3× faster than the 27b dense model across all task types
- **Quality:** Equal or better than 27b on every task we tested
- **Thinking efficiency:** When thinking is enabled, the overhead is only 1.8× (vs 7× for the 27b)
- **Context window:** Same 256K support as the 27b

The 27b dense model should be reserved as a **fallback/verification model** for cases where we want a second opinion on high-stakes analysis, not as the primary workhorse.

### Context Window Strategy for Users

| Project Size | Atlas `num_predict` | Atlas `num_ctx` | Group `num_predict` | Notes |
|---|---|---|---|---|
| < 50 files | 4096 | default | 4096 | Current defaults work fine |
| 50-200 files | 6000 | 16384 | 6000 | Increase for larger module summaries |
| 200-500 files | 8192 | 32768 | 8192 | Segment Atlas recommended |
| 500+ files | 8192 | 65536 | 8192 | Must use Segmented Atlas |

### What Users Should Control

Users should be able to configure:
1. **Model selection** per tier (fast/deep/scope) — power users may prefer different models
2. **Think mode** toggle — off by default for fast tier, on for deep tier
3. **Context window budget** — auto-scaled by project size, but overridable
4. **num_predict ceiling** — defaults scale with project size, but users can increase for deeper output
