"""
A2A (Agent-to-Agent) Protocol Handler for CoDRAG — Phase 63.

Implements a JSON-RPC 2.0 handler per the A2A specification
(Google/Linux Foundation). Maps A2A task requests to CoDRAG's
existing pipeline functions.

Protocol: https://a2a-protocol.org
Transport: HTTPS + JSON-RPC 2.0 + SSE for streaming
Discovery: Agent Card at /.well-known/agent.json

Task lifecycle:
    submitted → working → completed | failed | input-required

This handler is mounted at /a2a on CoDRAG's existing HTTP server.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Agent Card loader ───────────────────────────────────────────────

_AGENT_CARD_PATH = Path(__file__).parent / "agent_card.json"


def load_agent_card() -> Dict[str, Any]:
    """Load the static Agent Card from disk."""
    with open(_AGENT_CARD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Task state management ──────────────────────────────────────────

class TaskState:
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    INPUT_REQUIRED = "input-required"
    CANCELED = "canceled"


class A2ATask:
    """Represents an in-flight A2A task."""

    def __init__(self, task_id: str, skill_id: str, input_text: str) -> None:
        self.id = task_id
        self.skill_id = skill_id
        self.input_text = input_text
        self.state = TaskState.SUBMITTED
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.artifacts: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.history: List[Dict[str, Any]] = []

        self._record_transition(TaskState.SUBMITTED)

    def transition(self, new_state: str) -> None:
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self._record_transition(new_state)

    def add_artifact(self, mime_type: str, content: str) -> None:
        self.artifacts.append({
            "parts": [{"type": mime_type, "text": content}],
        })

    def fail(self, error: str) -> None:
        self.error = error
        self.transition(TaskState.FAILED)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "status": {
                "state": self.state,
                "timestamp": self.updated_at,
            },
        }
        if self.artifacts:
            result["artifacts"] = self.artifacts
        if self.error:
            result["status"]["message"] = {"text": self.error}
        if self.history:
            result["status"]["history"] = self.history
        return result

    def _record_transition(self, state: str) -> None:
        self.history.append({
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ── A2A Handler ─────────────────────────────────────────────────────

class A2AHandler:
    """Handles A2A protocol JSON-RPC 2.0 task requests.

    Maps A2A skill IDs to CoDRAG pipeline functions:
        codebase-context      → context assembly (search)
        opportunity-discovery → OpportunityManager.refresh + export
        impact-analysis       → dependency/dependent analysis
        structural-overview   → module structure + hub files

    Usage (in Flask):
        handler = A2AHandler(project_registry)
        @app.route('/a2a', methods=['POST'])
        def a2a_endpoint():
            return handler.handle(request.get_json())
    """

    SUPPORTED_METHODS = {
        "tasks/send",
        "tasks/get",
        "tasks/cancel",
    }

    def __init__(
        self,
        get_index_dir: Callable[[Optional[str]], Path],
        get_project_root: Callable[[Optional[str]], Optional[Path]],
    ) -> None:
        """Initialize the A2A handler.

        Args:
            get_index_dir: Callable that returns the index directory for a project.
            get_project_root: Callable that returns the project root for a project.
        """
        self._get_index_dir = get_index_dir
        self._get_project_root = get_project_root
        self._tasks: Dict[str, A2ATask] = {}

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC 2.0 request.

        Returns a JSON-RPC 2.0 response dict.
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method not in self.SUPPORTED_METHODS:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

        try:
            if method == "tasks/send":
                result = self._handle_send(params)
            elif method == "tasks/get":
                result = self._handle_get(params)
            elif method == "tasks/cancel":
                result = self._handle_cancel(params)
            else:
                return self._error_response(req_id, -32601, f"Unknown method: {method}")

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
        except Exception as e:
            logger.exception("A2A handler error for method %s", method)
            return self._error_response(req_id, -32000, str(e))

    # ── Method handlers ─────────────────────────────────────────

    def _handle_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/send — create and immediately execute a task."""
        task_id = params.get("id") or str(uuid.uuid4())
        message = params.get("message", {})
        skill_id = self._extract_skill_id(message)
        input_text = self._extract_input_text(message)
        project_id = params.get("metadata", {}).get("project_id")

        task = A2ATask(task_id, skill_id, input_text)
        self._tasks[task_id] = task

        # Execute synchronously (tasks are fast)
        task.transition(TaskState.WORKING)

        try:
            self._execute_skill(task, project_id)
            task.transition(TaskState.COMPLETED)
        except Exception as e:
            task.fail(str(e))

        return task.to_dict()

    def _handle_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/get — retrieve task status."""
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        return task.to_dict()

    def _handle_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/cancel — cancel a running task."""
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.transition(TaskState.CANCELED)
        return task.to_dict()

    # ── Skill execution ─────────────────────────────────────────

    def _execute_skill(self, task: A2ATask, project_id: Optional[str]) -> None:
        """Route task to the appropriate CoDRAG pipeline function."""
        index_dir = self._get_index_dir(project_id)
        project_root = self._get_project_root(project_id)

        handlers = {
            "codebase-context": self._skill_context,
            "opportunity-discovery": self._skill_opportunities,
            "impact-analysis": self._skill_impact,
            "structural-overview": self._skill_overview,
        }

        handler = handlers.get(task.skill_id)
        if not handler:
            raise ValueError(
                f"Unknown skill: {task.skill_id}. "
                f"Available: {', '.join(handlers.keys())}"
            )

        handler(task, index_dir, project_root)

    def _skill_context(
        self, task: A2ATask, index_dir: Path, project_root: Optional[Path]
    ) -> None:
        """Assemble codebase context for a query.

        Maps to codrag_search internally.
        """
        try:
            from codrag.mcp_server import _handle_codrag_search

            result = _handle_codrag_search(
                query=task.input_text,
                project_id=None,
                search_type="context",
                max_chars=12000,
            )
            task.add_artifact("text/plain", result)
        except ImportError:
            # Fallback: return a basic message
            task.add_artifact(
                "text/plain",
                f"Context assembly requested for: {task.input_text}\n"
                f"(MCP server not available for direct invocation)"
            )

    def _skill_opportunities(
        self, task: A2ATask, index_dir: Path, project_root: Optional[Path]
    ) -> None:
        """Discover opportunities using the OpportunityManager.

        Maps to OpportunityManager.refresh + export.
        """
        from codrag.core.audit.opportunity_manager import OpportunityManager

        mgr = OpportunityManager(index_dir)

        # Determine output format from input text
        if "sarif" in task.input_text.lower():
            fmt = "sarif"
            mime = "application/json"
        elif "csv" in task.input_text.lower():
            fmt = "csv"
            mime = "text/csv"
        elif "json" in task.input_text.lower():
            fmt = "json"
            mime = "application/json"
        else:
            fmt = "md"
            mime = "text/markdown"

        # Try to refresh from scanners (may fail if no graph data)
        try:
            mgr.refresh(project_root=project_root)
        except Exception as e:
            logger.warning("Opportunity refresh partial failure: %s", e)

        content = mgr.export(fmt)
        task.add_artifact(mime, content)

        # Also add summary as text
        summary = mgr.get_summary()
        task.add_artifact(
            "text/plain",
            f"Found {summary['total']} opportunities: "
            f"{summary['critical']} critical, "
            f"{summary['warning']} warning, "
            f"{summary['info']} info."
        )

    def _skill_impact(
        self, task: A2ATask, index_dir: Path, project_root: Optional[Path]
    ) -> None:
        """Analyze impact/dependencies of a file.

        Maps to codrag_impact internally.
        """
        try:
            from codrag.mcp_server import _handle_codrag_impact

            result = _handle_codrag_impact(
                file_path=task.input_text.strip(),
                direction="all",
                max_hops=2,
                project_id=None,
            )
            task.add_artifact("text/plain", result)
        except ImportError:
            task.add_artifact(
                "text/plain",
                f"Impact analysis requested for: {task.input_text}\n"
                f"(MCP server not available for direct invocation)"
            )

    def _skill_overview(
        self, task: A2ATask, index_dir: Path, project_root: Optional[Path]
    ) -> None:
        """Return structural overview.

        Maps to codrag (base overview) internally.
        """
        try:
            from codrag.mcp_server import _handle_codrag

            result = _handle_codrag(project_id=None)
            task.add_artifact("text/plain", result)
        except ImportError:
            task.add_artifact(
                "text/plain",
                f"Structural overview requested\n"
                f"(MCP server not available for direct invocation)"
            )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_skill_id(message: Dict[str, Any]) -> str:
        """Extract the target skill ID from an A2A message."""
        # Check metadata.skill_id first
        metadata = message.get("metadata", {})
        if "skill_id" in metadata:
            return metadata["skill_id"]

        # Fall back to inferring from the message role/content
        parts = message.get("parts", [])
        for part in parts:
            if isinstance(part, dict) and "metadata" in part:
                if "skill_id" in part["metadata"]:
                    return part["metadata"]["skill_id"]

        # Default to structural overview
        return "structural-overview"

    @staticmethod
    def _extract_input_text(message: Dict[str, Any]) -> str:
        """Extract the input text from an A2A message."""
        parts = message.get("parts", [])
        texts = []
        for part in parts:
            if isinstance(part, dict):
                if "text" in part:
                    texts.append(part["text"])
            elif isinstance(part, str):
                texts.append(part)
        return " ".join(texts) if texts else ""

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Build a JSON-RPC 2.0 error response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
