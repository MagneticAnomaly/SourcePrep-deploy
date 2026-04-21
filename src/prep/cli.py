"""
Prep CLI entry point.

Usage:
    prep serve              Start the daemon
    prep add <path>         Add a project
    prep list               List projects
    prep build <id>         Build project index
    prep search <id> <q>    Search project
    prep reset              Full reset (delete all project data)
    prep sync-headless      Run headless team sync (CI/CD)
    prep ui                 Open dashboard
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from prep import __version__

app = typer.Typer(
    name="prep",
    help="Prep - Code Documentation and RAG.\n\nSemantic search, context assembly, and structural analysis for your codebase.",
    no_args_is_help=False,
    add_completion=False,
)
console = Console()


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _post_json(url: str, payload: dict) -> Any:
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return _unwrap_envelope(r.json())
    except requests.exceptions.HTTPError as e:
        try:
            err = e.response.json()
            if isinstance(err, dict) and "error" in err:
                code = err["error"].get("code", "ERROR")
                msg = err["error"].get("message", str(e))
                console.print(f"[red]Error ({code}): {msg}[/red]")
                if "hint" in err["error"]:
                    console.print(f"[dim]Hint: {err['error']['hint']}[/dim]")
                raise typer.Exit(1)
        except ValueError:
            pass
        console.print(f"[red]HTTP Error: {e}[/red]")
        raise typer.Exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to Prep daemon at {url}[/red]")
        console.print("[dim]Is the server running? Try: prep serve[/dim]")
        raise typer.Exit(1)


def _get_json(url: str) -> Any:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return _unwrap_envelope(r.json())
    except requests.exceptions.HTTPError as e:
        try:
            err = e.response.json()
            if isinstance(err, dict) and "error" in err:
                code = err["error"].get("code", "ERROR")
                msg = err["error"].get("message", str(e))
                console.print(f"[red]Error ({code}): {msg}[/red]")
                if "hint" in err["error"]:
                    console.print(f"[dim]Hint: {err['error']['hint']}[/dim]")
                raise typer.Exit(1)
        except ValueError:
            pass
        console.print(f"[red]HTTP Error: {e}[/red]")
        raise typer.Exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to Prep daemon at {url}[/red]")
        console.print("[dim]Is the server running? Try: prep serve[/dim]")
        raise typer.Exit(1)


def _delete_json(url: str) -> Any:
    try:
        r = requests.delete(url, timeout=60)
        r.raise_for_status()
        return _unwrap_envelope(r.json())
    except requests.exceptions.HTTPError as e:
        try:
            err = e.response.json()
            if isinstance(err, dict) and "error" in err:
                code = err["error"].get("code", "ERROR")
                msg = err["error"].get("message", str(e))
                console.print(f"[red]Error ({code}): {msg}[/red]")
                if "hint" in err["error"]:
                    console.print(f"[dim]Hint: {err['error']['hint']}[/dim]")
                raise typer.Exit(1)
        except ValueError:
            pass
        console.print(f"[red]HTTP Error: {e}[/red]")
        raise typer.Exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to Prep daemon at {url}[/red]")
        console.print("[dim]Is the server running? Try: prep serve[/dim]")
        raise typer.Exit(1)


def _is_server_available(base: str) -> bool:
    """Quick health check — returns True if the daemon responds."""
    try:
        r = requests.get(f"{base}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _unwrap_envelope(resp: Any) -> Any:
    """Extract `data` from the standard {success, data, error} envelope."""
    if isinstance(resp, dict):
        if resp.get("success") and "data" in resp:
            return resp["data"]
        if "error" in resp:
            err = resp["error"]
            code = err.get("code", "ERROR") if isinstance(err, dict) else "ERROR"
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            console.print(f"[red]Error ({code}): {msg}[/red]")
            raise typer.Exit(1)
    return resp


def _resolve_project(base: str, project_id: Optional[str] = None, auto: bool = True) -> str:
    """Resolve project ID from argument, CWD (auto), or default if single project."""
    if project_id:
        return project_id

    # List all projects
    try:
        data = _get_json(f"{base}/projects")
        projects = data.get("projects", []) if isinstance(data, dict) else []
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error listing projects: {e}[/red]")
        raise typer.Exit(1)

    if not projects:
        console.print("[yellow]No projects found in daemon.[/yellow]")
        console.print("Run 'prep add <path>' to register a project.")
        raise typer.Exit(1)

    # 1. Try auto-detect from CWD
    cwd = str(Path.cwd().resolve())
    if auto:
        best: Optional[Dict[str, Any]] = None
        best_len = -1
        for p in projects:
            p_path = str(p.get("path") or "").rstrip("/")
            if not p_path:
                continue
            if cwd == p_path or cwd.startswith(p_path + "/"):
                if len(p_path) > best_len:
                    best = p
                    best_len = len(p_path)
        
        if best and best.get("id"):
            pid = str(best.get("id"))
            # console.print(f"[dim]Auto-selected project: {best.get('name')} ({pid})[/dim]")
            return pid

    # 2. If only one project exists, use it
    if len(projects) == 1 and projects[0].get("id"):
        pid = str(projects[0].get("id"))
        return pid

    # 3. Ambiguous
    console.print("[red]Multiple projects available. Please specify --project-id or run inside a project directory.[/red]")
    table = Table(title="Available Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Path")
    for p in projects:
        table.add_row(p.get("id"), p.get("name"), p.get("path"))
    console.print(table)
    raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """
    Prep: Code Documentation and Retrieval Augmented Generation.

    Manage code indexes, run semantic searches, and assemble context for LLMs.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"Prep v{__version__}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8400, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """
    Start the Prep daemon.

    The daemon manages projects, indexes, and provides the API for clients/IDEs.
    """
    console.print(f"[green]Starting Prep server on {host}:{port}...[/green]")

    # Phase 113: ensure legacy ./codrag_data/ is migrated before
    # `prep.server` imports the store modules. Safe no-op in the
    # common case (sentinel present → no-op).
    from prep.core.data_dir_migration import (
        migrate_from_legacy_codrag,
        migrate_from_legacy_prep,
        migrate_legacy_data_dir,
    )
    migrate_from_legacy_codrag()  # codrag -> runprep XDG dirs (rename one-shot, D4)
    migrate_from_legacy_prep()    # prep -> runprep XDG dirs (brand-split one-shot)
    migrate_legacy_data_dir()     # CWD codrag_data -> XDG (Phase 113 one-shot)

    import uvicorn
    from prep.server import app as fastapi_app, configure, mount_dashboard

    configure()
    mount_dashboard()
    
    uvicorn.run("prep.server:app" if reload else fastapi_app, host=host, port=port, reload=reload)


@app.command()
def add(
    path: str = typer.Argument(..., help="Path to project root directory"),
    name: str = typer.Option(None, "--name", "-n", help="Project name (defaults to folder name)"),
    mode: str = typer.Option(
        "standalone", "--mode", "-m",
        help="Index location: standalone (app data dir, best for portability), "
             "embedded (.runprep/ in repo, best when boot disk is faster), "
             "or custom (specify --index-path, best for fast scratch disks)",
    ),
    index_path: str = typer.Option(
        None, "--index-path",
        help="Custom path for the index database (only used when --mode=custom). "
             "Ideal for NVMe scratch disks, Optane drives, or RAM disks.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Register a new project with the daemon.

    Does not automatically build the index. Run 'prep build' after adding.
    """
    base = _base_url(host, port)
    abs_path = str(Path(path).resolve())
    
    if mode == "custom" and not index_path:
        console.print("[red]Error:[/red] --index-path is required when --mode=custom")
        raise typer.Exit(1)
    
    payload: dict = {
        "path": abs_path,
        "mode": mode,
    }
    if name:
        payload["name"] = name
    if index_path:
        payload["index_path"] = str(Path(index_path).resolve())
        
    data = _post_json(f"{base}/projects", payload)
    p = data.get("project", {})
    
    console.print(f"[green]Project added successfully:[/green] {p.get('name')}")
    console.print(f"  ID: {p.get('id')}")
    console.print(f"  Path: {p.get('path')}")
    console.print(f"  Mode: {p.get('mode')}")
    if index_path:
        console.print(f"  Index Path: {p.get('index_path', index_path)}")
    console.print("\n[dim]Run 'prep build' to index this project.[/dim]")


@app.command("list")
def list_projects(
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """List all registered projects."""
    base = _base_url(host, port)
    data = _get_json(f"{base}/projects")
    
    projects = data.get("projects", [])
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(title="Prep Projects")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Path")
    table.add_column("Mode")
    table.add_column("Created")
    
    for p in projects:
        table.add_row(
            p.get("id"),
            p.get("name"),
            p.get("path"),
            p.get("mode"),
            p.get("created_at", "")[:19].replace("T", " "),
        )
    
    console.print(table)


def _do_remove(project_id: str, purge: bool, host: str, port: int) -> None:
    base = _base_url(host, port)
    url = f"{base}/projects/{project_id}"
    if purge:
        url += "?purge=true"
    try:
        r = requests.delete(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        console.print(f"[red]Error removing project: {e}[/red]")
        raise typer.Exit(1)
    if data.get("success"):
        console.print(f"[green]Project '{project_id}' removed.[/green]")
        if data.get("purged"):
            console.print("[dim]Index data purged.[/dim]")
    else:
        console.print(f"[red]Failed to remove project: {data}[/red]")


@app.command()
def remove(
    project_id: str = typer.Argument(..., help="Project ID to remove"),
    purge: bool = typer.Option(False, "--purge", help="Also delete the index data from disk"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Unregister a project.

    Use --purge to also delete the persistent index files.
    """
    _do_remove(project_id, purge, host, port)


@app.command("delete")
def delete(
    project_id: str = typer.Argument(..., help="Project ID to delete"),
    purge: bool = typer.Option(False, "--purge", help="Also delete the index data from disk"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Alias for 'remove'. Unregister a project (use --purge to also wipe index files)."""
    _do_remove(project_id, purge, host, port)


@app.command("prune")
def prune(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Prune orphan enrichments from the index.

    Removes entries in trace_epistemic.jsonl, trace_augmented.jsonl, and
    knowledge_documents.json that reference nodes no longer in the trace graph.
    Reclaims disk space and fixes inflated progress metrics.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)

    # Get the project's index directory from the daemon
    proj_data = _get_json(f"{base}/projects/{pid}")
    proj_path = proj_data.get("path", "")
    mode = proj_data.get("mode", "standalone")

    if mode == "embedded":
        idx_dir = Path(proj_path) / ".runprep"
    else:
        from prep.core.project_registry import prep_data_dir
        idx_dir = prep_data_dir() / "projects" / pid

    if not idx_dir.exists():
        console.print("[yellow]No index directory found.[/yellow]")
        raise typer.Exit(1)

    from prep.core.trace import prune_orphan_enrichments
    result = prune_orphan_enrichments(idx_dir)

    if result.get("skipped"):
        console.print(f"[yellow]Skipped: {result.get('reason', 'unknown')}[/yellow]")
        raise typer.Exit(0)

    total = result.get("total_pruned", 0)
    if total == 0:
        console.print("[green]No orphan enrichments found — index is clean.[/green]")
    else:
        console.print(f"[green]Pruned {total} orphan enrichments:[/green]")
        for key in ("epistemic", "augmented", "knowledge"):
            info = result.get(key, {})
            if info.get("pruned", 0) > 0:
                console.print(f"  {key}: {info['pruned']} removed, {info['kept']} kept")


@app.command()
def reset(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Full reset: delete ALL project data.

    Permanently deletes: embeddings, search index, trace graph, and all
    enrichment data. You will need to rebuild everything from scratch.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)

    if not yes:
        console.print("[bold red]⚠ FULL RESET — this will permanently delete ALL project data:[/bold red]")
        console.print("  • Embeddings and search index")
        console.print("  • Trace graph and all enrichment")
        console.print("  • Knowledge index")
        console.print("[dim]You will need to rebuild everything from scratch.[/dim]")
        confirm = typer.confirm("Are you absolutely sure?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    data = _delete_json(f"{base}/projects/{pid}/index/destroy")
    deleted = data.get("deleted", [])
    errors = data.get("errors", [])

    if deleted:
        console.print(f"[green]Full reset complete: deleted {len(deleted)} files.[/green]")
        for f in deleted:
            console.print(f"  [dim]- {f}[/dim]")
    else:
        console.print("[yellow]No data files found to delete.[/yellow]")

    if errors:
        console.print(f"[red]Errors ({len(errors)}):[/red]")
        for e in errors:
            console.print(f"  [red]- {e}[/red]")


@app.command()
def status(
    project_id: Optional[str] = typer.Argument(None, help="Project ID (optional if inside project dir)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Show index status for a project.

    Displays whether the index is loaded, build timestamp, and stats.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    
    data = _get_json(f"{base}/projects/{pid}/status")
    
    console.print(Panel(f"[bold]Project Status: {pid}[/bold]", expand=False))
    
    idx = data.get("index", {})
    trace = data.get("trace", {})
    
    # Embeddings Index
    if idx.get("exists"):
        console.print("[green]● Embeddings Index: Ready[/green]")
        console.print(f"  Chunks: {idx.get('total_chunks', 0):,}")
        console.print(f"  Model: {idx.get('embedding_model', 'unknown')}")
        console.print(f"  Last Build: {idx.get('last_build_at')}")
    else:
        console.print("[yellow]○ Embeddings Index: Not Built[/yellow]")
        console.print("  Run 'prep build' to create.")

    if data.get("building"):
        console.print("[cyan]  (Building in progress...)[/cyan]")
        
    console.print()
    
    # Code Graph
    if trace.get("exists"):
        console.print("[green]● Code Graph: Ready[/green]")
        counts = trace.get("counts", {})
        console.print(f"  Nodes: {counts.get('nodes', 0):,}")
        console.print(f"  Edges: {counts.get('edges', 0):,}")
    elif trace.get("enabled"):
        console.print("[yellow]○ Code Graph: Enabled but Not Built[/yellow]")
    else:
        console.print("[dim]○ Code Graph: Disabled[/dim]")
        
    if trace.get("building"):
        console.print("[cyan]  (Graph build in progress...)[/cyan]")


@app.command()
def build(
    project_id: Optional[str] = typer.Argument(None, help="Project ID (optional if inside project dir)"),
    full: bool = typer.Option(False, "--full", help="Force full rebuild (ignore incremental cache)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Trigger an index build.

    Builds are asynchronous. Use 'prep status' to check progress.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    
    url = f"{base}/projects/{pid}/build"
    if full:
        url += "?full=true"
        
    console.print(f"[cyan]Triggering build for project {pid}...[/cyan]")
    data = _post_json(url, {})
    
    if data.get("started"):
        console.print("[green]Build started successfully.[/green]")
        console.print("Use 'prep status' to monitor progress.")
    else:
        console.print(f"[yellow]Build did not start: {data}[/yellow]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language search query"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    k: int = typer.Option(10, "--limit", "-k", help="Number of results to return"),
    min_score: float = typer.Option(0.15, "--min-score", "-s", help="Minimum similarity score (0-1)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Semantic search across the codebase.

    Returns the most relevant code chunks for your query.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    
    data = _post_json(f"{base}/projects/{pid}/search", {
        "query": query,
        "k": k,
        "min_score": min_score,
    })
    
    results = data.get("results", [])
    if not results:
        console.print("[yellow]No results found matching query.[/yellow]")
        return
        
    console.print(f"[green]Found {len(results)} results for '{query}':[/green]\n")
    
    for i, r in enumerate(results, 1):
        path = r.get("source_path", "unknown")
        score = r.get("score", 0.0)
        preview = r.get("preview", "").strip()
        span = r.get("span", {})
        lines = f"{span.get('start_line', '?')}-{span.get('end_line', '?')}"
        
        console.print(f"[bold cyan]{i}. {path}:{lines}[/bold cyan] [dim](score: {score:.3f})[/dim]")
        if preview:
            # Simple syntax highlighting simulation
            safe_preview = preview[:200].replace('\n', ' ')
            console.print(f"   [dim]{safe_preview}...[/dim]")
        console.print()


@app.command()
def context(
    query: str = typer.Argument(..., help="Query to assemble context for"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    k: int = typer.Option(5, "--limit", "-k", help="Number of chunks to include"),
    max_chars: int = typer.Option(8000, "--max-chars", "-c", help="Maximum characters in context"),
    role: Optional[str] = typer.Option(None, "--role", help="Role filter for atlas (e.g. 'ceo', 'design engineer', 'security')"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output only the raw context string (for piping)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Assemble context for LLM prompts.

    Retrieves relevant chunks and formats them into a single context string
    optimized for LLM consumption (with source headers).

    Use --role to get a role-filtered codebase view appended to the context.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    
    data = _post_json(f"{base}/projects/{pid}/context", {
        "query": query,
        "k": k,
        "max_chars": max_chars,
        "include_sources": True,
        "structured": True,
    })
    
    ctx = data.get("context", "")
    chunks = data.get("chunks", [])
    total_chars = data.get("total_chars", 0)
    est_tokens = data.get("estimated_tokens", 0)

    # Phase 64A: Append role-filtered atlas if requested
    role_atlas = ""
    if role:
        try:
            atlas_data = _get_json(f"{base}/projects/{pid}/atlas?role={role}")
            role_atlas = atlas_data.get("role_atlas", "")
        except Exception:
            pass
    
    if raw:
        print(ctx)
        if role_atlas:
            print("\n---\n")
            print(role_atlas)
        return
        
    console.print(Panel(
        f"Chunks: {len(chunks)} | Chars: {total_chars} | Est. Tokens: {est_tokens}",
        title="Context Assembly Stats",
        expand=False
    ))
    console.print()
    console.print(ctx)

    if role_atlas:
        console.print()
        console.print(Panel(
            f"Role: {role} | Chars: {len(role_atlas)}",
            title="Role-Filtered Atlas",
            expand=False,
        ))
        console.print(role_atlas)


@app.command("models")
def models_download() -> None:
    """Download the built-in CPU embedding model (offline/air-gapped backup).

    Pre-downloads nomic-embed-text-v1.5 (quantized ONNX, ~132 MB) to the
    HuggingFace cache (~/.cache/huggingface/). Runs entirely on CPU —
    no GPU or Ollama required. Use this if you cannot run Ollama or need
    fully offline / air-gapped operation.
    """
    from prep.core.embedder import NativeEmbedder

    native = NativeEmbedder()
    if not native.is_available():
        console.print("[red]Error: Native embedder dependencies not installed.[/red]")
        console.print("[dim]Run: pip install onnxruntime tokenizers huggingface-hub[/dim]")
        raise typer.Exit(1)

    console.print(f"[cyan]Downloading model: {NativeEmbedder.HF_REPO_ID}[/cyan]")
    console.print(f"[dim]Files: {NativeEmbedder.TOKENIZER_FILE}, {NativeEmbedder.ONNX_FILE}[/dim]")

    try:
        model_path = native.download_model()
        console.print(f"[green]✓ Model downloaded to: {model_path}[/green]")
        console.print("[dim]Built-in ONNX model ready.[/dim]")
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ui(
    port: int = typer.Option(8400, "--port", "-p", help="Dashboard port"),
) -> None:
    """Open the Prep web dashboard."""
    import webbrowser
    url = f"http://localhost:{port}/ui"
    console.print(f"[green]Opening dashboard: {url}[/green]")
    webbrowser.open(url)


@app.command()
def mcp(
    project_id: str = typer.Option(None, "--project", "-p", help="Project ID (pinned mode)"),
    auto: bool = typer.Option(True, "--auto", "-a", help="Auto-detect project from cwd (Server Mode). Enabled by default."),
    mode: str = typer.Option("server", "--mode", "-m", help="Mode: server | direct"),
    daemon_url: str = typer.Option("http://127.0.0.1:8400", "--daemon", "-d", help="Prep daemon URL (Server Mode)"),
    repo_root: str = typer.Option(None, "--repo-root", "-r", help="Repository root (Direct Mode). Defaults to cwd."),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging (stderr)."),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write MCP debug logs to a file (rotating)."),
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio | http"),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP transport host"),
    port: int = typer.Option(8401, "--port", help="HTTP transport port"),
) -> None:
    """
    Run the Model Context Protocol (MCP) server.

    Connects IDEs (Cursor, Windsurf, Claude Desktop) to Prep.
    
    Modes:
      server (default): Bridges IDE to the running Prep daemon.
      direct: Runs the Prep engine in-process (no daemon required).
      
    Transports:
      stdio (default): Standard input/output (for local IDEs).
      http: Server-Sent Events (SSE) over HTTP (for remote/containerized IDEs).
    """
    from prep.mcp_server import main as mcp_server_main, configure_logging
    from prep.mcp_direct import DirectMCPServer, run_stdio
    import asyncio
    
    if mode == "direct":
        if transport == "http":
            print("[prep] Error: Direct mode currently only supports stdio transport.", file=sys.stderr)
            raise typer.Exit(1)
            
        root = Path(repo_root).resolve() if repo_root else Path.cwd()
        configure_logging(debug=bool(debug), log_file=log_file)
        print(f"[prep] Starting MCP (Direct Mode) at {root}...", file=sys.stderr)
        server = DirectMCPServer(repo_root=root)
        asyncio.run(run_stdio(server))
    else:
        # Server mode
        print(f"[prep] Starting MCP (Server Mode) -> {daemon_url}...", file=sys.stderr)
        mcp_server_main(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto,
            debug=bool(debug),
            log_file=log_file,
            transport=transport,
            host=host,
            port=port,
        )


@app.command("mcp-config")
def mcp_config(
    ide: str = typer.Option(
        "all",
        "--ide",
        "-i",
        help="Target IDE: claude, cursor, windsurf, vscode, jetbrains, all",
    ),
    mode: str = typer.Option("auto", "--mode", "-m", help="Mode: auto | project | direct"),
    daemon_url: str = typer.Option("http://127.0.0.1:8400", "--daemon", "-d", help="Prep daemon URL"),
    project_id: str = typer.Option(None, "--project", "-p", help="Optional pinned Project ID"),
) -> None:
    """
    Generate MCP configuration for IDEs.

    Prints the JSON configuration needed to add Prep to your IDE.
    """
    from prep.mcp_config import generate_mcp_configs
    
    # We simplify this command to assume "server" mode for most users
    resolved_mode = mode
    if resolved_mode == "auto" and project_id:
        resolved_mode = "project"
    try:
        configs = generate_mcp_configs(
            ide=ide,
            daemon_url=daemon_url,
            mode=resolved_mode,
            project_id=project_id
        )
    except Exception as e:
        console.print(f"[red]Error generating config: {e}[/red]")
        raise typer.Exit(1)

    if ide == "all":
        for name, cfg in configs.items():
            console.print(Panel(
                json.dumps(cfg["config"], indent=2),
                title=f"{name.upper()} Config ({cfg['file']})",
                expand=False
            ))
    else:
        # Single IDE
        cfg = next(iter(configs.values()))
        print(json.dumps(cfg["config"], indent=2))


@app.command()
def activity(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    weeks: int = typer.Option(12, "--weeks", "-w", help="Number of weeks to display"),
    no_legend: bool = typer.Option(False, "--no-legend", help="Hide color legend"),
    no_labels: bool = typer.Option(False, "--no-labels", help="Hide day/month labels"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON data"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Show index activity heatmap (GitHub-style contribution graph).
    
    Displays embeddings (cyan), trace (yellow), and mixed (green) activity.
    """
    from prep.viz.activity_heatmap import (
        render_activity_heatmap,
        generate_sample_data,
        ActivityHeatmapData,
        ActivityDay,
    )
    
    base = _base_url(host, port)
    
    try:
        if not _is_server_available(base):
            raise requests.exceptions.ConnectionError()
        pid = _resolve_project(base, project_id)
        # Try to fetch real data from server (endpoint not yet implemented)
        url = f"{base}/projects/{pid}/activity?weeks={weeks}"
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            raise ValueError("Activity API not available")
        r.raise_for_status()
        data = _unwrap_envelope(r.json())
        
        # Convert API response to ActivityHeatmapData
        days = [
            ActivityDay(
                date=d["date"],
                embeddings=d.get("embeddings", 0),
                trace=d.get("trace", 0),
                builds=d.get("builds", 0),
            )
            for d in data.get("days", [])
        ]
        activity_data = ActivityHeatmapData(
            days=days,
            totals=data.get("totals", {"embeddings": 0, "trace": 0, "builds": 0}),
        )
        
    except typer.Exit:
        raise
    except requests.exceptions.ConnectionError:
        # Server not running - use sample data for demo
        console.print("[yellow]Server not connected. Showing sample data.[/yellow]\n")
        activity_data = generate_sample_data(weeks)
    except Exception as e:
        # API endpoint not implemented yet - use sample data
        console.print(f"[yellow]Activity API not available ({e}). Showing sample data.[/yellow]\n")
        activity_data = generate_sample_data(weeks)
    
    if json_output:
        import json
        output = {
            "days": [{"date": d.date, "embeddings": d.embeddings, "trace": d.trace, "builds": d.builds} for d in activity_data.days],
            "totals": activity_data.totals,
        }
        console.print_json(json.dumps(output))
    else:
        render_activity_heatmap(
            activity_data,
            weeks=weeks,
            show_legend=not no_legend,
            show_labels=not no_labels,
            console=console,
        )


@app.command()
def config(
    key: str = typer.Argument(None, help="Config key to get/set (dot-notation, e.g. llm_config.embedding.source)"),
    value: str = typer.Argument(None, help="Value to set"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """View or modify Prep configuration."""
    import json
    base = _base_url(host, port)
    
    if key is None:
        # Show full config
        try:
            cfg = _get_json(f"{base}/global/config")
            console.print("[cyan]Current configuration:[/cyan]")
            console.print(json.dumps(cfg, indent=2))
        except Exception as e:
            console.print(f"[red]Failed to get config: {e}[/red]")
    elif value is None:
        # Get specific key (dot-notation)
        try:
            cfg = _get_json(f"{base}/global/config")
            parts = key.split(".")
            val = cfg
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    console.print(f"[yellow]Key '{key}' not found[/yellow]")
                    return
            console.print(f"[cyan]{key}[/cyan] = {json.dumps(val, indent=2)}")
        except Exception as e:
            console.print(f"[red]Failed to get config: {e}[/red]")
    else:
        # Set specific key (dot-notation)
        try:
            # Parse value as JSON if possible, else use as string
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
            
            # Build nested dict from dot-notation key
            parts = key.split(".")
            update: dict = {}
            current = update
            for i, part in enumerate(parts[:-1]):
                current[part] = {}
                current = current[part]
            current[parts[-1]] = parsed_value
            
            # PUT the update
            import requests
            resp = requests.put(f"{base}/global/config", json=update, timeout=10)
            resp.raise_for_status()
            console.print(f"[green]Set {key} = {value}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to set config: {e}[/red]")


@app.command()
def coverage(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show file tree coverage visualization."""
    from prep.viz.coverage import render_file_coverage
    
    # In a real app, we would fetch the file tree from the server
    # e.g. _get_json(f"{base}/files/tree")
    # For now, we will show the demo data structure
    
    base = _base_url(host, port)
    demo_tree_data = {
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
                    {"name": "schema.py", "type": "file", "status": "indexed"},
                ],
            },
            {
                "name": "core",
                "type": "dir",
                "coverage": 0.8,
                "children": [
                    {"name": "index.py", "type": "file", "status": "indexed"},
                    {"name": "search.py", "type": "file", "status": "indexed"},
                    {"name": "experimental.py", "type": "file", "status": "excluded"},
                ],
            },
            {
                "name": "utils",
                "type": "dir",
                "coverage": 0.5,
                "children": [
                    {"name": "helpers.py", "type": "file", "status": "indexed"},
                    {"name": "legacy.py", "type": "file", "status": "excluded"},
                ],
            },
            {
                "name": "tests",
                "type": "dir",
                "coverage": 0.0,
                "children": [
                    {"name": "test_api.py", "type": "file", "status": "excluded"},
                    {"name": "test_core.py", "type": "file", "status": "excluded"},
                ],
            },
        ],
    }
    try:
        if not _is_server_available(base):
            raise requests.exceptions.ConnectionError()
        pid = _resolve_project(base, project_id)
        # Try to fetch real data from server (endpoint not yet implemented)
        url = f"{base}/projects/{pid}/coverage"
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            raise ValueError("Coverage API not available")
        r.raise_for_status()
        data = _unwrap_envelope(r.json())
        tree_data = data.get("tree") if isinstance(data, dict) else None
        if not isinstance(tree_data, dict):
            tree_data = data if isinstance(data, dict) else None
        if not isinstance(tree_data, dict):
            raise ValueError("Invalid coverage response")
        render_file_coverage(tree_data, console=console)
    except typer.Exit:
        raise
    except requests.exceptions.ConnectionError:
        console.print("[yellow]Server not connected. Showing demo data.[/yellow]\n")
        render_file_coverage(demo_tree_data, console=console)
    except ValueError as e:
        console.print(f"[yellow]Coverage API not available ({e}). Showing demo data.[/yellow]\n")
        render_file_coverage(demo_tree_data, console=console)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def overview(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    weeks: int = typer.Option(12, "--weeks", "-w", help="Number of weeks for activity"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show comprehensive dashboard overview."""
    from prep.viz.overview import render_dashboard
    from prep.viz.activity_heatmap import generate_sample_data, ActivityDay, ActivityHeatmapData
    
    base = _base_url(host, port)
    
    # Initialize with empty/default data
    health_stats = {}
    activity_data = generate_sample_data(weeks)
    trace_stats = {}
    
    try:
        if not _is_server_available(base):
            raise requests.exceptions.ConnectionError()
        pid = _resolve_project(base, project_id)
        
        # 1. Fetch Status (Health) from project-scoped endpoint
        status_data = _get_json(f"{base}/projects/{pid}/status")
        index = status_data.get("index", {})
        trace = status_data.get("trace", {})
        total_chunks = index.get("total_chunks", 0)
        trace_counts = trace.get("counts", {}) if isinstance(trace, dict) else {}
        health_stats = {
            "total_files": total_chunks,
            "indexed_files": total_chunks,
            "embeddings_count": total_chunks,
            "trace_nodes": trace_counts.get("nodes", 0),
            "trace_edges": trace_counts.get("edges", 0),
            "last_build": index.get("last_build_at", "Never"),
            "disk_usage_mb": 0.0,
        }
        
        # 2. Fetch Activity
        try:
            url = f"{base}/projects/{pid}/activity?weeks={weeks}"
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                raise ValueError("Activity API not available")
            r.raise_for_status()
            act_data = _unwrap_envelope(r.json())
            days = [
                ActivityDay(
                    date=d["date"],
                    embeddings=d.get("embeddings", 0),
                    trace=d.get("trace", 0),
                    builds=d.get("builds", 0),
                )
                for d in act_data.get("days", [])
            ]
            activity_data = ActivityHeatmapData(
                days=days,
                totals=act_data.get("totals", {"embeddings": 0, "trace": 0, "builds": 0}),
            )
        except:
            pass # Fallback to sample if endpoint missing
            
        # 3. Fetch Trace Stats (from project status, which includes trace info)
        try:
            tr_data = status_data.get("trace", {})
            trace_stats = {
                "node_count": tr_data.get("counts", {}).get("nodes", 0),
                "edge_count": tr_data.get("counts", {}).get("edges", 0),
                "avg_degree": (
                    (2.0 * float(tr_data.get("counts", {}).get("edges", 0)))
                    / float(tr_data.get("counts", {}).get("nodes", 0))
                )
                if float(tr_data.get("counts", {}).get("nodes", 0) or 0) > 0
                else 0.0,
            }
        except:
            pass # Fallback to empty if endpoint missing

        render_dashboard(health_stats, activity_data, trace_stats, weeks=weeks, console=console)
        
    except typer.Exit:
        raise
    except requests.exceptions.ConnectionError:
        console.print("[yellow]Server not connected. Showing demo dashboard.[/yellow]\n")
        
        # Demo Data
        demo_health = {
            "total_files": 1240, "indexed_files": 1100,
            "embeddings_count": 4500, "trace_nodes": 850,
            "trace_edges": 2300, "last_build": "2023-10-27 14:30", "disk_usage_mb": 45.2
        }
        demo_activity = generate_sample_data(weeks)
        demo_trace = {
            "node_count": 850, "edge_count": 2341, "avg_degree": 5.5
        }
        
        render_dashboard(demo_health, demo_activity, demo_trace, weeks=weeks, console=console)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def drift(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show index drift report (stale files, freshness metrics)."""
    from prep.viz.drift import render_drift_report
    
    base = _base_url(host, port)
    
    # Demo data for now - real implementation would fetch from /projects/{id}/coverage
    demo_drift = {
        "total_files": 150,
        "stale_files": 12,
        "stale_pct": 8.0,
        "freshness_score": 92.0,
        "last_scan": "2026-02-10 01:30:00",
    }
    demo_rotting = [
        {"path": "src/legacy/old_api.py", "days_stale": 45, "size": 2400},
        {"path": "docs/outdated.md", "days_stale": 30, "size": 1200},
    ]
    
    try:
        if not _is_server_available(base):
            raise requests.exceptions.ConnectionError()
        pid = _resolve_project(base, project_id)
        
        # Try to fetch real coverage data
        url = f"{base}/projects/{pid}/coverage"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = _unwrap_envelope(r.json())
            summary = data.get("summary", {})
            demo_drift = {
                "total_files": summary.get("total_files", 0),
                "stale_files": summary.get("pending_files", 0),
                "stale_pct": (summary.get("pending_files", 0) / max(summary.get("total_files", 1), 1)) * 100,
                "freshness_score": summary.get("coverage_pct", 0),
                "last_scan": "now",
            }
            demo_rotting = []
        render_drift_report(demo_drift, demo_rotting, console=console)
    except typer.Exit:
        raise
    except requests.exceptions.ConnectionError:
        console.print("[yellow]Server not connected. Showing demo drift report.[/yellow]\n")
        render_drift_report(demo_drift, demo_rotting, console=console)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def flow(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show RAG flow visualization (query → retrieval → context)."""
    from prep.viz.flow import render_rag_flow
    
    base = _base_url(host, port)
    
    # Demo data showing a typical RAG flow
    demo_flow = {
        "query": "How does authentication work?",
        "embedding_time_ms": 45,
        "search_time_ms": 12,
        "chunks_retrieved": 5,
        "chunks_used": 3,
        "context_chars": 4500,
        "estimated_tokens": 1125,
        "trace_expanded": True,
        "trace_nodes_added": 2,
    }
    
    try:
        if not _is_server_available(base):
            raise requests.exceptions.ConnectionError()
        # For now just show demo - real implementation would need a recent query
        render_rag_flow(demo_flow, console=console)
    except typer.Exit:
        raise
    except requests.exceptions.ConnectionError:
        console.print("[yellow]Server not connected. Showing demo RAG flow.[/yellow]\n")
        render_rag_flow(demo_flow, console=console)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command("sync-headless")
def sync_headless(
    repo_url: str = typer.Option("", "--repo-url", help="HTTPS or SSH URL of the repository to clone"),
    repo_path: str = typer.Option("", "--repo-path", help="Path to a pre-cloned repository (e.g., from GitHub Actions checkout)"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to index"),
    model_provider: str = typer.Option("local", "--model-provider", help="LLM provider: local | openai | anthropic | google"),
    model_name: str = typer.Option("qwen3:4b", "--model-name", help="Model name for the enrichment pipeline"),
    api_key: str = typer.Option("", "--api-key", help="API key for cloud LLM provider (or use env vars)"),
    embedder: str = typer.Option("native", "--embedder", help="Embedding engine: native (ONNX, CPU) | ollama"),
    full: bool = typer.Option(False, "--full", help="Force a full rebuild (skip incremental diffing)"),
    s3_endpoint: str = typer.Option("", "--s3-endpoint", help="S3-compatible endpoint URL (or PREP_S3_ENDPOINT env)"),
    s3_bucket: str = typer.Option("", "--s3-bucket", help="S3 bucket name (or PREP_S3_BUCKET env)"),
    s3_prefix: str = typer.Option("", "--s3-prefix", help="S3 key prefix for this project (or PREP_S3_PREFIX env)"),
    s3_access_key: str = typer.Option("", "--s3-access-key", help="S3 access key (or PREP_S3_ACCESS_KEY env)"),
    s3_secret_key: str = typer.Option("", "--s3-secret-key", help="S3 secret key (or PREP_S3_SECRET_KEY env)"),
) -> None:
    """
    Run the headless indexing pipeline for team sync.

    Clones (or uses) a repository, runs the 11-stage enrichment pipeline,
    and uploads the resulting index artifacts to an S3-compatible bucket.

    \b
    Quick Start (CPU + BYOK):
      prep sync-headless --repo-path . --model-provider openai --model-name gpt-4.1-mini

    \b
    GPU + Local LLM:
      prep sync-headless --repo-url https://github.com/org/repo --model-provider local --model-name qwen3:4b

    S3 credentials can be passed via flags or environment variables
    (PREP_S3_ENDPOINT, PREP_S3_BUCKET, PREP_S3_ACCESS_KEY, PREP_S3_SECRET_KEY).
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    from prep.core.feature_gate import check_feature, get_license, License
    from prep.services.s3_storage import S3Config
    from prep.services.headless_runner import HeadlessRunner, HeadlessConfig

    # Team Sync requires Team or Enterprise tier
    if not check_feature("team_config"):
        lic = get_license()
        console.print(
            f"[red]Error: sync-headless requires a Team or Enterprise license "
            f"(current: {License._display_tier(lic.tier)}). "
            f"Upgrade at https://prep.io/pricing[/red]"
        )
        raise typer.Exit(1)

    if not repo_url and not repo_path:
        console.print("[red]Error: Either --repo-url or --repo-path is required.[/red]")
        raise typer.Exit(1)

    # EA-B4: Deprecation warnings for CLI secret flags
    if s3_access_key or s3_secret_key:
        console.print(
            "[yellow]⚠ Deprecation warning: Passing S3 credentials via CLI flags is deprecated "
            "and will be removed in a future version. Use environment variables instead: "
            "PREP_S3_ACCESS_KEY, PREP_S3_SECRET_KEY[/yellow]"
        )
    if api_key:
        console.print(
            "[yellow]⚠ Deprecation warning: Passing --api-key via CLI flag is deprecated. "
            "Use environment variables instead: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY[/yellow]"
        )

    # Build S3 config from flags + env vars (flags take priority)
    s3_cfg = S3Config.from_env()
    if s3_endpoint:
        s3_cfg.endpoint = s3_endpoint
    if s3_bucket:
        s3_cfg.bucket = s3_bucket
    if s3_prefix:
        s3_cfg.prefix = s3_prefix
    if s3_access_key:
        s3_cfg.access_key = s3_access_key
    if s3_secret_key:
        s3_cfg.secret_key = s3_secret_key

    # Validate S3 config if any S3 fields are set
    has_s3 = bool(s3_cfg.bucket)
    if has_s3:
        errors = s3_cfg.validate()
        if errors:
            for e in errors:
                console.print(f"[red]S3 config error: {e}[/red]")
            raise typer.Exit(1)

    # Resolve API key from flag or env
    resolved_api_key = api_key
    if not resolved_api_key:
        if model_provider == "openai":
            resolved_api_key = os.environ.get("OPENAI_API_KEY", "")
        elif model_provider == "anthropic":
            resolved_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        elif model_provider == "google":
            resolved_api_key = os.environ.get("GOOGLE_API_KEY", "")

    config = HeadlessConfig(
        repo_url=repo_url,
        repo_path=repo_path,
        branch=branch,
        model_provider=model_provider,
        model_name=model_name,
        api_key=resolved_api_key,
        embedder=embedder,
        full_rebuild=full,
        s3=s3_cfg if has_s3 else None,
    )

    console.print(f"[cyan]Prep Headless Sync[/cyan]")
    console.print(f"  Repo: {repo_url or repo_path}")
    console.print(f"  Branch: {branch}")
    console.print(f"  Model: {model_provider}/{model_name}")
    console.print(f"  Embedder: {embedder}")
    console.print(f"  S3: {'s3://' + s3_cfg.bucket + '/' + s3_cfg.prefix if has_s3 else 'disabled (local only)'}")
    console.print(f"  Mode: {'full rebuild' if full else 'incremental'}")
    console.print()

    try:
        runner = HeadlessRunner(config)
        manifest = runner.run()
        console.print(f"[green]Sync complete.[/green]")
        if manifest.commit_sha:
            console.print(f"  Commit: {manifest.commit_sha[:12]}")
        if manifest.artifact_count:
            console.print(f"  Artifacts: {manifest.artifact_count}")

        # Print stage summary
        for sr in runner.stage_results:
            icon = "[green]✓[/green]" if sr.success else "[red]✗[/red]"
            console.print(f"  {icon} {sr.stage} ({sr.duration_seconds:.1f}s)")
    except Exception as e:
        console.print(f"[red]Headless sync failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def opportunities(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID (optional if inside project dir)"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Run a fresh scan before displaying"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, sarif, csv, md, ai_prompt"),
    priority: Optional[str] = typer.Option(None, "--priority", help="Min priority filter: P0, P1, P2, P3"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by source"),
    include_dismissed: bool = typer.Option(False, "--dismissed", help="Include dismissed items"),
    limit: int = typer.Option(50, "--limit", "-k", help="Max items to show"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """
    Show codebase improvement opportunities.

    Prep discovers actionable opportunities across your codebase:
    architecture issues, tech debt, naming inconsistencies, and more.

    \b
    Quick Start:
      prep opportunities                         # Show existing findings
      prep opportunities --refresh               # Fresh scan + display
      prep opportunities --format sarif > out.sarif  # SARIF export
      prep opportunities --format ai_prompt      # Paste into AI agent
      prep opportunities --priority P0           # Critical only
    """
    base = _base_url(host, port)

    # If format is a direct export, use the export endpoint
    if format in ("json", "sarif", "csv", "md", "ai_prompt"):
        pid = _resolve_project(base, project_id)
        if refresh:
            console.print("[cyan]Running fresh scan...[/cyan]", highlight=False)
            _post_json(f"{base}/projects/{pid}/opportunities/refresh", {})

        # Build query params
        params = [f"format={format}"]
        if priority:
            params.append(f"min_priority={priority}")
        if category:
            params.append(f"category={category}")
        if source:
            params.append(f"source={source}")
        qs = "&".join(params)

        try:
            r = requests.get(f"{base}/projects/{pid}/opportunities/export?{qs}", timeout=60)
            r.raise_for_status()
            print(r.text)
        except requests.exceptions.HTTPError as e:
            console.print(f"[red]Export error: {e}[/red]")
            raise typer.Exit(1)
        except requests.exceptions.ConnectionError:
            console.print(f"[red]Cannot connect to Prep daemon at {base}[/red]")
            raise typer.Exit(1)
        return

    # Table format: rich table display
    pid = _resolve_project(base, project_id)

    if refresh:
        console.print("[cyan]Running fresh scan...[/cyan]", highlight=False)
        data = _post_json(f"{base}/projects/{pid}/opportunities/refresh", {})
        items = data.get("items", [])
        summary = data.get("summary", {})
    else:
        # Build query params
        params_list = [f"limit={limit}"]
        if priority:
            params_list.append(f"min_priority={priority}")
        if category:
            params_list.append(f"category={category}")
        if source:
            params_list.append(f"source={source}")
        if include_dismissed:
            params_list.append("include_dismissed=true")
        qs = "&".join(params_list)

        data = _get_json(f"{base}/projects/{pid}/opportunities?{qs}")
        items = data.get("items", [])

        # Also get summary
        summary = _get_json(f"{base}/projects/{pid}/opportunities/summary")

    if not items:
        console.print("[yellow]No opportunities found.[/yellow]")
        if not refresh:
            console.print("[dim]Run 'prep opportunities --refresh' to scan for new findings.[/dim]")
        return

    # Summary panel
    total = summary.get("total", len(items))
    critical = summary.get("critical", 0)
    warning = summary.get("warning", 0)
    info = summary.get("info", 0)
    dismissed = summary.get("dismissed", 0)
    last_refresh = summary.get("last_refresh", "never")

    console.print(Panel(
        f"[bold]{total}[/bold] opportunities | "
        f"[red]{critical}[/red] critical | "
        f"[yellow]{warning}[/yellow] warnings | "
        f"[blue]{info}[/blue] info | "
        f"[dim]{dismissed} dismissed[/dim]\n"
        f"[dim]Last refresh: {last_refresh}[/dim]",
        title="Prep Opportunities",
        expand=False,
    ))

    # Items table
    table = Table()
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("P", style="bold", width=3)
    table.add_column("Title", style="green")
    table.add_column("Cat")
    table.add_column("Effort")
    table.add_column("Files", justify="right")

    prio_styles = {"P0": "[red]P0[/red]", "P1": "[yellow]P1[/yellow]", "P2": "[blue]P2[/blue]", "P3": "[dim]P3[/dim]"}

    for item in items[:limit]:
        file_count = len(item.get("affected_files", []))
        table.add_row(
            item.get("id", "?"),
            prio_styles.get(item.get("priority", "P2"), item.get("priority", "?")),
            item.get("title", "")[:60],
            item.get("category", ""),
            item.get("effort", ""),
            str(file_count) if file_count else "-",
        )

    console.print(table)
    console.print()
    console.print("[dim]Export: prep opportunities --format sarif | json | csv | md | ai_prompt[/dim]")


# ── Agent Commands (Phase 67) ──────────────────────────────────────

@app.command("hr-readiness")
def hr_readiness(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Check codebase readiness for HR role generation."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    data = _get_json(f"{base}/projects/{pid}/agents/hr/readiness")
    score = data.get("score", 0)
    color = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
    console.print(f"Readiness score: [{color}]{score:.2f}[/{color}]")
    console.print(f"  List mode: {'Ready' if data.get('ready_for_list') else 'Not ready'}")
    console.print(f"  Auto mode: {'Ready' if data.get('ready_for_auto') else 'Not ready'}")
    missing = data.get("missing", [])
    if missing:
        console.print("\n[yellow]Missing:[/yellow]")
        for m in missing:
            console.print(f"  - {m}")


@app.command("hr-generate")
def hr_generate(
    role_names: Optional[List[str]] = typer.Argument(None, help="Role names (for list/hybrid mode)"),
    mode: str = typer.Option("list", "--mode", "-m", help="Generation mode: list, auto, hybrid"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be generated without writing files"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Generate AI agent role definitions.

    \b
    Examples:
      prep hr-generate "Backend Dev" "API Engineer" --mode list
      prep hr-generate --mode auto
      prep hr-generate "CTO" --mode hybrid
      prep hr-generate --mode auto --dry-run
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    payload = {"mode": mode, "role_names": role_names or [], "dry_run": dry_run}

    if dry_run:
        console.print(f"[cyan]Dry run — previewing {mode} mode...[/cyan]")
        data = _post_json(f"{base}/projects/{pid}/agents/hr/generate", payload)
        readiness = data.get("readiness", {})
        console.print(f"\nReadiness: {readiness.get('score', 0):.2f}")
        proposed = data.get("proposed_roles", [])
        console.print(f"\n[bold]Proposed roles ({len(proposed)}):[/bold]")
        for r in proposed:
            console.print(f"  - {r.get('display_name', '?')} ({r.get('slug', '?')})")
            if r.get("justification"):
                console.print(f"    {r['justification'][:120]}")
        sizes = data.get("estimated_knowledge_sizes", {})
        if sizes:
            console.print("\n[bold]Estimated KNOWLEDGE.md sizes:[/bold]")
            for slug, size in sizes.items():
                console.print(f"  - {slug}: {size:,} chars")
        drift = data.get("drift")
        if drift:
            console.print("\n[bold]Drift vs existing roster:[/bold]")
            for rf in drift.get("role_fitness", []):
                score = rf["fitness_score"]
                color = "green" if score > 0.8 else "yellow" if score > 0.6 else "red"
                console.print(f"  - {rf['slug']}: [{color}]{score:.2f}[/{color}] ({rf['recommendation']})")
            overlaps = drift.get("overlap_warnings", [])
            for w in overlaps:
                console.print(f"  [yellow]⚠ {w}[/yellow]")
        return

    console.print(f"[cyan]Generating roles ({mode} mode)...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/hr/generate", payload)
    count = data.get("roles_generated", 0)
    slugs = data.get("slugs", [])
    agents_dir = data.get("agents_dir", "")
    file_paths = data.get("files", {})
    console.print(f"[green]Generated {count} role(s):[/green]")
    for s in slugs:
        console.print(f"  [bold]{s}[/bold]")
        for fp in file_paths.get(s, []):
            console.print(f"    → {fp}")
    if agents_dir:
        console.print(f"\n[dim]Files written to: {agents_dir}[/dim]")
        console.print("[dim]Edit any file manually — changes will be preserved on re-generation.[/dim]")


@app.command("hr-roster")
def hr_roster(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """List all generated agent roles."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    data = _get_json(f"{base}/projects/{pid}/agents/hr/roster")
    roles = data.get("roles", [])
    if not roles:
        console.print("[dim]No roles generated yet. Run: prep hr-generate[/dim]")
        return
    table = Table(title="Agent Roster")
    table.add_column("Slug")
    table.add_column("Display Name")
    table.add_column("AGENTS.md")
    table.add_column("SOUL.md")
    table.add_column("KNOWLEDGE.md")
    for r in roles:
        table.add_row(
            r["slug"], r["display_name"],
            "yes" if r.get("has_agents_md") else "-",
            "yes" if r.get("has_soul_md") else "-",
            "yes" if r.get("has_knowledge_md") else "-",
        )
    console.print(table)


@app.command("hr-audit")
def hr_audit(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Run drift detection on the current agent roster."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    data = _post_json(f"{base}/projects/{pid}/agents/hr/audit", {})
    fitness = data.get("role_fitness", [])
    if not fitness:
        console.print("[dim]No roles to audit.[/dim]")
        return
    table = Table(title="Role Drift Report")
    table.add_column("Slug")
    table.add_column("Fitness")
    table.add_column("Status")
    for rf in fitness:
        score = rf["fitness_score"]
        color = "green" if score > 0.8 else "yellow" if score > 0.6 else "red"
        table.add_row(rf["slug"], f"[{color}]{score:.2f}[/{color}]", rf["recommendation"])
    console.print(table)
    gaps = data.get("coverage_gaps", [])
    if gaps:
        console.print(f"\n[yellow]Coverage gaps:[/yellow] {', '.join(gaps)}")
    overlaps = data.get("overlap_warnings", [])
    for w in overlaps:
        console.print(f"[yellow]⚠ {w}[/yellow]")


@app.command("hr-sync")
def hr_sync(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Sync generated roles to Paperclip as managed agents."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    console.print("[cyan]Syncing roster to Paperclip...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/hr/sync", {})
    synced = data.get("synced", {})
    if not synced:
        console.print("[dim]No roles to sync. Generate roles first: prep hr-generate[/dim]")
        return
    console.print(f"[green]Synced {len(synced)} role(s) to Paperclip:[/green]")
    for slug, agent_id in synced.items():
        console.print(f"  - {slug} -> {agent_id}")


@app.command("hr-adopt")
def hr_adopt(
    agents_dir: str = typer.Argument(".agents", help="Path to directory containing agent subdirectories"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Import existing agent files and enrich with Prep intelligence.

    \b
    Reads AGENTS.md from each subdirectory of the given path, then generates
    role-filtered KNOWLEDGE.md and SOUL.md (if missing) for each role.

    \b
    Examples:
      prep hr-adopt .agents
      prep hr-adopt /path/to/agents --project my-project
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    console.print(f"[cyan]Adopting agents from {agents_dir}...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/hr/adopt", {"agents_dir": agents_dir})
    count = data.get("adopted_count", 0)
    adopted = data.get("adopted", [])
    if not adopted:
        console.print("[dim]No agents found to adopt.[/dim]")
        return
    console.print(f"[green]Adopted {count} role(s):[/green]")
    for r in adopted:
        console.print(f"  - {r.get('slug', '?')} ({r.get('display_name', '?')})")


@app.command("research-run")
def research_run(
    max_topics: int = typer.Option(3, "--max-topics", "-n", help="Max topics to research"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Run the researcher agent: select topics, research, formulate plans."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    console.print(f"[cyan]Running researcher (max {max_topics} topics)...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/researcher/run", {"max_topics": max_topics})
    plans = data.get("plans", [])
    console.print(f"[green]Produced {len(plans)} research plan(s):[/green]")
    for p in plans:
        console.print(f"  - [{p.get('effort', '?')}] {p.get('title', 'Untitled')}")
        if p.get("fix_steps"):
            for i, step in enumerate(p["fix_steps"][:3], 1):
                console.print(f"      {i}. {step}")


@app.command("research-history")
def research_history(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show research run history."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    data = _get_json(f"{base}/projects/{pid}/agents/researcher/history")
    runs = data.get("runs", [])
    if not runs:
        console.print("[dim]No research runs yet. Run: prep research-run[/dim]")
        return
    table = Table(title="Research History")
    table.add_column("Run ID")
    table.add_column("Timestamp")
    table.add_column("Topics")
    table.add_column("Plans")
    for r in runs:
        table.add_row(r["run_id"], r["timestamp"][:19], str(r["topic_count"]), str(r["plan_count"]))
    console.print(table)


@app.command("custodian-run")
def custodian_run(
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Preview mode (default) or live mode"),
    max_files: int = typer.Option(20, "--max-files", "-n", help="Max files per cleanup"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Run the custodian agent: detect dead code, plan cleanup.

    Dry-run by default — shows what would be cleaned without modifying git.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    mode = "dry-run" if dry_run else "LIVE"
    console.print(f"[cyan]Running custodian ({mode}, max {max_files} files)...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/custodian/run", {
        "dry_run": dry_run, "max_files": max_files,
    })
    candidates = data.get("candidates", [])
    console.print(f"[green]{len(candidates)} file(s) identified for cleanup:[/green]")
    for c in candidates:
        console.print(f"  - {c.get('file_path', '?')} [{c.get('classification', '?')}]")
    if dry_run and candidates:
        console.print("\n[dim]This was a dry run. Use --live to execute.[/dim]")


@app.command("custodian-manifest")
def custodian_manifest(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Show the custodian archive manifest."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    data = _get_json(f"{base}/projects/{pid}/agents/custodian/manifest")
    entries = data.get("entries", [])
    if not entries:
        console.print("[dim]No archived items yet.[/dim]")
        return
    table = Table(title="Archive Manifest")
    table.add_column("ID")
    table.add_column("Files")
    table.add_column("Reason")
    table.add_column("Archived At")
    for e in entries:
        table.add_row(
            e["entry_id"],
            str(len(e.get("original_paths", []))),
            e.get("reason", "")[:50],
            e.get("archived_at", "")[:19],
        )
    console.print(table)


@app.command("agents")
def agents_overview(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Agent Operations — status overview and command reference.

    \b
    Shows the current state of all three Prep agents and lists
    available commands for each.
    """
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)

    # Fetch status
    data = _get_json(f"{base}/projects/{pid}/agents/status")
    hr = data.get("hr", {})
    res = data.get("researcher", {})
    cust = data.get("custodian", {})
    latest = res.get("latest_run", "")

    # Status section
    console.print()
    console.print("[bold]Agent Operations[/bold]")
    console.print()

    status_table = Table(show_header=False, box=None, padding=(0, 2))
    status_table.add_column("Agent", style="bold")
    status_table.add_column("Status")
    status_table.add_column("Metric")

    hr_count = hr.get("role_count", 0)
    hr_status = "[green]Active[/green]" if hr_count > 0 else "[dim]No roles[/dim]"
    status_table.add_row("HR Agent", hr_status, f"{hr_count} roles")

    res_count = res.get("run_count", 0)
    res_status = "[green]Active[/green]" if res_count > 0 else "[dim]No runs[/dim]"
    res_metric = f"{res_count} runs"
    if latest:
        res_metric += f" (latest: {latest[:10]})"
    status_table.add_row("Researcher", res_status, res_metric)

    cust_count = cust.get("archive_count", 0)
    cust_status = "[green]Active[/green]" if cust_count > 0 else "[dim]No scans[/dim]"
    status_table.add_row("Custodian", cust_status, f"{cust_count} archived")

    console.print(status_table)

    # Commands section
    console.print()
    console.print("[bold]Commands[/bold]")
    console.print()

    cmd_table = Table(show_header=False, box=None, padding=(0, 2))
    cmd_table.add_column("Command", style="cyan")
    cmd_table.add_column("Description", style="dim")

    cmd_table.add_row("prep hr-readiness", "Check codebase readiness for role generation")
    cmd_table.add_row('prep hr-generate "Role Name"', "Generate role definitions (list mode)")
    cmd_table.add_row("prep hr-generate --mode auto", "Auto-infer roles from codebase")
    cmd_table.add_row("prep hr-roster", "List generated roles")
    cmd_table.add_row("prep hr-audit", "Run drift detection on roles")
    cmd_table.add_row("prep hr-generate --dry-run", "Preview what generation would produce")
    cmd_table.add_row("prep hr-adopt .agents", "Import existing agents and enrich with Prep")
    cmd_table.add_row("prep hr-sync", "Sync roles to Paperclip")
    cmd_table.add_row("", "")
    cmd_table.add_row("prep research-run", "Mine audit findings, formulate plans")
    cmd_table.add_row("prep research-history", "Show research run history")
    cmd_table.add_row("", "")
    cmd_table.add_row("prep custodian-run", "Scan for dead code (dry-run default)")
    cmd_table.add_row("prep custodian-run --live", "Execute cleanup (creates branch)")
    cmd_table.add_row("prep custodian-manifest", "Show archive manifest")

    console.print(cmd_table)

    # Quick start hint if nothing is set up
    if hr_count == 0 and res_count == 0 and cust_count == 0:
        console.print()
        console.print("[yellow]Get started:[/yellow]")
        console.print("  1. Ensure an LLM is configured: [cyan]prep config[/cyan]")
        console.print("  2. Check readiness: [cyan]prep hr-readiness[/cyan]")
        console.print("  3. Generate roles: [cyan]prep hr-generate --mode auto[/cyan]")


@app.command("agents-discover")
def agents_discover(
    url: Optional[str] = typer.Option(None, "--url", help="Paperclip URL to probe (overrides config)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Discover Paperclip connection status.

    Probes for a running Paperclip instance and reports connection details.
    """
    base = _base_url(host, port)
    if url:
        data = _post_json(f"{base}/agents/discovery/probe", {"url": url})
    else:
        data = _get_json(f"{base}/agents/discovery")

    connected = data.get("connected", False)
    configured = data.get("configured", False)

    if not configured:
        console.print("[dim]Paperclip is not configured. Enable pm_push in Settings.[/dim]")
        return

    if connected:
        console.print(f"[green]✓ Paperclip connected[/green] at {data.get('url', '?')}")
        if data.get("company_name"):
            console.print(f"  Company: {data['company_name']}")
        if data.get("agent_count"):
            console.print(f"  Agents: {data['agent_count']}")
        if data.get("plugin_detected"):
            console.print("  [green]Prep plugin detected ✓[/green]")
        else:
            console.print("  [yellow]Prep plugin not detected[/yellow]")
        if data.get("version"):
            console.print(f"  Version: {data['version']}")
    else:
        reason = data.get("reason", "Unknown")
        console.print(f"[red]✗ Paperclip not reachable[/red]")
        console.print(f"  {reason}")


@app.command("research-push")
def research_push(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Push latest research plans to Paperclip."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    console.print("[cyan]Pushing research plans to Paperclip...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/researcher/push", {})
    if data.get("pushed"):
        console.print(f"[green]Pushed {data.get('issues_pushed', 0)} issue(s) to Paperclip[/green]")
        for iss in data.get("issues", []):
            console.print(f"  - {iss.get('title', '?')} → {iss.get('id', '?')}")
    else:
        console.print(f"[dim]{data.get('reason', 'Nothing to push')}[/dim]")


@app.command("custodian-push")
def custodian_push(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8400, "--port", help="Server port"),
) -> None:
    """Push cleanup plan to Paperclip."""
    base = _base_url(host, port)
    pid = _resolve_project(base, project_id)
    console.print("[cyan]Pushing cleanup plan to Paperclip...[/cyan]")
    data = _post_json(f"{base}/projects/{pid}/agents/custodian/push", {})
    if data.get("pushed"):
        console.print(f"[green]Pushed {data.get('issues_pushed', 0)} cleanup item(s) to Paperclip[/green]")
        for iss in data.get("issues", []):
            console.print(f"  - {iss.get('title', '?')} → {iss.get('id', '?')}")
    else:
        console.print(f"[dim]{data.get('reason', 'Nothing to push')}[/dim]")

def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    app()
