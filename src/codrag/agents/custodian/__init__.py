"""Digital Custodian Engine — detects dead code, archives safely, cleans up codebases."""

from codrag.agents.custodian.engine import CustodianEngine
from codrag.agents.custodian.manifest import ArchiveManifest, ManifestEntry

__all__ = [
    "CustodianEngine",
    "ArchiveManifest",
    "ManifestEntry",
]
