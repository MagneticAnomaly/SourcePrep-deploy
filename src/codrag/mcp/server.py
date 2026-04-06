"""
MCPServer — the main MCP server class with tool implementations,
project resolution, and protocol handling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .errors import (
    BuildInProgressError,
    DaemonError,
    DaemonUnavailableError,
    IndexNotReadyError,
    InvalidParamsError,
    MCPError,
    MethodNotFoundError,
    ProjectNotFoundError,
    ProjectSelectionAmbiguousError,
)

logger = logging.getLogger(__name__)


def configure_logging(*, debug: bool = False, log_file: Optional[str] = None) -> None:
    stderr_level = logging.DEBUG if debug else logging.WARNING
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr:
            h.setLevel(stderr_level)

    if log_file:
        path = Path(str(log_file)).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        for h in root.handlers:
            if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(path):
                break
        else:
            fh = RotatingFileHandler(str(path), maxBytes=1_000_000, backupCount=3)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            root.addHandler(fh)

    root.setLevel(logging.DEBUG if (debug or log_file) else logging.WARNING)
    logger.setLevel(logging.DEBUG if (debug or log_file) else logging.WARNING)


# =============================================================================
# MCP Protocol Constants (spec 2025-11-25)
# =============================================================================

MCP_PROTOCOL_VERSION = "2024-11-05"
JSONRPC_VERSION = "2.0"

# Error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# CoDRAG-specific error codes
DAEMON_UNAVAILABLE = -32000
INDEX_NOT_READY = -32001
BUILD_IN_PROGRESS = -32002
PROJECT_NOT_FOUND = -32003
PROJECT_SELECTION_AMBIGUOUS = -32004

MAX_SEARCH_K = 50
MAX_CONTEXT_K = 50
MAX_CONTEXT_CHARS = 80_000  # Phase 73.2b: raised for Tier 1 (1M context) first-call boost


from codrag.mcp_tools import TOOLS

# =============================================================================
# Tool Definitions
# =============================================================================

# Imported from mcp_tools.py


# =============================================================================
# MCP Server Implementation
# =============================================================================


class MCPServer:
    """
    CoDRAG MCP Server.

    Communicates with the CoDRAG daemon via HTTP API.
    """

    def __init__(
        self,
        daemon_url: str = "http://127.0.0.1:8400",
        project_id: Optional[str] = None,
        auto_detect: bool = False,
    ):
        self.daemon_url = daemon_url.rstrip("/")
        self.project_id = project_id
        self.auto_detect = auto_detect
        self._client: Optional[httpx.AsyncClient] = None
        self._initialize_roots: List[str] = []
        self._client_name: str = "unknown"  # Phase 50: set by handle_initialize
        self._client_version: str = ""  # Phase 50: set by handle_initialize
        self._codrag_called: bool = False  # Phase 50 Sprint 3: nudge tracker
        self._notification_callback = None  # OPP-2: set by transport for resource notifications
        self._last_atlas_signal: Dict[str, float] = {}  # D1: per-project atlas signal mtime

    # OPP-W5: Adaptive token budget tiers based on detected MCP client.
    # Maps clientInfo.name patterns to max_chars defaults.
    #
    # Phase 73.2b: 2.5-tier strategy for 2026 model landscape:
    #
    #   Tier 1 — 1M context (Opus 4, Gemini 2.5 Pro):
    #     50K chars (~12.5K tokens = 1.3% of window).
    #     These models excel at long-context reasoning. Give them
    #     rich structural context: more hub files, deeper LOD,
    #     full concept content (not just stats).
    #
    #   Tier 2 — 200-250K context (Sonnet 4, GPT-4o, Qwen3):
    #     30K chars (~7.5K tokens = 3% of window).
    #     Solid workhorse models. Standard structural context with
    #     hub files + neighbor signatures + module hierarchy.
    #
    #   Tier 2.5 — Local models (assume 250K floor):
    #     20K chars (~5K tokens = 2% of window).
    #     Local models via Cline/Roo/Continue. We drop support for
    #     sub-250K models since they're not useful for code-agent
    #     tasks. 20K is generous for structured context.
    #
    _CLIENT_BUDGETS: Dict[str, int] = {
        # Tier 1: 1M context window models
        "gemini": 50_000,    # Gemini 2.5 Pro: 1M tokens
        # Claude Code sends clientInfo.name="claude-code" for both Opus
        # and Sonnet. Since Opus (1M) and Sonnet (200K) both handle 50K
        # chars easily (6.25% of Sonnet's window), use Tier 1 for all.
        "claude": 50_000,    # Claude Code: Opus (1M) / Sonnet (200K)
        # Tier 2: 200-250K context window models (IDE integrations)
        "cursor": 30_000,    # Cursor: 200K+ (Claude Sonnet / Gemini)
        "windsurf": 30_000,  # Windsurf: 200K+ (Claude Sonnet)
        "cascade": 30_000,   # Windsurf Cascade
        "copilot": 24_000,   # GitHub Copilot: 200K (GPT-4o / Claude)
        "qwen": 24_000,      # Qwen Code: 128-256K tokens
        # Tier 2.5: Local models (250K floor assumed)
        "cline": 20_000,     # Cline: local models
        "roo": 20_000,       # Roo Code: local models
        "continue": 20_000,  # Continue: local models
    }
    _DEFAULT_BUDGET = 24_000  # Assume Tier 2 for unknown clients

    def _get_context_budget(self) -> int:
        """Return adaptive max_chars based on detected MCP client.

        Phase 50 OPP-W5: Different AI tools have different context window
        sizes. We detect the client from the MCP initialize handshake
        and assign the appropriate tier budget.

        Phase 73.2: First-call orientation boost — the first `codrag` call
        in a session gets 50% more context because that's when the agent
        is building its mental model of the codebase. Subsequent calls
        get the standard budget since the agent already has orientation.
        """
        client_lower = self._client_name.lower()
        base = self._DEFAULT_BUDGET
        for pattern, budget in self._CLIENT_BUDGETS.items():
            if pattern in client_lower:
                base = budget
                break

        # First-call orientation boost: give 50% more context
        if not self._codrag_called:
            base = int(base * 1.5)

        # Clamp to hard cap so auto-computed budgets never fail validation
        return min(base, MAX_CONTEXT_CHARS)

    def _get_context_tier(self) -> int:
        """Return the context tier int for the current client.

        Phase 73.3b: Flows the tier to the backend so LOD thresholds,
        hub selection, and module display adapt per client.
        Uses the BASE budget (without orientation boost) for tier detection.
        """
        from codrag.core.context_tier import tier_from_budget
        client_lower = self._client_name.lower()
        base = self._DEFAULT_BUDGET
        for pattern, budget in self._CLIENT_BUDGETS.items():
            if pattern in client_lower:
                base = budget
                break
        return tier_from_budget(base).value

    def _project_has_rules_file(self, project_id: str) -> bool:
        """Check if a CoDRAG rules file exists for the resolved project.

        ISSUE-6: When a rules file exists, the atlas is already in the AI's
        system prompt. The codrag tool response can skip the atlas and allocate
        more budget to actual code content.

        Checks for any of: .cursor/rules/codrag.mdc, .windsurf/rules/codrag.md,
        AGENTS.md with CoDRAG markers, CLAUDE.md with CoDRAG markers.
        Cached per project_id for the session lifetime (~0 cost after first check).

        Also extracts the atlas content hash if present, cached in
        ``_rules_atlas_hash_cache`` for use by ``tool_context()``.
        """
        cache = getattr(self, "_rules_file_cache", None)
        if cache is None:
            self._rules_file_cache: Dict[str, bool] = {}
            cache = self._rules_file_cache
        if project_id in cache:
            return cache[project_id]

        # Ensure hash cache exists
        if not hasattr(self, "_rules_atlas_hash_cache"):
            self._rules_atlas_hash_cache: Dict[str, Optional[str]] = {}

        found = False
        try:
            # Resolve project path from daemon (cached by _resolve_project_id)
            # Use a sync approach: check the project path we got from initialize roots
            # or fall back to a lightweight heuristic.
            project_path = self._get_project_path_sync(project_id)
            if project_path:
                p = Path(project_path)
                # Check the most common rules files
                if (p / ".cursor" / "rules" / "codrag.mdc").exists():
                    found = True
                elif (p / ".windsurf" / "rules" / "codrag.md").exists():
                    found = True
                elif (p / "AGENTS.md").exists():
                    try:
                        content = (p / "AGENTS.md").read_text(encoding="utf-8")[:500]
                        if "codrag-managed" in content or "CoDRAG" in content:
                            found = True
                    except Exception:
                        pass
                # CLAUDE.md — also extract atlas hash for precise freshness
                if not found and (p / "CLAUDE.md").exists():
                    try:
                        content = (p / "CLAUDE.md").read_text(encoding="utf-8")
                        if "codrag-managed" in content[:500] or "CoDRAG" in content[:500]:
                            found = True
                        # Extract atlas hash (may be anywhere in the managed section)
                        atlas_hash = self._extract_atlas_hash(content)
                        if atlas_hash:
                            self._rules_atlas_hash_cache[project_id] = atlas_hash
                    except Exception:
                        pass
                elif found and (p / "CLAUDE.md").exists():
                    # Rules found via another file, but also check CLAUDE.md for hash
                    try:
                        content = (p / "CLAUDE.md").read_text(encoding="utf-8")
                        atlas_hash = self._extract_atlas_hash(content)
                        if atlas_hash:
                            self._rules_atlas_hash_cache[project_id] = atlas_hash
                    except Exception:
                        pass
        except Exception:
            pass

        cache[project_id] = found
        return found

    def _get_rules_atlas_hash(self, project_id: str) -> Optional[str]:
        """Return the cached atlas hash from the project's rules file, or None."""
        if not hasattr(self, "_rules_atlas_hash_cache"):
            return None
        return self._rules_atlas_hash_cache.get(project_id)

    @staticmethod
    def _extract_atlas_hash(content: str) -> str | None:
        """Extract the atlas content hash from a rules file.

        Looks for <!-- codrag-atlas-hash:XXXX --> comment.
        Returns the hash string or None if not found.
        """
        match = re.search(r"codrag-atlas-hash:([a-f0-9]{12})", content)
        return match.group(1) if match else None

    def _get_project_path_sync(self, project_id: str) -> Optional[str]:
        """Get the filesystem path for a project without an async call.

        Uses cached data from previous _resolve_project_id calls or
        initialize roots. Returns None if path is unknown.
        """
        # If we have initialize roots, the first one is likely the project path
        if self._initialize_roots:
            return self._initialize_roots[0]
        # Fall back to CWD (common in single-project setups)
        try:
            return str(Path.cwd().resolve())
        except Exception:
            return None

    async def _check_atlas_signal(self, project_id: str) -> None:
        """D1: Check if the pipeline wrote a new atlas since our last check.

        Reads the atlas_updated.signal file from the project's index directory.
        If it's newer than our last recorded mtime, invalidate the rules file
        cache (rules were regenerated alongside the atlas) and send resource
        notifications to the MCP host.

        The signal file is written by PipelineOrchestrator._write_atlas_signal()
        after Stage 1 (preliminary atlas) and Stage 9 (full LLM atlas).

        Cost: one stat() call per tool_context() invocation (~0.1ms).
        No HTTP calls -- uses local filesystem path from initialize roots / CWD.
        """
        try:
            project_path = self._get_project_path_sync(project_id)
            if not project_path:
                return

            # CoDRAG index lives at <project_path>/.codrag/ or the daemon's
            # configured data dir. Check both common locations.
            candidates = [
                Path(project_path) / ".codrag" / "atlas_updated.signal",
            ]
            # Also check if project_path itself IS the index dir (daemon mode)
            direct = Path(project_path) / "atlas_updated.signal"
            if direct.exists():
                candidates.insert(0, direct)

            signal_path = None
            for c in candidates:
                if c.exists():
                    signal_path = c
                    break

            if signal_path is None:
                return

            mtime = signal_path.stat().st_mtime
            last = self._last_atlas_signal.get(project_id, 0.0)

            if mtime > last:
                self._last_atlas_signal[project_id] = mtime
                # Invalidate rules file cache (rules were regenerated with new atlas)
                if hasattr(self, "_rules_file_cache"):
                    self._rules_file_cache.pop(project_id, None)
                # Notify host that cached resources are stale.
                # Atlas rebuild affects: atlas, structure, modules (all derived from index).
                for resource_type in ("atlas", "structure", "modules", "health"):
                    await self.notify_resource_changed(f"codrag://{project_id}/{resource_type}")
                logger.debug(
                    "D1: Atlas signal detected for %s (mtime %.0f > %.0f)", project_id, mtime, last
                )
        except Exception:
            pass  # Non-fatal -- worst case the AI gets slightly stale data

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def notify_resource_changed(self, uri: str) -> None:
        """OPP-2: Send resource-updated notification to the MCP host.

        Tells the host that a cached resource is stale and should be re-read.
        The transport layer must set ``_notification_callback`` for this to work.
        Best-effort -- hosts that don't support subscriptions ignore this.
        """
        if self._notification_callback is None:
            return
        try:
            notification = {
                "jsonrpc": JSONRPC_VERSION,
                "method": "notifications/resources/updated",
                "params": {"uri": uri},
            }
            await self._notification_callback(notification)
        except Exception:
            logger.debug("Resource notification failed for %s (non-fatal)", uri, exc_info=True)

    def _unwrap_envelope(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        if "success" not in payload or "data" not in payload:
            return payload
        if payload.get("success") is True:
            return payload.get("data")
        err = payload.get("error")
        if isinstance(err, dict):
            code = str(err.get("code") or "ERROR")
            message = str(err.get("message") or "Request failed")
            hint = err.get("hint")
            text = f"{code}: {message}"
            if hint:
                text = f"{text} (hint: {hint})"
            if code == "PROJECT_NOT_FOUND":
                raise ProjectNotFoundError(text)
            if code in ("INDEX_NOT_BUILT", "INDEX_NOT_READY"):
                raise IndexNotReadyError(text)
            if code in ("BUILD_ALREADY_RUNNING", "TRACE_BUILD_ALREADY_RUNNING"):
                raise BuildInProgressError(text)
            raise DaemonError(text)
        raise DaemonError("Request failed")

    async def _api_get(self, path: str) -> Any:
        """GET request to daemon API."""
        client = await self._get_client()
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.daemon_url}{path}"
        logger.debug(f"GET {url}")

        # SECURITY: Include IPC token if daemon requires authentication
        headers: Dict[str, str] = {}
        ipc_token = os.environ.get("CODRAG_DAEMON_TOKEN")
        if ipc_token:
            headers["Authorization"] = f"Bearer {ipc_token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise DaemonUnavailableError(
                f"Cannot connect to CoDRAG daemon at {self.daemon_url}\n\n"
                f"Start the daemon in a terminal:\n"
                f"  codrag serve"
            )
        except httpx.HTTPStatusError as e:
            try:
                self._unwrap_envelope(e.response.json())
            except DaemonError as de:
                raise de
            except Exception:
                pass
            raise DaemonError(f"Daemon returned {e.response.status_code}: {e.response.text}")

        try:
            payload = resp.json()
        except Exception:
            raise DaemonError(f"Daemon returned invalid JSON: {resp.text}")
        return self._unwrap_envelope(payload)

    async def _api_post(self, path: str, payload: Dict[str, Any]) -> Any:
        """POST request to daemon API."""
        client = await self._get_client()
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.daemon_url}{path}"
        logger.debug(f"POST {url} payload_keys={list(payload.keys())}")

        # SECURITY: Include IPC token if daemon requires authentication
        headers: Dict[str, str] = {}
        ipc_token = os.environ.get("CODRAG_DAEMON_TOKEN")
        if ipc_token:
            headers["Authorization"] = f"Bearer {ipc_token}"

        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise DaemonUnavailableError(
                f"Cannot connect to CoDRAG daemon at {self.daemon_url}\n\n"
                f"Start the daemon in a terminal:\n"
                f"  codrag serve"
            )
        except httpx.HTTPStatusError as e:
            try:
                self._unwrap_envelope(e.response.json())
            except DaemonError as de:
                raise de
            except Exception:
                pass
            raise DaemonError(f"Daemon returned {e.response.status_code}: {e.response.text}")

        try:
            payload_out = resp.json()
        except Exception:
            raise DaemonError(f"Daemon returned invalid JSON: {resp.text}")
        return self._unwrap_envelope(payload_out)

    def _best_project_match(
        self, projects: List[Dict[str, Any]], paths: List[str]
    ) -> Optional[str]:
        """Return the project_id whose root best matches any of the given paths.

        Only uses filesystem path matching. The caller is responsible for
        filtering to active projects (via activity_status) before calling.

        Returns None if zero matches or if multiple projects tie (ambiguous).

        Scoring:
          - Exact match:                    10000 + len(path)
          - Check path is subfolder of proj: 1000 + len(project_path)
          - Project is subfolder of check:   len(check_path)
        """
        best_id: Optional[str] = None
        best_len = -1
        ambiguous = False

        for p in projects:
            pid = p.get("id")
            p_path = str(p.get("path") or "").rstrip("/")
            if not pid or not p_path:
                continue
            for check_path in paths:
                check = check_path.rstrip("/")
                if not check or check == "/":
                    continue  # Root FS is not a useful signal

                score = -1
                if check == p_path:
                    score = 10000 + len(p_path)
                elif check.startswith(p_path + "/"):
                    score = 1000 + len(p_path)
                elif p_path.startswith(check + "/"):
                    score = len(check)

                if score > -1:
                    if score > best_len:
                        best_id = str(pid)
                        best_len = score
                        ambiguous = False
                    elif score == best_len and str(pid) != best_id:
                        ambiguous = True

        if ambiguous:
            return None
        return best_id

    async def _auto_register_codrag_folders(
        self, paths: List[str], existing_projects: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Auto-register projects with .codrag/ folders that aren't in the daemon yet.

        When a workspace root or CWD contains a .codrag/ directory (created by
        ``codrag init``), the project should be usable immediately without
        manual ``codrag add``. This checks each path for .codrag/ and registers
        any unregistered ones as embedded-mode projects.

        Returns the project_id of the first newly-registered project, or None.
        """
        existing_paths = {
            str(p.get("path", "")).rstrip("/") for p in existing_projects if p.get("path")
        }

        for path in paths:
            clean = path.rstrip("/")
            if not clean or clean == "/":
                continue

            codrag_dir = Path(clean) / ".codrag"
            if not codrag_dir.is_dir():
                continue

            # Already registered?
            if clean in existing_paths:
                continue

            # Auto-register as embedded project
            try:
                result = await self._api_post(
                    "/projects",
                    {
                        "path": clean,
                        "name": Path(clean).name,
                        "mode": "embedded",
                    },
                )
                new_id = None
                if isinstance(result, dict):
                    new_id = str(result.get("id") or result.get("project", {}).get("id", ""))
                if new_id:
                    logger.info(f"Auto-registered project from .codrag folder: {clean} -> {new_id}")
                    return new_id
            except Exception as e:
                logger.debug(f"Auto-register failed for {clean}: {e}")

        return None

    async def _get_project_name(self, project_id: str) -> Optional[str]:
        """Get the display name for a project from the daemon API.

        Returns the project name, or None if lookup fails.
        The /projects/{id} API returns {"project": {"name": ...}}.
        """
        try:
            data = await self._api_get(f"/projects/{project_id}")
            if isinstance(data, dict):
                # Handle nested response: {"project": {"name": ...}}
                proj = data.get("project", data)
                name = proj.get("name") if isinstance(proj, dict) else None
                if name and str(name).strip():
                    return str(name).strip()
        except Exception:
            pass
        return None

    async def _resolve_project_id(self, override: Optional[str] = None) -> str:
        """Resolve which project to target.

        Runs fresh on every tool call (no caching) to prevent stale routing
        when the user switches workspaces.

        Priority (workspace-specific signals first, global fallbacks last):
          1. Explicit override (from tool call ``project_id`` param)
          2. Pinned project (from CLI ``--project`` flag)
          3. .codrag/project.json pointer (workspace roots, CWD, CODRAG_WORKSPACE)
          4. Auto-register .codrag/ folders not yet in daemon
          5. Initialize roots (workspace URIs sent by the IDE)
          6. CWD auto-detect (process working directory)
          7. CODRAG_PROJECT env var (pin by name or ID)
          8. Single-project shortcut (only 1 project registered)
          9. Actionable error with project list
        """
        # 1. Tool-call override
        if override and override.strip():
            return override.strip()

        # 2. CLI pinned
        if self.project_id:
            return self.project_id

        # 3. Pointer check — instant routing via .codrag/project.json
        #    Checks: IDE workspace roots → CWD → CODRAG_WORKSPACE env var
        #    This works without the daemon, making it the fastest path.
        from codrag.core.project_registry import read_codrag_pointer

        cwd = str(Path.cwd().resolve())
        pointer_paths = list(self._initialize_roots)
        if cwd != "/" and cwd not in pointer_paths:
            pointer_paths.append(cwd)

        # CODRAG_WORKSPACE env var — guaranteed routing for IDEs that don't
        # send workspace roots in MCP initialize (e.g. Antigravity).
        # Set per-workspace in the MCP config's "env" block.
        env_workspace = os.environ.get("CODRAG_WORKSPACE", "").strip()
        if env_workspace and env_workspace not in pointer_paths:
            pointer_paths.append(env_workspace)

        for pp in pointer_paths:
            pointer = read_codrag_pointer(pp)
            if pointer and pointer.get("id"):
                pid = pointer["id"]
                logger.debug(
                    f"Resolved project from .codrag/project.json pointer: "
                    f"{pid} (path={pp})"
                )
                return pid

        # --- Steps 4-8 require the full project list from the daemon ---
        data = await self._api_get("/projects")
        all_projects: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            raw = data.get("projects")
            if isinstance(raw, list):
                all_projects = [p for p in raw if isinstance(p, dict)]

        # Filter to active/inactive only (frozen/locked excluded)
        projects = [
            p for p in all_projects
            if p.get("activity_status", "active") in ("active", "inactive")
        ]

        # 4. Auto-register workspace roots / CWD with .codrag/ folders
        #    that aren't yet in the daemon (zero-config).
        auto_paths = list(self._initialize_roots)
        if cwd != "/" and cwd not in auto_paths:
            auto_paths.append(cwd)
        if auto_paths:
            new_pid = await self._auto_register_codrag_folders(auto_paths, all_projects)
            if new_pid:
                return new_pid

        if not projects:
            raise ProjectNotFoundError(
                "No projects configured in CoDRAG daemon. "
                "Add one with: codrag add /path/to/your/repo"
            )

        def _project_lines() -> str:
            lines: List[str] = []
            for p in projects:
                pid = str(p.get("id") or "").strip()
                if not pid:
                    continue
                name = str(p.get("name") or "").strip() or "(unnamed)"
                path = str(p.get("path") or "").strip()
                lines.append(f"  - {pid}: {name} ({path})")
            return "\n".join(lines)

        # 5. Try initialize roots (workspace URIs from the IDE)
        if self._initialize_roots:
            pid = self._best_project_match(projects, self._initialize_roots)
            if pid:
                logger.debug(f"Resolved project from initialize roots: {pid}")
                return pid

        # 6. CWD auto-detect
        #    _best_project_match skips cwd="/" internally
        pid = self._best_project_match(projects, [cwd])
        if pid:
            logger.debug(f"Auto-detected project from CWD: {pid} cwd={cwd}")
            return pid

        # 7. CODRAG_PROJECT env var — pin by name or ID
        env_project = os.environ.get("CODRAG_PROJECT", "").strip()
        if env_project:
            for p in projects:
                if (
                    str(p.get("id", "")) == env_project
                    or str(p.get("name", "")).strip().lower() == env_project.lower()
                ):
                    pid = str(p["id"])
                    logger.debug(f"Resolved project from CODRAG_PROJECT env: {pid}")
                    return pid

        # 8. Single-project shortcut
        if len(projects) == 1 and projects[0].get("id"):
            pid = str(projects[0]["id"])
            logger.debug(f"Single project shortcut: {pid}")
            return pid

        # 9. No match — return actionable error with full project list
        msg = (
            "PROJECT_SELECTION_AMBIGUOUS: Could not automatically determine which project to use.\n"
            f"cwd: {cwd}\n"
        )
        if self._initialize_roots:
            msg += f"workspace roots: {self._initialize_roots}\n"
        msg += (
            "\nAvailable projects:\n"
            + _project_lines()
            + "\n\nACTION REQUIRED: You must explicitly specify which project to use. "
            "Look at the 'Available projects' list above, find the project whose path matches the codebase you are currently working in, "
            "and call THIS EXACT SAME tool again, but this time include the 'project_id' parameter with the correct ID."
        )
        raise ProjectSelectionAmbiguousError(msg)

    # -------------------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------------------

    async def tool_status(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Get index status."""
        project_id = await self._resolve_project_id(override=project_override)
        data = await self._api_get(f"/projects/{project_id}/status")

        # Lean output for token efficiency
        index = (data or {}).get("index", {}) if isinstance(data, dict) else {}
        result: Dict[str, Any] = {
            "project_id": project_id,
            "daemon": "running",
            "index_loaded": bool(index.get("exists", False)),
            "total_documents": int(index.get("total_chunks") or 0),
            "model": index.get("embedding_model", "unknown"),
            "built_at": index.get("last_build_at"),
            "building": bool(
                (data or {}).get("building", False) if isinstance(data, dict) else False
            ),
            "watch_enabled": bool(
                (
                    ((data or {}).get("watch") or {}).get("enabled", False)
                    if isinstance(data, dict)
                    else False
                )
            ),
        }

        # When no project_override was given, also list all projects so the AI
        # can see what's available (useful for multi-project setups).
        if not project_override and not self.project_id:
            try:
                pdata = await self._api_get("/projects")
                plist = []
                for p in (pdata or {}).get("projects", []) if isinstance(pdata, dict) else []:
                    if isinstance(p, dict) and p.get("id"):
                        plist.append(
                            {"id": p["id"], "name": p.get("name", ""), "path": p.get("path", "")}
                        )
                if len(plist) > 1:
                    result["available_projects"] = plist
            except Exception:
                pass  # Non-critical

        return result

    async def tool_build(
        self, full: bool = False, project_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger index build."""
        project_id = await self._resolve_project_id(override=project_override)
        path = f"/projects/{project_id}/build"
        if full:
            path = f"{path}?full=true"

        try:
            data = await self._api_post(path, {})
        except BuildInProgressError:
            return {"status": "already_building", "message": "A build is already in progress."}

        if isinstance(data, dict) and data.get("started"):
            return {
                "project_id": project_id,
                "status": "started",
                "message": "Index build started. Use codrag_status to check progress.",
            }
        return {"project_id": project_id, "status": "unknown", "data": data}

    async def tool_search(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 12000,
        trace_expand: bool = True,
        compression: str = "none",
        compression_level: str = "standard",
        compression_timeout_s: float = 30.0,
        exclude_paths: Optional[List[str]] = None,
        role: Optional[str] = None,  # Phase 67: agent scope filtering
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query-based context retrieval with trace expansion and routing."""
        if not query.strip():
            raise InvalidParamsError("query is required")

        try:
            k = int(k)
        except Exception:
            raise InvalidParamsError("k must be an integer")
        if k < 1:
            raise InvalidParamsError("k must be >= 1")
        if k > MAX_CONTEXT_K:
            raise InvalidParamsError(f"k too large (max {MAX_CONTEXT_K})")

        try:
            max_chars = int(max_chars)
        except Exception:
            raise InvalidParamsError("max_chars must be an integer")
        if max_chars < 1:
            raise InvalidParamsError("max_chars must be >= 1")
        if max_chars > MAX_CONTEXT_CHARS:
            raise InvalidParamsError(f"max_chars too large (max {MAX_CONTEXT_CHARS})")

        if compression not in ("none", "lingua", "auto"):
            raise InvalidParamsError("compression must be 'none', 'lingua', or 'auto'")
        if compression_level not in ("light", "standard", "aggressive"):
            raise InvalidParamsError(
                "compression_level must be 'light', 'standard', or 'aggressive'"
            )

        project_id = await self._resolve_project_id(override=project_override)
        # OPP-W3: Request augmented summaries alongside source content
        payload: Dict[str, Any] = {
            "query": query,
            "k": k,
            "max_chars": max_chars,
            "include_sources": True,
            "include_scores": True,  # Phase 73.1 Fix 4: expose relevance scores
            "structured": True,
            "trace_expand": bool(trace_expand),
            "context_tier": self._get_context_tier(),
        }
        if compression != "none":
            payload["compression"] = compression
            payload["compression_level"] = compression_level
            payload["compression_timeout_s"] = float(compression_timeout_s)
        if exclude_paths:
            payload["exclude_paths"] = list(exclude_paths)
        # Phase 67: Agent scope filtering
        if role:
            payload["role"] = role

        data = await self._api_post(f"/projects/{project_id}/context", payload)
        result = self._format_context_response(project_id, data)

        # Phase 50 Sprint 3: Markdown output for search results.
        context_str = result.get("context", "")

        # Phase 73.2: Per-subsystem deep dive from chunks (structured path)
        # or sources (non-structured path).
        subsystem_hint = ""
        if isinstance(data, dict):
            source_items = data.get("chunks", []) or data.get("sources", [])
            if isinstance(source_items, list) and source_items:
                # Detect dominant directory from source paths
                dir_counts: Dict[str, int] = {}
                for src in source_items:
                    if not isinstance(src, dict):
                        continue
                    path = src.get("source_path", "") or src.get("file_path", "")
                    if "/" in path:
                        top_dir = path.split("/")[0]
                        dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1
                if dir_counts:
                    top_dir, top_count = max(dir_counts.items(), key=lambda x: x[1])
                    # If >60% of results are in one directory, add subsystem hint
                    if top_count >= len(source_items) * 0.6 and top_count >= 2:
                        subsystem_hint = f"\n[Subsystem focus: {top_dir}/ -- {top_count}/{len(source_items)} results in this area]\n"

        if context_str:
            # Phase 73.2: Add retrieval confidence indicator
            # Structured path returns scores in chunks; non-structured in sources
            score_items = []
            if isinstance(data, dict):
                score_items = data.get("chunks", []) or data.get("sources", [])
            if score_items and isinstance(score_items, list):
                scores = [s.get("score", 0) for s in score_items
                          if isinstance(s, dict) and s.get("score")]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    confidence = "high" if avg_score > 0.7 else "medium" if avg_score > 0.4 else "low"
                    confidence_line = f"[retrieval confidence: {confidence} | top score: {max(scores):.2f} | {len(scores)} chunks]\n"
                    context_str = confidence_line + context_str

            # Phase 74: Concept augmentation — surface matching concepts
            concept_hint = ""
            try:
                concept_data = await self._api_post(
                    f"/projects/{project_id}/concepts/search",
                    {"query": query, "limit": 3},
                )
                if isinstance(concept_data, dict):
                    cdata = concept_data.get("data", concept_data)
                    concepts = cdata.get("concepts", [])
                    if concepts:
                        c_lines = ["[Related concepts:]"]
                        for c in concepts[:2]:  # Max 2 to limit token usage
                            title = c.get("title", "")
                            content = c.get("content", "")[:150]
                            category = c.get("category", "")
                            c_lines.append(f"  • {title} [{category}]: {content}")
                        concept_hint = "\n".join(c_lines) + "\n"
            except Exception:
                pass  # Non-critical

            prefix = concept_hint + subsystem_hint if concept_hint else subsystem_hint
            result["_to_markdown"] = prefix + context_str if prefix else context_str
        else:
            result["_to_markdown"] = f"No results found for: {query}"

        return result

    async def tool_context(
        self,
        max_chars: int = 0,  # 0 = use adaptive budget from OPP-W5
        role: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ambient context assembly — no query needed.

        Phase 50 ISSUE-3: If the index hasn't been built yet, returns a
        helpful onboarding response (isError=False) instead of an error.
        This prevents the AI from learning to avoid CoDRAG after a failed
        first attempt.
        """
        try:
            max_chars = int(max_chars)
        except Exception:
            raise InvalidParamsError("max_chars must be an integer")
        # OPP-W5: Adaptive budget -- use client-specific default when not specified
        if max_chars <= 0:
            max_chars = self._get_context_budget()
        if max_chars > MAX_CONTEXT_CHARS:
            raise InvalidParamsError(f"max_chars too large (max {MAX_CONTEXT_CHARS})")

        project_id = await self._resolve_project_id(override=project_override)

        # D1: Check atlas signal file for cross-process freshness detection.
        # If the pipeline wrote a new atlas since our last check, invalidate
        # the rules file cache (rules file was regenerated too) and notify
        # the host that cached resources are stale.
        await self._check_atlas_signal(project_id)

        # ISSUE-6 + Phase 73.4: Adaptive atlas inclusion with hash freshness.
        # If a CoDRAG rules file exists, the atlas is already in the AI's
        # system prompt (via alwaysApply/always_on). Skipping the atlas
        # prepend saves ~500-2500 chars of budget that goes to actual code
        # content instead. Without rules files, include the atlas so the AI
        # gets structural orientation from the tool response.
        #
        # Phase 73.4 enhancement: If the rules file has an atlas hash, we
        # compare it against the current atlas. Match = skip (atlas is fresh).
        # Mismatch = include (atlas is stale in the rules file).
        has_rules = self._project_has_rules_file(project_id)
        include_atlas = not has_rules
        atlas_fresh = False
        if has_rules:
            rules_hash = self._get_rules_atlas_hash(project_id)
            if rules_hash:
                # We have a hash — will compare after we get the current atlas.
                # For now, tentatively skip atlas; we'll override if stale.
                include_atlas = False
            # else: rules exist but no hash — use the old behavior (skip atlas)

        payload: Dict[str, Any] = {
            "query": "",
            "max_chars": max_chars,
            "include_atlas": include_atlas,
            "context_tier": self._get_context_tier(),
        }

        try:
            data = await self._api_post(f"/projects/{project_id}/context", payload)
        except IndexNotReadyError:
            # Phase 50 ISSUE-3: Graceful first-run response.
            setup_md = (
                "## CoDRAG (setup in progress)\n\n"
                "The codebase index hasn't been built yet. "
                "CoDRAG needs to scan your code before it can provide structural context.\n\n"
                "To build the index:\n"
                "1. Open the CoDRAG dashboard (http://localhost:8400)\n"
                "2. Click 'Rebuild Knowledge Base'\n"
                "-- OR run: codrag build\n\n"
                "Once built, call `codrag` again for module structure, hub files, "
                "and structural relationships.\n\n"
                "For now, work with the code directly using read_file and grep_search."
            )
            return {
                "project_id": project_id,
                "setup_in_progress": True,
                "_to_markdown": setup_md,
            }

        result = self._format_context_response(project_id, data)

        # Phase 73.4: Hash-based atlas freshness check.
        # If we skipped the atlas because rules file exists, verify via hash
        # that the rules file's atlas is still current. If stale, re-fetch
        # with atlas included so the agent gets fresh structural context.
        if has_rules and isinstance(data, dict):
            rules_hash = self._get_rules_atlas_hash(project_id)
            if rules_hash:
                import hashlib
                current_atlas = (data.get("atlas", {}) or {}).get("text", "")
                if current_atlas:
                    current_hash = hashlib.sha256(current_atlas.strip().encode()).hexdigest()[:12]
                    if current_hash == rules_hash:
                        atlas_fresh = True
                    else:
                        # Atlas is stale in rules file — re-fetch with atlas included
                        logger.debug(
                            "Atlas hash mismatch for %s: rules=%s current=%s — including fresh atlas",
                            project_id, rules_hash, current_hash,
                        )
                        payload["include_atlas"] = True
                        try:
                            data = await self._api_post(f"/projects/{project_id}/context", payload)
                            result = self._format_context_response(project_id, data)
                        except Exception:
                            pass  # Fall through with original response
                else:
                    # No atlas text in response — can't compare, assume fresh
                    atlas_fresh = True
            else:
                # No hash in rules file — fall back to old behavior (rules exist = skip)
                atlas_fresh = True

        result["atlas_fresh"] = atlas_fresh

        # Add ambient-specific metadata
        if isinstance(data, dict):
            for key in ("ambient", "hub_files", "modules_in_scope", "neighbor_files"):
                if key in data:
                    result[key] = data[key]

        # Phase 50 Sprint 3: Build markdown version for AI consumption.
        # The "context" field already contains formatted text blocks from
        # the backend (_assemble_ambient_context). We wrap it with a
        # header + health footer for better AI readability.
        context_str = result.get("context", "")
        hub_count = result.get("hub_files", 0)
        mod_count = result.get("modules_in_scope", 0)
        neighbor_count = result.get("neighbor_files", 0)
        chunks = result.get("chunks_used", 0)
        total_chars = result.get("total_chars", 0)

        md_parts: List[str] = []
        # Phase 73.2: Clean header — AI doesn't need chunk/char counts
        md_parts.append("## Project Structure")
        md_parts.append("")
        if context_str:
            md_parts.append(context_str)

        # Phase 64A: Role-based atlas projection
        if role:
            try:
                atlas_data = await self._api_get(
                    f"/projects/{project_id}/atlas?role={role}"
                )
                if isinstance(atlas_data, dict):
                    role_content = atlas_data.get("role_atlas", "")
                    role_content = self._truncate_section(role_content, 2000, "role atlas")
                    if role_content:
                        md_parts.append("\n---\n")
                        md_parts.append(role_content)
                        result["role"] = role
                        result["role_atlas_chars"] = len(role_content)
            except Exception as e:
                logger.debug("Role projection failed for role=%s: %s", role, e)

        # Phase 73.2: Architecture context (user-curated, budget-capped)
        # Only include when annotations exist — otherwise it's redundant
        # with the module list already in the ambient context.
        try:
            arch_data = await self._api_get(
                f"/projects/{project_id}/architecture/context"
            )
            if isinstance(arch_data, dict) and arch_data.get("exists"):
                arch_text = arch_data.get("text", "")
                # Phase 73.2: Halved budget from 3000→1500 to reduce redundancy
                arch_text = self._truncate_section(arch_text, 1500, "architecture")
                # Skip if it's just the header + empty module list
                if arch_text and len(arch_text.strip().splitlines()) > 3:
                    md_parts.append("\n---\n")
                    md_parts.append(arch_text)
        except Exception as e:
            logger.debug("Architecture context failed: %s", e)

        # Phase 74: Concepts summary (lightweight — just counts)
        try:
            concepts_data = await self._api_get(
                f"/projects/{project_id}/concepts/stats"
            )
            if isinstance(concepts_data, dict):
                cdata = concepts_data.get("data", concepts_data)
                total = cdata.get("total", 0)
                if total > 0:
                    active = cdata.get("active", 0)
                    seeds = cdata.get("seeds", 0)
                    pending_q = cdata.get("pending_questions", 0)
                    cats = cdata.get("by_category", {})
                    concept_line = f"\n[Concepts: {active} active, {seeds} seeds"
                    if cats:
                        # Show top 4 categories to keep ambient context concise
                        sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
                        top = sorted_cats[:4]
                        concept_line += f" — {', '.join(f'{k}: {v}' for k, v in top)}"
                        if len(sorted_cats) > 4:
                            concept_line += f", +{len(sorted_cats) - 4} more"
                    if pending_q:
                        concept_line += f" | {pending_q} questions pending"
                    concept_line += ". Use codrag_concepts to explore.]"
                    md_parts.append(concept_line)
                    result["concepts_total"] = total
                    result["concepts_active"] = active
        except Exception as e:
            logger.debug("Concepts context failed: %s", e)

        result["_to_markdown"] = "\n".join(md_parts)
        return result

    @staticmethod
    def _truncate_section(text: str, max_chars: int, label: str) -> str:
        """Truncate a response section to a hard character cap."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        last_nl = truncated.rfind("\n")
        if last_nl > max_chars // 2:
            truncated = truncated[:last_nl]
        return truncated + f"\n\n[{label}: truncated to {max_chars} chars]"

    @staticmethod
    def _format_context_response(project_id: str, data: Any) -> Dict[str, Any]:
        """Shared response formatting for context endpoints."""
        chunks = data.get("chunks") if isinstance(data, dict) else None
        chunks_used = len(chunks) if isinstance(chunks, list) else 0
        result: Dict[str, Any] = {
            "project_id": project_id,
            "context": (data or {}).get("context", "") if isinstance(data, dict) else "",
            "chunks_used": chunks_used,
            "total_chars": (data or {}).get("total_chars", 0) if isinstance(data, dict) else 0,
            "estimated_tokens": (data or {}).get("estimated_tokens", 0)
            if isinstance(data, dict)
            else 0,
        }
        comp_meta = (data or {}).get("compression") if isinstance(data, dict) else None
        if comp_meta:
            result["compression"] = comp_meta
        return result

    async def tool_trace_search(
        self,
        query: str,
        kind: Optional[str] = None,
        limit: int = 20,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search the trace index for symbols."""
        if not query.strip():
            raise InvalidParamsError("query is required")

        try:
            limit = int(limit)
        except Exception:
            raise InvalidParamsError("limit must be an integer")
        if limit < 1:
            raise InvalidParamsError("limit must be >= 1")
        if limit > 100:
            raise InvalidParamsError("limit too large (max 100)")

        project_id = await self._resolve_project_id(override=project_override)
        payload: Dict[str, Any] = {"query": query, "limit": limit}
        if kind:
            payload["kind"] = kind

        data = await self._api_post(f"/projects/{project_id}/trace/search", payload)

        nodes = (data or {}).get("nodes", []) if isinstance(data, dict) else []
        formatted = []
        for n in nodes:
            formatted.append(
                {
                    "id": n.get("id", ""),
                    "name": n.get("name", ""),
                    "kind": n.get("kind", ""),
                    "path": n.get("file_path", n.get("path", "")),
                    "line": n.get("start_line", n.get("line")),
                }
            )

        # Phase 50 Sprint 3: Markdown for symbol search results
        if formatted:
            md_lines = [f"## Symbol search: {query} ({len(formatted)} results)\n"]
            for n in formatted:
                line = f"- `{n['name']}` ({n['kind']}) @ `{n['path']}`"
                if n.get("line"):
                    line += f":{n['line']}"
                md_lines.append(line)
            md_text = "\n".join(md_lines)
        else:
            md_text = f"No symbols found matching: {query}"

        return {
            "project_id": project_id,
            "query": query,
            "count": len(formatted),
            "nodes": formatted,
            "_to_markdown": md_text,
        }

    async def tool_trace_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_kinds: Optional[List[str]] = None,
        max_nodes: int = 25,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get neighbors for a trace node."""
        if not node_id.strip():
            raise InvalidParamsError("node_id is required")

        if direction not in ("in", "out", "both"):
            raise InvalidParamsError("direction must be 'in', 'out', or 'both'")

        try:
            max_nodes = int(max_nodes)
        except Exception:
            raise InvalidParamsError("max_nodes must be an integer")
        if max_nodes < 1:
            raise InvalidParamsError("max_nodes must be >= 1")
        if max_nodes > 100:
            raise InvalidParamsError("max_nodes too large (max 100)")

        project_id = await self._resolve_project_id(override=project_override)

        # Build query params
        params = [f"direction={direction}", f"max_nodes={max_nodes}"]
        if edge_kinds:
            params.append(f"edge_kinds={','.join(edge_kinds)}")
        query_string = "&".join(params)

        data = await self._api_get(
            f"/projects/{project_id}/trace/neighbors/{node_id}?{query_string}"
        )

        # Format response
        center = (data or {}).get("center") if isinstance(data, dict) else None
        nodes = (data or {}).get("nodes", []) if isinstance(data, dict) else []
        edges = (data or {}).get("edges", []) if isinstance(data, dict) else []

        return {
            "project_id": project_id,
            "center": center,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes[:max_nodes],
            "edges": edges[:50],  # Cap edges for token efficiency
        }

    async def tool_trace_coverage(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Get trace coverage statistics."""
        project_id = await self._resolve_project_id(override=project_override)
        data = await self._api_get(f"/projects/{project_id}/trace/coverage")

        # Return lean summary for token efficiency
        return {
            "project_id": project_id,
            "traced_count": (data or {}).get("traced_count", 0) if isinstance(data, dict) else 0,
            "untraced_count": (data or {}).get("untraced_count", 0)
            if isinstance(data, dict)
            else 0,
            "stale_count": (data or {}).get("stale_count", 0) if isinstance(data, dict) else 0,
            "excluded_count": (data or {}).get("excluded_count", 0)
            if isinstance(data, dict)
            else 0,
            "total_nodes": (data or {}).get("total_nodes", 0) if isinstance(data, dict) else 0,
            "total_edges": (data or {}).get("total_edges", 0) if isinstance(data, dict) else 0,
            "building": bool((data or {}).get("building", False))
            if isinstance(data, dict)
            else False,
        }

    async def tool_impact(
        self,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None,
        max_hops: int = 2,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze what depends on a file or symbol — blast radius analysis."""
        if not file_path and not symbol:
            raise InvalidParamsError("Either file_path or symbol is required")

        project_id = await self._resolve_project_id(override=project_override)

        # Resolve node_id: symbol takes precedence, else convert file_path to file node ID
        if symbol:
            node_id = symbol
        else:
            node_id = f"file:{file_path}"

        try:
            max_hops = min(int(max_hops), 4)
        except Exception:
            max_hops = 2

        data = await self._api_get(
            f"/projects/{project_id}/trace/impact/{node_id}?max_hops={max_hops}&max_nodes=30"
        )

        if not isinstance(data, dict):
            return {"project_id": project_id, "error": "No impact data available"}

        target = data.get("target", {})
        dependents = data.get("dependents", [])

        # Format as human-readable summary for the LLM
        lines = []
        target_name = target.get("name", node_id)
        target_path = target.get("file_path", "")
        lines.append(f"Impact analysis for: {target_name} ({target_path})")
        lines.append(f"Total dependents found: {len(dependents)}")
        lines.append("")

        if dependents:
            d1 = [d for d in dependents if d.get("distance") == 1]
            d2 = [d for d in dependents if d.get("distance", 0) > 1]

            if d1:
                lines.append(f"Direct dependents ({len(d1)}):")
                for dep in d1:
                    sig = dep.get("signature", dep.get("name", "?"))
                    kind = dep.get("kind", "")
                    path = dep.get("path", "")
                    doc = dep.get("docstring", "")
                    entry = f"  {sig} ({path}) [{kind}]"
                    if doc:
                        entry += f" -- {doc}"
                    lines.append(entry)

            if d2:
                lines.append(f"\nTransitive dependents ({len(d2)}):")
                for dep in d2:
                    lines.append(f"  {dep.get('name', '?')} ({dep.get('path', '')})")
        else:
            lines.append("No dependents found — this node has no reverse dependencies.")

        summary = "\n".join(lines)
        return {
            "project_id": project_id,
            "summary": summary,
            "target": target,
            "dependents": dependents,
            "total_dependents": len(dependents),
            "_to_markdown": summary,
        }

    async def tool_save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None,
        category: str = "note",
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save an observation about the codebase for cross-session memory.

        OPP-4: Write-through -- after saving, also fetches a lightweight
        context refresh so the AI gets structural orientation alongside the
        confirmation. This makes saves feel 'free' and encourages usage.
        """
        project_id = await self._resolve_project_id(override=project_override)
        payload = {"content": content}
        if file_path:
            payload["file_path"] = file_path
        if symbol:
            payload["symbol"] = symbol
        if category:
            payload["category"] = category
        data = await self._api_post(f"/projects/{project_id}/observations", payload)
        obs_id = (data or {}).get("id", "unknown") if isinstance(data, dict) else "unknown"
        msg = f"Observation saved (id={obs_id}). It will persist across sessions and be flagged stale if the linked file changes."

        # OPP-4: Write-through -- append a lightweight context refresh.
        # Use a small budget (4000 chars) so the save response stays fast.
        context_snippet = ""
        try:
            has_rules = self._project_has_rules_file(project_id)
            ctx_data = await self._api_post(
                f"/projects/{project_id}/context",
                {
                    "query": "",
                    "max_chars": 4000,
                    "include_atlas": not has_rules,
                },
            )
            if isinstance(ctx_data, dict):
                context_snippet = ctx_data.get("context", "") or ""
        except Exception:
            pass  # Non-fatal -- save already succeeded

        md_parts = [msg]
        if context_snippet:
            md_parts.append("\n---\n## Updated Context\n")
            md_parts.append(context_snippet)

        return {
            "saved": True,
            "id": obs_id,
            "project_id": project_id,
            "message": msg,
            "_to_markdown": "\n".join(md_parts),
        }

    async def tool_get_observations(
        self,
        query: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 10,
        include_stale: bool = True,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve previous observations about the codebase."""
        project_id = await self._resolve_project_id(override=project_override)
        params = []
        if query:
            params.append(f"query={query}")
        if file_path:
            params.append(f"file_path={file_path}")
        params.append(f"limit={limit}")
        if not include_stale:
            params.append("include_stale=false")
        qs = "&".join(params)
        data = await self._api_get(f"/projects/{project_id}/observations?{qs}")

        observations = []
        if isinstance(data, dict):
            for obs in data.get("observations", []):
                entry = {
                    "content": obs.get("content", ""),
                    "category": obs.get("category", "note"),
                }
                if obs.get("file_path"):
                    entry["file_path"] = obs["file_path"]
                if obs.get("symbol_fqn"):
                    entry["symbol"] = obs["symbol_fqn"]
                if obs.get("stale"):
                    entry["stale"] = True
                    entry["stale_reason"] = obs.get("stale_reason", "file modified")
                observations.append(entry)

        # Phase 50: Markdown output for observations
        if observations:
            md_lines = [f"## Observations ({len(observations)})\n"]
            for obs in observations:
                stale_tag = " [STALE]" if obs.get("stale") else ""
                cat = obs.get("category", "note")
                fp = f" @ `{obs['file_path']}`" if obs.get("file_path") else ""
                md_lines.append(f"- **[{cat}]{stale_tag}**{fp}: {obs['content']}")
            obs_md = "\n".join(md_lines)
        else:
            obs_md = "No observations found."

        return {
            "project_id": project_id,
            "count": len(observations),
            "observations": observations,
            "_to_markdown": obs_md,
        }

    async def tool_concepts(
        self,
        action: str = "get",
        query: Optional[str] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        anchors: Optional[List[str]] = None,
        status: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get or save codebase concepts — high-level 'why' knowledge.

        Phase 74: Concepts are heavier than observations — they capture
        business rationale, design decisions, domain knowledge, and
        architectural intent that isn't obvious from the code.

        action='get' (default): List or search concepts.
        action='save': Create or update a concept.
        """
        project_id = await self._resolve_project_id(override=project_override)

        if action == "save":
            if not title or not content:
                raise InvalidParamsError(
                    "Both 'title' and 'content' are required when action='save'"
                )
            payload: Dict[str, Any] = {
                "title": title,
                "content": content,
                "category": category or "technical",
                "status": "active",  # AI-created concepts are active
            }
            if anchors:
                payload["anchors"] = anchors
            data = await self._api_post(
                f"/projects/{project_id}/concepts", payload
            )
            cid = (data or {}).get("id", "unknown") if isinstance(data, dict) else "unknown"
            msg = (
                f"Concept saved: \"{title}\" (id={cid}). "
                f"It will persist in the concept store and appear in ambient context."
            )
            return {
                "saved": True,
                "id": cid,
                "project_id": project_id,
                "message": msg,
                "_to_markdown": msg,
            }
        else:
            # Get/search concepts
            if query:
                data = await self._api_post(
                    f"/projects/{project_id}/concepts/search",
                    {"query": query, "limit": 10},
                )
            else:
                params = []
                if status:
                    params.append(f"status={status}")
                if category:
                    params.append(f"category={category}")
                qs = "&".join(params) if params else ""
                url = f"/projects/{project_id}/concepts"
                if qs:
                    url += f"?{qs}"
                data = await self._api_get(url)

            concepts = []
            if isinstance(data, dict):
                raw_concepts = data.get("concepts", [])
                for c in raw_concepts:
                    entry = {
                        "id": c.get("id", ""),
                        "title": c.get("title", ""),
                        "content": c.get("content", ""),
                        "category": c.get("category", ""),
                        "status": c.get("status", ""),
                    }
                    if c.get("anchors"):
                        entry["anchors"] = c["anchors"]
                    if c.get("stale"):
                        entry["stale"] = True
                    concepts.append(entry)

            # Cap results to avoid flooding agent context
            total_count = len(concepts)
            if total_count > 25:
                concepts = concepts[:25]

            # Markdown output
            if concepts:
                header = f"## Concepts ({len(concepts)}"
                if total_count > len(concepts):
                    header += f" of {total_count} — use query or category filter to narrow"
                header += ")\n"
                md_lines = [header]
                for c in concepts:
                    stale_tag = " [STALE]" if c.get("stale") else ""
                    status_tag = f" ({c['status']})" if c.get("status") == "seed" else ""
                    anchors_str = ""
                    if c.get("anchors"):
                        anchors_str = f" → {', '.join(c['anchors'][:3])}"
                    md_lines.append(
                        f"- **{c['title']}** [{c['category']}]{status_tag}{stale_tag}{anchors_str}\n"
                        f"  {c['content'][:200]}"
                    )
                concepts_md = "\n".join(md_lines)
            else:
                concepts_md = "No concepts found. Use the CoDRAG dashboard to initialize concepts, or save one with action='save'."

            return {
                "project_id": project_id,
                "count": len(concepts),
                "concepts": concepts,
                "_to_markdown": concepts_md,
            }

    async def tool_audit(
        self,
        synthesize: bool = False,
        category: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run or retrieve a codebase health audit."""
        project_id = await self._resolve_project_id(override=project_override)

        # Phase 73.1 Fix 3: Always run fresh audit — stale cached results
        # mislead agents (e.g., package-lock.json appearing as "critical"
        # after the analyzer was updated to ignore it).
        findings = []
        try:
            payload: Dict[str, Any] = {"synthesize": synthesize}
            if category:
                payload["categories"] = [category]
            await self._api_post(f"/projects/{project_id}/audit", payload)

            # Poll for completion (max 30s for Tier 1, should be <2s)
            import asyncio

            for _ in range(30):
                await asyncio.sleep(1)
                status = await self._api_get(f"/projects/{project_id}/audit/status")
                if isinstance(status, dict) and not status.get("running", True):
                    break

            data = await self._api_get(f"/projects/{project_id}/audit/findings")
            findings = data.get("findings", []) if isinstance(data, dict) else []
        except Exception as e:
            return {"project_id": project_id, "error": f"Audit failed: {e}"}

        # Format findings for token efficiency
        severity_counts = {}
        for f in findings:
            sev = f.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Return top findings with full detail
        top_findings = []
        for f in findings[:15]:
            entry: Dict[str, Any] = {
                "severity": f.get("severity"),
                "title": f.get("title"),
                "action": f.get("suggested_action"),
            }
            if f.get("file_paths"):
                entry["files"] = f["file_paths"][:3]
            top_findings.append(entry)

        result: Dict[str, Any] = {
            "project_id": project_id,
            "total_findings": len(findings),
            "severity_counts": severity_counts,
            "findings": top_findings,
        }

        # Check if reports are available
        try:
            reports_data = await self._api_get(f"/projects/{project_id}/audit/reports")
            reports = reports_data.get("reports", []) if isinstance(reports_data, dict) else []
            if reports:
                result["available_reports"] = [r.get("name") for r in reports]
        except Exception:
            pass

        # Phase 50: Markdown output for AI consumption
        md_lines = [f"## Audit Results ({len(findings)} findings)\n"]
        if severity_counts:
            sev_parts = [f"{k}: {v}" for k, v in sorted(severity_counts.items())]
            md_lines.append(f"Severity: {', '.join(sev_parts)}\n")
        for f in top_findings:
            sev = f.get("severity", "")
            title = f.get("title", "")
            action = f.get("action", "")
            files = ", ".join(f"`{fp}`" for fp in (f.get("files") or [])[:3])
            md_lines.append(f"- **[{sev}] {title}**")
            if files:
                md_lines.append(f"  Files: {files}")
            if action:
                md_lines.append(f"  Action: {action}")
        if result.get("available_reports"):
            md_lines.append(f"\nAvailable reports: {', '.join(result['available_reports'])}")
            md_lines.append("Use `codrag_audit action='report' report_name='...'` to retrieve.")
        result["_to_markdown"] = "\n".join(md_lines)

        return result

    async def tool_audit_refactor(
        self,
        finding_ids: List[str],
        instructions: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get selected audit findings with trace context for implementation."""
        if not finding_ids:
            raise InvalidParamsError("finding_ids is required and must not be empty")

        project_id = await self._resolve_project_id(override=project_override)

        # Get findings
        data = await self._api_get(f"/projects/{project_id}/audit/findings?limit=500")
        all_findings = data.get("findings", []) if isinstance(data, dict) else []

        # Filter to requested IDs
        id_set = set(finding_ids)
        selected = [f for f in all_findings if f.get("finding_id") in id_set]

        if not selected:
            return {
                "project_id": project_id,
                "error": f"No findings matched IDs: {finding_ids}. Run codrag_audit first.",
            }

        # Collect all affected file paths for context retrieval
        affected_files: List[str] = []
        for f in selected:
            affected_files.extend(f.get("file_paths", []))
        affected_files = list(dict.fromkeys(affected_files))[:20]  # dedupe, cap at 20

        lines = [
            "## Audit Findings to Address\n",
            "CRITICAL SYSTEM INSTRUCTIONS FOR AI:",
            "1. Focus strictly on resolving the findings listed below.",
            "2. If 'Relevant Code Context' is truncated (stops abruptly), focus on the first few findings, then use `codrag_search` to gather the rest.",
            "3. When you finish implementing these fixes, you MUST call `codrag_audit` with `action='verify'` and the relevant analyzers to verify your work before telling the user you are done.\n",
        ]
        for f in selected:
            fid = f.get("finding_id", "")
            title = f.get("title", "")
            priority = f.get("priority", "")
            severity = f.get("severity", "")
            effort = f.get("effort", "")
            desc = f.get("description", "")
            action = f.get("suggested_action", "")
            files = ", ".join(f.get("file_paths", [])[:5])

            lines.append(f"### {fid}: {title} [{priority} · {severity} · {effort}]")
            lines.append(f"**Files:** {files}")
            lines.append(f"**Problem:** {desc}")
            lines.append(f"**Action:** {action}")
            lines.append("")

        if instructions:
            lines.append(f"## User Instructions\n{instructions}\n")

        # Get trace context for affected files
        context_text = ""
        if affected_files:
            try:
                query = " ".join(affected_files[:5])
                ctx_data = await self._api_post(
                    f"/projects/{project_id}/context",
                    {
                        "query": query,
                        "k": 10,
                        "max_chars": 8000,
                        "include_sources": True,
                        "structured": False,
                        "trace_expand": True,
                    },
                )
                context_text = ctx_data.get("context", "") if isinstance(ctx_data, dict) else ""
            except Exception:
                pass

        if context_text:
            lines.append("---\n\n## Relevant Code Context\n")
            lines.append(context_text)

        content_md = "\n".join(lines)
        return {
            "project_id": project_id,
            "finding_count": len(selected),
            "finding_ids": [f.get("finding_id") for f in selected],
            "content": content_md,
            "affected_files": affected_files,
            "_to_markdown": content_md,
        }

    async def tool_audit_check(
        self,
        analyzers: List[str],
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Re-run specific analyzers to verify fixes."""
        if not analyzers:
            raise InvalidParamsError("analyzers is required and must not be empty")

        project_id = await self._resolve_project_id(override=project_override)

        # Trigger audit with category filter
        try:
            await self._api_post(
                f"/projects/{project_id}/audit",
                {
                    "synthesize": False,
                },
            )

            # Poll for completion
            import asyncio

            for _ in range(30):
                await asyncio.sleep(1)
                status = await self._api_get(f"/projects/{project_id}/audit/status")
                if isinstance(status, dict) and not status.get("running", True):
                    break

            # Get fresh findings
            data = await self._api_get(f"/projects/{project_id}/audit/findings?limit=500")
            all_findings = data.get("findings", []) if isinstance(data, dict) else []

            # Filter to requested analyzers
            analyzer_set = set(analyzers)
            matched = [f for f in all_findings if f.get("analyzer") in analyzer_set]

            if not matched:
                return {
                    "project_id": project_id,
                    "status": "clean",
                    "message": f"No findings from analyzers: {analyzers}. The issues appear to be resolved!",
                    "analyzers_checked": analyzers,
                    "finding_count": 0,
                }

            check_result: Dict[str, Any] = {
                "project_id": project_id,
                "status": "findings_remain",
                "analyzers_checked": analyzers,
                "finding_count": len(matched),
                "findings": [
                    {
                        "id": f.get("finding_id"),
                        "severity": f.get("severity"),
                        "title": f.get("title"),
                        "action": f.get("suggested_action"),
                    }
                    for f in matched[:15]
                ],
            }
            md = [f"## Verify: {len(matched)} finding(s) remain\n"]
            for f in matched[:15]:
                md.append(
                    f"- **[{f.get('severity', '')}] {f.get('title', '')}** -- {f.get('suggested_action', '')}"
                )
            check_result["_to_markdown"] = "\n".join(md)
            return check_result
        except Exception as e:
            return {"project_id": project_id, "error": f"Check failed: {e}"}

    async def tool_audit_report(
        self,
        report_name: str,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve a specific audit report document."""
        if not report_name or not report_name.strip():
            raise InvalidParamsError("report_name is required")

        project_id = await self._resolve_project_id(override=project_override)

        data = await self._api_get(f"/projects/{project_id}/audit/report/{report_name}")

        content = data.get("content", "") if isinstance(data, dict) else ""
        return {
            "project_id": project_id,
            "report": report_name,
            "content": content,
            "_to_markdown": content
            or f"(Report '{report_name}' not found. Run `codrag_audit action='scan' synthesize=true` first.)",
        }

    async def tool_advise(
        self,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return forward-looking design proposals (Advisor).

        Reads goalposts state and converts proposals to ActionItems.
        Returns approved milestones + open proposals as markdown.
        """
        from codrag.core.audit.action_item import goalpost_to_action_item

        project_id = await self._resolve_project_id(override=project_override)

        try:
            data = await self._api_get(f"/projects/{project_id}/goalposts")
        except Exception:
            return {
                "project_id": project_id,
                "status": "no_data",
                "_to_markdown": (
                    "No Advisor data available yet. "
                    "Open the dashboard Advisor panel and click 'Generate' "
                    "to get forward-looking design proposals."
                ),
            }

        proposals = data.get("proposals", []) if isinstance(data, dict) else []
        questions = data.get("questions", []) if isinstance(data, dict) else []

        # Convert to ActionItems
        items = [goalpost_to_action_item(p) for p in proposals]

        # Build markdown
        approved = [i for i in items if i.state == "approved"]
        proposed = [i for i in items if i.state == "proposed"]

        parts: list = []
        if approved:
            parts.append(f"## Approved Milestones ({len(approved)})\n")
            for a in approved:
                tasks_str = ""
                if a.tasks:
                    tasks_str = "\n".join(f"  - {t.description}" for t in a.tasks)
                    tasks_str = f"\n{tasks_str}"
                parts.append(
                    f"### ✅ {a.title}\n"
                    f"**{a.priority}** · {a.category} · {a.effort}\n\n"
                    f"{a.description}{tasks_str}\n"
                )

        if proposed:
            parts.append(f"## Open Proposals ({len(proposed)})\n")
            for p in proposed:
                files = ", ".join(p.affected_files[:5]) if p.affected_files else "—"
                parts.append(
                    f"### 💡 [{p.id}] {p.title}\n"
                    f"**{p.priority}** · {p.category} · {p.effort}\n\n"
                    f"{p.description}\n\n"
                    f"Files: {files}\n"
                )

        unanswered = [q for q in questions if not q.get("answer")]
        if unanswered:
            parts.append(f"## Open Questions ({len(unanswered)})\n")
            for q in unanswered:
                parts.append(f"- {q.get('question', '?')}\n")

        md = "\n".join(parts) if parts else "No proposals yet. Generate from the dashboard Advisor panel."

        return {
            "project_id": project_id,
            "approved_count": len(approved),
            "proposed_count": len(proposed),
            "items": [i.to_dict() for i in items],
            "_to_markdown": f"# Advisor — {project_id}\n\n{md}",
        }

    async def tool_roadmap(
        self,
        tier: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return roadmap state as structured markdown.

        Reads the roadmap REST API and formats tiers with nodes.
        Optional tier filter to show only one tier.
        """
        from codrag.core.audit.action_item import roadmap_node_to_action_item

        project_id = await self._resolve_project_id(override=project_override)

        try:
            data = await self._api_get(f"/projects/{project_id}/roadmap")
        except Exception:
            return {
                "project_id": project_id,
                "status": "no_data",
                "_to_markdown": (
                    "No Roadmap data available yet. "
                    "Open the dashboard Roadmap panel to get started."
                ),
            }

        nodes = data.get("nodes", []) if isinstance(data, dict) else []
        north_star = data.get("north_star") if isinstance(data, dict) else None
        app_ethos = data.get("app_ethos", "") if isinstance(data, dict) else ""

        # Group by tier
        tiers_order = ["completed", "active", "planned", "proposed"]
        by_tier: dict = {t: [] for t in tiers_order}
        for n in nodes:
            t = n.get("tier", "proposed")
            if tier and t != tier:
                continue
            by_tier.setdefault(t, []).append(n)

        # Build markdown
        parts: list = []

        if north_star:
            parts.append(
                f"> **🌟 North Star:** {north_star['title']} "
                f"({north_star['priority']})\n"
            )

        if app_ethos:
            parts.append(f"*App Ethos: {app_ethos[:200]}*\n")

        tier_emoji = {
            "completed": "✅",
            "active": "🔥",
            "planned": "📋",
            "proposed": "💡",
        }

        total = 0
        for t in tiers_order:
            t_nodes = by_tier.get(t, [])
            if not t_nodes:
                continue
            emoji = tier_emoji.get(t, "")
            parts.append(f"## {emoji} {t.title()} ({len(t_nodes)})\n")
            for n in sorted(t_nodes, key=lambda x: x.get("position", 0)):
                src = f" · {n.get('source', 'manual')}" if n.get("source") != "manual" else ""
                parts.append(
                    f"### [{n.get('id', '?')}] {n.get('title', 'Untitled')}\n"
                    f"**{n.get('priority', 'P2')}** · {n.get('category', 'feature')}{src}\n\n"
                    f"{n.get('description', '')}\n"
                )
                total += 1

        md = "\n".join(parts) if parts else "Roadmap is empty. Add nodes or generate proposals."

        return {
            "project_id": project_id,
            "total_nodes": total,
            "north_star": north_star,
            "_to_markdown": f"# Roadmap — {project_id}\n\n{md}",
        }

    async def tool_hi(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Project overview and context discovery tool.

        Delegates to mcp.tool_hi module (extracted Phase 50 audit).
        """
        from codrag.mcp.tool_hi import tool_hi as _tool_hi

        return await _tool_hi(self, project_override=project_override)

    # -------------------------------------------------------------------------
    # MCP Protocol Handlers
    # -------------------------------------------------------------------------

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request.

        Extracts workspace roots from the client so we can match them
        against registered CoDRAG projects for automatic routing.
        """
        self._initialize_roots = []

        # MCP spec: roots array in params
        roots = params.get("roots", [])
        if isinstance(roots, list):
            for root in roots:
                if isinstance(root, dict):
                    uri = root.get("uri", "")
                    path = self._uri_to_path(uri)
                    if path:
                        self._initialize_roots.append(path)
                elif isinstance(root, str):
                    path = self._uri_to_path(root)
                    if path:
                        self._initialize_roots.append(path)

        # LSP compat: rootUri (string)
        root_uri = params.get("rootUri") or params.get("rootPath", "")
        if root_uri:
            path = self._uri_to_path(str(root_uri))
            if path and path not in self._initialize_roots:
                self._initialize_roots.append(path)

        # LSP compat: workspaceFolders (array of {uri, name})
        workspace_folders = params.get("workspaceFolders", [])
        if isinstance(workspace_folders, list):
            for folder in workspace_folders:
                if isinstance(folder, dict):
                    uri = folder.get("uri", "")
                    path = self._uri_to_path(str(uri))
                    if path and path not in self._initialize_roots:
                        self._initialize_roots.append(path)

        if self._initialize_roots:
            logger.debug(f"Workspace roots from client: {self._initialize_roots}")

        # Phase 50 (OPP-3): Extract client identity for host-aware behavior
        client_info = params.get("clientInfo", {})
        if isinstance(client_info, dict):
            self._client_name = str(client_info.get("name", "unknown"))
            self._client_version = str(client_info.get("version", ""))
            # T1: Log at INFO so it appears in log files for empirical validation
            logger.info(
                "MCP client detected: name=%s version=%s", self._client_name, self._client_version
            )

        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": True},
                "prompts": {"listChanged": True},
            },
            "serverInfo": {
                "name": "codrag",
                "version": "2.0.0",
            },
            # Phase 50: MCP server instructions (spec 2025-06-18).
            # Gemini CLI, Claude Code, Qwen Code append this to system prompt.
            # Cursor/Windsurf may ignore it -- rules files cover those.
            "instructions": (
                "CoDRAG maps how your codebase is connected -- modules, dependencies, "
                "hub files, and architectural patterns. All tools are read-only. "
                "Call `codrag` at the start of every task for structural overview. "
                "Use `codrag_search` for code queries with dependency expansion. "
                "Use `codrag_impact` before changes to see what breaks. "
                "Use `codrag_audit` for codebase health findings. "
                "Categories: code structure, architecture, dependencies, navigation."
            ),
        }

    @staticmethod
    def _uri_to_path(uri: str) -> Optional[str]:
        """Convert a file:// URI or bare path to a filesystem path."""
        if not uri:
            return None
        if uri.startswith("file:///"):
            return uri[7:]  # file:///Users/... -> /Users/...
        if uri.startswith("file://"):
            return uri[7:]
        if uri.startswith("/"):
            return uri
        return None

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": TOOLS}

    # ── Phase 50 Sprint 4: MCP Resources ─────────────────────────────

    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request.

        Returns lightweight resource descriptors. Resources provide on-demand
        context the user can attach via @ mention (no tool call needed).
        """
        try:
            project_id = await self._resolve_project_id()
        except Exception:
            project_id = "default"

        return {
            "resources": [
                {
                    "uri": f"codrag://{project_id}/atlas",
                    "name": "Codebase Atlas",
                    "description": "Architectural overview: identity, stack, workspace map, cross-cutting concerns.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/structure",
                    "name": "Codebase Structure",
                    "description": "Hub files with connection counts and structural roles.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/modules",
                    "name": "Module Map",
                    "description": "Module list with file counts, dependencies, and summaries.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/audit",
                    "name": "Audit Findings",
                    "description": "Latest codebase health findings: architecture, quality, tech debt.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["user", "assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/concepts",
                    "name": "Concepts",
                    "description": "High-level codebase concepts: business rationale, design decisions, domain knowledge.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/focus",
                    "name": "Focus Areas",
                    "description": "User-selected focus areas with content excerpts.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["assistant"]},
                },
                {
                    "uri": f"codrag://{project_id}/health",
                    "name": "Index Health",
                    "description": "Index freshness, coverage, and build status.",
                    "mimeType": "text/markdown",
                    "annotations": {"audience": ["user", "assistant"]},
                },
            ]
        }

    async def handle_resources_templates_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/templates/list — parameterized resource templates."""
        try:
            project_id = await self._resolve_project_id()
        except Exception:
            project_id = "default"

        return {
            "resourceTemplates": [
                {
                    "uriTemplate": f"codrag://{project_id}/modules/{{name}}",
                    "name": "Module Detail",
                    "description": "Detailed view of a single module: files, dependencies, summary.",
                    "mimeType": "text/markdown",
                },
            ]
        }

    async def handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request.

        Reads a specific resource by URI. Each resource generator is
        lightweight (<50ms) -- reads pre-computed data from disk, no LLM.
        """
        uri = params.get("uri", "")
        if not uri:
            raise InvalidParamsError("uri is required")

        # Parse URI: codrag://{project_id}/{resource_type}
        if not uri.startswith("codrag://"):
            raise InvalidParamsError(f"Unknown resource URI scheme: {uri}")

        parts = uri[len("codrag://") :].split("/", 1)
        if len(parts) != 2:
            raise InvalidParamsError(f"Invalid resource URI: {uri}")

        project_id_from_uri, resource_path = parts

        # Resolve actual project (URI project_id is a hint, auto-detect if needed)
        try:
            project_id = await self._resolve_project_id(override=project_id_from_uri)
        except Exception:
            project_id = project_id_from_uri

        # Parse resource path — may be simple ("atlas") or templated ("modules/Pipeline")
        resource_parts = resource_path.split("/", 1)
        resource_type = resource_parts[0]
        resource_param = resource_parts[1] if len(resource_parts) > 1 else None

        content = ""
        try:
            if resource_type == "structure":
                content = await self._resource_structure(project_id)
            elif resource_type == "atlas":
                content = await self._resource_atlas(project_id)
            elif resource_type == "modules":
                if resource_param:
                    content = await self._resource_module_detail(project_id, resource_param)
                else:
                    content = await self._resource_modules(project_id)
            elif resource_type == "audit":
                content = await self._resource_audit(project_id)
            elif resource_type == "concepts":
                content = await self._resource_concepts(project_id)
            elif resource_type == "focus":
                content = await self._resource_focus(project_id)
            elif resource_type == "health":
                content = await self._resource_health(project_id)
            else:
                raise InvalidParamsError(f"Unknown resource type: {resource_type}")
        except InvalidParamsError:
            raise
        except Exception as e:
            logger.debug("Resource read failed for %s: %s", uri, e)
            content = f"(Resource unavailable: {e})"

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content,
                }
            ]
        }

    # ── Resource content generators ──────────────────────────────────

    async def _resource_structure(self, project_id: str) -> str:
        """Hub files + graph topology. Tier-adaptive hub count."""
        from codrag.core.context_tier import tier_from_budget

        data = await self._api_get(f"/projects/{project_id}/status")
        if not isinstance(data, dict):
            return "(No project data available)"

        index = data.get("index", {}) or {}
        trace = data.get("trace", {}) or {}
        parts: List[str] = []

        parts.append("## Codebase Structure\n")

        # Graph topology
        nodes = trace.get("total_nodes", 0)
        edges = trace.get("total_edges", 0)
        chunks = index.get("total_chunks", 0)
        if nodes or chunks:
            parts.append(f"Graph: {nodes} nodes, {edges} edges | Index: {chunks} chunks\n")

        # Hub files — tier-adaptive count
        tier = tier_from_budget(self._get_context_budget())
        hub_k = tier.hub_count
        try:
            hub_data = await self._api_get(f"/projects/{project_id}/trace/hub_files?k={hub_k}")
            hub_files = (hub_data or {}).get("hub_files", []) if isinstance(hub_data, dict) else []
            if hub_files:
                parts.append("### Hub Files (most connected)")
                for h in hub_files[:hub_k]:
                    if isinstance(h, dict) and h.get("path"):
                        parts.append(f"- `{h['path']}` ({h.get('in_degree', 0)} connections)")
                parts.append("")
        except Exception:
            pass

        if len(parts) <= 2:
            return "(Structure data not yet available -- build the index first)"

        parts.append("Call `codrag` for full module summaries and hub file content.")
        return "\n".join(parts)

    async def _resource_atlas(self, project_id: str) -> str:
        """Codebase atlas text. Tier-adaptive budget."""
        try:
            # Tier-adaptive: T1 gets 4K, T2 gets 3K, T2.5 gets 2K
            budget = min(4000, self._get_context_budget() // 10)
            budget = max(budget, 2000)  # floor at 2K
            ctx_data = await self._api_post(
                f"/projects/{project_id}/context",
                {
                    "query": "",
                    "max_chars": budget,
                    "include_atlas": True,
                },
            )
            if not isinstance(ctx_data, dict):
                return "(Atlas not available)"

            atlas_meta = ctx_data.get("atlas", {}) or {}
            context = ctx_data.get("context", "") or ""

            if atlas_meta.get("included") and context:
                return context[:budget]

            return "(Atlas not yet generated -- the pipeline will create it at Stage 9)"
        except IndexNotReadyError:
            return "(Index not built yet -- atlas will be available after the pipeline runs)"
        except Exception as e:
            return f"(Atlas unavailable: {e})"

    async def _resource_files(self, project_id: str) -> str:
        """Selected knowledge base files. ~300 tokens."""
        try:
            data = await self._api_get(f"/projects/{project_id}/included_paths")
            paths = (data or {}).get("included_paths", []) if isinstance(data, dict) else []

            if not paths:
                return "(No files selected in knowledge base)"

            parts = [f"## Selected Files ({len(paths)} paths)\n"]
            for p in paths[:20]:
                parts.append(f"- `{p}`")
            if len(paths) > 20:
                parts.append(f"- ... +{len(paths) - 20} more")
            parts.append("\nCall `codrag` for detailed content from these areas.")
            return "\n".join(parts)
        except Exception as e:
            return f"(File list unavailable: {e})"

    async def _resource_health(self, project_id: str) -> str:
        """Index health summary. ~100 tokens."""
        try:
            data = await self._api_get(f"/projects/{project_id}/status")
            if not isinstance(data, dict):
                return "(Health data unavailable)"

            index = data.get("index", {}) or {}
            trace = data.get("trace", {}) or {}
            watch = data.get("watch", {}) or {}
            building = data.get("building", False)
            stale = data.get("stale", False)
            stale_count = data.get("stale_count", 0)

            parts = ["## Index Health\n"]

            # Index status
            if index.get("exists"):
                built_at = index.get("last_build_at", "unknown")
                parts.append(
                    f"Index: loaded ({index.get('total_chunks', 0)} chunks, built {built_at})"
                )
            elif building:
                parts.append("Index: building...")
            else:
                parts.append("Index: not built")

            # Trace status
            nodes = trace.get("total_nodes", 0)
            if nodes:
                parts.append(f"Trace: {nodes} nodes, {trace.get('total_edges', 0)} edges")

            # Watch status
            if watch.get("enabled"):
                parts.append("Watch: active (auto-rebuild on file changes)")
            else:
                parts.append("Watch: inactive")

            # Staleness
            if stale:
                parts.append(f"Stale: {stale_count} file(s) changed since last build")

            return "\n".join(parts)
        except Exception as e:
            return f"(Health data unavailable: {e})"

    async def _resource_modules(self, project_id: str) -> str:
        """Module map with summaries."""
        try:
            ctx_data = await self._api_post(
                f"/projects/{project_id}/context",
                {"query": "", "max_chars": self._get_context_budget() // 2, "include_atlas": False},
            )
            if not isinstance(ctx_data, dict):
                return "(Module data not available)"

            modules = ctx_data.get("modules", [])
            if not modules:
                return "(No modules detected yet -- run the pipeline to Stage 7+)"

            parts = ["## Module Map\n"]
            for mod in modules:
                if isinstance(mod, dict):
                    name = mod.get("name", "unnamed")
                    count = mod.get("file_count", 0)
                    summary = mod.get("summary", "")
                    parts.append(f"- **{name}** ({count} files): {summary}")
            return "\n".join(parts)
        except Exception as e:
            return f"(Module map unavailable: {e})"

    async def _resource_module_detail(self, project_id: str, module_name: str) -> str:
        """Single module detail — files, dependencies, summary."""
        try:
            data = await self._api_get(f"/projects/{project_id}/modules")
            if not isinstance(data, dict):
                return f"(Module '{module_name}' not found)"

            modules = data.get("modules", [])
            # Find by name (case-insensitive partial match)
            match = None
            for mod in modules:
                if isinstance(mod, dict):
                    name = mod.get("name", "")
                    if name.lower() == module_name.lower() or module_name.lower() in name.lower():
                        match = mod
                        break

            if not match:
                available = [m.get("name", "") for m in modules if isinstance(m, dict)][:10]
                return f"(Module '{module_name}' not found. Available: {', '.join(available)})"

            parts = [f"## Module: {match.get('name', module_name)}\n"]
            if match.get("summary"):
                parts.append(match["summary"])
                parts.append("")
            if match.get("files"):
                parts.append(f"**Files ({len(match['files'])}):**")
                for f in match["files"][:30]:
                    parts.append(f"- `{f}`")
                if len(match["files"]) > 30:
                    parts.append(f"- ... +{len(match['files']) - 30} more")
            if match.get("dependencies"):
                parts.append(f"\n**Dependencies:** {', '.join(match['dependencies'][:10])}")
            return "\n".join(parts)
        except Exception as e:
            return f"(Module detail unavailable: {e})"

    async def _resource_audit(self, project_id: str) -> str:
        """Latest audit findings summary."""
        try:
            data = await self._api_get(f"/projects/{project_id}/audit/findings")
            if not isinstance(data, dict):
                return "(No audit data available -- run `codrag_audit` first)"

            findings = data.get("findings", [])
            if not findings:
                return "(No audit findings -- codebase looks healthy!)"

            parts = [f"## Audit Findings ({len(findings)} issues)\n"]
            for f in findings[:20]:
                if isinstance(f, dict):
                    severity = f.get("severity", "info")
                    title = f.get("title", "untitled")
                    fid = f.get("id", "")
                    parts.append(f"- [{severity.upper()}] {title} ({fid})")
            if len(findings) > 20:
                parts.append(f"- ... +{len(findings) - 20} more")
            return "\n".join(parts)
        except Exception as e:
            return f"(Audit data unavailable: {e})"

    async def _resource_concepts(self, project_id: str) -> str:
        """Epistemic knowledge layer summary."""
        try:
            data = await self._api_get(f"/projects/{project_id}/concepts")
            if not isinstance(data, dict):
                return "(No concepts available)"

            concepts = data.get("concepts", [])
            if not concepts:
                return "(No concepts saved yet -- use `codrag_concepts` to add them)"

            # Group by category
            by_cat: Dict[str, list] = {}
            for c in concepts:
                if isinstance(c, dict):
                    cat = c.get("category", "technical")
                    by_cat.setdefault(cat, []).append(c)

            parts = [f"## Codebase Concepts ({len(concepts)} total)\n"]
            for cat, items in sorted(by_cat.items()):
                parts.append(f"### {cat.title()} ({len(items)})")
                for item in items[:5]:
                    title = item.get("title", "untitled")
                    parts.append(f"- {title}")
                if len(items) > 5:
                    parts.append(f"- ... +{len(items) - 5} more")
                parts.append("")
            return "\n".join(parts)
        except Exception as e:
            return f"(Concepts unavailable: {e})"

    async def _resource_focus(self, project_id: str) -> str:
        """User's selected focus areas."""
        try:
            data = await self._api_get(f"/projects/{project_id}/included_paths")
            paths = (data or {}).get("included_paths", []) if isinstance(data, dict) else []

            if not paths:
                return "(No focus areas selected -- configure in dashboard or CLI)"

            parts = [f"## Focus Areas ({len(paths)} paths)\n"]
            for p in paths[:20]:
                parts.append(f"- `{p}`")
            if len(paths) > 20:
                parts.append(f"- ... +{len(paths) - 20} more")
            return "\n".join(parts)
        except Exception as e:
            return f"(Focus areas unavailable: {e})"

    # ── Phase 50 Sprint 5: MCP Prompts ─────────────────────────────

    _PROMPTS = [
        {
            "name": "codrag-onboard",
            "description": "Orient to this codebase — get structural overview, key modules, and hub files",
            "arguments": [],
        },
        {
            "name": "codrag-review",
            "description": "Review a file with structural awareness — blast radius, dependencies, and related code",
            "arguments": [
                {
                    "name": "file_path",
                    "description": "Path of the file to review",
                    "required": True,
                },
                {
                    "name": "scope",
                    "description": "Review scope: 'file' (default), 'module', or 'blast-radius'",
                    "required": False,
                },
            ],
        },
        {
            "name": "codrag-plan",
            "description": "Plan a change with impact analysis — understand what files are affected before editing",
            "arguments": [
                {
                    "name": "change",
                    "description": "Description of the change you want to make",
                    "required": True,
                },
            ],
        },
        {
            "name": "codrag-investigate",
            "description": "Deep-dive into a topic — search, trace expansion, and module context",
            "arguments": [
                {
                    "name": "query",
                    "description": "What you want to understand (e.g., 'authentication flow', 'how caching works')",
                    "required": True,
                },
            ],
        },
        {
            "name": "codrag-health",
            "description": "Check codebase health — audit findings, tech debt, and improvement recommendations",
            "arguments": [
                {
                    "name": "focus",
                    "description": "Optional focus area: 'debt', 'complexity', 'coverage', 'architecture'",
                    "required": False,
                },
            ],
        },
    ]

    async def handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {"prompts": self._PROMPTS}

    async def handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if name == "codrag-onboard":
            try:
                pid = await self._resolve_project_id()
            except Exception:
                pid = "default"
            return {
                "description": "Codebase orientation",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Orient me to this codebase using CoDRAG.\n\n"
                                    "I've attached the codebase atlas and module map as context. "
                                    "Use these plus CoDRAG tools to:\n\n"
                                    "1. Summarize the architecture: what are the main components and how do they connect?\n"
                                    "2. Identify the most important files (hub files) and explain their role.\n"
                                    "3. List the key entry points and data flow patterns.\n"
                                    "4. Note any areas that need attention (from audit findings if available)."
                                ),
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": f"codrag://{pid}/atlas",
                                    "mimeType": "text/markdown",
                                    "text": "",
                                },
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": f"codrag://{pid}/modules",
                                    "mimeType": "text/markdown",
                                    "text": "",
                                },
                            },
                        ],
                    }
                ],
            }

        elif name == "codrag-review":
            file_path = arguments.get("file_path", "the current file")
            scope = arguments.get("scope", "file")
            return {
                "description": "Structural code review",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Review `{file_path}` (scope: {scope}) using CoDRAG's structural understanding.\n\n"
                                "1. Call `codrag_impact` on the file to understand its dependencies and dependents.\n"
                                "2. Call `codrag_search` to find related code and patterns.\n"
                                "3. Check for bugs, style issues, missing error handling, and structural problems.\n"
                                "4. Consider how changes here would affect connected files.\n"
                                "5. Provide concrete improvement suggestions with file references."
                            ),
                        },
                    }
                ],
            }

        elif name == "codrag-plan":
            change = arguments.get("change", "the proposed change")
            return {
                "description": "Change planning with impact analysis",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Plan this change: {change}\n\n"
                                "1. Call `codrag` for structural overview of the codebase.\n"
                                "2. Call `codrag_impact` on files that will be modified to understand the blast radius.\n"
                                "3. Call `codrag_search` to find related code that may need updates.\n"
                                "4. Create a step-by-step implementation plan that accounts for all dependencies.\n"
                                "5. List all files that need changes, in the order they should be modified."
                            ),
                        },
                    }
                ],
            }

        elif name == "codrag-investigate":
            query = arguments.get("query", "this topic")
            return {
                "description": "Deep investigation with structural context",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Help me understand: {query}\n\n"
                                "1. Call `codrag_search` to find relevant code and documentation.\n"
                                "2. Call `codrag` for module structure around the relevant area.\n"
                                "3. Call `codrag_impact` on key files to trace the dependency graph.\n"
                                "4. Explain how the pieces connect — data flow, call chains, design patterns.\n"
                                "5. Summarize with a clear mental model I can use going forward."
                            ),
                        },
                    }
                ],
            }

        elif name == "codrag-health":
            focus = arguments.get("focus", "")
            focus_text = f" Focus on: {focus}." if focus else ""
            try:
                pid = await self._resolve_project_id()
            except Exception:
                pid = "default"
            return {
                "description": "Codebase health check",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Check the health of this codebase using CoDRAG.{focus_text}\n\n"
                                    "I've attached the latest audit findings. Use these plus CoDRAG tools to:\n\n"
                                    "1. Prioritize findings by impact: what's most likely to cause problems?\n"
                                    "2. Call `codrag` for structural context — hub files and module dependencies.\n"
                                    "3. For the top 3 findings, suggest concrete fixes with file references.\n"
                                    "4. Summarize the overall health: what's good, what needs work."
                                ),
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": f"codrag://{pid}/audit",
                                    "mimeType": "text/markdown",
                                    "text": "",
                                },
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": f"codrag://{pid}/health",
                                    "mimeType": "text/markdown",
                                    "text": "",
                                },
                            },
                        ],
                    }
                ],
            }

        else:
            raise MethodNotFoundError(f"Unknown prompt: {name}")

    # ── Argument auto-completion ────────────────────────────────────

    async def handle_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion/complete — auto-complete prompt arguments.

        Provides file path completions for prompt arguments like file_path
        and module name completions for resource templates.
        """
        ref = params.get("ref", {})
        ref_type = ref.get("type", "")  # "ref/prompt" or "ref/resource"
        argument = params.get("argument", {})
        arg_name = argument.get("name", "")
        arg_value = argument.get("value", "")

        completions: List[Dict[str, str]] = []

        try:
            project_id = await self._resolve_project_id()
        except Exception:
            return {"completion": {"values": [], "hasMore": False}}

        # File path completion (for codrag-review file_path argument)
        if arg_name == "file_path" and arg_value:
            try:
                data = await self._api_get(f"/projects/{project_id}/files")
                files = (data or {}).get("files", []) if isinstance(data, dict) else []
                # Filter by prefix match
                matches = [f for f in files if isinstance(f, str) and arg_value.lower() in f.lower()]
                completions = [{"value": f} for f in matches[:20]]
            except Exception:
                pass

        # Module name completion (for resource templates)
        elif arg_name == "name" and ref_type == "ref/resource":
            try:
                data = await self._api_get(f"/projects/{project_id}/modules")
                modules = (data or {}).get("modules", []) if isinstance(data, dict) else []
                for mod in modules:
                    if isinstance(mod, dict):
                        name = mod.get("name", "")
                        if name and (not arg_value or arg_value.lower() in name.lower()):
                            completions.append({"value": name})
                completions = completions[:20]
            except Exception:
                pass

        # Query completion (for codrag-investigate query argument)
        elif arg_name == "query" and arg_value:
            # Suggest from recent observations/concepts as query hints
            try:
                data = await self._api_get(f"/projects/{project_id}/concepts")
                concepts = (data or {}).get("concepts", []) if isinstance(data, dict) else []
                for c in concepts:
                    if isinstance(c, dict):
                        title = c.get("title", "")
                        if title and arg_value.lower() in title.lower():
                            completions.append({"value": title})
                completions = completions[:10]
            except Exception:
                pass

        return {"completion": {"values": completions, "hasMore": len(completions) >= 20}}

    # EA-B12: MCP rate limiting state
    _mcp_call_times: List[float] = []
    _MCP_RATE_LIMIT = 120  # max calls
    _MCP_RATE_WINDOW = 60.0  # per N seconds

    def _check_rate_limit(self) -> None:
        """EA-B12: Enforce rate limit on MCP tool calls (120 calls/60s)."""
        import time

        now = time.monotonic()
        # Prune old entries
        self._mcp_call_times = [t for t in self._mcp_call_times if now - t < self._MCP_RATE_WINDOW]
        if len(self._mcp_call_times) >= self._MCP_RATE_LIMIT:
            raise MCPError(
                -32000,
                f"Rate limit exceeded: {self._MCP_RATE_LIMIT} calls per {int(self._MCP_RATE_WINDOW)}s",
            )
        self._mcp_call_times.append(now)

    def _audit_mcp_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        """EA-B12: Record MCP tool call to audit log."""
        try:
            from codrag.core.audit_log import get_audit_log

            audit = get_audit_log()
            audit.record(
                event_type="mcp_tool_call",
                severity="info",
                message=f"MCP tool called: {tool_name}",
                metadata={"tool": tool_name, "args_keys": list(args.keys())},
            )
        except Exception:
            pass  # Audit logging is best-effort

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request.

        Phase 50: Consolidated dispatch with alias routing.
        New tool names (codrag, codrag_search, codrag_impact, codrag_audit,
        codrag_observe) are handled directly. Legacy tool names are
        transparently routed via TOOL_ALIASES with parameter transforms.
        """
        from codrag.mcp_tools import TOOL_ALIASES

        original_name = params.get("name", "")
        args = params.get("arguments", {})

        # EA-B12: Rate limit + audit log
        self._check_rate_limit()
        self._audit_mcp_call(original_name, args)

        # Phase 50: Resolve legacy aliases to new tool names.
        # Apply parameter transforms for consolidated tools.
        name = original_name
        if name in TOOL_ALIASES:
            resolved = TOOL_ALIASES[name]
            logger.debug("Alias dispatch: %s -> %s", name, resolved)

            # Parameter transforms for legacy -> consolidated routing
            if name == "codrag_trace_search":
                args.setdefault("type", "symbol")
                name = resolved
            elif name == "codrag_trace_neighbors":
                # Map neighbors params to impact params
                args.setdefault("direction", "all")
                if "node_id" in args:
                    args.setdefault("symbol", args.pop("node_id"))
                if "max_nodes" in args:
                    args.setdefault("max_hops", 1)
                name = resolved
            elif name == "codrag_audit_refactor":
                args.setdefault("action", "refactor")
                name = resolved
            elif name == "codrag_audit_check":
                args.setdefault("action", "verify")
                name = resolved
            elif name == "codrag_audit_report":
                args.setdefault("action", "report")
                name = resolved
            elif name == "codrag_save_observation":
                args.setdefault("action", "save")
                name = resolved
            elif name == "codrag_get_observations":
                args.setdefault("action", "get")
                name = resolved
            else:
                name = resolved

        project_override = args.get("project_id")

        try:
            # ── Primary tools (new consolidated set) ────────────────
            if name in ("codrag", "codrag_context", "codrag_"):
                result = await self.tool_context(
                    max_chars=args.get("max_chars", 0),  # 0 = adaptive budget (OPP-W5)
                    role=args.get("role"),  # Phase 64A: role-based atlas projection
                    project_override=project_override,
                )
                # Set AFTER tool_context so first-call orientation boost fires
                self._codrag_called = True

            elif name == "codrag_search":
                search_type = args.get("type", "context")
                if search_type == "symbol":
                    result = await self.tool_trace_search(
                        query=args.get("query", ""),
                        kind=args.get("kind"),
                        limit=args.get("limit", args.get("k", 20)),
                        project_override=project_override,
                    )
                else:
                    result = await self.tool_search(
                        query=args.get("query", ""),
                        k=args.get("k", 5),
                        max_chars=args.get("max_chars", 12000),
                        trace_expand=bool(args.get("trace_expand", True)),
                        compression=args.get("compression", "none"),
                        compression_level=args.get("compression_level", "standard"),
                        compression_timeout_s=args.get("compression_timeout_s", 30.0),
                        exclude_paths=args.get("exclude_paths") or None,
                        role=args.get("role"),  # Phase 67: agent scope filtering
                        project_override=project_override,
                    )
                # Phase 50 Sprint 3: Nudge if codrag hasn't been called yet
                if not self._codrag_called and isinstance(result, dict):
                    md = result.get("_to_markdown", "")
                    if md:
                        result["_to_markdown"] = (
                            md + "\n\n---\n[tip: Call `codrag` (no args) for structural "
                            "codebase overview -- modules, hub files, and architecture.]"
                        )

            elif name == "codrag_impact":
                if not args.get("file_path") and not args.get("symbol") and not args.get("node_id"):
                    raise InvalidParamsError("codrag_impact requires file_path or symbol")
                direction = args.get("direction", "dependents")
                if direction == "all":
                    # Full neighborhood -- use trace_neighbors backend
                    node_id = args.get("symbol") or args.get("node_id", "")
                    if not node_id and args.get("file_path"):
                        node_id = f"file:{args['file_path']}"
                    result = await self.tool_trace_neighbors(
                        node_id=node_id,
                        direction="both",
                        edge_kinds=args.get("edge_kinds"),
                        max_nodes=args.get("max_nodes", 25),
                        project_override=project_override,
                    )
                elif direction == "dependencies":
                    # What does X depend on? (outgoing edges)
                    node_id = args.get("symbol") or ""
                    if not node_id and args.get("file_path"):
                        node_id = f"file:{args['file_path']}"
                    result = await self.tool_trace_neighbors(
                        node_id=node_id,
                        direction="out",
                        edge_kinds=args.get("edge_kinds"),
                        max_nodes=args.get("max_nodes", 25),
                        project_override=project_override,
                    )
                else:
                    # Default: dependents (what breaks if I change X?)
                    result = await self.tool_impact(
                        file_path=args.get("file_path"),
                        symbol=args.get("symbol"),
                        max_hops=args.get("max_hops", 2),
                        project_override=project_override,
                    )
                # Phase 50: Nudge if codrag hasn't been called yet
                if not self._codrag_called and isinstance(result, dict):
                    md = result.get("_to_markdown", "")
                    if md:
                        result["_to_markdown"] = (
                            md + "\n\n---\n[tip: Call `codrag` (no args) for structural "
                            "codebase overview -- modules, hub files, and architecture.]"
                        )

            elif name == "codrag_audit":
                action = args.get("action", "scan")
                if action == "refactor":
                    result = await self.tool_audit_refactor(
                        finding_ids=args.get("finding_ids", []),
                        instructions=args.get("instructions"),
                        project_override=project_override,
                    )
                elif action == "verify":
                    result = await self.tool_audit_check(
                        analyzers=args.get("analyzers", []),
                        project_override=project_override,
                    )
                elif action == "report":
                    result = await self.tool_audit_report(
                        report_name=args.get("report_name", ""),
                        project_override=project_override,
                    )
                elif action == "advise":
                    result = await self.tool_advise(
                        project_override=project_override,
                    )
                elif action == "roadmap":
                    result = await self.tool_roadmap(
                        tier=args.get("tier"),
                        project_override=project_override,
                    )
                else:
                    # Default: scan
                    result = await self.tool_audit(
                        synthesize=bool(args.get("synthesize", False)),
                        category=args.get("category"),
                        project_override=project_override,
                    )
                # Phase 50: Nudge if codrag hasn't been called yet
                if not self._codrag_called and isinstance(result, dict):
                    md = result.get("_to_markdown", "")
                    if md:
                        result["_to_markdown"] = (
                            md + "\n\n---\n[tip: Call `codrag` (no args) for structural "
                            "codebase overview -- modules, hub files, and architecture.]"
                        )

            elif name == "codrag_observe":
                action = args.get("action", "get")
                if action == "save":
                    if not args.get("content", "").strip():
                        raise InvalidParamsError(
                            "codrag_observe action='save' requires non-empty content"
                        )
                    result = await self.tool_save_observation(
                        content=args.get("content", ""),
                        file_path=args.get("file_path"),
                        symbol=args.get("symbol"),
                        category=args.get("category", "note"),
                        project_override=project_override,
                    )
                else:
                    # Default: get
                    result = await self.tool_get_observations(
                        query=args.get("query"),
                        file_path=args.get("file_path"),
                        limit=args.get("limit", 10),
                        include_stale=args.get("include_stale", True),
                        project_override=project_override,
                    )

            # Phase 74: Concepts tool
            elif name == "codrag_concepts":
                result = await self.tool_concepts(
                    action=args.get("action", "get"),
                    query=args.get("query"),
                    title=args.get("title"),
                    content=args.get("content"),
                    category=args.get("category"),
                    anchors=args.get("anchors"),
                    status=args.get("status"),
                    project_override=project_override,
                )

            # ── Hidden admin tool (not listed, but dispatches) ──────
            elif name == "codrag_build":
                result = await self.tool_build(
                    full=args.get("full", False),
                    project_override=project_override,
                )

            else:
                raise MethodNotFoundError(f"Unknown tool: {original_name}")

            # Phase 55: Inject resolved project metadata into every response.
            # This helps LLMs detect misrouted requests (e.g. DebateHaus
            # workspace getting HomeColab data).
            resolved_pid = project_override
            if not resolved_pid:
                try:
                    resolved_pid = await self._resolve_project_id()
                except Exception:
                    resolved_pid = None

            project_label = ""
            if resolved_pid:
                pname = await self._get_project_name(resolved_pid)
                if pname and pname != resolved_pid:
                    project_label = f"[project: {pname}]"
                else:
                    project_label = f"[project: {resolved_pid[:8]}…]"

            if isinstance(result, dict) and "_to_markdown" in result:
                text = result.pop("_to_markdown")
                if project_label:
                    text = f"{project_label}\n{text}"
            else:
                if isinstance(result, dict) and resolved_pid:
                    result["_project"] = resolved_pid
                text = json.dumps(result, indent=2)

            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }

        except (DaemonUnavailableError, DaemonError, InvalidParamsError) as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        # Notifications (no id) don't get responses
        if req_id is None:
            if method == "notifications/initialized":
                pass  # Client confirmed initialization
            return None

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            elif method == "resources/list":
                result = await self.handle_resources_list(params)
            elif method == "resources/templates/list":
                result = await self.handle_resources_templates_list(params)
            elif method == "resources/read":
                result = await self.handle_resources_read(params)
            elif method == "prompts/list":
                result = await self.handle_prompts_list(params)
            elif method == "prompts/get":
                result = await self.handle_prompts_get(params)
            elif method == "completion/complete":
                result = await self.handle_completion(params)
            elif method == "ping":
                result = {}
            else:
                raise MethodNotFoundError(f"Unknown method: {method}")

            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "result": result,
            }

        except MCPError as e:
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": e.code, "message": str(e)},
            }
        except Exception as e:
            logger.exception("Internal error handling request")
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": INTERNAL_ERROR, "message": str(e)},
            }


# =============================================================================
# Errors
# =============================================================================
