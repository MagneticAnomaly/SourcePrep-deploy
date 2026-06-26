"""PR-S (§9.3 #32) — DEEPENING worker adoption of the orchestrator
override contract.

Closes PRQ-CSI-002 from PR-Q round-1 scrutiny.

History:
  - PR-S (ca241743): initial worker change. emits _expected_total +
    _processed_count via inline computation.
  - PR-S-fixup-r1 (5fc91683): round-1 scrutiny followups. Extracted
    _compute_deepening_override_keys module-level helper. Added
    convergence-preferred path. Numerator filter pass_number>=3.
    WARNING + telemetry on failure.
  - PR-S-fixup-r2 (HEAD): round-2 scrutiny followups. Dropped the
    convergence-preferred path (its denominator/numerator both had
    semantic gaps — F-1, F-2 from scrutiny). Helper is now single-
    source-of-truth scope-read with empty-file + pass_number filters.
    Fixed deepening.py:497/554 to always write pass_number>=3 when
    DEEPENING runs (F-2). Moved WARNING + telemetry into helper's
    except block so exc_info + per-exception payload are preserved
    (F-3). Narrowed telemetry's bare except (F-4). Empty project
    case emits (0, 0) override keys explicitly instead of dropping
    them (F-5). Narrowed inner _get_file_excerpt except (F-6).
    Added KeyError to outer except tuple (F-7).

This file pins:
  - source-level wiring (worker delegates to the helper)
  - functional behavior of the helper (most coverage here)
  - deepening.py's pass_number>=3 invariant (F-2 regression catcher)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────
# Source-level wiring pins.
# ─────────────────────────────────────────────────────────────────


class TestDeepeningWorkerWiresHelper:
    """The DEEPENING worker must route override-key computation through
    `_compute_deepening_override_keys`. Source-regex pins; functional
    behavior covered by TestComputeDeepeningOverrideKeys.
    """

    def _workers_body(self) -> str:
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        return src_path.read_text(encoding="utf-8")

    def _deepening_region(self) -> str:
        body = self._workers_body()
        idx = body.index("def _deepening_worker(")
        return body[idx:idx + 8000]

    def test_helper_function_exists_at_module_level(self):
        body = self._workers_body()
        assert "def _compute_deepening_override_keys(" in body

    def test_deepening_worker_calls_helper(self):
        region = self._deepening_region()
        assert "_compute_deepening_override_keys(" in region

    def test_worker_passes_idx_dir_and_project_id_to_helper(self):
        # PR-S-fixup-r2 F-3: telemetry needs idx_dir + project_id so
        # it can fire from inside the helper's except block. Worker
        # must pass them as kwargs.
        region = self._deepening_region()
        assert "idx_dir=idx_dir" in region, (
            "F-3 regression: worker must pass idx_dir to helper so "
            "telemetry can emit from the helper's except block."
        )
        assert "project_id=project_id" in region, (
            "F-3 regression: worker must pass project_id to helper "
            "so telemetry can emit from the helper's except block."
        )

    def test_deepening_worker_emits_expected_total_key(self):
        region = self._deepening_region()
        assert '"_expected_total"' in region

    def test_deepening_worker_emits_processed_count_key(self):
        region = self._deepening_region()
        assert '"_processed_count"' in region

    def test_worker_emits_keys_for_empty_project(self):
        # F-5: worker must emit override keys when expected_total == 0
        # (legitimate empty project case) instead of falling through
        # to JSONL semantics. The conditional should be
        # `if expected_total is not None` (NOT `> 0`).
        region = self._deepening_region()
        assert "expected_total is not None" in region, (
            "F-5 regression: worker must emit override keys for "
            "empty projects (expected_total == 0). The check should "
            "be `is not None`, not `> 0`."
        )
        # Pin the OLD pattern is GONE so reverting accidentally fails.
        assert "expected_total is not None and expected_total > 0" not in region, (
            "F-5 regression: the old `is not None and > 0` conditional "
            "drops the empty-project case. Use `is not None` only."
        )

    def test_skip_path_documents_known_gap(self):
        region = self._deepening_region()
        # FIXUP-5 (from round-1): skip path is documented as a known leak.
        assert "FIXUP-5" in region or "no_llm" in region


# ─────────────────────────────────────────────────────────────────
# Functional pins on _compute_deepening_override_keys.
# These exercise real behavior — not just source-regex.
# ─────────────────────────────────────────────────────────────────


def _make_enricher(file_nodes_with_excerpt, existing_entries):
    """Build a mock enricher whose load_trace_nodes / load_existing /
    _get_file_excerpt return the supplied fixtures.

    file_nodes_with_excerpt: list of (node_dict, excerpt_str). excerpt
        empty-string ⇒ the empty-file filter rejects the node.
    existing_entries: dict[node_id, SimpleNamespace(pass_number=N)].
    """
    enricher = MagicMock()
    enricher.load_trace_nodes.return_value = [n for n, _ in file_nodes_with_excerpt]

    def _excerpt(file_path, max_lines=150):
        for n, ex in file_nodes_with_excerpt:
            if n.get("file_path") == file_path:
                return ex
        return ""

    enricher._get_file_excerpt.side_effect = _excerpt
    enricher.load_existing.return_value = existing_entries
    return enricher


def _entry(pass_number=2):
    return SimpleNamespace(pass_number=pass_number)


class TestComputeDeepeningOverrideKeys:
    """Functional pins on the helper."""

    def test_basic_scope_read_returns_expected_counts(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n2 = {"id": "file:b.py", "kind": "file", "file_path": "b.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "real content"), (n2, "real content")],
            existing_entries={
                "file:a.py": _entry(pass_number=3),  # deepened
                "file:b.py": _entry(pass_number=2),  # enriched only
            },
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 2  # both file nodes in scope
        assert processed == 1  # only a.py has pass_number >= 3

    def test_deepening_result_param_removed_in_fixup_r3(self):
        # PR-S-fixup-r3 FIX-2: dropped the `deepening_result`
        # parameter entirely. Pre-fixup-r3 it was kept "for backward
        # compatibility" — a foot-gun on a module-private helper
        # with one caller, inviting future re-introduction of the
        # convergence path that two rounds of scrutiny dropped.
        # Pin via source-regex that the signature uses keyword-only
        # arguments after enricher (no positional deepening_result).
        from pathlib import Path

        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        assert "def _compute_deepening_override_keys(\n    enricher: Any,\n    *," in body, (
            "FIX-2 regression: _compute_deepening_override_keys "
            "signature must NOT accept deepening_result. If a future "
            "PR needs DeepeningResult context, that becomes a "
            "deliberate API addition — not a vestigial parameter."
        )
        # Pin that no legacy deepening_result= kwarg remains in the
        # worker callsite.
        assert "deepening_result=result" not in body, (
            "FIX-2 regression: worker still passes deepening_result "
            "kwarg. The helper no longer accepts it."
        )

    def test_empty_file_filter_excludes_empty_init(self):
        # F-1 cornerstone: empty file nodes (empty __init__.py) excluded
        # from the denominator. Mirrors ENRICHMENT scope.
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_real = {"id": "file:real.py", "kind": "file", "file_path": "real.py"}
        n_empty = {"id": "file:__init__.py", "kind": "file", "file_path": "__init__.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n_real, "content"), (n_empty, "")],
            existing_entries={"file:real.py": _entry(pass_number=3)},
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 1  # __init__.py excluded
        assert processed == 1

    def test_empty_file_filter_survives_oserror_on_excerpt(self):
        # F-6: narrowed inner except. _get_file_excerpt may raise
        # OSError (file deleted between trace_node enumeration and
        # excerpt read). The narrowed catch must still treat the
        # file as empty (excluded from scope).
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_ok = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n_io_fail = {"id": "file:gone.py", "kind": "file", "file_path": "gone.py"}
        enricher = MagicMock()
        enricher.load_trace_nodes.return_value = [n_ok, n_io_fail]

        def _excerpt(file_path, max_lines=150):
            if file_path == "gone.py":
                raise OSError("file vanished")
            return "real content"

        enricher._get_file_excerpt.side_effect = _excerpt
        enricher.load_existing.return_value = {
            "file:a.py": _entry(pass_number=3),
        }

        total, processed = _compute_deepening_override_keys(enricher)
        # gone.py treated as empty → excluded from denominator.
        assert total == 1
        assert processed == 1

    def test_kind_filter_excludes_non_file_nodes(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_file = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n_sym = {"id": "sym:Foo", "kind": "symbol", "file_path": "a.py"}
        n_sec = {"id": "sec:1", "kind": "section", "file_path": "doc.md"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[
                (n_file, "content"),
                (n_sym, "content"),
                (n_sec, "content"),
            ],
            existing_entries={"file:a.py": _entry(pass_number=3)},
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 1

    def test_pass_number_filter_excludes_enrichment_only_entries(self):
        # FIXUP-2 anchor: chip must NOT read 100% just because
        # ENRICHMENT completed.
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        nodes = [
            ({"id": f"file:f{i}.py", "kind": "file", "file_path": f"f{i}.py"}, "content")
            for i in range(3)
        ]
        enricher = _make_enricher(
            file_nodes_with_excerpt=nodes,
            existing_entries={
                "file:f0.py": _entry(pass_number=2),  # enrichment only
                "file:f1.py": _entry(pass_number=2),  # enrichment only
                "file:f2.py": _entry(pass_number=3),  # deepened
            },
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 3
        assert processed == 1

    def test_pass_number_high_passes_count(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n2 = {"id": "file:b.py", "kind": "file", "file_path": "b.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "real"), (n2, "real")],
            existing_entries={
                "file:a.py": _entry(pass_number=3),
                "file:b.py": _entry(pass_number=5),
            },
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 2
        assert processed == 2

    def test_orphan_filter_excludes_out_of_scope_entries(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_current = {"id": "file:current.py", "kind": "file", "file_path": "current.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n_current, "content")],
            existing_entries={
                "file:current.py": _entry(pass_number=3),
                "file:deleted.py": _entry(pass_number=3),  # ORPHAN
                "file:also_deleted.py": _entry(pass_number=5),  # ORPHAN
            },
        )

        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 1
        assert processed == 1

    def test_zero_file_nodes_returns_zero_total(self):
        # F-5: zero file_nodes is a legitimate "empty project" — must
        # return (0, 0), NOT (None, None). Caller emits the keys so
        # the chip shows 0/0 instead of falling back to JSONL.
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = _make_enricher(file_nodes_with_excerpt=[], existing_entries={})
        total, processed = _compute_deepening_override_keys(enricher)
        assert total == 0
        assert processed == 0
        # CRITICAL: not None. The worker's `is not None` check then
        # emits the keys.
        assert total is not None
        assert processed is not None


class TestHelperFailurePath:
    """F-3: WARNING + telemetry emitted from helper's except block."""

    def test_returns_none_on_oserror(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("disk full")

        total, processed = _compute_deepening_override_keys(enricher)
        assert total is None
        assert processed is None

    def test_returns_none_on_json_decode_error(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = json.JSONDecodeError("bad", "doc", 0)

        total, processed = _compute_deepening_override_keys(enricher)
        assert total is None
        assert processed is None

    def test_returns_none_on_keyerror(self):
        # F-7: corrupt jsonl missing "id" key. Pre-F7 the KeyError
        # propagated and crashed the deepening worker; the narrowed
        # except now catches it cleanly.
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_no_id = {"kind": "file", "file_path": "a.py"}  # missing "id"
        enricher = MagicMock()
        enricher.load_trace_nodes.return_value = [n_no_id]
        enricher._get_file_excerpt.return_value = "content"
        enricher.load_existing.return_value = {}

        total, processed = _compute_deepening_override_keys(enricher)
        assert total is None
        assert processed is None

    def test_propagates_programmer_errors(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = TypeError("oops")

        import pytest as _pytest
        with _pytest.raises(TypeError):
            _compute_deepening_override_keys(enricher)

    def test_warning_logged_with_exc_info(self, caplog):
        # F-3: WARNING + exc_info must be emitted from the except
        # block where the exception is in scope. Pre-fixup-r2 the
        # WARNING was in the caller and lost both.
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("disk error msg")

        with caplog.at_level(logging.WARNING, logger="prep.services.pipeline.workers"):
            _compute_deepening_override_keys(enricher)

        # WARNING level present with the exception type AND message.
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1
        record = warning_records[0]
        assert "OSError" in record.getMessage()
        assert "disk error msg" in record.getMessage()
        # exc_info captured → traceback available.
        assert record.exc_info is not None
        assert record.exc_info[0] is OSError

    def test_telemetry_emitted_with_exception_metadata(self, tmp_path, monkeypatch):
        # F-3: telemetry payload carries per-exception type + message
        # so operators can triage without re-running with logger
        # output capture.
        from prep.services.pipeline import workers as workers_mod

        calls = []

        def _fake_record_event(idx_dir, event_type, payload, stage=None, project_id=None):
            calls.append({
                "idx_dir": idx_dir,
                "event_type": event_type,
                "payload": payload,
                "stage": stage,
                "project_id": project_id,
            })

        # Inject the fake into the lazy import path.
        import sys
        fake_module = type(sys)("prep.services.pipeline_telemetry")
        fake_module.record_event = _fake_record_event
        monkeypatch.setitem(sys.modules, "prep.services.pipeline_telemetry", fake_module)

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = json.JSONDecodeError("bad json", "doc", 5)

        workers_mod._compute_deepening_override_keys(
            enricher,
            idx_dir=tmp_path,
            project_id="test-project",
        )

        assert len(calls) == 1
        c = calls[0]
        assert c["event_type"] == "deepening_override_failed"
        assert c["stage"] == "deepening"
        assert c["project_id"] == "test-project"
        assert c["payload"]["reason"] == "scope_read_failure"
        assert c["payload"]["error_type"] == "JSONDecodeError"
        assert "bad json" in c["payload"]["error_message"]

    def test_telemetry_skipped_when_idx_dir_missing(self, monkeypatch):
        # When caller omits idx_dir/project_id, helper still logs
        # WARNING but doesn't try to call record_event.
        from prep.services.pipeline import workers as workers_mod

        calls = []
        import sys
        fake_module = type(sys)("prep.services.pipeline_telemetry")
        fake_module.record_event = lambda *a, **k: calls.append((a, k))
        monkeypatch.setitem(sys.modules, "prep.services.pipeline_telemetry", fake_module)

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("disk")

        workers_mod._compute_deepening_override_keys(enricher)
        # No telemetry call when idx_dir/project_id absent.
        assert calls == []

    def test_telemetry_failure_does_not_crash_helper(self, tmp_path, monkeypatch):
        # F-4: telemetry call is wrapped in a narrowed except. An
        # OSError in record_event must not crash the helper.
        from prep.services.pipeline import workers as workers_mod

        import sys
        fake_module = type(sys)("prep.services.pipeline_telemetry")

        def _bad_record_event(*a, **k):
            raise OSError("event log unwritable")

        fake_module.record_event = _bad_record_event
        monkeypatch.setitem(sys.modules, "prep.services.pipeline_telemetry", fake_module)

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("scope read failed")

        # Should not raise — helper returns (None, None) cleanly.
        total, processed = workers_mod._compute_deepening_override_keys(
            enricher, idx_dir=tmp_path, project_id="p",
        )
        assert total is None
        assert processed is None

    def test_telemetry_programmer_error_swallowed_in_fixup_r3(
        self, tmp_path, monkeypatch, caplog,
    ):
        # PR-S-fixup-r3 FIX-1: telemetry must NEVER crash the
        # deepening worker after all LLM work completed. The inner
        # defensive `except Exception: logger.debug(...)` guards
        # against future record_event signature drift or refactors
        # that emit a different exception class.
        #
        # Pre-FIX-1 (PR-S-fixup-r2 narrow except behavior):
        # TypeError from record_event propagated past the narrowed
        # except (only ImportError/OSError were caught), crashing
        # the deepening worker. Now it's swallowed defensively and
        # logged at DEBUG so a future grep finds the suppression.
        from prep.services.pipeline import workers as workers_mod

        import sys
        fake_module = type(sys)("prep.services.pipeline_telemetry")

        def _bad_record_event(*a, **k):
            raise TypeError("signature drift")

        fake_module.record_event = _bad_record_event
        monkeypatch.setitem(sys.modules, "prep.services.pipeline_telemetry", fake_module)

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("scope failure")

        # NEW behavior: defensive wrap swallows the TypeError.
        # Helper still returns (None, None) cleanly.
        with caplog.at_level(logging.DEBUG, logger="prep.services.pipeline.workers"):
            total, processed = workers_mod._compute_deepening_override_keys(
                enricher, idx_dir=tmp_path, project_id="p",
            )
        assert total is None
        assert processed is None
        # The defensive swallow logs at DEBUG with the exception type
        # so future grep finds it.
        debug_records = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "telemetry" in r.getMessage().lower()
        ]
        assert len(debug_records) >= 1, (
            "FIX-1 regression: telemetry exception must be logged at "
            "DEBUG (not silently swallowed) so a future operator can "
            "trace the suppression via log grep."
        )


# ─────────────────────────────────────────────────────────────────
# F-2 regression catcher on deepening.py: DEEPENING must always
# write pass_number >= 3 (not 2 on first-time deepening).
# ─────────────────────────────────────────────────────────────────


class TestDeepeningAlwaysIncrementsPassNumber:
    """deepening.py:497 (sequential) and :554 (concurrent) used to
    write `entry.pass_number = previous + 1 if is_re_enrichment else 2`.
    The `else 2` branch made first-time DEEPENING entries indistinguishable
    from ENRICHMENT entries — breaking the chip's pass_number>=3
    numerator filter.

    PR-S-fixup-r2 F-2: both branches now write max(prev_pass + 1, 3)
    so a DEEPENING-touched entry is ALWAYS pass_number >= 3.
    """

    def _deepening_body(self) -> str:
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "core" / "deepening.py"
        )
        return src_path.read_text(encoding="utf-8")

    def test_uses_max_prev_plus_one_three(self):
        body = self._deepening_body()
        # Both branches should use the same max(prev+1, 3) pattern.
        assert "max(prev_pass + 1, 3)" in body, (
            "F-2 regression: deepening.py must always write "
            "pass_number >= 3 when DEEPENING runs. The old "
            "`else 2` branch made first-time deepening entries "
            "indistinguishable from ENRICHMENT entries, breaking "
            "the chip's pass_number>=3 numerator filter."
        )

    def test_no_legacy_else_two_pattern_remains(self):
        body = self._deepening_body()
        # Pin the OLD pattern is GONE.
        assert "pass_number + 1 if is_re_enrichment else 2" not in body, (
            "F-2 regression: legacy `else 2` first-time-deepening "
            "pattern resurfaced in deepening.py."
        )
        assert "pass_number + 1 if is_re else 2" not in body, (
            "F-2 regression: legacy `else 2` concurrent branch "
            "resurfaced."
        )

    def test_documents_pr_s_fixup_rationale(self):
        body = self._deepening_body()
        # The change should be commented so the next maintainer
        # doesn't revert it.
        assert "PR-S-fixup-r2 F-2" in body, (
            "F-2 regression: deepening.py must document why "
            "max(prev_pass + 1, 3) replaced `else 2` so the next "
            "maintainer doesn't revert it as 'unnecessary'."
        )


# ─────────────────────────────────────────────────────────────────
# PR-T: skip-path leak fix.
# When LLM is unavailable, the deepening worker returns BEFORE
# instantiating the enricher. The new disk-based helper reads
# jsonl files directly so the chip still gets accurate scope on
# the skip path. Closes PR-S round-1 FIXUP-5 / round-3 DEF-6.
# ─────────────────────────────────────────────────────────────────


def _seed_idx_dir(idx_dir, repo_root, file_specs, epistemic_specs):
    """Seed an index dir + repo root for the disk-based helper.

    file_specs: list of (rel_path, file_content) tuples. file_content
        empty string ⇒ file exists but is empty (excluded from scope).
    epistemic_specs: list of (node_id, pass_number) tuples for
        trace_epistemic.jsonl.
    """
    idx_dir.mkdir(parents=True, exist_ok=True)
    repo_root.mkdir(parents=True, exist_ok=True)

    nodes = []
    for rel_path, content in file_specs:
        nodes.append({
            "id": f"file:{rel_path}",
            "kind": "file",
            "file_path": rel_path,
        })
        full = repo_root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    (idx_dir / "trace_nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + ("\n" if nodes else ""),
        encoding="utf-8",
    )

    (idx_dir / "trace_epistemic.jsonl").write_text(
        "\n".join(
            json.dumps({"node_id": nid, "pass_number": pn})
            for nid, pn in epistemic_specs
        ) + ("\n" if epistemic_specs else ""),
        encoding="utf-8",
    )


class TestComputeDeepeningOverrideKeysFromDisk:
    """Functional pins on `_compute_deepening_override_keys_from_disk`
    (PR-T) — the enricher-free version used by the deepening worker's
    LLM-unavailable skip path.
    """

    def test_basic_scope_read(self, tmp_path):
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        _seed_idx_dir(
            idx, repo,
            file_specs=[("a.py", "# real content\n"), ("b.py", "# also real\n")],
            epistemic_specs=[
                ("file:a.py", 3),  # deepened
                ("file:b.py", 2),  # enriched only
            ],
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 2
        assert processed == 1

    def test_empty_file_filter_excludes_empty_init(self, tmp_path):
        # Same denominator semantic as the enricher-based path.
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        _seed_idx_dir(
            idx, repo,
            file_specs=[
                ("real.py", "import os\n"),
                ("__init__.py", ""),  # empty
            ],
            epistemic_specs=[("file:real.py", 3)],
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 1  # empty __init__.py excluded
        assert processed == 1

    def test_pass_number_filter_excludes_enrichment_only(self, tmp_path):
        # Same numerator semantic as the enricher-based path:
        # pass_number=2 (ENRICHMENT-only) entries do NOT count.
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        _seed_idx_dir(
            idx, repo,
            file_specs=[
                ("f0.py", "content\n"),
                ("f1.py", "content\n"),
                ("f2.py", "content\n"),
            ],
            epistemic_specs=[
                ("file:f0.py", 2),
                ("file:f1.py", 2),
                ("file:f2.py", 3),
            ],
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 3
        assert processed == 1

    def test_orphan_filter_excludes_out_of_scope_entries(self, tmp_path):
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        _seed_idx_dir(
            idx, repo,
            file_specs=[("current.py", "content\n")],
            epistemic_specs=[
                ("file:current.py", 3),
                ("file:deleted.py", 3),  # orphan
                ("file:also_deleted.py", 5),  # orphan
            ],
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 1
        assert processed == 1  # orphans excluded

    def test_missing_jsonl_files_return_zero(self, tmp_path):
        # Brand-new project: no jsonl files exist yet. Helper returns
        # (0, 0), not None — caller emits keys explicitly to defeat
        # JSONL fallback (same F-5 semantic as enricher path).
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        idx.mkdir()
        repo.mkdir()
        # No trace_nodes.jsonl, no trace_epistemic.jsonl.

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 0
        assert processed == 0
        assert total is not None  # F-5: emit keys for empty project

    def test_corrupt_jsonl_line_skipped_not_crashed(self, tmp_path):
        # A single corrupt line should not crash the helper.
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        idx.mkdir()
        repo.mkdir()

        (repo / "a.py").write_text("content\n")
        # Mix valid and corrupt lines in trace_nodes.jsonl.
        (idx / "trace_nodes.jsonl").write_text(
            json.dumps({"id": "file:a.py", "kind": "file", "file_path": "a.py"})
            + "\n"
            + "!!! not json at all !!!\n",
            encoding="utf-8",
        )
        (idx / "trace_epistemic.jsonl").write_text(
            json.dumps({"node_id": "file:a.py", "pass_number": 3})
            + "\n",
            encoding="utf-8",
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        # Valid line counted, corrupt line silently skipped.
        assert total == 1
        assert processed == 1

    def test_file_path_missing_from_disk_treated_as_empty(self, tmp_path):
        # trace_nodes.jsonl references a file_path that doesn't exist
        # on disk (deleted between snapshot and now). Helper treats
        # it as empty (excluded from scope) — same defensive behavior
        # as the enricher path.
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        idx.mkdir()
        repo.mkdir()

        (repo / "exists.py").write_text("content\n")
        # NOTE: gone.py NOT created.
        (idx / "trace_nodes.jsonl").write_text(
            json.dumps({"id": "file:exists.py", "kind": "file", "file_path": "exists.py"})
            + "\n"
            + json.dumps({"id": "file:gone.py", "kind": "file", "file_path": "gone.py"})
            + "\n",
            encoding="utf-8",
        )
        (idx / "trace_epistemic.jsonl").write_text(
            json.dumps({"node_id": "file:exists.py", "pass_number": 3})
            + "\n",
            encoding="utf-8",
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 1  # gone.py excluded by file-not-found
        assert processed == 1

    def test_kind_filter_excludes_non_file_nodes(self, tmp_path):
        from prep.services.pipeline.workers import (
            _compute_deepening_override_keys_from_disk,
        )

        idx = tmp_path / "idx"
        repo = tmp_path / "repo"
        idx.mkdir()
        repo.mkdir()

        (repo / "a.py").write_text("content\n")
        (idx / "trace_nodes.jsonl").write_text(
            json.dumps({"id": "file:a.py", "kind": "file", "file_path": "a.py"})
            + "\n"
            + json.dumps({"id": "sym:Foo", "kind": "symbol", "file_path": "a.py"})
            + "\n"
            + json.dumps({"id": "sec:1", "kind": "section", "file_path": "doc.md"})
            + "\n",
            encoding="utf-8",
        )
        (idx / "trace_epistemic.jsonl").write_text(
            json.dumps({"node_id": "file:a.py", "pass_number": 3})
            + "\n",
            encoding="utf-8",
        )

        total, processed = _compute_deepening_override_keys_from_disk(idx, repo)
        assert total == 1  # only file: counted


class TestSkipPathEmitsOverrideKeys:
    """Source-regex pins on the _deepening_worker skip path."""

    def _skip_region(self) -> str:
        from pathlib import Path
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        # Take just the front of the function — skip path is near the top.
        return body[idx:idx + 3500]

    def test_skip_path_calls_disk_helper(self):
        region = self._skip_region()
        assert "_compute_deepening_override_keys_from_disk(" in region, (
            "PR-T regression: skip path must call "
            "_compute_deepening_override_keys_from_disk so override "
            "keys fire even when LLM is unavailable."
        )

    def test_skip_path_emits_override_keys_into_result(self):
        region = self._skip_region()
        # Pin the skip result dict carries the override keys when
        # the disk helper succeeds.
        assert "skip_result[\"_expected_total\"]" in region, (
            "PR-T regression: skip path must add _expected_total to "
            "the skip result dict so the orchestrator helper hoists "
            "it into manifest.quality."
        )
        assert "skip_result[\"_processed_count\"]" in region, (
            "PR-T regression: skip path must add _processed_count "
            "for the orchestrator override."
        )

    def test_skip_path_handles_disk_helper_failure(self):
        region = self._skip_region()
        # The conditional guard `if skip_total is not None` must
        # gate the assignment so failure falls back to JSONL
        # semantics (the pre-PR-T behavior — degradation, not crash).
        assert "skip_total is not None" in region, (
            "PR-T regression: skip path must gate override-key "
            "emission on disk-helper success. On failure the worker "
            "should degrade silently to JSONL semantics, not crash."
        )


# NOTE: producer-only scope.
# The consumer-side contract (orchestrator helper reading the same
# keys) is intentionally NOT pinned here because PR-S branches off
# main while the consumer (PR-Q's _apply_worker_quality_overrides)
# is on an independent branch. When both PRs merge to main, the
# producer-consumer end-to-end behavior is covered by
# test_phase145_pr_q_quality_overrides.py's
# TestPRQEndToEndProducerConsumer. Extending that test to also cover
# the deepening worker is a logical follow-up after both branches
# land.
