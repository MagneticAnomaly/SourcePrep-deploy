import os

filepath = 'packages/ui/src/components/marketing/CompetitorMatrix.tsx'

with open(filepath, 'r') as f:
    content = f.read()

replacements = {
    "text: 'Node.js / WASM'": "text: 'Node.js \\n / WASM'",
    "text: 'SQLite / Tree-sitter'": "text: 'SQLite \\n / Tree-sitter'",
    "text: 'KuzuDB / FTS'": "text: 'KuzuDB \\n / FTS'",
    "text: 'FTS5 + TF-IDF (No Embeddings)'": "text: 'FTS5 + TF-IDF \\n (No Embeddings)'",
    "text: 'Local ONNX Embeddings + BM25'": "text: 'Local ONNX \\n Embeddings + BM25'",
    "text: 'LOD (Level of Detail) Capsule Context'": "text: 'LOD Capsule \\n Context'",
    "text: 'Precomputed Raw Graph Data'": "text: 'Precomputed \\n Raw Graph Data'",
    "text: 'Dual-Engine Compression (3-20x)'": "text: 'Dual-Engine \\n Compression (3-20x)'",
    "text: 'Dual-Engine Compression (3\u201320x)'": "text: 'Dual-Engine \\n Compression (3\u201320x)'",
    "text: 'High (via Precomputation)'": "text: 'High \\n (via Precomputation)'",
    "text: 'High (Signature Only)'": "text: 'High \\n (Signature Only)'",
    "text: 'Low (State Dumps)'": "text: 'Low \\n (State Dumps)'",
    "text: 'Low (Full Symbols)'": "text: 'Low \\n (Full Symbols)'",
    "text: 'Low (Sends full chunks)'": "text: 'Low \\n (Sends full chunks)'",
    "text: 'Low (Full snippets)'": "text: 'Low \\n (Full snippets)'",
    "text: 'Static until re-indexed'": "text: 'Static \\n until re-indexed'",
    "text: 'Git-Native Pre/Postflight'": "text: 'Git-Native \\n Pre/Postflight'",
    "text: 'Automated via Watcher & Graph'": "text: 'Automated via \\n Watcher & Graph'",
    "text: 'Manual git-diff checks'": "text: 'Manual \\n git-diff checks'",
    "text: 'Manual Observation Staling'": "text: 'Manual \\n Observation Staling'",
    "text: 'Mirror Drift Detection'": "text: 'Mirror \\n Drift Detection'",
    "text: 'Dedicated Desktop Health Dashboard'": "text: 'Dedicated Desktop \\n Health Dashboard'",
    "text: 'Web UI / Terminal'": "text: 'Web UI \\n / Terminal'",
    "text: 'VS Code Only'": "text: 'VS Code \\n Only'",
    "text: 'Git Log Only'": "text: 'Git Log \\n Only'",
    "text: 'Terminal Only'": "text: 'Terminal \\n Only'",
    "text: 'Desktop App'": "text: 'Desktop \\n App'",
    "text: 'Visual Folder-Tree with Include/Exclude'": "text: 'Visual Folder-Tree \\n with Include/Exclude'",
    "text: '.gitignore-style Patterns'": "text: '.gitignore-style \\n Patterns'",
    "text: 'VS Code Workspace Scope'": "text: 'VS Code \\n Workspace Scope'",
    "text: 'Git Repo Scope Only'": "text: 'Git Repo \\n Scope Only'",
    "text: 'LSP Workspace Scope'": "text: 'LSP \\n Workspace Scope'",
    "text: 'CLI Path Arguments'": "text: 'CLI \\n Path Arguments'",
    "text: 'Repo-Level Selection'": "text: 'Repo-Level \\n Selection'",
    "text: 'Configurable Edge Weights + Module Importance'": "text: 'Configurable Edge Weights \\n + Module Importance'",
    "text: 'Graph Centrality Metrics'": "text: 'Graph Centrality \\n Metrics'",
    "text: 'Graph Centrality in Ranking'": "text: 'Graph Centrality \\n in Ranking'",
    "text: 'Embedding Similarity Only'": "text: 'Embedding Similarity \\n Only'",
    "text: 'Vector Similarity Only'": "text: 'Vector Similarity \\n Only'",
    "text: '100% Local: Rust + ONNX, Zero Cloud'": "text: '100% Local: Rust + ONNX \\n Zero Cloud'",
    "text: '100% Local: Rust + ONNX \\n Zero Cloud'": "text: '100% Local: Rust + ONNX \\n Zero Cloud'",
    "text: 'Local (Node.js + WASM option)'": "text: 'Local \\n (Node.js + WASM option)'",
    "text: 'Local (VS Code Extension)'": "text: 'Local \\n (VS Code Extension)'",
    "text: 'Git-Native (LLM calls needed)'": "text: 'Git-Native \\n (LLM calls needed)'",
    "text: 'Local Server (LLM calls needed)'": "text: 'Local Server \\n (LLM calls needed)'",
    "text: 'Privacy-First Local'": "text: 'Privacy-First \\n Local'",
    "text: 'Local (Qdrant Instance)'": "text: 'Local \\n (Qdrant Instance)'",
    "text: 'Native Rust Engine (Tree-sitter)'": "text: 'Native Rust Engine \\n (Tree-sitter)'",
    "text: 'Active LSP Server'": "text: 'Active \\n LSP Server'",
    "text: 'Git Notes / No Graph'": "text: 'Git Notes \\n / No Graph'",
    "text: 'Local Semantic Index'": "text: 'Local \\n Semantic Index'",
    "text: 'Local Qdrant / Vector'": "text: 'Local Qdrant \\n / Vector'",
    "text: 'Raw Symbol Matches'": "text: 'Raw \\n Symbol Matches'",
    "text: 'Raw File Chunks'": "text: 'Raw \\n File Chunks'",
    "text: 'Raw Snippets'": "text: 'Raw \\n Snippets'",
    "text: 'Session Memory'": "text: 'Session \\n Memory'",
    "text: 'Reasoning Checkpoints'": "text: 'Reasoning \\n Checkpoints'"
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(filepath, 'w') as f:
    f.write(content)

print("Done")
