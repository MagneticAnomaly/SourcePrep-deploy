"""
CoDRAG CLI Health Visualization (Index DNA)

Visualizes the health and coverage of the code index.
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

def render_index_health(
    stats: dict,
    console: Console | None = None
) -> None:
    """
    Render a rich dashboard showing index health.
    
    Args:
        stats: Dictionary containing index statistics
            - total_files: int
            - indexed_files: int
            - embeddings_count: int
            - trace_nodes: int
            - last_build: str (ISO date)
            - disk_usage_mb: float
    """
    if console is None:
        console = Console()

    # Calculate metrics
    total = stats.get("total_files", 0) or 1
    indexed = stats.get("indexed_files", 0)
    coverage = (indexed / total) * 100
    
    embeddings = stats.get("embeddings_count", 0)
    trace_nodes = stats.get("trace_nodes", 0)
    trace_edges = stats.get("trace_edges", 0)
    
    # --- Layout Setup ---
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", size=10),
        Layout(name="footer", size=3)
    )
    
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )

    # --- Header ---
    title = Text(" 🧬 Index DNA & Health Report ", style="bold white on blue")
    layout["header"].update(Panel(title, box=box.HEAVY, style="blue"))

    # --- Left Panel: Coverage DNA ---
    # Simulate a DNA strip of file status
    # In a real implementation, this would map to actual file statuses
    dna_segments = []
    import random
    
    # Deterministic "random" based on total count for visual stability
    random.seed(total)
    
    for _ in range(40):
        r = random.random()
        if r > 0.9:
            dna_segments.append(("█", "red"))     # Error/Missing
        elif r > 0.7:
            dna_segments.append(("▓", "yellow"))  # Outdated
        else:
            dna_segments.append(("█", "green"))   # Indexed
            
    dna_visual = Text()
    for char, color in dna_segments:
        dna_visual.append(char, style=color)
        dna_visual.append(" ")
        
    coverage_text = Text(f"{coverage:.1f}%", style="bold green" if coverage > 80 else "yellow")
    
    left_content = Table.grid(padding=1)
    left_content.add_column(style="bold")
    left_content.add_column()
    
    left_content.add_row("Coverage Score:", coverage_text)
    left_content.add_row("Indexed Files:", f"{indexed:,} / {total:,}")
    left_content.add_row("Health DNA:", dna_visual)
    
    layout["left"].update(Panel(
        left_content, 
        title="[bold]Semantic Coverage[/bold]",
        border_style="green"
    ))

    # --- Right Panel: Structural Stats ---
    right_content = Table.grid(padding=1)
    right_content.add_column(style="bold")
    right_content.add_column(justify="right")
    
    right_content.add_row("Vector Dimensions:", "768")
    right_content.add_row("Embeddings:", f"{embeddings:,}")
    right_content.add_row("Trace Symbols:", f"{trace_nodes:,}")
    right_content.add_row("Trace Edges:", f"{trace_edges:,}")
    right_content.add_row("Disk Usage:", f"{stats.get('disk_usage_mb', 0):.1f} MB")
    
    layout["right"].update(Panel(
        right_content,
        title="[bold]Structural Depth[/bold]",
        border_style="cyan"
    ))
    
    # --- Footer: Status ---
    last_build = stats.get("last_build", "Never")
    status = "READY" if coverage > 0 else "EMPTY"
    footer_text = f"Status: {status} • Last Build: {last_build}"
    layout["footer"].update(Panel(Text(footer_text, justify="center"), style="dim"))

    console.print(layout)

if __name__ == "__main__":
    # Demo
    stats = {
        "total_files": 1240,
        "indexed_files": 1100,
        "embeddings_count": 4500,
        "trace_nodes": 850,
        "trace_edges": 2300,
        "last_build": "2023-10-27 14:30:00",
        "disk_usage_mb": 45.2
    }
    render_index_health(stats)
