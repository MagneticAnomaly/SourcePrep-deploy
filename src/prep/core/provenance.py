"""
Provenance Helpers — Capture version info, file hashes, and quality metrics.

Provides utilities for tracking:
- Prep version
- Rust engine version (if available)
- File hashes (blake3)
- Quality metric aggregation from JSONL files
- File metadata (size, item count)
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_prep_version() -> str:
    """Get the current Prep version."""
    try:
        import prep
        return getattr(prep, "__version__", "unknown")
    except Exception:
        return "unknown"


def get_engine_version() -> Optional[str]:
    """Get the Rust engine version if available."""
    try:
        import prep_engine  # type: ignore
        return getattr(prep_engine, "__version__", None)
    except ImportError:
        return None


def get_engine_backend() -> str:
    """Detect which trace engine backend is in use.
    
    Returns "rust" if prep_engine is available, "python" otherwise.
    """
    try:
        import prep_engine  # type: ignore  # noqa: F401
        return "rust"
    except ImportError:
        return "python"


def compute_file_hash(path: Path, algorithm: str = "blake3") -> str:
    """Compute hash of a file.
    
    Args:
        path: Path to file
        algorithm: "blake3" (default) or "sha256"
    
    Returns:
        Hash string in format "algorithm:hexdigest"
    """
    if not path.exists():
        return ""
    
    try:
        if algorithm == "blake3":
            try:
                import blake3  # type: ignore
                hasher = blake3.blake3()
            except ImportError:
                # Fallback to sha256 if blake3 not available
                algorithm = "sha256"
                hasher = hashlib.sha256()
        else:
            hasher = hashlib.sha256()
        
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        return f"{algorithm}:{hasher.hexdigest()[:16]}"  # First 16 chars for brevity
    except Exception as e:
        logger.debug("Failed to hash %s: %s", path, e)
        return ""


def get_file_metadata(path: Path) -> Dict[str, Any]:
    """Get metadata for a file (size, hash, item count for JSONL).
    
    Returns:
        {
            "size_bytes": int,
            "hash": str,
            "item_count": int  # Only for .jsonl files
        }
    """
    if not path.exists():
        return {}
    
    metadata: Dict[str, Any] = {
        "size_bytes": path.stat().st_size,
        "hash": compute_file_hash(path),
    }
    
    # Count items for JSONL files
    if path.suffix == ".jsonl":
        try:
            count = 0
            with open(path, "r", encoding="utf-8") as f:
                for _ in f:
                    count += 1
            metadata["item_count"] = count
        except Exception as e:
            logger.debug("Failed to count items in %s: %s", path, e)
    
    return metadata


def aggregate_quality_metrics(
    jsonl_path: Path,
    confidence_field: str = "confidence",
) -> Dict[str, Any]:
    """Aggregate quality metrics from a JSONL file.
    
    Computes:
    - total_items: total entries in file
    - avg_confidence: average confidence score
    - min_confidence: minimum confidence score
    - max_confidence: maximum confidence score
    - parse_errors: count of entries with missing/invalid confidence
    
    Args:
        jsonl_path: Path to JSONL file
        confidence_field: Name of confidence field (default "confidence")
    
    Returns:
        Dict with quality metrics
    """
    if not jsonl_path.exists():
        return {}

    confidences: List[float] = []
    total_items = 0
    parse_errors = 0

    def _lookup(entry: Dict[str, Any], field: str) -> Any:
        """Resolve a possibly-dotted field path. Falls back to a recursive
        scan for the leaf key if the dotted path is absent — handles cases
        where the producer nests the score under metadata/quality/etc.
        without the caller having to know the exact shape.
        """
        cur: Any = entry
        for part in field.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
            if cur is None:
                break
        if cur is not None:
            return cur
        leaf = field.rsplit(".", 1)[-1]
        for v in entry.values():
            if isinstance(v, dict) and leaf in v and isinstance(v[leaf], (int, float)):
                return v[leaf]
        return None

    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                total_items += 1
                try:
                    entry = json.loads(line)
                    conf = _lookup(entry, confidence_field)
                    if conf is not None and isinstance(conf, (int, float)):
                        confidences.append(float(conf))
                    else:
                        parse_errors += 1
                except Exception:
                    parse_errors += 1
    except Exception as e:
        logger.debug("Failed to aggregate quality from %s: %s", jsonl_path, e)
        return {}
    
    if not confidences:
        return {
            "total_items": total_items,
            "parse_errors": parse_errors,
        }
    
    return {
        "total_items": total_items,
        "processed": len(confidences),
        "skipped": 0,  # Would need to track this separately
        "failed": parse_errors,
        "success_rate": round(len(confidences) / total_items, 3) if total_items > 0 else 0.0,
        "avg_confidence": round(sum(confidences) / len(confidences), 3),
        "min_confidence": round(min(confidences), 3),
        "max_confidence": round(max(confidences), 3),
        "parse_errors": parse_errors,
    }


def aggregate_epistemic_quality(jsonl_path: Path) -> Dict[str, Any]:
    """Aggregate quality metrics from trace_epistemic.jsonl.
    
    Uses "epistemic_confidence" field instead of "confidence".
    """
    return aggregate_quality_metrics(jsonl_path, confidence_field="epistemic_confidence")


def aggregate_model_breakdown(
    jsonl_path: Path,
    model_field: str = "model",
    confidence_field: str = "confidence",
) -> Optional[List[Dict[str, Any]]]:
    """Scan a JSONL file and group entries by model name.
    
    Returns a list of per-model stats sorted by count (descending).
    Returns None when only one model is present (the common case),
    so the caller can skip multi-model display.
    
    Args:
        jsonl_path: Path to JSONL file
        model_field: JSON key holding the model name (default "model")
        confidence_field: JSON key holding confidence (default "confidence")
    
    Returns:
        None if 0-1 models, or list of:
        [{"model": str, "count": int, "percentage": float, "avg_confidence": float}, ...]
    """
    if not jsonl_path.exists():
        return None
    
    # model_name → (count, confidence_sum)
    buckets: Dict[str, List[float]] = {}
    total = 0
    
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    entry = json.loads(line)
                    model = entry.get(model_field) or "unknown"
                    conf = entry.get(confidence_field)
                    if model not in buckets:
                        buckets[model] = []
                    if conf is not None and isinstance(conf, (int, float)):
                        buckets[model].append(float(conf))
                    else:
                        buckets[model].append(-1.0)  # sentinel: no confidence
                except Exception:
                    pass
    except Exception as e:
        logger.debug("Failed to scan model breakdown from %s: %s", jsonl_path, e)
        return None
    
    # Single model (or empty) → no breakdown needed
    if len(buckets) <= 1:
        return None
    
    result: List[Dict[str, Any]] = []
    for model, confs in buckets.items():
        valid_confs = [c for c in confs if c >= 0]
        entry: Dict[str, Any] = {
            "model": model,
            "count": len(confs),
            "percentage": round(len(confs) / total * 100, 1) if total > 0 else 0.0,
        }
        if valid_confs:
            entry["avg_confidence"] = round(sum(valid_confs) / len(valid_confs), 3)
        result.append(entry)
    
    # Sort by count descending (dominant model first)
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def compute_throughput(
    total_items: int,
    elapsed_seconds: float,
    total_bytes: int = 0,
) -> Dict[str, float]:
    """Compute throughput metrics.
    
    Args:
        total_items: Number of items processed
        elapsed_seconds: Time taken in seconds
        total_bytes: Total bytes processed (optional)
    
    Returns:
        {
            "items_per_second": float,
            "bytes_per_second": float  # Only if total_bytes > 0
        }
    """
    if elapsed_seconds <= 0:
        return {}
    
    throughput: Dict[str, float] = {
        "items_per_second": round(total_items / elapsed_seconds, 2),
    }
    
    if total_bytes > 0:
        throughput["bytes_per_second"] = round(total_bytes / elapsed_seconds, 2)
    
    return throughput


def extract_model_info_from_llm_client(llm_client: Any) -> Dict[str, Any]:
    """Extract model provenance info from an LLMClient instance.
    
    Args:
        llm_client: LLMClient instance
    
    Returns:
        {
            "provider": str,
            "endpoint_id": str,
            "model_name": str,
            "model_variant": str,  # e.g., "q8_0", "q4_0"
            "base_url": str,
        }
    """
    if llm_client is None:
        return {}
    
    info: Dict[str, Any] = {}
    
    # Extract basic fields
    for field in ["provider", "endpoint_id", "model", "base_url"]:
        value = getattr(llm_client, field, None)
        if value:
            if field == "model":
                info["model_name"] = value
            else:
                info[field] = value
    
    # Try to extract model variant from model name
    # e.g., "qwen3:14b-q8_0" → variant="q8_0"
    model_name = info.get("model_name", "")
    if "-" in model_name:
        parts = model_name.split("-")
        if len(parts) > 1:
            variant = parts[-1]
            if variant.startswith("q") or variant in ["fp16", "bf16", "int8"]:
                info["model_variant"] = variant
    
    return info


def extract_embedding_model_info(embedder: Any) -> Dict[str, Any]:
    """Extract embedding model info from an embedder instance.
    
    Args:
        embedder: NativeEmbedder or OllamaEmbedder instance
    
    Returns:
        {
            "provider": str,  # "native" or "ollama"
            "model_name": str,
            "dimensions": int,
        }
    """
    if embedder is None:
        return {}
    
    info: Dict[str, Any] = {}
    
    # Detect provider from class name
    class_name = embedder.__class__.__name__
    if "Native" in class_name:
        info["provider"] = "native"
    elif "Ollama" in class_name:
        info["provider"] = "ollama"
    
    # Extract model name
    model = getattr(embedder, "model", None)
    if model:
        info["model_name"] = model
    
    # Extract dimensions
    dim = getattr(embedder, "dimensions", None) or getattr(embedder, "dim", None)
    if dim:
        info["dimensions"] = dim
    
    return info
