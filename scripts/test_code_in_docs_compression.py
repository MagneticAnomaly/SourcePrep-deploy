#!/usr/bin/env python3
"""Test LLMLingua-2 compression on real repo chunks with code-in-docs analysis.

Measures:
1. Compression quality on pure-language doc chunks vs mixed code+language chunks
2. A "splice" strategy: strip code fences before compression, re-insert after
3. How doc-comments in code files affect compression
"""

import json
import re
import time
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ── LLMLingua-2 setup ──────────────────────────────────────────────
try:
    from llmlingua import PromptCompressor
except ImportError:
    print("ERROR: pip install llmlingua")
    sys.exit(1)

FENCE_RE = re.compile(r"(```[\w]*\n.*?```)", re.DOTALL)

@dataclass
class ChunkResult:
    source: str
    chunk_type: str  # "pure_language", "mixed_code_lang", "code_with_docs"
    original_chars: int
    compressed_chars: int
    ratio: float
    latency_ms: float
    # Retention checks
    key_terms_total: int = 0
    key_terms_retained: int = 0
    file_refs_total: int = 0
    file_refs_retained: int = 0
    code_fences_original: int = 0
    code_chars_original: int = 0


def extract_key_terms(text: str) -> List[str]:
    """Extract important terms from text for retention checking."""
    terms = []
    # File paths
    terms.extend(re.findall(r'[\w/]+\.\w{1,4}', text))
    # Backtick terms
    terms.extend(re.findall(r'`([^`]+)`', text))
    # Bold terms
    terms.extend(re.findall(r'\*\*([^*]+)\*\*', text))
    # Capitalized compound words (e.g., ScrollTrigger, TcpListener)
    terms.extend(re.findall(r'\b[A-Z][a-z]+[A-Z]\w+\b', text))
    return list(set(terms))


def extract_file_refs(text: str) -> List[str]:
    """Extract file path references."""
    refs = re.findall(r'[\w/-]+\.\w{1,4}', text)
    return list(set(refs))


def splice_code_fences(text: str) -> Tuple[str, List[Tuple[int, str]]]:
    """Remove code fences, return (stripped_text, [(position, fence_content)])."""
    fences = []
    stripped = text
    for match in FENCE_RE.finditer(text):
        fences.append((match.start(), match.group(0)))

    if not fences:
        return text, []

    stripped = FENCE_RE.sub("[CODE_BLOCK_PLACEHOLDER]", text)
    return stripped, fences


def unsplice_code_fences(compressed: str, fences: List[Tuple[int, str]]) -> str:
    """Re-insert code fences into compressed text."""
    result = compressed
    for _, fence_content in fences:
        result = result.replace("[CODE_BLOCK_PLACEHOLDER]", fence_content, 1)
    return result


def compress_chunk(compressor, text: str, rate: float = 0.6) -> Tuple[str, float]:
    """Compress text and return (compressed_text, latency_ms)."""
    t0 = time.time()
    result = compressor.compress_prompt(
        text,
        rate=rate,
        force_tokens=['\n', '.', '/', ':', '`', '*', '#', '-', '@', '_'],
        force_reserve_digit=True,
        drop_consecutive=True,
    )
    latency = (time.time() - t0) * 1000
    return result.get("compressed_prompt", ""), latency


def analyze_chunk(compressor, content: str, source: str, chunk_type: str,
                  rate: float = 0.6) -> ChunkResult:
    """Compress a chunk and measure retention."""
    key_terms = extract_key_terms(content)
    file_refs = extract_file_refs(content)
    fences = FENCE_RE.findall(content)
    code_chars = sum(len(f) for f in fences)

    compressed, latency = compress_chunk(compressor, content, rate)

    terms_retained = sum(1 for t in key_terms if t in compressed)
    refs_retained = sum(1 for r in file_refs if r in compressed)

    return ChunkResult(
        source=source,
        chunk_type=chunk_type,
        original_chars=len(content),
        compressed_chars=len(compressed),
        ratio=len(content) / max(len(compressed), 1),
        latency_ms=latency,
        key_terms_total=len(key_terms),
        key_terms_retained=terms_retained,
        file_refs_total=len(file_refs),
        file_refs_retained=refs_retained,
        code_fences_original=len(fences),
        code_chars_original=code_chars,
    )


def analyze_spliced(compressor, content: str, source: str,
                    rate: float = 0.6) -> ChunkResult:
    """Splice strategy: strip code, compress language only, re-insert code."""
    stripped, fences = splice_code_fences(content)
    if not fences:
        return analyze_chunk(compressor, content, source, "splice_noop", rate)

    key_terms = extract_key_terms(content)
    file_refs = extract_file_refs(content)

    t0 = time.time()
    compressed_lang, _ = compress_chunk(compressor, stripped, rate)
    recombined = unsplice_code_fences(compressed_lang, fences)
    latency = (time.time() - t0) * 1000

    terms_retained = sum(1 for t in key_terms if t in recombined)
    refs_retained = sum(1 for r in file_refs if r in recombined)
    code_chars = sum(len(f[1]) for f in fences)

    return ChunkResult(
        source=source,
        chunk_type="spliced",
        original_chars=len(content),
        compressed_chars=len(recombined),
        ratio=len(content) / max(len(recombined), 1),
        latency_ms=latency,
        key_terms_total=len(key_terms),
        key_terms_retained=terms_retained,
        file_refs_total=len(file_refs),
        file_refs_retained=refs_retained,
        code_fences_original=len(fences),
        code_chars_original=code_chars,
    )


def load_chunks(repo_path: str) -> dict:
    """Load and classify chunks from a repo."""
    docs_path = Path(repo_path) / ".codrag" / "documents.json"
    with open(docs_path) as f:
        docs = json.load(f)

    classified = {"pure_language": [], "mixed_code_lang": [], "code_with_docs": []}

    for d in docs:
        src = d.get("source_path", "")
        content = d.get("content", "")
        if len(content) < 100:
            continue

        if src.endswith((".md", ".txt", ".rst")):
            fences = FENCE_RE.findall(content)
            if fences:
                classified["mixed_code_lang"].append(d)
            else:
                classified["pure_language"].append(d)
        else:
            # Check for heavy doc comments in code
            lines = content.split('\n')
            comment_lines = sum(1 for l in lines if l.strip().startswith(('///', '//!', '#', '/**', '*')))
            total_lines = max(len(lines), 1)
            if comment_lines / total_lines > 0.3:
                classified["code_with_docs"].append(d)

    return classified


def print_category_results(results: List[ChunkResult], label: str):
    if not results:
        print(f"\n  {label}: (no chunks)")
        return

    avg_ratio = sum(r.ratio for r in results) / len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results)
    total_terms = sum(r.key_terms_total for r in results)
    retained_terms = sum(r.key_terms_retained for r in results)
    total_refs = sum(r.file_refs_total for r in results)
    retained_refs = sum(r.file_refs_retained for r in results)

    term_rate = retained_terms / max(total_terms, 1)
    ref_rate = retained_refs / max(total_refs, 1)

    print(f"\n  {label} ({len(results)} chunks):")
    print(f"    Avg compression ratio: {avg_ratio:.1f}x")
    print(f"    Avg latency: {avg_latency:.0f}ms")
    print(f"    Key terms retained: {retained_terms}/{total_terms} ({term_rate:.0%})")
    print(f"    File refs retained: {retained_refs}/{total_refs} ({ref_rate:.0%})")


def main():
    print("Loading LLMLingua-2 model...")
    compressor = PromptCompressor(
        model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        use_llmlingua2=True,
        device_map="cpu",
    )
    print("Model loaded.\n")

    repos = [
        ("/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST", "DebateHaus"),
        ("/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/mini-redis-rust", "mini-redis"),
    ]

    all_results = {}
    rate = 0.6  # Light compression

    for repo_path, label in repos:
        print(f"\n{'='*70}")
        print(f"TESTING: {label}")
        print(f"{'='*70}")

        chunks = load_chunks(repo_path)

        repo_results = {}

        # Test pure language chunks (sample up to 5)
        pure = chunks["pure_language"][:5]
        results_pure = []
        for d in pure:
            r = analyze_chunk(compressor, d["content"], d["source_path"], "pure_language", rate)
            results_pure.append(r)
        repo_results["pure_language"] = results_pure
        print_category_results(results_pure, "Pure Language Docs")

        # Test mixed code+lang chunks
        mixed = chunks["mixed_code_lang"]
        results_mixed = []
        for d in mixed:
            r = analyze_chunk(compressor, d["content"], d["source_path"], "mixed_code_lang", rate)
            results_mixed.append(r)
        repo_results["mixed_direct"] = results_mixed
        print_category_results(results_mixed, "Mixed Code+Lang (direct compression)")

        # Test splice strategy on mixed chunks
        results_spliced = []
        for d in mixed:
            r = analyze_spliced(compressor, d["content"], d["source_path"], rate)
            results_spliced.append(r)
        repo_results["mixed_spliced"] = results_spliced
        print_category_results(results_spliced, "Mixed Code+Lang (splice strategy)")

        # Test code files with heavy doc comments (sample up to 5)
        code_docs = chunks["code_with_docs"][:5]
        results_code_docs = []
        for d in code_docs:
            r = analyze_chunk(compressor, d["content"], d["source_path"], "code_with_docs", rate)
            results_code_docs.append(r)
        repo_results["code_with_docs"] = results_code_docs
        print_category_results(results_code_docs, "Code with Heavy Doc Comments")

        all_results[label] = repo_results

    # --- Comparison summary ---
    print(f"\n{'='*70}")
    print("STRATEGY COMPARISON: Direct vs Splice on Mixed Chunks")
    print(f"{'='*70}")

    for label, repo_results in all_results.items():
        direct = repo_results.get("mixed_direct", [])
        spliced = repo_results.get("mixed_spliced", [])
        if not direct:
            continue

        print(f"\n{label}:")
        for d, s in zip(direct, spliced):
            d_term_rate = d.key_terms_retained / max(d.key_terms_total, 1)
            s_term_rate = s.key_terms_retained / max(s.key_terms_total, 1)
            d_ref_rate = d.file_refs_retained / max(d.file_refs_total, 1)
            s_ref_rate = s.file_refs_retained / max(s.file_refs_total, 1)
            print(f"\n  {d.source} ({d.code_fences_original} fences, {d.code_chars_original} code chars)")
            print(f"    Direct:  ratio={d.ratio:.1f}x, terms={d_term_rate:.0%}, refs={d_ref_rate:.0%}, latency={d.latency_ms:.0f}ms")
            print(f"    Spliced: ratio={s.ratio:.1f}x, terms={s_term_rate:.0%}, refs={s_ref_rate:.0%}, latency={s.latency_ms:.0f}ms")
            delta_terms = s_term_rate - d_term_rate
            delta_refs = s_ref_rate - d_ref_rate
            print(f"    Delta:   terms {'+' if delta_terms >= 0 else ''}{delta_terms:.0%}, refs {'+' if delta_refs >= 0 else ''}{delta_refs:.0%}")

    # --- Show concrete examples of compression damage ---
    print(f"\n{'='*70}")
    print("EXAMPLES: What LLMLingua-2 does to code-in-docs")
    print(f"{'='*70}")

    for label, repo_results in all_results.items():
        mixed = repo_results.get("mixed_direct", [])
        if not mixed:
            continue
        # Pick worst performer
        worst = max(mixed, key=lambda r: r.code_chars_original)
        # Re-compress to get the actual text
        docs_path = Path([p for p, l in repos if l == label][0]) / ".codrag" / "documents.json"
        with open(docs_path) as f:
            all_docs = json.load(f)
        for d in all_docs:
            if d.get("source_path") == worst.source:
                content = d["content"]
                if FENCE_RE.search(content):
                    compressed, _ = compress_chunk(compressor, content, rate)
                    print(f"\n--- {label}: {worst.source} ---")
                    print(f"ORIGINAL (first 500 chars):\n{content[:500]}")
                    print(f"\nCOMPRESSED (first 500 chars):\n{compressed[:500]}")
                    break

    print("\nDone.")


if __name__ == "__main__":
    main()
