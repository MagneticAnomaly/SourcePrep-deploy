"""
Shared tool definitions for CoDRAG MCP servers.
"""

TOOLS = [
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
        "description": "Search for specific code context using a natural language query. CoDRAG applies semantic search, structural trace expansion, LOD compression, and atlas routing to assemble focused context. For complex requests spanning multiple topics, call once per topic.",
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
        "description": "Get ambient codebase context based on the user's selected focus areas and code graph structure. Returns hub files (highest connectivity), module summaries, and structurally related neighbors — no query needed. Use codrag_search instead when you need to find something specific.",
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
]
