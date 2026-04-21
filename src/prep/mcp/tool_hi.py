"""
Project overview and context discovery tool (hi_codrag).

Extracted from MCPServer to keep the main server module focused on
protocol handling. This tool aggregates project state from multiple
endpoints and returns a friendly markdown summary with health notes
and content-aware suggested prompts.

Phase 32: prep_hi — Selected Files as Primary Context.
Phase 50: Preserved as standalone module; routed via alias dispatch.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from prep.mcp.server import MCPServer


async def tool_hi(server: MCPServer, project_override: Optional[str] = None) -> Dict[str, Any]:
    """Project overview and context discovery tool.

    Aggregates project state from multiple endpoints and returns a
    friendly markdown summary with health notes and suggested prompts.
    """
    project_id = await server._resolve_project_id(override=project_override)

    # -- Parallel data fetch ------------------------------------------------
    status_coro = server._api_get(f"/projects/{project_id}/status")
    included_coro = server._api_get(f"/projects/{project_id}/included_paths")
    weights_coro = server._api_get(f"/projects/{project_id}/path_weights")
    coverage_coro = server._api_get(f"/projects/{project_id}/trace/coverage")
    projects_coro = server._api_get("/projects")
    project_coro = server._api_get(f"/projects/{project_id}")
    hub_coro = server._api_get(f"/projects/{project_id}/trace/hub_files?k=5")

    results = await asyncio.gather(
        status_coro, included_coro, weights_coro,
        coverage_coro, projects_coro, project_coro,
        hub_coro,
        return_exceptions=True,
    )

    status = results[0] if not isinstance(results[0], Exception) else {}
    included = results[1] if not isinstance(results[1], Exception) else {}
    weights = results[2] if not isinstance(results[2], Exception) else {}
    coverage = results[3] if not isinstance(results[3], Exception) else {}
    all_projects = results[4] if not isinstance(results[4], Exception) else {}
    project_data = results[5] if not isinstance(results[5], Exception) else {}
    hub_data = results[6] if not isinstance(results[6], Exception) else {}

    # Safely unwrap dicts
    if not isinstance(status, dict):
        status = {}
    if not isinstance(included, dict):
        included = {}
    if not isinstance(weights, dict):
        weights = {}
    if not isinstance(coverage, dict):
        coverage = {}
    if not isinstance(all_projects, dict):
        all_projects = {}
    if not isinstance(project_data, dict):
        project_data = {}
    if not isinstance(hub_data, dict):
        hub_data = {}

    # -- Extract data -------------------------------------------------------
    index = status.get("index", {}) or {}
    trace = status.get("trace", {}) or {}
    watch = status.get("watch", {}) or {}
    building = bool(status.get("building", False))
    stale = bool(status.get("stale", False))
    stale_count = int(status.get("stale_count", 0))

    index_exists = bool(index.get("exists", False))
    total_chunks = int(index.get("total_chunks") or 0)

    trace_enabled = bool(trace.get("enabled", False))
    total_nodes = int(trace.get("total_nodes") or coverage.get("total_nodes") or 0)
    total_edges = int(trace.get("total_edges") or coverage.get("total_edges") or 0)
    traced_count = int(coverage.get("traced_count", 0))
    untraced_count = int(coverage.get("untraced_count", 0))
    trace_total = traced_count + untraced_count
    trace_pct = round(100 * traced_count / trace_total) if trace_total > 0 else 0

    included_paths = included.get("included_paths", []) or []
    path_weights = weights.get("path_weights", {}) or {}

    watch_enabled = bool(watch.get("enabled", False))

    # O-2: Hub files (from trace graph)
    hub_files_raw = hub_data.get("hub_files", []) or []
    hub_files: List[Dict[str, Any]] = [
        h for h in hub_files_raw
        if isinstance(h, dict) and h.get("path") and h.get("in_degree", 0) > 0
    ][:5]

    # O-7: Change detection -- extract stale file paths from coverage
    stale_file_list = coverage.get("stale", []) or []
    stale_file_paths: List[str] = []
    if isinstance(stale_file_list, list):
        for sf in stale_file_list[:10]:
            if isinstance(sf, dict):
                sp = sf.get("path", "")
                if sp:
                    stale_file_paths.append(sp)
            elif isinstance(sf, str):
                stale_file_paths.append(sf)

    # Project name
    proj = project_data.get("project", project_data) if isinstance(project_data, dict) else {}
    if not isinstance(proj, dict):
        proj = {}
    project_name = proj.get("name") or project_id

    # Other projects
    proj_list = all_projects.get("projects", []) if isinstance(all_projects, dict) else []
    other_projects = [
        p.get("name") or p.get("id", "")
        for p in (proj_list if isinstance(proj_list, list) else [])
        if isinstance(p, dict) and str(p.get("id", "")) != project_id
    ]

    # -- O-3: Filename-based topic detection --------------------------------
    detected_topics = _detect_topics(included_paths)

    # -- Categorize selected files ------------------------------------------
    file_count = len(included_paths)
    _DOC_EXTS = {".md", ".txt", ".rst", ".adoc", ".mdx"}
    _CODE_EXTS = {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java",
        ".cpp", ".c", ".h", ".cs", ".rb", ".swift", ".kt", ".vue",
        ".svelte", ".php", ".scala", ".zig", ".lua", ".ex", ".exs",
    }
    _TEST_HINTS = {"test", "spec", "__tests__", "tests"}
    _CONFIG_EXTS = {
        ".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".cfg",
        ".lock", ".config",
    }
    _DOC_DIR_HINTS = {"docs", "documentation", "doc", "design", "designplan"}

    docs: List[str] = []
    code: List[str] = []
    tests: List[str] = []
    config: List[str] = []
    other_files: List[str] = []

    dir_counts: Dict[str, int] = {}
    all_dir_segments: set = set()  # all directory names at any level
    for p in included_paths:
        ps = str(p)
        parts = ps.split("/")
        top_dir = parts[0] if len(parts) > 1 else "(root)"
        dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1
        # Collect all directory segments (not just top-level)
        for seg in parts[:-1]:  # exclude filename
            all_dir_segments.add(seg.lower())

        # Categorize
        ext = ("." + ps.rsplit(".", 1)[-1]).lower() if "." in ps else ""
        low_parts = {seg.lower() for seg in parts}
        if low_parts & _TEST_HINTS:
            tests.append(ps)
        elif ext in _DOC_EXTS:
            docs.append(ps)
        elif ext in _CODE_EXTS:
            code.append(ps)
        elif ext in _CONFIG_EXTS:
            config.append(ps)
        elif low_parts & _DOC_DIR_HINTS:
            docs.append(ps)
        else:
            other_files.append(ps)

    top_dirs = sorted(dir_counts.items(), key=lambda x: -x[1])[:5]

    # -- Build file inventory (structured data for AI) ---------------------
    _MAX_LIST = 10  # max filenames per category in the inventory

    file_inventory: Dict[str, Any] = {}
    if docs:
        file_inventory["docs"] = {
            "count": len(docs),
            "files": [str(Path(d).name) for d in docs[:_MAX_LIST]],
            "paths": docs[:_MAX_LIST],
        }
    if code:
        file_inventory["code"] = {
            "count": len(code),
            "files": [str(Path(c).name) for c in code[:_MAX_LIST]],
            "paths": code[:_MAX_LIST],
        }
    if tests:
        file_inventory["tests"] = {
            "count": len(tests),
            "files": [str(Path(t).name) for t in tests[:_MAX_LIST]],
            "paths": tests[:_MAX_LIST],
        }
    if config:
        file_inventory["config"] = {
            "count": len(config),
            "files": [str(Path(c).name) for c in config[:_MAX_LIST]],
            "paths": config[:_MAX_LIST],
        }

    # -- Build conversational summary ---------------------------------------
    lines: List[str] = []

    # Lead with selected files -- this is the primary context
    if file_count > 0:
        dir_summary = ", ".join(f"**{d}/** ({n})" for d, n in top_dirs)
        lines.append(f"I'm looking at **{project_name}** -- {file_count} files selected across {dir_summary}.")
        lines.append("")

        # File inventory by category (what the AI can actually discuss)
        if docs:
            doc_names = ", ".join(f"`{Path(d).name}`" for d in docs[:8])
            lines.append(f"**Docs & design files ({len(docs)}):** {doc_names}" + (f" +{len(docs)-8} more" if len(docs) > 8 else ""))
        if code:
            code_names = ", ".join(f"`{Path(c).name}`" for c in code[:8])
            lines.append(f"**Code ({len(code)}):** {code_names}" + (f" +{len(code)-8} more" if len(code) > 8 else ""))
        if tests:
            test_names = ", ".join(f"`{Path(t).name}`" for t in tests[:6])
            lines.append(f"**Tests ({len(tests)}):** {test_names}" + (f" +{len(tests)-6} more" if len(tests) > 6 else ""))
        if config:
            cfg_names = ", ".join(f"`{Path(c).name}`" for c in config[:4])
            lines.append(f"**Config ({len(config)}):** {cfg_names}" + (f" +{len(config)-4} more" if len(config) > 4 else ""))

        # O-3: Topic detection -- surface detected topics naturally
        if detected_topics:
            topic_parts = [f"**{t['topic']}** ({', '.join(f'`{f}`' for f in t['files'][:3])})" for t in detected_topics[:3]]
            lines.append(f"\nIt looks like you're working on: {', '.join(topic_parts)}.")

        if total_chunks > 0:
            lines.append(f"\nIndex: {total_chunks} searchable chunks.")
    elif index_exists:
        lines.append(f"I'm looking at **{project_name}** -- {total_chunks} chunks indexed across the project (no specific files selected).")
    elif building:
        lines.append(f"I'm setting up **{project_name}** -- the index is building right now.")
    else:
        lines.append(f"I see **{project_name}** but there's no index yet. I'll need one before I can help with code questions.")

    # Trace as background capability (not the lead)
    if trace_enabled and total_nodes > 0:
        lines.append(f"Code graph active ({total_nodes} nodes, {total_edges} edges, {trace_pct}% coverage) -- I can trace imports, calls, and structural connections between these files.")

    # O-2: Hub files -- show the most connected files
    if hub_files:
        hub_parts = [f"`{Path(h['path']).name}` ({h['in_degree']} connections)" for h in hub_files[:5]]
        lines.append(f"Most connected files: {', '.join(hub_parts)}.")

    # O-7: Stale file names -- show which files changed
    if stale_file_paths:
        stale_names = [f"`{Path(sp).name}`" for sp in stale_file_paths[:5]]
        suffix = f" +{len(stale_file_paths)-5} more" if len(stale_file_paths) > 5 else ""
        lines.append(f"Changed since last build: {', '.join(stale_names)}{suffix}.")

    # Path weights
    if path_weights:
        pw_parts = [f"`{k}` = {v}x" for k, v in sorted(path_weights.items())]
        lines.append(f"Priority areas: {', '.join(pw_parts)}.")

    lines.append("")  # blank line before health/observations

    # Health observations
    observations: List[str] = []
    if not index_exists:
        observations.append("No index exists yet -- build from the Prep dashboard to get started.")
    elif building:
        observations.append("Index is currently building -- results will improve once it finishes.")
    elif stale:
        if watch_enabled:
            observations.append(f"{stale_count} file(s) changed since last build. Auto-rebuild is on, so it will catch up shortly.")
        else:
            observations.append(f"{stale_count} file(s) changed since last build. Rebuild from the dashboard to refresh.")

    if trace_enabled and trace_pct < 60 and trace_total > 0:
        observations.append(f"Trace coverage is only {trace_pct}% ({traced_count}/{trace_total} files). Some structural connections may be missing.")

    if not watch_enabled and index_exists and not stale:
        observations.append("Auto-rebuild is off -- if you change files, I won't pick up the changes until you rebuild.")

    if observations:
        lines.append("**Heads up:**")
        for obs in observations:
            lines.append(f"- {obs}")
        lines.append("")
    else:
        lines.append("Everything looks good -- index is fresh and ready.\n")

    # -- O-8: Cross-file relationships (for small selections) --------------
    file_edges: List[Dict[str, str]] = []
    if trace_enabled and 2 <= len(included_paths) <= 30:
        try:
            path_param = "&paths=".join(str(p) for p in included_paths[:20])
            edges_data = await server._api_get(
                f"/projects/{project_id}/trace/file_edges?paths={path_param}"
            )
            if isinstance(edges_data, dict):
                file_edges = edges_data.get("edges", []) or []
        except Exception:
            pass

    if file_edges:
        rel_parts: List[str] = []
        for e in file_edges[:8]:
            src_name = Path(str(e.get("source", ""))).name
            tgt_name = Path(str(e.get("target", ""))).name
            kind = e.get("kind", "imports")
            rel_parts.append(f"`{src_name}` {kind} `{tgt_name}`")
        lines.append(f"File connections: {', '.join(rel_parts)}.")
        lines.append("")

    # -- O-1: Doc content previews -----------------------------------------
    doc_previews: List[Dict[str, str]] = []
    if docs:
        preview_paths = [d for d in docs[:5] if d.endswith((".md", ".mdx", ".txt", ".rst"))]
        preview_coros = [
            server._api_get(f"/projects/{project_id}/file?path={p}")
            for p in preview_paths
        ]
        if preview_coros:
            preview_results = await asyncio.gather(*preview_coros, return_exceptions=True)
            for p, pr in zip(preview_paths, preview_results):
                if isinstance(pr, Exception) or not isinstance(pr, dict):
                    continue
                content = pr.get("content", "") or ""
                if not content:
                    continue
                heading = ""
                paragraph = ""
                for line in content.split("\n"):
                    stripped = line.strip()
                    if not heading and stripped.startswith("#"):
                        heading = stripped.lstrip("# ").strip()
                    elif heading and not paragraph and stripped and not stripped.startswith("#"):
                        paragraph = stripped[:200]
                        break
                if heading:
                    doc_previews.append({
                        "path": p,
                        "file": str(Path(p).name),
                        "heading": heading,
                        "preview": paragraph,
                    })

    # -- Content-aware prompts (based on what's actually selected) ----------
    prompts: List[str] = _build_prompts(
        index_exists=index_exists,
        docs=docs,
        code=code,
        tests=tests,
        all_dir_segments=all_dir_segments,
        project_name=project_name,
        trace_enabled=trace_enabled,
        total_nodes=total_nodes,
        stale=stale,
        stale_file_paths=stale_file_paths,
        detected_topics=detected_topics,
    )

    if prompts:
        lines.append("**Here are some things I can help with:**")
        for i, p in enumerate(prompts[:6], 1):
            lines.append(f"{i}. {p}")
        lines.append("")

    # Other projects
    if other_projects:
        lines.append(f"_(You also have {', '.join(other_projects[:5])} indexed.)_\n")

    summary_md = "\n".join(lines)

    # -- Structured diagnostics for programmatic use ------------------------
    diagnostics: Dict[str, Any] = {
        "project_id": project_id,
        "project_name": project_name,
        "index_loaded": index_exists,
        "total_chunks": total_chunks,
        "building": building,
        "stale": stale,
        "stale_count": stale_count,
        "trace_enabled": trace_enabled,
        "trace_nodes": total_nodes,
        "trace_edges": total_edges,
        "trace_coverage_pct": trace_pct,
        "watch_enabled": watch_enabled,
        "included_paths_count": file_count,
        "path_weights": path_weights,
        "other_projects": other_projects[:5],
    }
    if hub_files:
        diagnostics["hub_files"] = hub_files
    if stale_file_paths:
        diagnostics["stale_files"] = stale_file_paths
    if file_edges:
        diagnostics["file_edges"] = file_edges[:10]
    if detected_topics:
        diagnostics["detected_topics"] = detected_topics

    # -- AI presentation guidance ------------------------------------------
    ai_note = (
        "IMPORTANT: The selected files ARE the user's focus. Lead with them.\n\n"
        "STANDALONE (user only said 'hi_codrag'): Present the file inventory "
        "conversationally -- tell the user exactly which files and areas you're "
        "looking at. Group them naturally: 'I can see your design docs (X, Y), "
        "the code in components/ (A, B, C), and some tests.' If docs are selected, "
        "mention what they appear to be about (from filenames and doc_previews). "
        "Mention hub files as 'the most important/connected files'. "
        "Mention trace/graph as a background capability, not the lead. "
        "Offer the suggested prompts as numbered options. Speak in first person.\n\n"
        "WITH A QUESTION (user said 'hi_codrag' AND asked something): Briefly "
        "acknowledge the selected files (1 sentence), then address their question. "
        "Use prep_search to retrieve specific content from the selected files.\n\n"
        "DEEPER CONTEXT: For detailed file content, call `prep` (the ambient "
        "context tool) -- it returns LOD-stratified content from hub files and "
        "module summaries. Use it when the user picks a suggested prompt or asks "
        "a specific question about the selected files."
    )

    result: Dict[str, Any] = {
        "_ai_note": ai_note,
        "summary": summary_md,
        "file_inventory": file_inventory,
        "diagnostics": diagnostics,
        "_to_markdown": summary_md,
    }
    if doc_previews:
        result["doc_previews"] = doc_previews
    if detected_topics:
        result["detected_topics"] = detected_topics
    return result


# ── Helper functions ─────────────────────────────────────────────────


_TOPIC_CLUSTERS: Dict[str, set] = {
    "authentication": {"auth", "login", "logout", "session", "token", "tokens", "jwt", "oauth", "sso", "password", "credential", "signup", "signin"},
    "e-commerce": {"cart", "checkout", "payment", "order", "orders", "invoice", "billing", "subscription", "pricing", "product", "products", "catalog", "shop", "store"},
    "UI components": {"button", "modal", "dialog", "sidebar", "navbar", "nav", "header", "footer", "card", "cards", "form", "input", "dropdown", "tooltip", "menu", "tabs", "panel", "layout", "widget"},
    "API layer": {"api", "endpoint", "endpoints", "route", "routes", "router", "controller", "controllers", "handler", "handlers", "middleware", "rest", "graphql", "grpc"},
    "data models": {"model", "models", "schema", "schemas", "entity", "entities", "migration", "migrations", "database", "db", "orm", "repository", "repo"},
    "testing": {"test", "tests", "spec", "specs", "fixture", "fixtures", "mock", "mocks", "e2e", "integration", "unit"},
    "infrastructure": {"deploy", "deployment", "docker", "dockerfile", "compose", "terraform", "k8s", "kubernetes", "ci", "cd", "pipeline", "github", "workflow", "nginx", "helm"},
    "configuration": {"config", "settings", "env", "environment", "constants", "defaults", "options", "preferences"},
    "state management": {"store", "redux", "context", "provider", "reducer", "action", "actions", "state", "slice", "zustand", "atom"},
    "animation & visuals": {"animation", "parallax", "scroll", "canvas", "transition", "effect", "shader", "particle", "three", "webgl", "gsap"},
    "messaging & events": {"event", "events", "listener", "emitter", "queue", "message", "messages", "pubsub", "webhook", "webhooks", "notification", "notifications"},
    "file & storage": {"upload", "download", "file", "files", "storage", "s3", "blob", "media", "image", "images", "asset", "assets"},
}


def _detect_topics(paths: List[str]) -> List[Dict[str, Any]]:
    """Cluster filenames into recognizable topics via keyword matching."""
    all_stems: List[str] = []
    for p in paths:
        name = Path(p).stem
        parts = re.findall(r'[a-z]+|[A-Z][a-z]*|\d+', name)
        all_stems.extend(w.lower() for w in parts if len(w) > 1)

    stem_set = set(all_stems)

    detected: List[Dict[str, Any]] = []
    for topic, keywords in _TOPIC_CLUSTERS.items():
        matches = stem_set & keywords
        if len(matches) >= 2:
            matched_files: List[str] = []
            for p in paths:
                name = Path(p).stem
                file_parts = {w.lower() for w in re.findall(r'[a-z]+|[A-Z][a-z]*|\d+', name) if len(w) > 1}
                if file_parts & keywords:
                    matched_files.append(str(Path(p).name))
            detected.append({
                "topic": topic,
                "match_count": len(matches),
                "keywords": sorted(matches),
                "files": matched_files[:8],
            })

    detected.sort(key=lambda x: -x["match_count"])
    return detected[:5]


def _build_prompts(
    *,
    index_exists: bool,
    docs: List[str],
    code: List[str],
    tests: List[str],
    all_dir_segments: set,
    project_name: str,
    trace_enabled: bool,
    total_nodes: int,
    stale: bool,
    stale_file_paths: List[str],
    detected_topics: List[Dict[str, Any]],
) -> List[str]:
    """Generate content-aware suggested prompts."""
    prompts: List[str] = []

    if not index_exists:
        prompts.append("Build the index from the Prep dashboard to get started.")
        return prompts

    # Doc-aware prompts
    if docs:
        doc_basenames = [Path(d).stem.replace("_", " ").replace("-", " ") for d in docs[:5]]
        joined = " ".join(doc_basenames).lower()
        if any(kw in joined for kw in ("design", "plan", "spec", "rfc", "proposal", "architecture")):
            prompts.append("What do the design docs say? Summarize the plans and identify next steps.")
        elif any(kw in joined for kw in ("todo", "task", "roadmap", "backlog")):
            prompts.append("What's on the TODO/roadmap? What should I work on next?")
        elif any(kw in joined for kw in ("api", "endpoint", "route")):
            prompts.append("Summarize the API documentation and identify any gaps.")
        else:
            prompts.append("Summarize these docs and identify any action items or open questions.")

    # Code-aware prompts
    _code_prompt_added = False
    if code:
        if all_dir_segments & {"api", "routes", "endpoints", "server"}:
            prompts.append("What API endpoints are in these files? Any missing error handling?")
            _code_prompt_added = True
        if all_dir_segments & {"components", "views", "pages", "ui"}:
            prompts.append("What UI components are here and how do they connect?")
            _code_prompt_added = True
        if not _code_prompt_added:
            if len(code) <= 10:
                prompts.append("Walk me through this code -- what does each file do and how do they relate?")
            else:
                prompts.append(f"How is {project_name} structured? What are the main modules?")

    if tests:
        prompts.append("Review my tests -- what's well-covered and what's missing?")

    if docs and code:
        prompts.append("Compare the design docs to the implementation -- is anything out of sync?")

    if trace_enabled and total_nodes > 0 and len(prompts) < 5:
        prompts.append("What are the most connected files and why?")

    if stale:
        prompts.append("Rebuild the index from the Prep dashboard to refresh.")

    if stale_file_paths and not stale:
        stale_sample = ", ".join(f"`{Path(sp).name}`" for sp in stale_file_paths[:3])
        prompts.append(f"Review what changed in {stale_sample} since the last build.")

    # O-3: Topic-aware prompts
    if detected_topics and len(prompts) < 5:
        top_topic = detected_topics[0]["topic"]
        topic_files = ", ".join(f"`{f}`" for f in detected_topics[0]["files"][:3])
        _topic_prompts: Dict[str, str] = {
            "authentication": f"Review the auth flow across {topic_files} -- any security concerns?",
            "e-commerce": f"Trace the purchase flow through {topic_files} -- what happens end to end?",
            "UI components": f"How do the UI components ({topic_files}) compose together?",
            "API layer": f"What API endpoints exist in {topic_files}? Any missing validation?",
            "data models": f"Review the data models in {topic_files} -- are the relationships clean?",
            "infrastructure": f"Review the infra setup ({topic_files}) -- anything missing or outdated?",
            "state management": f"How is state managed across {topic_files}? Any unnecessary complexity?",
            "animation & visuals": f"Walk me through the animation system ({topic_files}) -- how do the effects compose?",
            "messaging & events": f"Trace the event flow through {topic_files} -- what triggers what?",
            "file & storage": f"Review the file handling in {topic_files} -- any edge cases with large files?",
        }
        topic_prompt = _topic_prompts.get(top_topic)
        if topic_prompt and topic_prompt not in prompts:
            prompts.append(topic_prompt)

    # Generic fallbacks to reach minimum 3
    fallbacks = [
        f"What does {project_name} do? Give me a high-level overview.",
        "What are the key data models or types?",
        "What could be improved or refactored in this code?",
    ]
    for fb in fallbacks:
        if len(prompts) >= 4:
            break
        if fb not in prompts:
            prompts.append(fb)

    # O-4: Smart prompt ordering -- reorder by category match
    dominant_cat = "code"
    cat_counts = {"docs": len(docs), "code": len(code), "tests": len(tests)}
    if cat_counts:
        dominant_cat = max(cat_counts, key=lambda k: cat_counts[k])

    def _prompt_score(prompt_text: str) -> int:
        pt = prompt_text.lower()
        if dominant_cat == "docs" and any(kw in pt for kw in ("doc", "design", "plan", "summarize", "todo", "roadmap")):
            return 3
        if dominant_cat == "tests" and any(kw in pt for kw in ("test", "coverage", "edge case")):
            return 3
        if dominant_cat == "code" and any(kw in pt for kw in ("code", "module", "endpoint", "component", "structured", "walk")):
            return 3
        if docs and code and any(kw in pt for kw in ("compare", "sync", "implementation")):
            return 2
        return 1

    prompts.sort(key=_prompt_score, reverse=True)
    return prompts
