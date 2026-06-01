"""Phase 129 regression: known-clean files must stay leak-free.

Phase 129 (Dev-Leak Audit) is rolling out one cluster at a time.  This
test pins the cluster that already shipped: high-visibility user-facing
log call sites whose strings used to lead with "Phase N: ..." or
"F-NN: ..." and now read as plain operational copy.

Scope:
  - src/prep/server.py             — daemon startup logs
  - src/prep/core/watcher.py       — continuous watchdog logs
  - src/prep/core/embedder.py      — startup banner for CoreML opts
  - src/prep/core/system_concept_seeder.py — startup banner for system seeds
  - src/prep/mcp/server.py         — MCP scope-filter debug log

What counts as a leak (per Phase 129 README):
  - Phase-number or F-NN prefix at the START of a string literal passed
    positionally to a logger.* call.  Comments and docstrings are out
    of scope; this test inspects ast.Call nodes, so neither contributes.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import prep.server as server_mod
import prep.core.watcher as watcher_mod
import prep.core.embedder as embedder_mod
import prep.core.system_concept_seeder as system_seeder_mod
import prep.mcp.server as mcp_server_mod
import prep.services.pipeline.orchestrator as pipeline_orchestrator_mod
import prep.services.pipeline.recovery as pipeline_recovery_mod
import prep.services.pipeline.resume as pipeline_resume_mod
import prep.services.pipeline.post_flight as pipeline_post_flight_mod
import prep.services.pipeline_metadata as pipeline_metadata_mod
import prep.core.trace.builder as trace_builder_mod


# A leak string starts with either "Phase NN" / "Phase NNX" (e.g.
# Phase 61B) or "F-NN" — these are the patterns Phase 129 targets.
_LEAK_PREFIX = re.compile(r"^(Phase \d+[A-Z]?(?:/F-\d+)?|F-\d+)\b")


def _logger_call_string_leaks(source: str) -> list[tuple[int, str]]:
    """Return (lineno, string) for every string literal passed
    positionally to a logger.* call whose value starts with a Phase /
    F-NN prefix.
    """
    tree = ast.parse(source)
    leaks: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match logger.info / logger.warning / etc — Attribute call on
        # a Name whose id is "logger".
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "logger":
            continue
        # Inspect each positional arg.  String literals appear as
        # ast.Constant(value=str); also handle f-strings (ast.JoinedStr)
        # whose first segment is a plain string.
        for arg in node.args:
            text: str | None = None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                text = arg.value
            elif isinstance(arg, ast.JoinedStr) and arg.values:
                first = arg.values[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    text = first.value
            if text and _LEAK_PREFIX.match(text):
                leaks.append((arg.lineno, text))
    return leaks


CLEAN_MODULES = [
    # 2026-05-27 (Lane C): high-visibility startup + watcher cluster.
    server_mod,
    watcher_mod,
    embedder_mod,
    system_seeder_mod,
    mcp_server_mod,
    # 2026-05-28 (Lane C): pipeline orchestration cluster.
    pipeline_orchestrator_mod,
    pipeline_recovery_mod,
    pipeline_resume_mod,
    pipeline_post_flight_mod,
    pipeline_metadata_mod,
    trace_builder_mod,
]


@pytest.mark.parametrize(
    "module", CLEAN_MODULES, ids=[m.__name__ for m in CLEAN_MODULES]
)
def test_module_has_no_phase_prefix_in_logger_strings(module):
    """logger.* strings in this module must not lead with Phase N / F-NN."""
    src_path = Path(module.__file__)
    leaks = _logger_call_string_leaks(src_path.read_text())
    assert not leaks, (
        f"{src_path} has dev-nomenclature leaks in logger calls "
        f"(Phase 129 recipe 1 / 3 regression):\n"
        + "\n".join(f"  line {ln}: {s!r}" for ln, s in leaks)
    )
