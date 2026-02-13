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

import json
import logging
import time
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from codrag.core.embedder import Embedder
from codrag.core.index import ManifestBuildStats, build_manifest, write_manifest
from codrag.core.project_registry import project_index_dir

logger = logging.getLogger(__name__)

class KnowledgeIndex:
    """
    Manages the Knowledge Vector Index.
    
    On-disk format (in project index_dir):
    - knowledge_documents.json: List of knowledge chunks
    - knowledge_embeddings.npy: Float32 vectors
    - knowledge_manifest.json: Metadata
    """
    
    def __init__(self, index_dir: Path, embedder: Embedder):
        self.index_dir = Path(index_dir)
        self.embedder = embedder
        
        self.docs_path = self.index_dir / "knowledge_documents.json"
        self.emb_path = self.index_dir / "knowledge_embeddings.npy"
        self.manifest_path = self.index_dir / "knowledge_manifest.json"
        
        self._documents: Optional[List[Dict[str, Any]]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._manifest: Dict[str, Any] = {}
        
        self._load()

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
        return {
            "exists": self.exists(),
            "count": len(self._documents) if self._documents else 0,
            "last_build_at": self._manifest.get("built_at"),
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

    def build(self, progress_callback=None) -> Dict[str, Any]:
        """
        Build the knowledge index from trace_epistemic.jsonl and trace_modules.jsonl.
        """
        epistemic_path = self.index_dir / "trace_epistemic.jsonl"
        modules_path = self.index_dir / "trace_modules.jsonl"
        
        docs: List[Dict[str, Any]] = []
        
        # 1. Index Epistemic Enrichments
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
                                
                            # Construct rich text representation for embedding
                            text_parts = [
                                f"File: {node_id}",
                                f"Domain: {', '.join(entry.get('domain_tags', []))}",
                                f"Layer: {entry.get('architecture_layer', 'unknown')}",
                                f"Summary: {summary}"
                            ]
                            content = "\n".join(text_parts)
                            
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

        # 2. Index Modules
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
            logger.info("No knowledge documents found to index.")
            return {"count": 0, "status": "empty"}

        # 3. Generate Embeddings
        total = len(docs)
        vectors = []
        
        batch_size = 32
        for i in range(0, total, batch_size):
            batch = docs[i : i + batch_size]
            texts = [d["content"] for d in batch]
            
            if progress_callback:
                progress_callback("embedding", i, total)
                
            try:
                batch_vectors = self.embedder.embed_batch(texts)
                vectors.extend([r.vector for r in batch_vectors])
            except Exception as e:
                logger.error(f"Failed to embed batch {i}: {e}")
                # Pad with zeros or skip? Skipping might align wrong. 
                # Let's fail hard for now or fill zeros.
                # Actually embed_batch should handle retries. If it fails, the build fails.
                raise e

        embeddings = np.array(vectors, dtype=np.float32)

        # 4. Save Atomic
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
                "model": self.embedder.model,
                "version": 1
            }
            with open(temp_dir / "knowledge_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f)
                
            # Atomic swap files (manual since it's not a full dir swap, just files)
            # Actually, let's just move the files into place
            for fname in ["knowledge_documents.json", "knowledge_embeddings.npy", "knowledge_manifest.json"]:
                src = temp_dir / fname
                dst = self.index_dir / fname
                if dst.exists():
                    dst.unlink()
                shutil.move(src, dst)
                
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        self._documents = docs
        self._embeddings = embeddings
        self._manifest = manifest
        
        return manifest
