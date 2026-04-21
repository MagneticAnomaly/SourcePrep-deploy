"""
CoDRAG CLI Trace Visualization

Visualizes structural code analysis data (GraphRAG).
Includes degree distribution, hub identification, and graph stats.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

def render_trace_stats(
    stats: dict,
    top_hubs: list[dict] | None = None,
    console: Console | None = None
) -> None:
    """
    Render a structural analysis dashboard for the trace index.
    
    Args:
        stats: Dictionary containing graph statistics
            - node_count: int
            - edge_count: int
            - density: float
            - avg_degree: float
            - communities: int
        top_hubs: List of dicts {name, kind, degree} for most connected nodes
    """
    if console is None:
        console = Console()
        
    node_count = stats.get("node_count", 0)
    edge_count = stats.get("edge_count", 0)
    avg_degree = stats.get("avg_degree", 0.0)
    
    # --- Top Panel: Network Metrics ---
    metrics_grid = Table.grid(expand=True, padding=2)
    metrics_grid.add_column(justify="center", ratio=1)
    metrics_grid.add_column(justify="center", ratio=1)
    metrics_grid.add_column(justify="center", ratio=1)
    
    def metric_cell(label, value, color="white"):
        return Text.assemble(
            (f"{value}\n", f"bold {color}"),
            (label, "dim")
        )

    metrics_grid.add_row(
        metric_cell("Total Nodes", f"{node_count:,}", "cyan"),
        metric_cell("Total Edges", f"{edge_count:,}", "yellow"),
        metric_cell("Avg Connections", f"{avg_degree:.1f}", "green"),
    )
    
    console.print(Panel(
        metrics_grid,
        title="[bold]Trace Index Structure[/bold]",
        border_style="blue"
    ))
    
    # --- Bottom Panel: Hubs (Central Nodes) ---
    if top_hubs:
        hubs_table = Table(
            box=box.SIMPLE_HEAD, 
            show_edge=False, 
            expand=True,
            header_style="dim"
        )
        hubs_table.add_column("Rank", width=4, justify="right")
        hubs_table.add_column("Symbol", ratio=1)
        hubs_table.add_column("Type", width=10)
        hubs_table.add_column("Connections", justify="right", width=12)
        hubs_table.add_column("Viz", width=15)
        
        max_degree = max((h.get("degree", 0) for h in top_hubs), default=1)
        
        for i, hub in enumerate(top_hubs, 1):
            degree = hub.get("degree", 0)
            
            # Bar viz
            bar_len = int((degree / max_degree) * 12)
            bar = "█" * bar_len
            
            # Kind color
            kind = hub.get("kind", "symbol")
            color = "cyan" if kind == "class" else "green" if kind == "function" else "yellow"
            
            hubs_table.add_row(
                f"{i}.",
                Text(hub.get("name", "?"), style="bold"),
                f"[{color}]{kind}[/{color}]",
                str(degree),
                f"[{color}]{bar}[/{color}]"
            )
            
        console.print(Panel(
            hubs_table,
            title="[bold]Structural Hubs (Most Connected)[/bold]",
            border_style="dim"
        ))

if __name__ == "__main__":
    # Demo
    stats = {
        "node_count": 850,
        "edge_count": 2341,
        "avg_degree": 5.5,
    }
    hubs = [
        {"name": "IndexManager", "kind": "class", "degree": 42},
        {"name": "build_graph", "kind": "function", "degree": 35},
        {"name": "CodeNode", "kind": "class", "degree": 28},
        {"name": "process_file", "kind": "function", "degree": 15},
        {"name": "utils.py", "kind": "module", "degree": 12},
    ]
    render_trace_stats(stats, top_hubs=hubs)
