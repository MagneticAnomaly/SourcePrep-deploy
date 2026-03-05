import re

with open('packages/ui/src/components/marketing/CompetitorMatrix.tsx', 'r') as f:
    content = f.read()

# 1. Update Widths
content = content.replace('w-[260px] min-w-[260px]', 'w-[220px] min-w-[220px]')
content = content.replace('left-[260px]', 'left-[220px]')
content = content.replace('w-[180px] min-w-[180px]', 'w-[150px] min-w-[150px]')
content = content.replace('left-[180px]', 'left-[150px]')
content = content.replace('w-[160px] min-w-[160px]', 'w-[140px] min-w-[140px]')

# Fix the specific CoDRAG cell width
content = content.replace('w-[180px] min-w-[180px] max-w-[180px]', 'w-[150px] min-w-[150px] max-w-[150px]')

# 2. Update Wheel Listener
old_wheel = """  // Add wheel event listener for horizontal scrolling
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      // Only intercept if we are scrolling vertically without holding Shift
      if (e.deltaY !== 0 && Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
        const canScrollLeft = el.scrollLeft > 0;
        const canScrollRight = Math.ceil(el.scrollLeft + el.clientWidth) < el.scrollWidth;

        // If we can scroll in the requested direction, intercept it
        if ((e.deltaY > 0 && canScrollRight) || (e.deltaY < 0 && canScrollLeft)) {
          e.preventDefault();
          el.scrollLeft += e.deltaY;
        }
      }
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);"""

new_wheel = """  // Add wheel event listener for horizontal scrolling
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      // Unconditionally prevent vertical page scroll when hovering over the matrix
      e.preventDefault();
      // Map both vertical and horizontal scroll deltas to the container's horizontal scroll
      el.scrollLeft += e.deltaY + e.deltaX;
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);"""

if old_wheel in content:
    content = content.replace(old_wheel, new_wheel)
else:
    print("WARNING: Old wheel listener not found for replacement!")

# 3. Update Text Renderer in JSX
codrag_old = '<span className="text-xs font-bold text-text leading-tight">{feature.codrag.text}</span>'
codrag_new = """<span className="text-xs font-bold text-text leading-tight text-center">
                            {feature.codrag.text.split('\\n').map((line, i) => (
                              <span key={i} className="block">{line.trim()}</span>
                            ))}
                          </span>"""
content = content.replace(codrag_old, codrag_new)

comp_old = '<span className="text-[11px] text-text-muted leading-tight">{cd.text}</span>'
comp_new = """<span className="text-[11px] text-text-muted leading-tight text-center">
                                {cd.text.split('\\n').map((line, i) => (
                                  <span key={i} className="block">{line.trim()}</span>
                                ))}
                              </span>"""
content = content.replace(comp_old, comp_new)

# 4. Text Replacements for Newlines
replacements = {
    "'Node.js / WASM'": "'Node.js \\n / WASM'",
    "'SQLite / Tree-sitter'": "'SQLite \\n / Tree-sitter'",
    "'KuzuDB / FTS'": "'KuzuDB \\n / FTS'",
    "'FTS5 + TF-IDF (No Embeddings)'": "'FTS5 + TF-IDF \\n (No Embeddings)'",
    "'Local ONNX Embeddings + BM25'": "'Local ONNX \\n Embeddings + BM25'",
    "'LOD (Level of Detail) Capsule Context'": "'LOD Capsule \\n Context'",
    "'Precomputed Raw Graph Data'": "'Precomputed \\n Raw Graph Data'",
    "'Dual-Engine Compression (3-20x)'": "'Dual-Engine \\n Compression (3-20x)'",
    "'High (via Precomputation)'": "'High \\n (via Precomputation)'",
    "'High (Signature Only)'": "'High \\n (Signature Only)'",
    "'Low (State Dumps)'": "'Low \\n (State Dumps)'",
    "'Low (Full Symbols)'": "'Low \\n (Full Symbols)'",
    "'Low (Sends full chunks)'": "'Low \\n (Sends full chunks)'",
    "'Low (Full snippets)'": "'Low \\n (Full snippets)'",
    "'Static until re-indexed'": "'Static \\n until re-indexed'",
    "'Git-Native Pre/Postflight'": "'Git-Native \\n Pre/Postflight'",
    "'Automated via Watcher & Graph'": "'Automated via \\n Watcher & Graph'",
    "'Manual git-diff checks'": "'Manual \\n git-diff checks'",
    "'Manual Observation Staling'": "'Manual \\n Observation Staling'",
    "'Mirror Drift Detection'": "'Mirror \\n Drift Detection'",
    "'Dedicated Desktop Health Dashboard'": "'Dedicated Desktop \\n Health Dashboard'",
    "'Web UI / Terminal'": "'Web UI \\n / Terminal'",
    "'VS Code Only'": "'VS Code \\n Only'",
    "'Git Log Only'": "'Git Log \\n Only'",
    "'Terminal Only'": "'Terminal \\n Only'",
    "'Desktop App'": "'Desktop \\n App'",
    "'Visual Folder-Tree with Include/Exclude'": "'Visual Folder-Tree \\n with Include/Exclude'",
    "'.gitignore-style Patterns'": "'.gitignore-style \\n Patterns'",
    "'VS Code Workspace Scope'": "'VS Code \\n Workspace Scope'",
    "'Git Repo Scope Only'": "'Git Repo \\n Scope Only'",
    "'LSP Workspace Scope'": "'LSP \\n Workspace Scope'",
    "'CLI Path Arguments'": "'CLI \\n Path Arguments'",
    "'Repo-Level Selection'": "'Repo-Level \\n Selection'",
    "'Configurable Edge Weights + Module Importance'": "'Configurable Edge Weights \\n + Module Importance'",
    "'Graph Centrality Metrics'": "'Graph Centrality \\n Metrics'",
    "'Graph Centrality in Ranking'": "'Graph Centrality \\n in Ranking'",
    "'Embedding Similarity Only'": "'Embedding Similarity \\n Only'",
    "'Vector Similarity Only'": "'Vector Similarity \\n Only'",
    "'100% Local: Rust + ONNX, Zero Cloud'": "'100% Local: Rust + ONNX \\n Zero Cloud'",
    "'Local (Node.js + WASM option)'": "'Local \\n (Node.js + WASM option)'",
    "'Local (VS Code Extension)'": "'Local \\n (VS Code Extension)'",
    "'Git-Native (LLM calls needed)'": "'Git-Native \\n (LLM calls needed)'",
    "'Local Server (LLM calls needed)'": "'Local Server \\n (LLM calls needed)'",
    "'Privacy-First Local'": "'Privacy-First \\n Local'",
    "'Local (Qdrant Instance)'": "'Local \\n (Qdrant Instance)'",
    "'Native Rust Engine (Tree-sitter)'": "'Native Rust Engine \\n (Tree-sitter)'",
    "'Active LSP Server'": "'Active \\n LSP Server'",
    "'Git Notes / No Graph'": "'Git Notes \\n / No Graph'",
    "'Local Semantic Index'": "'Local \\n Semantic Index'",
    "'Local Qdrant / Vector'": "'Local Qdrant \\n / Vector'",
    "'Raw Symbol Matches'": "'Raw \\n Symbol Matches'",
    "'Raw File Chunks'": "'Raw \\n File Chunks'",
    "'Raw Snippets'": "'Raw \\n Snippets'",
    "'Session Memory'": "'Session \\n Memory'",
    "'Reasoning Checkpoints'": "'Reasoning \\n Checkpoints'"
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open('packages/ui/src/components/marketing/CompetitorMatrix.tsx', 'w') as f:
    f.write(content)

print("Done")
