# CoDRAG MCP Tool Reference

Detailed signatures and usage patterns for all CoDRAG MCP tools.

## codrag — Structural Overview

Get the structural overview of the current codebase. Returns module summaries, hub files (most-connected), and knowledge base content from user-curated focus areas.

**Call this FIRST at the start of every task.**

```
codrag()
codrag(project_id="<uuid>")         # explicit project routing
codrag(role="security")             # role-scoped view
codrag(max_chars=20000)             # adjust context budget
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_id` | string | auto-detected | CoDRAG project UUID |
| `role` | string | none | Filter for a specific audience (e.g. 'ceo', 'security', 'intern') |
| `max_chars` | integer | auto-sized | Maximum characters in assembled context |

### Returns

- Module summaries with file counts and descriptions
- Hub files (highest connectivity / blast radius)
- Knowledge base content from curated focus areas
- Workspace map showing segment structure

---

## codrag_search — Semantic Code Search

Search for code using a natural language query. CoDRAG applies semantic search, structural trace expansion, and LOD compression to assemble focused context.

```
codrag_search(query="authentication middleware")
codrag_search(query="database connection pooling", type="context")
codrag_search(query="UserService", type="symbol", kind="class")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | **required** | Natural language query or symbol name |
| `type` | "context" \| "symbol" | "context" | Search mode |
| `project_id` | string | auto-detected | CoDRAG project UUID |
| `k` | integer | 5 | Number of initial chunks to retrieve |
| `max_chars` | integer | 12000 | Maximum characters in assembled context |
| `kind` | string | none | Symbol mode only: "function", "class", "module", "method", "variable", "import" |
| `role` | string | none | Filter results to role's Knowledge Scope |
| `exclude_paths` | string[] | [] | Paths already in context (avoids redundancy) |

### Returns

- Matched code chunks with source paths and relevance scores
- Structural trace expansion (dependencies and dependents of matched files)
- LOD-compressed context that fits within the character budget

---

## codrag_impact — Dependency Analysis

Analyze what connects to a file or symbol. **Call this BEFORE making changes to understand the blast radius.**

```
codrag_impact(file_path="src/auth/login.py")
codrag_impact(file_path="src/auth/login.py", direction="dependents")  # what breaks?
codrag_impact(file_path="src/auth/login.py", direction="dependencies")  # what does it need?
codrag_impact(file_path="src/auth/login.py", direction="all")  # full neighborhood
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | string | none | File path to analyze (e.g. 'src/auth/login.py') |
| `symbol` | string | none | Symbol node ID for symbol-level analysis |
| `direction` | "dependents" \| "dependencies" \| "all" | "dependents" | Relationship direction |
| `max_hops` | integer | 2 | Traversal depth (1 = direct only, 2 = include transitive) |
| `project_id` | string | auto-detected | CoDRAG project UUID |

### Returns

- Direct dependents (files that import/call the target)
- Transitive dependents (2-hop impact radius)
- Dependency count and file paths

---

## codrag_audit — Codebase Health

Run or retrieve a codebase health audit with findings about architecture, code quality, and tech debt.

```
codrag_audit()                                     # scan
codrag_audit(action="scan", category="architecture")  # filtered scan
codrag_audit(action="refactor", finding_ids=["ARCH-1", "QUAL-3"])  # get fix context
codrag_audit(action="advise")                      # forward-looking proposals
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | "scan" \| "refactor" \| "verify" \| "report" \| "advise" | "scan" | Operation mode |
| `category` | string | none | Filter: "size", "architecture", "quality", "coverage", "naming", "testing" |
| `finding_ids` | string[] | none | (refactor) IDs of findings to address |
| `analyzers` | string[] | none | (verify) Analyzer names to re-run |
| `report_name` | string | none | (report) Report type to retrieve |
| `synthesize` | boolean | false | (scan) Also generate markdown reports |
| `project_id` | string | auto-detected | CoDRAG project UUID |

---

## codrag_observe — Cross-Session Memory

Save or retrieve observations about the codebase for cross-session memory. Observations persist across sessions and are flagged stale when linked files change.

```
codrag_observe(action="save", content="Auth uses JWT with RS256", category="decision")
codrag_observe(action="get", query="authentication")
codrag_observe(action="get", file_path="src/auth/login.py")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | "save" \| "get" | "get" | Operation mode |
| `content` | string | none | (save) The observation text (max 2000 chars) |
| `category` | string | "note" | (save) "note", "decision", "bug", "pattern", "assumption" |
| `file_path` | string | none | File the observation relates to |
| `symbol` | string | none | (save) Fully qualified symbol name |
| `query` | string | none | (get) Search observations by content |
| `limit` | integer | 10 | (get) Maximum observations to return |
| `include_stale` | boolean | true | (get) Include stale observations |
| `project_id` | string | auto-detected | CoDRAG project UUID |
