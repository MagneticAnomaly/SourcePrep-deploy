"""
CoDRAG CLI Index Drift Visualization

Visualizes the "freshness" of the index compared to the filesystem.
Identifies "rotting" files (modified after indexing) and age distribution.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from datetime import datetime, timedelta

def render_drift_report(
    drift_stats: dict,
    rotting_files: list[dict] | None = None,
    console: Console | None = None
) -> None:
    """
    Render a report on index freshness and drift.
    
    Args:
        drift_stats: Dict with keys:
            - freshness_score: float (0-100)
            - total_files: int
            - fresh_files: int
            - stale_files: int
            - missing_files: int
            - last_scan: str (ISO date)
        rotting_files: List of dicts {path, modified_at, indexed_at, age_gap}
    """
    if console is None:
        console = Console()
        
    score = drift_stats.get("freshness_score", 0)
    
    # --- Score Gauge ---
    # [██████████░░░░] 75%
    bar_width = 30
    filled = int((score / 100) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    color = "green" if score > 90 else "yellow" if score > 70 else "red"
    
    header = Table.grid(expand=True)
    header.add_column(ratio=1)
    header.add_column(justify="right")
    
    header.add_row(
        Text("Index Freshness", style="bold"),
        Text(f"{score:.1f}%", style=f"bold {color}")
    )
    header.add_row(f"[{color}]{bar}[/{color}]", "")
    
    # --- Stats ---
    stats_table = Table(box=box.SIMPLE, show_header=False, padding=0)
    stats_table.add_column("Label", style="dim")
    stats_table.add_column("Value", justify="right")
    
    total = drift_stats.get("total_files", 0)
    fresh = drift_stats.get("fresh_files", 0)
    stale = drift_stats.get("stale_files", 0)
    missing = drift_stats.get("missing_files", 0)
    
    stats_table.add_row("Total Files", f"{total:,}")
    stats_table.add_row("Fresh (Synced)", f"[green]{fresh:,}[/green]")
    stats_table.add_row("Stale (Rotting)", f"[yellow]{stale:,}[/yellow]")
    stats_table.add_row("Missing (New)", f"[red]{missing:,}[/red]")
    
    # --- Rotting Files List ---
    rot_table = None
    if rotting_files:
        rot_table = Table(
            title="[bold yellow]Rotting Content (Needs Rebuild)[/bold yellow]",
            box=box.SIMPLE_HEAD,
            expand=True,
            header_style="yellow"
        )
        rot_table.add_column("File Path", ratio=1)
        rot_table.add_column("Lag", justify="right", width=12)
        
        for file in rotting_files[:5]: # Show top 5
            path = file.get("path", "unknown")
            lag = file.get("age_gap", "unknown")
            rot_table.add_row(path, lag)
            
        if len(rotting_files) > 5:
            rot_table.add_row(f"... and {len(rotting_files)-5} more", "")

    # --- Layout ---
    main_grid = Table.grid(padding=1, expand=True)
    main_grid.add_row(header)
    main_grid.add_row("")
    main_grid.add_row(stats_table)
    
    if rot_table:
        main_grid.add_row("")
        main_grid.add_row(rot_table)
        
    console.print(Panel(
        main_grid,
        title="[bold]Index Drift Analysis[/bold]",
        border_style=color
    ))

if __name__ == "__main__":
    # Demo
    stats = {
        "freshness_score": 82.5,
        "total_files": 1240,
        "fresh_files": 1023,
        "stale_files": 145,
        "missing_files": 72,
        "last_scan": "2023-10-27 15:00:00"
    }
    
    rotting = [
        {"path": "src/core/index.py", "age_gap": "2h 15m"},
        {"path": "src/api/routes.py", "age_gap": "45m"},
        {"path": "README.md", "age_gap": "10m"},
        {"path": "docs/architecture.md", "age_gap": "5m"},
        {"path": "tests/test_search.py", "age_gap": "2m"},
        {"path": "infra/docker.tf", "age_gap": "1m"},
    ]
    
    render_drift_report(stats, rotting)
