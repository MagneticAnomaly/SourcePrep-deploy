"""Staffing Agent Engine — generates and manages AI agent role definitions."""

from prep.agents.hr.engine import StaffingEngine
from prep.agents.hr.readiness import ReadinessReport, compute_readiness
from prep.agents.hr.roster import Roster

__all__ = [
    "StaffingEngine",
    "ReadinessReport",
    "compute_readiness",
    "Roster",
]
