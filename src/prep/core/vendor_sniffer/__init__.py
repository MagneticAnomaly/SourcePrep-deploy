"""
Vendor-dir sniffer subsystem.

Detects vendored / dependency / build-output directories at the project root
so the Initialize flow can auto-exclude obvious cases (Tier 1) and propose
ambiguous ones via a confirmation modal (Tier 2). Public symbols below are
re-exported from sub-modules (``models``, ``scanner``, ``signals``,
``manifests``) which are added incrementally across the implementation plan.
"""
from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult

__all__ = ["VendorCandidate", "VendorScanResult"]
