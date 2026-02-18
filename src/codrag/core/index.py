"""
Core CoDRAG Index implementation.

Provides hybrid semantic + keyword search over documents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pathspec

from .chunking import Chunk, chunk_code, chunk_markdown
from .embedder import Embedder
from .ids import stable_file_hash, stable_file_node_id
from .manifest import ManifestBuildStats, build_manifest, write_manifest
from .repo_policy import ensure_repo_policy
from .repo_profile import DEFAULT_ROLE_WEIGHTS, classify_rel_path
from codrag.api.envelope import ApiException

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """A search result with document and score."""
    doc: Dict[str, Any]
    score: float


class CodeIndex:
    """
    A hybrid semantic + keyword search index for code and documentation.

    On-disk format:
    - documents.json: List of document chunks with metadata
    - embeddings.npy: Float32 embedding vectors (N x dim)
    - manifest.json: Index metadata (model, timestamps, config)
    - fts.sqlite3: Optional SQLite FTS5 keyword index
    """

    def __init__(
        self,
        index_dir: Path | str,
        embedder: Embedder,
    ):
        """
        Initialize a CodeIndex.

        Args:
            index_dir: Directory to store index files
            embedder: Embedder instance for generating vectors
        """
        self.index_dir = Path(index_dir)
        self.embedder = embedder

        self.documents_path = self.index_dir / "documents.json"
        self.embeddings_path = self.index_dir / "embeddings.npy"
        self.manifest_path = self.index_dir / "manifest.json"
        self.fts_path = self.index_dir / "fts.sqlite3"

        self._documents: Optional[List[Dict[str, Any]]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._manifest: Dict[str, Any] = {}

        self._load()
        self._cleanup_stale_builds()

    def _load(self) -> None:
        """Load existing index from disk."""
        if not self.documents_path.exists() or not self.embeddings_path.exists():
            self._documents = None
            self._embeddings = None
            self._manifest = {}
            return

        try:
            with open(self.documents_path, "r") as f:
                self._documents = json.load(f)
            self._embeddings = np.load(self.embeddings_path)
            if self.manifest_path.exists():
                with open(self.manifest_path, "r") as f:
                    self._manifest = json.load(f) or {}
            else:
                self._manifest = {}
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
            self._documents = None
            self._embeddings = None
            self._manifest = {}

    def is_loaded(self) -> bool:
        """Check if an index is loaded and ready for search."""
        return bool(self._documents) and self._embeddings is not None

    _DOC_EXTS = frozenset((".md", ".markdown", ".txt", ".rst", ".adoc"))

    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.is_loaded():
            return {
                "loaded": False,
                "index_dir": str(self.index_dir),
            }

        build = dict(self._manifest.get("build", {}))

        # Backfill chunks_code/chunks_docs if missing (old manifests)
        if "chunks_code" not in build or "chunks_docs" not in build:
            chunks_code = 0
            chunks_docs = 0
            for doc in (self._documents or []):
                sp = str(doc.get("source_path") or "")
                ext = Path(sp).suffix.lower() if sp else ""
                if ext in self._DOC_EXTS:
                    chunks_docs += 1
                else:
                    chunks_code += 1
            build["chunks_code"] = chunks_code
            build["chunks_docs"] = chunks_docs

        return {
            "loaded": True,
            "index_dir": str(self.index_dir),
            "model": self._manifest.get("model", "unknown"),
            "built_at": self._manifest.get("built_at"),
            "roots": self._manifest.get("roots", []),
            "total_documents": len(self._documents or []),
            "embedding_dim": int(self._embeddings.shape[1]) if self._embeddings is not None else 0,
            "config": self._manifest.get("config", {}),
            "build": build,
        }

    def build(
        self,
        repo_root: Path | str,
        roots: Optional[List[str]] = None,
        include_globs: Optional[List[str]] = None,
        exclude_globs: Optional[List[str]] = None,
        max_file_bytes: int = 500_000,
        hard_limit_bytes: int = 100_000_000,
        use_gitignore: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        included_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build the index from a repository.

        Args:
            repo_root: Root directory to index
            include_globs: Glob patterns for files to include (default: ["**/*.md", "**/*.py"])
            exclude_globs: Glob patterns for files to exclude
            max_file_bytes: Files larger than this are summarized/truncated
            hard_limit_bytes: Files larger than this are completely skipped
            progress_callback: Optional callback(file_path, current, total)
            included_paths: Optional list of relative paths (files/folders) to restrict indexing to.
                           When provided and non-empty, only files whose relative path is in this
                           set (or under a folder in this set) will be indexed.

        Returns:
            Build metadata
        """
        # P07-I6: Check disk space (need ~500MB free for safety during atomic swap)
        try:
            # Check space on the drive containing index_dir
            # If index_dir doesn't exist, check parent
            check_path = self.index_dir if self.index_dir.exists() else self.index_dir.parent
            if not check_path.exists():
                check_path = Path.cwd()
            
            usage = shutil.disk_usage(check_path)
            min_free = 500 * 1024 * 1024  # 500 MB
            if usage.free < min_free:
                raise ApiException(
                    status_code=500,
                    code="INSUFFICIENT_SPACE",
                    message=f"Insufficient disk space to build index (free: {usage.free/1024/1024:.1f}MB, required: 500MB)",
                    hint="Free up disk space on the drive containing the index.",
                    details={"free_bytes": usage.free, "required_bytes": min_free, "path": str(check_path)}
                )
        except ApiException:
            raise
        except Exception as e:
            logger.warning(f"Failed to check disk space: {e}")

        repo_root = Path(repo_root).resolve()

        policy = ensure_repo_policy(self.index_dir, repo_root)

        if include_globs is None:
            include_globs = list(policy.get("include_globs") or [])
        if exclude_globs is None:
            exclude_globs = list(policy.get("exclude_globs") or [])

        if not include_globs:
            include_globs = ["**/*.md", "**/*.py"]
        if not exclude_globs:
            # Base excludes
            exclude_globs = [f"**/{d}/**" for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES)]
            # Broad dotfile exclusion
            exclude_globs.append("**/.*")
            # Add specific file patterns
            exclude_globs.extend([
                "**/*.lock",
                "**/*.log",
                "**/.DS_Store",
            ])

        rw = policy.get("role_weights")
        role_weights: Dict[str, float] = dict(DEFAULT_ROLE_WEIGHTS)
        if isinstance(rw, dict) and rw:
            try:
                role_weights = {str(k): float(v) for k, v in rw.items()}
            except Exception:
                role_weights = dict(DEFAULT_ROLE_WEIGHTS)

        prev_docs = self._documents or []
        prev_emb = self._embeddings
        prev_model = str(self._manifest.get("model") or "")
        cur_model = str(getattr(self.embedder, "model", "unknown"))
        can_reuse = bool(prev_docs) and prev_emb is not None and prev_model == cur_model

        # Cold-start incremental: if not loaded in memory but manifest has file_hashes,
        # load previous index from disk so we can reuse unchanged chunks.
        if not can_reuse and prev_model == cur_model:
            manifest_hashes = self._manifest.get("file_hashes")
            if isinstance(manifest_hashes, dict) and manifest_hashes:
                try:
                    docs_path = self.index_dir / "documents.json"
                    emb_path = self.index_dir / "embeddings.npy"
                    if docs_path.exists() and emb_path.exists():
                        with open(docs_path) as f:
                            prev_docs = json.load(f)
                        prev_emb = np.load(emb_path)
                        can_reuse = bool(prev_docs) and prev_emb is not None
                        logger.info("Cold-start incremental: loaded %d previous docs for reuse", len(prev_docs))
                except Exception as e:
                    logger.warning("Failed to load previous index for cold-start incremental: %s", e)
                    prev_docs = []
                    prev_emb = None
                    can_reuse = False

        prev_by_source: Dict[str, List[int]] = {}
        prev_hash_by_source: Dict[str, str] = {}
        if can_reuse:
            for i, d in enumerate(prev_docs):
                sp = str(d.get("source_path") or "")
                if not sp:
                    continue
                prev_by_source.setdefault(sp, []).append(i)

            for sp, idxs in prev_by_source.items():
                h = str(prev_docs[idxs[0]].get("file_hash") or "")
                if h:
                    prev_hash_by_source[sp] = h

        # Load .gitignore if requested
        gitignore_spec = None
        if use_gitignore:
            gitignore_path = repo_root / ".gitignore"
            if gitignore_path.exists():
                try:
                    with open(gitignore_path, "r", encoding="utf-8") as f:
                        gitignore_spec = pathspec.PathSpec.from_lines("gitignore", f)
                    logger.info("Loaded .gitignore from %s", gitignore_path)
                except Exception as e:
                    logger.warning("Failed to parse .gitignore: %s", e)

        # Build exclude pathspec for proper ** support
        exclude_spec = None
        if exclude_globs:
            try:
                exclude_spec = pathspec.PathSpec.from_lines("gitignore", exclude_globs)
            except Exception as e:
                logger.warning("Failed to parse exclude globs: %s", e)

        selected_roots: Optional[List[str]] = None
        if roots:
            cleaned = [str(r).strip().strip("/") for r in roots]
            cleaned = [r for r in cleaned if r]
            selected_roots = cleaned or None

        files: List[Path] = []
        if selected_roots:
            for rel_root in selected_roots:
                rel_path = Path(rel_root)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    continue

                abs_root = (repo_root / rel_path).resolve()
                if not abs_root.is_relative_to(repo_root):
                    continue
                if not abs_root.exists() or not abs_root.is_dir():
                    continue
                for pat in include_globs:
                    files.extend(abs_root.glob(pat))
        else:
            for pat in include_globs:
                files.extend(repo_root.glob(pat))
        files = sorted(set(files))

        filtered_files: List[Path] = []
        for f in files:
            if not f.is_file():
                continue
            try:
                rel_path = str(f.relative_to(repo_root))
            except ValueError:
                continue
            if exclude_spec and exclude_spec.match_file(rel_path):
                continue
            
            # Check gitignore
            if gitignore_spec and gitignore_spec.match_file(rel_path):
                continue
            
            # Guardrail: Strictly skip files above hard limit
            try:
                if f.stat().st_size > hard_limit_bytes:
                    continue
            except OSError:
                continue
                
            filtered_files.append(f)

        # Apply included_paths filter: only index files the user selected in the tree.
        # Supports both exact file paths AND folder paths (includes all descendants).
        if included_paths:
            included_set = set(included_paths)

            def _is_included(rel: str) -> bool:
                if rel in included_set:
                    return True
                # Check if any ancestor folder is in the included set
                parts = rel.split("/")
                for i in range(1, len(parts)):
                    if "/".join(parts[:i]) in included_set:
                        return True
                return False

            before_count = len(filtered_files)
            filtered_files = [
                f for f in filtered_files
                if _is_included(str(f.relative_to(repo_root)))
            ]
            logger.info(
                "included_paths filter: %d -> %d files (from %d selected paths)",
                before_count, len(filtered_files), len(included_set),
            )

        docs: List[Dict[str, Any]] = []
        vectors: List[List[float]] = []
        total_files = len(filtered_files)
        current_file_hashes: Dict[str, str] = {}  # rel_path -> hash for manifest

        files_reused = 0
        files_embedded = 0
        chunks_reused = 0
        chunks_embedded = 0

        # Stats counters
        lines_scanned = 0
        lines_indexed = 0
        files_docs = 0
        files_code = 0
        lines_docs = 0
        lines_code = 0
        chunks_code = 0
        chunks_docs = 0

        # Count deleted files (in previous index but not in current scan)
        current_rel_paths = set()
        for f in filtered_files:
            try:
                current_rel_paths.add(str(f.relative_to(repo_root)))
            except ValueError:
                pass
        files_deleted = len(set(prev_hash_by_source.keys()) - current_rel_paths) if can_reuse else 0

        for i, file_path in enumerate(filtered_files):
            rel_path = str(file_path.relative_to(repo_root))
            role = classify_rel_path(rel_path)

            if progress_callback:
                progress_callback(rel_path, i + 1, total_files)

            # Check size for summarization vs full indexing
            file_size = 0
            try:
                file_size = file_path.stat().st_size
            except OSError:
                pass
            
            is_large = file_size > max_file_bytes
            
            try:
                if is_large:
                    # For large files, read only a prefix for the "summary"
                    # Read first 50KB to get header/intro
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw = f.read(50_000)
                else:
                    raw = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Stats: count lines and classify type
            line_count = raw.count('\n') + 1 if raw else 0
            lines_scanned += line_count
            
            is_doc = file_path.suffix.lower() in (".md", ".markdown", ".txt", ".rst", ".adoc")
            if is_doc:
                files_docs += 1
                lines_docs += line_count
            else:
                files_code += 1
                lines_code += line_count

            file_hash = stable_file_hash(raw) # Note: For large files, hash is based on prefix
            current_file_hashes[rel_path] = file_hash

            if can_reuse:
                prev_hash = prev_hash_by_source.get(rel_path)
                if prev_hash and prev_hash == file_hash:
                    # Even if it's large, if prefix hash matches, we assume reuse is safe
                    # (or we accept the collision risk for perf)
                    idxs = prev_by_source.get(rel_path) or []
                    for di in idxs:
                        prev_doc = dict(prev_docs[int(di)])
                        prev_doc["role"] = role
                        prev_doc["file_hash"] = file_hash
                        docs.append(prev_doc)
                        vectors.append(prev_emb[int(di)].tolist())

                    files_reused += 1
                    chunks_reused += len(idxs)
                    if is_doc:
                        chunks_docs += len(idxs)
                    else:
                        chunks_code += len(idxs)
                    lines_indexed += line_count
                    continue

            files_embedded += 1
            lines_indexed += line_count

            if is_large:
                # Create a single summary chunk
                summary_text = f"[LARGE FILE: {file_size / 1_000_000:.2f} MB - CONTENT TRUNCATED]\n{raw}"
                # We can't really chunk it intelligently if we only have partial content,
                # so we treat it as one big block or maybe a few chunks.
                # Let's just make one summary chunk for now.
                
                # Create a synthetic chunk
                chunk_id = stable_file_hash(rel_path + ":summary")
                
                # Embed the summary
                emb = self.embedder.embed(summary_text[:8000]).vector # Limit embedding input
                
                doc = {
                    "id": chunk_id,
                    "source_path": rel_path,
                    "file_hash": file_hash,
                    "role": role,
                    "section": "FILE_SUMMARY",
                    "span": None,
                    "content": summary_text,
                    "truncated": True,
                    "original_size": file_size
                }
                docs.append(doc)
                vectors.append(emb)
                chunks_embedded += 1
                if is_doc:
                    chunks_docs += 1
                else:
                    chunks_code += 1
                continue

            # Normal processing for small files
            if file_path.suffix.lower() in (".md", ".markdown"):
                chunks = chunk_markdown(raw, source_path=rel_path)
            else:
                chunks = chunk_code(raw, source_path=rel_path)

            for ch in chunks:
                text_for_embed = self._format_chunk_for_embedding(ch, file_hash)
                emb = self.embedder.embed(text_for_embed).vector

                doc = {
                    "id": ch.chunk_id,
                    "source_path": rel_path,
                    "file_hash": file_hash,
                    "role": role,
                    "section": ch.metadata.get("section", ""),
                    "span": ch.metadata.get("span"),
                    "content": ch.content,
                }
                docs.append(doc)
                vectors.append(emb)
                chunks_embedded += 1
                if is_doc:
                    chunks_docs += 1
                else:
                    chunks_code += 1

        if not docs:
            raise RuntimeError("No documents indexed")

        embeddings = np.array(vectors, dtype=np.float32)

        # Atomic build: write to temporary directory first
        build_id = uuid.uuid4().hex
        temp_dir = self.index_dir.parent / f".index_build_{build_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(temp_dir / "documents.json", "w") as f:
                json.dump(docs, f)
            np.save(temp_dir / "embeddings.npy", embeddings)

            try:
                self._rebuild_fts(docs, target_dir=temp_dir)
            except Exception as e:
                logger.warning(f"FTS rebuild failed (continuing without keyword index): {e}")

            build_mode = "full"
            if files_reused > 0 and files_embedded == 0 and files_deleted == 0:
                build_mode = "noop"  # Nothing changed
            elif files_reused > 0:
                build_mode = "incremental"

            manifest = build_manifest(
                model=str(getattr(self.embedder, "model", "unknown")),
                embedding_dim=int(embeddings.shape[1]),
                roots=list(selected_roots or []),
                count=len(docs),
                build=ManifestBuildStats(
                    mode=build_mode,
                    files_total=total_files,
                    files_reused=files_reused,
                    files_embedded=files_embedded,
                    files_deleted=files_deleted,
                    chunks_total=len(docs),
                    chunks_reused=chunks_reused,
                    chunks_embedded=chunks_embedded,
                    chunks_code=chunks_code,
                    chunks_docs=chunks_docs,
                    lines_scanned=lines_scanned,
                    lines_indexed=lines_indexed,
                    files_docs=files_docs,
                    files_code=files_code,
                    lines_docs=lines_docs,
                    lines_code=lines_code,
                ),
                file_hashes=current_file_hashes,
                config={
                    "include_globs": include_globs,
                    "exclude_globs": exclude_globs,
                    "max_file_bytes": max_file_bytes,
                    "role_weights": role_weights,
                    "path_weights": dict(policy.get("path_weights") or {}),
                    "primer": policy.get("primer"),
                },
                built_at=datetime.now(timezone.utc).isoformat(),
            )
            write_manifest(temp_dir / "manifest.json", manifest)

            # Preserve ALL pipeline-produced files in the old directory
            # because the atomic swap will wipe them out.
            _PRESERVE_FILES = [
                # Trace graph (structural)
                "trace_manifest.json",
                "trace_nodes.jsonl",
                "trace_edges.jsonl",
                # Fast Catalogue (augmentation)
                "trace_augmented.jsonl",
                "trace_augment_manifest.json",
                # Relationship Validation
                "trace_inferred_edges.jsonl",
                # Epistemic Enrichment
                "trace_epistemic.jsonl",
                "trace_epistemic_manifest.json",
                # Cluster Synthesis
                "trace_modules.jsonl",
                # Knowledge Embedding
                "knowledge_documents.json",
                "knowledge_embeddings.npy",
                "knowledge_manifest.json",
            ]
            for trace_file in _PRESERVE_FILES:
                old_path = self.index_dir / trace_file
                if old_path.exists():
                    try:
                        shutil.copy2(old_path, temp_dir / trace_file)
                        logger.info(f"Preserved existing trace file: {trace_file}")
                    except Exception as e:
                        logger.warning(f"Failed to preserve trace file {trace_file}: {e}")

            # Preserve pipeline checkpoint directory (rollback data)
            old_cp = self.index_dir / ".checkpoints"
            if old_cp.is_dir():
                try:
                    shutil.copytree(old_cp, temp_dir / ".checkpoints")
                    logger.info("Preserved .checkpoints directory")
                except Exception as e:
                    logger.warning(f"Failed to preserve .checkpoints: {e}")

            # Atomic swap
            self._swap_index_dir(temp_dir)

        except Exception:
            # Cleanup on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

        self._documents = docs
        self._embeddings = embeddings
        self._manifest = manifest

        return manifest

    def _swap_index_dir(self, new_dir: Path) -> None:
        """Atomically swap the new index directory with the current one."""
        # Ensure parent exists
        self.index_dir.parent.mkdir(parents=True, exist_ok=True)
        
        backup_dir = self.index_dir.parent / f".index_backup_{uuid.uuid4().hex}"
        
        # If index_dir exists, move it to backup
        if self.index_dir.exists():
            self.index_dir.rename(backup_dir)
        
        # Move new_dir to index_dir
        new_dir.rename(self.index_dir)
        
        # Cleanup backup
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    def _cleanup_stale_builds(self) -> None:
        """Cleanup stale temporary build directories."""
        if not self.index_dir.parent.exists():
            return
            
        try:
            for item in self.index_dir.parent.iterdir():
                if not item.is_dir():
                    continue
                name = item.name
                if name.startswith(".index_build_") or name.startswith(".index_backup_"):
                    # Check age - if older than 1 hour, delete
                    try:
                        mtime = item.stat().st_mtime
                        age = datetime.now().timestamp() - mtime
                        if age > 3600:  # 1 hour
                            shutil.rmtree(item, ignore_errors=True)
                    except Exception:
                        pass
        except Exception:
            pass

    def _classify_query_intent(self, query: str) -> str:
        q = query.lower()
        tokens = set(re.findall(r"[a-zA-Z0-9_./-]{2,}", q))
        if not tokens:
            return "default"

        docs_tokens = {
            "doc",
            "docs",
            "documentation",
            "readme",
            "guide",
            "tutorial",
            "manual",
            "architecture",
            "design",
            "adr",
            "adrs",
            "decision",
            "decisions",
            "rfc",
            "rfcs",
            "spec",
            "specs",
            "specification",
        }

        tests_tokens = {
            "test",
            "tests",
            "pytest",
            "unittest",
            "jest",
            "vitest",
            "cypress",
            "playwright",
            "e2e",
            "integration",
            "unit",
        }

        debug_tokens = {
            "bug",
            "error",
            "exception",
            "traceback",
            "stack",
            "crash",
            "fix",
            "broken",
            "fails",
            "failing",
        }

        code_tokens = {
            "function",
            "class",
            "module",
            "import",
            "entry",
            "entrypoint",
            "main",
            "api",
            "endpoint",
            "handler",
            "implementation",
        }

        if tokens & tests_tokens:
            return "tests"
        if tokens & docs_tokens:
            return "docs"
        if tokens & debug_tokens:
            return "code"
        if tokens & code_tokens:
            return "code"

        return "default"

    @staticmethod
    def _resolve_path_weight(
        source_path: str, path_weights: Dict[str, float]
    ) -> float:
        """Walk up the path hierarchy to find the most specific weight.

        Exact match wins first, then longest-prefix ancestor.
        Returns 1.0 if no match.
        """
        if source_path in path_weights:
            return path_weights[source_path]
        parts = source_path.split("/")
        for i in range(len(parts) - 1, 0, -1):
            parent = "/".join(parts[:i])
            if parent in path_weights:
                return path_weights[parent]
        return 1.0

    def _intent_role_multipliers(self, intent: str) -> Dict[str, float]:
        if intent == "docs":
            return {"docs": 1.15, "code": 0.98, "tests": 0.98, "other": 0.95}
        if intent == "tests":
            return {"tests": 1.12, "code": 1.0, "docs": 0.95, "other": 0.95}
        if intent == "code":
            return {"code": 1.08, "tests": 1.0, "docs": 0.93, "other": 0.9}
        return {}

    def query_policy(self, query: str) -> Dict[str, Any]:
        intent = self._classify_query_intent(query)
        intent_multipliers = self._intent_role_multipliers(intent)
        role_weights = (self._manifest.get("config") or {}).get("role_weights")
        if not isinstance(role_weights, dict):
            role_weights = {}

        roles = set(role_weights.keys()) | set(intent_multipliers.keys())
        effective: Dict[str, float] = {}
        for r in roles:
            try:
                base = float(role_weights.get(r, 1.0))
            except (TypeError, ValueError):
                base = 1.0
            try:
                mult = float(intent_multipliers.get(r, 1.0))
            except (TypeError, ValueError):
                mult = 1.0
            effective[str(r)] = base * mult

        return {
            "intent": intent,
            "intent_multipliers": intent_multipliers,
            "effective_role_weights": effective,
        }

    def get_indexed_file_paths(self) -> Set[str]:
        """Return set of file paths that have at least one chunk in the index."""
        if self._documents is None:
            return set()
        return {d.get("source_path", "") for d in self._documents if d.get("source_path")}

    def search(
        self,
        query: str,
        k: int = 8,
        min_score: float = 0.15,
    ) -> List[SearchResult]:
        """
        Search the index.

        Args:
            query: Search query
            k: Number of results to return
            min_score: Minimum similarity score

        Returns:
            List of SearchResult objects
        """
        if not self.is_loaded():
            return []

        embed_fn = getattr(self.embedder, "embed_query", self.embedder.embed)
        qv = np.array(embed_fn(query).vector, dtype=np.float32)
        qn = np.linalg.norm(qv)
        if qn == 0.0:
            return []

        emb = self._embeddings
        docs = self._documents
        if emb is None or docs is None:
            return []

        denom = np.linalg.norm(emb, axis=1) * qn
        denom = np.where(denom == 0.0, 1e-8, denom)
        sims = (emb @ qv) / denom

        sims = sims + self._keyword_boosts(query, docs)
        sims = sims + self._fts_boosts(query, docs, limit=max(10, k * 4))

        # Apply primer score boost
        sims = sims + self._primer_boosts(docs)

        intent = self._classify_query_intent(query)
        intent_mult = self._intent_role_multipliers(intent)
        role_weights = (self._manifest.get("config") or {}).get("role_weights")
        if not isinstance(role_weights, dict):
            role_weights = {}

        path_weights = (self._manifest.get("config") or {}).get("path_weights")
        if not isinstance(path_weights, dict):
            path_weights = {}

        if role_weights or intent_mult or path_weights:
            for i, d in enumerate(docs):
                sp = str(d.get("source_path") or "")
                role = str(d.get("role") or "")
                if not role:
                    role = classify_rel_path(sp) if sp else "other"

                w = 1.0
                base = role_weights.get(role)
                if base is not None:
                    try:
                        w *= float(base)
                    except (TypeError, ValueError):
                        pass
                mult = intent_mult.get(role)
                if mult is not None:
                    try:
                        w *= float(mult)
                    except (TypeError, ValueError):
                        pass
                if path_weights and sp:
                    pw = self._resolve_path_weight(sp, path_weights)
                    w *= pw
                if w != 1.0:
                    sims[i] = sims[i] * w

        top_idx = np.argsort(sims)[::-1]
        out: List[SearchResult] = []
        for idx in top_idx:
            score = float(sims[idx])
            if score < min_score:
                break
            out.append(SearchResult(doc=docs[int(idx)], score=score))
            if len(out) >= k:
                break

        return out

    def get_context(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 6000,
        include_sources: bool = True,
        include_scores: bool = False,
        min_score: float = 0.15,
    ) -> str:
        results = self.search(query, k=k, min_score=min_score)
        if not results:
            return ""

        parts: List[str] = []
        total = 0

        for r in results:
            d = r.doc
            header_bits: List[str] = []

            if d.get("section"):
                header_bits.append(str(d.get("section") or ""))
            if include_sources and d.get("source_path"):
                header_bits.append(f"@{d.get('source_path')}")
            if include_scores:
                header_bits.append(f"score={r.score:.3f}")

            if header_bits:
                header = " | ".join(header_bits)
            else:
                header = str(d.get("source_path") or "")

            block = f"[{header}]\n{d.get('content', '')}"

            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    block = block[:remaining] + "..."
                else:
                    break

            parts.append(block)
            total += len(block)

        return "\n\n---\n\n".join(parts)

    def get_context_structured(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 6000,
        min_score: float = 0.15,
    ) -> Dict[str, Any]:
        policy = self.query_policy(query)
        results = self.search(query, k=k, min_score=min_score)
        
        parts: List[str] = []
        chunks_meta: List[Dict[str, Any]] = []
        total = 0
        
        # Check if we should always include primer chunks
        config = self._manifest.get("config") or {}
        primer_cfg = config.get("primer") or {}
        always_include = primer_cfg.get("always_include", False)
        max_primer_chars = int(primer_cfg.get("max_primer_chars", 2000))
        
        # Track which chunk IDs we've already included (to avoid duplicates)
        included_ids: set = set()
        
        if always_include and self.is_loaded():
            primer_chunks = self.get_primer_chunks()
            primer_chars_used = 0
            
            for d in primer_chunks:
                chunk_id = d.get("id")
                if chunk_id:
                    included_ids.add(chunk_id)
                
                header_bits: List[str] = ["PRIMER"]
                if d.get("section"):
                    header_bits.append(str(d.get("section") or ""))
                if d.get("source_path"):
                    header_bits.append(f"@{d.get('source_path')}")
                header = " | ".join(header_bits)
                content = d.get("content", "")
                
                # Respect max_primer_chars budget
                if primer_chars_used + len(content) > max_primer_chars:
                    remaining = max_primer_chars - primer_chars_used
                    if remaining > 100:
                        content = content[:remaining] + "..."
                    else:
                        break
                
                block = f"[{header}]\n{content}"
                parts.append(block)
                total += len(block)
                primer_chars_used += len(content)
                chunks_meta.append({
                    "source_path": d.get("source_path", ""),
                    "section": d.get("section", ""),
                    "score": 1.0,  # Primer chunks always get max score
                    "truncated": content.endswith("..."),
                    "is_primer": True,
                })
        
        if not results and not parts:
            return {
                "context": "",
                "chunks": [],
                "total_chars": 0,
                "estimated_tokens": 0,
                "meta": {"query": query, "policy": policy},
            }

        for r in results:
            d = r.doc
            
            # Skip if this chunk was already included as a primer
            chunk_id = d.get("id")
            if chunk_id and chunk_id in included_ids:
                continue
            
            header_bits: List[str] = []
            if d.get("section"):
                header_bits.append(str(d.get("section") or ""))
            if d.get("source_path"):
                header_bits.append(f"@{d.get('source_path')}")
            header = " | ".join(header_bits) if header_bits else str(d.get("source_path") or "")
            block = f"[{header}]\n{d.get('content', '')}"

            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    block = block[:remaining] + "..."
                    parts.append(block)
                    total += len(block)
                    chunks_meta.append(
                        {
                            "source_path": d.get("source_path", ""),
                            "section": d.get("section", ""),
                            "score": r.score,
                            "truncated": True,
                        }
                    )
                break

            parts.append(block)
            total += len(block)
            chunks_meta.append(
                {
                    "source_path": d.get("source_path", ""),
                    "section": d.get("section", ""),
                    "score": r.score,
                    "truncated": False,
                }
            )

        context_str = "\n\n---\n\n".join(parts)
        return {
            "context": context_str,
            "chunks": chunks_meta,
            "total_chars": total,
            "estimated_tokens": total // 4,
            "meta": {"query": query, "policy": policy},
        }

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chunk by ID."""
        if not self._documents:
            return None
        for d in self._documents:
            if d.get("id") == chunk_id:
                return d
        return None

    def get_context_with_trace_expansion(
        self,
        query: str,
        trace_index: Any,
        k: int = 5,
        max_chars: int = 6000,
        min_score: float = 0.15,
        trace_hops: int = 1,
        trace_direction: str = "both",
        trace_edge_kinds: Optional[List[str]] = None,
        max_additional_nodes: int = 10,
        max_additional_chars: int = 2000,
    ) -> Dict[str, Any]:
        """
        Get context with optional trace-based expansion.
        
        After retrieving initial chunks, expands context by following trace edges
        to find related symbols/files and including their chunks.
        """
        base_result = self.get_context_structured(query, k=k, max_chars=max_chars - max_additional_chars, min_score=min_score)
        
        if trace_index is None or not trace_index.is_loaded():
            base_result["trace_expanded"] = False
            base_result["trace_nodes_added"] = 0
            return base_result
        
        source_paths = set()
        for chunk in base_result.get("chunks", []):
            sp = chunk.get("source_path")
            if sp:
                source_paths.add(sp)
        
        if not source_paths:
            base_result["trace_expanded"] = False
            base_result["trace_nodes_added"] = 0
            return base_result
        
        related_paths: set = set()
        for sp in source_paths:
            file_node_id = stable_file_node_id(sp)
            neighbors = trace_index.get_neighbors(
                file_node_id,
                direction=trace_direction,
                edge_kinds=trace_edge_kinds,
                max_nodes=max_additional_nodes,
            )
            
            for node in neighbors.get("in_nodes", []):
                fp = node.get("file_path")
                if fp and fp not in source_paths:
                    related_paths.add(fp)
            
            for node in neighbors.get("out_nodes", []):
                fp = node.get("file_path")
                if fp and fp not in source_paths:
                    related_paths.add(fp)
        
        if not related_paths:
            base_result["trace_expanded"] = True
            base_result["trace_nodes_added"] = 0
            return base_result
        
        additional_chunks: List[Dict[str, Any]] = []
        additional_chars = 0
        
        for rp in sorted(related_paths):
            if additional_chars >= max_additional_chars:
                break
            
            for d in self._documents or []:
                if d.get("source_path") == rp:
                    content = str(d.get("content") or "")
                    if additional_chars + len(content) > max_additional_chars:
                        continue
                    additional_chunks.append({
                        "source_path": rp,
                        "section": d.get("section", ""),
                        "score": 0.0,
                        "truncated": False,
                        "trace_expanded": True,
                    })
                    additional_chars += len(content)
                    break
        
        if additional_chunks:
            additional_parts: List[str] = []
            for chunk in additional_chunks:
                sp = chunk["source_path"]
                for d in self._documents or []:
                    if d.get("source_path") == sp:
                        header = f"[trace-expanded | @{sp}]"
                        block = f"{header}\n{d.get('content', '')}"
                        additional_parts.append(block)
                        break
            
            if additional_parts:
                base_result["context"] += "\n\n---\n\n" + "\n\n---\n\n".join(additional_parts)
                base_result["chunks"].extend(additional_chunks)
                base_result["total_chars"] += additional_chars
                base_result["estimated_tokens"] = base_result["total_chars"] // 4
        
        base_result["trace_expanded"] = True
        base_result["trace_nodes_added"] = len(additional_chunks)
        return base_result

    def _format_chunk_for_embedding(self, chunk: Chunk, file_hash: str) -> str:
        """Format a chunk for embedding."""
        meta = chunk.metadata
        bits: List[str] = []
        if meta.get("name"):
            bits.append(f"Name: {meta['name']}")
        bits.append(f"Path: {meta.get('source_path', '')}")
        if meta.get("section"):
            bits.append(f"Section: {meta['section']}")
        bits.append(f"Hash: {file_hash}")
        bits.append("")
        bits.append(chunk.content)
        return "\n".join(bits)

    def _keyword_boosts(self, query: str, docs: List[Dict[str, Any]]) -> np.ndarray:
        """Compute keyword-based score boosts."""
        q = query.lower()
        tokens = set(re.findall(r"[a-zA-Z0-9_./-]{3,}", q))
        if not tokens:
            return np.zeros(len(docs), dtype=np.float32)

        boosts = np.zeros(len(docs), dtype=np.float32)
        for i, d in enumerate(docs):
            score = 0.0
            for field in ("source_path", "section"):
                v = str(d.get(field, "")).lower()
                if not v:
                    continue
                for t in tokens:
                    if t in v:
                        score += 0.03
            boosts[i] = min(0.25, score)
        return boosts

    def _primer_boosts(self, docs: List[Dict[str, Any]]) -> np.ndarray:
        """Compute score boosts for primer documents (e.g., AGENTS.md)."""
        config = self._manifest.get("config") or {}
        primer_cfg = config.get("primer") or {}
        
        if not primer_cfg.get("enabled", True):
            return np.zeros(len(docs), dtype=np.float32)
        
        filenames = primer_cfg.get("filenames") or ["AGENTS.md", "CODRAG_PRIMER.md", "PROJECT_PRIMER.md"]
        score_boost = float(primer_cfg.get("score_boost", 0.25))
        
        # Normalize filenames to lowercase for comparison
        primer_names = {f.lower() for f in filenames}
        
        boosts = np.zeros(len(docs), dtype=np.float32)
        for i, d in enumerate(docs):
            sp = str(d.get("source_path") or "")
            if not sp:
                continue
            # Check if file is in repo root (no directory separators) and matches primer name
            if "/" not in sp and "\\" not in sp:
                if sp.lower() in primer_names:
                    boosts[i] = score_boost
        
        return boosts

    def get_primer_chunks(self) -> List[Dict[str, Any]]:
        """Get all chunks from primer documents for always-include functionality."""
        if not self.is_loaded():
            return []
        
        config = self._manifest.get("config") or {}
        primer_cfg = config.get("primer") or {}
        
        if not primer_cfg.get("enabled", True):
            return []
        
        filenames = primer_cfg.get("filenames") or ["AGENTS.md", "CODRAG_PRIMER.md", "PROJECT_PRIMER.md"]
        primer_names = {f.lower() for f in filenames}
        
        primer_chunks = []
        for d in (self._documents or []):
            sp = str(d.get("source_path") or "")
            if not sp:
                continue
            if "/" not in sp and "\\" not in sp:
                if sp.lower() in primer_names:
                    primer_chunks.append(d)
        
        return primer_chunks

    def _ensure_fts_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure the FTS5 table exists."""
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5("
            "chunk_id UNINDEXED, "
            "content, "
            "source_path, "
            "section"
            ")"
        )

    def _rebuild_fts(self, docs: List[Dict[str, Any]], target_dir: Optional[Path] = None) -> None:
        """Rebuild the FTS5 keyword index."""
        out_dir = target_dir or self.index_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        db_path = out_dir / "fts.sqlite3"

        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            self._ensure_fts_schema(conn)
            conn.execute("BEGIN")
            conn.execute("DELETE FROM fts")
            conn.executemany(
                "INSERT INTO fts(chunk_id, content, source_path, section) VALUES (?, ?, ?, ?)",
                [
                    (
                        str(d.get("id") or ""),
                        str(d.get("content") or ""),
                        str(d.get("source_path") or ""),
                        str(d.get("section") or ""),
                    )
                    for d in docs
                ],
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _fts_boosts(self, query: str, docs: List[Dict[str, Any]], limit: int) -> np.ndarray:
        """Compute FTS5-based score boosts."""
        if not self.fts_path.exists():
            return np.zeros(len(docs), dtype=np.float32)

        try:
            conn = sqlite3.connect(str(self.fts_path))
        except Exception:
            return np.zeros(len(docs), dtype=np.float32)

        try:
            self._ensure_fts_schema(conn)
            cur = conn.execute(
                "SELECT chunk_id, bm25(fts) AS rank FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                (query, int(limit)),
            )
            rows = cur.fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()

        if not rows:
            return np.zeros(len(docs), dtype=np.float32)

        id_to_idx = {str(d.get("id")): i for i, d in enumerate(docs)}
        boosts = np.zeros(len(docs), dtype=np.float32)

        for chunk_id, rank in rows:
            i = id_to_idx.get(str(chunk_id))
            if i is None:
                continue
            r = float(rank) if rank is not None else 0.0
            r = max(0.0, r)
            boost = 0.35 / (1.0 + r)
            boosts[i] = max(boosts[i], float(boost))

        return boosts
