"""Tests for the Ollama capacity probe used to seed new cloud slots."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from prep.services.pipeline.ollama_probe import probe_ollama_concurrency


def test_env_var_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "12")
    # Even if the API would say something else, env wins.
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{}, {}, {}]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 12


def test_env_var_invalid_falls_through_to_api(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "not-a-number")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{}, {}, {}, {}, {}, {}, {}]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 7


def test_env_unset_uses_ps_count(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{} for _ in range(10)]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 10


def test_falls_back_to_default_on_error(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.side_effect = Exception("connection refused")
        assert probe_ollama_concurrency("http://localhost:11434") == 5


def test_ps_returns_zero_models_falls_to_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": []}
        )
        # Zero loaded models means we have no capacity hint — use default.
        assert probe_ollama_concurrency("http://localhost:11434") == 5


def test_clamps_to_reasonable_range(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "9999")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(status_code=200, json=lambda: {"models": []})
        # Wildly large values get clamped — 256 is more than any real provider.
        assert probe_ollama_concurrency("http://localhost:11434") == 256

    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "-3")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(status_code=200, json=lambda: {"models": []})
        # Negative falls through to API → empty → default.
        assert probe_ollama_concurrency("http://localhost:11434") == 5


def test_host_without_scheme_gets_http_added(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    captured = {}
    def fake_get(url, timeout):
        captured["url"] = url
        return MagicMock(status_code=200, json=lambda: {"models": [{}, {}, {}, {}]})
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.side_effect = fake_get
        result = probe_ollama_concurrency("localhost:11434")
    assert result == 4
    assert captured["url"] == "http://localhost:11434/api/ps"


def test_host_with_https_scheme_preserved(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    captured = {}
    def fake_get(url, timeout):
        captured["url"] = url
        return MagicMock(status_code=200, json=lambda: {"models": [{}, {}]})
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.side_effect = fake_get
        result = probe_ollama_concurrency("https://ollama.example.com")
    assert result == 2
    assert captured["url"] == "https://ollama.example.com/api/ps"
