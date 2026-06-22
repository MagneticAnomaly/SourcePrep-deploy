# Phase 145 Finding — Manual Update click triggers a non-deterministic cluster of UI hang symptoms; the workaround for one bug spawns several others

**Status:** Open, recurring. 2026-06-19.
**Found:** 2026-06-19, Eric. Multiple sessions over the past three days. This finding describes the *pattern*, not a new individual bug — but the pattern itself is the diagnostic.
**Severity:** Medium-High (compound). Individual symptoms vary; cumulatively the dashboard becomes unusable mid-task and the user has no way to tell if the backend is healthy.
**Linked symptom in README:** §2u.

---

## 1. The pattern (as reported)

> "I clicked on Update and the UI during the incremental pipeline pauses and does weird things. It's currently running Applifier project, but I'm unsure if it's actually running because the UI is so hangy. It's the same bug I've been reporting but it's doing everything from not loading other projects without needing refresh, and not showing the progress bar, or showing multiple progress bars, and showing the initial progress bar instead of incremental — and it's sort of random so hard to track exact error, but seems only happens when I manually click the refresh button to get stale files to run incremental (because there's still a bug causing the Auto feature to not automatically add stale or new files)."

Decomposed: **one user action (manual Update click), several simultaneous symptoms, non-deterministic mix per session.**

## 2. Why this is its own entry (not just "another instance" of an existing finding)

Each individual symptom maps to an already-documented finding:

| Symptom | Existing finding |
|---|---|
| Other projects don't load until refresh | §2m §9 (retracted-attribution-to-daemon-freeze; reframed as pure frontend hang) |
| Update button gives no feedback / silent enqueue | §2p |
| Multiple progress bars showing | §2r |
| Initial-style bar instead of incremental | §2t §4 |
| Can't tell if backend is running | §2m / §2p cluster |
| Stage row spinner without actual progress | §2s |

But **the pattern of all-at-once-after-one-click-after-Auto-was-broken** isn't captured by any of them individually. The pattern itself is the finding:

1. **§2q** (Auto-incremental never fires) forces the user to click Update manually as a workaround.
2. **The manual Update click triggers** a cluster of frontend hang behaviors that vary session-to-session.
3. The cluster is **non-deterministic** — different symptoms surface each time, which is why each prior session got captured as a different §-letter.
4. The cluster's net effect: **the user can't tell if the backend is healthy**, and the dashboard requires multiple refreshes to stabilize.

This pattern is the user's actual experience. Each prior §-letter is a snapshot of one moment in that experience.

## 3. The cascade chain

```
[§2q + §2s — Auto-incremental never fires when stale/new files exist]
                     │
                     ▼
[User opens dashboard, sees stale files in queue, no auto run happening]
                     │
                     ▼
[User clicks "Update" on Graph Scope card as a workaround]
                     │
                     ▼
[Frontend hang cascade — non-deterministic mix of:]
   • Other projects show "Loading project…" forever
   • Update button stuck at "Updating…"
   • Progress bar absent OR multi-stage spinning OR wrong style
   • SSE event stream desyncs from polling
   • Backend (separately) actually does the work just fine
                     │
                     ▼
[User refreshes browser to stabilize] → recovers, work has progressed
                     │
                     ▼
[Next stale-file cycle starts, Auto is still broken → loop repeats]
```

**Killing the cascade requires fixing the trigger.** Fixing §2q (Auto fires reliably) removes the need for the manual Update workaround, which removes the trigger for the cluster. **This makes §2q the highest-leverage fix in the entire Phase 145 backlog** — not because §2q itself is the worst bug, but because §2q's existence forces the workaround that produces every other symptom.

## 4. Why the cluster is non-deterministic (hypothesis)

Each symptom comes from a different part of the frontend's reconciliation pipeline:

- **SSE event handler** decides per-row `running` flags (§2r)
- **Polling on `/projects/<id>/pipeline/status`** drives per-stage row data (§2l, §2n)
- **Polling on `/system/pipeline-queue`** drives sidebar queue widget (§2f, §2p)
- **Project-specific load endpoint** drives the Graph Scope + Enrichment panels (§2m §9)

When a manual Update fires:
- A burst of new events hits the SSE handler
- The polling reducers race against each other
- React re-renders may drop intermediate states
- Browser tab focus / SSE backpressure / network timing introduce non-determinism

So each session catches the race in a different state. None of the individual race outcomes is *new* — they're all already documented — but the trigger (manual click → race burst) is.

## 5. What this implies for the proposal stack

### 5.1 Execution-order implication

**`PROPOSAL_state-machine-re-centering-v1.md` should be re-ordered to prioritize the Auto-trigger fix.** Currently the proposal lists T1 (UI re-centering, closes 6 findings) as highest-yield. But T1 doesn't remove the trigger — it just makes individual rows render correctly. The user still has to click Update for every stale-file batch.

The smallest intervention that *removes* this cascade entirely:

1. **Fix §2q (Auto-incremental never fires)** — root of the cascade chain. Pin via H-Q1..H-Q6. Likely shares root cause with §2s per `FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md` §5.
2. **Then T1 (UI re-centering)** — closes residual UI rendering issues for the rare manual rebuilds that still happen.

If Auto is fixed, the user never clicks Update, the SSE burst that triggers the race never happens, and most of the cluster never manifests in practice. **Even if T1 takes months, fixing §2q alone may make the dashboard feel "fixed" to the user.**

### 5.2 Reframing of the synthesis hypothesis

The `SYNTHESIS_2026-06-18_did-the-state-machine-drift.md` says drift in the UI's per-row state derivation explains most findings. That's true at the *rendering* level. But this finding adds a complementary layer: **the trigger that exposes the drift is itself a bug.** Fixing the trigger (Auto) makes the drift much less visible to the user even without fixing it directly.

For the orchestrator (Fable or otherwise) picking up this corpus: **two parallel investigations are warranted** — (a) the state-machine re-centering per the existing proposal, and (b) the Auto-watcher reliability investigation per §2q. Order (b) before (a) if you can only do one.

## 6. Diagnostic guidance (when this happens again)

The instinct is to capture a screenshot. That's necessary but not sufficient. The valuable capture is the *event stream + polling response* at the moment of the cascade. While the UI is hung:

```bash
# In a terminal — capture what the daemon is actually serving
timeout 30 curl -sN http://localhost:8400/events > /tmp/cascade_events.log &

# Concurrently, snapshot all polled endpoints
for endpoint in /system/pipeline-queue /projects; do
    curl -s http://localhost:8400$endpoint > /tmp/cascade_$(echo $endpoint | tr / _).json
done

# And the projects the dashboard is rendering
for PID in <list of active project ids>; do
    curl -s http://localhost:8400/projects/$PID/pipeline/status > /tmp/cascade_$PID.json
done

# When done: open DevTools Network tab in the browser, filter "Pending"
# Anything that's been pending for > 5s is a frontend-side waiting request
```

If the events log shows steady output AND status endpoints respond fast, the cascade is purely frontend (most likely). If endpoints time out, the cascade has a backend component (re-evaluate §2m attribution).

## 6.1 Additional datapoint 2026-06-19 — cluster self-stabilizes by ~stage 8 with one refresh

Eric reported (live update): "it does seem to be running fine by stage 8 or so if you refresh the page."

This sharpens the cluster's character:

- The cluster is **transient**, not permanent. It clears on its own as the pipeline advances.
- The cluster is concentrated in the **early stages** (1–7, roughly fast_sync + early deep_enrichment).
- A **single browser refresh** accelerates recovery once the pipeline is past the burst window.
- The backend is healthy throughout (consistent with the §2m retraction).

This shape is consistent with a **race burst during the high-event-rate window**: early stages fire rapid `stage_start` / `stage_end` / `concurrency_snapshot` SSE events, the frontend's reducers can't keep up, intermediate state gets dropped. Later stages (Group Reasoning, Module Synthesis, etc.) take minutes each — the event rate drops naturally and polling catches up.

**Implication for the fix:** the actual bug is **debouncing / coalescing of SSE events in the frontend reducer** — NOT a fundamental state machine drift. The frontend's reducer needs back-pressure handling for high-event-rate windows. This is independent of T1 (UI re-centering) and may be a separate Thread D-shape sub-task in a future proposal.

**Diagnostic test:** open the dashboard with Chrome DevTools Performance recording active, click Update, capture the first 30 seconds. The trace will show if the React reducer is the bottleneck (long tasks on the main thread during the burst).

## 6.2 Recurrence 2026-06-21 19:48 — refresh leaves the UI without a current-stage indicator + new "progress > 100%" sub-symptom

User: "Applifier is currently running but it's not showing it's running. UI weirdly stalled on the run then when I refresh the web browser it seems to show no current process in the pipeline. I do believe it's actually running. This bug may already be reported."

**Confirmed actually running** via two corroborating signals in the same screenshot pair:

- Queue widget: `★ Applifier · Building · Deep Enrichment · Deep Reasoning · 1m 40s` (the orchestrator believes Deep Reasoning is the current stage).
- AI Gateway: `Thinking [3×] · kimi-k2.6:cloud · Deep Reasoning [3×] on Applifier`. `cloud:default_ollama: 3/10` — three real cloud LLM calls in flight.

So the backend is healthy AND running on Deep Reasoning. The Applifier panel's stage rows tell a different (broken) story:

- **Deep Reasoning** row shows `100%` progress bar + `1,069 / 1,058 files` — i.e. *more files processed than the total*. The denominator and numerator disagree by 11. This is a worker progress-callback bug: the counter doesn't respect the `progress_total` ceiling, or `progress_total` is the post-filter file count while `progress_current` includes pre-filter increments.
- **No stage row shows the spinner-as-current-stage decoration** that normally indicates "this is the active stage." A user looking at this panel can't tell which stage is currently running — they have to glance at the queue widget instead. The "currently running" affordance is missing from the main panel.
- Deep Knowledge Embedding shows "Not run" with a spinner glyph. Immune System shows "Not run". Both are downstream of Deep Reasoning.

**Two distinct sub-symptoms beyond what §2u already documented:**

- **Progress counter exceeds 100%** (1069/1058). New shape — most §2j / §2o issues are "progress lies low" (premature success at partial completion). This one lies high (more processed than possible). Same class: worker progress emission not bounded against the canonical total. Worth a one-line note in `FINDING_stage-progress-non-monotonic.md` (§2j) since it shares root.
- **Refresh wipes the "current stage" affordance.** After the browser refresh that the user did to unstick the original §2u cluster, the main panel rendered with NO indication of which stage is current. Queue widget remained correct. Suggests: the SSE channel that drives the "spinner-on-current-stage" decoration didn't replay the in-flight stage event on reconnect — only the cumulative state was re-fetched, not the transient "I am the current stage" signal.

**Implication for the proposal stack:**

- Strengthens §2u §5.1 — fixing §2q (Auto reliability) is still the priority, but **SSE-event-replay-on-reconnect is a separate UI thread** worth pinning. When the dashboard reconnects after a refresh during an active stage, the daemon needs to re-emit the in-flight `stage_start` for the current stage so the UI knows what's running.
- The "progress > 100%" bug should be cross-referenced from §2j. That finding is about progress *regressing*; this case is progress *overshooting*. Same family — worker progress emission isn't bounded by `progress_total`. A frontend monotonic + bounded guard would catch both, but the backend fix is more honest.

## 7. Cross-references

- Trigger: [`FINDING_auto-incremental-never-fired-despite-stale-files.md`](FINDING_auto-incremental-never-fired-despite-stale-files.md) (§2q) + [`FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md`](FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md) (§2s).
- Individual symptoms in the cluster: §2c, §2f, §2m (post-retraction), §2p, §2r, §2t.
- Proposal that needs re-ordering: [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) — see §5.1 above for the order swap.
- Synthesis context: [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md) — this finding adds the trigger layer to the drift hypothesis.
