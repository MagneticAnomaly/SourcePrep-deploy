"""
CoDRAG CLI Data Visualization

This module provides terminal-based visualizations that mirror
the GUI components in @codrag/ui. Same data models, different renderers.
"""

from .activity_heatmap import render_activity_heatmap, ActivityDay, ActivityHeatmapData
from .health import render_index_health
from .context import render_token_budget, render_relevance_spectrum
from .trace import render_trace_stats
from .coverage import render_file_coverage
from .overview import render_dashboard
from .drift import render_drift_report
from .flow import render_rag_flow

__all__ = [
    "render_activity_heatmap",
    "ActivityDay",
    "ActivityHeatmapData",
    "render_index_health",
    "render_token_budget",
    "render_relevance_spectrum",
    "render_trace_stats",
    "render_file_coverage",
    "render_dashboard",
    "render_drift_report",
    "render_rag_flow",
]
