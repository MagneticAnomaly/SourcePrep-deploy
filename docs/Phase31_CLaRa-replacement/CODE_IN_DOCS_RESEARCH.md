# Phase 31E: Code-in-Docs Compression Research

> **Date**: 2026-02-20
> **Status**: Research complete, decisions pending
> **Repos tested**: DebateHaus (Next.js marketing), mini-redis (Rust/Tokio)
> **Purpose**: Determine if embedded code samples in documentation hurt LLMLingua-2 compression quality, and evaluate mitigation strategies.

---

## 1. The Question

CoDRAG indexes both code files and documentation files. Documentation often contains embedded code samples (fenced blocks, inline code, CLI commands). When LLMLingua-2 compresses these mixed chunks, does the code content:
- Get mangled (destroying useful code examples)?
- Confuse the BERT classifier (reducing retention of surrounding language)?
- Waste compression budget on content that should be preserved verbatim?

---

## 2. Empirical Findings

### 2.1 How Much Code Lives in Docs?

Measured from real CoDRAG CodeIndex chunks (`documents.json`):

| Repo | Total Chunks | Markdown Chunks | Pure Language | With Code Fences | Code-in-Docs Ratio |
|------|-------------|-----------------|---------------|-------------------|---------------------|
| **DebateHaus** | 114 | 32 | 26 (81%) | **6 (19%)** | **51%** of mixed chars |
| **mini-redis** | 106 | 9 | 7 (78%) | **2 (22%)** | **20%** of mixed chars |

**Per-file breakdown (DebateHaus — worst case):**
| File | Chunks | Fences | Code Chars | Total Chars | Code Ratio |
|------|--------|--------|------------|-------------|------------|
| `docs/DesignPlan/1-hero.md` | 3 | 4 | 1,969 | 3,482 | **57%** |
| `docs/DesignPlan/0-overall-upgrad-plan.md` | 2 | 2 | 1,158 | 3,008 | **38%** |
| `docs/DesignPlan/4-Updated-Trust-paralax.md` | 1 | 1 | 384 | 384 | **100%** |

**Key insight**: Design specification docs are the worst offenders. They contain JavaScript/CSS/JSX examples inline with design rationale. READMEs have code too, but it's mostly short CLI commands (low ratio).

### 2.2 What LLMLingua-2 Does to Code-in-Docs

**Concrete example — CSS in a design doc:**

```
ORIGINAL: `--mouse-x` and `--mouse-y`
COMPRESSED: - mouse - x and - mouse - y
```

```
ORIGINAL: background: radial-gradient(circle 800px at var(--mouse-x)...
COMPRESSED: radial - gradient background layers.
```

```
ORIGINAL: `filter: blur(8px);`
COMPRESSED: (dropped entirely)
```

The BERT classifier trained on meeting transcripts treats CSS/JS tokens as noise. Hyphens, colons, semicolons, curly braces — all get stripped or mangled.

### 2.3 Compression Quality: Pure Language vs Mixed vs Spliced

Tested at rate=0.6 (light compression):

| Category | Chunks | Avg Ratio | Key Terms | File Refs | Latency |
|----------|--------|-----------|-----------|-----------|---------|
| **Pure language docs** (DebateHaus) | 5 | 1.5× | **19%** | 0% | 144ms |
| **Mixed code+lang** (direct) | 6 | 1.7× | **14%** | 0% | 129ms |
| **Mixed code+lang** (splice) | 6 | 10.4× | **11%** | 0% | 119ms |
| **Pure language docs** (mini-redis) | 5 | 1.4× | **34%** | 0% | 120ms |
| **Code w/ heavy doc comments** (mini-redis Rust) | 5 | 1.3× | **41%** | 0% | 139ms |

**Observations:**
1. **Mixed chunks retain fewer key terms (14%) than pure language (19-34%).** Code presence does degrade language retention.
2. **Splice strategy worsens term retention (11%)** — the remaining language text is compressed more aggressively since the code fences are removed, leaving a smaller text at the same rate.
3. **Code with heavy doc comments retains the MOST terms (41%)** — Rust `///` doc comments are pure language and the BERT model handles them well. The code structure around them provides useful context signals.
4. **File refs are 0% across the board** — confirms the known file-path problem from Phase 31C.

### 2.4 The Splice Strategy: Not a Silver Bullet

The "splice" approach (strip code fences → compress language → re-insert fences):

| Metric | Direct | Spliced | Delta |
|--------|--------|---------|-------|
| Compression ratio | 1.7× | 10.4× | **+8.7×** (misleading — code preserved at full size) |
| Key terms retained | 14% | 11% | **-3%** (worse!) |
| File refs retained | 0% | 0% | +0% |

The ratio increase is illusory — it just means the code fences aren't being compressed. The language portions are actually compressed *harder* because they're now a smaller input at the same rate. **Splicing helps code preservation but hurts language retention.**

---

## 3. The Reverse Problem: Doc-Comments in Code

Mini-redis Rust files are ~40-60% documentation (Rust `///` and `//!` comments). These read like natural language paragraphs:

```rust
/// Server state shared across all connections.
///
/// `Db` contains a `HashMap` storing the key/value data and all
/// `broadcast::Sender` values for active pub/sub channels.
///
/// A `Db` instance is a handle to shared state. Cloning `Db` is shallow
/// and only incurs an atomic ref count increment.
```

LLMLingua-2 actually handles these **better** than pure markdown docs (41% key term retention vs 19-34%). The structured comment format and focused technical vocabulary help the BERT classifier make better decisions about what to keep.

**This means the "code files with docs" direction is not a problem — it's actually the best case for our compressor.**

---

## 4. Strategy Evaluation

### Strategy A: Splice Code Fences (Strip → Compress Language → Re-insert)

| Aspect | Assessment |
|--------|------------|
| **Complexity** | Medium — regex fence detection, placeholder management, re-insertion |
| **Code preservation** | ✅ Perfect — code stays verbatim |
| **Language retention** | ❌ Worse (11% vs 14%) — smaller text compressed at same rate |
| **Compression ratio** | Misleading improvement — code uncompressed |
| **Verdict** | **REJECT for now.** Net negative on the metric that matters (language retention). Could revisit if we add rate-adjustment for smaller texts. |

### Strategy B: LLM Summarization in Pipeline (Already Exists)

CoDRAG's pipeline already produces code-free summaries:
- `trace_augmented.jsonl` → LLM summaries of every file (pure language)
- `trace_epistemic.jsonl` → design decisions, patterns (pure language)
- `trace_modules.jsonl` → module descriptions (pure language)
- `knowledge_documents.json` → **0 code fences** (confirmed by analysis)

The KnowledgeIndex is already a "docs without code" layer. When the AI queries CoDRAG, it gets:
1. **CodeIndex results** — raw source with embedded docs (for code understanding)
2. **KnowledgeIndex results** — LLM-generated summaries (pure language, ideal for LLMLingua-2)

**Verdict: The pipeline already solves this at the knowledge layer.** The question is whether we should compress CodeIndex results differently than KnowledgeIndex results. Answer: yes — that's exactly what the dual-compressor architecture does.

### Strategy C: Dual-Channel Routing (Already Planned)

The Phase 31D dual-compressor architecture already addresses this:
- **Code chunks** → LOD Extractor (structural compression, preserves syntax)
- **Language chunks** → LLMLingua-2 (token pruning)
- **Mixed chunks** → Route to code channel (code samples need structural preservation more than the surrounding prose needs compression)

**Verdict: ✅ CORRECT architecture.** Mixed doc-with-code chunks should be routed to the code compressor, not the language compressor. The `classify_rel_path()` function already classifies `.md` files as "docs" — we'd route those to language. But design specs with heavy code should be detectable by fence density.

### Strategy D: Don't Compress Docs At All

| Aspect | Assessment |
|--------|------------|
| **Complexity** | None — simplest option |
| **Risk** | Low — docs are typically 15-28% of chunks |
| **Impact** | If K=5 returns 2 doc chunks + 3 code chunks, skipping doc compression saves ~2-3KB but reduces overall compression by 40% |
| **Verdict** | **VIABLE as a quick win.** For small K values (5-10), doc chunks are short enough that compression adds marginal value. For large K (20+), this becomes expensive. |

### Strategy E: Improve force_tokens for Docs

Add markdown structural tokens to LLMLingua-2's `force_tokens`:
- `**` (bold markers for key terms)
- `##` (headings)
- `` ` `` (inline code)
- `- ` (list items)

**Verdict: ✅ QUICK WIN.** Low complexity, should improve retention of document structure. Won't fix the code-sample problem but will help pure language docs.

---

## 5. Recommendations (Ranked)

### Immediate (Low-Effort, High-Value)

1. **Add markdown force_tokens to LinguaCompressor** — protect `**`, `##`, `` ` ``, `- ` in the force_tokens list. ~5 lines of code.

2. **Skip compression on doc chunks when K ≤ 10** — if the context assembly retrieves ≤10 chunks, don't compress chunks classified as "docs". The savings are marginal and retention loss is real.

### Medium-Term (Dual-Compressor Integration)

3. **Route by fence density, not just file extension** — when the dual-compressor is wired up, classify chunks with >20% code-fence ratio as "code" even if they come from `.md` files. Send them to the LOD/code channel.

4. **Compress KnowledgeIndex results more aggressively** — the knowledge layer is pure language with 0 code fences. It's the ideal target for LLMLingua-2 at standard or even aggressive compression levels.

### Future (If Needed)

5. **Adaptive splice with rate correction** — if splicing is ever revisited, the rate should be adjusted upward (less compression) when the remaining language text is small. E.g., if 60% of a chunk is code fences, apply rate=0.8 to the remaining 40% language text instead of rate=0.6.

6. **Structured code-in-docs tags** — wrap code fences in `<llmlingua, compress=False>` tags to explicitly protect them. LLMLingua-2 supports this natively. Requires preprocessing the chunks before compression.

---

## 6. What We're NOT Doing (Rejected Ideas)

- **Splice strategy as default** — worsens language retention. Reject.
- **Separate compressor for docs** — over-engineered. The dual-compressor (code + language) is sufficient. Adding a third channel for "mixed" adds complexity with no clear benefit.
- **Re-training LLMLingua-2 on code** — out of scope, and LongCodeZip already exists for this. Our LOD Extractor is a better fit for CoDRAG's structured code understanding.
- **Removing code from docs pre-indexing** — destroys valuable context. Design docs with code examples are exactly what developers search for.

---

## 7. Test Artifacts

| File | Purpose |
|------|---------|
| `scripts/analyze_code_in_docs.py` | Quantify code-in-docs patterns across repos |
| `scripts/test_code_in_docs_compression.py` | LLMLingua-2 compression test on real repo chunks |

---

## 8. Connection to Pipeline

The insight that **KnowledgeIndex has 0 code fences** is powerful. Here's how the compression layers map:

```
┌─────────────────────────────────────────────────────┐
│ CoDRAG Context Assembly                             │
│                                                     │
│  CodeIndex results ──► LOD Extractor (code channel) │
│    └─ code files        structural compression      │
│    └─ mixed docs ──►    route by fence density      │
│                                                     │
│  KnowledgeIndex results ──► LLMLingua-2 (language)  │
│    └─ augmentation summaries   0% code, ideal target│
│    └─ epistemic entries                              │
│    └─ module descriptions                            │
│                                                     │
│  Atlas segments ──► No compression (routing only)   │
└─────────────────────────────────────────────────────┘
```

This is cleaner than trying to handle code-in-docs at the compressor level. The pipeline already separates concerns — we just need to route the two index types to different compressors.
