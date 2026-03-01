"""Hub bottleneck analyzer — flags files with disproportionate fan-in."""
from __future__ import annotations

import statistics
from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class HubBottleneckAnalyzer(BaseAnalyzer):
    name = "hub_bottlenecks"
    category = "architecture"

    def __init__(self, z_threshold: float = 2.0, min_in_degree: int = 8):
        self.z_threshold = z_threshold
        self.min_in_degree = min_in_degree

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Compute in-degree for every file node
        degrees = {}
        for nid in ctx.file_nodes:
            deg = ctx.in_degree(nid)
            if deg > 0:
                degrees[nid] = deg

        if len(degrees) < 5:
            return findings

        values = list(degrees.values())
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0

        for nid, deg in sorted(degrees.items(), key=lambda kv: -kv[1]):
            if deg < self.min_in_degree:
                continue

            z = (deg - mean) / stdev if stdev > 0 else 0.0
            if z < self.z_threshold:
                continue

            node = ctx.file_nodes[nid]
            file_path = node.get("file_path", "")
            aug = ctx.augmentations.get(nid, {})
            role = aug.get("role", "unknown")
            summary = aug.get("summary", "")

            severity = "warning" if z >= 3.0 else "info"

            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"Hub bottleneck: {file_path} (in-degree {deg})",
                description=(
                    f"{file_path} is imported by {deg} other files "
                    f"(mean={mean:.1f}, z-score={z:.1f}). "
                    f"Role: {role}."
                    + (f" {summary}" if summary else "")
                    + " Changes to this file have a large blast radius."
                ),
                file_paths=[file_path],
                evidence={
                    "in_degree": deg,
                    "mean_in_degree": round(mean, 1),
                    "z_score": round(z, 2),
                    "role": role,
                },
                suggested_action=(
                    "Consider splitting this file or extracting an interface "
                    "to reduce coupling."
                ),
            ))

        return findings
