"""
CLI Activity Heatmap Visualization

Renders a GitHub-style contribution grid in the terminal using rich.
Same data model as the GUI ActivityHeatmap component in @codrag/ui.

Color scheme:
- Cyan: Embeddings activity
- Yellow/Amber: Trace activity  
- Green: Mixed (both embeddings and trace)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class ActivityDay:
    """Single day of activity data."""
    date: str           # ISO date (YYYY-MM-DD)
    embeddings: int     # Files embedded
    trace: int          # Symbols traced
    builds: int         # Build count


@dataclass
class ActivityHeatmapData:
    """Activity data for heatmap visualization."""
    days: list[ActivityDay]
    totals: dict  # { embeddings, trace, builds }


# Block characters for intensity levels
BLOCKS = ['░', '▒', '▓', '█']

# ANSI color codes
CYAN = 'cyan'
YELLOW = 'yellow'
GREEN = 'green'
DIM = 'dim'

DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def get_cell_char(embeddings: int, trace: int, max_embeddings: int, max_trace: int) -> tuple[str, str]:
    """
    Get the character and color for a cell based on activity levels.
    
    Returns:
        Tuple of (character, color_style)
    """
    if embeddings == 0 and trace == 0:
        return '░', DIM
    
    embedding_intensity = embeddings / max_embeddings if max_embeddings > 0 else 0
    trace_intensity = trace / max_trace if max_trace > 0 else 0
    
    # Determine block character based on intensity
    def intensity_to_block(intensity: float) -> str:
        if intensity > 0.75:
            return '█'
        elif intensity > 0.5:
            return '▓'
        elif intensity > 0.25:
            return '▒'
        return '░'
    
    # Pure embedding (cyan)
    if trace == 0:
        return intensity_to_block(embedding_intensity), CYAN
    
    # Pure trace (yellow)
    if embeddings == 0:
        return intensity_to_block(trace_intensity), YELLOW
    
    # Mixed (green)
    combined = (embedding_intensity + trace_intensity) / 2
    return intensity_to_block(combined), GREEN


def render_activity_heatmap(
    data: ActivityHeatmapData,
    weeks: int = 12,
    show_legend: bool = True,
    show_labels: bool = True,
    console: Optional[Console] = None,
) -> None:
    """
    Render activity heatmap to terminal.
    
    Args:
        data: Activity data to visualize
        weeks: Number of weeks to display (default 12)
        show_legend: Show color legend below grid
        show_labels: Show day/month labels
        console: Rich console instance (creates new if None)
    """
    if console is None:
        console = Console()
    
    # Build activity map
    activity_map = {day.date: day for day in data.days}
    
    # Calculate max values for intensity scaling
    max_embeddings = max((d.embeddings for d in data.days), default=1) or 1
    max_trace = max((d.trace for d in data.days), default=1) or 1
    
    # Generate grid dates
    today = date.today()
    start_date = today - timedelta(days=weeks * 7 + today.weekday())
    
    # Build grid (7 rows x N columns)
    grid: list[list[tuple[date, ActivityDay | None]]] = [[] for _ in range(7)]
    
    current = start_date
    while current <= today:
        day_of_week = current.weekday()  # 0=Monday
        date_str = current.isoformat()
        activity = activity_map.get(date_str)
        grid[day_of_week].append((current, activity))
        current += timedelta(days=1)
    
    # Render
    output = Text()
    
    # Header with totals
    output.append("Activity ", style="bold")
    output.append(f"(last {weeks} weeks)\n", style="dim")
    output.append(f"  Embeddings: {data.totals.get('embeddings', 0):,}  ", style=CYAN)
    output.append(f"Trace: {data.totals.get('trace', 0):,}  ", style=YELLOW)
    output.append(f"Builds: {data.totals.get('builds', 0):,}\n\n", style=GREEN)
    
    # Month labels
    if show_labels:
        output.append("       ")  # Indent for day labels
        last_month = -1
        for i, (d, _) in enumerate(grid[0]):
            if d.month != last_month:
                output.append(MONTHS[d.month - 1] + " ", style="dim")
                last_month = d.month
            else:
                output.append("  ")
        output.append("\n")
    
    # Grid rows (one per day of week)
    for day_idx, day_name in enumerate(DAYS_OF_WEEK):
        if show_labels:
            output.append(f"{day_name} ", style="dim")
        
        for d, activity in grid[day_idx]:
            embeddings = activity.embeddings if activity else 0
            trace = activity.trace if activity else 0
            char, color = get_cell_char(embeddings, trace, max_embeddings, max_trace)
            output.append(char, style=color)
        
        output.append("\n")
    
    # Legend
    if show_legend:
        output.append("\n")
        output.append("Legend: ", style="dim")
        output.append("░", style="dim")
        output.append(" none  ", style="dim")
        output.append("▓", style=CYAN)
        output.append(" embedding  ", style="dim")
        output.append("█", style=YELLOW)
        output.append(" trace  ", style="dim")
        output.append("▓", style=GREEN)
        output.append(" mixed", style="dim")
    
    # Wrap in panel
    panel = Panel(
        output,
        title="[bold]Index Activity[/bold]",
        border_style="dim",
    )
    console.print(panel)


def generate_sample_data(weeks: int = 12) -> ActivityHeatmapData:
    """Generate sample activity data for testing."""
    import random
    
    days = []
    today = date.today()
    total_embeddings = 0
    total_trace = 0
    total_builds = 0
    
    for i in range(weeks * 7, -1, -1):
        d = today - timedelta(days=i)
        is_weekend = d.weekday() >= 5
        has_activity = random.random() > (0.7 if is_weekend else 0.3)
        
        if has_activity:
            embeddings = random.randint(0, 50)
            trace = random.randint(0, 30) if random.random() > 0.5 else 0
            builds = random.randint(1, 3) if random.random() > 0.7 else 0
            
            days.append(ActivityDay(
                date=d.isoformat(),
                embeddings=embeddings,
                trace=trace,
                builds=builds,
            ))
            total_embeddings += embeddings
            total_trace += trace
            total_builds += builds
    
    return ActivityHeatmapData(
        days=days,
        totals={
            'embeddings': total_embeddings,
            'trace': total_trace,
            'builds': total_builds,
        },
    )


if __name__ == "__main__":
    # Demo
    console = Console()
    sample = generate_sample_data(12)
    render_activity_heatmap(sample, weeks=12, console=console)
