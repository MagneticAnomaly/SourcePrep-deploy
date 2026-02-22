#!/usr/bin/env python3
"""Analyze code-in-docs patterns across real repos for compression research."""

import json
import re
import sys
from pathlib import Path

def analyze_repo(repo_path: str, label: str):
    codrag_dir = Path(repo_path) / ".codrag"
    docs_path = codrag_dir / "documents.json"
    knowledge_path = codrag_dir / "knowledge_documents.json"

    print(f"\n{'='*70}")
    print(f"REPO: {label} ({repo_path})")
    print(f"{'='*70}")

    # --- CodeIndex chunks ---
    with open(docs_path) as f:
        docs = json.load(f)

    # Classify each chunk
    md_chunks = []
    code_chunks = []
    md_with_code = []
    md_pure_language = []

    fence_pattern = re.compile(r"```[\w]*\n.*?```", re.DOTALL)

    for d in docs:
        src = d.get("source_path", "")
        content = d.get("content", "")

        if src.endswith((".md", ".txt", ".rst")):
            md_chunks.append(d)
            fences = fence_pattern.findall(content)
            if fences:
                total_code_chars = sum(len(f) for f in fences)
                code_ratio = total_code_chars / max(len(content), 1)
                md_with_code.append({
                    "source": src,
                    "chars": len(content),
                    "code_chars": total_code_chars,
                    "code_ratio": code_ratio,
                    "num_fences": len(fences),
                    "content": content,
                })
            else:
                md_pure_language.append(d)
        else:
            code_chunks.append(d)

    print(f"\n--- CodeIndex Summary ---")
    print(f"Total chunks: {len(docs)}")
    print(f"  Code file chunks: {len(code_chunks)}")
    print(f"  Markdown chunks: {len(md_chunks)}")
    print(f"    Pure language: {len(md_pure_language)}")
    print(f"    With code fences: {len(md_with_code)}")

    if md_with_code:
        avg_ratio = sum(c["code_ratio"] for c in md_with_code) / len(md_with_code)
        total_code_in_docs = sum(c["code_chars"] for c in md_with_code)
        total_doc_chars = sum(c["chars"] for c in md_with_code)
        print(f"\n--- Code-in-Docs Detail ---")
        print(f"Avg code ratio in mixed chunks: {avg_ratio:.1%}")
        print(f"Total code chars in docs: {total_code_in_docs:,}")
        print(f"Total doc chars (mixed only): {total_doc_chars:,}")
        print(f"Overall code-in-docs ratio: {total_code_in_docs/max(total_doc_chars,1):.1%}")

        print(f"\nPer-file breakdown:")
        by_file = {}
        for c in md_with_code:
            src = c["source"]
            if src not in by_file:
                by_file[src] = {"chunks": 0, "chars": 0, "code_chars": 0, "fences": 0}
            by_file[src]["chunks"] += 1
            by_file[src]["chars"] += c["chars"]
            by_file[src]["code_chars"] += c["code_chars"]
            by_file[src]["fences"] += c["num_fences"]

        for src, info in sorted(by_file.items(), key=lambda x: -x[1]["code_chars"]):
            ratio = info["code_chars"] / max(info["chars"], 1)
            print(f"  {src}: {info['chunks']} chunks, {info['fences']} fences, "
                  f"{info['code_chars']:,} code chars / {info['chars']:,} total ({ratio:.0%})")

        # Show example of worst offenders
        print(f"\nWorst code-heavy doc chunk examples:")
        worst = sorted(md_with_code, key=lambda x: -x["code_ratio"])[:3]
        for w in worst:
            print(f"\n  Source: {w['source']} (code ratio: {w['code_ratio']:.0%})")
            # Show first 400 chars
            preview = w["content"][:400].replace("\n", "\n    ")
            print(f"    {preview}...")

    # --- KnowledgeIndex ---
    if knowledge_path.exists():
        with open(knowledge_path) as f:
            know_docs = json.load(f)

        know_with_code = []
        for d in know_docs:
            content = d.get("content", "")
            if fence_pattern.search(content):
                know_with_code.append(d)

        print(f"\n--- KnowledgeIndex ---")
        print(f"Total knowledge docs: {len(know_docs)}")
        print(f"Knowledge docs with code fences: {len(know_with_code)}")

    return md_with_code


if __name__ == "__main__":
    repos = [
        ("/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST", "DebateHaus (Next.js marketing)"),
        ("/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/mini-redis-rust", "mini-redis (Rust/Tokio)"),
    ]

    all_mixed = {}
    for path, label in repos:
        mixed = analyze_repo(path, label)
        all_mixed[label] = mixed

    # Cross-repo summary
    print(f"\n{'='*70}")
    print(f"CROSS-REPO SUMMARY")
    print(f"{'='*70}")
    for label, mixed in all_mixed.items():
        if mixed:
            total_chars = sum(c["chars"] for c in mixed)
            total_code = sum(c["code_chars"] for c in mixed)
            print(f"\n{label}:")
            print(f"  {len(mixed)} mixed chunks, {total_code:,} code chars out of {total_chars:,} total ({total_code/max(total_chars,1):.0%})")
        else:
            print(f"\n{label}: No code-in-docs found")
