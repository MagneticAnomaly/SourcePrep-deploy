"""Digital Custodian Engine — detects dead code, archives safely, cleans up codebases."""

from prep.agents.custodian.engine import CustodianEngine
from prep.agents.custodian.manifest import ArchiveManifest, ManifestEntry

__all__ = [
    "CustodianEngine",
    "ArchiveManifest",
    "ManifestEntry",
]
