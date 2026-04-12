# GTC 2026 S81570 — "From Data to Decisions: Enabling AI Agents With Business Knowledge"

**Source:** NVIDIA GTC 2026, Session S81570
**Speakers:** Rupa (NVIDIA) and Rachel (NVIDIA)
**Captured:** 2026-04-11
**Transcript:** local copy at `~/Library/Mobile Documents/com~apple~CloudDocs/From_Data_to_Decisions__Enabli_transcript_en-us.txt`

---

## TL;DR

NVIDIA's session walks through their **Agentic Blueprints** — reference architectures for connecting AI agents to enterprise knowledge. The centerpiece is **AI-Q 2.0** (launched the morning of the talk), which sits on top of their RAG Blueprint and adds an orchestrator + dynamically-spawned planning/research subagents built on LangChain "deep agents" + NemoAgentToolkit.

The most actionable findings for CoDRAG come from **what NVIDIA learned the hard way** when they deployed AI-Q internally and to partners like Distyl, Red Hat, Canonical, and Dell.

---

## The Five Pillars (their framing for "reliable knowledge agents")

1. **Knowledge layer** — factual grounding, business context, long-term memory
2. **Agent-aware retrieval** — multi-source, reasoning-fused, not single-shot lookup
3. **Reasoning** — data must be "reason-ready"
4. **Scalability and reliability** — real-time data freshness
5. **Continuous learning** — feedback loops at runtime

CoDRAG already covers 1 and 2 well. The gaps are #3 (reason-ready surfaces over the graph), and #5 (the data flywheel idea — see below).

---

## AI-Q 2.0 Architecture (the most relevant blueprint)

- **Orchestrator agent + dynamically-spawned subagents** (planning + research)
- Built on **LangChain "deep agents"** + **NemoAgentToolkit**
- Solved context-management between orchestrator and subagents using a **shared file system** rather than passing context through prompts
- **Hybrid model architecture** (this is the winning recipe):
  - Frontier models (GPT-5-2 in their leaderboard run) for orchestration and planning
  - **Nemotron 3 Super** for researcher subagents
  - **Nemotron 3 Nano** for the intent classifier
- Won **#1 on DeepResearch Bench v1 and v2** (as of the morning of the talk)

### The 70/30 finding (most important takeaway)

NVIDIA deployed deep research internally. Their internal users wanted **shallow research 70% of the time**. They added an intent router and a shallow-research path. Without this, every query was paying the cost of a full deep-agent loop.

### The clarifying-questions finding

Users were kicking off deep research reports that take **10 minutes**, then getting results that didn't match their intent. NVIDIA added **2–3 clarifying questions and a plan-approval step** before the expensive work runs. This is human-in-the-loop applied at the *expensive operation boundary*, not at every step.

---

## Other Blueprints Mentioned

| Blueprint | Stack | Notable Detail |
|---|---|---|
| **NVIDIA RAG Blueprint** | GPU-accelerated ingestion + retrieval, multimodal (VLM at generation), vector DB abstraction | Mature, production-deployed at NVIDIA |
| **Vulnerability Analysis & Triage** | NemoAgentToolkit, CVE + per-environment context | Red Hat ExploitIQ, Canonical Ubuntu both built on it; on-prem + open was the deciding factor |
| **Video Search & Summarization** | 3-layer: real-time inference / analytics / agentic reasoning | Petabyte-scale stored video, real-time camera streams |
| **Data Flywheel** | Nemo Customizer (LoRA / distillation), Nemo Evaluator, Nemo Datastore | Continuous fine-tune → eval → push-to-prod loop |

---

## Partner Customizations (the proof points)

### Distyl + Telco — personal assistant agent
Took the AI-Q intent router pattern and applied it to personalization agents.
- **60% reduction in redundant processing**
- **27% improvement in recommendation accuracy**

### Red Hat ExploitIQ — vulnerability triage
Built on the Vulnerability Triage Blueprint. **On-prem requirement was the deciding factor** because it's fully open source. Contributed back to the repo.

### Canonical — Ubuntu vulnerability triage
Used the blueprint as inspiration, built **custom NemoAgentToolkit stages** for Ubuntu-specific package vulnerability logic.
- **2× faster triage than manual**
- **Surfaces vulnerabilities that had previously been missed**

### Dell + BioNeMo — drug discovery
Stacked RAG + AI-Q + BioNeMo virtual screening on Dell's AI Data Platform. Continuous medical literature ingestion feeds the virtual screening tools.

### Royal Bank of Canada — financial services
Measuring agent impact in **dollars, not time saved**. Open models matter for regulated industries.

---

## Scaling Best Practices (their slide)

- **Define latency and throughput thresholds per component** (because blueprints are composable, you scale each microservice independently)
- **Pre-process at source** — tokenize, chunk, and embed ahead of time, not at query time
- **GPU-accelerated indexing** (cuVS for vector indexes)
- **NIM Operator** (Kubernetes operator) for model lifecycle and updates
- **AI Data Platform** — push GPU compute *to the storage layer* for ingestion at scale

---

## What CoDRAG Should Learn / Steal

### 1. The 70/30 shallow-vs-deep finding validates and extends `codrag_search` intent classification
CoDRAG already auto-classifies query intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). What it doesn't do is **explicitly route between a fast/cheap path and a slow/deep path with cost asymmetry awareness**. AI-Q's pattern: small fast classifier (Nemotron 3 Nano) decides up front, then either GPT-4 Mini answers immediately or the deep loop kicks in.

**For CoDRAG:** LOCATE/DISCOVER are inherently shallow (symbol lookup, directory overview); EXPLAIN/RATIONALE/TRACE are inherently deep (semantic search + graph expansion + concept lookup). The cost asymmetry is real but we don't currently expose it to callers or budget against it. Worth adding an explicit "shallow / deep / auto" mode parameter and routing telemetry.

### 2. Hybrid model architecture is a proven recipe
Frontier for orchestration and planning, smaller specialized for per-unit work. CoDRAG's `src/codrag/core/llm_client.py` and `model_awareness.py` are already trying to do this — AI-Q's leaderboard win (GPT-5-2 + Nemotron 3 Super) is external validation that this is the *correct* shape, not just a cost-saving compromise.

**For CoDRAG:** the augmenter / enrichment pipeline (multi-pass LLM annotations) is the obvious place to apply this. Orchestrator decides what to enrich; smaller model does the per-file work.

### 3. Shared file system for subagent context (not prompts)
When CoDRAG eventually does multi-agent enrichment passes (which Phase 96/Phase 89 work hints at), the context-sharing pattern between agents should be a **shared file system**, not prompt context. NVIDIA explicitly called out that this fixed their context-management problems.

### 4. Clarifying questions before expensive operations
CoDRAG has plenty of expensive operations: full reindex, deep enrichment, impact analysis on hub files, large-scale audit enrichment. None of them currently pause to confirm intent. AI-Q's lesson: **users start expensive jobs, get the wrong result, lose 10 minutes**. Two or three clarifying questions and a "here's the scope, approve?" gate would prevent this.

### 5. CVE / vulnerability triage is the single most concrete enterprise win in the talk
Two of NVIDIA's highest-profile partner stories (Red Hat, Canonical) are vulnerability triage. CoDRAG's `codrag_audit` SARIF enrichment is in the same neighborhood — it adds blast radius, hub status, and concept context to lint findings. **There is a real positioning story here:** "structural blast radius for security findings" is something neither Snyk nor Semgrep nor Dependabot does, and neither does AI-Q.

### 6. "Reference architecture, not finished product" framing
NVIDIA's posture is: here are blueprints, take what you need, customize stages, leave out what you don't need. **This is also CoDRAG's posture** (pluggable adapters, blueprint-style pipelines, embedded vs standalone modes). It's external validation that the strategy is correct.

### 7. Open + on-prem is a real enterprise wedge
Red Hat picked AI-Q over alternatives because it could run on-prem fully open. **CoDRAG is local-first by default** — this is already a wedge against cloud-only competitors and the talk validates that enterprises actively select on this axis.

---

## The Honest Gap NVIDIA Left Open

Rachel says, almost in passing:

> "Everything we've talked about thus far hasn't been code, but the same idea of connecting code and context together to solve enterprise problems overlaps here as well."

…and then immediately pivots to vulnerability triage. **NVIDIA's blueprints do not treat code as a first-class knowledge type with structural awareness.** They have RAG over PDFs, web search, document corpora — and vulnerability triage as a special case. They do not have a structural code graph.

**CoDRAG's positioning shot:** AI-Q is the agentic knowledge layer for prose, PDFs, and web. **CoDRAG is the agentic knowledge layer for source code, with structural awareness no general RAG system has.** That framing lands in any room that already buys NVIDIA's "five pillars" framing — which is most enterprise AI rooms in 2026.

---

## Concrete CoDRAG Action Items (drafted, not committed)

| Item | Where | Notes |
|---|---|---|
| Shallow / deep / auto parameter on `codrag_search` | `src/codrag/api/routers/search.py`, `mcp_tools.py` | Surface cost asymmetry |
| Hybrid model routing in augmenter pipeline | `src/codrag/services/augmenter.py`, `core/llm_client.py` | Frontier for orchestration, small for per-file |
| Pre-flight scope confirmation for expensive ops | full reindex, deep enrichment, hub-file impact | Match AI-Q's "approve plan" gate |
| "Structural blast radius for security findings" positioning doc | `docs/Phase10_Business_And_Competitive_Research/` | Lean into the CVE wedge |
| `@codrag/langchain` adapter (deep-agent compatible) | `packages/` | Distribution channel — AI-Q ships through LangChain |

---

## Sources

- [GTC 2026 session S81570 page](https://www.nvidia.com/en-us/on-demand/session/gtc26-s81570/)
- [NVIDIA Agent Toolkit announcement (Mar 16, 2026)](https://nvidianews.nvidia.com/news/ai-agents)
- [build.nvidia.com — AI-Q Blueprint](https://build.nvidia.com/nvidia/aiq) *(URL inferred from talk; verify)*
- Local transcript copy noted at top
