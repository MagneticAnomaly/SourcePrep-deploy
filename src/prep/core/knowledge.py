"""
Knowledge Indexing module (Stage 7).

This module handles the indexing of high-level knowledge artifacts produced by
the Deep Analysis pipeline, specifically:
1. Epistemic Enrichments (trace_epistemic.jsonl)
2. Synthesized Modules (trace_modules.jsonl)

It creates a secondary vector index ('knowledge_index') that complements the
primary source code index ('code_index'). This allows semantic search to match
conceptual descriptions (intent, architecture, responsibility) rather than just
literal code implementation.
"""

import hashlib
import json
import logging
import re
import time
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from prep.core.embedder import Embedder
from prep.core.index import ManifestBuildStats, build_manifest, write_manifest
from prep.core.project_registry import project_index_dir
from prep.services.pipeline.recovery import is_reuse_blocked
from prep.services.pipeline.workers.base import Worker

logger = logging.getLogger(__name__)

class KnowledgeIndex(Worker):
    """
    Manages the Knowledge Vector Index.
    
    On-disk format (in project index_dir):
    - knowledge_documents.json: List of knowledge chunks
    - knowledge_embeddings.npy: Float32 vectors
    - knowledge_manifest.json: Metadata
    """
    
    def __init__(self, index_dir: Path, embedder: Embedder, project_id: str = ""):
        self.index_dir = Path(index_dir)
        self.embedder = embedder
        self.project_id = project_id
        
        self.docs_path = self.index_dir / "knowledge_documents.json"
        self.emb_path = self.index_dir / "knowledge_embeddings.npy"
        self.manifest_path = self.index_dir / "knowledge_manifest.json"
        
        self._documents: Optional[List[Dict[str, Any]]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._manifest: Dict[str, Any] = {}

        # Phase 135: stage 5 (initial) uses the legacy content-hash reuse
        # path; stage 10 (deep) uses the changeset. The worker sets
        # use_changeset=True only for the is_deep call.
        self.use_changeset: bool = False

        self._load()

    def invalidate(self) -> None:
        """Drop in-memory state. The next read forces a fresh _load() from disk.

        Called by scoped reset endpoints so post-reset reads do not see
        stale chunks from prior runs. Disk files are wiped by the reset's
        file-deletion pass, not by this method.
        """
        self._documents = None
        self._embeddings = None
        self._manifest = {}

    def _embedder_model(self) -> str:
        return str(
            getattr(self.embedder, "model", None)
            or getattr(self.embedder, "model_name", None)
            or "unknown"
        )

    @staticmethod
    def _normalize_model_name(raw: str) -> str:
        """Extract a canonical model family from a raw model string.

        Handles:
        - 'nomic-embed-text' (Ollama)
        - 'native:nomic-embed-text-v1.5' (NativeEmbedder)
        - 'nomic-embed-text:latest' (Ollama with tag)
        - Corrupted dict strings from previous manifest bug
          e.g. "{'provider': 'ollama', 'model_name': 'nomic-embed-text', ...}"
        """
        s = raw.strip()
        # Handle corrupted dict-string manifests
        if s.startswith("{") and "model_name" in s:
            # Extract model_name value from dict-like string
            m = re.search(r"'model_name'\s*:\s*'([^']+)'", s)
            if m:
                s = m.group(1)
        # Strip provider prefix: "native:nomic-embed-text-v1.5" → "nomic-embed-text-v1.5"
        if ":" in s and not s.startswith("nomic"):
            s = s.split(":", 1)[1]
        # Strip tag: "nomic-embed-text:latest" → "nomic-embed-text"
        if ":" in s:
            s = s.split(":")[0]
        # Strip version suffix: "nomic-embed-text-v1.5" → "nomic-embed-text"
        # Keep the base family name
        s = re.sub(r"-v\d+(\.\d+)*$", "", s)
        return s.lower()

    @classmethod
    def _models_compatible(cls, a: str, b: str) -> bool:
        """Check if two model strings refer to the same embedding space."""
        if a == b:
            return True
        return cls._normalize_model_name(a) == cls._normalize_model_name(b)

    def _load(self) -> None:
        if not self.docs_path.exists() or not self.emb_path.exists():
            return
            
        try:
            with open(self.docs_path, "r", encoding="utf-8") as f:
                self._documents = json.load(f)
            self._embeddings = np.load(self.emb_path)
            if self.manifest_path.exists():
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self._manifest = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load knowledge index: {e}")
            self._documents = None
            self._embeddings = None

    def exists(self) -> bool:
        return self.docs_path.exists() and self.emb_path.exists()

    def is_loaded(self) -> bool:
        return self._documents is not None and self._embeddings is not None

    def status(self) -> Dict[str, Any]:
        exists = self.exists()
        count = len(self._documents) if self._documents else 0
        built_at = self._manifest.get("built_at")
        
        # Count deep artifacts (Stage 8) vs fast artifacts (Stage 4)
        deep_count = 0
        if self._documents:
            deep_count = sum(1 for d in self._documents if d.get("type") in ("epistemic", "module"))
            
        return {
            # Frontend-expected fields (KnowledgeEmbeddingStatus)
            "enabled": exists and count > 0,
            "running": False,  # Overridden by callers when build is active
            "chunks_embedded": count,
            "deep_chunks_embedded": deep_count,
            "last_run_at": built_at,
            # Legacy / additional fields
            "exists": exists,
            "count": count,
            "last_build_at": built_at,
            "model": self._manifest.get("model", "unknown"),
        }

    def search(self, query: str, k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """Search the knowledge index."""
        if not self.is_loaded():
            self._load()
        if not self.is_loaded():
            return []

        # Embed query
        try:
            embed_query_fn = getattr(self.embedder, "embed_query", None)
            if callable(embed_query_fn):
                q_vec = embed_query_fn(query).vector
            else:
                q_vec = self.embedder.embed(query).vector
            q_vec = np.array(q_vec, dtype=np.float32)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return []

        # Cosine similarity
        # Normalize if not already (Embedder usually returns normalized, but let's be safe if needed)
        # Assuming embedder returns normalized vectors for dot product = cosine sim
        scores = np.dot(self._embeddings, q_vec)
        
        top_k_indices = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_k_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            doc = self._documents[idx]
            results.append({
                "doc": doc,
                "score": score
            })
        return results

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Strip surrogate codepoints that can leak from Rust trace output.

        Surrogates (U+D800..U+DFFF) are invalid in UTF-8 and will crash
        json.dump(), hashlib, and HTTP JSON payloads.  Replace them with
        U+FFFD so the pipeline doesn't abort on a single bad byte.
        """
        return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")

    @staticmethod
    def _content_hash(content: str) -> str:
        """Stable hash of document content for incremental reuse."""
        return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _load_previous_for_reuse(self) -> Dict[str, Any]:
        """Return prior embeddings keyed by doc_id.

        Phase 135: shape depends on `self.use_changeset`.
        - False (stage 5): returns {doc_id: (content_hash, vector)} —
          legacy path with content-hash compare.
        - True  (stage 10): returns {doc_id: vector} — reuse decision
          comes from the changeset, not hash equality.

        Returns empty dict if:
        - no previous index exists,
        - the embedding model has changed, or
        - a reset barrier is active for this project (treat as no prior data
          so build() falls into the full-embed path).
        """
        if self.project_id and is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Knowledge incremental reuse blocked by reset barrier for project %s — "
                "every doc will be re-embedded",
                self.project_id,
            )
            return {}
        # Extract previous model from manifest, handling both formats:
        # - v1 (KnowledgeIndex): {"model": "native:nomic-embed-text-v1.5", ...}
        # - v2 (StageManifest):  {"model": {"provider": "...", "model_name": "..."}, ...}
        #                    or  {"embedding_model": {"provider": "...", "model_name": "..."}, ...}
        raw_model = self._manifest.get("model") or self._manifest.get("embedding_model") or ""
        if isinstance(raw_model, dict):
            # v2 StageManifest format — extract model_name from the dict
            prev_model = raw_model.get("model_name", "")
        else:
            prev_model = str(raw_model)
        cur_model = self._embedder_model()

        # Can't reuse if model changed (different embedding space).
        # Normalize first: Ollama 'nomic-embed-text' and Native
        # 'native:nomic-embed-text-v1.5' produce identical 768-dim vectors.
        if prev_model and not self._models_compatible(prev_model, cur_model):
            logger.info(
                "Knowledge model changed (%s → %s), full re-embed required",
                prev_model, cur_model,
            )
            return {}

        prev_docs = self._documents
        prev_emb = self._embeddings

        # Cold-start: try loading from disk if not in memory
        if (prev_docs is None or prev_emb is None) and self.docs_path.exists() and self.emb_path.exists():
            try:
                with open(self.docs_path, "r", encoding="utf-8") as f:
                    prev_docs = json.load(f)
                prev_emb = np.load(self.emb_path)
                logger.info("Cold-start incremental: loaded %d previous knowledge docs for reuse", len(prev_docs))
            except Exception as e:
                logger.warning("Failed to load previous knowledge index for reuse: %s", e)
                return {}

        if not prev_docs or prev_emb is None or len(prev_docs) != prev_emb.shape[0]:
            return {}

        if self.use_changeset:
            # Stage 10 (deep): no hash compare — return {doc_id: vector}.
            # The per-doc reuse decision in build() will gate on the
            # Changeset (should_process) instead of content equality.
            return {
                doc.get("id", ""): prev_emb[i]
                for i, doc in enumerate(prev_docs)
                if doc.get("id")
            }

        # Stage 5 (legacy): return {doc_id: (content_hash, vector)}.
        reuse_map: Dict[str, tuple] = {}
        for i, doc in enumerate(prev_docs):
            doc_id = doc.get("id", "")
            content = doc.get("content", "")
            if doc_id and content:
                reuse_map[doc_id] = (self._content_hash(content), prev_emb[i])
        return reuse_map

    def build(self, progress_callback=None) -> Dict[str, Any]:
        """
        Build the knowledge index from trace_augmented.jsonl, trace_epistemic.jsonl,
        and trace_modules.jsonl.

        Incremental: reuses embeddings for documents whose content hasn't changed
        since the last build, only re-embedding new or modified documents.
        """
        epistemic_path = self.index_dir / "trace_epistemic.jsonl"
        modules_path = self.index_dir / "trace_modules.jsonl"
        augmented_path = self.index_dir / "trace_augmented.jsonl"

        docs: List[Dict[str, Any]] = []

        logger.info(
            "Knowledge build: index_dir=%s  augmented=%s  epistemic=%s  modules=%s",
            self.index_dir,
            augmented_path.exists(),
            epistemic_path.exists(),
            modules_path.exists(),
        )

        # 1. Index Fast Catalogue (Augmented Data)
        if augmented_path.exists():
            aug_total = 0
            aug_skipped = 0
            try:
                with open(augmented_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            aug_total += 1
                            node_id = entry.get("node_id")
                            summary = entry.get("summary")

                            if not summary:
                                aug_skipped += 1
                                continue

                            # Construct rich text representation for embedding
                            text_parts = [
                                f"File: {node_id}",
                                f"Role: {entry.get('role', 'unknown')}",
                                f"Summary: {summary}"
                            ]
                            content = self._sanitize_text("\n".join(text_parts))

                            docs.append({
                                "id": f"know:aug:{node_id}",
                                "type": "catalogue",
                                "source_id": node_id,
                                "content": content,
                                "metadata": {
                                    "role": entry.get("role"),
                                    "confidence": entry.get("confidence")
                                }
                            })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Error reading augmented file: {e}")
            logger.info(
                "Augmented data: %d entries read, %d with summary, %d skipped (no summary)",
                aug_total, aug_total - aug_skipped, aug_skipped,
            )

        # 2. Index Epistemic Enrichments
        if epistemic_path.exists():
            try:
                with open(epistemic_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            node_id = entry.get("node_id")
                            summary = entry.get("extended_summary") or entry.get("one_liner")

                            if not summary:
                                continue

                            # Synthesize contextual prefix from epistemic metadata
                            context_parts = []
                            layer = entry.get("architecture_layer")
                            if layer and layer != "unknown":
                                context_parts.append(f"Architecture: {layer} layer")
                            subsystem = entry.get("subsystem")
                            if subsystem:
                                context_parts.append(f"Subsystem: {subsystem}")
                            patterns = entry.get("design_patterns")
                            if patterns:
                                context_parts.append(f"Patterns: {', '.join(patterns)}")

                            # Construct rich text representation for embedding
                            text_parts = []
                            if context_parts:
                                text_parts.append(f"Context: {'. '.join(context_parts)}")
                            text_parts.extend([
                                f"File: {node_id}",
                                f"Domain: {', '.join(entry.get('domain_tags', []))}",
                                f"Layer: {entry.get('architecture_layer', 'unknown')}",
                                f"Summary: {summary}"
                            ])
                            content = self._sanitize_text("\n".join(text_parts))

                            docs.append({
                                "id": f"know:epistemic:{node_id}",
                                "type": "epistemic",
                                "source_id": node_id,
                                "content": content,
                                "metadata": {
                                    "domain_tags": entry.get("domain_tags"),
                                    "layer": entry.get("architecture_layer"),
                                    "score": entry.get("epistemic_score")
                                }
                            })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Error reading epistemic file: {e}")

        # 3. Index Modules
        if modules_path.exists():
            try:
                with open(modules_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            mod = json.loads(line)
                            mod_id = mod.get("module_id")
                            name = mod.get("name")
                            purpose = mod.get("purpose")

                            if not purpose:
                                continue

                            text_parts = [
                                f"Module: {name}",
                                f"Purpose: {purpose}",
                                f"Data Flow: {mod.get('data_flow', '')}"
                            ]
                            content = "\n".join(text_parts)

                            docs.append({
                                "id": f"know:module:{mod_id}",
                                "type": "module",
                                "source_id": mod_id,
                                "content": content,
                                "metadata": {
                                    "name": name,
                                    "entry_points": mod.get("entry_points")
                                }
                            })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Error reading modules file: {e}")

        if not docs:
            has_aug = augmented_path.exists()
            has_ep = epistemic_path.exists()
            has_mod = modules_path.exists()
            logger.info(
                "Knowledge embedding skipped — no documents extracted "
                "(augmented=%s, epistemic=%s, modules=%s).",
                has_aug, has_ep, has_mod,
            )
            return {"count": 0, "status": "empty"}

        # ── Incremental reuse: load previous embeddings ─────────────
        reuse_map = self._load_previous_for_reuse()
        can_reuse = bool(reuse_map)

        # Classify docs into reusable vs needs-embedding
        docs_to_embed: List[int] = []  # indices into docs[]
        reused_vectors: Dict[int, np.ndarray] = {}  # index → vector

        for i, doc in enumerate(docs):
            doc_id = doc.get("id", "")
            content = doc.get("content", "")

            if can_reuse and doc_id in reuse_map:
                if self.use_changeset:
                    # Phase 135: stage 10 trusts the changeset. If the
                    # doc's underlying file is unchanged, reuse the
                    # cached vector unconditionally — no hash compare.
                    file_path = self._file_path_for_doc_id(doc_id)
                    if file_path and not self.should_process(file_path):
                        reused_vectors[i] = reuse_map[doc_id]  # plain vector
                        continue
                else:
                    # Stage 5: legacy content-hash compare.
                    prev_hash, prev_vec = reuse_map[doc_id]
                    content_hash = self._content_hash(content)
                    if prev_hash == content_hash:
                        reused_vectors[i] = prev_vec
                        continue

            docs_to_embed.append(i)

        docs_reused = len(reused_vectors)
        docs_new = len(docs_to_embed)
        prev_ids = set(reuse_map.keys()) if can_reuse else set()
        current_ids = {d["id"] for d in docs}
        docs_deleted = len(prev_ids - current_ids)

        if docs_new == 0 and docs_deleted == 0:
            build_mode = "noop"
        elif docs_reused > 0:
            build_mode = "incremental"
        else:
            build_mode = "full"

        logger.info(
            "Knowledge build: %d total docs, %d reused, %d to embed, %d deleted (mode=%s)",
            len(docs), docs_reused, docs_new, docs_deleted, build_mode,
        )

        # ── Pre-flight: verify embedder (only if we need to embed) ──
        if docs_new > 0:
            logger.info("Knowledge build: testing embedder for %d new docs...", docs_new)
            try:
                test_result = self.embedder.embed("embedder pre-flight test")
                if not test_result or not test_result.vector:
                    raise RuntimeError("Embedder returned empty vector")
                logger.info(
                    "Embedder OK (model=%s, dim=%d)",
                    self._embedder_model(),
                    len(test_result.vector),
                )
            except Exception as e:
                model_name = self._embedder_model()
                logger.error("Embedder pre-flight FAILED: %s", e)
                raise RuntimeError(
                    f"Knowledge embedding failed — embedding model '{model_name}' is not responding. "
                    f"Check that your embedding provider is configured and available. Error: {e}"
                ) from e

        # ── Generate Embeddings (only for new/changed docs) ─────────
        total = len(docs)
        vectors: List[Any] = [None] * total  # pre-allocate

        # Fill in reused vectors
        for idx, vec in reused_vectors.items():
            vectors[idx] = vec

        # Embed new/changed docs in batches.
        #
        # F-44: report progress as cumulative work over the *full* document
        # set (cached + new), with baseline = docs_reused.  This activates
        # the 2-tone progress bar in StageProgressBar:
        #   - green section width  = baseline / total = docs_reused / docs_total
        #   - orange section width = (total - baseline) / total = docs_new / docs_total
        #   - orange brightness    = batch_start / docs_new (current rerun progress)
        # Before this change, only (current=batch_start, total=docs_new) were
        # reported, so the dashboard could only render a single-tone "embedding
        # X of Y new docs" bar that ignored the cached portion entirely.
        docs_total = len(docs)
        if docs_to_embed:
            batch_size = 32
            for batch_start in range(0, len(docs_to_embed), batch_size):
                batch_indices = docs_to_embed[batch_start : batch_start + batch_size]
                texts = [docs[i]["content"] for i in batch_indices]

                if progress_callback:
                    # current = cumulative docs accounted for (cached + embedded so far)
                    # total   = full document count (so the bar represents the entire build)
                    # baseline = number of docs reused from cache (the green portion)
                    progress_callback(
                        f"Embedding {batch_start}/{len(docs_to_embed)} new "
                        f"({docs_reused} reused)",
                        docs_reused + batch_start,
                        docs_total,
                        docs_reused,
                    )

                try:
                    batch_vectors = self.embedder.embed_batch(texts)
                    for j, bi in enumerate(batch_indices):
                        vectors[bi] = batch_vectors[j].vector
                except Exception as e:
                    logger.error(f"Failed to embed batch {batch_start}/{len(docs_to_embed)}: {e}")
                    raise

            # Final emit at the end of the embedding loop so the bar lands on
            # 100% before the index is written.
            if progress_callback:
                progress_callback(
                    f"Embedded {len(docs_to_embed)} new docs ({docs_reused} reused)",
                    docs_total,
                    docs_total,
                    docs_reused,
                )
        elif progress_callback:
            # Pure noop build (everything cached) — the entire bar should
            # render as solid green.  baseline == total triggers donePercent=100,
            # stalePercent=0 in StageProgressBar.
            progress_callback(
                f"All {docs_reused} docs reused (no embedding needed)",
                docs_total,
                docs_total,
                docs_reused,
            )

        embeddings = np.array(vectors, dtype=np.float32)

        # ── Save Atomically ─────────────────────────────────────────
        build_id = uuid.uuid4().hex
        temp_dir = self.index_dir.parent / f".know_index_build_{build_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(temp_dir / "knowledge_documents.json", "w", encoding="utf-8") as f:
                json.dump(docs, f)
            np.save(temp_dir / "knowledge_embeddings.npy", embeddings)

            manifest = {
                "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "count": total,
                "model": self._embedder_model(),
                "version": 1,
                "build": {
                    "mode": build_mode,
                    "docs_reused": docs_reused,
                    "docs_embedded": docs_new,
                    "docs_deleted": docs_deleted,
                },
            }
            with open(temp_dir / "knowledge_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f)

            # os.replace is atomic on the same filesystem and overwrites
            # in one syscall — the prior unlink+move pattern left a brief
            # window where knowledge_embeddings.npy was deleted but not
            # yet replaced. A crash in that window lost the embeddings.
            import os as _os
            for fname in ["knowledge_documents.json", "knowledge_embeddings.npy", "knowledge_manifest.json"]:
                src = temp_dir / fname
                dst = self.index_dir / fname
                _os.replace(src, dst)

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        self._documents = docs
        self._embeddings = embeddings
        self._manifest = manifest

        return manifest

    @staticmethod
    def _file_path_for_doc_id(doc_id: str) -> str:
        """Extract the underlying file path from a knowledge doc_id.

        Doc IDs constructed as:
          - know:aug:{node_id}        → node_id = "file:<rel_path>"
          - know:epistemic:{node_id}  → node_id = "file:<rel_path>"
          - know:module:{module_id}   → module IDs don't map to a file;
                                         return "" (caller treats as
                                         "always re-embed").
        """
        if doc_id.startswith("know:aug:") or doc_id.startswith("know:epistemic:"):
            tail = doc_id.split(":", 2)[2]  # strip "know:aug:" / "know:epistemic:"
            if tail.startswith("file:"):
                return tail[len("file:"):]
        return ""
