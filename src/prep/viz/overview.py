"""
CoDRAG CLI Dashboard Overview

Combines multiple visualizations into a single comprehensive dashboard view.
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich import box
from datetime import datetime

from .health import render_index_health
from .activity_heatmap import render_activity_heatmap, ActivityHeatmapData, ActivityDay
from .trace import render_trace_stats

def render_dashboard(
    health_stats: dict,
    activity_data: ActivityHeatmapData,
    trace_stats: dict,
    weeks: int = 12,
    console: Console | None = None
) -> None:
    """
    Render the full CoDRAG CLI dashboard.
    
    Args:
        health_stats: Stats for index health
        activity_data: Data for activity heatmap
        trace_stats: Stats for trace analysis
    """
    if console is None:
        console = Console()
        
    # --- Layout Setup ---
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="top", size=12),
        Layout(name="middle", size=12),
        Layout(name="bottom", ratio=1),
    )
    
    # --- Header ---
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header_text = Text(f" CoDRAG Index Dashboard • {now} ", style="bold white on blue", justify="center")
    layout["header"].update(header_text)
    
    # --- Top: Health & DNA ---
    # We'll use a simplified version of render_index_health content here
    # Since rich layouts can't easily nest full render functions that print directly,
    # we ideally would refactor those viz functions to return Renderables.
    # For now, we'll create a layout that mimics the health view structure.
    
    # NOTE: To properly compose this, we should refactor the individual viz modules 
    # to return Layout/Panel objects instead of printing directly. 
    # However, for this MVP 'overview', we might just print sections sequentially 
    # or use a grid if we keep the direct printing pattern (which is harder to layout).
    
    # Strategy: Since the existing viz functions print directly to console,
    # we cannot easily embed them in a Layout() without capturing output.
    # Refactoring them to return objects is better.
    # For this file, I will implement a 'composed' view assuming we can't change 
    # the other files right this second without breaking their CLI commands.
    
    # ACTUALLY: Let's just print them sequentially with nice headers for the MVP 
    # to avoid complex refactoring of the existing modules in this turn.
    # OR, better yet, let's make this function just print them in order.
    
    console.print(Panel(header_text, style="blue", box=box.HEAVY))
    console.print("")
    
    render_index_health(health_stats, console=console)
    console.print("")
    
    render_activity_heatmap(activity_data, weeks=weeks, console=console)
    console.print("")
    
    render_trace_stats(trace_stats, console=console)

if __name__ == "__main__":
    # Demo data
    stats = {
        "total_files": 1240,
        "indexed_files": 1100,
        "embeddings_count": 4500,
        "trace_nodes": 850,
        "trace_edges": 2300,
        "last_build": "2023-10-27 14:30:00",
        "disk_usage_mb": 45.2
    }
    
    # Sample activity
    import random
    days = []
    for i in range(84):
        days.append(ActivityDay(
            date=f"2023-01-{i%30+1}", 
            embeddings=random.randint(0, 50),
            trace=random.randint(0, 30),
            builds=random.randint(0, 2)
        ))
    
    activity = ActivityHeatmapData(
        days=days, 
        totals={"embeddings": 1200, "trace": 800, "builds": 15}
    )
    
    trace = {
        "node_count": 850,
        "edge_count": 2341,
        "avg_degree": 5.5,
    }
    
    render_dashboard(stats, activity, trace)
