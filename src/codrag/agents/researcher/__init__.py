"""Researcher Agent Engine — mines audit findings, researches solutions, formulates plans."""

from codrag.agents.researcher.engine import ResearcherEngine
from codrag.agents.researcher.history import ResearchHistory

__all__ = [
    "ResearcherEngine",
    "ResearchHistory",
]
