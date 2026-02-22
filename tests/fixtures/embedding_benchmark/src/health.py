"""Health check and readiness probes for the application."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthChecker:
    """Aggregate health checks for all application components."""

    def __init__(self):
        self._checks: Dict[str, callable] = {}

    def register(self, name: str, check_fn: callable):
        """Register a health check function."""
        self._checks[name] = check_fn

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks and return aggregate status."""
        results: List[ComponentHealth] = []
        overall = HealthStatus.HEALTHY

        for name, check_fn in self._checks.items():
            start = time.time()
            try:
                check_fn()
                latency = (time.time() - start) * 1000
                results.append(ComponentHealth(name=name, status=HealthStatus.HEALTHY, latency_ms=latency))
            except Exception as e:
                latency = (time.time() - start) * 1000
                results.append(ComponentHealth(
                    name=name, status=HealthStatus.UNHEALTHY,
                    latency_ms=latency, message=str(e),
                ))
                overall = HealthStatus.UNHEALTHY

        return {
            "status": overall.value,
            "components": [
                {"name": r.name, "status": r.status.value, "latency_ms": r.latency_ms, "message": r.message}
                for r in results
            ],
            "timestamp": time.time(),
        }

    def check_readiness(self) -> bool:
        """Quick readiness probe — returns True if all components are healthy."""
        result = self.check_all()
        return result["status"] == "healthy"
