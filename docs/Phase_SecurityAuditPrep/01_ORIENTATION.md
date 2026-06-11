# Security Audit Preparation — Phase Overview

**Status:** Orientation Phase (2026-06-11)  
**Effort:** Ultracode (xhigh + workflow orchestration)  
**Scope:** Familiarization → Scaffold → Deep Research Phases

---

## Executive Summary

This codebase is **SourcePrep**, a multi-platform AI-assisted development environment with:
- Python backend (FastAPI daemon on :8400)
- Rust performance engine (tree-sitter parsing, graph building)
- TypeScript/React frontends (Dashboard, VS Code extension, marketing sites)
- MCP (Model Context Protocol) server for IDE integration

**Previous security audit:** March 9, 2026 (Phase 06 Team/Enterprise layer audit) identified 2 critical and 5 high-severity findings. Core codebase assessed as generally sound.

---

## Codebase Architecture at a Glance

### Identity
A multi-platform AI coding environment that:
1. Indexes codebases via Rust engine (AST parsing, file system traversal)
2. Builds semantic knowledge graphs (symbol relationships, imports, calls)
3. Serves context to Claude Code, Cursor, Copilot, and other IDEs via MCP protocol
4. Provides a web dashboard (:5174) and VS Code extension for exploration
5. Orchestrates multi-pass enrichment pipeline (graph → embeddings → LLM augmentation)

### Stack Composition
- **Backend:** Python (FastAPI) — 80% of security surface area
  - Entry points: `src/prep/cli.py` (CLI), `src/prep/server.py` (HTTP), `src/prep/mcp_direct.py` (MCP)
  - Core: `src/prep/core/` (indexing, embeddings, LLM, trace graph, audit)
  - Services: `src/prep/services/` (pipeline, embedder, augmenter, enrichment)
  - API: `src/prep/api/routers/` (projects, search, context, audit, pipeline, etc.)

- **Engine:** Rust — 15% (performance-sensitive paths)
  - `engine/crates/prep-walker` — filesystem traversal
  - `engine/crates/prep-parser` — tree-sitter AST parsing
  - `engine/crates/prep-graph` — symbol graph construction
  - `engine/crates/prep-sanitize` — content filtering

- **Frontend:** TypeScript/React — 5% (lower risk, but integration points matter)
  - Dashboard: `src/prep/dashboard/` — React/Vite app
  - VS Code extension: `packages/vscode/`
  - Shared UI: `packages/ui/` (Radix UI, Tailwind)
  - Marketing/Docs: `websites/apps/`

### Critical Data Flows
1. **Index build pipeline:** Files → Rust parser → AST → Graph → Embeddings → LLM enrichment → SQLite storage
2. **Search/context serving:** Query → Vector search → Trace expansion → Context assembly → Response
3. **MCP protocol:** IDE request → Auth check → Query routing → Response streaming → Error handling
4. **LLM coordination:** Concept analysis → External LLM call → Response parsing → Storage

---

## Known Security Landscape (from March 2026 Audit)

### Critical Issues (CRIT-1, CRIT-2)
- **Unverified License System** — License validation has bypass vectors
- **SSRF via S3 Endpoint** — Attacker can control S3 endpoint URL

### High-Severity Issues (HIGH-1 through HIGH-5)
- **Git Clone Injection** — Shell escaping gaps in git operations
- **Secrets in Permissions** — Sensitive data exposure vectors
- **API Key Logging** — Keys logged to audit/telemetry channels
- **Path Traversal** — File path validation gaps in API
- **Zip Bomb DoS** — Unbounded decompression

### Core Assessment
✅ **Generally sound** — No shell injection, deserialization, or eval vulnerabilities found  
⚠️ **Audit system improvements needed** — Phase 83 plan addresses testing/coverage gaps

---

## Codebase Segments (for targeted review)

### 1. **HTTP API Surface** (Highest Risk)
- File: `src/prep/api/routers/`
- Entry points: `/projects`, `/search`, `/context`, `/pipeline`, `/audit`, `/llm`
- Auth: IPC token verification (check: is it sufficient?)
- Content handling: Query bounds, file path validation, response streaming

### 2. **MCP Server** (High Risk - IDE Integration)
- File: `src/prep/mcp/server.py` (daemon mode) or `src/prep/mcp_direct.py` (standalone)
- Tool definitions: `src/prep/mcp_tools.py`
- Security: Tool parameter validation, caller authentication, error disclosure

### 3. **LLM Coordination** (High Risk - External Calls)
- File: `src/prep/services/llm_*` (embedder, augmenter, enrichment)
- Key operations: Prompt injection, response parsing, token limits
- External models: Ollama, OpenAI, Anthropic (credential handling)

### 4. **File System Access** (Medium-High Risk)
- Rust walker: `engine/crates/prep-walker/`
- Parser: `engine/crates/prep-parser/` (tree-sitter)
- Python layer: `src/prep/core/file_*.py`
- Watch/rebuild: `src/prep/core/watcher.py`

### 5. **Data Storage** (Medium Risk)
- SQLite stores: `src/prep/services/{concept,observation,settings,audit}_store.py`
- JSON files: `.sourceprep/index/` (embedded mode)
- Embeddings: numpy arrays (`.sourceprep/index/embeddings.npy`)
- Secrets: IPC tokens, API keys, credentials

### 6. **Enrichment Pipeline** (Medium Risk)
- File: `src/prep/core/enrichment.py`
- Operation: Annotates external lint/SARIF findings with structural context
- Risk: SARIF injection, unbounded processing, LLM prompt construction

### 7. **Frontend/Dashboard** (Low-Medium Risk)
- React app: `src/prep/dashboard/`
- VS Code webview: `packages/vscode/webview-ui/`
- XSS vectors: Event logging, search results rendering, settings display

---

## Prior Audit Findings (March 2026)

| ID | Severity | Title | Status | File References |
|---|---|---|---|---|
| CRIT-1 | Critical | Unverified License System | Requires design decision | `src/prep/core/license_*.py` |
| CRIT-2 | Critical | SSRF via Attacker-Controlled S3 | Requires design decision | `src/prep/core/storage.py` |
| HIGH-1 | High | Git Clone Injection | Fixed | `src/prep/adapters/git.py` |
| HIGH-2 | High | Secrets in Permissions | Requires design decision | `src/prep/core/auth/permissions.py` |
| HIGH-3 | High | API Key Logging | Fixed (partial) | `src/prep/core/telemetry.py` |
| HIGH-4 | High | Path Traversal in API | Fixed | `src/prep/api/routers/projects/` |
| HIGH-5 | High | Zip Bomb DoS | Requires validation bounds | `src/prep/services/import_service.py` |

---

## Audit Scaffolding — Recommended Deep Dive Phases

### Phase 1: API Boundary Security (Week 1)
**Goal:** Validate all HTTP API endpoints for input validation, auth, and safe response handling
- Review: `src/prep/api/routers/` (all route handlers)
- Check: Path traversal, query injection, file disclosure, authentication bypass
- Tools: Fuzzing, static analysis (ruff, semgrep)

### Phase 2: LLM & External Integration (Week 2)
**Goal:** Audit prompt injection risks, credential handling, and external call bounds
- Review: LLM coordination (embedder, augmenter, enrichment)
- Check: Prompt injection, credential leakage, response parsing, rate limiting
- Tools: Prompt injection testing, credential scanning

### Phase 3: File System & Storage (Week 3)
**Goal:** Validate file access controls, path handling, and storage isolation
- Review: Rust walker, parser, SQLite stores, JSON file handling
- Check: Symlink attacks, directory traversal, isolation between projects
- Tools: Strace/audit, SQLite schema review, fuzzing

### Phase 4: Frontend & Web Security (Week 4)
**Goal:** Assess XSS, CSRF, and web attack surface
- Review: Dashboard, webview UI, search rendering
- Check: Event logging XSS, unsanitized content, CORS policy
- Tools: Browser dev tools, OWASP ZAP, source review

### Phase 5: Enrichment & SARIF Pipeline (Week 5)
**Goal:** Validate external finding handling and data flow safety
- Review: `src/prep/core/enrichment.py`, SARIF parsing, annotation logic
- Check: Injection in annotation templates, unbounded processing, data exposure
- Tools: Fuzzing SARIF inputs, capacity testing

### Phase 6: Auth & IPC Protocol (Week 6)
**Goal:** Audit token generation, verification, and MCP protocol safety
- Review: `src/prep/core/auth/`, IPC middleware, MCP tool dispatch
- Check: Token generation entropy, verification gaps, tool parameter bounds
- Tools: Crypto review, protocol fuzzing

---

## High-Priority Investigation Areas

1. **License enforcement** — CRIT-1 unresolved; requires architecture decision
2. **S3 endpoint validation** — CRIT-2 unresolved; attacker-controlled URLs
3. **Credential exposure** — HIGH-2 & HIGH-3; API keys in logs, secrets in perms
4. **Bounds enforcement** — HIGH-5 & enrichment DoS; zip bombs, unbounded LLM calls
5. **MCP security** — Low coverage; IDE integration entry point

---

## Files to Prioritize

### Must-Review (Security-Critical)
- `src/prep/core/auth/`
- `src/prep/api/routers/projects/`
- `src/prep/services/llm_*`
- `src/prep/mcp/server.py`
- `src/prep/core/enrichment.py`

### Should-Review (Supporting)
- `src/prep/core/watcher.py`
- `src/prep/services/*_store.py`
- `src/prep/adapters/`
- `src/prep/core/security_health.py`

### Could-Review (Lower Risk)
- `src/prep/dashboard/`
- `packages/ui/`
- `packages/vscode/`

---

## Tools & Resources Available

- **SourcePrep MCP tools:** `prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`
- **Static analysis:** ruff (linting), mypy (type checking)
- **Test suite:** `pytest tests/` (check: coverage gaps?)
- **Security docs:** `docs/Phase06_Team_And_Enterprise/SECURITY_AUDIT.md` (prior findings)
- **Audit system:** `src/prep/core/security_health.py` (16 built-in checks)

---

## Next Steps

1. ✅ **Completed:** Structural orientation (you are here)
2. **Next:** Run prep_audit to get baseline structural findings + antibody alerts
3. **Then:** Map vulnerability landscape (which prior issues are fixed vs. pending?)
4. **Then:** Spawn Phase 1 (API boundary security deep dive)

---

## Dogfooding Note

Because SourcePrep is its own development tool, security findings may surface SourcePrep product issues. When they do:
- Flag product findings explicitly: "This is a product bug, not just a security issue in the client project"
- Separate audit findings from tool improvements
- Contribute to SourcePrep roadmap via prep_observe

---

**Generated:** 2026-06-11  
**Next review:** After Phase 1 API audit
