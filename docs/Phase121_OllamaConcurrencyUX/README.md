# Phase 121 -- Ollama Concurrency: Honest Display & Platform-Aware Setup

> **Scope:** Stop the dashboard from claiming concurrency the local Ollama
> daemon cannot deliver, and give users the exact platform-specific
> command to set `OLLAMA_NUM_PARALLEL` correctly.
> **Prior art:** Phase 119-A (`OLLAMA_NUM_PARALLEL = local + cloud` formula),
> Phase 82 (latency-aware concurrency discovery), `services/pipeline/ollama_probe.py`.
> **Status:** Research & TODO
> **Date:** 2026-04-30

---

## 1. Problem Statement

Two complementary bugs surfaced during Phase 119 investigation of swarm
coordinator quality on the SourcePrep project:

### 1A. The dashboard lies about concurrency

The AI Gateway sidebar shows `Thinking [10x]` when 10 LLM workers are
live from the LLMClient's perspective. But Ollama daemon
(`ollama serve`) defaults to `OLLAMA_NUM_PARALLEL=4` — meaning **only 4
of those 10 are actually being processed**, and 6 sit in Ollama's
internal queue waiting for a free slot.

From the LLMClient HTTP perspective: 10 connections open.
From the AIMD scheduler perspective: 10 tokens granted.
From the Ollama-daemon-internal perspective: 4 inferring, 6 queued.
From the user's perspective: "10x" badge implying real parallel work.

We have the truth-source already: `services/pipeline/ollama_probe.py`
reads `OLLAMA_NUM_PARALLEL` from the daemon environment. We just don't
use it to clamp the displayed number.

### 1B. Setup hint is platform-agnostic and unactionable

`packages/ui/src/components/llm/EndpointManager.tsx:444` shows:

> Ollama requires manual startup configuration to run concurrently.
> Start your Ollama server with `OLLAMA_NUM_PARALLEL=11` (the sum: 1
> local-GPU model + 10 cloud-routed calls). Otherwise, requests will
> queue sequentially.

The hint correctly computes the right value but tells the user nothing
about *how* to set it. On macOS GUI Ollama.app, `export VAR=...`
in a shell does nothing — the GUI app is launched by `launchd` and
inherits a different env. On Linux systemd, you need a drop-in unit.
On Windows, `setx` + relaunch. Each platform needs its own snippet, and
the user shouldn't have to know which.

Investigation evidence (Phase 119):

```text
$ ps -eo pid,etime,command | grep "ollama serve"
10583 16-21:25:25 /Applications/Ollama.app/Contents/Resources/ollama serve
$ echo "$OLLAMA_NUM_PARALLEL"          # empty — Ollama.app inherits launchd env
$ launchctl getenv OLLAMA_NUM_PARALLEL  # empty — never set
```

The user's Ollama daemon had been running for 16 days with default
`NUM_PARALLEL=4` despite the dashboard recommending 11. The 502/503
"rate limits" we attributed to Ollama Cloud were actually local-daemon
queue overflows.

---

## 2. Goals

1. The displayed worker count never exceeds what Ollama can actually
   process in parallel.
2. Users on macOS / Linux / Windows see exact, copy-paste setup commands
   for `OLLAMA_NUM_PARALLEL`.
3. After the user claims to have applied the fix, a one-click Verify
   action re-probes and confirms the new value is in effect.

## 3. Non-goals

- Auto-applying the fix without user approval (privileged operation).
- Detecting non-Ollama proxy queueing (LM Studio etc. — separate phase).
- Changing the underlying AIMD or Phase 119 routing logic.

---

## 4. Approach

### 4.1 Honest concurrency display (Issue 1A)

**Step 1 — surface the probe in `/llm/slots/status`.**
`ollama_probe.py:detect_num_parallel()` already returns the effective
value via `/api/ps` headers + env. Add it to the slot status response
under `cloud:default_ollama` (or whichever Ollama node) as
`ollama_num_parallel: int | null`.

**Step 2 — clamp the displayed worker count.**
In `SidebarAIGateway.tsx`, when `slotsStatus.large_model.provider == "ollama"`
and `ollama_num_parallel` is known and lower than `concurrent_workers`,
display the badge as `{ollama_num_parallel}x (Y queued)` where
`Y = concurrent_workers - ollama_num_parallel`.

**Step 3 — pipe the truth into AIMD.**
The scheduler should not grant more tokens than Ollama can serve.
Either (a) clamp `dynamic_capacity` at runtime to
`min(max_concurrent, ollama_num_parallel)`, or (b) leave AIMD alone but
cap submission at the LLMClient level. Option (a) is cleaner because it
keeps AIMD in charge and ensures the rest of the system (UI, telemetry)
sees a coherent number.

### 4.2 Platform-aware setup commands (Issue 1B)

**Step 1 — detect platform in the dashboard.**
Use `navigator.platform` / `userAgent` plus a backend probe
(`/system/platform` returning `{platform: "darwin" | "linux" | "win32",
init_system: "launchd" | "systemd" | null}`).

**Step 2 — render platform-specific snippets.**
Replace the single hint with a tabbed component
(`<OllamaSetupHint platform={...} />`) showing:

- **macOS GUI app:**
  ```bash
  launchctl setenv OLLAMA_NUM_PARALLEL 11
  osascript -e 'quit app "Ollama"'
  open -a Ollama
  ```
  Plus an optional persistent-across-reboot LaunchAgent plist snippet.

- **Linux systemd:**
  ```bash
  sudo systemctl edit ollama
  # in editor:
  # [Service]
  # Environment="OLLAMA_NUM_PARALLEL=11"
  sudo systemctl daemon-reload && sudo systemctl restart ollama
  ```

- **Linux non-systemd / manual:**
  ```bash
  export OLLAMA_NUM_PARALLEL=11
  pkill ollama
  ollama serve &
  ```

- **Windows:**
  ```cmd
  setx OLLAMA_NUM_PARALLEL 11
  REM restart Ollama from Task Manager / system tray
  ```

Each block has a Copy button.

**Step 3 — Verify action.**
Button: "Verify Ollama is configured." On click, re-runs
`ollama_probe.detect_num_parallel()` and either:

- shows green check + "Effective NUM_PARALLEL = 11" if matched,
- shows red error + "Still seeing NUM_PARALLEL = 4" if not, with a
  hint to restart Ollama (the env var only takes effect at daemon
  startup).

### 4.3 Stretch: hide the recommendation when already applied

If `ollama_num_parallel >= local_concurrency + cloud_concurrency`, hide
the warning banner entirely. Most users only need to read it once.

---

## 5. Tasks

| ID | Task | Files | Owner |
|---|---|---|---|
| T1 | Backend: extend `/llm/slots/status` with `ollama_num_parallel` per Ollama node | `api/routers/llm.py`, `services/pipeline/ollama_probe.py` | |
| T2 | Backend: clamp `dynamic_capacity` for Ollama slots at `ollama_num_parallel` | `services/pipeline/scheduler.py` | |
| T3 | UI: split badge into `processing/queued` when relevant | `components/navigation/SidebarAIGateway.tsx`, `types.ts` | |
| T4 | Backend: add `/system/platform` route returning OS + init system | `api/routers/system.py` (new) | |
| T5 | UI: `OllamaSetupHint` component with platform tabs and Copy buttons | `components/llm/OllamaSetupHint.tsx` (new) | |
| T6 | UI: Verify button calling `/llm/slots/status` and reporting probe delta | `components/llm/EndpointManager.tsx` | |
| T7 | Tests: scheduler clamp logic, probe-driven cap update, platform-route shape | `tests/test_ollama_clamp.py`, `tests/test_system_platform.py` | |
| T8 | Stretch: auto-hide warning banner when already configured | `components/llm/EndpointManager.tsx` | |

## 6. Test plan

1. **Unit:** scheduler clamps `dynamic_capacity` to probed
   `ollama_num_parallel` even when AIMD wants higher.
2. **Unit:** badge renders `4x (6 queued)` when in_flight=10 and
   probe=4; renders plain `10x` when probe>=10 or unknown.
3. **Integration:** triggering a swarm with `OLLAMA_NUM_PARALLEL=2`
   produces no Ollama 502/503 backoffs (because we never submit > 2).
4. **Manual:** macOS user follows displayed launchctl snippet; Verify
   button turns green.

## 7. Open questions

1. **Should we ever oversubscribe?** Phase 119 evidence suggests no — every
   over-NUM_PARALLEL submission risks a 502. But some users may want to
   tolerate the queue for higher peak burst throughput. Default to clamp;
   advanced toggle to override?
2. **Auto-fix?** Tempting to write the launchctl + restart for the user.
   Likely too privileged / fragile. Defer indefinitely.
3. **What if Ollama daemon isn't running?** Probe returns null. UI should
   show a different state ("Ollama not detected") rather than zero.

## 8. Out-of-scope follow-ups

- LM Studio / vLLM / Triton equivalents of `OLLAMA_NUM_PARALLEL`.
- Auto-detecting concurrent capacity by stress-probing the Ollama
  endpoint.
- Multi-host Ollama (network-relayed) where probe over HTTP wouldn't
  reach the daemon.
