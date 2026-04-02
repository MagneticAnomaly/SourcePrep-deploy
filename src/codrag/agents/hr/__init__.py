"""Staffing Agent Engine — generates and manages AI agent role definitions."""

from codrag.agents.hr.engine import StaffingEngine
from codrag.agents.hr.readiness import ReadinessReport, compute_readiness
from codrag.agents.hr.roster import Roster

__all__ = [
    "StaffingEngine",
    "ReadinessReport",
    "compute_readiness",
    "Roster",
]
