# 04b — Integration: Atlas Hub & Hot-Zone Decoration

The second Phase 105 integration (Option γ). Companion to
`04_INTEGRATION_TODO_GATING.md`. Added after scrutiny showed the Atlas
is the highest-leverage single consumer — its output is embedded into
AGENTS.md and the ambient MCP response, so every AI agent inherits the
enrichment.

## The core principle

**The Atlas absorbs labels, not numbers.** All raw churn data lives in
the `git_evidence.json` artifact on disk. The Atlas text gains a small,
bounded set of qualitative classifications. This is non-negotiable —
stuffing metrics into the atlas block would undo the compression the
atlas exists to provide.

## Where the hook lands

`src/codrag/core/atlas/generator.py:469` currently emits:

```python
hub_str = ", ".join(f"{p} ({d} edges)" for p, d in hub_files[:5])
```

Replaced with:

```python
hub_str = _format_hub_str_with_evidence(hub_files[:5], evidence)
```

where `_format_hub_str_with_evidence` asks the evidence module to
classify each hub and emits the terse form.

Hub classification helper lives in `git_evidence.py`:

```python
def classify_hub(self, path: str, *, window_days: int = 60) -> str:
    """Return 'stable' | 'evolving' | 'fragile' | 'unknown'."""
```

Thresholds (tunable, dogfood-calibrated):

| Classification | Criteria |
|----------------|----------|
| `stable` | < 3 commits in window |
| `evolving` | 3–15 commits in window |
| `fragile` | > 15 commits in window **and** > 3 distinct authors |
| `unknown` | Not in churn map (new file, excluded, shallow clone) |

`unknown` hubs are formatted the same as today (no label suffix).

## Atlas text shape — concrete before/after

**Today** (from an actual `codrag()` call on this repo):

> Hub dependencies: typing 223 edges, pathlib 168 edges, logging 156 edges, json 153 edges.

**Option γ v1 (grouped by label, no counts):**

> Hub dependencies *(stable)*: typing, pathlib, logging, json.
> Hub dependencies *(evolving)*: backend_config.py, pipeline/orchestrator.py.

**Rejected shape (stats dump):**

> Hub dependencies: typing (223 edges, 0 commits 60d), pathlib (168 edges, 2 commits 60d), …

The rejected shape is exactly what the Atlas must not become. Token
budget must stay tight; users / agents who want numbers query the
evidence artifact.

## Hot zones section

New single line added to `cross_cutting` text in `_generate_root_atlas`
(generator.py:465+):

> Active zones (60d): `src/codrag/api/routers/projects/`, `src/codrag/services/pipeline/`, `src/codrag/dashboard/src/hooks/`.

**Rules:**

- At most **5** directory paths.
- Directory paths only, no commit counts.
- Directories selected by summed commit count in window, descending.
- Exclude CoDRAG-managed paths (same exclusion list as TODO gating).
- Hidden entirely if fewer than 3 qualifying directories exist.
- Deterministic ordering.

## What becomes possible downstream

These are **not** Phase 105 deliverables — listing so the ripple is
visible:

- MCP ambient response automatically inherits labeled hubs + hot zones
  (because atlas text is what the ambient `codrag()` call returns).
- AGENTS.md generation automatically inherits the labels (same source).
- Dashboard "Atlas" panel reads the same AtlasDocument and can style
  the label prefix if desired (not required for Phase 105).

One atlas enrichment → three surfaces benefit with zero extra work.

## Deterministic, not LLM-generated

Critical: the labels are **computed**, not produced by the atlas's
LLM summarization pass. They are injected into the formatted hub
string after the LLM-generated prose is assembled (or into the
deterministic `_generate_root_atlas` path, which does not use LLM
for the hub line).

Reasons:

- Stability. The same repo on the same HEAD produces the same labels.
- Auditability. Threshold logic is explicit, inspectable, adjustable.
- Cost. No extra LLM tokens.
- Honesty. LLM cannot hallucinate a classification that doesn't match
  the churn data.

## Feature flag

`settings.git_evidence.atlas_decoration` — independent of the TODO
gate flag so one can be toggled without the other. Default: `true`
after shipping.

If `git_evidence` returns no churn data (not a git repo, shallow
clone, disabled), atlas generator falls back to today's format. Zero
regression path.

## What doesn't change

- `_identify_hubs` logic — still purely structural.
- Hub ordering — still by edge count.
- Number of hubs surfaced — still 5.
- Atlas schema — no new fields in `AtlasDocument`. Labels are in the
  existing `hub_files` text field and `cross_cutting` text field.
- LLM prompts for atlas generation — unchanged.
- AGENTS.md template — unchanged (it reads from AtlasDocument).
- Dashboard — no changes required.

## Testing

1. **Unit:** `classify_hub` threshold tests with synthetic churn maps.
2. **Unit:** `_format_hub_str_with_evidence` with mixed-label inputs.
3. **Unit:** hot-zone selection — capped at 5, sorted correctly,
   excluded paths skipped.
4. **Fixture-repo integration:** build an atlas against a fixture repo,
   assert the hub line and cross-cutting line contain expected labels.
5. **Fallback:** evidence disabled → atlas output matches current
   format byte-for-byte for unchanged repos (golden file test).
6. **Dogfood:** run atlas against this repo, eyeball. Check that
   `pipeline/orchestrator.py` ends up `fragile` or `evolving` (known
   high churn), `typing`/`pathlib` end up `stable`.

## Acceptance gate

On this repo, after build:

1. Atlas hub line contains at least one `stable` and one `evolving`
   classification that Eric agrees with on manual inspection.
2. "Active zones" line appears with at least 2 directories that match
   actual recent work.
3. Atlas total token count increases by **< 50 tokens** compared to
   pre-Phase-105 baseline.
4. With `atlas_decoration=false`, atlas output matches the baseline
   byte-for-byte.
