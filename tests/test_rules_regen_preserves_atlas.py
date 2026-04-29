"""C1 regression: schedule_rules_regeneration loads atlas when caller omits it.

When scope CRUD triggers a debounced regen and doesn't pass atlas_content,
the regenerator must load the project's current atlas rather than rewriting
AGENTS.md with an empty atlas section.
"""
from __future__ import annotations

import threading

import pytest


@pytest.mark.asyncio
async def test_schedule_rules_regeneration_loads_atlas_when_caller_omits_it(
    tmp_settings, dummy_project_in_registry, monkeypatch, tmp_path,
):
    """C1 regression: atlas_content must be loaded from disk when the caller
    (e.g. scope CRUD) doesn't pass it to schedule_rules_regeneration."""
    from prep.core import rules_generator as rg

    captured: dict = {}

    def fake_write(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(rg, "write_rules_file", fake_write)
    monkeypatch.setattr(rg, "_get_current_atlas_content",
                        lambda pid: "EXPECTED ATLAS BODY")
    monkeypatch.setattr(rg, "_get_current_stats",
                        lambda pid: {"file_count": 100})

    # Bypass the 2-second debounce timer by replacing threading.Timer with an
    # immediate synchronous variant.
    fired = threading.Event()

    class _ImmediateTimer:
        def __init__(self, _delay: float, fn: object, args: tuple = (), kwargs: dict | None = None) -> None:
            self._fn = fn
            self._args = args
            self._kwargs = kwargs or {}

        def start(self) -> None:
            try:
                self._fn(*self._args, **self._kwargs)
            finally:
                fired.set()

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(rg.threading, "Timer", _ImmediateTimer)

    rg.schedule_rules_regeneration(
        project_id=dummy_project_in_registry.id,
        project_path=tmp_path,
        project_name="Test",
        included_paths=["src/"],
        # atlas_content and stats intentionally omitted (the C1 scenario)
    )

    assert fired.is_set(), "regen never fired"
    assert captured.get("atlas_content") == "EXPECTED ATLAS BODY", (
        f"atlas was wiped: {captured.get('atlas_content')!r}"
    )
    assert captured.get("stats") == {"file_count": 100}, (
        f"stats was wiped: {captured.get('stats')!r}"
    )
