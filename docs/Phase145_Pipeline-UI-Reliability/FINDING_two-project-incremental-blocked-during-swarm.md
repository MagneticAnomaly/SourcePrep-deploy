# Phase 145 Finding — Two-project incremental: second project hangs on Update with no queue surface; one project's swarm consumes full cloud budget

**Status:** Open. Captured live from dashboard screenshot 2026-06-18 21:30 EDT. Two related sub-bugs documented together because they appeared in the same incident. **2026-06-18 22:38 update — the daemon is now the leading hypothesis for the root cause.** See §9 (added).
**Found:** 2026-06-18, reported by Eric (dogfooding).
**Severity:** Medium-High. (i) The user clicked Update on the second project and got no visible feedback — the button shows "Updating..." indefinitely, no queued badge, no "behind DebateHaus" hint. This is the §4c invariant 4 violation ("No silent endpoint failure"), reproduced on a non-error path. (ii) Background: a project with no boost star is monopolizing the entire `cloud:default_ollama` budget via a swarm window, blocking incremental work on every other non-starred project.
**Linked symptom in README:** §2p.

---

## 1. Symptom (as reported, with screenshot details)

Two projects active in the sidebar (auto toggles ON):
- **DebateHaus** — no star, currently rendered as **`Swarming · Deep Enrichment · Module Synthesis · 19m 13s`** in the queue widget at the bottom-left.
- **Applifier** — no star, the user clicked **Update** on its Graph Scope card.

Result the user observed:
- Applifier's "Update" button stays in the `Updating...` state with no visible progress.
- The Graph Scope card shows the spinner sub-message `Building knowledge graph…` (apparently a UI hold, not an actual graph build — see §3a).
- The sidebar's queue widget shows only DebateHaus active; **Applifier does not appear as queued anywhere visible.**
- The left-sidebar concurrency readout shows `cloud:default_ollama: 10/10` — the cloud budget is fully consumed by DebateHaus's swarm.

User-stated expectation:

> "Neither has a star check, so they should divide resources equally (until it gets to swarm-enabled stages of course). But it's not even beginning the incremental pipeline for the second repo."

This is consistent with the design contract per `docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md`:

- §Tier 4 (Normal Mode): equal share of worker budget among all active projects when no project is boost/exclusive/swarming.
- §Swarm (Tier 1): swarm takes the full slot budget, bypassing fair-share. Other projects' stages enter the queue and wait.
- §4a (UI invariants — established in Phase 145 README §4a): `queued` state must render as `Hourglass + "Queued behind <other-project>"`. Today it renders nothing — silent.

So there are two layers:
- **Backend behavior:** DebateHaus's swarm legitimately holds 10/10. The contract says Applifier should be enqueued and wait.
- **UI behavior:** even if Applifier IS enqueued behind the swarm, the user has no signal. The Update button just sits.

## 2. What the screenshot also reveals (side observations worth pinning)

### 2a. "Module Synthesis" badged as "Swarming"

Per `docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md`:
- Stage 7 (Group Reasoning) — **HIGH swarm benefit, primary swarm target.**
- Stage 8 (Module Synthesis / clustering) — **MEDIUM swarm benefit, future swarm candidate.** Not currently expected to run as a swarm.

DebateHaus's queue badge says `Module Synthesis · Swarming`. Either:
- The swarm window was acquired during Group Reasoning and is being held into Module Synthesis (Phase 91 §Swarm Cooldown says swarm closes immediately after the swarm stage ends, then a 45s cooldown gate prevents re-acquisition — so this shouldn't carry).
- Module Synthesis has been enabled as a swarm stage (config change?).
- The "Swarming" badge is stale and the project actually finished swarming N minutes ago.

This is independent of the main bug but should be pinned in diagnostics.

### 2b. AI Gateway label disagrees with queue widget

- Queue widget: `DebateHaus · Module Synthesis · 19m 13s`.
- AI Gateway widget: `Thinking [10x] · kimi-k2.6:cloud · Deep Reasoning [10x] on DebateHaus`.

Two different stage names ("Module Synthesis" vs "Deep Reasoning") attributed to the same active project at the same instant. One of these is stale (probably the AI Gateway, since the actual model load matches the project being on Module Synthesis right now, but the label says Deep Reasoning).

### 2c. 19m 13s on a single stage with no progress visible

DebateHaus has been on `Module Synthesis · Swarming` for ~19 minutes. Phase 91's drain timeout (default 600 s = 10 min) should be irrelevant here because nothing else is draining yet (Applifier hasn't been enqueued visibly). But 19 minutes on a single stage with 10× parallel cloud calls is a long time for a project the size of DebateHaus (small XCode project per memory). Two possibilities:
- The stage is legitimately doing a large amount of work (synthesizing many modules).
- The stage is stuck and the heartbeat / progress signal is silent — same shape as §2j (progress regresses) or §2a (skipped stage shows running forever).

## 3. Stacked issues (each could be a separate fix once diagnosed)

### 3a. Applifier's Update either never enqueues or is enqueued without UI surface

The user-facing question: did clicking Update *actually* enqueue work, or did it silently fail / silently no-op?

Two paths to discriminate:
- **`/system/pipeline-queue` snapshot** while the symptom is live. If Applifier appears there: bug is purely UI surfacing (Phase 145 §4a invariant violated — no queued badge). If Applifier does NOT appear: bug is in the endpoint that handles the Update click (it accepted the click but didn't enqueue).
- **`/events` SSE stream** while clicking Update. A successful enqueue should emit a `pipeline_status` or `queue_changed` event. Silent click → silent endpoint failure.

This needs to be captured the next time the symptom is live (see §4).

### 3b. Swarm consuming full budget on a stage that isn't supposed to swarm (§2a observation)

If Module Synthesis really is running with `swarming=true` and consuming 10/10 cloud slots, that's either:
- A regression vs Phase 79's stage profile.
- A config drift (`PREP_*` env var or per-project swarm enable flag).
- A swarm window held open past the Group Reasoning boundary that should have closed it.

### 3c. UI queue widget shows the active project but not waiters

Per Phase 145 §4a, a `queued` stage should render with the `Hourglass` icon and the message `Queued behind <project>`. The current queue widget shows only the active project (DebateHaus). There is no visual region in this UI where a waiting project would appear.

This is similar to §2f (sidebar queue shows stale state) but a different specific failure: not staleness, just *absence* of any queued-projects surface.

### 3d. "Building knowledge graph..." spinner with no actual graph build

The Graph Scope card shows `Building knowledge graph…` as a sub-message even though the project's Knowledge Embedding stage on the right panel is already at 100% and complete. This message is either:
- The wrong copy for the "Updating..." action the user clicked.
- A stale stale spinner that should have been cleared when the previous fast_sync finished.

## 4. Diagnostic checklist (capture next time the symptom is live)

```bash
# 1. Confirm budget is fully consumed and by whom
curl -s http://localhost:8400/system/pipeline-queue | python3 -m json.tool

# 2. Is the second project actually enqueued?
curl -s http://localhost:8400/projects/<APPLIFIER_PID>/pipeline/status | python3 -m json.tool
# Look at: fast_sync.is_queued, fast_sync.is_active, fast_sync.phase

# 3. Click Update on the second project; capture the events stream simultaneously
timeout 30 curl -sN http://localhost:8400/events | tee /tmp/dbg_2p_events.log &
# (in another terminal) click Update in dashboard, then ctrl-c the curl

# 4. Inspect the Update click's request/response in the browser Network tab
#    URL, method, payload, status code, response body

# 5. Does DebateHaus's Module Synthesis stage actually have swarm=true?
SCHED=$(curl -s http://localhost:8400/system/pipeline-queue | python3 -c "
import json, sys
data = json.load(sys.stdin)['data']
print(json.dumps(data.get('nodes', {}).get('cloud:default_ollama', {}).get('active', {}), indent=2))
")
echo "$SCHED"
# Should show which project owns each slot and which stage

# 6. Tail DebateHaus's pipeline log for the swarm window open/close events
DH_PID=76e2450c-89c7-4a29-9f22-1499294cffbe   # DebateHaus
DH_LOG=$(ls -t /Volumes/Thunderbolt/XcodeProjects/DebateHaus/DH/.sourceprep/logs/pipeline_*.log | head -1)
grep -E "swarm window|fair-share|capacity_changed|drain" "$DH_LOG" | tail -30
```

Save outputs to `EVIDENCE_dgP_two-project-incremental-blocked-<timestamp>.md`.

## 5. Hypotheses for the silent enqueue (3a)

- **H-P1:** The `/projects/{id}/pipeline/fast` (or whatever Update calls) endpoint sees a global barrier active (from another project's swarm) and returns a 4xx the dashboard handles as "show spinner, swallow the error." Check the response status.
- **H-P2:** The endpoint enqueues correctly, returns 200, but the queue persistence is per-node and the UI's queue widget reads from a different source that doesn't include cross-node queued items.
- **H-P3:** The `Update` button's handler optimistically transitions the UI to a spinner state but doesn't subscribe to a confirmation event, so a non-response leaves the spinner stuck.
- **H-P4:** The enqueue is silently deduped against an existing queue entry the user can't see (e.g., the watcher already enqueued a stage that's blocked behind DebateHaus, and the user's manual Update hit a dedupe).

## 6. Design invariants this surfaces (and may violate)

Lifted from Phase 145 README §4c and Phase 91 §Capacity Change Broadcast:

1. **No silent endpoint failure.** A Update click must surface a visible result — enqueued / busy / rejected with reason. Today: no surface.
2. **No `null` group → "stuck" rollup.** If Applifier's `/pipeline/status.fast_sync` is `null` or queued, the panel should reflect "queued behind DebateHaus", not just sit in the prior state.
3. **Queue surface must list waiters.** Per §4a, queued stages render with `Hourglass + "Queued behind <project>"`. The sidebar queue widget today shows only the active project — waiters are invisible.
4. **Swarm scope must match the stage's profile.** Per Phase 79 Stage 8, Module Synthesis is not a primary swarm target. If it's running as swarm, that's a config drift or a held-window bug.

## 7. Relationship to other open findings

- **§2k / `FINDING_concurrency-undershoot-and-cross-project-work-loss.md`:** same scheduler subsystem, different manifestation (§2k: second project's run cancels work in flight on the first; here: second project's run never visibly starts). Suggests the fix-thread that addresses §2k must also fix §2p's queue-surfacing layer. **Probably folds into Thread A (PROPOSAL_thread-A-v1) as a new sub-thread A.8 — UI surface for queued waiters** — to be evaluated in Thread A's next scrutiny pass.
- **§2f (sidebar queue shows stale state):** the queue widget is the same surface; §2f is about stale state, §2p is about *absent* state. May share a single fix.
- **§2a (skipped stages show "Running" forever):** similar shape — UI showing a stuck non-progress signal — but different root cause.

## 9. Update 2026-06-18 22:38 — frontend hang only (NOT a daemon freeze; earlier attribution retracted)

**Correction 2026-06-18 23:38 — the previous version of this section attributed the 22:38 incident to §2m's daemon freeze. Eric corrected this 2026-06-18 23:38: the daemon was running the entire time. A browser refresh showed every queued job had completed under the hood. The 22:38 symptom was a frontend hang — UI lost sync with a healthy backend — not a backend stall.**

The original §2p framing (silent enqueue + invisible queue) and the §2q framing (auto-incremental never fired) likely **are** standalone bugs after all, not symptoms of §2m. The daemon-freeze hypothesis was a wrong turn driven by reading the cross-panel inconsistency (queue widget empty while AI Gateway said `10× active`) as proof the daemon was silent, when it was actually proof the frontend wasn't polling cleanly.

What the 22:38 evidence does still support:

- **H5 — polling layer has no daemon-silence fallback** (added to §2m §9 originally for daemon-silence reasons) generalizes to **"polling layer has no fallback when *any* transient cause — silence, dropped SSE, browser tab backgrounding — desyncs the UI."** That defense-in-depth UI thread remains valuable regardless of root cause.
- **Cross-panel inconsistency** is itself a bug — different panels read different state stores and don't reconcile when one is stale. Same shape as §2r and §2l. Worth pinning as a separate symptom, not folding into §2m.

What this update does NOT change:

- §2p's two-layer framing (backend: is Applifier actually enqueued? + UI: if so, why no surface?) still applies. Both layers need their own evidence captures.
- §2q's six hypotheses still stand. The watcher could still be (a) not started, (b) starved on FSEvents, (c) silently gated by budget/barrier, (d) silently enqueued, (e) glob-filtered, (f) blocked by `_check_incomplete_deep_enrichment`. None of these are "the daemon froze."
- §2m's original 2026-06-17 evidence (10-minute uvicorn gap in the terminal log) is a genuine backend stall and stays valid. The 22:38 recurrence claim about §2m, however, is withdrawn.

The corpus needs to drop the "downstream of §2m" framing for §2p / §2q and treat them as independent bugs again.

About 45 minutes after the original §2p capture, with no UI state change (the Update button stayed at "Updating…" the whole time, Applifier never began), the user clicked into DebateHaus (the previously-running project that had been on Module Synthesis · Swarming · 19m 13s). DebateHaus's panels rendered as:

- **Graph Scope:** "No files in scope · Adjust include patterns or build the trace index"
- **Graph Enrichment:** spinner with "Loading project…" — never resolves

Other panels in the screenshot at 22:38:

- Sidebar queue widget: empty active slot, only SourcePrep "Pending · Fast Sync · Edge Discovery" remains
- `cloud:default_ollama: 0/10` (no in-flight work)
- AI Gateway still shows `Thinking [10×] · Deep Reasoning [10×] on DebateHaus` — stale; nothing is actually running

This pattern matches §2m (`FINDING_daemon-stall-and-frontend-lockup.md`) exactly: the daemon stopped processing requests, the UI's last-known state froze in place, and downstream symptoms (Update never starts, queued projects sit, click into the active project loads forever) all derive from the same underlying freeze. The original §2p framing — "scheduler bug, queue-surfacing bug" — is probably misdiagnosed; the scheduler likely behaved correctly *before* the freeze, and the silence afterward is daemon-wide, not queue-specific.

**Implication for the proposal:** §2p (and §2q, see its update) may be subsumed by §2m's root cause. Defer authoring scheduler/queue fixes until §2m's H1/H2 hypotheses (lock contention vs native CoreML hang) are pinned. Keep §2p as a UI-side issue (the *separately-real* "no visible feedback when the daemon is silent" — which §2m doesn't fix) but expect the queue-pathological half to evaporate when §2m lands.

**New sub-symptom worth its own line in §2m:** clicking a project whose data was being loaded mid-freeze leaves the right panel stuck at "Loading project…" with no timeout, no retry, no error surface. The polling layer apparently has no fallback when the daemon doesn't respond.

## 8. Cross-references

- Phase 91 design: `docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md` (Tier 1 swarm + Tier 4 normal + UI invariant §4c).
- Phase 79 swarm profiles: `docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md` (Stage 7 vs 8 swarm benefit).
- Related findings: `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` (§2k).
- Code: `src/prep/services/pipeline/scheduler.py` (swarm window, fair-share), `src/prep/api/routers/system.py` (`/system/pipeline-queue`), `src/prep/api/routers/projects/build.py` (Update / fast-sync trigger), `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` (queue widget), `packages/ui/src/components/trace/GraphScopeCard.tsx` (Update button), `src/prep/core/watcher.py` (AutoRebuildWatcher).
