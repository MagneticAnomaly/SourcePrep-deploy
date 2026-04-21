# Prompt Template Inventory (GAP-5)

All LLM prompt templates used by Prep, by file. This inventory exists
so that prompt auditing, style changes, or structured-output migrations
can be done from a single reference.

**Decision:** Prompts stay co-located with their consumers for now.
Each prompt references data structures specific to its module (e.g.
atlas prompts reference `Segment`, augmenter prompts reference `AugmentationEntry`).
A centralized `prompts/` directory would add indirection without clear benefit
until we need cross-cutting prompt changes (e.g. global JSON schema migration).

---

## `src/prep/core/augmenter.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `SYMBOL_SUMMARY_SYSTEM` | System prompt for symbol augmentation | Short |
| `SYMBOL_SUMMARY_PROMPT` | Per-symbol augmentation (name, type, source, imports → summary + role + confidence) | ~20 |
| `FILE_ROLE_SYSTEM` | System prompt for file classification | Short |
| `FILE_ROLE_PROMPT` | Per-file augmentation (path, symbols, imports, head → summary + role + key_exports + related_files) | ~15 |
| `DOC_ROLE_SYSTEM` | System prompt for markdown doc classification | Short |
| `DOC_ROLE_PROMPT` | Per-doc augmentation (path, sections, refs → summary + doc_type + doc_status + related_files) | ~15 |

## `src/prep/core/atlas.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `_ROOT_ATLAS_SYSTEM_PROMPT` | System prompt for root atlas generation | ~30 |
| `_ROOT_ATLAS_USER_PROMPT` | User prompt with module summaries, hub files, stats | ~40 |
| `_SEGMENT_ATLAS_SYSTEM_PROMPT` | System prompt for per-segment atlas | ~25 |
| `_SEGMENT_ATLAS_USER_PROMPT` | User prompt with segment-specific data | ~30 |

## `src/prep/core/cluster.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `MODULE_SYNTHESIS_PROMPT` | Per-cluster synthesis (member files, domain tags, epistemic data → module summary) | ~80 |

## `src/prep/core/epistemic_enrichment.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `CODE_ENRICHMENT_PROMPT` | Deep reasoning for code files (neighbor context → enriched analysis) | ~50 |
| `DOC_ENRICHMENT_PROMPT` | Deep reasoning for doc files | ~50 |

## `src/prep/core/inferred_edges.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `INFERRED_EDGES_PROMPT` | Cross-language/dynamic edge discovery per file | ~60 |

## `src/prep/core/group_reasoning.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `GROUP_REASONING_PROMPT` | Multi-file group reasoning (related files analyzed together) | ~50 |

## `src/prep/core/batch_prompts.py`
| Constant | Purpose | ~Lines |
|----------|---------|--------|
| `BATCH_AUGMENT_PROMPT` | Batched version of augmentation (multiple files per call) | ~40 |
| `BATCH_ENRICHMENT_PROMPT` | Batched epistemic enrichment | ~40 |
| `BATCH_CLUSTER_PROMPT` | Batched cluster synthesis | ~40 |
| `BATCH_EDGES_PROMPT` | Batched inferred edges | ~40 |
| Various JSON schemas | Structured output schemas for each batch type | ~60 |

---

**Total:** ~20 prompt constants across 7 files, ~600 lines of prompt text.
