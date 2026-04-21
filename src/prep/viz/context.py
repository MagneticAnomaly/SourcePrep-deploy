"""
CoDRAG CLI Context & Search Visualizations

Visualizes token usage, search relevance, and context assembly metrics.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

def render_token_budget(
    used_tokens: int,
    limit_tokens: int,
    breakdown: dict[str, int] | None = None,
    console: Console | None = None
) -> None:
    """
    Render a token budget gauge showing context window usage.
    
    Args:
        used_tokens: Number of tokens used
        limit_tokens: Context window limit (budget)
        breakdown: Optional dict of {category: token_count}
                   e.g. {'system': 100, 'query': 50, 'chunks': 4000}
    """
    if console is None:
        console = Console()
        
    usage_pct = min(100, (used_tokens / limit_tokens) * 100)
    
    # Color based on usage
    color = "green"
    if usage_pct > 75:
        color = "yellow"
    if usage_pct > 90:
        color = "red"
        
    # Create the gauge bar
    bar_width = 40
    filled = int((used_tokens / limit_tokens) * bar_width)
    filled = min(filled, bar_width)
    empty = bar_width - filled
    
    bar_visual = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
    
    # Main panel content
    grid = Table.grid(padding=1)
    grid.add_column()
    grid.add_column(justify="right")
    
    grid.add_row(Text("Context Usage", style="bold"), Text(f"{usage_pct:.1f}%", style=color))
    grid.add_row(bar_visual, "")
    grid.add_row(f"{used_tokens:,} / {limit_tokens:,} tokens", "")
    
    # Breakdown breakdown if provided
    if breakdown:
        grid.add_row("", "") # Spacer
        grid.add_row(Text("Breakdown", style="dim underline"), "")
        for cat, count in breakdown.items():
            cat_pct = (count / used_tokens) * 100 if used_tokens > 0 else 0
            grid.add_row(f"{cat}:", f"{count:,} ({cat_pct:.1f}%)")

    console.print(Panel(
        grid,
        title="[bold]Token Budget[/bold]",
        border_style="dim",
        width=60
    ))


def render_relevance_spectrum(
    results: list[dict],
    console: Console | None = None
) -> None:
    """
    Render a visual spectrum of search result relevance scores.
    
    Args:
        results: List of dicts with 'score' (0-1) and 'source_path'
    """
    if console is None:
        console = Console()
        
    if not results:
        return

    # Sort just in case, though search usually returns sorted
    scores = [r.get('score', 0) for r in results]
    max_score = max(scores) if scores else 1
    min_score = min(scores) if scores else 0
    
    # Create a spectrum visual
    # High scores (near 1.0) -> Cyan/Green
    # Mid scores (0.5-0.7) -> Yellow
    # Low scores (<0.5) -> Red/Dim
    
    chart_height = 5
    chart_width = len(results) * 2
    
    # ASCII Bar Chart logic
    # We want to draw bars for each result
    # r1 r2 r3 ...
    
    bars = []
    for r in results:
        score = r.get('score', 0)
        
        # Color
        if score > 0.8: color = "cyan"
        elif score > 0.6: color = "green"
        elif score > 0.4: color = "yellow"
        else: color = "red"
        
        # Height (1-8 blocks) using block chars
        #  , ▂, ▃, ▄, ▅, ▆, ▇, █
        blocks = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        idx = int(score * 7)
        idx = max(0, min(7, idx))
        char = blocks[idx]
        
        bars.append(f"[{color}]{char}[/{color}]")
        
    spectrum = "".join(bars)
    
    # Create table for detailed top results
    table = Table(box=box.SIMPLE, show_header=False, padding=0)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Score", width=8)
    table.add_column("Viz", width=10)
    table.add_column("Path")
    
    for i, r in enumerate(results[:5]): # Show top 5 details
        score = r.get('score', 0)
        # Mini bar for the table row
        bar_len = int(score * 8)
        bar_str = "█" * bar_len
        
        if score > 0.8: color = "cyan"
        elif score > 0.6: color = "green"
        else: color = "yellow"
        
        path = r.get('doc', {}).get('source_path', 'unknown')
        
        table.add_row(
            f"#{i+1}", 
            f"{score:.3f}", 
            f"[{color}]{bar_str}[/{color}]", 
            path
        )

    # Layout
    grid = Table.grid(padding=1)
    grid.add_row(Text("Relevance Spectrum", style="bold"))
    grid.add_row(spectrum)
    grid.add_row("")
    grid.add_row(table)
    
    if len(results) > 5:
        grid.add_row(Text(f"... and {len(results)-5} more results", style="dim italic"))

    console.print(Panel(
        grid,
        title="[bold]Search Analysis[/bold]",
        border_style="dim",
    ))

if __name__ == "__main__":
    # Demo
    render_token_budget(
        4500, 
        8192, 
        breakdown={"System": 500, "Query": 120, "Chunks": 3880}
    )
    
    results = [
        {"score": 0.92, "doc": {"source_path": "src/core/index.ts"}},
        {"score": 0.88, "doc": {"source_path": "src/utils/helpers.ts"}},
        {"score": 0.75, "doc": {"source_path": "tests/core_test.ts"}},
        {"score": 0.65, "doc": {"source_path": "docs/README.md"}},
        {"score": 0.45, "doc": {"source_path": "package.json"}},
        {"score": 0.30, "doc": {"source_path": "legacy/old.ts"}},
    ]
    render_relevance_spectrum(results)
