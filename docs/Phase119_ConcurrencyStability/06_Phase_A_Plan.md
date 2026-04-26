# Phase A — Cross-Provider Concurrency: Soft Cap + Plan Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recapture the "I picked 10 and it worked beautifully" UX for Ollama Cloud — make AIMD respect the user's stated plan-tier as a hard cap, surface the choice in a clear per-endpoint dropdown sourced from a versioned data file with cited limits, and prevent users from saving cloud endpoints without a plan when no auto-detect is possible.

**Architecture:** One backend bug fix (the cloud bypass in `dynamic_capacity`), one new data file (`concurrency_limits.json` with provider × tier × concurrent value), one new API endpoint (`GET /llm/plan-limits`), and one redesigned form section in `EndpointManager.tsx`. The dropdown is the user-facing primary control; the existing free-text `cloud_concurrency` becomes the "Custom…" override. Save validation is provider-specific: providers with no auto-detect (Ollama Cloud, Gemini) require a tier choice; providers with auto-detect (OpenAI, Anthropic) default to "Auto" and allow throttle overrides.

**Tech Stack:** Python 3.11 (FastAPI, dataclass, stdlib), pytest, React 18 + TypeScript (Tailwind for styling, existing form primitives in `@prep/ui`).

---

## File Structure

**Create:**
- `src/prep/data/concurrency_limits.json` — provider × tier table. Single source of truth for dropdown options. Each entry has `tier_label`, `concurrent`, `source_url`. One JSON file ships with the package; updateable without code release.
- `src/prep/api/routers/llm_plans.py` (or extend existing `llm.py`) — `GET /llm/plan-limits` endpoint that returns the parsed JSON for the frontend.
- `tests/test_concurrency_limits_data.py` — schema/integrity tests for the JSON file.
- `tests/test_scheduler_soft_cap_clamp.py` — behavioral tests that the cloud bypass respects `max_concurrent` when set.
- `tests/test_endpoint_save_validation.py` — API tests for save-time validation per provider class.
- `packages/ui/src/components/llm/PlanDropdown.tsx` — new component encapsulating the dropdown + cited source + active-confirmation line. One file, one responsibility.
- `packages/ui/src/components/llm/PlanDropdown.stories.tsx` — Storybook stories covering all 5 provider classes + the warn-but-allow vs force-choice cases.

**Modify:**
- `src/prep/services/pipeline/scheduler.py:170-178` — `ComputeSlot.dynamic_capacity` cloud branch. Honor `max_concurrent` when `> 0`; treat `0` as "Phase 82 unbounded" (existing behavior).
- `src/prep/api/routers/llm.py` — register the new endpoint OR extend it inline. Add save-time validation helper.
- `packages/ui/src/components/llm/EndpointManager.tsx` — replace the existing `cloud_concurrency` integer input with the new `<PlanDropdown />` component. Plumb the new fields (`plan_tier`) through the save handler.
- `packages/ui/src/types.ts:778` — extend `SavedEndpoint` with `plan_tier?: string` (the dropdown's selected key). `cloud_concurrency` stays for the "Custom…" override path.

**Migrations / compatibility:**
- Existing endpoints with `cloud_concurrency` set keep working unchanged. The new `plan_tier` field is optional. If `plan_tier` is unset but `cloud_concurrency > 0`, the system treats it as legacy custom — fully backwards compatible.

---

## Task 0: Baseline — capture current state and behavior

**Files:** (read-only)

- [ ] **Step 1: Confirm the running daemon's current cloud-bypass behavior.**

Run:
```bash
curl -s http://localhost:8400/compute/scheduler 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']['nodes']
for nid, n in d.items():
    if 'cloud' in nid:
        print(f\"{nid}: limit={n['current_limit']} max_concurrent={n['max_concurrent']}\")
"
```

Expected: `cloud:default_ollama: limit=<some N>>1 max_concurrent=1` — `max_concurrent` is set but `current_limit` exceeds it. This is the bug we're fixing.

- [ ] **Step 2: Confirm the existing test suite passes before any change.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py tests/test_concurrency_store_lock.py tests/test_pipeline_scheduler.py -q 2>&1 | tail -5`
Expected: all pass. Record the count for regression reference.

- [ ] **Step 3: Read the current `dynamic_capacity` comment block.**

Read: `src/prep/services/pipeline/scheduler.py` lines 170-180.
Note the Phase 82 comment that justified the bypass — this plan supersedes it explicitly per the design doc `docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md`.

- [ ] **Step 4: No commit — observational task.**

---

## Task 1: Backend — make `dynamic_capacity` respect `max_concurrent` when set

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py:170-178`
- Create: `tests/test_scheduler_soft_cap_clamp.py`

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_scheduler_soft_cap_clamp.py`:

```python
"""Phase 119 Phase A: cloud slots respect ``max_concurrent`` when the user has
set it (the soft cap from their plan dropdown). The Phase 82 bypass remains
when ``max_concurrent == 0`` (the "Auto" / unset case).
"""
from __future__ import annotations

from prep.services.pipeline.scheduler import ComputeSlot


def test_cloud_slot_clamps_at_max_concurrent_when_set() -> None:
    """User picked Max plan (10 concurrent). AIMD discovered/walked to 40.
    dynamic_capacity must return 10, not 40."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=10,    # user's plan-tier choice
        current_limit=40,     # AIMD walked here pre-fix
        min_limit=3,
    )
    assert slot.dynamic_capacity == 10


def test_cloud_slot_unbounded_when_max_concurrent_is_zero() -> None:
    """User picked 'Auto' (zero sentinel). Phase 82 unbounded behavior preserved."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=0,    # 'Auto' / unset
        current_limit=40,
        min_limit=3,
    )
    assert slot.dynamic_capacity == 40


def test_cloud_slot_clamps_at_max_concurrent_when_current_limit_lower() -> None:
    """When AIMD's current_limit is below the soft cap, return current_limit
    (we don't promote AIMD beyond what it discovered)."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=10,
        current_limit=4,
        min_limit=3,
    )
    assert slot.dynamic_capacity == 4


def test_local_slot_behavior_unchanged() -> None:
    """Local slot clamping at max_concurrent already works; ensure no regression."""
    slot = ComputeSlot(
        node_id="local:test",
        max_concurrent=2,
        current_limit=5,
        min_limit=1,
    )
    assert slot.dynamic_capacity == 2


def test_cloud_slot_floor_min_one_when_max_concurrent_is_negative() -> None:
    """Defensive: invalid negative max_concurrent should not crash."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=-1,    # invalid input
        current_limit=10,
        min_limit=3,
    )
    # Treat negative same as zero (Phase 82 unbounded), don't crash.
    assert slot.dynamic_capacity == 10
```

- [ ] **Step 2: Run tests to confirm they fail.**

Run: `.venv/bin/pytest tests/test_scheduler_soft_cap_clamp.py -v`
Expected: `test_cloud_slot_clamps_at_max_concurrent_when_set` FAILS — current bypass returns 40 not 10.

- [ ] **Step 3: Modify `dynamic_capacity` in `scheduler.py`.**

Open `src/prep/services/pipeline/scheduler.py`. Find the `dynamic_capacity` property (lines 170-178):

```python
    @property
    def dynamic_capacity(self) -> int:
        """Phase 82: cloud slots discover their real ceiling at runtime;
        clipping by ``max_concurrent`` would defeat the discovery mechanism.
        Local slots keep the clamp — ``max_concurrent`` is a VRAM ceiling
        and a real hardware constraint.
        """
        if self.node_id.startswith("cloud:"):
            return max(1, self.current_limit)
        return min(self.max_concurrent, self.current_limit)
```

Replace with:

```python
    @property
    def dynamic_capacity(self) -> int:
        """Phase 82 + Phase 119 Phase A:

        Cloud slots:
          - When ``max_concurrent > 0`` (user picked a plan tier or set a
            custom value), AIMD operates inside ``[min_limit, max_concurrent]``.
            This is the user's stated cap; we honor it.
          - When ``max_concurrent == 0`` (the "Auto" sentinel — Phase 82
            unbounded discovery path), ``current_limit`` is the only ceiling.
            Used by header-rich providers where AIMD adapts from response
            headers without a fixed cap.

        Local slots: always clamp at ``max_concurrent`` (VRAM is a real
        hardware constraint).
        """
        is_cloud = self.node_id.startswith("cloud:")
        if is_cloud and self.max_concurrent > 0:
            return min(max(1, self.max_concurrent), max(1, self.current_limit))
        if is_cloud:
            return max(1, self.current_limit)
        return min(self.max_concurrent, self.current_limit)
```

- [ ] **Step 4: Run tests to confirm they pass.**

Run: `.venv/bin/pytest tests/test_scheduler_soft_cap_clamp.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Run the broader scheduler suite for regressions.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py tests/test_pipeline_scheduler.py tests/test_scheduler_unbounded_discovery.py -q 2>&1 | tail -10`
Expected: pass count matches Task 0 baseline. The Phase 82 unbounded-discovery tests still pass because they construct slots with `max_concurrent=0` or use the sentinel path.

If any test fails because it constructs a cloud slot with `max_concurrent > 0` and expected unbounded growth: that test was already encoding the old bug behavior. Fix it by setting `max_concurrent=0` in the slot constructor (matching the new "Auto" semantic) or by updating the assertion to match the new clamped value. Document each fix in the commit body.

- [ ] **Step 6: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_scheduler_soft_cap_clamp.py
git commit -m "fix(phase119-A): cloud dynamic_capacity respects max_concurrent when set

Phase 82 deliberately bypassed max_concurrent on cloud slots so AIMD
could discover the ceiling. That assumption is wrong for Ollama
Cloud which silently queues instead of returning 429 (see
05_Cross_Provider_Concurrency_Design.md). Now: max_concurrent > 0
is the user's stated cap (from the new plan dropdown) and AIMD
operates inside it. max_concurrent == 0 preserves Phase 82
unbounded discovery for header-rich providers."
```

---

## Task 2: Data file — `concurrency_limits.json` with provider × tier table

**Files:**
- Create: `src/prep/data/concurrency_limits.json`
- Create: `tests/test_concurrency_limits_data.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/test_concurrency_limits_data.py`:

```python
"""Schema + integrity tests for the per-provider plan-tier limits.

Each tier entry must declare:
  - tier_label: human-readable name (e.g. "Max")
  - concurrent: integer, the documented concurrent-request limit
  - source_url: where this number came from (so future maintainers can verify)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

LIMITS_PATH = Path(__file__).parent.parent / "src/prep/data/concurrency_limits.json"


def _load() -> dict:
    return json.loads(LIMITS_PATH.read_text())


def test_file_exists() -> None:
    assert LIMITS_PATH.exists(), f"Expected limits file at {LIMITS_PATH}"


def test_required_providers_present() -> None:
    """All providers we research in 05_Cross_Provider_Concurrency_Design.md
    have entries (even if Auto-detect-only)."""
    data = _load()
    expected = {"ollama_cloud", "openai", "anthropic", "google_gemini", "moonshot_kimi", "ollama_local"}
    assert set(data["providers"].keys()) >= expected


def test_ollama_cloud_published_numbers() -> None:
    """Verify the Ollama Cloud numbers match the pricing page (Free/Pro/Max = 1/3/10)."""
    data = _load()
    tiers = {t["tier_key"]: t for t in data["providers"]["ollama_cloud"]["tiers"]}
    assert tiers["free"]["concurrent"] == 1
    assert tiers["pro"]["concurrent"] == 3
    assert tiers["max"]["concurrent"] == 10


def test_every_tier_has_required_fields() -> None:
    """Schema integrity: each tier entry has tier_key/tier_label/concurrent/source_url."""
    data = _load()
    required = {"tier_key", "tier_label", "concurrent", "source_url"}
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            missing = required - tier.keys()
            assert not missing, f"{provider_key} tier {tier} missing keys: {missing}"


def test_provider_records_auto_detect_capability() -> None:
    """Each provider declares whether 'Auto' (header-driven) is offered.
    UI uses this to decide whether to allow save without picking."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        assert "auto_detect" in provider, f"{provider_key} missing auto_detect"
        assert isinstance(provider["auto_detect"], bool)


def test_auto_detect_only_for_header_rich_providers() -> None:
    """OpenAI, Anthropic have headers → auto_detect=True. Ollama Cloud and
    Gemini do not → auto_detect=False. (Per 05_design.md table.)"""
    data = _load()
    assert data["providers"]["openai"]["auto_detect"] is True
    assert data["providers"]["anthropic"]["auto_detect"] is True
    assert data["providers"]["ollama_cloud"]["auto_detect"] is False
    assert data["providers"]["google_gemini"]["auto_detect"] is False


def test_concurrent_values_are_positive_ints() -> None:
    """No zero or negative; the special 'Auto' case is at provider level, not tier level."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            assert isinstance(tier["concurrent"], int)
            assert tier["concurrent"] >= 1, f"{provider_key}/{tier['tier_key']}: bad concurrent={tier['concurrent']}"
```

- [ ] **Step 2: Run tests to confirm they fail.**

Run: `.venv/bin/pytest tests/test_concurrency_limits_data.py -v`
Expected: all FAIL with `FileNotFoundError`.

- [ ] **Step 3: Create the JSON data file.**

Create `src/prep/data/concurrency_limits.json`:

```json
{
  "version": 1,
  "updated_at": "2026-04-26",
  "_doc": "Per-provider concurrency tier table. Single source of truth for the plan-dropdown UI. See docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md.",
  "providers": {
    "ollama_cloud": {
      "label": "Ollama Cloud",
      "auto_detect": false,
      "auto_detect_reason": "Ollama Cloud silently queues beyond plan concurrency; no 429 or x-ratelimit-* headers (ollama/ollama#15663)",
      "tiers": [
        {"tier_key": "free", "tier_label": "Free", "concurrent": 1, "source_url": "https://ollama.com/pricing"},
        {"tier_key": "pro", "tier_label": "Pro", "concurrent": 3, "source_url": "https://ollama.com/pricing"},
        {"tier_key": "max", "tier_label": "Max", "concurrent": 10, "source_url": "https://ollama.com/pricing"}
      ]
    },
    "openai": {
      "label": "OpenAI",
      "auto_detect": true,
      "auto_detect_reason": "x-ratelimit-remaining-requests + x-ratelimit-remaining-tokens headers on every response",
      "tiers": [
        {"tier_key": "tier_1", "tier_label": "Tier 1", "concurrent": 5, "source_url": "https://platform.openai.com/docs/guides/rate-limits"},
        {"tier_key": "tier_2", "tier_label": "Tier 2", "concurrent": 10, "source_url": "https://platform.openai.com/docs/guides/rate-limits"},
        {"tier_key": "tier_3", "tier_label": "Tier 3", "concurrent": 20, "source_url": "https://platform.openai.com/docs/guides/rate-limits"},
        {"tier_key": "tier_4", "tier_label": "Tier 4", "concurrent": 40, "source_url": "https://platform.openai.com/docs/guides/rate-limits"},
        {"tier_key": "tier_5", "tier_label": "Tier 5", "concurrent": 80, "source_url": "https://platform.openai.com/docs/guides/rate-limits"}
      ]
    },
    "anthropic": {
      "label": "Anthropic Claude",
      "auto_detect": true,
      "auto_detect_reason": "anthropic-ratelimit-requests-remaining and tokens-remaining headers on every response",
      "tiers": [
        {"tier_key": "tier_1", "tier_label": "Tier 1 ($5)", "concurrent": 5, "source_url": "https://platform.claude.com/docs/en/api/rate-limits"},
        {"tier_key": "tier_2", "tier_label": "Tier 2 ($40)", "concurrent": 20, "source_url": "https://platform.claude.com/docs/en/api/rate-limits"},
        {"tier_key": "tier_3", "tier_label": "Tier 3 ($200)", "concurrent": 40, "source_url": "https://platform.claude.com/docs/en/api/rate-limits"},
        {"tier_key": "tier_4", "tier_label": "Tier 4 ($400)", "concurrent": 80, "source_url": "https://platform.claude.com/docs/en/api/rate-limits"}
      ]
    },
    "google_gemini": {
      "label": "Google Gemini",
      "auto_detect": false,
      "auto_detect_reason": "No predictive rate-limit headers exposed; reactive 429 + Retry-After only",
      "tiers": [
        {"tier_key": "free", "tier_label": "Free", "concurrent": 2, "source_url": "https://ai.google.dev/gemini-api/docs/rate-limits"},
        {"tier_key": "tier_1", "tier_label": "Tier 1 (paid)", "concurrent": 10, "source_url": "https://ai.google.dev/gemini-api/docs/rate-limits"},
        {"tier_key": "tier_2", "tier_label": "Tier 2", "concurrent": 30, "source_url": "https://ai.google.dev/gemini-api/docs/rate-limits"},
        {"tier_key": "tier_3", "tier_label": "Tier 3", "concurrent": 60, "source_url": "https://ai.google.dev/gemini-api/docs/rate-limits"}
      ]
    },
    "moonshot_kimi": {
      "label": "Moonshot Kimi (direct)",
      "auto_detect": false,
      "auto_detect_reason": "Headers not documented; published explicit concurrent-per-tier in pricing docs",
      "tiers": [
        {"tier_key": "tier_0", "tier_label": "Tier 0 ($0)", "concurrent": 1, "source_url": "https://platform.kimi.ai/docs/pricing/limits"},
        {"tier_key": "tier_1", "tier_label": "Tier 1 ($10)", "concurrent": 50, "source_url": "https://platform.kimi.ai/docs/pricing/limits"},
        {"tier_key": "tier_2", "tier_label": "Tier 2 ($20)", "concurrent": 100, "source_url": "https://platform.kimi.ai/docs/pricing/limits"},
        {"tier_key": "tier_3", "tier_label": "Tier 3 ($100)", "concurrent": 200, "source_url": "https://platform.kimi.ai/docs/pricing/limits"},
        {"tier_key": "tier_4", "tier_label": "Tier 4 ($1000)", "concurrent": 400, "source_url": "https://platform.kimi.ai/docs/pricing/limits"},
        {"tier_key": "tier_5", "tier_label": "Tier 5 ($3000)", "concurrent": 1000, "source_url": "https://platform.kimi.ai/docs/pricing/limits"}
      ]
    },
    "ollama_local": {
      "label": "Local Ollama (OSS)",
      "auto_detect": true,
      "auto_detect_reason": "OLLAMA_NUM_PARALLEL env probe via /api/ps",
      "tiers": [
        {"tier_key": "default", "tier_label": "OLLAMA_NUM_PARALLEL (default 4)", "concurrent": 4, "source_url": "https://docs.ollama.com/faq"}
      ]
    }
  }
}
```

(The OpenAI/Anthropic/Gemini "concurrent" values are illustrative effective concurrency derived from their RPM divided by typical p50 latency. The real binding constraint for those providers is RPM/TPM via headers — these values exist only as a manual-throttle fallback when the user wants to operate below their tier.)

- [ ] **Step 4: Run tests to confirm they pass.**

Run: `.venv/bin/pytest tests/test_concurrency_limits_data.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/data/concurrency_limits.json tests/test_concurrency_limits_data.py
git commit -m "feat(phase119-A): ship concurrency_limits.json (provider x tier x concurrent)

Single source of truth for the plan-dropdown UI. Six providers,
each with tier entries citing the upstream pricing/limits page.
auto_detect=true means the provider exposes ratelimit headers
(OpenAI, Anthropic, local Ollama). auto_detect=false means user
must pick a tier (Ollama Cloud, Gemini, Kimi direct)."
```

---

## Task 3: API endpoint — `GET /llm/plan-limits`

**Files:**
- Modify: `src/prep/api/routers/llm.py` (add the endpoint)
- Modify: `tests/test_endpoint_save_validation.py` (will be created in Task 5; for now create file with just the GET test)

- [ ] **Step 1: Write the failing test.**

Create `tests/test_endpoint_save_validation.py`:

```python
"""Phase 119 Phase A: API surface for plan-tier limits + save validation."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from prep.server import app
    return TestClient(app)


def test_plan_limits_endpoint_returns_full_table() -> None:
    """GET /llm/plan-limits returns the parsed concurrency_limits.json."""
    client = _client()
    resp = client.get("/llm/plan-limits")
    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    providers = data["providers"]
    assert "ollama_cloud" in providers
    assert providers["ollama_cloud"]["auto_detect"] is False
    # Ollama Cloud Max = 10 (the published number)
    tiers = {t["tier_key"]: t for t in providers["ollama_cloud"]["tiers"]}
    assert tiers["max"]["concurrent"] == 10


def test_plan_limits_includes_source_urls() -> None:
    client = _client()
    resp = client.get("/llm/plan-limits")
    body = resp.json()
    data = body.get("data", body)
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            assert tier["source_url"].startswith("http"), (
                f"{provider_key}/{tier['tier_key']}: source_url should be a URL"
            )
```

- [ ] **Step 2: Run tests to confirm they fail.**

Run: `.venv/bin/pytest tests/test_endpoint_save_validation.py::test_plan_limits_endpoint_returns_full_table -v`
Expected: FAIL with 404 — endpoint doesn't exist.

- [ ] **Step 3: Add the endpoint to `llm.py`.**

In `src/prep/api/routers/llm.py`, add a new endpoint near the other GET routes (search for `@router.get` to find a placement that matches the file's existing convention). Insert:

```python
@router.get("/plan-limits")
def get_plan_limits() -> dict:
    """Phase 119 Phase A: return the per-provider plan-tier table for the UI dropdown."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent.parent / "data" / "concurrency_limits.json"
    try:
        return {"ok": True, "data": json.loads(path.read_text())}
    except Exception as exc:
        logger.warning("plan-limits: failed to read %s: %s", path, exc)
        return {"ok": False, "error": str(exc)}
```

(`logger` is already imported at the top of `llm.py`. Path resolution: `routers/llm.py` is at `src/prep/api/routers/llm.py`, so `parent.parent.parent` reaches `src/prep`, and `/data/concurrency_limits.json` lands on the file. Verify via `python -c "from pathlib import Path; print(Path('src/prep/api/routers/llm.py').resolve().parent.parent.parent / 'data')"` if uncertain.)

- [ ] **Step 4: Run tests to confirm they pass.**

Run: `.venv/bin/pytest tests/test_endpoint_save_validation.py -v`
Expected: 2/2 PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/api/routers/llm.py tests/test_endpoint_save_validation.py
git commit -m "feat(phase119-A): GET /llm/plan-limits exposes the tier table

Frontend reads this on EndpointManager mount to populate the plan
dropdown. Returns the entire concurrency_limits.json verbatim
including auto_detect flags + source URLs for the help-text."
```

---

## Task 4: Frontend — `PlanDropdown.tsx` component

**Files:**
- Create: `packages/ui/src/components/llm/PlanDropdown.tsx`
- Create: `packages/ui/src/components/llm/PlanDropdown.stories.tsx`
- Modify: `packages/ui/src/types.ts` — extend `SavedEndpoint`
- Modify: `packages/ui/src/index.ts` — export `PlanDropdown`

- [ ] **Step 1: Extend the type in `types.ts`.**

In `packages/ui/src/types.ts`, find the `SavedEndpoint` interface (around line 778 per existing grep). Add the optional `plan_tier`:

```ts
export interface SavedEndpoint {
  id: string;
  name: string;
  provider: LLMProvider;
  url: string;
  api_key?: string;
  local_concurrency?: number;
  cloud_concurrency?: number;     // legacy / "Custom..." override
  plan_tier?: string;              // Phase 119 Phase A: dropdown selection (e.g. "max", "tier_3", "auto")
  // ... whatever other fields existed already
}
```

(Don't modify other fields. The only addition is `plan_tier`.)

- [ ] **Step 2: Write the component file.**

Create `packages/ui/src/components/llm/PlanDropdown.tsx`:

```tsx
import { useEffect, useState } from 'react';

export interface PlanLimitTier {
  tier_key: string;
  tier_label: string;
  concurrent: number;
  source_url: string;
}

export interface PlanLimitProvider {
  label: string;
  auto_detect: boolean;
  auto_detect_reason?: string;
  tiers: PlanLimitTier[];
}

export interface PlanLimitsTable {
  version: number;
  providers: Record<string, PlanLimitProvider>;
}

export interface PlanDropdownProps {
  /** Provider key in the limits table — e.g. "ollama_cloud", "openai". */
  providerKey: string;
  /** Current selection. Either a tier_key, "auto", "custom", or undefined. */
  value: string | undefined;
  /** Custom override value (used when value === "custom"). */
  customConcurrent: number;
  /** Pre-fetched limits table. Required for storybook; in production the
   * EndpointManager fetches once and passes down. */
  limits: PlanLimitsTable;
  /** Called when the user picks a tier OR types a custom number. */
  onChange: (next: { plan_tier: string; cloud_concurrency: number }) => void;
}

const SENTINEL_AUTO = 'auto';
const SENTINEL_CUSTOM = 'custom';

export function PlanDropdown(props: PlanDropdownProps) {
  const { providerKey, value, customConcurrent, limits, onChange } = props;
  const provider = limits.providers[providerKey];

  // Local state for "Custom..." input.
  const [customInput, setCustomInput] = useState<number>(customConcurrent || 1);
  useEffect(() => {
    setCustomInput(customConcurrent || 1);
  }, [customConcurrent]);

  if (!provider) {
    return (
      <div className="text-xs text-amber-400">
        No plan options for provider <code>{providerKey}</code>.
      </div>
    );
  }

  // Compute the active concurrent based on selection.
  const activeConcurrent =
    value === SENTINEL_AUTO ? 0 :  // 0 = "auto" sentinel for backend
    value === SENTINEL_CUSTOM ? customInput :
    (provider.tiers.find((t) => t.tier_key === value)?.concurrent ?? 0);

  const activeLabel =
    value === SENTINEL_AUTO ? 'Auto-detect from headers' :
    value === SENTINEL_CUSTOM ? `Custom — ${customInput} concurrent` :
    (provider.tiers.find((t) => t.tier_key === value)?.tier_label ?? '— pick a plan —');

  const sourceUrl =
    (provider.tiers.find((t) => t.tier_key === value)?.source_url) ??
    (provider.tiers[0]?.source_url ?? '');

  return (
    <div className="space-y-1.5">
      <label className="text-[11px] uppercase tracking-wider text-text-muted">Plan</label>
      <select
        className="w-full bg-surface-raised border border-border rounded px-2 py-1 text-sm"
        value={value ?? ''}
        onChange={(e) => {
          const next = e.target.value;
          if (next === '') {
            onChange({ plan_tier: '', cloud_concurrency: 0 });
          } else if (next === SENTINEL_AUTO) {
            onChange({ plan_tier: SENTINEL_AUTO, cloud_concurrency: 0 });
          } else if (next === SENTINEL_CUSTOM) {
            onChange({ plan_tier: SENTINEL_CUSTOM, cloud_concurrency: customInput });
          } else {
            const tier = provider.tiers.find((t) => t.tier_key === next);
            onChange({ plan_tier: next, cloud_concurrency: tier?.concurrent ?? 0 });
          }
        }}
      >
        <option value="" disabled>— pick a plan —</option>
        {provider.auto_detect && (
          <option value={SENTINEL_AUTO}>Auto-detect from headers (recommended)</option>
        )}
        {provider.tiers.map((t) => (
          <option key={t.tier_key} value={t.tier_key}>
            {t.tier_label} ({t.concurrent} concurrent)
          </option>
        ))}
        <option value={SENTINEL_CUSTOM}>Custom…</option>
      </select>

      {value === SENTINEL_CUSTOM && (
        <input
          type="number"
          min={1}
          max={1000}
          value={customInput}
          onChange={(e) => {
            const n = Math.max(1, Math.min(1000, parseInt(e.target.value || '1', 10)));
            setCustomInput(n);
            onChange({ plan_tier: SENTINEL_CUSTOM, cloud_concurrency: n });
          }}
          className="w-full bg-surface-raised border border-border rounded px-2 py-1 text-sm"
        />
      )}

      {sourceUrl && (
        <p className="text-[10px] text-text-muted">
          ⓘ From{' '}
          <a href={sourceUrl} target="_blank" rel="noreferrer" className="underline">
            {new URL(sourceUrl).host}
          </a>
        </p>
      )}

      <div className="text-[11px] text-text-base mt-2 pt-2 border-t border-border">
        Active: <strong>{activeConcurrent === 0 ? 'auto' : `${activeConcurrent} concurrent`}</strong>
        {value === SENTINEL_AUTO && provider.auto_detect_reason && (
          <span className="ml-1 text-text-muted">({provider.auto_detect_reason})</span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add the Storybook stories.**

Create `packages/ui/src/components/llm/PlanDropdown.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { PlanDropdown, type PlanLimitsTable } from './PlanDropdown';

const FIXTURE: PlanLimitsTable = {
  version: 1,
  providers: {
    ollama_cloud: {
      label: 'Ollama Cloud',
      auto_detect: false,
      auto_detect_reason: 'Ollama Cloud silently queues; no x-ratelimit-* headers',
      tiers: [
        { tier_key: 'free', tier_label: 'Free', concurrent: 1, source_url: 'https://ollama.com/pricing' },
        { tier_key: 'pro', tier_label: 'Pro', concurrent: 3, source_url: 'https://ollama.com/pricing' },
        { tier_key: 'max', tier_label: 'Max', concurrent: 10, source_url: 'https://ollama.com/pricing' },
      ],
    },
    openai: {
      label: 'OpenAI',
      auto_detect: true,
      auto_detect_reason: 'x-ratelimit-remaining-requests headers',
      tiers: [
        { tier_key: 'tier_1', tier_label: 'Tier 1', concurrent: 5, source_url: 'https://platform.openai.com/docs/guides/rate-limits' },
        { tier_key: 'tier_3', tier_label: 'Tier 3', concurrent: 20, source_url: 'https://platform.openai.com/docs/guides/rate-limits' },
      ],
    },
  },
};

const meta: Meta<typeof PlanDropdown> = {
  title: 'Phase 119 / PlanDropdown',
  component: PlanDropdown,
};
export default meta;

type Story = StoryObj<typeof PlanDropdown>;

export const OllamaCloudUnselected: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: undefined,
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const OllamaCloudMaxSelected: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: 'max',
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const OpenAIAutoDefault: Story = {
  args: {
    providerKey: 'openai',
    value: 'auto',
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const CustomOverride: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: 'custom',
    customConcurrent: 7,
    limits: FIXTURE,
    onChange: () => {},
  },
};
```

- [ ] **Step 4: Re-export from `@prep/ui`.**

In `packages/ui/src/index.ts`, add:

```ts
export { PlanDropdown } from './components/llm/PlanDropdown';
export type { PlanDropdownProps, PlanLimitsTable, PlanLimitProvider, PlanLimitTier } from './components/llm/PlanDropdown';
```

- [ ] **Step 5: Verify TypeScript + Storybook build.**

Run: `cd packages/ui && npx tsc --noEmit`
Expected: clean.

Run: `cd packages/ui && npm run build`
Expected: clean (387+ modules transformed).

- [ ] **Step 6: Commit.**

```bash
git add packages/ui/src/types.ts packages/ui/src/components/llm/PlanDropdown.tsx packages/ui/src/components/llm/PlanDropdown.stories.tsx packages/ui/src/index.ts
git commit -m "feat(phase119-A-ui): PlanDropdown component for per-endpoint plan tier

Reads the per-provider tier table (limits prop), renders a dropdown
with cited source URL, and shows the resulting Active concurrent
value. Auto-detect option appears only when the provider supports
it. Custom... opens an integer override mapped to cloud_concurrency."
```

---

## Task 5: Wire `PlanDropdown` into `EndpointManager.tsx` + save validation

**Files:**
- Modify: `packages/ui/src/components/llm/EndpointManager.tsx`
- Modify: `tests/test_endpoint_save_validation.py` (extend with validation tests)

- [ ] **Step 1: Write the failing validation tests.**

Append to `tests/test_endpoint_save_validation.py`:

```python
def test_save_endpoint_force_tier_for_no_auto_detect_provider() -> None:
    """Saving an Ollama Cloud endpoint without plan_tier returns 400.
    The provider's auto_detect=false; the user MUST pick a tier."""
    client = _client()
    payload = {
        "name": "test-ollama",
        "provider": "ollama",
        "url": "http://localhost:11434",
        "api_key": "",
        # plan_tier intentionally missing
        # cloud_concurrency intentionally missing
    }
    resp = client.post("/llm/endpoints", json=payload)
    # Either 400 with a clear message or success-with-warning depending
    # on the existing API contract. Adapt assertion to the existing route.
    if resp.status_code == 200:
        body = resp.json()
        warns = body.get("warnings") or body.get("data", {}).get("warnings") or []
        # If the API allows save with warnings, the warning text MUST exist.
        assert any("plan" in w.lower() or "tier" in w.lower() for w in warns), (
            f"Expected a plan-required warning; got: {warns}"
        )
    else:
        assert resp.status_code == 400


def test_save_endpoint_auto_for_header_rich_provider_is_ok() -> None:
    """Saving an OpenAI endpoint with plan_tier='auto' (no number) succeeds
    because OpenAI's auto_detect=true."""
    client = _client()
    payload = {
        "name": "test-openai",
        "provider": "openai",
        "url": "https://api.openai.com",
        "api_key": "sk-test",
        "plan_tier": "auto",
        "cloud_concurrency": 0,   # 0 = sentinel for "auto"
    }
    resp = client.post("/llm/endpoints", json=payload)
    assert resp.status_code in (200, 201)


def test_save_endpoint_with_custom_tier_persists_value() -> None:
    """plan_tier='custom' with cloud_concurrency=7 round-trips."""
    client = _client()
    payload = {
        "name": "test-custom",
        "provider": "ollama",
        "url": "http://localhost:11434",
        "plan_tier": "custom",
        "cloud_concurrency": 7,
    }
    resp = client.post("/llm/endpoints", json=payload)
    assert resp.status_code in (200, 201)
    # GET back and verify
    list_resp = client.get("/llm/endpoints")
    body = list_resp.json()
    eps = body.get("data", body).get("endpoints", body.get("endpoints", []))
    saved = next((e for e in eps if e["name"] == "test-custom"), None)
    assert saved is not None
    assert saved.get("plan_tier") == "custom"
    assert saved.get("cloud_concurrency") == 7
```

(If the actual save endpoint path or response shape differs, adapt the test BEFORE implementing — the test should match the real API contract. Search existing endpoint tests to find the right pattern: `grep -rn "POST.*endpoints" tests/`.)

- [ ] **Step 2: Run tests to confirm they fail.**

Run: `.venv/bin/pytest tests/test_endpoint_save_validation.py::test_save_endpoint_force_tier_for_no_auto_detect_provider -v`
Expected: FAIL — endpoint accepts the payload without warning.

- [ ] **Step 3: Add server-side validation.**

In whichever router file owns the `/llm/endpoints` POST handler (search via `grep -rn "def.*endpoint" src/prep/api/routers/`), add validation before persisting:

```python
def _validate_endpoint_concurrency(provider: str, plan_tier: str | None, cloud_concurrency: int | None) -> list[str]:
    """Phase 119 Phase A: warn (or reject) if a no-auto-detect provider has no plan_tier set.

    Returns a list of warning strings. Empty list = OK.
    """
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent.parent / "data" / "concurrency_limits.json"
    try:
        table = json.loads(path.read_text())
    except Exception:
        return []  # If the table is unreadable, don't block saves.
    # Map adapter provider -> concurrency table provider key.
    provider_map = {
        "ollama": "ollama_cloud",   # Ollama is the cloud variant in this app's saved-endpoint schema
        "openai": "openai",
        "anthropic": "anthropic",
        "google": "google_gemini",
        "kimi": "moonshot_kimi",
    }
    table_key = provider_map.get(provider.lower(), provider.lower())
    provider_entry = table.get("providers", {}).get(table_key)
    if not provider_entry:
        return []  # Unknown provider — don't block.
    has_explicit_tier = bool(plan_tier) and plan_tier not in ("", "auto")
    has_explicit_concurrency = isinstance(cloud_concurrency, int) and cloud_concurrency > 0
    if not provider_entry["auto_detect"] and not (has_explicit_tier or has_explicit_concurrency):
        return [
            f"Provider '{provider}' does not expose rate-limit headers; "
            f"please pick a Plan tier from the dropdown so concurrency can be capped correctly. "
            f"Defaulting to safe minimum until you set this."
        ]
    return []
```

Wire this helper into the POST handler. The exact integration depends on the existing handler — read it first. Behavior:

- **Reject (400)** when the provider has `auto_detect=false` AND the user provided neither a `plan_tier` nor a positive `cloud_concurrency`. This implements the "force choice" rule for Ollama Cloud and Gemini per the design.
- **Allow** when `plan_tier` is set (any value including `"auto"`) OR `cloud_concurrency > 0`.
- For header-rich providers (OpenAI/Anthropic), `plan_tier="auto"` is valid; the user can save without picking a number.

If the existing POST handler returns a non-standard response shape, return the warnings in whatever the existing convention is (e.g., a `warnings` array in the response body) rather than 400. The test (Step 1) accepts either contract; pick the one that matches the file's existing pattern.

- [ ] **Step 4: Update `EndpointManager.tsx` to mount `PlanDropdown`.**

In `packages/ui/src/components/llm/EndpointManager.tsx`, find the form that today has `formCloudConcurrency` (around lines 70-100 per the existing grep). Add:

1. A new state hook for the plan tier:
   ```tsx
   const [formPlanTier, setFormPlanTier] = useState<string | undefined>(undefined);
   ```

2. A fetch on mount for the limits table:
   ```tsx
   const [planLimits, setPlanLimits] = useState<PlanLimitsTable | null>(null);
   useEffect(() => {
     fetch('/llm/plan-limits')
       .then((r) => r.json())
       .then((body) => {
         const data = body.data ?? body;
         setPlanLimits(data);
       })
       .catch(() => setPlanLimits(null));
   }, []);
   ```

3. Replace the existing cloud_concurrency `<input>` with the dropdown:
   ```tsx
   {planLimits && providerNeedsCloudPlan(formProvider) && (
     <PlanDropdown
       providerKey={mapProviderToTableKey(formProvider)}
       value={formPlanTier}
       customConcurrent={formCloudConcurrency}
       limits={planLimits}
       onChange={({ plan_tier, cloud_concurrency }) => {
         setFormPlanTier(plan_tier);
         setFormCloudConcurrency(cloud_concurrency);
       }}
     />
   )}
   ```

   `providerNeedsCloudPlan` returns true for cloud providers (ollama, openai, anthropic, google, kimi). `mapProviderToTableKey` is the inverse of the backend's `provider_map`:
   ```ts
   function mapProviderToTableKey(provider: LLMProvider): string {
     switch (provider) {
       case 'ollama': return 'ollama_cloud';
       case 'openai': return 'openai';
       case 'anthropic': return 'anthropic';
       case 'google': return 'google_gemini';
       case 'kimi': return 'moonshot_kimi';
       default: return provider;
     }
   }
   function providerNeedsCloudPlan(p: LLMProvider): boolean {
     return ['ollama', 'openai', 'anthropic', 'google', 'kimi'].includes(p);
   }
   ```

4. Update `handleAdd` and `handleSaveEdit` to include `plan_tier`:
   ```tsx
   onAdd({
     name: formName.trim(),
     provider: formProvider,
     url: formUrl.trim(),
     api_key: formApiKey.trim() || undefined,
     local_concurrency: formLocalConcurrency,
     cloud_concurrency: formCloudConcurrency,
     plan_tier: formPlanTier,   // NEW
   });
   ```

5. Hydrate `formPlanTier` from existing endpoint on edit:
   ```tsx
   const handleEdit = (ep: SavedEndpoint) => {
     // ... existing field hydration
     setFormPlanTier(ep.plan_tier);
     setFormCloudConcurrency(ep.cloud_concurrency ?? 0);  // 0 = auto/unset
   };
   ```

- [ ] **Step 5: Run tests + UI build.**

Run: `.venv/bin/pytest tests/test_endpoint_save_validation.py -v`
Expected: 5/5 PASS.

Run: `cd packages/ui && npm run build`
Expected: clean.

Run: `cd packages/ui && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 6: Commit.**

```bash
git add tests/test_endpoint_save_validation.py packages/ui/src/components/llm/EndpointManager.tsx src/prep/api/routers/llm.py
git commit -m "feat(phase119-A): wire PlanDropdown into EndpointManager + save validation

EndpointManager mounts <PlanDropdown> for cloud providers, reading
the limits table from /llm/plan-limits on mount. Save handler now
sends plan_tier alongside cloud_concurrency. Backend validates:
no-auto-detect providers (Ollama Cloud, Gemini) reject saves
without a tier; auto-detect providers default 'auto' is accepted
without a number."
```

---

## Task 6: Live verification

**Files:** (read-only validation)

- [ ] **Step 1: Restart the daemon.**

When the daemon is idle (`infly=0 load=0 swarm_window=null`):

```bash
pkill -f "prep serve"; sleep 4
nohup .venv/bin/prep serve > /tmp/prep_phaseA_boot.log 2>&1 &
disown
until curl -s -m 1 http://localhost:8400/health | grep -q ok; do sleep 1; done
echo "daemon up"
```

- [ ] **Step 2: Confirm new endpoint serves the table.**

```bash
curl -s http://localhost:8400/llm/plan-limits | python3 -m json.tool | head -40
```

Expected: JSON with `providers.ollama_cloud.tiers[2].concurrent == 10` and a source URL.

- [ ] **Step 3: Set the soft cap on the live endpoint.**

In the dashboard (`http://localhost:5174`), navigate to Settings → AI Models, edit the `default_ollama` endpoint, pick `Max — 10 concurrent` from the new Plan dropdown, save.

- [ ] **Step 4: Verify the soft cap is honored.**

```bash
curl -s http://localhost:8400/compute/scheduler 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']['nodes']['cloud:default_ollama']
print(f\"limit={d['current_limit']} max_concurrent={d['max_concurrent']}\")
print(f\"dynamic_capacity should now be min(max_concurrent, current_limit)\")
"
```

Expected: `max_concurrent=10`. Even if `current_limit` is currently higher (lingering from before), the gate's effective cap is now 10.

- [ ] **Step 5: Run a sweep, watch the swarm log.**

Trigger a small build through the UI. Tail the latest swarm log:

```bash
ls -t ~/.local/share/sourceprep/logs/swarm/ | head -1 | xargs -I {} tail -f ~/.local/share/sourceprep/logs/swarm/{}
```

Expected: worker dispatches happen in waves of ≤10 (the soft cap), and `duration_s` values cluster tightly (no 9.8→37.4 staircase like the pre-fix log).

- [ ] **Step 6: No commit — observation only.**

If anything failed, return to the relevant task before declaring Phase A done.

---

## Task 7: Documentation

**Files:**
- Modify: `docs/Phase119_ConcurrencyStability/01_Design.md` — add a "Phase A Shipped" banner
- Modify: `docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md` — mark Phase A complete

- [ ] **Step 1: Append a "Phase A Shipped" note to `01_Design.md`.**

Add at the top after the existing date line:

```markdown
> **Phase A shipped 2026-04-26**: AIMD now respects user-stated plan tier as a
> hard cap. New `concurrency_limits.json` data file + `PlanDropdown` UI in
> Settings → AI Models. See `06_Phase_A_Plan.md` for execution. Phase B
> (header-driven discovery for OpenAI/Anthropic) and Phase C (Probe button)
> are queued but not yet started.
```

- [ ] **Step 2: Update the design doc's status table.**

In `05_Cross_Provider_Concurrency_Design.md`, find the "Phase A — Restore the soft cap" section and add at the bottom:

```markdown
**Status: SHIPPED 2026-04-26.** See `06_Phase_A_Plan.md` for the as-built changes.
```

- [ ] **Step 3: Commit.**

```bash
git add docs/Phase119_ConcurrencyStability/01_Design.md docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md
git commit -m "docs(phase119-A): mark Phase A complete in design + status docs"
```

---

## Self-Review Checklist

After execution:

1. **Spec coverage**: Every UX decision from the user (warn-but-allow general, force-choice for no-auto-detect providers, default-Auto for header-rich) is implemented?
   - Force-choice for Ollama Cloud / Gemini → Task 5 backend validation ✓
   - Default-Auto for OpenAI / Anthropic → PlanDropdown auto option only when `auto_detect=true` ✓
   - "Active: N concurrent" visible confirmation → PlanDropdown footer ✓
   - Cited source URL in help-text → PlanDropdown source URL line ✓
   - Custom… override → PlanDropdown SENTINEL_CUSTOM path ✓
   - Backwards compat with existing `cloud_concurrency` → preserved as fallback ✓

2. **Placeholder scan**: No "TBD", "similar to", "add error handling" — every step has actual code.

3. **Type consistency**: `plan_tier` is the field name across types.ts, the JSON tier_key, the backend validation, the API request payload. `cloud_concurrency` keeps its existing meaning (the integer cap; 0 = auto). `auto_detect` is the table-level boolean used in both Python and TypeScript.

4. **No new unused code**: `PlanDropdown` is exported from `@prep/ui`, used by `EndpointManager.tsx`, has Storybook stories, has consumers verified via TypeScript build.

5. **No regressions to Phase 119 backend**: scheduler tests still pass with new `dynamic_capacity` semantics. Demand-gate, locked ceiling, swarm-window enforcement all unaffected because the change is purely on the upper-bound clamp side.

---

## Execution Handoff

Plan complete and saved to `docs/Phase119_ConcurrencyStability/06_Phase_A_Plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
