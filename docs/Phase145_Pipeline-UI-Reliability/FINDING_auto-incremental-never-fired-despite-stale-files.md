# Phase 145 Finding — Auto-incremental pipeline never auto-triggered despite hours of untracked files

**Status:** Open. Captured live from dashboard screenshot 2026-06-18 21:30 EDT. **2026-06-18 23:38 — earlier daemon-freeze attribution retracted.** The 22:38 incident that I temporarily attributed to §2m was a frontend hang, not a daemon stall (the daemon was running and finished the queued work under the hood — verified by browser refresh). §2q remains a standalone watcher-side bug. Its 6 hypotheses (H-Q1 through H-Q6) still apply. **The new 23:38 dashboard capture surfaces an adjacent symptom (§2s — Edge Discovery shows spinner but is actually pending; auto-incremental refusing to fire)** that's worth investigating alongside §2q's H-Q3/H-Q4 (debounce-fire silently gated / silently enqueued).
**Found:** 2026-06-18, reported by Eric (dogfooding, Applifier project).
**Severity:** Medium — silent loss of expected automation. The user has Auto-* mode enabled and assumes the watcher is doing its job; for at least 7 hours it has not been. No UI signal that auto fired-and-failed vs never-fired.
**Linked symptom in README:** §2q.

---

## 1. Symptom (as reported, with screenshot details)

Project: **Applifier** (`7cdea5e4-c94d-4612-be67-81597da3d6ec`).

Graph Scope card shows:
- 892 / 901 files traced (99.9%).
- **9 untraced files in queue**, oldest **7h ago**:
  - `Packages/DetectionEngine/JS/tests/lab…` — 6h ago
  - `Packages/DetectionEngine/JS/tests/rul…` — 6h ago
  - `Packages/DetectionEngine/Tests…` — 6h ago, swift tag
  - `design/AppIcon/README.md` — 7h ago, markdown
  - `design/AppIcon/generate_icon…` — 7h ago, Python
  - `docs/Phase34_multivendor_qa…` — 4h ago, markdown ×2
  - `docs/superpowers/plans/2026…` — 3h ago, markdown
- **Last updated: 7h ago.**

Right panel ("Graph Enrichment"):
- Fast Sync header set to **Auto** (highlighted toggle).
- Deep Enrichment header set to **Auto** (highlighted toggle).
- Finalize header set to **Auto** (highlighted toggle).
- All 14 of 15 stages rendered as green check (Immune System is the only `Not run` — that's §2n).

So the project is configured `auto_config.fastSync = true` AND `auto_config.deepEnrichment = "auto"` AND `auto_config.finalize = "auto"`, yet the watcher hasn't fired in 7+ hours despite files being modified that long ago.

The user-stated expectation:

> "There's untracked files multiple hours old, this should have already incrementally run many of those."

## 2. What the screenshot does NOT tell us (needs evidence capture)

The watcher's state is opaque from the dashboard:

- Is the AutoRebuildWatcher actually running for Applifier? `/projects/<id>/watch/status` would say.
- Has the watcher detected the file events at all? File watchers can silently fail (FSEvents permissions, symlink boundaries, network volumes).
- Is the debounce timer firing then deciding "nothing to do"? The watcher's debounce-fire callback consults `auto_config` + budget + scheduler busy state.
- Is the watcher running but every fire is being rejected (e.g., by `_check_incomplete_deep_enrichment` selfheal-gate, by the `cloud:default_ollama` budget being saturated by another project's swarm — see §2p — or by a stale reset-barrier)?

The screenshot also shows the cloud:default_ollama node at 10/10 (DebateHaus is swarming, per §2p). So even *if* the watcher fired, the work might have been silently queued behind the swarm without surface — that's the §2p surfacing bug, not a separate auto-watcher bug. To know which, we need the watcher's actual log entries.

## 3. Hypotheses

### H-Q1 — Watcher never started for this project

Possible if Applifier was added to the registry before the watcher's auto-start path was wired, or if a previous error left the watcher in a half-initialized state. Check `/projects/<id>/watch/status` for `state` and `started_at`.

### H-Q2 — Watcher running but file events are not being received

Mac FSEvents on Thunderbolt-mounted volumes is generally reliable, but project paths under `/Volumes/Thunderbolt/AI/ApplicationBrowser` could be affected by:
- macOS Privacy & Security restrictions on full disk access.
- A symlink crossing the project root that breaks the watch tree.
- The watcher pointing at the wrong path (e.g., the registered path doesn't match the actual project location).

Check: `lsof | grep ApplicationBrowser` should show fseventsd watchers.

### H-Q3 — Watcher receives events but debounce coalesces them then exits silently

`AutoRebuildWatcher._on_debounce_fire` decides whether to trigger a rebuild based on:
- `auto_config.fastSync` true.
- Project not currently building.
- No active reset-barrier or guard rejection markers blocking.
- Budget allows the run.

If any of these gates returns False without logging, the debounce fires, drops the trigger, and resets. The user sees no rebuild and no error.

### H-Q4 — Watcher fires but the run gets enqueued silently behind the swarm

This is the §2p case (`FINDING_two-project-incremental-blocked-during-swarm.md`). If DebateHaus has been swarming for 19+ minutes and other multi-hour swarm windows preceded it today, the watcher could have correctly enqueued multiple fast_sync runs that all sit invisibly waiting. The user's "Last updated: 7h ago" stamp suggests no fast_sync has *completed* in 7h, which is consistent.

### H-Q5 — gitignore / include_globs filtered out the new files post-watch but pre-rebuild

The `Packages/DetectionEngine/JS/tests/...` and `design/AppIcon/...` paths could be excluded by the project's `exclude_globs` or by `.gitignore`. The Graph Scope shows them in the "Untraced" queue, though — so the dashboard's scanner sees them. That suggests they're not filtered. But the watcher and the dashboard's scanner may use different filter logic; need to check.

### H-Q6 — `_check_incomplete_deep_enrichment` self-heal gate is permanently holding off

`src/prep/core/watcher.py:664` has a `_check_incomplete_deep_enrichment` parallel that can hold off fast_sync triggers if it thinks deep_enrichment is incomplete. With Applifier's Immune System stage stuck at `Not run` (§2n), this gate might fire continuously and silently skip the watcher's debounce.

## 4. Diagnostic checklist

```bash
PID=7cdea5e4-c94d-4612-be67-81597da3d6ec
REPO=/Volumes/Thunderbolt/AI/ApplicationBrowser

# 1. Is the watcher actually running for this project?
curl -s http://localhost:8400/projects/$PID/watch/status | python3 -m json.tool

# 2. Confirm auto_config is set to what the toggles imply
curl -s http://localhost:8400/projects/$PID | python3 -c "
import json, sys
data = json.load(sys.stdin)['data']['project']
auto = data['config'].get('auto_config', {})
print('auto_config:', json.dumps(auto, indent=2))
print('auto_rebuild:', json.dumps(data['config'].get('auto_rebuild', {}), indent=2))
"

# 3. Are FSEvents actually attaching to the project root?
lsof 2>/dev/null | grep "$REPO" | head -10

# 4. Manually touch a file and watch for the debounce-fire callback in logs
touch "$REPO/.sourceprep-watcher-probe-$(date +%s)"
LATEST=$(ls -t $REPO/.sourceprep/logs/pipeline_*.log 2>/dev/null | head -1)
sleep 10  # let debounce expire (default 5000ms)
grep -E "watcher|debounce|_on_debounce_fire|_on_coverage_check|_check_incomplete" \
  "$LATEST" 2>/dev/null | tail -20

# 5. Are there reset-barriers or guard rejections preventing the run?
ls -la "$REPO/.sourceprep/.reset_barrier" "$REPO/.sourceprep/.guard_rejections.json" 2>/dev/null

# 6. Cross-check: is the scheduler currently free for cloud:default_ollama?
curl -s http://localhost:8400/system/pipeline-queue | python3 -c "
import json, sys
data = json.load(sys.stdin)['data']
node = data['nodes'].get('cloud:default_ollama', {})
print('cloud current_load:', node.get('current_load'), '/', node.get('max_concurrent'))
print('cloud active:', node.get('active'))
print('cloud queued:', node.get('queued'))
print('global queue:', data.get('queue'))
"

# 7. Most aggressive check: tail the daemon log live during a forced touch
# (requires the daemon to be running with a known log location)
```

Save outputs to `EVIDENCE_dgQ_watcher-state-<timestamp>.md`.

## 5. Design questions for the next review

1. **Should the watcher's "I tried to fire but bailed" decisions be logged at INFO level?** Today many of them are DEBUG or unlogged. A user with Auto mode on has no way to know that the watcher *did* see the file change but decided not to act, vs never saw it.
2. **Should the Graph Scope card surface the watcher's last-fire timestamp + last-decision?** Today the user sees "Last updated: 7h ago" which is the last *completed run* — not "watcher last looked: 2m ago, decided nothing-to-do because (reason)."
3. **Should `_check_incomplete_deep_enrichment` distinguish "stage genuinely incomplete" from "stage produced 0 derivable outputs" (§2n)?** Today they look the same to the gate.
4. **Should the dashboard show a "stale" badge on the Graph Scope card after N hours since last fast_sync, given there are untraced files?** This is a defensive UI signal independent of the watcher's mechanism.
5. **Does the watcher have any backoff / quiet-hours behavior the user wouldn't expect?** If a project triggered N rebuilds in M minutes earlier, is the watcher temporarily silent? (If so, that needs surface.)

## 6. Relationship to other open findings

- **§2p / `FINDING_two-project-incremental-blocked-during-swarm.md`:** very likely paired. If the watcher *did* fire and enqueue, §2p's invisible-queue bug would hide it. Diagnostic checklist §4.6 here cross-references §2p directly.
- **§2n / `FINDING_stage15-antibodies-never-complete.md`:** if the Immune System never-complete state is feeding into `_check_incomplete_deep_enrichment`'s gating (H-Q6), §2n's UI mis-rendering becomes a structural blocker for the watcher.
- **§2o / `FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`:** different shape (orchestrator records spurious success after partial work) but same overall pattern: silent state divergence between what the system reports and what's actually happening.

## 7. Cross-references

- Watcher code: `src/prep/core/watcher.py` (`AutoRebuildWatcher`, `_on_debounce_fire`, `_check_incomplete_deep_enrichment` at line 664, `_on_coverage_check`).
- API routers: `src/prep/api/routers/projects/watch.py` (`/projects/<id>/watch/status`).
- Auto-config gating: `src/prep/services/pipeline/orchestrator.py:_is_fast_sync_auto`, `_is_deep_enrichment_auto`, `_is_finalize_auto` (lines ~1736–1830).
- Budget gating: `src/prep/services/pipeline_budget.py` (referenced from orchestrator auto-chain).
- Recovery markers: `src/prep/services/pipeline/recovery.py` (`reset_barrier_active`, `guard_rejections_present`).
- Related symptoms: §2f (sidebar queue stale), §2p (queue surface absent), §2n (stage 15 never complete).
