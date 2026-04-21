"""
CoDRAG CLI File Tree Coverage Visualization

Visualizes which parts of the codebase are indexed vs excluded.
"""

from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.panel import Panel
from rich.style import Style

def render_file_coverage(
    file_tree: dict,
    console: Console | None = None
) -> None:
    """
    Render a file tree showing index coverage.
    
    Args:
        file_tree: Nested dict structure representing the file system.
                   Each node should have:
                   - name: str
                   - type: 'file' | 'dir'
                   - status: 'indexed' | 'excluded' | 'error' | 'missing'
                   - children: list[dict] (if dir)
                   - coverage: float (0-1, optional for dirs)
    """
    if console is None:
        console = Console()

    root_node = file_tree
    
    # Create the root of the rich Tree
    root_label = Text(root_node.get("name", "root"), style="bold blue")
    if "coverage" in root_node:
        cov = root_node["coverage"]
        color = "green" if cov > 0.8 else "yellow" if cov > 0.5 else "red"
        root_label.append(f" [{cov*100:.0f}%]", style=color)
        
    tree = Tree(root_label)
    
    def add_children(tree_node: Tree, data_node: dict):
        for child in data_node.get("children", []):
            name = child.get("name", "?")
            node_type = child.get("type", "file")
            status = child.get("status", "unknown")
            
            # Determine icon and style
            if node_type == "dir":
                icon = "📂 "
                style = "bold blue"
                cov = child.get("coverage", 0)
                
                # Visual indicator for directory coverage
                # [████░░]
                bar_len = 5
                filled = int(cov * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                bar_color = "green" if cov > 0.8 else "yellow" if cov > 0.5 else "red"
                
                label = Text(icon)
                label.append(name, style=style)
                label.append(f" [{bar}]", style=bar_color)
                
                branch = tree_node.add(label)
                add_children(branch, child)
                
            else:
                # File
                icon = "📄 "
                style = "white"
                
                if status == "indexed":
                    status_icon = "✓"
                    status_style = "green"
                elif status == "excluded":
                    status_icon = "∅"
                    status_style = "dim"
                    style = "dim"
                elif status == "error":
                    status_icon = "✗"
                    status_style = "red"
                else:
                    status_icon = "?"
                    status_style = "yellow"
                    
                label = Text(icon)
                label.append(name, style=style)
                label.append(f" {status_icon}", style=status_style)
                
                tree_node.add(label)

    add_children(tree, root_node)
    
    console.print(Panel(
        tree,
        title="[bold]File Coverage Tree[/bold]",
        border_style="dim"
    ))

if __name__ == "__main__":
    # Demo data
    tree_data = {
        "name": "src",
        "type": "dir",
        "coverage": 0.75,
        "children": [
            {
                "name": "api",
                "type": "dir",
                "coverage": 1.0,
                "children": [
                    {"name": "server.py", "type": "file", "status": "indexed"},
                    {"name": "routes.py", "type": "file", "status": "indexed"},
                ]
            },
            {
                "name": "utils",
                "type": "dir",
                "coverage": 0.5,
                "children": [
                    {"name": "helpers.py", "type": "file", "status": "indexed"},
                    {"name": "legacy.py", "type": "file", "status": "excluded"},
                ]
            },
            {
                "name": "tests",
                "type": "dir",
                "coverage": 0.0,
                "children": [
                    {"name": "test_api.py", "type": "file", "status": "excluded"},
                ]
            }
        ]
    }
    render_file_coverage(tree_data)
