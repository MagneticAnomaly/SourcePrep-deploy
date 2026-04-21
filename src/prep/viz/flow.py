"""
CoDRAG CLI RAG Flow Visualization

Visualizes the end-to-step RAG pipeline execution.
Shows the flow of data from Query -> Retrieval -> Reranking -> Context -> LLM.
"""

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich.table import Table
from rich import box

def render_rag_flow(
    trace_data: dict,
    console: Console | None = None
) -> None:
    """
    Render a visualization of a RAG pipeline execution trace.
    
    Args:
        trace_data: Dict with keys:
            - query: str
            - embedding_model: str
            - embedding_ms: int
            - retrieval_count: int
            - retrieval_ms: int
            - rerank_count: int
            - rerank_ms: int
            - context_tokens: int
            - context_limit: int
            - llm_model: str
            - llm_ms: int
            - top_chunks: list[dict] {path, score}
    """
    if console is None:
        console = Console()
        
    # Root: Query
    query = trace_data.get("query", "Unknown query")
    root_label = Text(" 🔎 Query: ", style="bold blue")
    root_label.append(f'"{query}"', style="italic white")
    
    tree = Tree(root_label, guide_style="blue")
    
    # Step 1: Embedding
    model = trace_data.get("embedding_model", "nomic-embed-text")
    ms = trace_data.get("embedding_ms", 0)
    
    embed_node = tree.add(Text(f"🧠 Embedding ({model})", style="cyan"))
    embed_node.add(Text(f"Vectorized in {ms}ms", style="dim"))
    
    # Step 2: Retrieval
    count = trace_data.get("retrieval_count", 0)
    ms = trace_data.get("retrieval_ms", 0)
    
    retrieval_node = tree.add(Text(f"📂 Retrieval (Vector Search)", style="yellow"))
    retrieval_node.add(Text(f"Found {count} chunks in {ms}ms", style="dim"))
    
    # Show top chunks (branching off Retrieval or Rerank)
    # Step 3: Reranking (Optional in data, usually part of pipeline)
    rerank_count = trace_data.get("rerank_count", count)
    rerank_ms = trace_data.get("rerank_ms", 0)
    
    rerank_node = tree.add(Text(f"⚖️  Reranking & Filtering", style="magenta"))
    rerank_node.add(Text(f"Selected top {rerank_count} chunks in {rerank_ms}ms", style="dim"))
    
    # Add chunks to Rerank node
    chunks_node = rerank_node.add(Text("Top Context Sources", style="bold white"))
    for i, chunk in enumerate(trace_data.get("top_chunks", [])[:5]):
        path = chunk.get("path", "unknown")
        score = chunk.get("score", 0)
        chunks_node.add(f"[green]{score:.3f}[/green] {path}")
        
    if len(trace_data.get("top_chunks", [])) > 5:
        chunks_node.add(Text("... and more", style="dim"))
        
    # Step 4: Context
    tokens = trace_data.get("context_tokens", 0)
    limit = trace_data.get("context_limit", 8192)
    pct = (tokens / limit) * 100
    
    ctx_node = tree.add(Text(f"📝 Context Assembly", style="green"))
    ctx_node.add(Text(f"Budget: {tokens:,} / {limit:,} tokens ({pct:.1f}%)", style="dim"))
    
    # Step 5: LLM (Simulation of generation)
    llm = trace_data.get("llm_model", "gpt-4-turbo")
    gen_ms = trace_data.get("llm_ms", 0)
    
    llm_node = tree.add(Text(f"🤖 LLM Generation ({llm})", style="bold red"))
    llm_node.add(Text(f"Response generated in {gen_ms/1000:.1f}s", style="dim"))
    
    # Render
    console.print(Panel(
        tree,
        title="[bold]RAG Pipeline Trace[/bold]",
        border_style="blue"
    ))

if __name__ == "__main__":
    # Demo
    trace = {
        "query": "How does the indexer handle python async functions?",
        "embedding_model": "nomic-embed-text-v1.5",
        "embedding_ms": 45,
        "retrieval_count": 150,
        "retrieval_ms": 120,
        "rerank_count": 10,
        "rerank_ms": 350,
        "context_tokens": 4200,
        "context_limit": 8192,
        "llm_model": "claude-3-5-sonnet",
        "llm_ms": 2400,
        "top_chunks": [
            {"path": "src/core/indexer.py", "score": 0.92},
            {"path": "src/parsers/python.py", "score": 0.88},
            {"path": "tests/test_async.py", "score": 0.85},
            {"path": "docs/architecture.md", "score": 0.72},
            {"path": "src/core/utils.py", "score": 0.65},
        ]
    }
    render_rag_flow(trace)
