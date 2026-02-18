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
        "description": "Search the CoDRAG index with a semantic query. Returns ranked code/doc chunks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return. Default: 8.",
                    "default": 8,
                },
                "min_score": {
                    "type": "number",
                    "description": "Minimum similarity score (0-1). Default: 0.15.",
                    "default": 0.15,
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
                "default": "search",
                "light": "search",
                "dark": "search"
            }
        }
    },
    {
        "name": "codrag",
        "description": "Get assembled context for LLM prompt injection. Returns formatted chunks optimized for token efficiency. Optionally compress context via CLaRa sidecar.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what context you need.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of chunks to include. Default: 5.",
                    "default": 5,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in assembled context. Default: 6000.",
                    "default": 6000,
                },
                "trace_expand": {
                    "type": "boolean",
                    "description": "Follow trace edges (imports, calls) to include structurally related code. Requires trace index to be built. Default: false.",
                    "default": False,
                },
                "compression": {
                    "type": "string",
                    "description": "Compression mode: 'none' (default) or 'clara' (CLaRa sidecar).",
                    "enum": ["none", "clara"],
                    "default": "none",
                },
                "compression_level": {
                    "type": "string",
                    "description": "Compression aggressiveness: 'light', 'standard' (default), or 'aggressive'.",
                    "enum": ["light", "standard", "aggressive"],
                    "default": "standard",
                },
                "compression_timeout_s": {
                    "type": "number",
                    "description": "Hard timeout for CLaRa compression in seconds. Default: 30.",
                    "default": 30.0,
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
]
