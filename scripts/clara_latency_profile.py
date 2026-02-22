#!/usr/bin/env python3
"""
CLaRa Latency Profiler — Phase 31

Measures CLaRa server performance across:
- Increasing input volumes (1K → 100K chars)
- Cold start vs warm request latency
- Different max_new_tokens values
- Memory usage snapshots

Usage:
    # Basic profiling (requires CLaRa server on :8765)
    python scripts/clara_latency_profile.py

    # Custom endpoint
    python scripts/clara_latency_profile.py --clara-url http://gpu-server:8765

    # Quick test (3 volume steps)
    python scripts/clara_latency_profile.py --quick

    # Include cold-start measurement (unloads model first)
    python scripts/clara_latency_profile.py --cold-start
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clara_latency")


# ---------------------------------------------------------------------------
# Synthetic code chunks for volume scaling
# ---------------------------------------------------------------------------

CHUNK_TEMPLATE = """# File: src/codrag/core/module_{n}.py
\"\"\"Module {n}: Handles {purpose}.\"\"\"

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class {class_name}:
    \"\"\"Primary class for {purpose} operations.\"\"\"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._cache: Dict[str, Any] = {{}}
        self._initialized = False
        logger.info("Initializing {class_name}")

    def process(self, input_data: List[str], *, max_items: int = 100) -> List[Dict]:
        \"\"\"Process input data with optional max_items limit.

        Args:
            input_data: List of strings to process.
            max_items: Maximum items to return.

        Returns:
            List of processed result dictionaries.
        \"\"\"
        if not self._initialized:
            self._initialize()

        results = []
        for item in input_data[:max_items]:
            result = self._transform(item)
            if result:
                results.append(result)
                self._cache[item] = result

        logger.info("{class_name}.process: %d items → %d results", len(input_data), len(results))
        return results

    def _initialize(self) -> None:
        \"\"\"Lazy initialization.\"\"\"
        self._initialized = True

    def _transform(self, item: str) -> Optional[Dict]:
        \"\"\"Transform a single item.\"\"\"
        return {{"input": item, "output": item.upper(), "module": "{class_name}"}}

    def status(self) -> Dict[str, Any]:
        \"\"\"Return module status.\"\"\"
        return {{
            "module": "{class_name}",
            "initialized": self._initialized,
            "cache_size": len(self._cache),
        }}


def create_{func_name}(config: Optional[Dict] = None) -> {class_name}:
    \"\"\"Factory function for {class_name}.\"\"\"
    return {class_name}(config or {{}})
"""

PURPOSES = [
    "search indexing", "trace graph building", "embedding generation",
    "context assembly", "compression pipeline", "file watching",
    "project management", "API routing", "license validation",
    "cluster synthesis", "epistemic scoring", "deepening loop",
    "atlas routing", "MCP tool dispatch", "build orchestration",
    "configuration persistence", "path weight resolution",
    "role weight calculation", "intent detection", "keyword boosting",
    "primer boost computation", "chunk assembly", "score normalization",
    "trace expansion", "neighbor discovery", "symbol resolution",
    "module boundary detection", "coverage computation",
    "staleness detection", "drift propagation", "convergence tracking",
]


def generate_code_chunks(n: int) -> List[str]:
    """Generate n synthetic code chunks (~800 chars each)."""
    chunks = []
    for i in range(n):
        purpose = PURPOSES[i % len(PURPOSES)]
        class_name = "".join(w.capitalize() for w in purpose.split())
        func_name = purpose.replace(" ", "_")
        chunk = CHUNK_TEMPLATE.format(
            n=i, purpose=purpose, class_name=class_name, func_name=func_name,
        )
        chunks.append(chunk.strip())
    return chunks


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class LatencyPoint:
    """A single latency measurement."""
    volume_label: str
    num_memories: int
    input_chars: int
    input_tokens_est: int
    max_new_tokens: int
    output_chars: int
    output_tokens_est: int
    compression_ratio: float
    latency_ms: float
    is_cold_start: bool = False
    success: bool = True
    error: Optional[str] = None


@dataclass
class LatencyProfile:
    """Complete latency profiling run."""
    timestamp: str
    clara_url: str
    clara_status: Dict[str, Any] = field(default_factory=dict)
    points: List[Dict[str, Any]] = field(default_factory=list)
    cold_start_ms: Optional[float] = None
    warm_avg_ms: Optional[float] = None
    total_duration_s: float = 0.0


# ---------------------------------------------------------------------------
# Volume test configurations
# ---------------------------------------------------------------------------

@dataclass
class VolumeStep:
    """A volume configuration to test."""
    label: str
    num_chunks: int
    max_new_tokens: int


DEFAULT_STEPS: List[VolumeStep] = [
    VolumeStep("1K-tiny",       1,  128),
    VolumeStep("3K-small",      3,  128),
    VolumeStep("6K-default",    7,  256),
    VolumeStep("10K-medium",   12,  256),
    VolumeStep("20K-large",    25,  512),
    VolumeStep("40K-xlarge",   50,  512),
    VolumeStep("60K-huge",     75,  512),
    VolumeStep("100K-max",    125,  512),
]

QUICK_STEPS: List[VolumeStep] = [
    DEFAULT_STEPS[0],  # 1K
    DEFAULT_STEPS[2],  # 6K
    DEFAULT_STEPS[4],  # 20K
]

# max_new_tokens sweep at fixed 40K input
TOKEN_SWEEP_STEPS: List[VolumeStep] = [
    VolumeStep("40K-tok64",   50,   64),
    VolumeStep("40K-tok128",  50,  128),
    VolumeStep("40K-tok256",  50,  256),
    VolumeStep("40K-tok512",  50,  512),
    VolumeStep("40K-tok1024", 50, 1024),
]


# ---------------------------------------------------------------------------
# Profiler
# ---------------------------------------------------------------------------

class LatencyProfiler:
    """Profiles CLaRa server latency across volume and token configurations."""

    def __init__(self, clara_url: str = "http://localhost:8765", timeout_s: float = 180.0):
        self.clara_url = clara_url.rstrip("/")
        self.timeout_s = timeout_s
        self._chunks_cache: List[str] = []

    def check_server(self) -> Dict[str, Any]:
        """Get CLaRa server status."""
        try:
            r = requests.get(f"{self.clara_url}/status", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def is_healthy(self) -> bool:
        try:
            r = requests.get(f"{self.clara_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _get_chunks(self, n: int) -> List[str]:
        """Get n code chunks, generating if needed."""
        if len(self._chunks_cache) < n:
            self._chunks_cache = generate_code_chunks(max(n, 130))
        return self._chunks_cache[:n]

    def measure_cold_start(self) -> Optional[float]:
        """Measure cold start by requesting unload then timing first request."""
        logger.info("Measuring cold start...")

        # Send keep_alive=0 to trigger immediate unload
        try:
            chunks = self._get_chunks(1)
            requests.post(
                f"{self.clara_url}/compress",
                json={"memories": chunks[:1], "query": "test", "keep_alive": 0},
                timeout=30,
            )
            # Wait a moment for unload
            time.sleep(2)
        except Exception:
            pass

        # Time the next request (should trigger model load)
        t0 = time.monotonic()
        try:
            r = requests.post(
                f"{self.clara_url}/compress",
                json={
                    "memories": ["Test memory for cold start measurement."],
                    "query": "What is this?",
                    "max_new_tokens": 32,
                },
                timeout=self.timeout_s,
            )
            elapsed = (time.monotonic() - t0) * 1000
            if r.status_code == 200 and r.json().get("success"):
                logger.info("  Cold start: %.0fms", elapsed)
                return elapsed
        except Exception as e:
            logger.error("  Cold start measurement failed: %s", e)

        return None

    def measure_point(self, step: VolumeStep, query: str) -> LatencyPoint:
        """Measure a single volume/tokens combination."""
        chunks = self._get_chunks(step.num_chunks)
        input_text = "\n\n---\n\n".join(chunks)
        input_chars = len(input_text)

        point = LatencyPoint(
            volume_label=step.label,
            num_memories=step.num_chunks,
            input_chars=input_chars,
            input_tokens_est=input_chars // 4,
            max_new_tokens=step.max_new_tokens,
            output_chars=0,
            output_tokens_est=0,
            compression_ratio=0.0,
            latency_ms=0.0,
        )

        payload = {
            "memories": chunks,
            "query": query,
            "max_new_tokens": step.max_new_tokens,
        }

        t0 = time.monotonic()
        try:
            r = requests.post(
                f"{self.clara_url}/compress",
                json=payload,
                timeout=self.timeout_s,
            )
            elapsed = (time.monotonic() - t0) * 1000
            point.latency_ms = round(elapsed, 1)

            if r.status_code != 200:
                point.success = False
                point.error = f"HTTP {r.status_code}"
                return point

            data = r.json()
            if not data.get("success"):
                point.success = False
                point.error = data.get("error", "unknown")
                return point

            answer = data.get("answer", "")
            point.output_chars = len(answer)
            point.output_tokens_est = len(answer) // 4
            point.compression_ratio = round(
                data.get("compression_ratio", input_chars / max(len(answer), 1)), 1
            )

        except requests.Timeout:
            point.success = False
            point.error = f"Timeout after {self.timeout_s}s"
            point.latency_ms = self.timeout_s * 1000
        except Exception as e:
            point.success = False
            point.error = str(e)
            point.latency_ms = (time.monotonic() - t0) * 1000

        return point

    def run(
        self,
        steps: List[VolumeStep],
        query: str = "How does this codebase handle search, indexing, and context assembly?",
        include_cold_start: bool = False,
        include_token_sweep: bool = True,
        warmup: bool = True,
    ) -> LatencyProfile:
        """Run the full latency profiling suite."""
        profile = LatencyProfile(
            timestamp=datetime.now(timezone.utc).isoformat(),
            clara_url=self.clara_url,
        )

        if not self.is_healthy():
            logger.error("CLaRa server not healthy at %s", self.clara_url)
            return profile

        profile.clara_status = self.check_server()
        logger.info("CLaRa status: %s", json.dumps(profile.clara_status, indent=2, default=str))

        t_start = time.monotonic()

        # Warmup: send a small request to ensure model is loaded
        if warmup:
            logger.info("Warmup request...")
            self.measure_point(VolumeStep("warmup", 1, 32), "warmup")

        # Cold start measurement
        if include_cold_start:
            profile.cold_start_ms = self.measure_cold_start()
            # Re-warm after cold start test
            if warmup:
                logger.info("Re-warming model...")
                self.measure_point(VolumeStep("rewarm", 1, 32), "rewarm")

        # Volume scaling
        logger.info("\n═══ Volume Scaling ═══")
        for step in steps:
            logger.info("Testing %s (%d chunks, max_tokens=%d)...",
                       step.label, step.num_chunks, step.max_new_tokens)
            point = self.measure_point(step, query)

            if point.success:
                logger.info(
                    "  ✓ %d→%d chars (%.1f×), %.0fms",
                    point.input_chars, point.output_chars,
                    point.compression_ratio, point.latency_ms,
                )
            else:
                logger.warning("  ✗ %s", point.error)

            profile.points.append(asdict(point))

        # Token sweep
        if include_token_sweep:
            logger.info("\n═══ Token Sweep (fixed 40K input) ═══")
            for step in TOKEN_SWEEP_STEPS:
                logger.info("Testing %s (max_tokens=%d)...",
                           step.label, step.max_new_tokens)
                point = self.measure_point(step, query)

                if point.success:
                    logger.info(
                        "  ✓ %d output chars, %.0fms",
                        point.output_chars, point.latency_ms,
                    )
                else:
                    logger.warning("  ✗ %s", point.error)

                profile.points.append(asdict(point))

        profile.total_duration_s = round(time.monotonic() - t_start, 1)

        # Compute warm average (exclude cold start point)
        warm_points = [
            p for p in profile.points
            if p.get("success") and not p.get("is_cold_start")
            and p["volume_label"] not in ("warmup", "rewarm")
        ]
        if warm_points:
            profile.warm_avg_ms = round(
                sum(p["latency_ms"] for p in warm_points) / len(warm_points), 1
            )

        return profile


# ---------------------------------------------------------------------------
# Output & reporting
# ---------------------------------------------------------------------------

def save_profile(profile: LatencyProfile, output_path: Path) -> None:
    """Save profile to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(profile), f, indent=2, default=str)
    logger.info("Profile saved to %s", output_path)


def print_profile(profile: LatencyProfile) -> None:
    """Print latency profile as a readable table."""
    print("\n" + "═" * 80)
    print("  CLaRa Latency Profile")
    print("═" * 80)
    print(f"  Server:       {profile.clara_url}")
    print(f"  Backend:      {profile.clara_status.get('backend', 'unknown')}")
    print(f"  Device:       {profile.clara_status.get('device', 'unknown')}")
    print(f"  Duration:     {profile.total_duration_s:.1f}s")

    if profile.cold_start_ms:
        print(f"  Cold start:   {profile.cold_start_ms:.0f}ms")
    if profile.warm_avg_ms:
        print(f"  Warm avg:     {profile.warm_avg_ms:.0f}ms")

    # Volume scaling table
    vol_points = [
        p for p in profile.points
        if p["volume_label"] not in ("warmup", "rewarm")
        and not p["volume_label"].startswith("40K-tok")
    ]

    if vol_points:
        print("\n## Volume Scaling")
        header = (
            f"{'Volume':<14} {'Chunks':>7} {'Input':>8} {'Output':>8} "
            f"{'Ratio':>7} {'Latency':>9} {'Status':>8}"
        )
        print(header)
        print("─" * len(header))

        for p in vol_points:
            status = "✓" if p["success"] else f"✗ {p.get('error', '')[:20]}"
            print(
                f"{p['volume_label']:<14} {p['num_memories']:>7} "
                f"{p['input_chars']:>7}c {p['output_chars']:>7}c "
                f"{p['compression_ratio']:>6.1f}× {p['latency_ms']:>8.0f}ms "
                f"{status:>8}"
            )

    # Token sweep table
    tok_points = [
        p for p in profile.points
        if p["volume_label"].startswith("40K-tok")
    ]

    if tok_points:
        print("\n## Token Sweep (40K input)")
        header = (
            f"{'max_tokens':>11} {'Output Chars':>13} {'Output Tokens':>14} "
            f"{'Latency':>9} {'Status':>8}"
        )
        print(header)
        print("─" * len(header))

        for p in tok_points:
            status = "✓" if p["success"] else f"✗ {p.get('error', '')[:20]}"
            print(
                f"{p['max_new_tokens']:>11} {p['output_chars']:>13} "
                f"{p['output_tokens_est']:>14} {p['latency_ms']:>8.0f}ms "
                f"{status:>8}"
            )

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLaRa Latency Profiler",
    )
    parser.add_argument(
        "--clara-url", default="http://localhost:8765",
        help="CLaRa server URL (default: http://localhost:8765)",
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSON path (default: docs/Phase31_CLaRa-tests/latency_<timestamp>.json)",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick test (3 volume steps, no sweep)",
    )
    parser.add_argument(
        "--cold-start", action="store_true",
        help="Include cold-start measurement (sends keep_alive=0 to unload first)",
    )
    parser.add_argument(
        "--no-token-sweep", action="store_true",
        help="Skip the max_new_tokens sweep",
    )
    parser.add_argument(
        "--timeout", type=float, default=180.0,
        help="Per-request timeout in seconds (default: 180)",
    )

    args = parser.parse_args()

    profiler = LatencyProfiler(
        clara_url=args.clara_url,
        timeout_s=args.timeout,
    )

    steps = QUICK_STEPS if args.quick else DEFAULT_STEPS

    profile = profiler.run(
        steps=steps,
        include_cold_start=args.cold_start,
        include_token_sweep=not args.quick and not args.no_token_sweep,
    )

    # Save
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"docs/Phase31_CLaRa-tests/latency_{ts}.json")

    save_profile(profile, output_path)
    print_profile(profile)

    # Exit code
    failed = sum(1 for p in profile.points if not p.get("success"))
    if failed:
        logger.warning("%d/%d measurements failed", failed, len(profile.points))
        sys.exit(1)


if __name__ == "__main__":
    main()
