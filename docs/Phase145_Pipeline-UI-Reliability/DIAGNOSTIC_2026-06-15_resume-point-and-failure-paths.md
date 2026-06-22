# Phase 145 — Diagnostic plan: nail the resume-point bug and the failure-path inventory

**Status:** Open. Evidence-gathering work item in the Phase 145 corpus — not a "do this next." Tasks DG1–DG7 are the menu; a future orchestrator (likely Fable) picks how many to run and in what order when it picks up the whole Phase 145 bundle.
**Authored:** 2026-06-15 after a scrutiny pass on `PLAN_threads-B-and-C-barrier-and-rollup.md` (now parked).
**Why this exists:** the previous plan's scrutiny exposed five defects (D1–D5 below). Two of them (D1, D3) are diagnostic-shaped, not fix-shaped — we don't yet have the evidence to write a correct plan, and Phase 145's working principle is "document and organize, don't fix yet" (see README §0). This doc enumerates the exact evidence to capture, the exact commands to capture it with, and the questions each piece answers, so that when the future orchestrator gets to §2l it can choose to run these tasks in parallel without rediscovering the question list.

---

## Why the previous plan was parked

Quick recap of the defects so the next reader doesn't have to chase them across docs:

| # | Defect | Shape |
|---|---|---|
| D1 | Thread C misdiagnosed — `provenance.state == "match"` only compares model names, not output presence (`src/prep/services/pipeline_provenance.py:184-191`). The UI rendering "Not run" on Applifier is honest; the real bug is upstream. | **Diagnostic** — need to confirm upstream cause |
| D2 | Thread B test uses `Event.PIPELINE_STARTED` and `Event.STAGE_STARTED` which don't exist in the actual enum (`src/prep/services/pipeline/state_machine.py:112-191` — the real events are `START`, `STAGE_COMPLETED`, `STAGE_FAILED`, etc.). | Mechanical, fixable in the next plan |
| D3 | Thread B's fix in `_on_build_transition`'s FAILED branch misses at least three other failure paths (line 1596 direct STAGE_FAILED, line 2673 Write-Guard-Blocked, lines 2837/2872). | **Diagnostic** — need full failure-path inventory |
| D4 | `packages/ui` has no test runner wired (no vitest in `package.json`, no `test` task in `turbo.json`); the `__tests__/*.test.ts` files are dormant. | Mechanical — vitest install needed *if* any UI test ends up in scope |
| D5 | Plan described `enabled: false` as a config-like flag; it's actually computed from output count (`src/prep/api/routers/pipeline.py:623, 652`). | Documentation only — fixed in §2l README revision |

D1 and D3 dictate this diagnostic pass. D2, D4, D5 are notes for the next plan author.

---

## What we already know (do not re-investigate)

| Fact | Evidence |
|---|---|
| `provenance.state == "match"` only compares manifest model to current-config model. | `src/prep/services/pipeline_provenance.py:160-191`. |
| `epistemic.enabled` in the API response = `enriched_count > 0`, where `enriched_count = _fast_line_count(trace_epistemic.jsonl)`. | `src/prep/api/routers/pipeline.py:600-628`. |
| `_detect_resume_point` delegates to `ResumeStrategy.detect_resume_point` (in `src/prep/services/pipeline/resume.py`). | `src/prep/services/pipeline/orchestrator.py:1724-1734`. |
| The resume detector logs a per-stage decision with `manifest_size` and treats a non-zero manifest as COMPLETE. | `src/prep/services/pipeline/resume.py:467, 512, 539, 822-828`; journal evidence in `pipeline_20260615_214245.log`: `{"stage": "enrichment", "decision": "COMPLETE", "manifest_size": 690}`. |
| Applifier's `trace_epistemic.jsonl` is 0 bytes despite the manifest being 690 bytes. | `ls -la /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/trace_epistemic.jsonl` shows size=0. |
| The reset barrier persists across selfheal cycles because `maybe_clear_scoped_barrier` is only called from `_advance_pipeline`'s success branch (orchestrator.py:2118, 2152, 2166). | grep + read confirmed in the parked plan. |
| `_finalize_run_metadata(run, "completed")` is called at line 2080; there is no `_finalize_run_metadata(run, "failed")` callsite anywhere in the file. | grep on `_finalize_run_metadata` returns only the definition (4787) and one success-path call (2080). |
| `_journal_run_failed` exists (line 3811) and is called from the Write Guard Blocked path (line 2681); it does NOT call `_finalize_run_metadata`. | Read of orchestrator.py around the two callsites. |
| Stub manifests (Phase 72C self-heal restores) are explicitly NOT proof of completion. | `manifest_store.py:149-162` (`is_stub_manifest`). |

These are the lampposts; the dark places are below.

---

## Questions to answer in this pass

### Q1 — On Applifier, what exact sequence produced a 690-byte `trace_epistemic_manifest.json` next to a 0-byte `trace_epistemic.jsonl`?

This is the central question for D1. Three plausible candidates:

- **C1a — `full_reset` wiped the output (jsonl) but left the manifest.** Look at the full_reset wipe list in `src/prep/api/routers/projects/enrichment.py` (or wherever the endpoint lives). If the output file is in the wipe list but the manifest file isn't, that's the bug.
- **C1b — The freshness check skipped the enrichment stage so it ran for 15 s without producing output.** Look at `epistemic_enrichment.py` for an early-return path that writes a manifest without writing the jsonl.
- **C1c — A stub manifest was created by self-heal post-reset.** Check whether the manifest has `restored: true`. If yes, that's the Phase 72C stub manifest pattern, and the resume detector's COMPLETE decision based on `manifest_size > 0` is wrong by design — stubs should not count as complete.

The discrimination between these matters because the fix differs:
- C1a → fix the full_reset wipe list
- C1b → fix the enrichment stage's early-return path to not write a manifest if it produced 0 outputs (or to write a manifest with `output_count: 0` that the resume detector inspects)
- C1c → fix `_detect_resume_point` to reject stub manifests, OR change selfheal to not write stubs for stages where output presence matters

### Q2 — What does the resume detector actually consider for "COMPLETE"?

Read `src/prep/services/pipeline/resume.py`'s `detect_resume_point`. Concretely: what is the decision tree? Does it ever look at output files (jsonl, embeddings.npy) or only at manifest files? Does it skip empty-manifest checks for "always-on" stages? Does it differentiate stub manifests from genuine ones?

If the answer is "manifest size alone, no output check, no stub check" — that's the bug. Output presence is the missing predicate.

### Q3 — Inventory every pipeline failure path

For D3. List every call to `Event.STAGE_FAILED.transition` or any path that leaves the run in `PipelineState.FAILED`. For each, answer: does the path eventually flow through `_on_build_transition`'s FAILED branch (which is where the parked plan tried to fix the barrier-clear), or does it bypass?

Concrete list to investigate:

| Line | What | Does it reach FAILED branch in _on_build_transition? |
|---|---|---|
| `orchestrator.py:1596` | direct `run.transition(Event.STAGE_FAILED, …)` | unknown — read |
| `orchestrator.py:2673` | Write Guard Blocked, inside COMPLETED branch's except | unknown — read |
| `orchestrator.py:2737` | the failure dispatcher inside the FAILED branch | yes (this IS the FAILED branch) |
| `orchestrator.py:2837` | another STAGE_FAILED callsite | unknown — read |
| `orchestrator.py:2872` | another STAGE_FAILED callsite | unknown — read |

The completed inventory answers: is there a single shared hook (`_finalize_run_metadata`-shaped) we should refactor to, or do we need to insert the barrier-clear at every callsite?

### Q4 — Are there other projects in the Applifier-shaped state right now?

Across all registered projects, find any whose `enrichment.enriched_nodes == 0` AND `enrichment.provenance.state == "match"`. That's the manifest-says-complete-but-no-output pattern. If multiple projects exhibit it, the bug is systemic (resume detector's heuristic) rather than Applifier-specific (e.g. a corruption from one particular reset).

### Q5 — Is there any UI signal that already differentiates "complete with output" from "complete but empty"?

Even if the real fix is upstream, the UI could be a helpful safety net. Find out: does the dashboard currently distinguish a stage that completed with 0 output vs N output? If `enriched_nodes` is already wired into the rollup somewhere, the fix might be smaller than expected.

---

## Diagnostic tasks (no code changes — evidence capture only)

### Task DG1: Confirm the Applifier disk state, with hashes

**Goal:** lock the on-disk snapshot so subsequent runs can be compared against it. If Applifier auto-rebuilds during this pass, we want the pre-state captured.

```bash
PID=7cdea5e4-c94d-4612-be67-81597da3d6ec
REPO=/Volumes/Thunderbolt/AI/ApplicationBrowser
IDX=$REPO/.sourceprep

# 1. Manifest vs output sizes for every deep_enrichment stage
for f in trace_epistemic_manifest.json trace_epistemic.jsonl \
         group_reasoning_manifest.json \
         clustering_manifest.json trace_modules.jsonl \
         deepening_manifest.json \
         deep_knowledge_manifest.json knowledge_documents.json \
         atlas_manifest.json atlas.json \
         rules_manifest.json \
         concepts_manifest.json; do
    if [ -f "$IDX/$f" ]; then
        size=$(stat -f%z "$IDX/$f")
        mtime=$(stat -f%Sm "$IDX/$f")
        echo "$f  size=$size  mtime=$mtime"
    else
        echo "$f  ABSENT"
    fi
done

# 2. Is the epistemic manifest a stub?
python3 -c "
import json
m = json.load(open('$IDX/trace_epistemic_manifest.json'))
print('restored:', m.get('restored'))
print('quality:', m.get('quality'))
print('model:', m.get('model'))
print('counts:', m.get('counts'))
"

# 3. Reset barrier + last success
cat $IDX/.reset_barrier 2>/dev/null
cat $IDX/.pipeline_last_success 2>/dev/null

# 4. The full pipeline status, dumped to a file we can diff later
curl -s http://localhost:8400/projects/$PID/pipeline/status \
  > /tmp/applifier_status_$(date +%s).json
```

**Write the output** to `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_applifier-disk-state.md` so the next pass can reference it. Include the timestamps.

### Task DG2: Read `src/prep/services/pipeline/resume.py` end-to-end

**Goal:** answer Q2. We have outputs from the journal (`{"stage": "enrichment", "decision": "COMPLETE", "manifest_size": 690}`) but we don't know the *full* decision tree. Read the actual code.

Specifically write a one-page summary of:

1. The signal sources `detect_resume_point` consults (manifest existence? manifest size? output file existence? output file size? mtime ordering?).
2. Whether stub manifests are detected and excluded.
3. Whether any per-stage overrides exist (e.g. "knowledge embedder skips manifest check").
4. Whether the decision is the same for `fast_sync`, `deep_enrichment`, and `finalize` groups.

Save as `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_resume-detector-decision-tree.md`. Cite line numbers.

### Task DG3: Failure-path inventory

**Goal:** answer Q3. For every place a pipeline run can become terminally failed, document:

1. Line number + the call (`run.transition(Event.STAGE_FAILED, …)`, `_journal_run_failed(…)`, etc.).
2. The trigger condition (worker exception, write-guard rejection, cancel from endpoint, timeout, …).
3. Whether the path subsequently flows through `_on_build_transition`'s FAILED branch (`orchestrator.py:2737`) or bypasses it.
4. Whether any shared cleanup hook (e.g. `_finalize_run_metadata`, `_journal_run_failed`, state-machine `_on_transition` callback) fires for that path.

Save as `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_failure-path-inventory.md`. The output of this task is what the next plan author uses to decide between "insert at every path" vs "factor into a shared hook."

### Task DG4: Cross-project scan for the Applifier shape

**Goal:** answer Q4. Walk every registered project's `.sourceprep/` directory and find ones where the enrichment manifest exists with size > 0 but `trace_epistemic.jsonl` is empty (or absent).

```bash
curl -s http://localhost:8400/projects | python3 -c "
import json, sys, os
data = json.load(sys.stdin)['data']['projects']
for p in data:
    idx = os.path.join(p['path'], '.sourceprep')
    if not os.path.isdir(idx):
        continue
    manifest = os.path.join(idx, 'trace_epistemic_manifest.json')
    output = os.path.join(idx, 'trace_epistemic.jsonl')
    if not os.path.exists(manifest):
        continue
    m_size = os.path.getsize(manifest)
    o_size = os.path.getsize(output) if os.path.exists(output) else None
    flag = '   '
    if m_size > 0 and (o_size == 0 or o_size is None):
        flag = '** '
    print(f'{flag}{p[\"name\"]:30s}  manifest={m_size:>6d}  output={o_size}')
"
```

If multiple `**`-flagged rows appear, the bug is systemic (resume detector + reset interaction), not Applifier-specific. If only Applifier shows it, look for a specific reset event that produced the divergence.

Save findings (+ the project IDs flagged) as `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_cross-project-empty-output-scan.md`.

### Task DG5: Re-trigger the Applifier deep_enrichment with verbose tracing

**Goal:** capture *how* the orchestrator decides PIPELINE_UP_TO_DATE. Run `run_deep_enrichment` once with the daemon's existing log infra and read the result chain.

```bash
PID=7cdea5e4-c94d-4612-be67-81597da3d6ec
LATEST=$(ls -t /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_*.log | head -1)

# Trigger
curl -s -X POST http://localhost:8400/projects/$PID/pipeline/deep -w "\nHTTP: %{http_code}\n"

# Wait a beat, then capture the new entries
sleep 2
NEW=$(ls -t /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_*.log | head -1)
if [ "$NEW" != "$LATEST" ]; then
    echo "New log file: $NEW"
    cat "$NEW"
else
    echo "Same log file as before; check for appended lines"
    tail -100 "$LATEST"
fi

# Also grab the decision event from the journal
grep -E "resume_point|all_complete|COMPLETE|deep_enrichment" "$NEW" 2>/dev/null \
    || grep -E "resume_point|all_complete|COMPLETE|deep_enrichment" "$LATEST"
```

Save the captured log entries as `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_applifier-deep-rerun.md`.

**Expected output if the hypothesis is correct:** a `decision` event with `decision_type: "resume_point", choice: "all_complete"` and per-stage entries showing `manifest_size > 0` for every deep stage. That confirms the resume detector is the upstream signal.

### Task DG6: UI rollup audit for "empty-but-complete" signal

**Goal:** answer Q5. Read `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (specifically the `compute*State` family) and determine:

1. Does any compute function inspect `enriched_nodes`, `module_count`, `total_scored`, etc. when deciding `complete` vs `not_built`?
2. If yes, why does the user see "Not run" on Applifier despite those counts being computed? (Probably because the per-stage `enabled` flag is checked first and returns `disabled` / `not_built` before the count check fires.)
3. If no, is there a simple secondary check we could add later — a "if backend says PIPELINE_UP_TO_DATE but `enriched_nodes == 0`, show a warning chip" — that would catch this class of bug at the UI even if upstream is wrong?

This task is for the NEXT plan to use, not for this pass to act on. Document findings as `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_ui-rollup-audit.md`.

### Task DG7: Synthesis writeup

Once DG1–DG6 are done, write a single synthesis doc — `docs/Phase145_Pipeline-UI-Reliability/SYNTHESIS_2026-06-15_resume-detector-and-failure-paths.md` — that:

1. States the upstream root cause of D1 with evidence (which of C1a/C1b/C1c won).
2. Lists every failure path that needs barrier-clear coverage (from DG3).
3. Proposes the fix shape (one shared hook vs N callsites) with reasoning.
4. Notes which projects (if any) are currently in the Applifier-shaped state.
5. Lists the open follow-ups that didn't fit (e.g., the UI secondary check from DG6).

This synthesis doc is the input the next plan reads from. The next plan can then be written without any of the diagnostic uncertainty that broke this one.

---

## What a future fix-pass will need (notes for the orchestrator)

This is a forward-looking summary so the orchestrator picking up Phase 145 understands the shape of the future fix without re-reading the parked plan. Do NOT treat this as the next plan — DG7's synthesis is the input to that.

1. **Thread B (revised shape):** likely a refactor that adds barrier-clear to a shared hook covering all failure paths from DG3. Test the new hook from each failure-path entry point so a future fifth path doesn't regress it.
2. **Thread C (revised shape):** the real fix — probably in `src/prep/services/pipeline/resume.py`'s `detect_resume_point` or in `pipeline_orchestrator.run_deep_enrichment` — to reject COMPLETE when manifest exists but output is empty. May also want a Phase 72C stub-manifest rejection check.
3. **Thread D (new, optional):** UI safety net — surface a "stage is complete-per-manifest but produced 0 output" warning chip when the backend's count is 0 but provenance is match. Independent of B and C; could ship alone.
4. **Thread A is on a parallel track.** The §2k concurrency-and-work-loss audit waits on its own evidence capture (`FINDING_concurrency-undershoot-and-cross-project-work-loss.md` §4). When the orchestrator bundles fixes, A's evidence pass and DG1–DG7 can run in parallel since they probe disjoint subsystems.

---

## Cross-references

- Parked plan: `PLAN_threads-B-and-C-barrier-and-rollup.md` (this doc supersedes its execution).
- Original symptom catalog: `README.md` §2k (concurrency/work loss) and §2l (UI drift + barrier deadlock + this diagnostic).
- Findings: `FINDING_concurrency-undershoot-and-cross-project-work-loss.md`, `FINDING_reset-barrier-stuck-on-failed-finalize.md`.
- Source pointers cited above: `src/prep/services/pipeline_provenance.py:160-205`, `src/prep/api/routers/pipeline.py:600-660`, `src/prep/services/pipeline/orchestrator.py:1724, 2080, 2118, 2152, 2166, 2737`, `src/prep/services/pipeline/state_machine.py:112-191`, `src/prep/services/pipeline/manifest_store.py:149-162`.
