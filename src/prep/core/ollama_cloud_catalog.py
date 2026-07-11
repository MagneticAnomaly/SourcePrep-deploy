"""Curated candidate list of Ollama Cloud (``:cloud``) models.

Why this exists
----------------
Ollama's ``GET /api/tags`` only enumerates models the user has explicitly
*subscribed/pinned* to their Ollama Cloud account. Cloud models that are
available **on demand** (Ollama serves them via ``/api/show`` and chat, but
the user never "added" them) do NOT appear in ``/api/tags``. The AI Gateway
model picker reads only ``/api/tags``, so on-demand cloud models like
``glm-5.2:cloud`` are invisible to it even though Ollama happily serves them.

There is no "list all Ollama Cloud models" API anywhere — not on the local
Ollama server (``/api/library``, ``/api/search`` all 404; ``/v1/models`` is
identical to ``/api/tags``) and not on ollama.com (no public catalog
endpoint). So the only way to surface on-demand cloud models in the picker
is to maintain a *curated candidate list* and verify each candidate against
the user's Ollama via ``POST /api/show``.

``/api/show`` rejects unknown/inaccessible cloud models
(``{"error": "model 'X' not found"}``) and returns full metadata for
accessible ones. That verification is the safety net: **we never display a
cloud model the user's Ollama cannot actually serve.**

Maintenance
-----------
This list is NOT a live catalog — it is a best-effort set of known Ollama
Cloud model tags. When Ollama publishes new cloud models, add them here.
Bump ``OLLAMA_CLOUD_CATALOG_VERSION`` whenever the list changes so the
backend's per-endpoint probe cache is invalidated.

Because verification prunes anything inaccessible, a stale or over-broad
list never shows broken models — it only risks *missing* a newly added
cloud model until someone updates this file.
"""

from __future__ import annotations

# Bump when OLLAMA_CLOUD_CANDIDATES changes. Used as part of the probe cache
# key so the cache is invalidated automatically when the catalog is updated.
OLLAMA_CLOUD_CATALOG_VERSION = 1

# Candidate Ollama Cloud model tags to probe via /api/show.
#
# Seed set: concrete tags known to be served by Ollama Cloud (observed in a
# live subscription set + on-demand `glm-5.2:cloud`), plus a modest set of
# plausible candidates drawn from the cloud-only families already encoded in
# ``batch_profiles._OLLAMA_CLOUD_PATTERNS`` (kimi, gemini, glm, gpt-[45],
# claude, mistral-large, command-r). Inaccessible candidates are pruned by
# /api/show verification, so broad inclusion is safe — but every candidate
# costs one /api/show call, so keep the list bounded.
OLLAMA_CLOUD_CANDIDATES: tuple[str, ...] = (
    # ── Known-good (observed live) ────────────────────────────────────
    "glm-5.2:cloud",
    "kimi-k2.5:cloud",
    "kimi-k2.6:cloud",
    "kimi-k2.7-code:cloud",
    "gemini-3-flash-preview:cloud",
    "qwen3-coder-next:cloud",

    # ── Plausible candidates from known cloud-only families ───────────
    # pruned automatically by /api/show if not served on this account.
    "gpt-5:cloud",
    "gpt-4.1:cloud",
    "claude-opus-4.8:cloud",
    "claude-sonnet-5:cloud",
    "claude-haiku-4.5:cloud",
    "gemini-3-pro:cloud",
    "deepseek-v3.5:cloud",
    "deepseek-r1:cloud",
    "mistral-large:cloud",
    "command-r:cloud",
)
