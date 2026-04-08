"""Codebase immune system — antibodies derived from concepts.

Antibodies are (trigger, response) pairs that detect architectural violations.
They are derived from constraint/architecture concepts and fire when code
changes match their trigger patterns. All alerts are informational — nothing
is blocked.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TriggerType(Enum):
    IMPORT_ADDED = "import_added"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    PATTERN_MATCH = "pattern_match"
    COUPLING_THRESHOLD = "coupling_threshold"


class ResponseType(Enum):
    AMBIENT_INJECT = "ambient_inject"
    AUDIT_FINDING = "audit_finding"
    OBSERVATION_AUTO = "observation_auto"


class Severity(Enum):
    INFORM = "inform"
    WARN = "warn"
    REVIEW = "review"


@dataclass
class Trigger:
    type: TriggerType
    target: str          # File path, directory, or glob pattern
    pattern: str = ""    # Regex pattern for IMPORT_ADDED, PATTERN_MATCH
    max_dependents: int = 0  # For COUPLING_THRESHOLD

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type.value, "target": self.target}
        if self.pattern:
            d["pattern"] = self.pattern
        if self.max_dependents:
            d["max_dependents"] = self.max_dependents
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Trigger":
        return Trigger(
            type=TriggerType(d["type"]),
            target=d.get("target", ""),
            pattern=d.get("pattern", ""),
            max_dependents=d.get("max_dependents", 0),
        )


@dataclass
class Response:
    type: ResponseType
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type.value, "message": self.message}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Response":
        return Response(
            type=ResponseType(d["type"]),
            message=d.get("message", ""),
        )


@dataclass
class Antibody:
    id: str
    name: str
    source_concept_id: str
    trigger: Trigger
    response: Response
    severity: Severity = Severity.WARN
    status: str = "testing"  # testing | active | disabled
    created_at: float = field(default_factory=time.time)
    last_triggered: Optional[float] = None
    trigger_count: int = 0
    dismiss_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_concept_id": self.source_concept_id,
            "trigger": self.trigger.to_dict(),
            "response": self.response.to_dict(),
            "severity": self.severity.value,
            "status": self.status,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
            "dismiss_count": self.dismiss_count,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Antibody":
        return Antibody(
            id=d["id"],
            name=d.get("name", ""),
            source_concept_id=d.get("source_concept_id", ""),
            trigger=Trigger.from_dict(d.get("trigger", {})),
            response=Response.from_dict(d.get("response", {})),
            severity=Severity(d.get("severity", "warn")),
            status=d.get("status", "testing"),
            created_at=d.get("created_at", 0),
            last_triggered=d.get("last_triggered"),
            trigger_count=d.get("trigger_count", 0),
            dismiss_count=d.get("dismiss_count", 0),
        )


def evaluate_trigger(trigger: Trigger, file_path: str, file_content: str = "") -> bool:
    """Evaluate whether a file change matches an antibody trigger.

    Args:
        trigger: The trigger to evaluate
        file_path: Path of the changed file
        file_content: Content of the changed file (for PATTERN_MATCH, IMPORT_ADDED)

    Returns:
        True if the trigger fires.
    """
    # Check if file matches the trigger target (exact, prefix, or glob)
    if not _path_matches(file_path, trigger.target):
        return False

    if trigger.type == TriggerType.FILE_MODIFIED:
        return True  # Any change to a matching file

    if trigger.type == TriggerType.FILE_CREATED:
        return True  # File existence in matching path

    if trigger.type == TriggerType.IMPORT_ADDED:
        if not trigger.pattern or not file_content:
            return False
        # Check if any import line matches the pattern
        for line in file_content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if re.search(trigger.pattern, stripped):
                    return True
        return False

    if trigger.type == TriggerType.PATTERN_MATCH:
        if not trigger.pattern or not file_content:
            return False
        return bool(re.search(trigger.pattern, file_content))

    return False


def _path_matches(file_path: str, target: str) -> bool:
    """Check if a file path matches a trigger target (exact, prefix, or glob)."""
    if file_path == target:
        return True
    # Directory prefix match
    if target.endswith("/") and file_path.startswith(target):
        return True
    # Glob-style: target ends with * or **
    if "*" in target:
        import fnmatch
        return fnmatch.fnmatch(file_path, target)
    # Prefix match for directory-like targets without trailing slash
    if "/" in target and "." not in target.split("/")[-1]:
        return file_path.startswith(target + "/") or file_path.startswith(target)
    return False
