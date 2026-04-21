"""
AutoAudit analyzers for Prep (Phase 43).

Each analyzer is a callable that takes an AuditContext and returns
a list of Finding objects. Analyzers are pure — no side effects,
no LLM calls, no disk writes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..models import AuditContext, Finding


class BaseAnalyzer(ABC):
    """Abstract base for all audit analyzers."""

    name: str = "base"
    category: str = "quality"

    @abstractmethod
    def analyze(self, ctx: AuditContext) -> List[Finding]:
        ...
