"""
CoDRAG Performance Benchmarks

Run with: python scripts/benchmark.py

Measures:
1. Index build time (synthetic repo)
2. Search latency (cold vs warm)
3. Context assembly latency
4. Embedder throughput
"""

import time
import shutil
import tempfile
import random
import string
import statistics
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("benchmark")

from codrag.core import CodeIndex, FakeEmbedder, NativeEmbedder
from codrag.server import _create_embedder

def generate_synthetic_repo(root: Path, file_count: int = 100, lines_per_file: int = 100):
    """Generate a synthetic repository with Python files."""
    root.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Generating synthetic repo with {file_count} files...")
    
    for i in range(file_count):
        content = []
        content.append(f'"""File number {i}"""')
        content.append("import os")
        content.append("import sys")
        content.append("")
        
        for j in range(lines_per_file):
            func_name = f"function_{i}_{j}"
            content.append(f"def {func_name}(arg1, arg2):")
            content.append(f"    '''Docstring for {func_name}.'''")
            content.append(f"    return arg1 + arg2 + {j}")
            content.append("")
            
        file_path = root / f"module_{i}.py"
        file_path.write_text("\n".join(content))

def benchmark_build(repo_root: Path, index_dir: Path, embedder):
    """Benchmark index build time."""
    logger.info(f"Benchmarking build with {embedder.__class__.__name__}...")
    
    if index_dir.exists():
        shutil.rmtree(index_dir)
    
    idx = CodeIndex(index_dir=index_dir, embedder=embedder)
    
    start_time = time.time()
    idx.build(repo_root=repo_root)
    duration = time.time() - start_time
    
    stats = idx.stats()
    total_docs = stats.get("total_documents", 0)
    
    logger.info(f"Build completed in {duration:.4f}s")
    logger.info(f"Throughput: {total_docs / duration:.2f} chunks/sec")
    
    return idx, duration

def benchmark_search(idx: CodeIndex, queries: list[str], runs: int = 5):
    """Benchmark search latency."""
    logger.info(f"Benchmarking search ({len(queries)} queries, {runs} runs)...")
    
    latencies = []
    
    for query in queries:
        for _ in range(runs):
            start = time.perf_counter()
            idx.search(query, k=10)
            latencies.append((time.perf_counter() - start) * 1000) # ms
            
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18]
    
    logger.info(f"Search Latency: Avg={avg_latency:.2f}ms, P95={p95_latency:.2f}ms")
    return avg_latency

def benchmark_context(idx: CodeIndex, queries: list[str], runs: int = 5):
    """Benchmark context assembly latency."""
    logger.info(f"Benchmarking context assembly ({len(queries)} queries, {runs} runs)...")
    
    latencies = []
    
    for query in queries:
        for _ in range(runs):
            start = time.perf_counter()
            idx.get_context(query, k=5, max_chars=4000)
            latencies.append((time.perf_counter() - start) * 1000) # ms
            
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18]
    
    logger.info(f"Context Latency: Avg={avg_latency:.2f}ms, P95={p95_latency:.2f}ms")
    return avg_latency

def main():
    temp_root = Path(tempfile.mkdtemp(prefix="codrag_bench_"))
    repo_root = temp_root / "repo"
    index_dir = temp_root / "index"
    
    try:
        # 1. Setup
        generate_synthetic_repo(repo_root, file_count=50, lines_per_file=50)
        
        # 2. Benchmark FakeEmbedder (Baseline overhead)
        print("\n--- Baseline (FakeEmbedder) ---")
        idx_fake, _ = benchmark_build(repo_root, index_dir, FakeEmbedder())
        benchmark_search(idx_fake, ["function_10_5", "import os", "docstring"])
        benchmark_context(idx_fake, ["function_10_5", "import os", "docstring"])
        
        # 3. Benchmark NativeEmbedder (Real ONNX) - if available
        try:
            native = NativeEmbedder()
            if native.is_available():
                print("\n--- NativeEmbedder (ONNX) ---")
                idx_native, _ = benchmark_build(repo_root, index_dir, native)
                benchmark_search(idx_native, ["function_10_5", "import os", "docstring"])
                benchmark_context(idx_native, ["function_10_5", "import os", "docstring"])
            else:
                print("\nSkipping NativeEmbedder benchmark (not available/downloaded)")
        except Exception as e:
            print(f"\nSkipping NativeEmbedder benchmark: {e}")

    finally:
        shutil.rmtree(temp_root)

if __name__ == "__main__":
    main()
