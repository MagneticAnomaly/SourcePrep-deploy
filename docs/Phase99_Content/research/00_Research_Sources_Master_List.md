# CoDRAG — Research Sources Master List

Compiled 2026-04-10 from Phases 00, 04, 06, 10, 16, 28, 31, 38, 46, 47, 50, 54, 62, 74, 77, 80, 93, 94. Each entry shows the source, where it was originally cited in the CoDRAG docs, and how CoDRAG used it.

**Legend:** `type` = arxiv / paper / github / blog / whitepaper / docs / spec

---

## 1. arXiv Papers

### 1a. Context window, retrieval & RAG

| Citation | arXiv | Cited in | How CoDRAG used it |
|---|---|---|---|
| Liu et al. — *Lost in the Middle: How Language Models Use Long Contexts* (TACL 2024) | [2307.03172](https://arxiv.org/abs/2307.03172) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | Foundational justification for ranking the most relevant chunks to the edges of the context window; drove conservative context-budget defaults. |
| Chen et al. — *Context Length Alone Hurts LLM Performance Despite Perfect Retrieval* (EMNLP 2025) | [2510.05381](https://arxiv.org/abs/2510.05381) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | Validates CoDRAG's "retrieve-then-solve, don't pad the window" philosophy — reasoning degrades even with 100% retrieval. |
| *Context Discipline and Performance Correlation* (2025) | [2601.11564](https://arxiv.org/abs/2601.11564) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | Documents latency/quality cliffs beyond ~15K words; shaped the per-client char limits in `mcp/server.py:123-138`. |
| Han et al. — *RAG vs. GraphRAG: A Systematic Evaluation and Key Insights* | [2502.11371](https://arxiv.org/abs/2502.11371) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | Validates graph-expansion for multi-hop queries — directly motivates the trace-graph expansion hop in `codrag_search`. |
| Edge et al. — *GraphRAG: From Local to Global* | [2404.16130](https://arxiv.org/abs/2404.16130) | `Phase04_TraceIndex/LLM_TRACE_AUGMENTATION_RESEARCH.md` | Inspired the atlas + module summary layer: multi-stage community summaries rolled into project-level context. |
| *Retrieval-Augmented Code Generation: A Survey* | [2510.04905](https://arxiv.org/abs/2510.04905) | `Phase31_CLaRa-replacement/` | Broad map of code-RAG techniques; used as the lens for positioning CoDRAG inside the repository-level RAG quadrant. |
| *Context Engineering for Large Language Models: Survey* | [2507.13334](https://arxiv.org/abs/2507.13334) | `Phase31_CLaRa-replacement/` | Shaped the umbrella "context engineering" framing used in the marketing/whitepaper narrative. |

### 1b. Code compression, LOD & chunking

| Citation | arXiv | Cited in | How CoDRAG used it |
|---|---|---|---|
| *Stingy Context: 18:1 Hierarchical Code Compression for LLM Auto-Coding* | [2601.19929](https://arxiv.org/abs/2601.19929) | `Phase31_CLaRa-replacement/CODE_COMPRESSION_DEEP_RESEARCH.md` | Primary inspiration for the LOD 0–5 extraction ladder in the context assembler. |
| Zhang et al. — *Hierarchical Context Pruning (HCP)* | [2406.18294](https://arxiv.org/abs/2406.18294) | `Phase31_CLaRa-replacement/` | Validated that signatures-only context preserves ~90% of downstream quality — backbone for LOD 2. |
| *STALL+: Boosting LLM-based Repository-level Code Completion with Static Analysis* | [2406.10018](https://arxiv.org/abs/2406.10018) | `Phase31_CLaRa-replacement/` | Static-analysis-at-prompting pattern; maps onto CoDRAG's trace graph import edges driving dependency-aware retrieval. |
| *In Line with Context: Repository-Level Code Generation via Context Inlining* | [2601.00376](https://arxiv.org/abs/2601.00376) | `Phase31_CLaRa-replacement/` | Flagged as a Phase-2 enhancement — inline callees/callers on top of existing LOD results. |
| Zhang et al. — *cAST: Enhancing Code RAG with Structural Awareness* | [2506.15655](https://arxiv.org/abs/2506.15655) | `Phase31_CLaRa-replacement/`, `Phase93_ChunkingResearch/` | Confirms AST-boundary-respecting chunks outperform naive splits — the basis for CoDRAG's tree-sitter semantic chunker. |
| *LongCodeZip: Compress Long Context for Code Language Models* | [2510.00446](https://arxiv.org/abs/2510.00446) | `Phase31_CLaRa-replacement/COMPRESSION_MODELS_RESEARCH.md` | Two-stage coarse→fine compression evaluated as baseline; rejected (7B model dependency), concept retained for LOD scoring. |
| Wu et al. — *Repoformer: Selective Retrieval for Repository-Level Code Completion* (ICML 2024) | [2403.10059](https://arxiv.org/abs/2403.10059) | `Phase31_CLaRa-replacement/CODE_COMPRESSION_DEEP_RESEARCH.md` | Validates score-gated retrieval ("know when *not* to fetch"); underlies CoDRAG's min-score thresholds. |
| *GraphCoder: Code Completion via Code Context Graph-based Retrieval* | [2406.07003](https://arxiv.org/abs/2406.07003) | `Phase31_CLaRa-replacement/` | Baseline for graph-vs-embedding retrieval comparison; strengthens the case for CoDRAG's trace expansion. |
| *RepoHyper: Search-Expand-Refine on Semantic Graphs* | [2403.06095](https://arxiv.org/abs/2403.06095) | `Phase31_CLaRa-replacement/` | Search → Expand → Refine pipeline maps 1:1 onto `codrag_search` → trace expansion → LOD assembly. |
| *On the Impacts of Contexts on Repository-Level Code Generation* (NAACL 2025) | [2505.09999](https://arxiv.org/abs/2505.09999) | `Phase31_CLaRa-replacement/` | Empirically supports "signatures + docstrings are the highest-ROI context" — validates LOD 2 as default. |
| Zhang et al. — *Long Context Compression with Activation Beacon* (ICLR 2024) | [2401.03462](https://arxiv.org/abs/2401.03462) | `Phase31_CLaRa-replacement/CODE_COMPRESSION_DEEP_RESEARCH.md` | Model-internal KV compression; explicitly noted as *complementary* — CoDRAG compresses pre-prompt, Beacon compresses at inference. |
| *LLMLingua-2: Data Distillation for Prompt Compression* | [2310.05736](https://arxiv.org/abs/2310.05736) | `Phase31_CLaRa-replacement/` | Adopted as the language/docs compressor half of CoDRAG's dual-compressor architecture. |
| *CodeRAG: Supportive Code Retrieval on Bigraph* | [2504.10046](https://arxiv.org/abs/2504.10046) | `Phase31_CLaRa-replacement/` | Bigraph retrieval reference — further evidence for graph-structured code representation. |
| *CLaRa: Bridging Retrieval and Generation with Continuous Latent Reasoning* | [2511.18659](https://arxiv.org/abs/2511.18659) | `Phase31_CLaRa-replacement/tests-old` | Evaluated as a baseline compressor; code/language retention tested at 20–29%, which motivated moving to the dual-compressor design. |

### 1c. Traceability, code graphs & tool descriptions

| Citation | arXiv | Cited in | How CoDRAG used it |
|---|---|---|---|
| *CodeGraph: Code-Centric Knowledge Graphs* | [2308.09687](https://arxiv.org/abs/2308.09687) | `Phase04_TraceIndex/LLM_TRACE_AUGMENTATION_RESEARCH.md` | Early validation of graph-centric code understanding; shaped the TraceIndex node/edge model. |
| *RepoAgent: LLM-Powered Repository-level Code Documentation Generation* | [2402.16667](https://arxiv.org/abs/2402.16667) | `Phase04_TraceIndex/LLM_TRACE_AUGMENTATION_RESEARCH.md` | Inspired the multi-pass LLM augmentation pipeline that enriches each node with synopsis + rationale. |
| *TraceBERT: Pretrained BERT for Traceability Link Recovery* | [2102.04411](https://arxiv.org/abs/2102.04411) | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` | Researched for requirements↔code linking; rejected as too heavy for the CoDRAG architecture but kept as a baseline. |
| *On the Impacts of Contexts on Repository-Level Code Generation* (recent) | [2509.20149](https://arxiv.org/html/2509.20149v1) | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` | Supports the Option 2–4 strategy spectrum (retrieval → reasoning validation) in the traceability framework. |
| *Purpose + Guidelines Pattern for Tool Descriptions* | [2602.14878](https://arxiv.org/abs/2602.14878) | `Phase50_MCP-interfacing/PLAN.md`, `Phase77_Claude-Interoperability/implementation_plan.md` | Directly applied to the MCP tool description style in `src/codrag/mcp_tools.py` — avoids token bloat while keeping agent compliance high. |

---

## 2. Academic Work (non-arXiv or foundational)

| Citation | Venue | Cited in | How CoDRAG used it |
|---|---|---|---|
| Guo et al. — *GraphCodeBERT: Pre-training Code Representations with Data Flow* | ICLR 2021 | `Phase38_FinalTests/README.md` | Motivates why data-flow information improves code understanding — justification for PDG-style edges in the trace graph. |
| Ferrante et al. — *The Program Dependence Graph and its Use in Optimization* | 1987 | `Phase38_FinalTests/README.md` | Classical PDG reference; grounds CoDRAG's combined control-flow + data-flow graph strategy. |
| Traag et al. — *From Louvain to Leiden: Guaranteeing Well-Connected Communities* | 2019 | `Phase74_Concepts/02_Academic_Foundations.md` | Theoretical backing for concept clustering — concepts should emerge via community detection, not forced hierarchy. |
| Nonaka & Takeuchi — *The Knowledge-Creating Company* (SECI model) | 1995 | `Phase74_Concepts/02_Academic_Foundations.md` | Epistemological frame: concepts formalize tacit→explicit knowledge transfer ("externalization" in SECI). |
| Ganter & Wille — *Formal Concept Analysis: Mathematical Foundations* | 1999 | `Phase74_Concepts/02_Academic_Foundations.md` | Mathematical justification for lattice-based concept organization. |
| Khattab & Zaharia — *ColBERT: Efficient Passage Search via Contextualized Late Interaction over BERT* | SIGIR 2020 | `Phase93_ChunkingResearch/` | Token-level matching paradigm referenced when evaluating retrieval-quality upgrades. |
| Cormack, Clarke, Buettcher — *Reciprocal Rank Fusion Outperforms Condorcet* | SIGIR 2009 | `Phase93_ChunkingResearch/` | RRF (K=60) is the hybrid-fusion strategy CoDRAG uses when combining semantic and keyword search. |
| Shahul Es et al. — *RAGAS: Automated Evaluation of Retrieval Augmented Generation* | 2023 | `Phase93_ChunkingResearch/` | Context-precision / context-recall metrics used to evaluate chunking-strategy experiments. |
| Savitzky & Golay — *Smoothing and Differentiation of Data by Simplified Least Squares Procedures* | Analytical Chemistry 1964 | `Phase93_ChunkingResearch/` | Smoothing filter used for semantic-boundary detection on sentence-similarity curves (via gbrain's approach). |
| Suresh et al. — *CoRNStack: Training Data Curation for Code Retrieval* | ICLR 2025 | `Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md` | Rigor check for `nomic-embed-code`; ultimately CoDRAG kept `nomic-embed-text-v1.5` as the CPU default but noted the benchmark. |
| KARMA — *Multi-Agent Knowledge Graph Enrichment and Verification* | NeurIPS 2025 | `Phase62_Pi-research/10_Universal_Adapter_Architecture.md`, `Phase74_Concepts/02_Academic_Foundations.md` | Parallel to CoDRAG's multi-pass enrichment pipeline — used to argue the pattern is academically validated. |
| LLMs4OL Challenge (ISWC) | 2024/2025 | `Phase74_Concepts/02_Academic_Foundations.md` | Establishes SOTA for automated concept/ontology extraction; informed the hybrid embedding+LLM concept-discovery pipeline. |
| Brooks — *Top-Down Program Comprehension* | 1983 | `Phase74_Concepts/02_Academic_Foundations.md` | Cognitive-science justification for top-down reasoning over concepts (hypothesis → evidence). |
| Pennington — *Stimulus Structures and Mental Representations in Expert Comprehension* | 1987 | `Phase74_Concepts/02_Academic_Foundations.md` | Bottom-up comprehension counterpart; CoDRAG's structural trace index supports this mode. |
| Miller — *The Magical Number Seven, Plus or Minus Two* | 1956 | `Phase74_Concepts/02_Academic_Foundations.md` | Cognitive-load rationale for concept clustering (7±2 chunks per view). |
| Nygard — *Architecture Decision Records* | 2011 | `Phase74_Concepts/` | ADR template convention; CoDRAG concepts extend ADRs beyond per-node decisions. |
| NASA SWE-072 — *Bidirectional Traceability Standard* | NASA SWEHB | `Phase04_TraceIndex/CURATED_TRACEABILITY_FRAMEWORK.md` | Grounds the curated traceability framework in an established engineering standard. |
| KIT Publications — *Fine-grained Traceability & Recovery* | KIT Library | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` ([1000178589](https://publikationen.bibliothek.kit.edu/1000178589), [1000178348](https://publikationen.bibliothek.kit.edu/1000178348)) | Academic backing for Option 2 (IR/embedding-based link recovery) in the traceability framework. |

---

## 3. GitHub Repositories

### 3a. Direct architectural influence

| Repo | Cited in | How CoDRAG used it |
|---|---|---|
| [badlogic/pi-mono](https://github.com/badlogic/pi-mono) | `Phase62_Pi-research/01_Pi_Deep_Dive.md`, `05_Recommendations.md` | Mario Zechner's Pi agent — primary study subject for Phase 62. Architecture analysis (extension system, RPC modes) informs CoDRAG's MCP+CLI+skill hybrid distribution strategy. |
| [garrytan/gbrain](https://github.com/garrytan/gbrain) | `Phase93_ChunkingResearch/01_Chunking_Research.md`, `04_Implementation_Summary.md` | Catalyst for Phase 93. Savitzky-Golay semantic boundary detection and RRF hybrid search directly informed CoDRAG's semantic chunker and multi-query retrieval. |
| [yamadashy/repomix](https://github.com/yamadashy/repomix) | `Phase31_CLaRa-replacement/` | Production tree-sitter compression (~70% reduction) validating that LOD extraction is practical at scale. |
| [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) | `Phase31_CLaRa-replacement/COMPRESSION_MODELS_RESEARCH.md` | BERT-classifier token pruning — the language/docs compressor half of the dual-compressor design. |
| [YerbaPage/LongCodeZip](https://github.com/YerbaPage/LongCodeZip) | `Phase31_CLaRa-replacement/COMPRESSION_MODELS_RESEARCH.md` | Evaluated as an off-the-shelf baseline; rejected due to 7B-model requirement incompatible with local-first architecture. |
| [zilliztech/claude-context](https://github.com/zilliztech/claude-context) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | MCP server reporting ~40% token reduction via vector search — external validation of CoDRAG's retrieval-centric architecture. |
| [MemPalace](https://github.com/milla-jovovich/mempalace) | `Phase80_mempalace/01_MemPalace_Integration_Research_Strategy.md` | Studied for AAAK compression dialect, 4-layer memory stack, and temporal graph patterns; informed swarm-communication and staleness-tracking designs. |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | `Phase94_OpenClawResearch/01_OpenClaw_Integration_Research.md` | Evaluated as an MCP consumer for agent-driven code intelligence over messaging platforms. |
| [mergisi/awesome-openclaw-agents](https://github.com/mergisi/awesome-openclaw-agents), [VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills), [freema/openclaw-mcp](https://github.com/freema/openclaw-mcp) | `Phase94_OpenClawResearch/01_OpenClaw_Integration_Research.md` | Ecosystem inventory for the OpenClaw integration study. |

### 3b. Competitors benchmarked

| Repo | Cited in | How CoDRAG used it |
|---|---|---|
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | `Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md`, `Phase31_CLaRa-replacement/` | Production repo-map and LOD 4 signature extraction — the "proof it works" reference used when selling CoDRAG's LOD strategy. |
| [vitali87/code-graph-rag](https://github.com/vitali87/code-graph-rag) | `Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md` | Graph-RAG competitor (Memgraph + AST). Cutting-edge comparison point for CoDRAG's trace-graph approach. |
| [Neverdecel/CodeRAG](https://github.com/Neverdecel/CodeRAG) | `Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md`, `Phase10_Business_And_Competitive_Research/COMPETITOR_LANDSCAPE.md` | Early file-watcher + FAISS competitor — retrieval baseline. |
| [chunkhound/chunkhound](https://github.com/chunkhound/chunkhound) | `Phase00_Initial-Concept/opportunities.md`, `Phase10_Business_And_Competitive_Research/opportunities.md` | Chunking-strategy competitor — benchmark for chunk quality. |
| [zed-industries/zed](https://github.com/zed-industries/zed) | `Phase54_Zed-Antigravity-research/ZED_RESEARCH.md` | IDE integration target with first-class ACP/MCP support. |

### 3c. Traceability baselines

| Repo | Cited in | How CoDRAG used it |
|---|---|---|
| [doorstop-dev/doorstop](https://github.com/doorstop-dev/doorstop) | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` | Existing requirements-to-code traceability tool — benchmark showing the gap CoDRAG closes. |
| [CoEST/TraceLab](https://github.com/CoEST/TraceLab) | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` | Academic traceability link-recovery framework — reference for IR/ML approaches. |
| [tobhey/finegrained-traceability](https://github.com/tobhey/finegrained-traceability) | `Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` | Fine-grained requirement-to-code linking — input for hybrid deterministic + LLM design. |

### 3d. Enterprise / security tooling

| Repo | Cited in | How CoDRAG used it |
|---|---|---|
| [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md`, `SECURITY_RESEARCH_2026.md` | Container/dependency CVE scanner — planned for CoDRAG's Docker images and Python deps. |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | Pre-commit + CI secrets scanner — required for enterprise deployment. |
| [sigstore/cosign](https://github.com/sigstore/cosign) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | Image signing (Sigstore) — selected so enterprise customers can verify build authenticity. |
| [anchore/syft](https://github.com/anchore/syft) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | SBOM generation for SOC2 / FedRAMP compliance. |
| [protectai/llm-guard](https://github.com/protectai/llm-guard) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md`, `SECURITY_RESEARCH_2026.md` | Pre-send LLM input/output filter (PII, prompt injection, secrets) — replaces CoDRAG's custom regex redaction. |
| [microsoft/presidio](https://github.com/microsoft/presidio) | `Phase06_Team_And_Enterprise/SECURITY_RESEARCH_2026.md` | PII detection baseline for data-protection requirements. |
| [DataFog/datafog-python](https://github.com/DataFog/datafog-python) | `Phase06_Team_And_Enterprise/SECURITY_RESEARCH_2026.md` | Alternative PII library evaluated. |
| [NVIDIA-NeMo/Guardrails](https://github.com/NVIDIA-NeMo/Guardrails) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | Evaluated and rejected (too heavy for CoDRAG's use case), but "topical rails" pattern noted. |
| [MaxMLang/pytector](https://github.com/MaxMLang/pytector) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | Lightweight DeBERTa/DistilBERT prompt-injection detector — candidate to scan repo content pre-index. |
| [ossf/scorecard](https://github.com/ossf/scorecard) | `Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md` | Design inspiration for CoDRAG's Security Health Score (same aggregate-checks-to-score pattern). |

### 3e. UI & visualization dependencies studied

| Repo | Cited in | How CoDRAG used it |
|---|---|---|
| [tremorlabs/tremor](https://github.com/tremorlabs/tremor) | `Phase02_Dashboard/README.md` | Selected as the dashboard charting library. |
| [piccolomo/plotext](https://github.com/piccolomo/plotext) | `Phase18_DataVisualization/README.md` | Terminal plotting candidate for CLI output. |
| [react-grid-layout/react-grid-layout](https://github.com/react-grid-layout/react-grid-layout) | `Phase15_modular-design/README.md` | Draggable layout engine for the dashboard. |

---

## 4. Whitepapers, Blog Posts & Vendor Research

| Source | Cited in | How CoDRAG used it |
|---|---|---|
| [Anthropic — *Contextual Retrieval*](https://www.anthropic.com/news/contextual-retrieval) (Sept 2024) | `Phase93_ChunkingResearch/` | Directly adopted: prepend file-level context to chunks before embedding, cited as 49% failure-rate reduction. |
| [Jina AI — *Late Chunking*](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) (Oct 2024) | `Phase93_ChunkingResearch/` | Considered for long-context code files; kept as exploratory. |
| [Chroma Research — *Context Rot: How Increasing Input Tokens Impacts LLM Performance*](https://research.trychroma.com/context-rot) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | 18-LLM evaluation showing distractor-similarity compounds degradation — justification for CoDRAG's `min_score` defaults. |
| [Databricks — *Long Context RAG Performance of LLMs*](https://www.databricks.com/blog/long-context-rag-performance-llms) | `Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md` | RAG saturation at 4K–32K tokens — confirms the 6K–8K conservative defaults. |
| [Nomic — *Nomic Embed Code* announcement](https://www.nomic.ai/blog/posts/introducing-nomic-embed-code) (Mar 2025) | `Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md` | Benchmarked but not adopted as default (kept text-v1.5 for CPU footprint). |
| [Voyage AI — *Voyage Code 3*](https://blog.voyageai.com/2024/12/04/voyage-code-3/) (Dec 2024) | `Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md` | 32-dataset evaluation — reference point for Matryoshka / quantization trade-offs. |
| [Mario Zechner — *Building the Pi Coding Agent*](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/) | `Phase62_Pi-research/05_Recommendations.md` | Architecture philosophy from Pi's creator — informs CoDRAG's hybrid distribution rationale. |
| [Mario Zechner — *What if you don't need MCP?*](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/) | `Phase62_Pi-research/05_Recommendations.md` | Counterargument against MCP token cost — used honestly in Phase 62 to weigh the MCP-first decision. |
| [Sourcegraph — *Announcing SCIP*](https://sourcegraph.com/blog/announcing-scip) | `Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md` | Code-indexing protocol benchmark; Sourcegraph as long-standing competitor. |
| [Augment Code](https://www.augmentcode.com/) | `Phase10_Business_And_Competitive_Research/DEEP_DIVE_AUGMENT_SOURCEGRAPH.md` | Real-time index strategy and security posture study. |
| [AuthZed — *MCP Security Breaches Timeline*](https://authzed.com/blog/timeline-mcp-breaches) | `Phase06_Team_And_Enterprise/SECURITY_RESEARCH_2026.md`, `ENTERPRISE_ADMIN_DESIGN.md` | MCP incident tracking — feeds CoDRAG's MCP threat model. |
| [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) | `Phase06_Team_And_Enterprise/SECURITY_RESEARCH_2026.md` | CoDRAG's security architecture explicitly maps to these categories. |

---

## 5. Standards, Protocols & Specs

| Spec | Cited in | How CoDRAG used it |
|---|---|---|
| [Model Context Protocol (MCP)](https://modelcontextprotocol.io) | `Phase05_MCP_Integration/`, `Phase54_Zed-Antigravity-research/ZED_RESEARCH.md`, `Phase62_Pi-research/10_Universal_Adapter_Architecture.md` | Primary integration surface (Layer 3) — CoDRAG ships an MCP server as its main interface. |
| [Claude Code docs — memory, MCP, hooks, skills, settings, best-practices](https://code.claude.com/docs/en/) | `Phase77_Claude-Interoperability/implementation_plan.md` | Direct source for CLAUDE.md generation, MCP tool naming, skill frontmatter, and auto-approve permission shape. |
| [Agent Client Protocol (ACP)](https://agentclientprotocol.com) | `Phase54_Zed-Antigravity-research/ZED_RESEARCH.md` | Zed-backed standard — CoDRAG's multi-editor integration target. |
| [A2A Protocol](https://a2a-protocol.org) | `Phase62_Pi-research/10_Universal_Adapter_Architecture.md` | Google/Linux-Foundation agent-to-agent protocol — identified as a future Layer 4 target. |
| [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) | `Phase62_Pi-research/10_Universal_Adapter_Architecture.md`, `Phase85_SARIF-Enrichment/` | SARIF-in/SARIF-out enrichment is a shipped `codrag_audit` capability. |
| [OCSF](https://ocsf.io) | `Phase62_Pi-research/10_Universal_Adapter_Architecture.md` | AWS/Splunk event schema — alternative audit export format. |
| [agents.md](https://agents.md/) | `Phase00_Initial-Concept/TRACE_INDEX_RESEARCH.md`, `AI_INFRASTRUCTURE_RESEARCH.md`, `Phase67_AGENTS/` | Emerging convention for agent-facing context files — CoDRAG auto-generates AGENTS.md via `rules_generator.py`. |
| [MCP Registry](https://github.com/modelcontextprotocol/registry) | `Phase54_Zed-Antigravity-research/ZED_RESEARCH.md` | Discovery layer for publishing the CoDRAG MCP server. |

---

## 6. Infrastructure & Models Evaluated

| Project | Cited in | How CoDRAG used it |
|---|---|---|
| [Ollama](https://ollama.com) | `Phase47_BYOK-research/`, throughout | Local LLM runtime — the default BYOK backend for CoDRAG's augmentation pipeline. |
| [Apple CLaRa-7B-Instruct](https://huggingface.co/apple/CLaRa-7B-Instruct) | `Phase00_Initial-Concept/AI_INFRASTRUCTURE_RESEARCH.md` | Evaluated as a compression model; rejected in favor of Ollama's model flexibility. |
| Nomic Embed text-v1.5 / code | `Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md`, `Phase31_CLaRa-replacement/` | Default embedding models (ONNX) — text-v1.5 is the CPU default. |

---

## Notes on usage

- **For the whitepaper / marketing site:** Sections 1a–1c, 2, and 4 are the highest-priority citations — they're the sources that can defend specific claims about CoDRAG's retrieval / compression / chunking quality.
- **For the security & enterprise decks:** Section 3d + OWASP + AuthZed entries are the spine.
- **For investor / competitive positioning:** Sections 3a + 3b + Section 4 vendor blogs.
- **Verify before publishing:** A handful of arXiv IDs in §1a–b encode post-2025 publication years (`2601.xxxxx`, `2602.xxxxx`, `2511.xxxxx`). These are preserved verbatim from the phase docs; re-verify the canonical DOI/URL before quoting in public material.
- **Maintenance:** When a new research-labeled phase is added (`PhaseNN_*Research*`), its external citations should be folded into this file. The generator pattern: `grep -n "arxiv.org\|github.com\|doi.org" docs/PhaseNN_* | filter CoDRAG-own URLs`.
