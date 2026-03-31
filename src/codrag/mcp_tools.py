"""
Shared tool definitions for CoDRAG MCP servers.

Phase 50: Consolidated from 16 tools to 5 + 1 dev alias.
Descriptions use Purpose + Guidelines pattern (arXiv:2602.14878).

TOOLS       — the production tool set (listed in tools/list)
LEGACY_TOOLS — old definitions preserved for reference/testing
TOOL_ALIASES — maps old tool names to new tool handlers
"""
import os as _os

_DEV_MODE = _os.environ.get("CODRAG_DEV_MODE", "").lower() in ("1", "true", "yes")

# Shared project_id property — reused across all tools
_PROJECT_ID_PROP = {
    "type": "string",
    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
}

# =============================================================================
# Production Tools (5 tools + optional dev alias)
# =============================================================================

_CORE_TOOLS = [
    # ── 1. codrag (ambient context — the primary tool) ──────────────
    {
        "name": "codrag",
        "description": (
            "Get structural codebase context -- modules, hub files, and knowledge base content. "
            "Call this FIRST at the start of every task to understand the codebase architecture "
            "before reading or editing files. Returns module summaries, the most-connected files, "
            "and any files the user has selected as focus areas. No arguments needed. "
            "Use codrag_search instead when you need to find something specific."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": "(Advanced) Maximum characters in assembled context. Auto-sized for your AI tool if omitted.",
                },
                "role": {
                    "type": "string",
                    "description": (
                        "Optional role to filter context for a specific audience "
                        "(e.g. 'ceo', 'design engineer', 'security', 'intern'). "
                        "Returns a role-appropriate codebase view with matched detail level."
                    ),
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": [],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    # ── 2. codrag_search (query-based retrieval) ────────────────────
    {
        "name": "codrag_search",
        "description": (
            "Search for code using a natural language query or symbol name. "
            "CoDRAG applies semantic search, structural trace expansion, and LOD compression "
            "to assemble focused context. Use 'type' to select the search mode: "
            "'context' (default) for semantic search with structural expansion, "
            "'symbol' for finding functions/classes/modules by name."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query or symbol name to search for.",
                },
                "type": {
                    "type": "string",
                    "description": "Search mode: 'context' (semantic search, default) or 'symbol' (find by name).",
                    "enum": ["context", "symbol"],
                    "default": "context",
                },
                "exclude_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths already in your context. CoDRAG excludes these to avoid redundancy.",
                    "default": [],
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in assembled context. Default: 12000.",
                    "default": 12000,
                },
                "k": {
                    "type": "integer",
                    "description": "(Advanced) Number of initial chunks to retrieve. Default: 5.",
                    "default": 5,
                },
                "kind": {
                    "type": "string",
                    "description": "(Advanced, symbol mode only) Filter by node kind.",
                    "enum": ["function", "class", "module", "method", "variable", "import"],
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    # ── 3. codrag_impact (blast radius + graph traversal) ───────────
    {
        "name": "codrag_impact",
        "description": (
            "Analyze what connects to a file or symbol -- dependencies, dependents, or both. "
            "Requires file_path or symbol. "
            "Call this BEFORE making changes to understand the blast radius. "
            "Use direction='dependents' (default) for 'what breaks if I change X?', "
            "'dependencies' for 'what does X depend on?', "
            "'all' for full neighborhood in the code graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path to analyze (e.g., 'src/auth/login.py').",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol node ID for symbol-level analysis (from codrag_search type='symbol' results).",
                },
                "direction": {
                    "type": "string",
                    "description": "Relationship direction: 'dependents' (what breaks), 'dependencies' (what it needs), 'all' (both). Default: 'dependents'.",
                    "enum": ["dependents", "dependencies", "all"],
                    "default": "dependents",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Traversal depth. 1 = direct only, 2 = include transitive. Default: 2.",
                    "default": 2,
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": [],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    # ── 4. codrag_audit (codebase health) ───────────────────────────
    {
        "name": "codrag_audit",
        "description": (
            "Run or retrieve a codebase health audit with findings about architecture, "
            "code quality, and tech debt. Use 'action' to select the operation: "
            "'scan' (default) to run the audit, "
            "'refactor' to get findings with code context for implementation (pass finding_ids), "
            "'verify' to re-check specific analyzers after fixes (pass analyzers), "
            "'report' to retrieve a full report document (pass report_name), "
            "'advise' to get forward-looking design proposals and TODO detection."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Operation: 'scan', 'refactor', 'verify', 'report', or 'advise'. Default: 'scan'.",
                    "enum": ["scan", "refactor", "verify", "report", "advise"],
                    "default": "scan",
                },
                "synthesize": {
                    "type": "boolean",
                    "description": "(scan) Also generate LLM-written markdown reports. Default: false.",
                    "default": False,
                },
                "category": {
                    "type": "string",
                    "description": "(scan) Filter to a specific finding category.",
                    "enum": ["size", "architecture", "quality", "coverage", "naming", "testing"],
                },
                "finding_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "(refactor) IDs of findings to address (e.g. ['ARCH-1', 'QUAL-3']).",
                },
                "instructions": {
                    "type": "string",
                    "description": "(refactor) Additional instructions for the refactoring approach.",
                },
                "analyzers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "(verify) Analyzer names to re-run (e.g. ['large_files', 'circular_deps']).",
                },
                "report_name": {
                    "type": "string",
                    "description": "(report) Name of the report to retrieve.",
                    "enum": ["AUDIT_SUMMARY", "ARCHITECTURE_ANALYSIS", "GAP_ANALYSIS", "COMPONENT_INVENTORY", "TECH_DEBT_REPORT"],
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": [],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    # ── 5. codrag_observe (session memory) ──────────────────────────
    {
        "name": "codrag_observe",
        "description": (
            "Save or retrieve observations about the codebase for cross-session memory. "
            "Observations persist across sessions and are flagged stale when linked files change. "
            "Use action='save' to record a decision, bug, or pattern (pass content). "
            "Use action='get' to retrieve previous observations (optional query or file_path filter)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Operation: 'save' or 'get'. Default: 'get'.",
                    "enum": ["save", "get"],
                    "default": "get",
                },
                "content": {
                    "type": "string",
                    "description": "(save) The observation text. Concise and actionable (max 2000 chars).",
                },
                "file_path": {
                    "type": "string",
                    "description": "(save) File the observation relates to. (get) Filter by file path.",
                },
                "symbol": {
                    "type": "string",
                    "description": "(save) Fully qualified symbol name. Optional.",
                },
                "category": {
                    "type": "string",
                    "description": "(save) Category. Default: 'note'.",
                    "enum": ["note", "decision", "bug", "pattern", "assumption"],
                    "default": "note",
                },
                "query": {
                    "type": "string",
                    "description": "(get) Search observations by content.",
                },
                "limit": {
                    "type": "integer",
                    "description": "(get) Maximum observations to return. Default: 10.",
                    "default": 10,
                },
                "include_stale": {
                    "type": "boolean",
                    "description": "(get) Include stale observations. Default: true.",
                    "default": True,
                },
                "project_id": _PROJECT_ID_PROP,
            },
            "required": [],
        },
        "annotations": {"readOnlyHint": False},
    },
]

# Dev alias: codrag_context (listed only when CODRAG_DEV_MODE=1)
_DEV_ALIAS_TOOL = {
    "name": "codrag_context",
    "description": (
        "Alias for `codrag` -- get ambient structural codebase context. "
        "Same as calling codrag with no arguments. "
        "Provided for development/testing clarity."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters in assembled context. Default: 12000.",
                "default": 12000,
            },
            "project_id": _PROJECT_ID_PROP,
        },
        "required": [],
    },
    "annotations": {"readOnlyHint": True, "openWorldHint": True},
}

# Build the final TOOLS list
TOOLS = list(_CORE_TOOLS)
if _DEV_MODE:
    TOOLS.append(_DEV_ALIAS_TOOL)


# =============================================================================
# Backward Compatibility: Alias Mapping
# =============================================================================
# Maps old tool names to (new_tool_name, param_transform_hint).
# The MCP server dispatch uses this to route calls from old tool names
# to new handlers. Old names are NOT listed in tools/list but still work
# when called directly (e.g., from existing .cursorrules or user habits).

TOOL_ALIASES = {
    # Direct aliases (identical behavior)
    "codrag_context": "codrag",
    "codrag_":        "codrag",

    # Absorbed into codrag (ambient response includes health + coverage)
    "hi_codrag":           "codrag",
    "codrag_status":       "codrag",
    "codrag_trace_coverage": "codrag",

    # Consolidated into codrag_search
    "codrag_trace_search": "codrag_search",       # type=symbol

    # Consolidated into codrag_impact (direction=all for neighbors)
    "codrag_trace_neighbors": "codrag_impact",     # direction=all

    # Admin tool -- kept as hidden dispatch alias
    "codrag_build": "codrag_build",                # special: not in TOOLS but still dispatches

    # Consolidated into codrag_audit
    "codrag_audit_refactor": "codrag_audit",       # action=refactor
    "codrag_audit_check":    "codrag_audit",       # action=verify
    "codrag_audit_report":   "codrag_audit",       # action=report

    # Consolidated into codrag_observe
    "codrag_save_observation": "codrag_observe",   # action=save
    "codrag_get_observations": "codrag_observe",   # action=get
}


# =============================================================================
# Legacy Tools (preserved for reference and testing)
# =============================================================================
# The original 16 tool definitions. Not used in production but kept
# so tests can verify backward compatibility of the alias dispatch.

LEGACY_TOOLS = [
    {
        "name": "codrag_status",
        "description": "Get CoDRAG index status and daemon health. Returns index stats, build state, and configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted. Use codrag_status to list available projects.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "activity",
                "light": "activity",
                "dark": "activity"
            }
        }
    },
    {
        "name": "codrag_build",
        "description": "Trigger an index build. Returns immediately; build runs async in background. Use codrag_status to check progress.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "full": {
                    "type": "boolean",
                    "description": "Force full rebuild (ignore cache). Default: false (incremental).",
                    "default": False,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "database",
                "light": "database",
                "dark": "database"
            }
        }
    },
    {
        "name": "codrag_search",
        "description": "Search for specific code context using a natural language query. CoDRAG applies semantic search, structural trace expansion, LOD compression, and atlas routing to assemble focused context. For complex requests spanning multiple topics, call once per topic. IMPORTANT: If you receive a PROJECT_SELECTION_AMBIGUOUS error, it means the server cannot auto-detect which project you are working on. You must look at the list of available projects in the error message and immediately retry this tool by passing the correct `project_id`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what context you need.",
                },
                "exclude_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths already in your context. CoDRAG will exclude these from results to avoid redundancy.",
                    "default": [],
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in assembled context. Default: 12000.",
                    "default": 12000,
                },
                "k": {
                    "type": "integer",
                    "description": "(Advanced) Number of initial chunks to retrieve. Default: 5.",
                    "default": 5,
                },
                "trace_expand": {
                    "type": "boolean",
                    "description": "(Advanced) Follow trace edges to include structurally related code. Default: true.",
                    "default": True,
                },
                "compression": {
                    "type": "string",
                    "description": "(Advanced) Compression mode: 'none' (default), 'lingua' (LLMLingua-2 for docs), or 'auto' (dual-channel: lingua for docs, LOD for code).",
                    "enum": ["none", "lingua", "auto"],
                    "default": "none",
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": ["query"],
        },
        "_meta": {
            "icons": {
                "default": "search",
                "light": "search",
                "dark": "search"
            }
        }
    },
    {
        "name": "codrag",
        "description": "Get ambient codebase context — the primary CoDRAG tool. Returns hub files (highest connectivity), module summaries, and structurally related neighbors based on the user's selected focus areas. No query needed. Use codrag_search instead when you need to find something specific. (Full name: codrag_context) IMPORTANT: If you receive a PROJECT_SELECTION_AMBIGUOUS error, it means the server cannot auto-detect which project you are working on. You must look at the list of available projects in the error message and immediately retry this tool by passing the correct `project_id`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in assembled context. Default: 12000.",
                    "default": 12000,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "box",
                "light": "box",
                "dark": "box"
            }
        }
    },
    {
        "name": "codrag_context",
        "description": "Alias for the primary `codrag` tool — get ambient codebase context. Returns hub files (highest connectivity), module summaries, and structurally related neighbors based on the user's selected focus areas. No query needed. Use codrag_search instead when you need to find something specific. IMPORTANT: If you receive a PROJECT_SELECTION_AMBIGUOUS error, it means the server cannot auto-detect which project you are working on. You must look at the list of available projects in the error message and immediately retry this tool by passing the correct `project_id`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in assembled context. Default: 12000.",
                    "default": 12000,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "box",
                "light": "box",
                "dark": "box"
            }
        }
    },
    {
        "name": "codrag_trace_search",
        "description": "Search the code graph (trace index) for symbols by name. Returns matching functions, classes, modules, and other code elements with their file locations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for symbol names (e.g., 'handleClick', 'UserService').",
                },
                "kind": {
                    "type": "string",
                    "description": "Filter by node kind: 'function', 'class', 'module', 'method', etc. Default: all kinds.",
                    "enum": ["function", "class", "module", "method", "variable", "import"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 20.",
                    "default": 20,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": ["query"],
        },
        "_meta": {
            "icons": {
                "default": "git-branch",
                "light": "git-branch",
                "dark": "git-branch"
            }
        }
    },
    {
        "name": "codrag_trace_neighbors",
        "description": "Get neighboring nodes in the code graph for a given node ID. Returns imports, callers, callees, and other structural relationships.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "The ID of the node to get neighbors for (from trace search results).",
                },
                "direction": {
                    "type": "string",
                    "description": "Edge direction: 'in' (callers/importers), 'out' (callees/imports), or 'both'. Default: 'both'.",
                    "enum": ["in", "out", "both"],
                    "default": "both",
                },
                "edge_kinds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by edge kinds: 'imports', 'calls', 'inherits', etc. Default: ['imports'].",
                },
                "max_nodes": {
                    "type": "integer",
                    "description": "Maximum neighbor nodes to return. Default: 25.",
                    "default": 25,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": ["node_id"],
        },
        "_meta": {
            "icons": {
                "default": "share-2",
                "light": "share-2",
                "dark": "share-2"
            }
        }
    },
    {
        "name": "codrag_trace_coverage",
        "description": "Get trace coverage statistics: which files are traced, untraced, stale, or ignored. Useful for understanding code graph completeness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted. Use codrag_status to list available projects.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "pie-chart",
                "light": "pie-chart",
                "dark": "pie-chart"
            }
        }
    },
    {
        "name": "hi_codrag",
        "description": "Greet the user and show what you can see. Call this when the user says 'hi_codrag' or asks what CoDRAG knows. Present the response CONVERSATIONALLY — tell the user what files and areas you're looking at, mention any health issues, and offer the suggested prompts as numbered next-step options. If the user also asked a question, briefly summarize what you see then answer their question (use codrag_search for specifics).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "hand-wave",
                "light": "hand-wave",
                "dark": "hand-wave"
            }
        }
    },
    {
        "name": "codrag_impact",
        "description": "Analyze what depends on a file or symbol — 'what breaks if I change X?' Traverses reverse dependencies (callers, importers) in the code graph and returns a LOD-compressed impact summary. Use this before making changes to understand the blast radius.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path to analyze impact for (e.g., 'src/auth/login.py'). Converted to a file node ID internally.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol node ID to analyze (e.g., 'sym:UserService@src/auth/service.py:10'). Use this for symbol-level impact instead of file-level.",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum traversal depth. 1 = direct dependents only, 2 = include transitive dependents. Default: 2.",
                    "default": 2,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID to target. Optional — auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "alert-triangle",
                "light": "alert-triangle",
                "dark": "alert-triangle"
            }
        }
    },
    {
        "name": "codrag_save_observation",
        "description": "Save a note about the codebase for future sessions. Observations are linked to specific files or symbols and automatically flagged stale when those files change. Use this to record architectural decisions, discovered bugs, design patterns, or assumptions you've made during analysis. Observations persist across sessions so you don't re-discover the same things.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The observation text. Should be concise and actionable (max 2000 chars).",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path the observation relates to. When this file changes, the observation is flagged stale.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Fully qualified symbol name (e.g., 'UserService.validate'). Optional.",
                },
                "category": {
                    "type": "string",
                    "description": "Observation category. Default: 'note'.",
                    "enum": ["note", "decision", "bug", "pattern", "assumption"],
                    "default": "note",
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": ["content"],
        },
        "_meta": {
            "icons": {
                "default": "bookmark",
                "light": "bookmark",
                "dark": "bookmark"
            }
        }
    },
    {
        "name": "codrag_get_observations",
        "description": "Retrieve previous observations about the codebase. Returns notes saved in earlier sessions, with stale flags for observations whose linked files have changed. Use this at the start of a session or when working on a file to see what was previously discovered.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search observations by content. If omitted, returns the most recent observations.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Filter observations linked to a specific file path.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum observations to return. Default: 10.",
                    "default": 10,
                },
                "include_stale": {
                    "type": "boolean",
                    "description": "Include stale observations (linked file changed). Default: true.",
                    "default": True,
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "book-open",
                "light": "book-open",
                "dark": "book-open"
            }
        }
    },
    {
        "name": "codrag_audit",
        "description": "Run or retrieve a codebase health audit. Returns structured findings about architecture, code quality, test coverage, tech debt, and more. Findings are generated from trace graph analysis (no LLM needed). Call with synthesize=true to also generate full markdown reports via LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "synthesize": {
                    "type": "boolean",
                    "description": "If true, also generate LLM-written markdown reports (slower). Default: false (findings only).",
                    "default": False,
                },
                "category": {
                    "type": "string",
                    "description": "(Advanced) Filter to a specific finding category.",
                    "enum": ["size", "architecture", "quality", "coverage", "naming", "testing"],
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": [],
        },
        "_meta": {
            "icons": {
                "default": "clipboard-check",
                "light": "clipboard-check",
                "dark": "clipboard-check"
            }
        }
    },
    {
        "name": "codrag_audit_refactor",
        "description": "Get specific audit findings with trace context for implementation. The user has selected which findings to address. Each finding includes affected files, the problem, and the concrete action to take. CoDRAG automatically includes relevant code context from the trace graph for the affected files. Use this after the user reviews codrag_audit results and selects items to fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "finding_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of the findings to address (e.g. ['ARCH-1', 'QUAL-3']). Get these from codrag_audit.",
                },
                "instructions": {
                    "type": "string",
                    "description": "Optional additional instructions from the user about how to approach the refactoring.",
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": ["finding_ids"],
        },
        "_meta": {
            "icons": {
                "default": "wrench",
                "light": "wrench",
                "dark": "wrench"
            }
        }
    },
    {
        "name": "codrag_audit_check",
        "description": "Re-run specific audit analyzers to verify fixes. Returns only findings from the specified analyzers, so you can confirm whether a fix resolved the issue. Use this after making changes to verify the audit finding is gone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analyzers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analyzer names to re-run: large_files, circular_deps, misplaced_imports, dead_code, hub_bottlenecks, tech_debt, staleness, duplicate_logic, test_coverage, naming_consistency, api_surface.",
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": ["analyzers"],
        },
        "_meta": {
            "icons": {
                "default": "check-circle",
                "light": "check-circle",
                "dark": "check-circle"
            }
        }
    },
    {
        "name": "codrag_audit_report",
        "description": "Retrieve a specific audit report document by name. Reports are generated by codrag_audit with synthesize=true. Available reports: AUDIT_SUMMARY, ARCHITECTURE_ANALYSIS, GAP_ANALYSIS, COMPONENT_INVENTORY, TECH_DEBT_REPORT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string",
                    "description": "Name of the report to retrieve.",
                    "enum": ["AUDIT_SUMMARY", "ARCHITECTURE_ANALYSIS", "GAP_ANALYSIS", "COMPONENT_INVENTORY", "TECH_DEBT_REPORT"],
                },
                "project_id": {
                    "type": "string",
                    "description": "CoDRAG project ID. Auto-detected from workspace root if omitted.",
                },
            },
            "required": ["report_name"],
        },
        "_meta": {
            "icons": {
                "default": "file-text",
                "light": "file-text",
                "dark": "file-text"
            }
        }
    },
]
