# Part 12 — Group Reasoning cache invalidates on any membership shift

> **Status:** **FIXED 2026-05-18** — Jaccard-overlap fallback added,
> 11 regression tests landed.
> **Trigger:** 2026-05-18 dogfood — dashboard Group Reasoning bar
> showed ~90% orange (stale) on a 54-added-file incremental run.
> **Work order:** insert between Part 10 and Part 09 (Python-only,
> contained fix).

## The bug

`src/prep/core/group_reasoning.py:765` (pre-fix):

```python
gid = "group:" + hashlib.md5(
    "|".join(sorted(members)).encode()
).hexdigest()[:10]
```

The group's stable ID is the hash of its **exact sorted member list**.
Adding even one new file to a group → new hash → new gid →
`existing.get(new_gid)` returns `None` → `_group_is_stale` is never
consulted → group routed to `to_analyze` → forced full re-analysis.

The Phase 135 changeset gating in `_group_is_stale` would have
correctly skipped the analysis (0 modified, 0 deleted files mean
nothing is stale), but **the changeset check is only reached when the
exact-gid lookup hits**.

## Dogfood evidence

2026-05-18, SourcePrep repo:

```
changeset: added=54, modified=0, deleted=0
prior trace_group_reasoning.jsonl: 109 groups, mean ~10 members each
dashboard: Group Reasoning at 1% progress, two-tone bar showing
  ~10% green (carry-forward) + ~90% orange (stale)
```

Of 109 groups, only **11** had member sets that the new run reproduced
exactly. The other **98** had at least one new file join them (the 54
added files spread across the dependency graph), every join changed
the hash, every changed hash invalidated the cached entry.

## Why a stable-anchor fix doesn't work

Initial fix attempt anchored the gid on the 3 lexicographically-
smallest members. Caught by tests:

- `file:docs/X.md` sorts BEFORE `file:src/prep/core/a.py` because
  `d` < `s` in the path string.
- Adding a `docs/` file to a group whose anchors were all in `src/`
  → new anchor → new gid → cache miss.

For SourcePrep specifically, `docs/`, `packages/`, `src/`, `tests/`,
`websites/` are all common path prefixes. New files in lower-sorted
prefixes are routine. The anchor strategy was too fragile.

## The shipped fix — Jaccard-overlap fallback

`_stable_group_id` keeps the legacy formula (full-sorted-member hash)
for **on-disk format compatibility** — the gid in
`trace_group_reasoning.jsonl` doesn't change.

`_find_overlapping_entry` is a new fallback used when the exact-gid
lookup misses. It scans `existing` and returns the entry whose member
set has ≥ 70 % **symmetric Jaccard overlap** with the new group.

Symmetric Jaccard:

```python
score = min(intersection / len(new_set), intersection / len(old_set))
```

Both halves must clear the threshold so a tiny subset can't match its
parent and vice versa.

Call-site change in `run()`:

```python
ex = existing.get(gid)
if ex is None:
    _legacy_gid, ex = _find_overlapping_entry(members, existing)
if ex is not None and not self._group_is_stale(members):
    reuse[gid] = ex
else:
    to_analyze.append((gid, members))
```

Cost: O(N²) per run where N = group count (~100-1000). For SourcePrep
that's < 12 000 set operations — milliseconds. Acceptable.

## Tests

`tests/test_group_id_stability.py` — 11 new tests:

- `TestStableGroupIdFormat` (3): id format, intentional instability,
  caller-side ordering doesn't matter.
- `TestFindOverlappingEntry` (8): exact match, peripheral-add-within-
  threshold matches, realistic-incremental-shift matches, large-shift-
  below-threshold-doesn't-match, empty-input safety, empty-existing
  safety, picks-best-among-multiple, asymmetric-overlap-rejects-subset.

All 26 group_reasoning tests pass (11 new + 15 existing).

## Expected post-fix behavior

After this fix lands and the daemon picks up the new Python code:

- Same 54-added-file run: ~95-100 of 109 groups carry forward (the
  ones whose member sets are still > 70 % overlapping with their
  cached counterparts). Only ~5-10 groups genuinely need re-analysis.
- Dashboard bar: small orange (stale) wedge, big green (carry-forward)
  body — matches user intuition.
- Compute saved: ~90 LLM calls avoided per incremental run.

## Parallel finding (out of scope for Part 12)

`src/prep/core/cluster.py` uses `cluster_id = f"cluster:{tag}:{idx}"`
where `idx` is a sequential counter assigned during a single run. If
the count of clusters with the same tag shifts between runs, all
those indices renumber → similar cache invalidation pattern, less
hash-sensitive but still real. Flagged as Part 12b — separate
investigation needed.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/` — methodology baseline
- Phase 135 changeset cutover (the `_group_is_stale` check this Part
  unblocks)
- `00_Status_2026-05-17.md` — pipeline behavior snapshot
- User dogfood screenshots 2026-05-18 (Fast Catalogue + Group
  Reasoning bars)
