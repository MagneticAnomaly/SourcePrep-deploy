# Part 14 — Swarm capacity silently halved when supports_auto_detect is unknown

> **Status:** **FIXED 2026-05-18** — 5 regression tests landed.
> **Trigger:** user dogfood 2026-05-18 ("swarm was maxing out at 5 in
> the later stages... and again it's rarely using all 10 available
> resources").

## The bug

`ComputeSlot.dynamic_capacity` for cloud slots had three branches:

```python
if is_cloud and self.max_concurrent > 0 and self.supports_auto_detect is False:
    return max(1, self.max_concurrent)            # no-auto-detect → use max
if is_cloud and self.max_concurrent > 0:
    return min(max(1, self.max_concurrent), max(1, self.current_limit))  # AIMD-bound
if is_cloud:
    return max(1, self.current_limit)             # unbounded discovery
```

The first branch requires the **explicit** boolean `False`. The
dataclass default for `supports_auto_detect` is `None`, and the
populated path (`configure_node` line 513-518) can leave it as
`None` when `_provider_supports_auto_detect` raises — and that
function falls through to "no saved endpoint matches; defaulting to
auto_detect=True" if settings aren't loaded yet.

Race condition: configure_node runs at slot construction. If
settings_store hasn't finished loading (cold daemon, fast startup
sequence, slot reseed during pipeline retry), `_provider_supports_auto_detect`
returns the legacy `True`. The slot is stuck. The first branch
never fires. The second branch caps at
`min(max_concurrent=10, current_limit=5) = 5` — the jumpstart seed
silently halves the user's stated plan tier.

For providers documented as no-auto-detect (Ollama Cloud, Gemini,
Kimi via Moonshot), the user's `max_concurrent` is supposed to be
authoritative — see the long comment at `scheduler.py:203-217`.
But the implementation only honored that intent when the boolean
was *explicitly* False, not when it was unknown.

## Dogfood symptom

User observed swarm stages running at 5/10 even though Ollama Cloud
"Max" tier is 10 concurrent. Earlier in the session the swarm hit
10; after a daemon reseed (likely a `maturin develop` rebuild for
Part 02's Rust patch), it dropped back to 5 and stayed there.

## Fix

Change the no-auto-detect short-circuit to fire when
`supports_auto_detect is not True` — covering both `False` (explicit)
and `None` (unknown). When we don't know, the conservative default is
to honor the user's stated cap, not let AIMD's jumpstart silently
halve it.

```python
if is_cloud and self.max_concurrent > 0 and self.supports_auto_detect is not True:
    return max(1, self.max_concurrent)
```

Providers with confirmed auto-detect (OpenAI, Anthropic) still get
the AIMD-bounded path — `True is not True` is False, so the
short-circuit skips. No regression for header-rich providers.

## Tests

`tests/test_dynamic_capacity_unknown_autodetect.py` (5 new):

- `test_explicit_no_auto_detect_returns_max` — False bypasses AIMD (unchanged)
- `test_unknown_auto_detect_returns_max` — **None now bypasses AIMD too** (the fix)
- `test_explicit_auto_detect_returns_aimd_bound` — True keeps AIMD (unchanged)
- `test_local_slot_unaffected` — local slots are VRAM-bound (unchanged)
- `test_cloud_zero_max_concurrent_unbounded` — Auto sentinel (unchanged)

5/5 pass. Two unrelated pre-existing failures in `test_pipeline_scheduler.py`
verified to predate this fix (`git stash` + re-run confirmed).

## Why the symptom matters beyond Ollama Cloud

The race condition can hit any cloud slot where settings load lags
the slot construction. Pre-Phase-136 the symptom was masked because
AIMD eventually grows current_limit back toward max_concurrent — but
for **no-auto-detect providers** (Ollama Cloud, Gemini, Kimi-direct),
AIMD is intentionally disabled. The slot is stuck at 5 forever,
across the entire daemon lifecycle.

## Cross-refs

- `scheduler.py:_provider_supports_auto_detect` (the lookup that
  can return True when settings aren't loaded)
- `concurrency_limits.json` — provider tier table (ollama_cloud +
  google_gemini + moonshot_kimi marked `auto_detect: false`)
- Phase 119 §A 8 — the "no-auto-detect cloud override" design intent
  this Part hardens against the unknown-flag case.
