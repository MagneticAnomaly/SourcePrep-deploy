# Phase 38: Final Tests, Audit & Improvement Roadmap

## Overview

This phase documents the comprehensive health audit of CoDRAG's pipeline across 4 test repositories, identifies systemic weaknesses in the trace graph, clustering, and search systems, and proposes 30 improvement techniques drawn from computer science research, industry practice, and novel ideas. Each technique is evaluated for impact, feasibility, and implementation path.

## Audit Summary (from Phase 37)

Full audit: [../Phase37_Auto-v-LiveSync/REPO_HEALTH_AUDIT.md](../Phase37_Auto-v-LiveSync/REPO_HEALTH_AUDIT.md)

| Repo | Grade | Core Issue |
|------|-------|------------|
| TEST (44 files, Next.js) | B | Sparse graph, 1 module |
| TEST2 (135 files, docs+website) | B+ | `<think>` leak in atlas (**fixed**) |
| TEST3 (248 files, multi-platform) | B- | Auth mega-module (136/248 files), search relevance miss |
| slim-php (135 files, PHP framework) | C+ | **0 cross-file edges**, 20% epistemic settled |

### Fixes Already Applied
- **AT-1**: `<think>` token stripping in `_postprocess()` — `src/codrag/core/atlas.py`
- **T-2**: Trace validator handles `ext:*` nodes — `scripts/run_tests.py`

### Test Harness Created
- `scripts/repo_health_check.py` — 6 automated checks with pass/fail assertions

---

## Part I: Trace Graph Robustness — 10 Techniques

The trace graph is the backbone of CoDRAG. Currently it suffers from:
- **61-100% of files have 0 neighbors** (no cross-file edges resolved)
- **All import edges to external packages are dangling** (no resolution)
- **PHP/Ruby/Swift/C have 0 cross-file edges** (parser doesn't resolve `use`/`require`)
- **Even TypeScript repos only resolve ~16% of imports to in-project files**

### TG-1: Two-Pass Symbol Table Resolution (Rust)

**What**: Build a project-wide symbol table in Pass 1 (collect all exported symbols + their file paths), then resolve import targets in Pass 2 by looking up the symbol table.

**Research basis**: This is the standard technique used by compilers (rustc, tsc, javac). The key insight from CodeGraph (GitHub/ChrisRoyse) and Dossier (Reddit/r/rust) is that tree-sitter can extract enough information for ~80% resolution without full type checking.

**How it works**:
1. **Pass 1 (Collect)**: Walk all files, extract every exported symbol with its qualified name and file path. Build a `HashMap<QualifiedName, FilePath>`.
2. **Pass 2 (Resolve)**: For each import statement, look up the imported name in the symbol table. If found, create an edge from the importing file to the target file (not `ext:*`).
3. **Fallback**: If not found in the symbol table, create the existing `ext:*` node.

**Language-specific resolution**:
- **TypeScript/JS**: `import { X } from './foo'` → resolve `./foo` relative to current file, check `.ts`, `.tsx`, `.js`, `/index.ts` extensions
- **Python**: `from codrag.core import CodeIndex` → map `codrag.core` to `src/codrag/core/__init__.py` or `src/codrag/core.py`
- **PHP**: `use Slim\Routing\Router` → map namespace `Slim\Routing` to `Slim/Routing/Router.php` via PSR-4 autoload rules from `composer.json`
- **Go**: `import "github.com/gin-gonic/gin"` → external; `import "./internal/router"` → resolve relative
- **Rust**: `use crate::core::trace` → resolve `crate::` to project root, map `::` to `/`
- **Java/Kotlin**: `import com.example.Service` → map package to directory path

**Impact**: HIGH — would fix T-1 (PHP 0 edges), T-3 (dangling edges), and T-4 (0-neighbor files). This single technique addresses the #1 systemic issue.

**Complexity**: MEDIUM — Rust implementation, ~500-800 LOC. Each language needs a resolver function, but the framework is shared. The two-pass architecture fits naturally into the existing `codrag-parser` crate.

**Verdict**: ✅ **MUST DO** — highest ROI improvement possible.

---

### TG-2: Co-Change Analysis (Git History Mining)

**What**: Analyze git commit history to discover files that frequently change together. Files modified in the same commit have an implicit dependency even if no import exists.

**Research basis**: "Mining Software Repositories" (MSR) is a well-established field. Ball et al. (1997) "If Your Version Control System Could Talk" showed that co-change patterns reveal architectural dependencies invisible to static analysis. Zimmermann et al. (2005) "Mining Version Histories to Guide Software Changes" demonstrated 70%+ precision.

**How it works**:
1. Run `git log --name-only --pretty=format:"COMMIT:%H"` to extract commit→files mapping
2. For each pair of files that appear in ≥N commits together, compute Jaccard similarity: `|commits(A) ∩ commits(B)| / |commits(A) ∪ commits(B)|`
3. Emit `co_changes` edges with confidence = Jaccard score for pairs above threshold (e.g., 0.3)
4. Weight by recency: recent co-changes count more than ancient ones (exponential decay)

**Implementation**: Can be done in Rust (`git2` crate) or Python (`subprocess` + `git log`). ~200 LOC.

**Impact**: MEDIUM-HIGH — adds edges where static analysis fails (config files, CSS↔component, test↔implementation). Especially valuable for languages where import resolution is hard (Ruby, PHP).

**Complexity**: LOW — no tree-sitter needed, pure git history analysis.

**Verdict**: ✅ **SHOULD DO** — cheap to implement, language-agnostic, complementary to TG-1.

---

### TG-3: String-Based Import Heuristic Resolution

**What**: For unresolved imports, use fuzzy path matching against the project's file listing to find likely targets. If `import Router from '@/components/Router'` doesn't resolve via the symbol table, search for files named `Router.tsx`, `Router.ts`, `router.py`, etc.

**Research basis**: This is a pragmatic technique used by IDE indexers (VSCode, IntelliJ) as a fallback when full resolution fails. The insight is that developers name files after the symbols they export ~85% of the time.

**How it works**:
1. Extract the "leaf name" from the import path (e.g., `Router` from `@/components/Router`)
2. Search the project file listing for files matching `{leaf_name}.{ext}` or `{leaf_name}/index.{ext}`
3. If exactly 1 match → high confidence edge. If 2-3 matches → lower confidence edges to all.
4. Store as inferred edges with `method: "string_heuristic"` metadata.

**Implementation**: ~100 LOC in Rust, operates on the file manifest.

**Impact**: MEDIUM — catches the 60-80% of imports that are simple relative paths or aliased paths that the full resolver misses. Won't help with deeply aliased paths (webpack aliases, tsconfig paths).

**Complexity**: LOW

**Verdict**: ✅ **SHOULD DO** — quick win layered on top of TG-1.

---

### TG-4: Data Flow Graph from AST (Intra-File Call Chains)

**What**: Extract function call chains within files to build a data flow graph. When `functionA()` calls `functionB()` in the same file, add a `calls` edge. When a function references a class/type from another file's import, add a `uses_type` edge.

**Research basis**: GraphCodeBERT (Guo et al., ICLR 2021) showed that data flow information dramatically improves code understanding tasks. Their "data flow graph" extracted from AST captures variable-to-variable dependencies. Program Dependency Graphs (PDG) from Ferrante et al. (1987) combine control flow and data flow for deeper understanding.

**How it works**:
1. For each function body, walk the AST looking for `call_expression` nodes
2. Resolve the callee name to a symbol in the same file or an imported symbol
3. Emit `calls` edges between the caller and callee symbols
4. For type references in signatures, emit `uses_type` edges

**Implementation**: ~300-500 LOC per language in Rust. The tree-sitter queries are straightforward (`call_expression`, `member_expression`).

**Impact**: MEDIUM — enriches the graph with behavioral relationships (who calls whom), not just structural ones (who imports whom). Enables better trace expansion for "how does X work?" queries.

**Complexity**: MEDIUM — need to handle each language's call syntax.

**Verdict**: ✅ **SHOULD DO** — significant quality improvement, natural extension of current parser.

---

### TG-5: Type-Aware Inheritance/Implementation Edges

**What**: Extract class inheritance (`extends`), interface implementation (`implements`), and trait bounds to create explicit `inherits` and `implements` edges in the graph.

**Research basis**: Standard OOP analysis. The current inferred_edges system already generates `implements` edges via LLM, but these should come from static analysis for reliability and zero cost.

**How it works**:
1. When parsing `class Foo extends Bar`, create an `inherits` edge from Foo's symbol to Bar's symbol
2. When parsing `class Foo implements IBar`, create an `implements` edge
3. Resolve the parent/interface name via the symbol table (TG-1) to get cross-file edges
4. For Rust: `impl Trait for Type` → `implements` edge
5. For Go: implicit interface satisfaction → harder, may need LLM

**Implementation**: ~100-200 LOC per language, builds on TG-1's symbol table.

**Impact**: MEDIUM — critical for OOP codebases (Java, TypeScript, PHP). Reveals the "backbone" of class hierarchies.

**Complexity**: LOW-MEDIUM — straightforward tree-sitter extraction.

**Verdict**: ✅ **SHOULD DO** — the data is already in the AST, just need to extract it.

---

### TG-6: Export/Re-Export Graph (Barrel File Resolution)

**What**: Track `export` and re-export statements to resolve barrel files (index.ts files that re-export from multiple modules). Currently barrel files are opaque — importing from `./components` doesn't resolve to the individual component files.

**Research basis**: This is a TypeScript/JavaScript-specific but extremely common pattern. ~40% of TS/JS imports go through barrel files. Rollup and Vite perform "tree-shaking" by resolving these.

**How it works**:
1. When parsing `export { Router } from './Router'`, create an `re_exports` edge from the barrel file to the source file
2. When resolving `import { Router } from './components'`, first check if `./components/index.ts` exists, then follow re-export edges to find the actual source
3. Build a "re-export graph" as part of the symbol table

**Implementation**: ~200 LOC in the TypeScript parser, integrated with TG-1.

**Impact**: MEDIUM — specifically fixes the "barrel file problem" that causes many TS/JS imports to resolve only to the index file, not the actual implementation.

**Complexity**: LOW-MEDIUM

**Verdict**: ✅ **SHOULD DO** (for TS/JS repos) — common pattern, direct fix.

---

### TG-7: Semantic Similarity Edges (Embedding-Based)

**What**: Compute embedding vectors for each file's content and add `semantically_similar` edges between files whose embeddings are within a cosine similarity threshold. This creates edges between files that are conceptually related even without any import relationship.

**Research basis**: This is the core idea behind semantic code search. Feng et al. (2020) "CodeBERT" showed that pre-trained code embeddings capture functional similarity. The CoDRAG CodeIndex already computes these embeddings — we just need to cross-reference them.

**How it works**:
1. After building the CodeIndex embeddings, compute pairwise cosine similarity between all file embeddings
2. For each file, find the top-K most similar files (K=3-5)
3. If similarity > threshold (e.g., 0.7), emit a `semantically_similar` edge with confidence = similarity score
4. Filter out trivially similar files (same directory, same naming pattern)

**Implementation**: ~100 LOC in Python, uses existing embeddings. Could also use Rust with `ndarray`.

**Impact**: MEDIUM — creates a "semantic overlay" on the structural graph. Especially valuable when static analysis fails (no imports between files that are conceptually related, like a test file and its implementation).

**Complexity**: LOW — embeddings already exist.

**Verdict**: 🤔 **CONSIDER** — useful but risk of noisy edges. Should be low-weight in trace expansion.

---

### TG-8: Directory Proximity Edges

**What**: Add implicit edges between files in the same directory with a distance-decaying weight. Files in `src/api/` are likely related to each other even without imports.

**Research basis**: Aniche et al. (2016) "The Effectiveness of Supervised Machine Learning Algorithms in Predicting Software Refactoring" found that directory co-location is one of the strongest predictors of file relatedness. File system layout reflects developer's mental model of architecture.

**How it works**:
1. For each file, find all other files in the same directory
2. Add `co_located` edges with weight = 1.0 / (directory_depth + 1)
3. Optionally extend to sibling directories with lower weight
4. Filter: only add if both files are "code" files (not config, not tests)

**Implementation**: ~50 LOC, trivial.

**Impact**: LOW-MEDIUM — provides baseline connectivity for repos where import resolution fails entirely. Acts as a safety net so the graph is never fully disconnected.

**Complexity**: VERY LOW

**Verdict**: ✅ **SHOULD DO** — trivial to implement, prevents the "0 neighbors for all files" failure mode.

---

### TG-9: Cross-Language Bridge Edges

**What**: Detect cross-language boundaries (e.g., Python backend ↔ TypeScript frontend, Rust FFI ↔ Python bindings) and create explicit bridge edges.

**Research basis**: Multi-language projects are increasingly common. The challenge is that no single parser can resolve cross-language imports. However, common patterns are detectable:
- API routes defined in Python/Go → consumed by TypeScript `fetch()` calls
- FFI bindings: Rust `#[pyfunction]` → Python import
- gRPC/Proto definitions → generated code in multiple languages
- GraphQL schemas → typed clients

**How it works**:
1. Detect API route definitions (Flask/FastAPI `@app.route`, Express `app.get`)
2. Detect API consumers (fetch/axios calls with matching URL patterns)
3. Detect FFI boundaries (PyO3 `#[pyfunction]`, WASM exports, JNI)
4. Create `api_bridge` or `ffi_bridge` edges between the defining and consuming files

**Implementation**: ~300-500 LOC, heuristic-based, language-specific detectors.

**Impact**: HIGH for multi-language repos, LOW for single-language. TEST3 (Python+TypeScript+Swift) would benefit significantly.

**Complexity**: MEDIUM-HIGH — many patterns to detect.

**Verdict**: 🤔 **CONSIDER** — high impact for specific repos, but high implementation cost. Defer until TG-1/TG-2 are done.

---

### TG-10: Incremental Graph Updates (File-Level Granularity)

**What**: When a file changes, only re-parse that file and update its nodes/edges in the graph, rather than rebuilding the entire trace. This isn't about robustness per se, but about making the graph stay fresh, which prevents staleness-related quality degradation.

**Research basis**: Tree-sitter itself supports incremental parsing. The key challenge is maintaining consistency of the symbol table and cross-file edges when one file changes.

**How it works**:
1. Watch for file changes (already done via `fsnotify`)
2. Re-parse only the changed file
3. Diff the old and new `ParseResult` for that file
4. Remove old nodes/edges, insert new ones
5. Re-resolve any import edges that were affected (imports FROM the changed file, or imports TO symbols that moved)

**Implementation**: ~500 LOC in Rust, complex but well-bounded.

**Impact**: MEDIUM — keeps the graph fresh between full rebuilds. Reduces the "stale graph" problem that degrades search quality over time.

**Complexity**: HIGH — incremental graph updates with consistency guarantees are hard.

**Verdict**: 🔄 **DEFER** — important for UX but not for graph quality. Do after TG-1.

---

## Part II: Clustering Improvements — 10 Techniques

The current clustering algorithm (Pass 3) groups files by primary `domain_tag` then runs connected-component analysis. Issues:
- **Mega-modules**: AUTH in TEST3 has 136/248 files (55%)
- **Duplicate names**: Two "Ui" modules, two "Http" modules
- **Single-tag grouping**: Primary tag determines cluster, ignoring tag overlap
- **No max-size constraint**: Clusters grow unbounded

### CL-1: Leiden Algorithm (Replace Primary-Tag Grouping)

**What**: Replace the current "group by primary domain tag + connected components" with the Leiden algorithm, a state-of-the-art community detection algorithm that optimizes modularity.

**Research basis**: Traag et al. (2019) "From Louvain to Leiden: guaranteeing well-connected communities" (Nature Scientific Reports). Leiden guarantees that all detected communities are connected (Louvain does not) and produces higher-quality partitions. It runs in O(n log n) time.

**Why better than current approach**:
- Current approach uses a single tag as the grouping key → biased by tag ordering
- Leiden uses the full edge structure to find natural communities
- Leiden automatically determines the number of clusters (no preset)
- Guarantees connected communities (no disconnected subgraphs within a cluster)

**How it works**:
1. Build an undirected weighted graph from trace edges (imports, calls, co-changes)
2. Run Leiden with resolution parameter γ to control cluster granularity
3. For each community, compute domain tags from member files' epistemic entries
4. Name the cluster using the most common domain tag

**Implementation**: Use `igraph` (Python, C backend) or `grappolo` (Rust). ~150 LOC to integrate.

**Impact**: HIGH — directly fixes the mega-module problem by finding natural community boundaries.

**Complexity**: LOW — well-tested library, drop-in replacement.

**Verdict**: ✅ **MUST DO** — direct fix for C-1 (mega-modules).

---

### CL-2: Max Module Size Constraint with Recursive Splitting

**What**: Add a hard cap (e.g., 40% of project files or 50 files, whichever is smaller). When a cluster exceeds the cap, recursively split it using the same algorithm at higher resolution.

**Research basis**: Hierarchical community detection. Newman & Girvan (2004) showed that recursive bisection produces meaningful sub-communities.

**How it works**:
1. After initial clustering, check each cluster's size
2. If size > max_threshold, re-run Leiden on the subgraph with higher resolution
3. Repeat until all clusters are below threshold
4. Name sub-clusters with parent_name + distinguishing tag

**Implementation**: ~50 LOC on top of CL-1.

**Impact**: HIGH — guarantees no mega-modules.

**Complexity**: VERY LOW (given CL-1)

**Verdict**: ✅ **MUST DO** — trivial guard rail.

---

### CL-3: Multi-Tag Affinity Matrix

**What**: Instead of grouping by primary tag only, build an affinity matrix where the similarity between two files is the Jaccard similarity of their full tag sets, combined with edge connectivity.

**Research basis**: Multi-label clustering. Schapire & Singer (2000) showed that using all labels (not just the primary) dramatically improves classification quality.

**How it works**:
1. For each pair of enriched files (i, j), compute:
   - `tag_sim(i,j) = |tags(i) ∩ tags(j)| / |tags(i) ∪ tags(j)|`
   - `edge_sim(i,j) = 1 if directly connected, 0.5 if 2-hop, 0 otherwise`
   - `affinity(i,j) = α * tag_sim + β * edge_sim`
2. Use this affinity matrix as input to spectral clustering or Leiden
3. The multi-tag similarity naturally groups files that share multiple domain concepts

**Implementation**: ~100 LOC in Python using numpy.

**Impact**: MEDIUM-HIGH — eliminates the "first tag wins" bias that causes the AUTH mega-module.

**Complexity**: LOW

**Verdict**: ✅ **SHOULD DO** — better signal than current single-tag approach.

---

### CL-4: Directory-Aware Clustering (Structural Priors)

**What**: Use directory structure as a prior/constraint for clustering. Files in `src/api/` should preferentially cluster together. The directory tree provides a strong architectural signal that the current algorithm ignores.

**Research basis**: Bavota et al. (2013) "Using Structural and Semantic Measures to Improve Software Modularization" found that combining structural (directory) and semantic (topic) information produces the best modularization.

**How it works**:
1. Compute a "directory distance" between files: 0 for same dir, 1 for sibling dirs, 2 for cousin dirs, etc.
2. Add directory distance as a penalty term in the affinity matrix: `affinity(i,j) *= exp(-λ * dir_distance(i,j))`
3. This biases clustering toward directory-cohesive modules while still allowing cross-directory clusters when edges are strong

**Implementation**: ~50 LOC, trivial.

**Impact**: MEDIUM — prevents absurd cross-directory mega-clusters like AUTH (which spans `backend/`, `mobile/`, `docs/`).

**Complexity**: VERY LOW

**Verdict**: ✅ **SHOULD DO** — cheap, effective structural prior.

---

### CL-5: Architecture-Layer Separation

**What**: Enforce that test files and implementation files are in different clusters. Currently, slim-php's "Routing" module contains both `Slim/Routing/*.php` and `tests/Routing/*.php`.

**How it works**:
1. Before clustering, partition files into layers: `implementation`, `test`, `config`, `docs`
2. Run clustering independently within each layer
3. Link test clusters to their implementation clusters via naming heuristics
4. Present as: "Routing (67 impl files)" + "Routing Tests (23 test files)"

**Implementation**: ~80 LOC.

**Impact**: MEDIUM — cleaner module boundaries.

**Complexity**: LOW

**Verdict**: ✅ **SHOULD DO** — simple rule-based improvement.

---

### CL-6: Embedding-Based Clustering (Semantic Modules)

**What**: Use file-level embeddings from the CodeIndex to cluster files by semantic similarity, independent of domain tags or edge structure.

**Research basis**: Topic modeling meets code. Linares-Vásquez et al. (2015) "How do developers react to API deprecations?" used LDA topic models on code. Modern embeddings (CodeBERT, StarCoder) are far more powerful.

**How it works**:
1. Compute centroid embedding for each file (average of its chunk embeddings)
2. Run K-means or HDBSCAN on file embeddings
3. Use the resulting clusters as an alternative or complementary signal to tag-based clustering
4. Merge with tag-based clusters: if embedding-cluster and tag-cluster agree → high confidence; if they disagree → investigate

**Implementation**: ~100 LOC using existing embeddings + sklearn/hdbscan.

**Impact**: MEDIUM — provides a "second opinion" on clustering that doesn't depend on LLM-generated tags.

**Complexity**: LOW

**Verdict**: 🤔 **CONSIDER** — useful as validation signal, but may not add much over CL-1+CL-3.

---

### CL-7: Cluster Stability Scoring

**What**: Compute a stability score for each cluster by measuring how much it changes under perturbation (removing random edges or files). Unstable clusters are likely artifacts.

**Research basis**: Ben-Hur et al. (2002) "A Stability Based Method for Discovering Structure in Clustered Data." Clustering stability is a well-studied concept in ML — stable clusters represent real structure, unstable ones are noise.

**How it works**:
1. Run clustering N times (e.g., 10) with slight perturbations (remove 10% of edges randomly)
2. Compute the Adjusted Rand Index (ARI) between each pair of clusterings
3. For each cluster, measure how often its members stay together across runs
4. Flag clusters with stability < 0.5 as "weak" and consider splitting or merging

**Implementation**: ~100 LOC.

**Impact**: LOW-MEDIUM — diagnostic tool, not a direct improvement.

**Complexity**: LOW

**Verdict**: 🔄 **DEFER** — nice diagnostic but not urgent.

---

### CL-8: Hierarchical Module Tree

**What**: Instead of flat modules, build a hierarchy: top-level domains → sub-modules → leaf files. Display as a tree in the dashboard and use for multi-level atlas segmentation.

**Research basis**: Hierarchical Software Clustering (Maqbool & Babri, 2007). Most real software has a natural hierarchy (domain → module → class → function) that flat clustering loses.

**How it works**:
1. Run Leiden at multiple resolution levels (low → high)
2. At each level, clusters from the previous level become "super-nodes"
3. Build a tree: Level 0 = entire project, Level 1 = 3-5 domains, Level 2 = 10-20 modules, Level 3 = individual files
4. Each level has its own summary

**Implementation**: ~200 LOC.

**Impact**: MEDIUM — better atlas segmentation, better ambient context.

**Complexity**: MEDIUM

**Verdict**: 🤔 **CONSIDER** — valuable for large projects, overkill for small ones.

---

### CL-9: Cluster Name Deduplication

**What**: Detect and resolve duplicate cluster names by appending distinguishing suffixes.

**How it works**:
1. After synthesis, check for duplicate names
2. For duplicates, find the distinguishing characteristic (directory, architecture layer, primary file)
3. Rename: "Http" → "Http (Core)" and "Http (Testing)", or "Ui (Mobile)" and "Ui (Web)"

**Implementation**: ~30 LOC.

**Impact**: LOW — cosmetic but improves readability.

**Complexity**: VERY LOW

**Verdict**: ✅ **SHOULD DO** — trivial fix.

---

### CL-10: LLM-Free Structural Clustering Fallback

**What**: For repos where the LLM-based tag assignment fails or is unavailable (Free tier), provide a purely structural clustering algorithm based on edge connectivity + directory structure.

**How it works**:
1. Build weighted graph from edges (imports=1.0, calls=0.8, co_changes=0.6, co_located=0.3)
2. Run Leiden on this graph
3. Name clusters from directory paths (majority directory of members)
4. No LLM needed at any step

**Implementation**: ~100 LOC, reuses CL-1.

**Impact**: MEDIUM — makes clustering available to all tiers.

**Complexity**: LOW

**Verdict**: ✅ **SHOULD DO** — important for Free tier.

---

## Part III: Search & Context Improvements — 10 Techniques

The search system uses embedding-based retrieval + trace expansion + atlas routing. Issues:
- **S-1**: TEST3 Spotify OAuth query returns wrong file (CodeIndex too sparse)
- **S-2**: CodeIndex only covers 2-4% of files for large repos
- **Trace expansion produces 0 additional nodes** when graph has no cross-file edges

### SR-1: Hybrid Retrieval (Sparse + Dense)

**What**: Combine BM25 (keyword matching) with embedding-based (semantic) search. Use Reciprocal Rank Fusion (RRF) to merge results.

**Research basis**: Sawarkar et al. (2024) "Blended RAG" showed that hybrid retrieval (BM25 + dense) outperforms either alone by 10-20% on code search tasks. The key insight: embeddings capture semantics but miss exact identifiers; BM25 captures identifiers but misses semantics.

**How it works**:
1. **Dense path**: Current embedding search (cosine similarity)
2. **Sparse path**: BM25 index over chunk text. When query contains identifiers (e.g., `SpotifyOAuth`), BM25 will find exact matches that embedding search misses
3. **Fusion**: RRF score = Σ 1/(k + rank_i) where k=60 (standard). Return top-N by fused score
4. The BM25 index can be built in Rust using `tantivy` (Lucene-equivalent) for blazing speed

**Impact**: HIGH — directly fixes S-1. The query "Spotify OAuth authentication" would find `spotify_oauth.py` via BM25 exact match even if embedding similarity is lower.

**Complexity**: MEDIUM — need to integrate a BM25 library. `tantivy` (Rust) is the best option.

**Verdict**: ✅ **MUST DO** — single biggest search quality improvement.

---

### SR-2: Full-Project Search (Knowledge Index Fallback)

**What**: When the CodeIndex (user-selected files) returns poor results, fall back to searching the KnowledgeIndex (all project files).

**How it works**:
1. Search CodeIndex first (current behavior)
2. If top result score < threshold (e.g., 0.4), or fewer than K results, ALSO search KnowledgeIndex
3. Merge results, preferring CodeIndex hits but supplementing with KnowledgeIndex
4. Mark KnowledgeIndex results as "project-wide" in the context

**Impact**: HIGH — fixes S-2 for large repos where CodeIndex only covers 2-4% of files.

**Complexity**: LOW — both indexes already exist, just need fallback logic.

**Verdict**: ✅ **MUST DO** — simple but high-impact.

---

### SR-3: Query-Time Trace Expansion with Inferred Edges

**What**: Ensure that trace expansion at search time uses ALL edge types (static imports + inferred calls/implements + co-changes) with appropriate weights.

**Current state**: `_load_python()` in `trace.py` already loads inferred edges (line 1680-1694). But the Rust backend (`_load_rust()`) may not. Need to verify and fix.

**How it works**:
1. Verify Rust `load_trace()` loads `trace_inferred_edges.jsonl`
2. Weight edges by type during expansion: `imports` = 1.0, `calls` = 0.9, `implements` = 0.8, `co_changes` = 0.6, `semantically_similar` = 0.4
3. Use weighted scores in the neighbor ranking during trace expansion

**Impact**: MEDIUM — improves trace expansion quality, especially for repos with few static edges.

**Complexity**: LOW

**Verdict**: ✅ **SHOULD DO** — ensures all pipeline work pays off at search time.

---

### SR-4: Multi-Stage Re-Ranking (Cross-Encoder)

**What**: After initial retrieval (bi-encoder), re-rank top-N results using a cross-encoder model that sees query + chunk together.

**Research basis**: Nogueira & Cho (2019) "Passage Re-ranking with BERT" showed cross-encoders improve retrieval accuracy by 15-30% over bi-encoders alone. The two-stage approach (fast bi-encoder → precise cross-encoder) is standard in production search systems.

**How it works**:
1. Retrieve top-20 chunks via current embedding search
2. For each chunk, compute cross-encoder score: `score = CrossEncoder(query, chunk_text)`
3. Re-rank by cross-encoder score, return top-5
4. Use a small cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`, 22M params, runs in <50ms)

**Impact**: MEDIUM-HIGH — catches semantic misranking (like audio_analysis.py outranking spotify_oauth.py).

**Complexity**: MEDIUM — need to integrate a cross-encoder model. Could use ONNX Runtime (already a dependency for NativeEmbedder).

**Verdict**: 🤔 **CONSIDER** — significant quality improvement but adds latency (~50ms). Consider as opt-in for quality-sensitive queries.

---

### SR-5: Query Decomposition for Complex Questions

**What**: For complex multi-part queries, decompose into sub-queries and search for each independently, then merge results.

**Research basis**: Huang et al. (2024) "LQR: Layered Query Retrieval" showed that decomposing complex queries improves multi-hop retrieval accuracy by 25%.

**How it works**:
1. Detect multi-part queries (contains "and", multiple concepts, >10 words)
2. Decompose: "How does Spotify OAuth work and how is the playlist generated?" → ["Spotify OAuth authentication flow", "playlist generation algorithm"]
3. Search each sub-query independently
4. Merge results, dedup by file, boost files that appear in multiple sub-query results

**Implementation**: Can use the existing LLM or simple rule-based decomposition.

**Impact**: MEDIUM — helps with complex questions but most queries are simple.

**Complexity**: LOW-MEDIUM

**Verdict**: 🤔 **CONSIDER** — useful for power users, not critical.

---

### SR-6: Atlas-Guided Pre-Filtering

**What**: Use the atlas routing system to pre-filter chunks before embedding search, reducing the search space to relevant segments.

**Current state**: Atlas routing already exists (`atlas_routing.json` + `route_query()`). The context endpoint uses it to boost segment file paths. The improvement is to make routing a hard filter (not just a boost) when confidence is high.

**How it works**:
1. Route query to segments (existing)
2. If top segment score > 0.7 (high confidence), ONLY search within that segment's files
3. If no segment scores > 0.7, search all files (current behavior)
4. This reduces noise from irrelevant segments

**Impact**: MEDIUM — reduces false positives from unrelated segments.

**Complexity**: VERY LOW — adjustment to existing logic.

**Verdict**: ✅ **SHOULD DO** — simple tuning of existing system.

---

### SR-7: Context-Aware Chunk Boundaries

**What**: Improve chunking to respect code structure (function/class boundaries) rather than fixed-size splits. A chunk should never split a function in half.

**Research basis**: Agentic Chunking (Li et al., 2023) showed that structure-aware chunking improves retrieval by 15-20% on code tasks.

**How it works**:
1. Use the trace graph's symbol spans to define chunk boundaries
2. Each chunk = one symbol (function, class, method) + its docstring
3. For large symbols (>500 lines), split at inner function boundaries
4. For non-code files (markdown, config), use existing paragraph-based chunking

**Impact**: MEDIUM-HIGH — better chunks = better embeddings = better retrieval.

**Complexity**: MEDIUM — need to integrate trace spans into the chunking pipeline.

**Verdict**: ✅ **SHOULD DO** — improves both embedding quality and retrieved context quality.

---

### SR-8: Adaptive K Selection

**What**: Instead of fixed k=5, dynamically adjust K based on query complexity and result score distribution.

**How it works**:
1. Start with K=10 candidates
2. If top score >> second score (ratio > 2x), return only top 1-2 (high confidence single result)
3. If scores are close (ratio < 1.3x), return more results (diverse answers)
4. If all scores are low (< 0.3), expand K and lower min_score threshold

**Implementation**: ~50 LOC.

**Impact**: LOW-MEDIUM — avoids both over-fetching (diluting context) and under-fetching (missing relevant results).

**Complexity**: LOW

**Verdict**: 🤔 **CONSIDER** — nice refinement, not critical. Already partially implemented (`adaptive_k.py`).

---

### SR-9: Graph-Augmented Retrieval (GAR)

**What**: After initial retrieval, use the trace graph to find structurally related chunks that the embedding search missed, then re-rank the combined set.

**Research basis**: This is the core CoDRAG idea (trace expansion), but the current implementation is limited by graph sparsity. With TG-1 fixing the graph, this becomes much more powerful.

**How it works**: Already implemented in `get_context_with_trace_expansion()`. The improvement is:
1. Expand trace hops from 1 to 2 when graph density is high
2. Use edge weights (import > call > co_change > co_located) for expansion priority
3. Include symbol-level expansion (not just file-level): if query matches `handleAuth()`, expand to its callers/callees specifically

**Impact**: HIGH (conditional on TG-1 fixing the graph)

**Complexity**: LOW — adjustment to existing code.

**Verdict**: ✅ **SHOULD DO** (after TG-1)

---

### SR-10: Personalized Retrieval (User Focus Weighting)

**What**: Boost search results from files/directories the user has explicitly focused on (included_paths). This leverages the existing focus system to personalize search.

**Current state**: The `path_weights` system exists but may not be fully integrated into search scoring.

**How it works**:
1. Load user's path_weights from project config
2. During search, boost chunks from high-weight paths: `final_score = base_score * (1 + weight_bonus)`
3. This means if a user is focused on `src/api/`, queries will preferentially return API files

**Impact**: LOW-MEDIUM — improves relevance for users who actively manage their focus areas.

**Complexity**: VERY LOW

**Verdict**: ✅ **SHOULD DO** — trivial integration of existing signals.

---

## Part IV: Evaluation & Implementation Path

### Impact × Feasibility Matrix

```
                    LOW Complexity    MEDIUM Complexity    HIGH Complexity
HIGH Impact         TG-8 (dir prox)  TG-1 (symbol table)  TG-9 (cross-lang)
                    CL-2 (max size)  SR-1 (hybrid BM25)   TG-10 (incremental)
                    SR-2 (fallback)  TG-4 (data flow)
                    CL-1 (Leiden)    TG-2 (co-change)

MEDIUM Impact       TG-3 (string)    SR-4 (cross-encoder)  CL-8 (hierarchy)
                    CL-3 (multi-tag) TG-5 (inheritance)
                    CL-4 (dir-aware) SR-7 (chunk bounds)
                    CL-5 (layer sep) TG-6 (barrel files)
                    CL-9 (dedup)
                    CL-10 (no-LLM)
                    SR-3 (inf edges)
                    SR-6 (atlas pre-filter)
                    SR-9 (GAR boost)
                    SR-10 (focus wt)

LOW Impact          SR-8 (adaptive K) CL-7 (stability)
                                      SR-5 (decompose)
                                      CL-6 (embed cluster)
                                      TG-7 (semantic edges)
```

### Recommended Implementation Path

#### Sprint 1: Foundation Fixes (1-2 weeks)
1. **TG-1**: Two-pass symbol table resolution in Rust — THE critical fix
2. **TG-8**: Directory proximity edges — safety net, trivial
3. **CL-2**: Max module size constraint — trivial guard rail
4. **CL-9**: Cluster name deduplication — trivial

#### Sprint 2: Search Quality (1 week)
5. **SR-1**: Hybrid BM25+dense retrieval via `tantivy`
6. **SR-2**: Knowledge index fallback for sparse CodeIndex
7. **SR-6**: Atlas-guided pre-filtering (tune existing)

#### Sprint 3: Graph Enrichment (1-2 weeks)
8. **TG-2**: Co-change analysis from git history
9. **TG-4**: Intra-file call chain extraction
10. **TG-5**: Type inheritance/implementation edges
11. **TG-3**: String-based import heuristic resolution

#### Sprint 4: Clustering Overhaul (1 week)
12. **CL-1**: Leiden algorithm (replace current clustering)
13. **CL-3**: Multi-tag affinity matrix
14. **CL-4**: Directory-aware clustering prior
15. **CL-5**: Architecture-layer separation

#### Sprint 5: Polish & Advanced (1-2 weeks)
16. **TG-6**: Barrel file resolution (TS/JS only)
17. **SR-3**: Weighted trace expansion with all edge types
18. **SR-7**: Structure-aware chunk boundaries
19. **SR-9**: Graph-augmented retrieval boost
20. **CL-10**: LLM-free structural clustering

#### Future / Research
21. **SR-4**: Cross-encoder re-ranking
22. **TG-7**: Semantic similarity edges
23. **TG-9**: Cross-language bridge edges
24. **CL-8**: Hierarchical module tree
25. **TG-10**: Incremental graph updates

---

## TODO List

### Immediate (this session)
- [x] Create Phase38 documentation
- [x] Research 30 improvement techniques
- [ ] Prototype TG-1 (two-pass symbol table) design in Rust
- [ ] Prototype CL-2 (max module size) implementation

### Sprint 1
- [ ] TG-1: Implement two-pass symbol table resolution
  - [ ] TypeScript/JavaScript resolver
  - [ ] Python resolver
  - [ ] PHP PSR-4 resolver
  - [ ] Go resolver
  - [ ] Rust resolver
  - [ ] Java/Kotlin resolver
- [ ] TG-8: Directory proximity edges
- [ ] CL-2: Max module size constraint
- [ ] CL-9: Cluster name deduplication
- [ ] Run health check on all repos, verify improvement

### Sprint 2
- [ ] SR-1: Integrate tantivy for BM25 index
- [ ] SR-1: Implement RRF fusion
- [ ] SR-2: Knowledge index fallback logic
- [ ] SR-6: Tune atlas pre-filtering threshold

### Sprint 3
- [ ] TG-2: Git co-change analysis
- [ ] TG-4: Call chain extraction per language
- [ ] TG-5: Inheritance/implementation edges
- [ ] TG-3: String-based import heuristic

### Sprint 4
- [ ] CL-1: Leiden algorithm integration
- [ ] CL-3: Multi-tag affinity matrix
- [ ] CL-4: Directory-aware clustering
- [ ] CL-5: Architecture-layer separation

### Sprint 5
- [ ] TG-6: Barrel file resolution
- [ ] SR-3: Weighted trace expansion
- [ ] SR-7: Structure-aware chunking
- [ ] SR-9: Graph-augmented retrieval boost
- [ ] CL-10: LLM-free clustering fallback

---

*Created: 2026-02-23*
*Author: CoDRAG development team*
